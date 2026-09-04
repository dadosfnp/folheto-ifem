"""
Gera os JSONs de entrada do folheto lendo direto as planilhas oficiais.

POR QUE ESTE SCRIPT EXISTE
O caminho normal é `export_folheto_municipios.py` (Subfinanciados), que lê do
banco PostgreSQL. Esse banco só aceita conexão de dentro da VPC da DigitalOcean,
então não há como rodá-lo de uma máquina de trabalho.

As planilhas em `base_datas/` são a MESMA fonte que popula aquele banco — os
comandos `01_importar_municipios.py` a `09_*` apenas as carregam em tabelas. Ler
as planilhas direto produz os mesmos números, sem banco, sem rede e sem escrever
nada no Subfinanciados (que é read-only para este projeto).

FIDELIDADE
A saída replica `build_municipio_payload()` campo a campo, incluindo:
  - rankings de receita RECALCULADOS com pandas (o import oficial ignora as
    colunas `rank_receita_*` da planilha e recalcula — ver 01_importar_municipios.py:36)
  - `supera_pct_nacional` por rubrica via bisect sobre todos os municípios
    (replica compute_percentis_por_categoria)
  - rubricas com valor 0 ou ausente são omitidas, como no original

As CHAVES do JSON mantêm o sufixo `_2024` (`sintese_fiscal_2000_2024`,
`posicao_historica.ano_2024`) mesmo com dados de 2025. É contrato interno lido
por `python/temas/ifem.py`; renomear quebraria o gerador sem ganho. O ano que o
leitor vê vem de ANO_REF, não dessas chaves.

USO
    python tools/planilhas_para_json.py                 # só o recorte de docs/folhetos.json
    python tools/planilhas_para_json.py --todos         # os 5.4k municípios
    python tools/planilhas_para_json.py --cod-ibge 3304557,2304400
    python tools/planilhas_para_json.py --dry-run       # não escreve, só relata
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("Falta 'pandas'. Rode: pip install -r requirements.txt")

ROOT_DIR = Path(__file__).resolve().parent.parent
DESTINO = ROOT_DIR / "data" / "ifem" / "dados-ifem" / "export_folheto"
RECORTE_JSON = ROOT_DIR / "docs" / "folhetos.json"
COMPANHEIROS_DIR = ROOT_DIR / "data" / "ifem"

# Companheiros que são TEXTO EDITORIAL, não dado calculado: nenhuma planilha os
# origina, então este script não tem como gerá-los. Vivem versionados em
# `data/ifem/` e são copiados para o lote. A lista é o contrato: companheiro
# editorial novo entra aqui, não numa cópia manual em algum lugar.
COMPANHEIROS_EDITORIAIS = ("_problema.json", "_metodologia.json")


# --------------------------------------------------------------------------
# Configuração (.env)
# --------------------------------------------------------------------------

def carrega_env() -> dict:
    """Lê o .env da raiz. Sem dependência externa — o formato é trivial."""
    env = {}
    p = ROOT_DIR / ".env"
    if p.exists():
        for linha in p.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.split("=", 1)
            env[k.strip()] = v.strip()
    return env


_ENV = carrega_env()
PLANILHAS_DIR = Path(os.getenv("PLANILHAS_DIR") or _ENV.get("PLANILHAS_DIR", ""))
ANO_REF = int(os.getenv("ANO_REF") or _ENV.get("ANO_REF", "2025"))


# --------------------------------------------------------------------------
# Mapeamentos — espelham export_folheto_municipios.py
# --------------------------------------------------------------------------

GRUPOS_PRINCIPAIS = [
    ("imposto_taxas_contribuicoes", "Impostos, Taxas e Contribuições de Melhoria"),
    ("contribuicoes", "Contribuições"),
    ("transferencias_correntes", "Transferências Correntes"),
    ("outras_receita", "Outras Receitas"),
]

# coluna da planilha -> field do JSON (nível 1)
COL_NIVEL_1 = {
    "itc": "imposto_taxas_contribuicoes",
    "con": "contribuicoes",
    "trf": "transferencias_correntes",
    "our": "outras_receita",
}

DETALHE_ESPECIFICA = [
    ("imposto", "Impostos"),
    ("taxas", "Taxas"),
    ("contribuicoes_melhoria", "Contribuições de Melhoria"),
    ("contribuicoes_sociais", "Contribuições Sociais"),
    ("contribuicoes_iluminacao_publica", "Contribuição de Iluminação Pública"),
    ("outras_contribuicoes", "Outras Contribuições"),
    ("tranferencias_uniao", "Transferências da União"),
    ("tranferencias_estados", "Transferências dos Estados"),
    ("outras_tranferencias", "Outras Transferências"),
    ("receita_patrimonial", "Receita Patrimonial"),
    ("receita_agropecuaria", "Receita Agropecuária"),
    ("receita_industrial", "Receita Industrial"),
    ("receita_servicos", "Receita de Serviços"),
    ("outras_receitas", "Outras Receitas"),
]

COL_NIVEL_2 = {
    "itc_imp": "imposto",
    "itc_tax": "taxas",
    "itc_con": "contribuicoes_melhoria",
    "con_soc": "contribuicoes_sociais",
    "con_ipl": "contribuicoes_iluminacao_publica",
    "con_our": "outras_contribuicoes",
    "trf_uni": "tranferencias_uniao",
    "trf_est": "tranferencias_estados",
    "trf_our": "outras_tranferencias",
    "our_pat": "receita_patrimonial",
    "our_agr": "receita_agropecuaria",
    "our_ind": "receita_industrial",
    "our_ser": "receita_servicos",
    "our_our": "outras_receitas",
}

DETALHE_MAIS_ESPECIFICA = [
    ("iptu", "IPTU"),
    ("itbi", "ITBI"),
    ("iss", "ISS"),
    ("imposto_renda", "Imposto de Renda"),
    ("imposto_icms", "ICMS"),
    ("imposto_ipva", "IPVA"),
    ("outros_impostos", "Outros Impostos"),
    ("taxa_policia", "Taxa de Polícia"),
    ("taxa_prestacao_servico", "Taxa de Prestação de Serviço"),
    ("outras_taxas", "Outras Taxas"),
    ("contribuicao_melhoria_pavimento_obras", "Contribuição de Melhoria - Pavimentação/Obras"),
    ("contribuicao_melhoria_agua_potavel", "Contribuição de Melhoria - Água Potável"),
    ("contribuicao_melhoria_iluminacao_publica", "Contribuição de Melhoria - Iluminação Pública"),
    ("outras_contribuicoes_melhoria", "Outras Contribuições de Melhoria"),
    ("transferencia_uniao_fpm", "Transferência União - FPM"),
    ("transferencia_uniao_exploracao", "Transferência União - Royalties"),
    ("transferencia_uniao_sus", "Transferência União - SUS"),
    ("transferencia_uniao_fnde", "Transferência União - FNDE"),
    ("transferencia_uniao_fundeb", "Transferência União - FUNDEB"),
    ("transferencia_uniao_fnas", "Transferência União - FNAS"),
    ("transferencia_uniao_fpe", "Transferência União - FPE"),
    ("outras_transferencias_uniao", "Outras Transferências da União"),
    ("transferencia_estado_icms", "Transferência Estado - ICMS"),
    ("transferencia_estado_ipva", "Transferência Estado - IPVA"),
    ("transferencia_estado_exploracao", "Transferência Estado - Royalties"),
    ("transferencia_estado_sus", "Transferência Estado - SUS"),
    ("transferencia_estado_assistencia", "Transferência Estado - Assistência"),
    ("outras_transferencias_estado", "Outras Transferências do Estado"),
]

COL_NIVEL_3 = {
    "itc_imp_ptu": "iptu",
    "itc_imp_tbi": "itbi",
    "itc_imp_ser": "iss",
    "itc_imp_rnd": "imposto_renda",
    "itc_imp_cms": "imposto_icms",
    "itc_imp_pva": "imposto_ipva",
    "itc_imp_our": "outros_impostos",
    "itc_tax_pol": "taxa_policia",
    "itc_tax_ser": "taxa_prestacao_servico",
    "itc_tax_our": "outras_taxas",
    "itc_con_pav": "contribuicao_melhoria_pavimento_obras",
    "itc_con_age": "contribuicao_melhoria_agua_potavel",
    "itc_con_ipl": "contribuicao_melhoria_iluminacao_publica",
    "itc_con_our": "outras_contribuicoes_melhoria",
    "trf_uni_fpm": "transferencia_uniao_fpm",
    "trf_uni_exp": "transferencia_uniao_exploracao",
    "trf_uni_sus": "transferencia_uniao_sus",
    "trf_uni_fnd": "transferencia_uniao_fnde",
    "trf_uni_fun": "transferencia_uniao_fundeb",
    "trf_uni_fna": "transferencia_uniao_fnas",
    "trf_uni_fpe": "transferencia_uniao_fpe",
    "trf_uni_our": "outras_transferencias_uniao",
    "trf_est_icm": "transferencia_estado_icms",
    "trf_est_ipv": "transferencia_estado_ipva",
    "trf_est_exp": "transferencia_estado_exploracao",
    "trf_est_sus": "transferencia_estado_sus",
    "trf_est_ass": "transferencia_estado_assistencia",
    "trf_est_our": "outras_transferencias_estado",
}

PARENT_DE_NIVEL_2 = {
    "imposto": "imposto_taxas_contribuicoes",
    "taxas": "imposto_taxas_contribuicoes",
    "contribuicoes_melhoria": "imposto_taxas_contribuicoes",
    "contribuicoes_sociais": "contribuicoes",
    "contribuicoes_iluminacao_publica": "contribuicoes",
    "outras_contribuicoes": "contribuicoes",
    "tranferencias_uniao": "transferencias_correntes",
    "tranferencias_estados": "transferencias_correntes",
    "outras_tranferencias": "transferencias_correntes",
    "receita_patrimonial": "outras_receita",
    "receita_agropecuaria": "outras_receita",
    "receita_industrial": "outras_receita",
    "receita_servicos": "outras_receita",
    "outras_receitas": "outras_receita",
}

PARENT_DE_NIVEL_3 = {
    "iptu": "imposto", "itbi": "imposto", "iss": "imposto",
    "imposto_renda": "imposto", "imposto_icms": "imposto",
    "imposto_ipva": "imposto", "outros_impostos": "imposto",
    "taxa_policia": "taxas", "taxa_prestacao_servico": "taxas", "outras_taxas": "taxas",
    "contribuicao_melhoria_pavimento_obras": "contribuicoes_melhoria",
    "contribuicao_melhoria_agua_potavel": "contribuicoes_melhoria",
    "contribuicao_melhoria_iluminacao_publica": "contribuicoes_melhoria",
    "outras_contribuicoes_melhoria": "contribuicoes_melhoria",
    "transferencia_uniao_fpm": "tranferencias_uniao",
    "transferencia_uniao_exploracao": "tranferencias_uniao",
    "transferencia_uniao_sus": "tranferencias_uniao",
    "transferencia_uniao_fnde": "tranferencias_uniao",
    "transferencia_uniao_fundeb": "tranferencias_uniao",
    "transferencia_uniao_fnas": "tranferencias_uniao",
    "transferencia_uniao_fpe": "tranferencias_uniao",
    "outras_transferencias_uniao": "tranferencias_uniao",
    "transferencia_estado_icms": "tranferencias_estados",
    "transferencia_estado_ipva": "tranferencias_estados",
    "transferencia_estado_exploracao": "tranferencias_estados",
    "transferencia_estado_sus": "tranferencias_estados",
    "transferencia_estado_assistencia": "tranferencias_estados",
    "outras_transferencias_estado": "tranferencias_estados",
}

LABEL_NIVEL_1 = dict(GRUPOS_PRINCIPAIS)
LABEL_NIVEL_2 = dict(DETALHE_ESPECIFICA)
LABEL_NIVEL_3 = dict(DETALHE_MAIS_ESPECIFICA)

# field -> coluna da planilha (inverso dos COL_NIVEL_*), usado nas médias.
FIELD_PARA_COL = {v: k for k, v in {**COL_NIVEL_1, **COL_NIVEL_2, **COL_NIVEL_3}.items()}

# Lista de rubricas do _medias_receitas.json. São 43, não 46: o export oficial
# omite ICMS, IPVA e FPE das médias (ver RUBRICAS em export_folheto_complementares.py).
# A ordem e os labels são os de lá — inclusive "Outras Receitas (Nível 2)", que
# difere do label usado no payload municipal.
RUBRICAS_MEDIAS = (
    [(f, l, "nivel_1") for f, l in GRUPOS_PRINCIPAIS]
    + [(f, "Outras Receitas (Nível 2)" if f == "outras_receitas" else l, "nivel_2")
       for f, l in DETALHE_ESPECIFICA]
    + [(f, l, "nivel_3") for f, l in DETALHE_MAIS_ESPECIFICA
       if f not in ("imposto_icms", "imposto_ipva", "transferencia_uniao_fpe")]
)

PORTES_VALIDOS = [
    "Até 5 mil", "5 mil a 10 mil", "10 mil a 20 mil", "20 mil a 50 mil",
    "50 mil a 100 mil", "100 mil a 200 mil", "200 mil a 500 mil", "Acima de 500 mil",
]


# --------------------------------------------------------------------------
# Helpers (espelham os do export oficial)
# --------------------------------------------------------------------------

def slugify(value: str) -> str:
    if value is None:
        return ""
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "sem-nome"


def faixa_porte_label(pop) -> str:
    pop = int(pop or 0)
    if pop < 5000: return "Até 5 mil"
    if pop < 10000: return "5 mil a 10 mil"
    if pop < 20000: return "10 mil a 20 mil"
    if pop < 50000: return "20 mil a 50 mil"
    if pop < 100000: return "50 mil a 100 mil"
    if pop < 200000: return "100 mil a 200 mil"
    if pop < 500000: return "200 mil a 500 mil"
    return "Acima de 500 mil"


def rank(curr, total):
    if curr is None or total is None or pd.isna(curr) or pd.isna(total):
        return None
    return {"posicao": int(curr), "total": int(total)}


def delta_pct(novo, antigo):
    if not antigo or not novo or antigo <= 0:
        return None
    return round(((novo / antigo) - 1) * 100, 2)


def num(v):
    """NaN/NaT do pandas -> None; numpy scalar -> tipo nativo do Python."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


def percentil_numero(label):
    """'40º percentil' -> 40. Replica o str.extract(r'(\\d+)') do import oficial."""
    if label is None or pd.isna(label):
        return None
    m = re.search(r"(\d+)", str(label))
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------
# Carga das planilhas
# --------------------------------------------------------------------------

def carregar_planilhas() -> dict:
    """Lê todas as planilhas necessárias e normaliza chaves/colunas."""
    if not PLANILHAS_DIR or not PLANILHAS_DIR.is_dir():
        sys.exit(
            f"Pasta de planilhas não encontrada: {PLANILHAS_DIR or '(vazia)'}\n"
            f"Defina PLANILHAS_DIR no .env (veja .env.example)."
        )

    def ler(nome, obrigatoria=True):
        p = PLANILHAS_DIR / nome
        if not p.exists():
            if obrigatoria:
                sys.exit(f"Planilha obrigatória ausente: {p}")
            return None
        df = pd.read_excel(p)
        df.columns = df.columns.str.lower()
        if "cod_ibge" in df.columns:
            df["cod_ibge"] = df["cod_ibge"].astype(str).str.strip()
        return df

    print("Lendo planilhas...")
    dfs = {
        "pop": ler("populacao.xlsx"),
        "rec": ler(f"receitas_correntes_{ANO_REF}.xlsx"),
        "rec00": ler("receitas_correntes_2000.xlsx"),
        "n1": ler("receitas_correntes_detalhamento_n1.xlsx"),
        "n2": ler("receitas_correntes_detalhamento_n2.xlsx"),
        "perc0": ler("percentil_detalhamento_0.xlsx"),
        "perc1": ler("percentil_detalhamento_1.xlsx"),
        "perc2": ler("percentil_detalhamento_2.xlsx"),
    }
    for k, df in dfs.items():
        print(f"  {k:6s} {len(df):>6,} linhas")

    # RM é .xls antigo e opcional: sem ela o campo fica None, como para os ~84%
    # de municípios que não pertencem a região metropolitana nenhuma.
    rm_map = {}
    p_rm = PLANILHAS_DIR / "Composicao_RM_2023.xls"
    if p_rm.exists():
        try:
            df_rm = pd.read_excel(p_rm)
            df_rm.columns = df_rm.columns.str.lower()
            df_rm["cod_ibge"] = df_rm["cod_ibge"].astype(str).str.strip()
            rm_map = dict(zip(df_rm["cod_ibge"], df_rm["rm"]))
            print(f"  rm     {len(rm_map):>6,} municípios com região metropolitana")
        except Exception as e:
            print(f"  [aviso] não consegui ler {p_rm.name}: {e}", file=sys.stderr)
            print("          'regiao_metropolitana' sairá null em todos.", file=sys.stderr)
    else:
        print(f"  [aviso] {p_rm.name} ausente — 'regiao_metropolitana' sairá null.",
              file=sys.stderr)
    dfs["rm_map"] = rm_map
    return dfs


def montar_base(dfs: dict) -> pd.DataFrame:
    """
    Junta as planilhas e recalcula rankings — replicando 01_importar_municipios.py.

    Os rankings de receita NÃO são lidos das colunas `rank_receita_*` da planilha:
    o import oficial os recalcula com pandas (linha 36 de 01_importar_municipios.py),
    e é esse número que aparece nos folhetos publicados.
    """
    pop, rec, rec00 = dfs["pop"].copy(), dfs["rec"].copy(), dfs["rec00"].copy()

    # Rankings de 2000 (o import oficial também recalcula estes).
    rec00["rank_nacional00"] = rec00["receita_00_pc"].rank(method="min", ascending=False)
    rec00["total_nacional00"] = len(rec00)
    rec00["percentil00_n"] = rec00["percentil00"].astype(str).str.extract(r"(\d+)", expand=False)

    # Precisa de uf/faixas para os rankings estadual e por porte.
    rec = rec.merge(pop[["cod_ibge", "uf", "faixas"]], on="cod_ibge", how="left")
    rec["rank_nacional"] = rec["receita_pc"].rank(method="min", ascending=False)
    rec["total_nacional"] = len(rec)
    rec["rank_estadual"] = rec.groupby("uf")["receita_pc"].rank(method="min", ascending=False)
    rec["total_estadual"] = rec.groupby("uf")["uf"].transform("count")
    rec["rank_faixa"] = rec.groupby("faixas")["receita_pc"].rank(method="min", ascending=False)
    rec["total_faixa"] = rec.groupby("faixas")["faixas"].transform("count")
    rec["percentil_n"] = rec["percentil"].astype(str).str.extract(r"(\d+)", expand=False)

    base = pop.merge(rec.drop(columns=["uf", "faixas"], errors="ignore"),
                     on="cod_ibge", how="left")
    base = base.merge(rec00, on="cod_ibge", how="left")
    base = base.merge(dfs["n1"], on="cod_ibge", how="left")
    base = base.merge(dfs["n2"], on="cod_ibge", how="left")
    return base


def montar_percentis_planilha(dfs: dict) -> dict:
    """cod_ibge -> {col: percentil} lendo perc_<col>_pc_nac de percentil_detalhamento_0/1/2."""
    todas_colunas = {**COL_NIVEL_1, **COL_NIVEL_2, **COL_NIVEL_3}
    resultado: dict[str, dict] = {}
    for chave in ("perc0", "perc1", "perc2"):
        df = dfs[chave]
        for col in todas_colunas:
            offcol = f"perc_{col}_pc_nac"
            if offcol not in df.columns:
                continue
            for cod, pct in zip(df["cod_ibge"], df[offcol]):
                if pd.isna(pct):
                    continue
                resultado.setdefault(cod, {})[col] = pct
    return resultado


def computar_percentis(base: pd.DataFrame, percentis_planilha: dict) -> dict:
    """
    supera_pct_nacional por rubrica.

    Lê diretamente as colunas `perc_<col>_pc_nac` de percentil_detalhamento_0/1/2.xlsx
    em vez de recalcular. Essas planilhas SÃO a fonte oficial do percentil (o mesmo
    processo que gera o banco Subfinanciados as produz) — recalcular via bisect sobre
    per_capita não reproduzia esses números com fidelidade: municípios com valor 0 na
    rubrica entram ou não na base de comparação e o arredondamento não é round() nem
    ceil() de forma consistente, dependendo da rubrica. Ler o valor já pronto evita
    reproduzir essa regra às cegas.

    `total` (total_municipios_comparados, só informativo — não é lido pelo gerador de
    PDF) é a contagem de municípios com população positiva e valor da rubrica > 0.
    """
    todas_colunas = {**COL_NIVEL_1, **COL_NIVEL_2, **COL_NIVEL_3}
    resultado: dict[str, dict] = {}

    for col, field in todas_colunas.items():
        if col not in base.columns:
            continue
        sub = base[["cod_ibge", "populacao_25", col]].dropna(subset=[col])
        sub = sub[(sub["populacao_25"] > 0) & (sub[col] > 0)]
        total = len(sub)
        if total == 0:
            continue
        for cod in sub["cod_ibge"]:
            pct = percentis_planilha.get(cod, {}).get(col)
            if pct is None:
                continue
            resultado.setdefault(cod, {})[field] = {"supera_pct": int(pct), "total": total}
    return resultado


# --------------------------------------------------------------------------
# Montagem do payload
# --------------------------------------------------------------------------

def _rubricas(row, colunas_map, labels, pop, percentis) -> list:
    """Serializa um nível de rubricas. Omite valor ausente ou zero, como o original."""
    itens = []
    for col, field in colunas_map.items():
        v = num(row.get(col))
        if v is None or v == 0:
            continue
        item = {
            "rubrica": labels[field],
            "field": field,
            "valor_absoluto": round(v, 2),
            "per_capita": round(v / pop, 2) if pop else None,
        }
        if percentis and field in percentis:
            item["supera_pct_nacional"] = percentis[field]["supera_pct"]
            item["total_municipios_comparados"] = percentis[field]["total"]
        itens.append(item)
    return itens


def build_payload(row, percentis_do_muni, rm_map, medias_nacionais) -> dict:
    pop = num(row.get("populacao_25"))
    cod = str(row["cod_ibge"])

    resumo = _rubricas(row, COL_NIVEL_1, LABEL_NIVEL_1, pop, percentis_do_muni)
    resumo.sort(key=lambda x: x["valor_absoluto"], reverse=True)

    rc_pc = num(row.get("receita_pc"))
    rc00_pc = num(row.get("receita_00_pc"))
    pop00 = num(row.get("populacao_00"))

    return {
        "identificacao": {
            "cod_ibge": cod,
            "municipio": row.get("nome_muni"),
            "uf": row.get("uf"),
            "name_muni_uf": f"{row.get('nome_muni')} - {row.get('uf')}",
            "regiao": row.get("regiao"),
            "regiao_metropolitana": rm_map.get(cod),
            "porte": faixa_porte_label(pop),
            "coordenadas": {"x": num(row.get("coordx")), "y": num(row.get("coordy"))},
        },
        "populacao": {
            "ano": ANO_REF,
            "valor": pop,
            "ranking_nacional": rank(num(row.get("rank_pop_nac")), num(row.get("total_nac_pop"))),
            "ranking_estadual": rank(num(row.get("rank_pop_uf")), num(row.get("total_uf_pop"))),
            "ranking_por_porte": rank(num(row.get("rank_pop_faixas")), num(row.get("total_fax_pop"))),
        },
        "receita_corrente": {
            "ano": ANO_REF,
            "valor_absoluto": num(row.get("receita")),
            "per_capita": rc_pc,
            "ranking_por_per_capita": {
                "nacional": rank(num(row.get("rank_nacional")), num(row.get("total_nacional"))),
                "estadual": rank(num(row.get("rank_estadual")), num(row.get("total_estadual"))),
                "por_porte": rank(num(row.get("rank_faixa")), num(row.get("total_faixa"))),
            },
        },
        "sus_dependente": {
            "percentual_populacao": num(row.get("dependencia_sus")),
            "descricao": "Percentual da populacao dependente exclusivamente do SUS.",
        },
        "cadunico": {
            "qtd_pessoas_cadastradas": num(row.get("pop_cadunico_25")),
            "ranking_nacional": rank(num(row.get("rank_cadunico_nac")), num(row.get("total_nac_cad"))),
            "ranking_estadual": rank(num(row.get("rank_cadunico_uf")), num(row.get("total_uf_cad"))),
            "ranking_por_porte": rank(num(row.get("rank_cadunico_faixas")), num(row.get("total_fax_cad"))),
        },
        "percentil": {
            "ano": ANO_REF,
            "percentil_label": row.get("percentil") if not pd.isna(row.get("percentil")) else None,
            "percentil_numero": percentil_numero(row.get("percentil")),
            "quintil": row.get("quintil") if not pd.isna(row.get("quintil")) else None,
            "decil": row.get("decil") if not pd.isna(row.get("decil")) else None,
        },
        "estrutura_receita_resumo": resumo,
        "estrutura_receita_detalhada": {
            "nivel_2_categorias": _rubricas(row, COL_NIVEL_2, LABEL_NIVEL_2, pop, percentis_do_muni),
            "nivel_3_rubricas": _rubricas(row, COL_NIVEL_3, LABEL_NIVEL_3, pop, percentis_do_muni),
        },
        "hierarquia_receitas": {
            "nivel_1": [{"field": f, "label": l} for f, l in GRUPOS_PRINCIPAIS],
            "nivel_2": [{"field": f, "label": l, "parent_field": PARENT_DE_NIVEL_2.get(f)}
                        for f, l in DETALHE_ESPECIFICA],
            "nivel_3": [{"field": f, "label": l, "parent_field": PARENT_DE_NIVEL_3.get(f)}
                        for f, l in DETALHE_MAIS_ESPECIFICA],
        },
        # Chave mantida com sufixo 2024: é contrato lido por python/temas/ifem.py.
        "sintese_fiscal_2000_2024": {
            "delta_receita_per_capita_pct": delta_pct(rc_pc, rc00_pc),
            "delta_populacao_pct": delta_pct(pop, pop00),
            "media_nacional_delta_receita_per_capita_pct": medias_nacionais["receita"],
            "media_nacional_delta_populacao_pct": medias_nacionais["populacao"],
            "observacao": f"Valores financeiros corrigidos pela inflacao para {ANO_REF}.",
        },
        "posicao_historica": {
            "ano_2000": {
                "populacao": pop00,
                "receita_corrente_absoluta": num(row.get("receita_00")),
                "receita_per_capita": rc00_pc,
                "quintil": row.get("quintil00") if not pd.isna(row.get("quintil00")) else None,
                "decil": row.get("decil00") if not pd.isna(row.get("decil00")) else None,
                "percentil_label": row.get("percentil00") if not pd.isna(row.get("percentil00")) else None,
                "percentil_numero": percentil_numero(row.get("percentil00")),
                "ranking_nacional": rank(num(row.get("rank_nacional00")), num(row.get("total_nacional00"))),
            },
            "ano_2024": {
                "populacao": pop,
                "receita_corrente_absoluta": num(row.get("receita")),
                "receita_per_capita": rc_pc,
                "quintil": row.get("quintil") if not pd.isna(row.get("quintil")) else None,
                "decil": row.get("decil") if not pd.isna(row.get("decil")) else None,
                "percentil_label": row.get("percentil") if not pd.isna(row.get("percentil")) else None,
                "percentil_numero": percentil_numero(row.get("percentil")),
                "ranking_nacional": rank(num(row.get("rank_nacional")), num(row.get("total_nacional"))),
            },
        },
    }


def gerar_medias_receitas() -> dict:
    """
    Monta o `_medias_receitas.json` — replica montar_medias_receitas().

    É o arquivo que o folheto usa para comparar o município com a média/mediana
    nacional, do estado e do porte. Sem atualizá-lo, um folheto de 2025 compararia
    contra referências de 2024.
    """
    def ler(nome):
        p = PLANILHAS_DIR / nome
        if not p.exists():
            print(f"  [aviso] {nome} ausente — as médias correspondentes sairão null.",
                  file=sys.stderr)
            return None
        df = pd.read_excel(p)
        df.columns = df.columns.str.lower()
        return df

    def serializa(row) -> dict:
        """{field: valor} para as 43 rubricas. Ausente vira None, nunca zero."""
        if row is None:
            return {f: None for f, _, _ in RUBRICAS_MEDIAS}
        out = {}
        for field, _, _ in RUBRICAS_MEDIAS:
            col = FIELD_PARA_COL.get(field)
            v = num(row.get(col)) if col and col in row.index else None
            out[field] = round(v, 2) if isinstance(v, (int, float)) else None
        return out

    m_nac, md_nac = ler("media_nacional_detalhamento.xlsx"), ler("mediana_nacional_detalhamento.xlsx")
    m_uf, md_uf = ler("media_uf_detalhamento.xlsx"), ler("mediana_uf_detalhamento.xlsx")
    m_porte, md_porte = ler("media_porte_detalhamento.xlsx"), ler("mediana_porte_detalhamento.xlsx")

    def linha_por_chave(df, coluna, valor):
        if df is None or coluna not in df.columns:
            return None
        sel = df[df[coluna] == valor]
        return sel.iloc[0] if len(sel) else None

    ufs = sorted(m_uf["uf"].unique()) if m_uf is not None and "uf" in m_uf.columns else []
    por_uf = {
        uf: {
            "media": serializa(linha_por_chave(m_uf, "uf", uf)),
            "mediana": serializa(linha_por_chave(md_uf, "uf", uf)),
        }
        for uf in ufs
    }

    por_porte = {
        porte: {
            "media": serializa(linha_por_chave(m_porte, "faixas", porte)),
            "mediana": serializa(linha_por_chave(md_porte, "faixas", porte)),
        }
        for porte in PORTES_VALIDOS
    }

    return {
        "ano_referencia": ANO_REF,
        "observacao": (
            "Médias e medianas pré-calculadas, em valores per capita (R$/hab), para cada "
            "rubrica de receita. Use 'nacional' para a referência global, 'por_uf' para o "
            "comparativo estadual e 'por_porte' para o comparativo por faixa populacional."
        ),
        "rubricas": [{"field": f, "label": l, "nivel": n} for f, l, n in RUBRICAS_MEDIAS],
        "nacional": {
            "media": serializa(m_nac.iloc[0] if m_nac is not None and len(m_nac) else None),
            "mediana": serializa(md_nac.iloc[0] if md_nac is not None and len(md_nac) else None),
        },
        "por_uf": por_uf,
        "por_porte": por_porte,
    }


# Médias nacionais das variações 2000 -> ano de referência, usadas como linha de
# comparação no folheto. Hardcoded como no export oficial: recalcular a partir do
# snapshot local das planilhas não reproduz estes números com fidelidade.
#
# ATENÇÃO — estes valores foram calculados para 2024 e NÃO acompanham o ANO_REF.
# Com ANO_REF em outro ano, o folheto compara o município de um ano contra uma
# média nacional de outro. `calcular_medias_nacionais()` avisa quando isso
# acontece; a decisão de atualizar os números é editorial, não automática.
MEDIAS_NACIONAIS = {"receita": 316.74, "populacao": 16.04}
ANO_MEDIAS_NACIONAIS = 2024


def calcular_medias_nacionais() -> dict:
    """
    Devolve as médias nacionais de comparação (ver MEDIAS_NACIONAIS).

    Avisa em stderr quando as médias não são do ANO_REF em uso. O aviso é
    barulhento de propósito: o número entra no folheto de qualquer jeito, e sem
    ele a divergência de ano passa sem ninguém notar — foi assim que a página
    "Metodologia" saiu vazia por meses.
    """
    if ANO_REF != ANO_MEDIAS_NACIONAIS:
        print(f"\n[aviso] médias nacionais de comparação são de "
              f"{ANO_MEDIAS_NACIONAIS}, mas ANO_REF é {ANO_REF}. O folheto vai "
              f"comparar o município de {ANO_REF} contra uma média nacional de "
              f"{ANO_MEDIAS_NACIONAIS}.", file=sys.stderr)
        print(f"        Se quiser corrigir, atualize MEDIAS_NACIONAIS e "
              f"ANO_MEDIAS_NACIONAIS em tools/{Path(__file__).name}.",
              file=sys.stderr)
    # Copia: o chamador não deve conseguir mutar a constante do módulo.
    return dict(MEDIAS_NACIONAIS)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def codigos_do_recorte() -> list[str]:
    if not RECORTE_JSON.exists():
        sys.exit(f"Recorte não encontrado: {RECORTE_JSON}")
    d = json.loads(RECORTE_JSON.read_text(encoding="utf-8"))
    return [str(m["cod_ibge"]) for m in d.get("municipios", [])]


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera os JSONs do folheto a partir das planilhas")
    ap.add_argument("--todos", action="store_true", help="todos os municípios (ignora o recorte)")
    ap.add_argument("--cod-ibge", type=str, help="lista separada por vírgula")
    ap.add_argument("--dry-run", action="store_true", help="não escreve arquivos")
    args = ap.parse_args()

    print(f"Ano de referência: {ANO_REF}")
    print(f"Planilhas: {PLANILHAS_DIR}\n")

    dfs = carregar_planilhas()
    base = montar_base(dfs)
    print(f"\nBase consolidada: {len(base):,} municípios")

    medias = calcular_medias_nacionais()
    print(f"Médias nacionais 2000->{ANO_MEDIAS_NACIONAIS}: "
          f"receita {medias['receita']}% | população {medias['populacao']}%")

    print("Calculando percentis por rubrica...")
    percentis_planilha = montar_percentis_planilha(dfs)
    percentis = computar_percentis(base, percentis_planilha)
    print(f"  {len(percentis):,} municípios com percentis")

    # Seleção
    if args.cod_ibge:
        alvo = [c.strip() for c in args.cod_ibge.split(",") if c.strip()]
    elif args.todos:
        alvo = None
    else:
        alvo = codigos_do_recorte()
        print(f"\nRecorte de docs/folhetos.json: {len(alvo)} municípios")

    if alvo is not None:
        sel = base[base["cod_ibge"].isin(alvo)]
        faltando = set(alvo) - set(sel["cod_ibge"])
        if faltando:
            print(f"[aviso] {len(faltando)} código(s) do recorte sem dado nas planilhas: "
                  f"{sorted(faltando)[:5]}{'...' if len(faltando) > 5 else ''}", file=sys.stderr)
    else:
        sel = base

    # Sem receita não há folheto AQUI — o import oficial também pula esses.
    #
    # Mas "pulado" não é "sem folheto": quem não declarou no ano corrente é
    # publicado com o dado do ano anterior mais uma tarja de ressalva, por
    # `tools/gerar_sem_declaracao.py`. O aviso precisa dizer isso e destacar
    # quantos caem no recorte publicado — um `[aviso] 130 pulados` solto já fez
    # colega concluir que o município simplesmente não tinha folheto.
    antes = len(sel)
    pulados = sel[sel["receita"].isna()]
    sel = sel[sel["receita"].notna()]
    if len(sel) < antes:
        print(f"\n[aviso] {antes - len(sel)} município(s) sem receita declarada em "
              f"{ANO_REF} — fora deste lote.", file=sys.stderr)
        if "populacao_25" in pulados.columns:
            grandes = pulados[pulados["populacao_25"] > 80_000]
            if len(grandes):
                nomes = ", ".join(
                    f"{r['nome_muni']}/{r['uf']}"
                    for _, r in grandes.sort_values("populacao_25", ascending=False).iterrows()
                )
                plural = "estão" if len(grandes) > 1 else "está"
                print(f"        {len(grandes)} {plural} no recorte publicado "
                      f"(> 80 mil hab.): {nomes}", file=sys.stderr)
        print("        Esses saem por `python tools/gerar_sem_declaracao.py`, "
              "com o dado do ano anterior e ressalva.", file=sys.stderr)

    if not args.dry_run:
        DESTINO.mkdir(parents=True, exist_ok=True)

    print(f"\nGerando {len(sel):,} JSONs...")
    escritos, erros = 0, []
    for _, row in sel.iterrows():
        try:
            payload = build_payload(row, percentis.get(str(row["cod_ibge"])), dfs["rm_map"], medias)
            nome = f"{row['cod_ibge']}_{slugify(row['nome_muni'])}-{str(row['uf']).lower()}.json"
            if not args.dry_run:
                (DESTINO / nome).write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            escritos += 1
        except Exception as e:
            erros.append(f"{row.get('cod_ibge')} ({row.get('nome_muni')}): {e}")

    # Companheiros editoriais: copia a versão do repo para o lote, sempre.
    #
    # Duas coisas dependem disso. (1) O gerador prefere a cópia que está ao lado
    # dos JSONs municipais ao fallback versionado — um lote antigo com cópia
    # desatualizada venceria em silêncio e o folheto sairia com o texto e os
    # números do ano anterior. (2) Quem clona o repo não tem lote nenhum: sem esta
    # cópia a página correspondente sai vazia, e o único sinal é um `[aviso]` no
    # stderr. Foi exatamente assim que a página "Metodologia" saiu em branco.
    if not args.dry_run:
        for nome in COMPANHEIROS_EDITORIAIS:
            versionado = COMPANHEIROS_DIR / nome
            if not versionado.exists():
                print(f"\n[aviso] {nome} não existe em data/ifem/ — a seção que "
                      f"depende dele sairá vazia.", file=sys.stderr)
                continue
            destino = DESTINO / nome
            if not destino.exists() or destino.read_bytes() != versionado.read_bytes():
                destino.write_bytes(versionado.read_bytes())
                print(f"\n{nome} sincronizado a partir de data/ifem/ (versionado)")

    # Companheiro compartilhado: sem ele os comparativos do folheto ficam no ano errado.
    if not args.dry_run:
        print("\nGerando _medias_receitas.json...")
        medias_json = gerar_medias_receitas()
        (DESTINO / "_medias_receitas.json").write_text(
            json.dumps(medias_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        n_uf = len(medias_json["por_uf"])
        print(f"  {len(medias_json['rubricas'])} rubricas | {n_uf} UFs | "
              f"{len(medias_json['por_porte'])} portes | ano {medias_json['ano_referencia']}")

    print(f"\n{'-' * 60}")
    print(f"{'Geraria' if args.dry_run else 'Gerados'}: {escritos:,} | Erros: {len(erros)}")
    if erros:
        for e in erros[:10]:
            print(f"  - {e}", file=sys.stderr)
        if len(erros) > 10:
            print(f"  ... e mais {len(erros) - 10}", file=sys.stderr)
        return 1
    if not args.dry_run:
        print(f"Destino: {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

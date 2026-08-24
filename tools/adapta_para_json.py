"""
Gera os JSONs de Risco Climático (AdaptaBrasil) consumidos pelo tema `clima`.

POR QUE ESTE SCRIPT EXISTE
Mesmo motivo de `planilhas_para_json.py`: a planilha oficial
`indicadores_adapta_brasil.xlsx` vive em `<PLANILHAS_DIR>` (repo Subfinanciados,
read-only aqui) e é a MESMA fonte que o comando `10_adapta_brasil.py` carrega no
banco do IFEM em produção. Ler a planilha direto produz os mesmos números, sem
banco, sem rede.

O QUE ELE PRODUZ
  data/clima/_panorama_nacional.json   agregados nacionais (companheiro do lote)
  data/clima/<cod>_<slug>.json         um por município, com as 13 notas

CLASSES DE RISCO
O AdaptaBrasil corta o índice 0-1 em cinco classes de amplitude 0,2.
Reclassificando a planilha e cruzando com o quintil do IFEM chega-se exatamente
à distribuição publicada no painel (1o quintil: 207 / 593 / 258 / 30 / 0), o que
confirma o corte. Ver data/clima/PROVENIENCIA.md.

RISCO ALTO É RUIM
Ao contrário do IFEM - onde valor alto = município bem financiado - aqui o
índice mede EXPOSIÇÃO. Por isso `ranking_nacional.posicao == 1` significa MAIOR
risco do país, e `supera_pct_nacional` lê-se "tem risco maior que X% dos
municípios". Inverter isso silenciosamente pintaria de verde o município mais
vulnerável do Brasil.

USO
    python tools/adapta_para_json.py --injetar       # enriquece o lote do IFEM
    python tools/adapta_para_json.py                 # só o recorte de docs/folhetos.json
    python tools/adapta_para_json.py --todos         # os 5.570 municípios
    python tools/adapta_para_json.py --cod-ibge 3304557,2304400
    python tools/adapta_para_json.py --dry-run       # não escreve, só relata
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from bisect import bisect_left
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("Falta 'pandas'. Rode: pip install -r requirements.txt")

ROOT_DIR = Path(__file__).resolve().parent.parent
DESTINO = ROOT_DIR / "data" / "clima"
_DADOS_IFEM = ROOT_DIR / "data" / "ifem" / "dados-ifem"
# Os dois lotes que o build_site.py publica. `_sem_declaracao` guarda os
# municípios que não declararam receita no ano e saem com o dado anterior
# + ressalva; esquecer essa pasta deixaria 7 folhetos publicados sem a
# seção de risco, sem erro nenhum na saída.
LOTES_IFEM = (_DADOS_IFEM / "export_folheto", _DADOS_IFEM / "_sem_declaracao")
RECORTE_JSON = ROOT_DIR / "docs" / "folhetos.json"
PLANILHA = "indicadores_adapta_brasil.xlsx"

# --------------------------------------------------------------------------
# Taxonomia AdaptaBrasil
# --------------------------------------------------------------------------
# Ordem = ordem de leitura no folheto: os subsetores de um mesmo setor
# estratégico ficam juntos. As colunas da planilha são abreviações do próprio
# setor/subsetor (`seg_ali_dis` = segurança alimentar / disponibilidade), então
# este mapa é a única tradução necessária - não há planilha de rótulos.
INDICADORES = (
    ("bio_int_bio",         "Biodiversidade",             "Integridade da biodiversidade"),
    ("des_des_ter",         "Desastres geo-hidrológicos", "Deslizamentos de terra"),
    ("des_in_enx_ala",      "Desastres geo-hidrológicos", "Inundações, enxurradas e alagamentos"),
    ("rec_ris_est_hid",     "Recursos hídricos",          "Risco de estresse hídrico"),
    ("sau_arb",             "Saúde",                      "Arboviroses"),
    ("sau_lei_teg_ame",     "Saúde",                      "Leishmaniose tegumentar americana"),
    ("sau_lei_vis",         "Saúde",                      "Leishmaniose visceral"),
    ("sau_mal",             "Saúde",                      "Malária"),
    ("seg_ali_ace_con_ali", "Segurança alimentar",        "Acesso e consumo de alimentos"),
    ("seg_ali_dis",         "Segurança alimentar",        "Disponibilidade de alimentos"),
    ("seg_ene_ace",         "Segurança energética",       "Acesso à energia"),
    ("seg_ene_dis",         "Segurança energética",       "Disponibilidade de energia"),
)
CAMPOS = [c for c, _, _ in INDICADORES]

COL_MEDIA = "pontuacao_risco_norm_pond"

# Limite inferior (inclusivo) e superior (exclusivo) de cada classe. Do pior
# para o melhor, que é a ordem em que a legenda aparece no painel e no folheto.
CLASSES = (
    ("Muito alto",  0.8, 1.01),
    ("Alto",        0.6, 0.8),
    ("Médio",       0.4, 0.6),
    ("Baixo",       0.2, 0.4),
    ("Muito baixo", 0.0, 0.2),
)


def classe_risco(v) -> str | None:
    """Classe AdaptaBrasil de um índice 0-1. None para valor ausente."""
    if v is None or pd.isna(v):
        return None
    for nome, lo, hi in CLASSES:
        if lo <= v < hi:
            return nome
    return "Muito alto" if v >= 0.8 else "Muito baixo"


# --------------------------------------------------------------------------
# Configuração (.env)
# --------------------------------------------------------------------------

def carrega_env() -> dict:
    """Lê o .env da raiz. Sem dependência externa - o formato é trivial."""
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
# Helpers
# --------------------------------------------------------------------------

def slugify(value: str) -> str:
    """Idêntico ao de planilhas_para_json.py - os nomes de arquivo têm que casar."""
    if value is None:
        return ""
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "sem-nome"


def _ordinal_limpo(s) -> str | None:
    """Normaliza '2? quintil' para '2o quintil' com o ordinal correto.

    A coluna veio de um export salvo em codepage errada e o indicador ordinal
    chegou corrompido. Normalizar aqui evita espalhar mojibake por 5.570 JSONs.
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    n = "".join(ch for ch in str(s) if ch.isdigit())
    if not n:
        return None
    unidade = "decil" if "decil" in str(s).lower() else "quintil"
    return f"{n}º {unidade}"


def _supera_pct(valores_ordenados: list[float], v: float) -> int:
    """% de municípios com risco ESTRITAMENTE menor que `v` (0-100).

    Lê-se "tem risco maior que X% dos municípios". bisect_left dá a contagem de
    valores menores em O(log n) - o mesmo truque de compute_percentis_por_categoria.
    """
    n = len(valores_ordenados)
    if not n:
        return 0
    return int(round(bisect_left(valores_ordenados, v) / n * 100))


def _rank(serie_desc: dict, cod: str, total: int) -> dict | None:
    """Posição no ranking DECRESCENTE de risco: 1o = mais exposto."""
    pos = serie_desc.get(cod)
    if pos is None or pd.isna(pos):
        return None
    return {"posicao": int(pos), "total": int(total)}


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------

def carregar() -> pd.DataFrame:
    """Lê AdaptaBrasil + população e devolve a base consolidada por município."""
    if not PLANILHAS_DIR or not PLANILHAS_DIR.is_dir():
        sys.exit(
            f"Pasta de planilhas não encontrada: {PLANILHAS_DIR or '(vazia)'}\n"
            f"Defina PLANILHAS_DIR no .env (veja .env.example)."
        )

    def ler(nome: str) -> pd.DataFrame:
        p = PLANILHAS_DIR / nome
        if not p.exists():
            sys.exit(f"Planilha obrigatória ausente: {p}")
        df = pd.read_excel(p)
        df.columns = df.columns.str.lower()
        df["cod_ibge"] = df["cod_ibge"].astype(str).str.strip()
        return df

    print("Lendo planilhas...")
    ad = ler(PLANILHA)
    pop = ler("populacao.xlsx")
    print(f"  adapta    {len(ad):>6,} linhas")
    print(f"  populacao {len(pop):>6,} linhas")

    faltando = [c for c in CAMPOS + [COL_MEDIA] if c not in ad.columns]
    if faltando:
        sys.exit(f"{PLANILHA} sem as colunas esperadas: {', '.join(faltando)}")

    base = ad.merge(
        pop[["cod_ibge", "nome_muni", "uf", "regiao"]],
        on="cod_ibge", how="left", validate="one_to_one",
    )
    orfaos = int(base["nome_muni"].isna().sum())
    if orfaos:
        print(f"  [aviso] {orfaos} município(s) do AdaptaBrasil sem cadastro em "
              f"populacao.xlsx - serão ignorados.", file=sys.stderr)
        base = base[base["nome_muni"].notna()].copy()

    return base


# --------------------------------------------------------------------------
# Agregados
# --------------------------------------------------------------------------

def montar_panorama(base: pd.DataFrame) -> dict:
    """Agregados nacionais: distribuição por classe, cruzamento com o quintil
    do IFEM (o gráfico do painel) e média nacional de cada indicador."""
    total = len(base)
    cl = base[COL_MEDIA].map(classe_risco)
    contagem = cl.value_counts().to_dict()

    # Cruzamento classe x quintil IFEM. Os municípios sem quintil ficam de fora
    # do gráfico de propósito: não estão na base do IFEM, então não há coluna
    # onde empilhá-los. O total excluído sai no JSON para não sumir do relato.
    qn = base["quintil"].map(lambda s: (_ordinal_limpo(s) or " ")[0])
    por_quintil = []
    for q in "12345":
        sel = qn == q
        cq = cl[sel].value_counts().to_dict()
        por_quintil.append({
            "quintil": int(q),
            "total": int(sel.sum()),
            "classes": {nome: int(cq.get(nome, 0)) for nome, _, _ in CLASSES},
        })
    sem_quintil = int((~qn.isin(list("12345"))).sum())

    return {
        "fonte": "AdaptaBrasil (MCTI) · Índice de risco climático municipal",
        "ano_ref": ANO_REF,
        "total_municipios": total,
        "media_nacional": round(float(base[COL_MEDIA].mean()), 4),
        "mediana_nacional": round(float(base[COL_MEDIA].median()), 4),
        "classes": [
            {"nome": nome, "min": lo, "max": min(hi, 1.0),
             "total": int(contagem.get(nome, 0))}
            for nome, lo, hi in CLASSES
        ],
        "por_quintil_ifem": por_quintil,
        "municipios_sem_quintil_ifem": sem_quintil,
        "indicadores": [
            {"campo": campo, "setor": setor, "subsetor": sub,
             "media_nacional": round(float(base[campo].mean()), 4),
             "classe_media": classe_risco(float(base[campo].mean()))}
            for campo, setor, sub in INDICADORES
        ],
    }


def montar_municipios(base: pd.DataFrame) -> dict[str, dict]:
    """Um payload por município, já com rankings e comparação nacional."""
    total = len(base)

    # Ordenações para percentil (crescente) e ranking (decrescente = mais
    # exposto primeiro). method="min" reproduz o empate do IFEM: dois municípios
    # com o mesmo índice dividem a mesma posição.
    ordenados = {c: sorted(base[c].dropna().tolist()) for c in CAMPOS + [COL_MEDIA]}
    rank_nac = dict(zip(base["cod_ibge"],
                        base[COL_MEDIA].rank(ascending=False, method="min")))
    rank_uf = dict(zip(base["cod_ibge"],
                       base.groupby("uf")[COL_MEDIA].rank(ascending=False, method="min")))
    total_uf = base.groupby("uf")["cod_ibge"].count().to_dict()

    medias = {c: round(float(base[c].mean()), 4) for c in CAMPOS}

    out = {}
    for row in base.to_dict("records"):
        cod = row["cod_ibge"]
        media = float(row[COL_MEDIA])
        out[cod] = {
            "identificacao": {
                "cod_ibge": cod,
                "municipio": str(row["nome_muni"]),
                "uf": str(row["uf"]),
                "regiao": str(row["regiao"]),
            },
            "risco_climatico": {
                "fonte": "AdaptaBrasil (MCTI)",
                "ano_ref": ANO_REF,
                "quintil_ifem": _ordinal_limpo(row.get("quintil")),
                "decil_ifem": _ordinal_limpo(row.get("decil")),
                "media_geral": {
                    "valor": round(media, 4),
                    "classe": classe_risco(media),
                    "supera_pct_nacional": _supera_pct(ordenados[COL_MEDIA], media),
                    "ranking_nacional": _rank(rank_nac, cod, total),
                    "ranking_estadual": _rank(rank_uf, cod, total_uf.get(row["uf"], 0)),
                },
                "indicadores": [
                    {
                        "campo": campo,
                        "setor": setor,
                        "subsetor": sub,
                        "valor": round(float(row[campo]), 4),
                        "classe": classe_risco(float(row[campo])),
                        "media_nacional": medias[campo],
                        "supera_pct_nacional": _supera_pct(ordenados[campo],
                                                           float(row[campo])),
                    }
                    for campo, setor, sub in INDICADORES
                    if row.get(campo) is not None and not pd.isna(row.get(campo))
                ],
            },
        }
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def codigos_do_recorte() -> list[str]:
    if not RECORTE_JSON.exists():
        sys.exit(f"Recorte não encontrado: {RECORTE_JSON}")
    d = json.loads(RECORTE_JSON.read_text(encoding="utf-8"))
    return [str(m["cod_ibge"]) for m in d.get("municipios", [])]


def injetar_no_lote(municipios: dict, alvos: list[str]) -> int:
    """Grava o bloco `risco_climatico` dentro dos JSONs do lote do IFEM.

    POR QUE ENRIQUECER, EM VEZ DE O FOLHETO LER DOIS ARQUIVOS
    O gerador tem um contrato só: um JSON por município é a verdade completa
    daquele município. Se `ifem.py` fosse buscar um segundo arquivo por
    cod_ibge, o payload deixaria de descrever o folheto que ele produz — e
    ninguém perceberia até um lote sair pela metade.

    É idempotente: reescreve a chave `risco_climatico` inteira a cada execução.
    Quando o export oficial do Subfinanciados passar a trazer o bloco, este modo
    vira ruído e some sem tocar no gerador.
    """
    if not LOTES_IFEM[0].is_dir():
        sys.exit(f"Lote do IFEM não encontrado: {LOTES_IFEM[0]}. "
                 f"Rode antes: python tools/planilhas_para_json.py")

    # Indexa os lotes por cod_ibge: o nome do arquivo traz o código como prefixo,
    # e casar pelo slug seria frágil (acentuação, apóstrofo, hífen).
    por_cod = {}
    for lote in LOTES_IFEM:
        for arq in lote.glob("*.json"):
            if not arq.name.startswith("_"):
                por_cod.setdefault(arq.name.split("_", 1)[0], []).append(arq)

    tocados, ausentes = 0, []
    for cod in alvos:
        arquivos = por_cod.get(cod)
        if not arquivos:
            ausentes.append(cod)
            continue
        for arq in arquivos:
            with arq.open(encoding="utf-8") as f:
                payload = json.load(f)
            payload["risco_climatico"] = municipios[cod]["risco_climatico"]
            escrever(arq, payload)
            tocados += 1

    if ausentes:
        print(f"[aviso] {len(ausentes)} município(s) sem JSON em nenhum lote do IFEM: "
              f"{', '.join(ausentes[:5])}{'...' if len(ausentes) > 5 else ''}",
              file=sys.stderr)
    return tocados


def escrever(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Gera os JSONs de Risco Climático (AdaptaBrasil) do folheto")
    ap.add_argument("--todos", action="store_true", help="todos os municípios (ignora o recorte)")
    ap.add_argument("--cod-ibge", type=str, help="lista separada por vírgula")
    ap.add_argument("--injetar", action="store_true",
                    help="grava o bloco risco_climatico dentro do lote do IFEM "
                         "(data/ifem/dados-ifem/export_folheto)")
    ap.add_argument("--dry-run", action="store_true", help="não escreve arquivos")
    args = ap.parse_args()

    print(f"Ano de referência: {ANO_REF}")
    print(f"Planilhas: {PLANILHAS_DIR}\n")

    base = carregar()
    panorama = montar_panorama(base)
    municipios = montar_municipios(base)
    print(f"\nBase consolidada: {len(municipios):,} municípios")

    if args.cod_ibge:
        alvos = [c.strip() for c in args.cod_ibge.split(",") if c.strip()]
    elif args.todos:
        alvos = list(municipios)
    else:
        alvos = codigos_do_recorte()
        print(f"Recorte de {RECORTE_JSON.name}: {len(alvos):,} municípios")

    ausentes = [c for c in alvos if c not in municipios]
    if ausentes:
        print(f"[aviso] {len(ausentes)} código(s) sem dado no AdaptaBrasil: "
              f"{', '.join(ausentes[:5])}{'...' if len(ausentes) > 5 else ''}",
              file=sys.stderr)
    alvos = [c for c in alvos if c in municipios]

    if args.dry_run:
        destino = LOTES_IFEM[0] if args.injetar else DESTINO
        print(f"\n[dry-run] escreveria 1 panorama + {len(alvos):,} município(s) em {destino}")
        return 0

    # O panorama fica SEMPRE em data/clima/: é versionado, tem 3 KB e é o
    # mesmo agregado para os 5.570 municípios. O gerador o lê de lá com ou
    # sem injeção — replicá-lo em cada JSON do lote custaria ~18 MB por nada.
    DESTINO.mkdir(parents=True, exist_ok=True)
    escrever(DESTINO / "_panorama_nacional.json", panorama)

    if args.injetar:
        tocados = injetar_no_lote(municipios, alvos)
        print(f"\n[OK] risco_climatico gravado em {tocados:,} JSON(s) do lote do IFEM")
        return 0

    for cod in alvos:
        p = municipios[cod]
        ident = p["identificacao"]
        nome = f"{cod}_{slugify(ident['municipio'])}-{ident['uf'].lower()}.json"
        escrever(DESTINO / nome, p)

    print(f"\n[OK] {len(alvos):,} município(s) + _panorama_nacional.json em {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

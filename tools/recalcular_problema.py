"""
Recalcula os números da página "O Problema" a partir das planilhas.

POR QUE EXISTE
`data/ifem/_problema.json` é texto editorial: nenhum export do Subfinanciados o
gera. Mas ele contém NÚMEROS ("em 2024, 82 milhões de pessoas") que envelhecem
junto com a base. Trocar só o rótulo do ano deixaria o folheto afirmando que um
dado de 2024 é de 2025 — falseando um documento institucional.

O QUE É RECALCULADO
  - população somada nos 1º e 5º quintis de receita per capita, em 2000 e no
    ano de referência, e a variação entre eles
  - composição da receita municipal: % de transferências vs arrecadação própria

O TEXTO CORRIDO NÃO É REESCRITO AUTOMATICAMENTE. Os parágrafos de `diagnostico`
citam números por extenso; o script mostra quais frases ficaram inconsistentes e
deixa a redação para revisão humana — reescrever texto institucional por regex é
pedir para publicar bobagem.

USO
    python tools/recalcular_problema.py            # mostra antes/depois, não grava
    python tools/recalcular_problema.py --aplicar  # grava data/ifem/_problema.json
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("Falta 'pandas'. Rode: pip install -r requirements.txt")

ROOT_DIR = Path(__file__).resolve().parent.parent
PROBLEMA = ROOT_DIR / "data" / "ifem" / "_problema.json"


def carrega_env() -> dict:
    env = {}
    p = ROOT_DIR / ".env"
    if p.exists():
        for linha in p.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                env[k.strip()] = v.strip()
    return env


_ENV = carrega_env()
PLANILHAS_DIR = Path(os.getenv("PLANILHAS_DIR") or _ENV.get("PLANILHAS_DIR", ""))
ANO_REF = int(os.getenv("ANO_REF") or _ENV.get("ANO_REF", "2025"))


def carregar():
    def ler(nome):
        df = pd.read_excel(PLANILHAS_DIR / nome)
        df.columns = df.columns.str.lower()
        df["cod_ibge"] = df["cod_ibge"].astype(str)
        return df

    pop = ler("populacao.xlsx")
    rec = ler(f"receitas_correntes_{ANO_REF}.xlsx")
    rec00 = ler("receitas_correntes_2000.xlsx")
    return pop, rec, rec00


def _quintil_num(v):
    """'1º quintil' -> 1. Retorna None se não der para ler."""
    if v is None or pd.isna(v):
        return None
    m = re.search(r"(\d)", str(v))
    return int(m.group(1)) if m else None


def populacao_por_quintil(pop, rec, rec00):
    """
    Soma a população nos quintis extremos, em 2000 e no ano de referência.

    O quintil é o da receita per capita DAQUELE ano — o conjunto de municípios
    no 1º quintil de 2000 não é o mesmo de 2025. É justamente essa recomposição
    que a página "O Problema" narra.
    """
    atual = rec[["cod_ibge", "quintil"]].merge(
        pop[["cod_ibge", "populacao_25"]], on="cod_ibge", how="left")
    atual["q"] = atual["quintil"].map(_quintil_num)

    antigo = rec00[["cod_ibge", "quintil00"]].merge(
        pop[["cod_ibge", "populacao_00"]], on="cod_ibge", how="left")
    antigo["q"] = antigo["quintil00"].map(_quintil_num)

    def milhoes(df, col, q):
        return round(float(df[df["q"] == q][col].sum()) / 1_000_000, 1)

    return {
        "q1_2000": milhoes(antigo, "populacao_00", 1),
        "q1_atual": milhoes(atual, "populacao_25", 1),
        "q5_2000": milhoes(antigo, "populacao_00", 5),
        "q5_atual": milhoes(atual, "populacao_25", 5),
    }


def composicao_receita(rec):
    """% de transferências e de arrecadação própria no total da receita corrente."""
    total = float(rec["receita"].sum())
    transf = float(rec["trf"].sum())
    # Própria = tudo que não é transferência (impostos/taxas, contribuições, outras).
    propria = total - transf
    return {
        "transferencias_pct": round(transf / total * 100),
        "arrecadacao_propria_pct": round(propria / total * 100),
    }


def var_pct(novo, antigo):
    if not antigo:
        return None
    return round(((novo / antigo) - 1) * 100, 2)


# Faixas usadas na página "O Problema" — NÃO são as mesmas do `porte` do folheto.
# Aqui os cortes são 5/10/30/100/500 mil; o porte usa 5/10/20/50/100/200/500.
FAIXAS_PROBLEMA = [
    ("ate_5_mil", 0, 5_000),
    ("5_a_10_mil", 5_000, 10_000),
    ("10_a_30_mil", 10_000, 30_000),
    ("30_a_100_mil", 30_000, 100_000),
    ("100_a_500_mil", 100_000, 500_000),
    ("acima_500_mil", 500_000, float("inf")),
]


def _classifica(pop_valor):
    for nome, lo, hi in FAIXAS_PROBLEMA:
        if lo <= pop_valor < hi:
            return nome
    return None


def crescimento_por_porte(pop, rec, rec00):
    """
    Variação de população e de receita per capita por faixa, de 2000 ao ano atual.

    PREMISSA: a faixa é a do porte ATUAL do município — é como a frase é lida
    ("cidades de 100 a 500 mil cresceram X% desde 2000"). Classificar pelo porte
    de 2000 daria outro número; se a metodologia original usou o outro critério,
    estes valores divergirão.
    """
    df = pop[["cod_ibge", "populacao_25", "populacao_00"]].copy()
    df = df.merge(rec[["cod_ibge", "receita_pc"]], on="cod_ibge", how="left")
    df = df.merge(rec00[["cod_ibge", "receita_00_pc"]], on="cod_ibge", how="left")
    df = df[df["populacao_25"].notna() & (df["populacao_25"] > 0)]
    df["faixa"] = df["populacao_25"].map(_classifica)

    cresc_pop, cresc_rec = {}, {}
    for nome, _, _ in FAIXAS_PROBLEMA:
        g = df[df["faixa"] == nome]
        if g.empty:
            continue
        # População: variação do agregado da faixa (soma), não média de variações.
        p00, p25 = float(g["populacao_00"].sum()), float(g["populacao_25"].sum())
        if p00 > 0:
            cresc_pop[nome] = round((p25 / p00 - 1) * 100, 1)

        # Receita per capita: média das variações individuais, como no texto
        # ("cidades até 30 mil tiveram ganhos reais acima de 30%").
        gr = g[(g["receita_00_pc"] > 0) & g["receita_pc"].notna()]
        if len(gr):
            v = ((gr["receita_pc"] / gr["receita_00_pc"]) - 1) * 100
            cresc_rec[nome] = round(float(v.mean()), 1)

    # Média nacional para o comparativo relativo.
    val = df[(df["receita_00_pc"] > 0) & df["receita_pc"].notna()]
    media_nac = float((((val["receita_pc"] / val["receita_00_pc"]) - 1) * 100).mean())
    rel = {k: round(v - media_nac, 1) for k, v in cresc_rec.items()}

    return cresc_pop, rel, round(media_nac, 1)


def participacao_80k(pop):
    """% da população em municípios acima e abaixo de 80 mil habitantes."""
    out = {}
    for rotulo, col in (("ano_2000", "populacao_00"), ("ano_atual", "populacao_25")):
        d = pop[pop[col].notna() & (pop[col] > 0)]
        total = float(d[col].sum())
        acima = float(d[d[col] > 80_000][col].sum())
        out[rotulo] = {
            "acima_80_mil": round(acima / total * 100, 1),
            "abaixo_80_mil": round((total - acima) / total * 100, 1),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Recalcula os números de _problema.json")
    ap.add_argument("--aplicar", action="store_true", help="grava o arquivo")
    args = ap.parse_args()

    if not PLANILHAS_DIR.is_dir():
        sys.exit(f"PLANILHAS_DIR inválido: {PLANILHAS_DIR}")

    d = json.loads(PROBLEMA.read_text(encoding="utf-8"))
    print(f"Ano de referência: {ANO_REF}\n")

    pop, rec, rec00 = carregar()
    q = populacao_por_quintil(pop, rec, rec00)
    comp = composicao_receita(rec)

    velho_q = d.get("populacao_por_quintil_de_receita", {})
    v1 = velho_q.get("menor_renda_1q", {})
    v5 = velho_q.get("maior_renda_5q", {})
    velho_c = d.get("composicao_receita_municipal", {})

    print("=" * 66)
    print(f"{'CAMPO':<38}{'ANTES (2024)':>14}{'DEPOIS':>14}")
    print("=" * 66)
    linhas = [
        ("1º quintil — pop. 2000 (mi)", v1.get("ano_2000_milhoes"), q["q1_2000"]),
        (f"1º quintil — pop. {ANO_REF} (mi)", v1.get("ano_2024_milhoes"), q["q1_atual"]),
        ("1º quintil — variação %", v1.get("variacao_pct"), var_pct(q["q1_atual"], q["q1_2000"])),
        ("5º quintil — pop. 2000 (mi)", v5.get("ano_2000_milhoes"), q["q5_2000"]),
        (f"5º quintil — pop. {ANO_REF} (mi)", v5.get("ano_2024_milhoes"), q["q5_atual"]),
        ("5º quintil — variação %", v5.get("variacao_pct"), var_pct(q["q5_atual"], q["q5_2000"])),
        ("transferências %", velho_c.get("transferencias_pct"), comp["transferencias_pct"]),
        ("arrecadação própria %", velho_c.get("arrecadacao_propria_pct"), comp["arrecadacao_propria_pct"]),
    ]
    for nome, antes, depois in linhas:
        marca = "  " if antes == depois else " *"
        print(f"{nome:<38}{str(antes):>14}{str(depois):>14}{marca}")
    print("=" * 66)
    print("* = valor mudou\n")

    # Atualiza o payload (chaves mantêm o sufixo _2024: contrato lido por ifem.py)
    d["composicao_receita_municipal"]["transferencias_pct"] = comp["transferencias_pct"]
    d["composicao_receita_municipal"]["arrecadacao_propria_pct"] = comp["arrecadacao_propria_pct"]
    d["populacao_por_quintil_de_receita"]["menor_renda_1q"].update({
        "ano_2000_milhoes": q["q1_2000"],
        "ano_2024_milhoes": q["q1_atual"],
        "variacao_pct": var_pct(q["q1_atual"], q["q1_2000"]),
    })
    d["populacao_por_quintil_de_receita"]["maior_renda_5q"].update({
        "ano_2000_milhoes": q["q5_2000"],
        "ano_2024_milhoes": q["q5_atual"],
        "variacao_pct": var_pct(q["q5_atual"], q["q5_2000"]),
    })
    d["ano_referencia"] = ANO_REF

    # ---- Campos que não entram no PDF, mas ficam errados no repo se não mudarem ----
    cresc_pop, cresc_rec_rel, media_nac = crescimento_por_porte(pop, rec, rec00)
    part = participacao_80k(pop)

    print("CRESCIMENTO POR PORTE (não aparece no folheto, mas fica no repo)")
    print(f"{'faixa':<18}{'pop antes':>11}{'pop depois':>12}{'  |':>3}"
          f"{'rec antes':>11}{'rec depois':>12}")
    velho_cp = d.get("crescimento_populacional_por_porte_2000_2024_pct", {})
    velho_cr = d.get("crescimento_receita_per_capita_vs_media_nacional_2000_2024_pct", {})
    for nome, _, _ in FAIXAS_PROBLEMA:
        print(f"{nome:<18}{str(velho_cp.get(nome)):>11}{str(cresc_pop.get(nome)):>12}   "
              f"{str(velho_cr.get(nome)):>11}{str(cresc_rec_rel.get(nome)):>12}")
    print(f"\n(média nacional de variação da receita per capita: {media_nac}%)")

    vp = d.get("participacao_populacao_por_porte_pct", {})
    print(f"\nPOPULAÇÃO ACIMA DE 80 MIL HAB — o corte do recorte publicado")
    print(f"  2000:  antes {vp.get('ano_2000', {}).get('acima_80_mil')}%"
          f"  ->  depois {part['ano_2000']['acima_80_mil']}%")
    print(f"  {ANO_REF}:  antes {vp.get('ano_2024', {}).get('acima_80_mil')}%"
          f"  ->  depois {part['ano_atual']['acima_80_mil']}%\n")

    # População e participação: metodologia confirmada — os valores recalculados
    # reproduzem os originais de 2024 (ex.: 10_a_30_mil 12.4 e participação 2000
    # 55.2% saem idênticos). Seguro sobrescrever.
    for nome in cresc_pop:
        d.setdefault("crescimento_populacional_por_porte_2000_2024_pct", {})[nome] = cresc_pop[nome]
    if "participacao_populacao_por_porte_pct" in d:
        d["participacao_populacao_por_porte_pct"]["ano_2000"] = part["ano_2000"]
        d["participacao_populacao_por_porte_pct"]["ano_2024"] = part["ano_atual"]

    # Receita relativa à média nacional: NÃO sobrescrito de propósito.
    #
    # A diferença simples (variação da faixa menos variação nacional) produz uma
    # escala incompatível com os valores originais — 34.2 vira -2.9, -25.2 vira
    # -151.3. A metodologia de origem é outra (razão relativa? mediana? agregado
    # por faixa?) e não está documentada em lugar nenhum do Subfinanciados.
    #
    # Este campo não é lido pelo folheto, então mantê-lo com os números de 2024 é
    # apenas desatualizado; sobrescrevê-lo com uma fórmula adivinhada seria errado
    # e passaria despercebido. Fica para quem conhece a metodologia decidir.
    print("[atenção] 'crescimento_receita_per_capita_vs_media_nacional' NÃO foi")
    print("          atualizado: não reproduzi a metodologia original (escala")
    print("          incompatível). Segue com os valores de 2024.")
    print("          Esse campo não é usado no folheto.\n")

    # Frases do texto corrido que citam números/anos e podem ter ficado velhas.
    print("TEXTO CORRIDO — revisar à mão (não é reescrito automaticamente):")
    achou = False
    for i, par in enumerate(d.get("diagnostico", [])):
        if re.search(r"\b(20\d\d|\d+[,.]?\d*\s*milh)", par):
            achou = True
            print(f"\n  [diagnostico {i}]")
            print(f"    {par[:230]}{'...' if len(par) > 230 else ''}")
    if not achou:
        print("  (nenhuma frase com número ou ano)")

    resumo = d.get("resumo", "")
    if re.search(r"\b20\d\d", resumo):
        print(f"\n  [resumo]\n    {resumo[:230]}")

    if args.aplicar:
        PROBLEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nGRAVADO: {PROBLEMA}")
        print("Os números foram atualizados. O texto corrido acima continua como estava.")
    else:
        print(f"\n(dry-run — nada gravado. Use --aplicar para gravar.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

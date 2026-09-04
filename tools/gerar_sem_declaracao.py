"""
Gera folhetos dos municípios que não declararam receita no ano de referência.

O CASO
A base do SICONFI não cobre todos os municípios todo ano. Em 2025, 130 cidades
ficaram sem declaração — sete delas acima de 80 mil habitantes, entre as quais
Volta Redonda/RJ (280 mil) e Magé/RJ (244 mil). Todas tinham folheto no lote
anterior.

A ESCOLHA
Publicar o folheto do último ano disponível, com ressalva explícita, em vez de
deixar a cidade de fora sem explicação. Quem procura o folheto de Volta Redonda
prefere o dado de 2024 marcado como tal do que um 404.

DE ONDE VEM O DADO
De `data/ifem/fallback_<ano anterior>/`, que é **versionado**. Isso não é
detalhe de organização: o dado do ano anterior NÃO é regenerável — em
`base_datas/` só existem `receitas_correntes_2000.xlsx` e
`receitas_correntes_<ANO_REF>.xlsx`, e as planilhas de detalhamento e percentil
não têm recorte por ano. Rodar o gerador com o ano anterior morre em "Planilha
obrigatória ausente".

Enquanto esse dado morava só em `data/ifem/dados-ifem/_backup_2024/` (ignorado
pelo git), quem clonava o repo não conseguia gerar esses folhetos e não recebia
erro nenhum — o município sumia do lote em silêncio. Um lote local de backup,
quando existe, ainda é aceito como complemento para municípios fora do recorte.

COMO
Injeta `aviso_dados` no JSON do ano anterior — o tema renderiza como tarja em
todas as páginas — e gera o folheto com `ANO_REF` do ano do dado, para que todos
os rótulos internos fiquem coerentes. Nada no folheto afirma ser do ano corrente.

O `ANO_REF` precisa ir por subprocesso porque `core/tokens.py` o lê uma vez, no
import: dois anos diferentes não coexistem no mesmo processo.

USO
    python tools/gerar_sem_declaracao.py --listar
    python tools/gerar_sem_declaracao.py --apenas-preparar   # antes do adapta
    python tools/gerar_sem_declaracao.py
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
LOTE_ATUAL = ROOT_DIR / "data" / "ifem" / "dados-ifem" / "export_folheto"
TEMP_DIR = ROOT_DIR / "data" / "ifem" / "dados-ifem" / "_sem_declaracao"
PANORAMA_CLIMA = ROOT_DIR / "data" / "clima" / "_panorama_nacional.json"

# Companheiros que precisam ser os do ANO ANTERIOR, não os do lote corrente:
# `_medias_receitas` compararia o município contra a média do ano errado, e
# `_problema` traz números datados. `_metodologia` fica de fora de propósito —
# é texto estável, idêntico ao versionado em data/ifem/, que o gerar.py já usa
# como fallback.
COMPANHEIROS_DO_ANO = ("_medias_receitas.json", "_problema.json")


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
ANO_ANTERIOR = ANO_REF - 1
LIMITE_POP = 80_000

# Versionado vence lote local: a mesma precedência que o `planilhas_para_json.py`
# aplica aos companheiros editoriais. Um backup velho em disco não pode ganhar
# de silêncio da cópia que o repo entrega — foi assim que a página "Metodologia"
# saiu em branco uma vez.
FALLBACK_DIR = ROOT_DIR / "data" / "ifem" / f"fallback_{ANO_ANTERIOR}"
BACKUP_LOCAL = ROOT_DIR / "data" / "ifem" / "dados-ifem" / f"_backup_{ANO_ANTERIOR}"


def _json_do_ano_anterior(cod: str) -> Path | None:
    """JSON do ano anterior para um código IBGE, priorizando o versionado."""
    for pasta in (FALLBACK_DIR, BACKUP_LOCAL):
        if pasta.is_dir():
            achados = sorted(pasta.glob(f"{cod}_*.json"))
            if achados:
                return achados[0]
    return None


def _companheiro_do_ano(nome: str) -> Path | None:
    for pasta in (FALLBACK_DIR, BACKUP_LOCAL):
        p = pasta / nome
        if p.exists():
            return p
    return None


def _codigos_com_fallback() -> list[str]:
    """Todo código IBGE que tem dado do ano anterior disponível."""
    codigos = set()
    for pasta in (FALLBACK_DIR, BACKUP_LOCAL):
        if pasta.is_dir():
            codigos.update(p.name.split("_")[0] for p in pasta.glob("*.json")
                           if not p.name.startswith("_"))
    return sorted(codigos)


def identificar_por_planilha() -> list[dict]:
    """
    Municípios acima do limite, sem receita no ano de referência.

    É a leitura autoritativa: as planilhas dizem quem declarou. Exige pandas e
    PLANILHAS_DIR — quem não tem cai em `identificar_por_lote()`.
    """
    import pandas as pd

    pop = pd.read_excel(PLANILHAS_DIR / "populacao.xlsx")
    rec = pd.read_excel(PLANILHAS_DIR / f"receitas_correntes_{ANO_REF}.xlsx")
    pop.columns, rec.columns = pop.columns.str.lower(), rec.columns.str.lower()
    pop["cod_ibge"] = pop["cod_ibge"].astype(str).str.strip()
    rec["cod_ibge"] = rec["cod_ibge"].astype(str).str.strip()

    com_receita = set(rec["cod_ibge"])
    grandes = pop[pop["populacao_25"] > LIMITE_POP]
    sem = grandes[~grandes["cod_ibge"].isin(com_receita)]

    out = []
    for _, r in sem.sort_values("populacao_25", ascending=False).iterrows():
        cod = str(r["cod_ibge"])
        out.append({
            "cod_ibge": cod,
            "municipio": r["nome_muni"],
            "uf": r["uf"],
            "populacao": int(r["populacao_25"]),
            "json_anterior": _json_do_ano_anterior(cod),
        })
    return out


def identificar_por_lote() -> list[dict]:
    """
    Fallback sem planilha: quem tem dado do ano anterior e não saiu no lote atual.

    Menos preciso que a planilha (não conhece população nem o motivo da
    ausência), mas suficiente — e é o caminho de quem clonou o repo e ainda não
    configurou `PLANILHAS_DIR`. Sem ele o script simplesmente não roda, que era
    o comportamento antigo.
    """
    ja_gerados = {p.name.split("_")[0] for p in LOTE_ATUAL.glob("*.json")
                  if not p.name.startswith("_")} if LOTE_ATUAL.is_dir() else set()

    out = []
    for cod in _codigos_com_fallback():
        if cod in ja_gerados:
            continue
        origem = _json_do_ano_anterior(cod)
        try:
            d = json.loads(origem.read_text(encoding="utf-8"))
            ident = d.get("identificacao") or {}
            nome, uf = ident.get("municipio", "?"), ident.get("uf", "??")
            pop = (d.get("populacao") or {}).get("valor") or 0
        except (OSError, json.JSONDecodeError, AttributeError) as erro:
            print(f"[aviso] ignorando {cod}: {erro}", file=sys.stderr)
            continue
        out.append({"cod_ibge": cod, "municipio": nome, "uf": uf,
                    "populacao": int(pop), "json_anterior": origem})
    return sorted(out, key=lambda m: -m["populacao"])


def identificar() -> tuple[list[dict], str]:
    """Devolve (alvos, origem_da_identificacao)."""
    if PLANILHAS_DIR.is_dir():
        try:
            return identificar_por_planilha(), "planilhas oficiais"
        except ImportError:
            print("[aviso] pandas ausente — identificando pelo lote em disco.",
                  file=sys.stderr)
        except (OSError, KeyError) as erro:
            print(f"[aviso] não consegui ler as planilhas ({erro}); "
                  f"identificando pelo lote em disco.", file=sys.stderr)
    return identificar_por_lote(), "lote em disco"


def preparar(geraveis: list[dict], aviso: str) -> list[tuple[Path, dict]]:
    """Escreve em TEMP_DIR os JSONs do ano anterior já com a ressalva."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    for nome in COMPANHEIROS_DO_ANO:
        origem = _companheiro_do_ano(nome)
        if origem is None:
            print(f"[aviso] {nome} do ano {ANO_ANTERIOR} não encontrado — o "
                  f"folheto vai comparar contra o ano errado.", file=sys.stderr)
            continue
        (TEMP_DIR / nome).write_bytes(origem.read_bytes())

    preparados = []
    for m in geraveis:
        d = json.loads(m["json_anterior"].read_text(encoding="utf-8"))
        d["aviso_dados"] = aviso
        destino = TEMP_DIR / m["json_anterior"].name

        # O dado versionado é cru: o bloco de Risco Climático entra pelo
        # `adapta_para_json.py --injetar`, que também varre esta pasta.
        # Reescrever por cima sem carregar o bloco de volta derrubaria a seção
        # inteira destes folhetos em silêncio.
        if destino.exists():
            try:
                anterior = json.loads(destino.read_text(encoding="utf-8"))
            except json.JSONDecodeError as erro:
                print(f"[aviso] {destino.name} ilegível, será reescrito: {erro}",
                      file=sys.stderr)
                anterior = {}
            if anterior.get("risco_climatico"):
                d["risco_climatico"] = anterior["risco_climatico"]
        destino.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        preparados.append((destino, m))
    return preparados


def _sem_risco(preparados: list[tuple[Path, dict]]) -> list[str]:
    """Municípios preparados sem o bloco de Risco Climático."""
    faltando = []
    for destino, m in preparados:
        d = json.loads(destino.read_text(encoding="utf-8"))
        if not d.get("risco_climatico"):
            faltando.append(f"{m['municipio']}/{m['uf']}")
    return faltando


def gerar(preparados: list[tuple[Path, dict]]) -> list[str]:
    """Gera um PDF por município, cada um com ANO_REF do ano do dado."""
    # Sem isto o folheto imprimiria o ano corrente sobre números do ano
    # anterior — exatamente o erro que a ressalva existe para evitar.
    env = {**os.environ, "ANO_REF": str(ANO_ANTERIOR), "PYTHONIOENCODING": "utf-8"}

    erros = []
    for destino, m in preparados:
        r = subprocess.run(
            [sys.executable, str(ROOT_DIR / "python" / "gerar.py"),
             "--tema", "ifem", "--dados", str(destino)],
            cwd=ROOT_DIR, env=env, capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode == 0:
            print(f"  [ok] {m['municipio']}/{m['uf']}")
        else:
            erros.append(f"{m['municipio']}/{m['uf']}: {(r.stderr or '').strip()[:160]}")
            print(f"  [X]  {m['municipio']}/{m['uf']}", file=sys.stderr)
    return erros


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Folhetos de municípios sem declaração no ano de referência")
    ap.add_argument("--listar", action="store_true", help="só lista, não gera")
    ap.add_argument("--apenas-preparar", action="store_true",
                    help="escreve os JSONs com a ressalva e para, sem gerar PDF "
                         "(rode antes do adapta_para_json.py --injetar)")
    ap.add_argument("--sem-risco", action="store_true",
                    help="gera mesmo sem o bloco de Risco Climático")
    args = ap.parse_args()

    alvos, origem = identificar()
    print(f"Ano de referência: {ANO_REF} | dado de fallback: {ANO_ANTERIOR}")
    print(f"Identificação por: {origem}")
    print(f"Fallback versionado: {FALLBACK_DIR.relative_to(ROOT_DIR)} "
          f"({'existe' if FALLBACK_DIR.is_dir() else 'AUSENTE'})\n")

    print(f"Municípios sem receita declarada em {ANO_REF}: {len(alvos)}\n")
    for m in alvos:
        origem_json = m["json_anterior"].name if m["json_anterior"] else "SEM DADO ANTERIOR"
        print(f"  {m['municipio']:<28} {m['uf']}  {m['populacao']:>9,}   {origem_json}")

    # Município sem dado em ano nenhum não tem conserto aqui, mas some do lote
    # sem deixar rastro se ninguém o nomear. Vale a regra da casa: degradar
    # é aceitável, degradar em silêncio não.
    sem_fonte = [m for m in alvos if not m["json_anterior"]]
    if sem_fonte:
        print(f"\n[aviso] {len(sem_fonte)} município(s) sem dado de {ANO_ANTERIOR} — "
              f"não há como gerar, ficam fora do lote:", file=sys.stderr)
        for m in sem_fonte:
            print(f"          {m['municipio']}/{m['uf']}", file=sys.stderr)
        print(f"          Para cobrir: copie o JSON correspondente para "
              f"{FALLBACK_DIR.relative_to(ROOT_DIR)}/ "
              f"(ver o README de lá).", file=sys.stderr)

    if args.listar:
        return 0

    geraveis = [m for m in alvos if m["json_anterior"]]
    if not geraveis:
        print("\nNada a gerar.")
        return 0

    aviso = (
        f"Dados de {ANO_ANTERIOR}: este município não declarou receita "
        f"de {ANO_REF} ao SICONFI"
    )
    print(f"\nPreparando {len(geraveis)} JSON(s) com a ressalva:")
    print(f'  "{aviso}"\n')
    preparados = preparar(geraveis, aviso)

    if args.apenas_preparar:
        print(f"{len(preparados)} JSON(s) em {TEMP_DIR.relative_to(ROOT_DIR)}.")
        print("Rode `python tools/adapta_para_json.py --injetar --todos` e "
              "depois este script sem --apenas-preparar.")
        return 0

    # O projeto usa Risco Climático quando o panorama nacional está presente.
    # Gerar sem o bloco produz um folheto com duas páginas a menos, e o único
    # sinal seria um aviso no stderr de um lote inteiro — ninguém lê.
    if PANORAMA_CLIMA.exists() and not args.sem_risco:
        faltando = _sem_risco(preparados)
        if faltando:
            print(f"\n[erro] {len(faltando)} JSON(s) sem o bloco `risco_climatico`: "
                  f"{', '.join(faltando[:5])}{'...' if len(faltando) > 5 else ''}",
                  file=sys.stderr)
            print("       O folheto sairia com a seção de Risco Climático "
                  "inteira faltando.", file=sys.stderr)
            print("       Rode `python tools/adapta_para_json.py --injetar --todos` "
                  "e chame este script de novo", file=sys.stderr)
            print("       (ou use --sem-risco para gerar assim mesmo).",
                  file=sys.stderr)
            return 1

    print()
    erros = gerar(preparados)

    print(f"\n{'-' * 58}")
    print(f"Gerados: {len(preparados) - len(erros)} | Falhas: {len(erros)}")
    for e in erros:
        print(f"  - {e}", file=sys.stderr)
    if len(erros) < len(preparados):
        print("\nOs PDFs saíram em output/ com a tarja de ressalva em todas as páginas.")
        print("Rode `python tools/build_site.py --release-tag <tag>` para reindexar.")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())

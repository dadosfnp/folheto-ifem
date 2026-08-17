"""
Gera folhetos dos municípios que não declararam receita no ano de referência.

O CASO
A base do SICONFI não cobre todos os municípios todo ano. Em 2025, sete cidades
acima de 80 mil habitantes ficaram sem declaração — entre elas Volta Redonda/RJ
(280 mil) e Magé/RJ (244 mil). Todas tinham folheto no lote anterior.

A ESCOLHA
Publicar o folheto do último ano disponível, com ressalva explícita, em vez de
deixar a cidade de fora sem explicação. Quem procura o folheto de Volta Redonda
prefere o dado de 2024 marcado como tal do que um 404.

COMO
Reaproveita o JSON do lote anterior (que tem os dados daquele ano) e injeta o
campo `aviso_dados`, que o tema renderiza como tarja em todas as páginas. O
folheto é gerado com ANO_REF do ano do dado, então todos os rótulos internos
ficam coerentes — nada afirma ser de 2025.

USO
    python tools/gerar_sem_declaracao.py --listar
    python tools/gerar_sem_declaracao.py
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("Falta 'pandas'. Rode: pip install -r requirements.txt")

ROOT_DIR = Path(__file__).resolve().parent.parent
LOTE_ATUAL = ROOT_DIR / "data" / "ifem" / "dados-ifem" / "export_folheto"
LOTE_ANTERIOR = ROOT_DIR / "data" / "ifem" / "dados-ifem" / "_backup_2024"
TEMP_DIR = ROOT_DIR / "data" / "ifem" / "dados-ifem" / "_sem_declaracao"


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


def identificar() -> list[dict]:
    """Municípios acima do limite, sem receita no ano de referência."""
    pop = pd.read_excel(PLANILHAS_DIR / "populacao.xlsx")
    rec = pd.read_excel(PLANILHAS_DIR / f"receitas_correntes_{ANO_REF}.xlsx")
    pop.columns, rec.columns = pop.columns.str.lower(), rec.columns.str.lower()
    pop["cod_ibge"] = pop["cod_ibge"].astype(str)
    rec["cod_ibge"] = rec["cod_ibge"].astype(str)

    com_receita = set(rec["cod_ibge"])
    grandes = pop[pop["populacao_25"] > LIMITE_POP]
    sem = grandes[~grandes["cod_ibge"].isin(com_receita)]

    out = []
    for _, r in sem.sort_values("populacao_25", ascending=False).iterrows():
        cod = r["cod_ibge"]
        anteriores = list(LOTE_ANTERIOR.glob(f"{cod}_*.json"))
        out.append({
            "cod_ibge": cod,
            "municipio": r["nome_muni"],
            "uf": r["uf"],
            "populacao": int(r["populacao_25"]),
            "json_anterior": anteriores[0] if anteriores else None,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Folhetos de municípios sem declaração no ano")
    ap.add_argument("--listar", action="store_true", help="só lista, não gera")
    args = ap.parse_args()

    if not PLANILHAS_DIR.is_dir():
        sys.exit(f"PLANILHAS_DIR inválido: {PLANILHAS_DIR}")

    alvos = identificar()
    print(f"Municípios acima de {LIMITE_POP:,} sem receita declarada em {ANO_REF}: "
          f"{len(alvos)}\n")
    for m in alvos:
        origem = m["json_anterior"].name if m["json_anterior"] else "SEM DADO ANTERIOR"
        print(f"  {m['municipio']:<28} {m['uf']}  {m['populacao']:>9,}   {origem}")

    sem_fonte = [m for m in alvos if not m["json_anterior"]]
    if sem_fonte:
        print(f"\n[aviso] {len(sem_fonte)} sem lote anterior — não dá para gerar:",
              file=sys.stderr)
        for m in sem_fonte:
            print(f"          {m['municipio']}/{m['uf']}", file=sys.stderr)

    if args.listar:
        return 0

    geraveis = [m for m in alvos if m["json_anterior"]]
    if not geraveis:
        print("\nNada a gerar.")
        return 0

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Companheiros do ano anterior, para o folheto ficar coerente com o dado.
    for nome in ("_metodologia.json", "_medias_receitas.json", "_problema.json"):
        origem = LOTE_ANTERIOR / nome
        if origem.exists():
            (TEMP_DIR / nome).write_bytes(origem.read_bytes())

    aviso = (
        f"Dados de {ANO_ANTERIOR} — este município não declarou receita "
        f"de {ANO_REF} ao SICONFI"
    )

    print(f"\nPreparando {len(geraveis)} JSON(s) com a ressalva:")
    print(f'  "{aviso}"\n')

    preparados = []
    for m in geraveis:
        d = json.loads(m["json_anterior"].read_text(encoding="utf-8"))
        d["aviso_dados"] = aviso
        destino = TEMP_DIR / m["json_anterior"].name
        destino.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        preparados.append((destino, m))

    # ANO_REF do ano do dado: sem isso o folheto imprimiria 2025 sobre números
    # de 2024 — exatamente o erro que a ressalva existe para evitar.
    env = {**os.environ, "ANO_REF": str(ANO_ANTERIOR), "PYTHONIOENCODING": "utf-8"}

    ok, erros = 0, []
    for destino, m in preparados:
        r = subprocess.run(
            [sys.executable, str(ROOT_DIR / "python" / "gerar.py"),
             "--tema", "ifem", "--dados", str(destino)],
            cwd=ROOT_DIR, env=env, capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode == 0:
            ok += 1
            print(f"  [ok] {m['municipio']}/{m['uf']}")
        else:
            erros.append(f"{m['municipio']}/{m['uf']}: {(r.stderr or '').strip()[:160]}")
            print(f"  [X]  {m['municipio']}/{m['uf']}", file=sys.stderr)

    print(f"\n{'-' * 58}")
    print(f"Gerados: {ok} | Falhas: {len(erros)}")
    for e in erros:
        print(f"  - {e}", file=sys.stderr)
    if ok:
        print(f"\nOs PDFs saíram em output/ com a tarja de ressalva em todas as páginas.")
        print(f"Rode `python tools/build_site.py --release-tag <tag>` para reindexar.")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())

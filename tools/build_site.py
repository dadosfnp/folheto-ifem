"""
Gera o site estático para GitHub Pages a partir dos PDFs em `output/` e dos
JSONs de dados em `data/ifem/dados-ifem/export_folheto/`.

Os PDFs são hospedados em GitHub Releases (grátis, sem limite de quantidade,
bandwidth ilimitado pra repos públicos), por isso este script NÃO copia
arquivos pesados pro repo. Só gera o índice JSON com URLs apontando pra release.

Saída:
  docs/folhetos.json   — índice de municípios disponíveis (lido pela página)
  docs/index.html      — UI estática (já existe; este script só atualiza o JSON)

Uso típico:
    1) Subir os PDFs como assets de uma release no GitHub (ex.: tag 'v1').
    2) Rodar:
         python tools/build_site.py --release-tag v1
       (owner/repo são auto-detectados de `git remote get-url origin`;
        sobrescreva com --owner / --repo se necessário.)

Subir os PDFs em batch via CLI (precisa do `gh` autenticado):
    gh release create v1 output/FolhetoIFEM_*.pdf --title "Folhetos IFEM v1" \\
        --notes "Lote inicial de folhetos IFEM por município."
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
EXPORT_DIR = ROOT / "data" / "ifem" / "dados-ifem" / "export_folheto"
DOCS_DIR = ROOT / "docs"


# Espelha `_TC_MINUSCULAS` de python/temas/ifem.py — palavras de ligação
# que permanecem minúsculas em title case brasileiro.
_TC_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o"}


def _title_case_br(s: str) -> str:
    """Replica `_title_case_br()` do tema IFEM: capitaliza palavras, exceto
    artigos/preposições brasileiras quando não estão no início."""
    palavras = s.split()
    out = []
    for i, w in enumerate(palavras):
        wl = w.lower()
        out.append(wl if i > 0 and wl in _TC_MINUSCULAS else wl.capitalize())
    return " ".join(out)


def _strip_acentos(s: str) -> str:
    """Remove diacríticos (NFD + filtra combining marks). GitHub Releases
    descarta acentos do nome do asset no upload, então o folhetos.json
    precisa apontar pro nome ASCII pra evitar 404."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _slug_release(s: str) -> str:
    """Filename SEM acento — o que o GitHub Releases efetivamente armazena."""
    return _strip_acentos(_title_case_br(s or "folheto")).replace(" ", "_")


def _slug_local(s: str) -> str:
    """Filename COM acento — o que o gerador local escreve em output/."""
    return _title_case_br(s or "folheto").replace(" ", "_")


def _detectar_owner_repo() -> tuple[str | None, str | None]:
    """Lê `git remote get-url origin` e devolve (owner, repo).
    Aceita formatos git@github.com:owner/repo.git e https://github.com/owner/repo(.git)."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return (None, None)

    m = re.search(r"github\.com[:/]([^/]+)/([^/.\s]+)(?:\.git)?$", url)
    if not m:
        return (None, None)
    return (m.group(1), m.group(2))


def _carregar_indice_municipios() -> dict[str, dict]:
    """
    Lê os JSONs dos municípios e devolve {cod_ibge: meta}.

    Duas origens: o lote do ano corrente e `_sem_declaracao/`, que guarda os
    municípios que não declararam receita no ano e cujo folheto foi gerado com a
    base anterior + ressalva (ver tools/gerar_sem_declaracao.py). Sem a segunda,
    essas cidades sumiriam da landing mesmo tendo PDF publicado.
    """
    idx: dict[str, dict] = {}
    fontes = [EXPORT_DIR]
    sem_decl = EXPORT_DIR.parent / "_sem_declaracao"
    if sem_decl.is_dir():
        fontes.append(sem_decl)

    for pasta in fontes:
        for jpath in sorted(pasta.glob("*.json")):
            nome = jpath.name
            if nome.startswith("_") or "_sintese" in nome:
                continue
            try:
                with jpath.open(encoding="utf-8") as f:
                    d = json.load(f)
                ident = d["identificacao"]
                meta = {
                    "cod_ibge":  ident["cod_ibge"],
                    "municipio": ident["municipio"],
                    "uf":        ident["uf"],
                    "regiao":    ident.get("regiao", ""),
                    "porte":     ident.get("porte", ""),
                    "populacao": d["populacao"]["valor"],
                    "rk_pop":    (d["populacao"].get("ranking_nacional") or {}).get("posicao"),
                    "rk_rec":    ((d["receita_corrente"].get("ranking_por_per_capita") or {})
                                  .get("nacional") or {}).get("posicao"),
                    "quintil":   d.get("percentil", {}).get("quintil", ""),
                }
                # Ressalva viaja para a landing: quem baixa precisa saber que o
                # folheto é do ano anterior antes de abrir o PDF.
                if d.get("aviso_dados"):
                    meta["aviso"] = d["aviso_dados"]
                    meta["ano_dados"] = (d.get("receita_corrente") or {}).get("ano")
                idx[ident["cod_ibge"]] = meta
            except Exception as e:
                print(f"[skip] {nome}: {e}", file=sys.stderr)
    return idx


def _pdf_filename_local(municipio: str, uf: str) -> str:
    """Filename como o gerador escreve em output/ — com acentos."""
    return f"FolhetoIFEM_{_slug_local(municipio)}_{uf}.pdf"


def _pdf_filename_release(municipio: str, uf: str) -> str:
    """Filename como o GitHub Releases armazena — sem acentos."""
    return f"FolhetoIFEM_{_slug_release(municipio)}_{uf}.pdf"


def _agora_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(release_tag: str, owner: str, repo: str) -> None:
    if not OUTPUT_DIR.exists():
        sys.exit(f"output/ não encontrado em {OUTPUT_DIR}")
    if not EXPORT_DIR.exists():
        sys.exit(f"export_folheto/ não encontrado em {EXPORT_DIR}")

    DOCS_DIR.mkdir(exist_ok=True)

    municipios_meta = _carregar_indice_municipios()
    pdfs_disponiveis = {p.name for p in OUTPUT_DIR.glob("FolhetoIFEM_*.pdf")}

    base_release_url = (
        f"https://github.com/{owner}/{repo}/releases/download/{release_tag}/"
    )

    items = []
    for cod, meta in municipios_meta.items():
        fname_local   = _pdf_filename_local(meta["municipio"], meta["uf"])
        fname_release = _pdf_filename_release(meta["municipio"], meta["uf"])
        # Confere disponibilidade pelo arquivo local (que tem acento), mas
        # aponta a URL pro nome sem acento (forma como o GitHub Releases guarda).
        if fname_local not in pdfs_disponiveis:
            continue
        items.append({
            **meta,
            "pdf":          base_release_url + fname_release,
            "pdf_filename": fname_release,
        })

    # Cidades grandes primeiro — são as mais procuradas.
    items.sort(key=lambda x: -x["populacao"])

    indice = {
        "total":       len(items),
        "release_tag": release_tag,
        "owner":       owner,
        "repo":        repo,
        "atualizado":  _agora_iso(),
        "municipios":  items,
    }

    out_json = DOCS_DIR / "folhetos.json"
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)

    print(f"[ok] {out_json} — {len(items)} municípios")
    print(f"[ok] URLs apontam para release '{release_tag}' em {owner}/{repo}")


def main():
    auto_owner, auto_repo = _detectar_owner_repo()

    p = argparse.ArgumentParser()
    p.add_argument("--release-tag", required=True,
                   help="Tag da release do GitHub que contém os PDFs (ex.: v1).")
    p.add_argument("--owner", default=auto_owner,
                   help=f"Owner do repo no GitHub (auto: {auto_owner!r}).")
    p.add_argument("--repo",  default=auto_repo,
                   help=f"Nome do repo no GitHub (auto: {auto_repo!r}).")
    args = p.parse_args()

    if not args.owner or not args.repo:
        sys.exit("Owner/repo do GitHub não detectados. Passe --owner e --repo.")

    build(release_tag=args.release_tag, owner=args.owner, repo=args.repo)


if __name__ == "__main__":
    main()

"""
CLI unificada: gera folhetos de qualquer tema a partir de JSON de dados.

Uso:
    python python/gerar.py --tema ifem  --dados data/ifem/rio_de_janeiro.json
    python python/gerar.py --tema cosip --dados data/cosip/rio_de_janeiro.json
    python python/gerar.py --tema ifem  --lote data/ifem/*.json

Para listar os temas disponíveis:
    python python/gerar.py --listar

Adicionar um tema novo: ver python/temas/__init__.py.
"""
import argparse
import glob
import json
import sys
from pathlib import Path

# Permite executar tanto como módulo (-m) quanto como script direto.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from temas import TEMAS  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent


def carregar_json(path: str) -> dict:
    """Carrega arquivo de dados validando o JSON."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {p}")
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _carregar_companheiro(dados_path: str, nome_arquivo: str, tema: str) -> dict | None:
    """
    Carrega um JSON compartilhado entre municípios (ex.: _metodologia.json).

    Procura em duas camadas, nesta ordem:
      1. Pasta do próprio --dados — é onde caem os companheiros gerados pelos
         exports do Subfinanciados (_metodologia, _medias_receitas).
      2. `data/<tema>/` — fallback versionado no repo, para companheiros que são
         conteúdo editorial e não saem de nenhum export (_problema.json). Sem
         este fallback, quem regenera os dados numa pasta limpa perde a página
         "O Problema" silenciosamente.
    """
    candidatos = [
        Path(dados_path).resolve().parent / nome_arquivo,
        ROOT_DIR / "data" / tema / nome_arquivo,
    ]
    for p in candidatos:
        if p.exists():
            with p.open(encoding="utf-8") as f:
                return json.load(f)
    return None


def gerar_um(tema: str, dados_path: str) -> Path:
    if tema not in TEMAS:
        raise ValueError(
            f"Tema '{tema}' desconhecido. Disponíveis: {', '.join(TEMAS.keys())}"
        )
    Cls = TEMAS[tema]
    dados = carregar_json(dados_path)

    # Companheiros compartilhados entre municípios.
    for nome in ("_metodologia.json", "_problema.json", "_medias_receitas.json"):
        extra = _carregar_companheiro(dados_path, nome, tema)
        if extra is not None:
            chave = nome.removesuffix(".json")  # "_metodologia"
            dados[chave] = extra
        else:
            # Página correspondente sai vazia — avisa em vez de degradar calado.
            print(f"[aviso] {nome} não encontrado; a seção que depende dele sairá vazia.",
                  file=sys.stderr)

    folheto = Cls(dados)
    out = folheto.gerar()
    print(f"[OK] {out}")
    return out


def _filtra_por_populacao(arquivos: list[str], minimo: int) -> list[str]:
    """
    Mantém só os municípios acima de `minimo` habitantes.

    Lê `populacao.valor` de cada JSON. Arquivo sem esse campo é descartado com
    aviso: melhor faltar no lote do que gerar um folheto de município que não
    deveria entrar no recorte.
    """
    selecionados = []
    for arq in arquivos:
        try:
            with open(arq, encoding="utf-8") as f:
                pop = (json.load(f).get("populacao") or {}).get("valor")
        except (OSError, json.JSONDecodeError) as e:
            print(f"[aviso] ignorando {Path(arq).name}: {e}", file=sys.stderr)
            continue
        if pop and pop > minimo:
            selecionados.append(arq)
    return selecionados


def main():
    parser = argparse.ArgumentParser(description="Gerador de folhetos FNP unificado")
    parser.add_argument("--tema",   type=str, help=f"Tema do folheto: {', '.join(TEMAS.keys())}")
    parser.add_argument("--dados",  type=str, help="Caminho do JSON de dados")
    parser.add_argument("--lote",   type=str, help="Glob de JSONs (ex.: 'data/ifem/*.json')")
    parser.add_argument("--pop-minima", type=int, default=None, metavar="N",
                        help="no lote, só municípios com população acima de N")
    parser.add_argument("--listar", action="store_true", help="Lista temas registrados")
    args = parser.parse_args()

    if args.listar:
        print("Temas disponíveis:")
        for nome, cls in TEMAS.items():
            print(f"  - {nome:8s} -> {cls.__name__}")
        return

    if not args.tema:
        parser.error("--tema é obrigatório (use --listar para ver disponíveis)")

    if args.lote:
        arquivos = sorted(glob.glob(args.lote))
        # Companheiros compartilhados (_metodologia, _problema…) não são municípios.
        arquivos = [a for a in arquivos if not Path(a).name.startswith("_")]
        if not arquivos:
            sys.exit(f"Nenhum arquivo casou com o padrão: {args.lote}")

        if args.pop_minima:
            arquivos = _filtra_por_populacao(arquivos, args.pop_minima)
            if not arquivos:
                sys.exit(f"Nenhum município acima de {args.pop_minima:,} habitantes.")
            print(f"{len(arquivos)} município(s) acima de {args.pop_minima:,} habitantes.\n")

        total, falhas = len(arquivos), 0
        for i, arq in enumerate(arquivos, 1):
            try:
                gerar_um(args.tema, arq)
            except Exception as e:
                falhas += 1
                print(f"✗ Erro em {arq}: {e}", file=sys.stderr)
            if total > 20 and i % 50 == 0:
                print(f"    ... {i}/{total}", file=sys.stderr)
        if total > 1:
            print(f"\nConcluído: {total - falhas}/{total} folhetos"
                  + (f" ({falhas} falha(s))" if falhas else ""))
    elif args.dados:
        gerar_um(args.tema, args.dados)
    else:
        parser.error("Use --dados <arquivo.json> ou --lote <glob>")


if __name__ == "__main__":
    main()

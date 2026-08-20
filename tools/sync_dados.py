"""
Copia o lote `export_folheto/` gerado pelo Subfinanciados para dentro deste repo.

Este é o elo que faltava documentar no pipeline: os scripts de export do
Subfinanciados escrevem em `Subfinanciados/export_folheto/`, mas o gerador de
folhetos lê de `data/ifem/dados-ifem/export_folheto/`. Até aqui a cópia era
manual e não estava escrita em lugar nenhum — quem clonava o repo não tinha
como saber que esse passo existia.

Os dados NÃO são versionados (5.4k arquivos, ~94 MB, regeneráveis a partir do
banco), por isso todo mundo precisa rodar este passo ao menos uma vez.

Uso:
    python tools/sync_dados.py                    # auto-detecta o Subfinanciados
    python tools/sync_dados.py --origem <caminho> # aponta o export_folheto na mão
    python tools/sync_dados.py --dry-run          # mostra o que faria
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DESTINO = ROOT_DIR / "data" / "ifem" / "dados-ifem" / "export_folheto"

# Arquivos compartilhados que o gerador procura ao lado dos JSONs municipais.
COMPANHEIROS = ("_metodologia.json", "_medias_receitas.json", "_problema.json")

# Companheiros de conteúdo EDITORIAL: aqui o repo é a fonte da verdade. Nenhum
# export gera o `_problema.json`, e o `_metodologia.json`, mesmo vindo do export,
# é texto revisado neste repo. Sobrescrever a cópia que o export trouxe é
# intencional: sem isso as edições feitas aqui seriam desfeitas a cada sync, em
# silêncio, e quem regenerasse o lote geraria um PDF diferente do de todo mundo.
COMPANHEIROS_EDITORIAIS = ("_problema.json", "_metodologia.json")
COMPANHEIROS_DIR = ROOT_DIR / "data" / "ifem"


def descobrir_origem(informado: str | None) -> Path:
    """
    Resolve a pasta `export_folheto` de origem.

    Ordem: --origem > env SUBFINANCIADOS_DIR > repo irmão em ../Subfinanciados.
    """
    if informado:
        p = Path(informado).expanduser().resolve()
        # Aceita tanto a raiz do Subfinanciados quanto o export_folheto direto.
        return p / "export_folheto" if (p / "export_folheto").is_dir() else p

    env = os.getenv("SUBFINANCIADOS_DIR")
    if env:
        return Path(env).expanduser().resolve() / "export_folheto"

    return ROOT_DIR.parent / "Subfinanciados" / "export_folheto"


def precisa_copiar(origem: Path, destino: Path) -> bool:
    """
    Copia só o que mudou — o lote tem 5.4k arquivos e a maioria não muda entre
    execuções. Compara tamanho e mtime, que é suficiente para arquivos gerados
    por script (não há edição manual no meio do caminho).
    """
    if not destino.exists():
        return True
    o, d = origem.stat(), destino.stat()
    return o.st_size != d.st_size or o.st_mtime > d.st_mtime


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza os JSONs do Subfinanciados para este repo"
    )
    parser.add_argument("--origem", type=str, default=None,
                        help="caminho do Subfinanciados (ou do export_folheto direto)")
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o que seria copiado, sem escrever nada")
    args = parser.parse_args()

    origem = descobrir_origem(args.origem)

    if not origem.is_dir():
        print(f"Pasta de origem não encontrada: {origem}\n", file=sys.stderr)
        print("Rode os exports no Subfinanciados primeiro:", file=sys.stderr)
        print("    python export_folheto_municipios.py", file=sys.stderr)
        print("    python export_folheto_complementares.py\n", file=sys.stderr)
        print("Ou aponte a pasta na mão:", file=sys.stderr)
        print("    python tools/sync_dados.py --origem C:\\caminho\\para\\Subfinanciados",
              file=sys.stderr)
        return 1

    arquivos = sorted(origem.glob("*.json"))
    if not arquivos:
        print(f"Nenhum .json em {origem} — os exports rodaram?", file=sys.stderr)
        return 1

    municipais = [a for a in arquivos if not a.name.startswith("_")]
    print(f"Origem:  {origem}")
    print(f"Destino: {DESTINO}")
    print(f"Encontrados: {len(municipais)} municípios + "
          f"{len(arquivos) - len(municipais)} arquivo(s) compartilhado(s)\n")

    if not args.dry_run:
        DESTINO.mkdir(parents=True, exist_ok=True)

    copiados = inalterados = 0
    erros: list[str] = []
    for arq in arquivos:
        alvo = DESTINO / arq.name
        if not precisa_copiar(arq, alvo):
            inalterados += 1
            continue
        if args.dry_run:
            copiados += 1
            continue
        try:
            shutil.copy2(arq, alvo)
            copiados += 1
        except OSError as e:
            erros.append(f"{arq.name}: {e}")

    # Companheiros editoriais: a versão do repo vence a do export (ver constante).
    for nome in COMPANHEIROS_EDITORIAIS:
        versionado = COMPANHEIROS_DIR / nome
        if not versionado.exists():
            print(f"[aviso] {nome} não existe em data/ifem/ — a seção que depende "
                  f"dele sairá vazia.", file=sys.stderr)
            continue
        veio_do_export = any(a.name == nome for a in arquivos)
        if not args.dry_run:
            shutil.copy2(versionado, DESTINO / nome)
        detalhe = ("sobrescrevi a do export" if veio_do_export
                   else "o export não traz este arquivo")
        print(f"[info] {nome}: usei a versão de data/ifem/ ({detalhe}).")

    faltando = [c for c in COMPANHEIROS if not (DESTINO / c).exists()] if not args.dry_run else []

    print(f"{'-' * 58}")
    verbo = "Copiaria" if args.dry_run else "Copiados:"
    print(f"{verbo} {copiados} | Inalterados: {inalterados}")

    if faltando:
        print(f"\n[aviso] compartilhados ausentes: {', '.join(faltando)}", file=sys.stderr)
        print("        As seções que dependem deles sairão vazias.", file=sys.stderr)

    if erros:
        print(f"\n{len(erros)} falha(s) de cópia:", file=sys.stderr)
        for e in erros[:10]:
            print(f"  - {e}", file=sys.stderr)
        if len(erros) > 10:
            print(f"  ... e mais {len(erros) - 10}", file=sys.stderr)
        return 1

    if not args.dry_run:
        print("\nPronto. Gere um folheto com:")
        print("    python python/gerar.py --tema ifem --dados "
              "data/ifem/dados-ifem/export_folheto/3304557_rio-de-janeiro-rj.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

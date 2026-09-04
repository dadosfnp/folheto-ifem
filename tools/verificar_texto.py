"""
Verifica as convenções tipográficas da publicação no texto do PDF gerado.

Hoje checa uma regra: **travessão (—) não aparece em texto impresso**. É
convenção da publicação, não gosto de quem escreve — vale para copy nova, para o
texto editorial dos JSONs e para placeholder de valor ausente (que é `n/d`, nunca
um traço solto: num KPI o leitor confunde com sinal de menos).

A meia-risca (–) é permitida e não é acusada: ela tem uso legítimo em intervalo
numérico, como em "Síntese Fiscal 2000–2025".

Uso:
    python tools/verificar_texto.py output/*.pdf
    python tools/verificar_texto.py output            # varre a pasta

Sai com código 1 se achar qualquer ocorrência, para poder entrar em CI ou num
passo de release.
"""
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("[erro] PyMuPDF não instalado: pip install pymupdf")


TRAVESSAO = "—"        # em dash — proibido
CONTEXTO = 45               # caracteres em volta, para localizar a ocorrência


def verificar(pdf: Path) -> list[tuple[int, str]]:
    """Devolve [(pagina, trecho)] para cada ocorrência de travessão."""
    achados = []
    with fitz.open(pdf) as doc:
        for pno, page in enumerate(doc, start=1):
            texto = page.get_text()
            inicio = 0
            while (i := texto.find(TRAVESSAO, inicio)) != -1:
                trecho = texto[max(0, i - CONTEXTO):i + CONTEXTO]
                achados.append((pno, " ".join(trecho.split())))
                inicio = i + 1
    return achados


def _expandir(args: list[str]) -> list[Path]:
    pdfs: list[Path] = []
    for a in args:
        p = Path(a)
        pdfs.extend(sorted(p.glob("*.pdf")) if p.is_dir() else [p])
    return pdfs


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdfs = _expandir(sys.argv[1:])
    if not pdfs:
        sys.exit("[erro] nenhum PDF encontrado nos caminhos informados")

    falhas = 0
    for pdf in pdfs:
        try:
            achados = verificar(pdf)
        except Exception as erro:                   # PDF corrompido, truncado…
            print(f"[erro] {pdf.name}: {erro}", file=sys.stderr)
            falhas += 1
            continue
        if achados:
            falhas += 1
            print(f"FALHA {pdf.name}: {len(achados)} travessão(ões)")
            for pno, trecho in achados[:3]:
                print(f"   p{pno}: …{trecho}…")

    print(f"--- {len(pdfs) - falhas}/{len(pdfs)} PDFs sem travessão no texto")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

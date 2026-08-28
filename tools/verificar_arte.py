"""
Verifica que nenhuma arte decorativa do rodapé cobre conteúdo do folheto.

A decoração de rodapé (`assets/padroes/arte{0,1,2}.png`) é a última coisa
desenhada em cada página. Em PDF, o que é desenhado depois cobre o que veio
antes: uma arte alta demais para o espaço livre apaga silenciosamente a última
linha de uma tabela — o PDF abre normalmente, nada quebra, e o defeito só
aparece quando alguém olha a página impressa.

Por isso a verificação é feita no PDF gerado, e não na conta interna do
gerador: mede o retângulo real da imagem e o compara com o retângulo real de
cada texto e vetor da página.

Uso:
    python tools/verificar_arte.py output/*.pdf
    python tools/verificar_arte.py output            # varre a pasta

Saída: uma linha por PDF com colisão. Código de saída 1 se houver qualquer uma,
para poder entrar em CI ou num passo de release.
"""
import sys
from collections import defaultdict
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("[erro] PyMuPDF não instalado: pip install pymupdf")


# Dimensões em pixels dos PNGs de assets/padroes — é como a arte é
# identificada dentro do PDF, já que o nome do arquivo não sobrevive à
# incorporação.
ARTES = {(437, 39): "arte0", (591, 108): "arte1", (592, 216): "arte2"}

# Faixas de moldura (header, footer, tarja de ressalva, logo FNP) medidas a
# partir das bordas. Elas são desenhadas fora da área útil e a arte encosta
# nelas por projeto, então não contam como colisão.
MOLDURA_TOPO = 40
MOLDURA_BASE = 40

# Ruído de renderização: interseções menores que isso são artefato de
# arredondamento do bbox, não sobreposição visível.
TOLERANCIA_PT = 0.5


def _alvos_da_pagina(page, W: float, H: float) -> list:
    """Retângulos de tudo que é conteúdo — texto e vetores — na área útil."""
    alvos = []
    for x0, y0, x1, y1, texto, *_ in page.get_text("blocks"):
        if not texto.strip():
            continue
        r = fitz.Rect(x0, y0, x1, y1)
        if r.y0 < MOLDURA_TOPO or r.y0 > H - MOLDURA_BASE:
            continue
        alvos.append(r)
    for d in page.get_drawings():
        r = d["rect"]
        if r.width >= W * 0.9 and r.height >= H * 0.9:
            continue                      # fundo branco da página
        if r.width <= 22 and r.height >= H * 0.9:
            continue                      # stripe lateral
        if r.y0 > H - MOLDURA_BASE:
            continue
        if r.height < 0.2 and r.width < 0.2:
            continue
        alvos.append(r)
    return alvos


def verificar(pdf: Path) -> dict:
    """Retorna {(pagina, nome_da_arte): maior_sobreposicao_em_pt}."""
    colisoes: dict = defaultdict(float)
    with fitz.open(pdf) as doc:
        W, H = doc[0].rect.width, doc[0].rect.height
        for pno, page in enumerate(doc, start=1):
            artes = []
            for info in page.get_images(full=True):
                nome = ARTES.get((info[2], info[3]))
                if nome:
                    artes.extend((nome, r) for r in page.get_image_rects(info[0]))
            if not artes:
                continue
            alvos = _alvos_da_pagina(page, W, H)
            for nome, arte in artes:
                for alvo in alvos:
                    inter = arte & alvo
                    if (inter.is_valid and inter.width > TOLERANCIA_PT
                            and inter.height > TOLERANCIA_PT):
                        chave = (pno, nome)
                        colisoes[chave] = max(colisoes[chave], inter.height)
    return colisoes


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
            colisoes = verificar(pdf)
        except Exception as erro:                      # PDF corrompido, truncado…
            print(f"[erro] {pdf.name}: {erro}", file=sys.stderr)
            falhas += 1
            continue
        if colisoes:
            falhas += 1
            detalhe = ", ".join(f"p{pno}/{arte}:{pt:.0f}pt"
                                for (pno, arte), pt in sorted(colisoes.items()))
            print(f"FALHA {pdf.name}: {detalhe}")

    print(f"--- {len(pdfs) - falhas}/{len(pdfs)} PDFs sem arte sobre o conteúdo")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

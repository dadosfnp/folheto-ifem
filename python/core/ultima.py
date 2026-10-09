"""
Última página padrão FNP — verso do folheto.

A arte de referência é `data/ifem/ultimapaginaifem.png`: grade do alfabeto
modular (quadrados e quartos de círculo em contorno) + logo FNP no pé. Ela é
quadrada; no A5 retrato a grade é redesenhada em vetor com as MESMAS primitivas
(`core.padrao.draw_tile`) e as cores amostradas do PNG, e só o logo vem da arte
(`draw_recorte`). Esticar o PNG transformaria os quartos de círculo em ovais.

Semente fixa: o verso é igual em todos os folhetos, como era o PNG.
"""
import random

from reportlab.lib import colors

from .tokens import WHITE, BLUE_DARK, ROOT_DIR
from .fonts import F
from .components import draw_recorte
from .padrao import TILE_WEIGHTS_DENSO, _weighted_choice


_ULTIMA_PNG = ROOT_DIR / "data" / "ifem" / "ultimapaginaifem.png"
_ULTIMA_PX = (717, 707)
_LOGO_FNP_PX = (283, 608, 427, 657)    # logo FNP no pé da arte (pixels)

# Cores amostradas do PNG (as 4 mais frequentes nos contornos da grade).
PALETA_VERSO = [
    colors.HexColor("#06496D"),   # azul petróleo escuro
    colors.HexColor("#19678A"),   # azul petróleo
    colors.HexColor("#4296AF"),   # azul claro
    colors.HexColor("#9B8055"),   # dourado
]

# A arte de referência não tem buracos nem círculos soltos em excesso: tira o
# "empty" e deixa o círculo raro, como no PNG.
_PESOS_VERSO = {**TILE_WEIGHTS_DENSO, "empty": 0, "circle": 1}

_COLUNAS = 8          # 11 no quadrado; 8 deixa o tile do A5 perto do original
_GAP = 0.09           # respiro entre tiles, em fração do lado da célula
_SEMENTE = 7


def _draw_tile_fechado(c, kind: str, x: float, y: float, s: float, cor, lw: float):
    """Tile do verso. Diferente de `padrao.draw_tile`, o quarto de círculo é
    um SETOR FECHADO (dois raios + arco), como na arte de referência — só o
    arco solto deixava a grade rala e com cara de rascunho."""
    c.setStrokeColor(cor)
    c.setLineWidth(lw)
    if kind == "square":
        c.rect(x, y, s, s, fill=0, stroke=1)
    elif kind == "circle":
        c.circle(x + s / 2, y + s / 2, s / 2 * 0.92, fill=0, stroke=1)
    elif kind.startswith("qc_"):
        # Centro do setor no canto indicado; o arco bojuda para o canto oposto.
        cx, cy, ang = {
            "qc_sw": (x,     y,     0),
            "qc_se": (x + s, y,     90),
            "qc_ne": (x + s, y + s, 180),
            "qc_nw": (x,     y + s, 270),
        }[kind]
        c.wedge(cx - s, cy - s, cx + s, cy + s, ang, 90, stroke=1, fill=0)


def _draw_grade_verso(c, x: float, y: float, w: float, h: float,
                      semente: int = _SEMENTE) -> None:
    """Grade do alfabeto preenchendo (x, y, w, h), com respiro entre tiles."""
    rng = random.Random(semente)
    cell = w / _COLUNAS
    linhas = int(h // cell)
    off_y = y + (h - linhas * cell)          # encosta a grade no topo da área
    g = cell * _GAP
    for r in range(linhas):
        for col in range(_COLUNAS):
            kind = _weighted_choice(rng, _PESOS_VERSO)
            cor = PALETA_VERSO[rng.randrange(len(PALETA_VERSO))]
            _draw_tile_fechado(c, kind, x + col * cell + g / 2,
                               off_y + r * cell + g / 2, cell - g, cor, lw=1.1)


# Semente da página de arte: diferente da do verso para as duas grades, que
# ficam lado a lado no fim do folheto, não lerem como a mesma página repetida.
_SEMENTE_ARTE = 11


def draw_arte_complemento(c, page_w: float, page_h: float) -> None:
    """Página só de arte, que completa o folheto quando o total de páginas é ímpar.

    O folheto é impresso frente e verso, então um total ímpar deixava a última
    folha com um lado em branco, e o verso deixava de ser a última página. Esta
    página entra logo antes do verso e fecha a conta par.

    É a grade do verso em página inteira, sem logo, texto, stripe ou numeração:
    não é conteúdo, e por isso não pode parecer uma página que faltou preencher.
    A semente é fixa, então a página é a mesma em todos os folhetos.
    """
    c.setFillColor(WHITE)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    margem = page_w * 0.085         # mesma margem lateral do verso
    _draw_grade_verso(c, margem, margem, page_w - 2 * margem,
                      page_h - 2 * margem, semente=_SEMENTE_ARTE)


def draw_ultima_padrao(c, page_w: float, page_h: float, n_pagina: int,
                       url: str = "",
                       seed: int = 7,
                       lado: str = "dir"):
    """Verso: grade modular + logo FNP. Sem stripe nem numeração — borda livre.
    `seed` e `lado` ficam na assinatura por compatibilidade com os temas."""
    c.setFillColor(WHITE)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    margem_x = page_w * 0.085       # mesma margem relativa da arte quadrada
    logo_w, logo_y = 112, 40
    topo_grade = page_h - 60
    base_grade = logo_y + 70
    _draw_grade_verso(c, margem_x, base_grade, page_w - 2 * margem_x,
                      topo_grade - base_grade)

    if _ULTIMA_PNG.exists():
        draw_recorte(c, _ULTIMA_PNG, _ULTIMA_PX, _LOGO_FNP_PX,
                     (page_w - logo_w) / 2, logo_y, logo_w)
    else:
        c.setFillColor(BLUE_DARK)
        c.setFont(F("BarlowCondensed-Bold"), 14)
        c.drawCentredString(page_w / 2, logo_y + 10,
                            "FRENTE NACIONAL DE PREFEITAS E PREFEITOS")

    # URL discreta (se fornecida) no rodapé, abaixo do logo.
    if url:
        c.setFillColor(BLUE_DARK)
        c.setFont(F("Inter-Regular"), 7)
        c.drawCentredString(page_w / 2, 18, url)

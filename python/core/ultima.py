"""
Última página padrão FNP — usa o PNG `data/ifem/ultimapaginaifem.png` como
arte completa (grid modular + FNP). Sem dependência de dados externos.
"""
from pathlib import Path

from .tokens import (
    PAPER, WHITE, BLUE_DARK,
    STRIPE_W, ROOT_DIR,
)
from .fonts import F
from .components import draw_stripe, draw_page_number


_ULTIMA_PNG = ROOT_DIR / "data" / "ifem" / "ultimapaginaifem.png"


def draw_ultima_padrao(c, page_w: float, page_h: float, n_pagina: int,
                       url: str = "",
                       seed: int = 7,
                       lado: str = "dir"):
    """Última página: PNG `ultimapaginaifem.png` full-bleed.
    Stripe e numeração ainda aparecem no rodapé."""

    # Fundo branco (consistente com o resto do folheto, sem descrepância com a arte).
    c.setFillColor(WHITE)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # PNG full bleed (mantendo aspecto se quase quadrado)
    if _ULTIMA_PNG.exists():
        c.drawImage(str(_ULTIMA_PNG), 0, 0,
                    width=page_w, height=page_h,
                    preserveAspectRatio=False, mask="auto")
    else:
        c.setFillColor(BLUE_DARK)
        c.setFont(F("BarlowCondensed-Bold"), 14)
        c.drawCentredString(page_w / 2, page_h / 2,
                            "FRENTE NACIONAL DE PREFEITAS E PREFEITOS")

    # Última página sem stripe nem numeração — borda livre.

    # URL discreta (se fornecida) no rodapé, abaixo do logo do PNG
    if url:
        c.setFillColor(BLUE_DARK)
        c.setFont(F("Inter-Regular"), 7)
        c.drawCentredString(page_w / 2, 14, url)

"""
Registro de fontes Barlow Condensed + Inter com fallback automático.

Por que fallback automático: o gerador precisa rodar em qualquer máquina
(servidor de CI, máquina de outro desenvolvedor) sem depender de instalação
manual de fontes. Se o .ttf não estiver em fonts/, usa Helvetica.
"""
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .tokens import FONTS_DIR

_FONT_FILES = [
    ("BarlowCondensed-Bold",     "BarlowCondensed-Bold.ttf"),
    ("BarlowCondensed-SemiBold", "BarlowCondensed-SemiBold.ttf"),
    ("BarlowCondensed-Regular",  "BarlowCondensed-Regular.ttf"),
    ("Inter-Regular",            "Inter-Regular.ttf"),
    ("Inter-SemiBold",           "Inter-SemiBold.ttf"),
    ("Inter-Bold",               "Inter-Bold.ttf"),
]

_REGISTERED: dict[str, str] = {}


def register_fonts() -> dict[str, str]:
    """Registra fontes uma única vez. Retorna mapa logical→nome registrado."""
    if _REGISTERED:
        return _REGISTERED

    for logical_name, filename in _FONT_FILES:
        path = FONTS_DIR / filename
        if path.exists():
            pdfmetrics.registerFont(TTFont(logical_name, str(path)))
            _REGISTERED[logical_name] = logical_name
        else:
            # Fallback: Helvetica é built-in no ReportLab.
            _REGISTERED[logical_name] = "Helvetica-Bold" if "Bold" in logical_name else "Helvetica"

    return _REGISTERED


def F(key: str) -> str:
    """Retorna nome da fonte registrada (ou fallback). Use sempre F('...') no código."""
    if not _REGISTERED:
        register_fonts()
    return _REGISTERED.get(key, "Helvetica")

"""
Pré-processamento de assets do tema IFEM.

- `ifem_lettermark_vertical_path()`: gera (uma vez) uma versão vertical do
  `ifemestilo.png` em branco-com-transparência, pronto pra desenhar dentro do
  stripe azul. Resultado é cacheado em `data/ifem/_ifemestilo_stripe.png`.
"""
from pathlib import Path

from .tokens import ROOT_DIR

DATA_IFEM = ROOT_DIR / "data" / "ifem"

_SRC = DATA_IFEM / "ifemestilo.png"
_CACHE = DATA_IFEM / "_ifemestilo_stripe.png"


def ifem_lettermark_vertical_path() -> Path | None:
    """Retorna o caminho de uma versão branca-em-transparente do `ifemestilo.png`,
    rotacionada 90° no sentido horário (I no topo → M na base ao usar)."""
    if not _SRC.exists():
        return None
    if _CACHE.exists() and _CACHE.stat().st_mtime >= _SRC.stat().st_mtime:
        return _CACHE

    from PIL import Image
    img = Image.open(_SRC).convert("RGBA")
    # 90° anti-horário no PIL = letras lidas top→down quando desenhado (I no topo).
    img = img.rotate(90, expand=True)

    # Converte para branco-em-transparente: pixels claros ficam transparentes,
    # pixels escuros (strokes) viram brancos sólidos.
    pixels = img.load()
    for py in range(img.height):
        for px in range(img.width):
            r, g, b, a = pixels[px, py]
            # Threshold sensível: pixels muito claros = fundo branco.
            if (r + g + b) / 3 > 235:
                pixels[px, py] = (255, 255, 255, 0)
            else:
                pixels[px, py] = (255, 255, 255, 255)

    DATA_IFEM.mkdir(parents=True, exist_ok=True)
    img.save(_CACHE)
    return _CACHE

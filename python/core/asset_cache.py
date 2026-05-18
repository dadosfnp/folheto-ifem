"""
Cache em memória para assets que aparecem em todos os folhetos
(capa, metodologia, padrões decorativos, lettermark IFEM).

Por que existe: gerar 5.479 folhetos em lote relê os mesmos PNGs do disco
milhares de vezes — quando o conteúdo nunca muda. Aqui mantemos um único
`ImageReader` por path em RAM. Em projetos pequenos a economia é desprezível,
mas no lote completo reduz I/O de disco em ~80%.

Uso:
    from core.asset_cache import cached_image
    c.drawImage(cached_image(path), x, y, width=w, height=h)
"""
from pathlib import Path
from reportlab.lib.utils import ImageReader

_CACHE: dict[str, ImageReader] = {}


def cached_image(path) -> ImageReader:
    """Retorna o ImageReader cacheado para o caminho (ou cria e cacheia).
    O cache cresce sob demanda — basta esvaziar `_CACHE` se um asset mudar
    em runtime (raro: assets mudam só entre lotes/releases)."""
    key = str(Path(path).resolve())
    if key not in _CACHE:
        _CACHE[key] = ImageReader(key)
    return _CACHE[key]


def clear_cache() -> None:
    """Esvazia o cache. Útil para hot-reload durante desenvolvimento."""
    _CACHE.clear()

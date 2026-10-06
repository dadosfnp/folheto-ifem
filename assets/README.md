# Assets

Imagens e logos usados pelos folhetos. Organizados por subpasta.

## Estrutura

```
assets/
├── logos/
│   ├── fnp-logo.png         # Logo oficial FNP (rodapé de todas as páginas)
│   └── ifem-logo.png        # Logo IFEM (apenas folhetos do tema IFEM)
├── padroes/
│   └── (padrão modular geométrico — usar nas divisórias e capas)
└── (capas e fundos prontos)
    ├── capa-cosip.png       # Capa do tema COSIP
    ├── capa-ifem.png        # Capa do tema IFEM
    ├── ultima-clean.png     # Fundo da última página IFEM (com QR)
    └── ultima-cosip.png     # Fundo da última página COSIP
```

## Especificações

- **Capas e fundos de página inteira:** proporção do A5 retrato (≈ 1:1,42 — ex.:
  1240×1754px a 300 dpi). O código desenha esses PNGs na página inteira; uma arte
  quadrada sai esticada. As artes quadradas antigas do IFEM entram por recorte
  (`core/components.py::draw_recorte`).
- **Logos:** PNG com fundo transparente, alta resolução (mínimo 2× do tamanho final).
- **Padrões:** PNG ou vetor SVG; podem ser usados como fundo translúcido.

## Como o código resolve os caminhos

`python/core/tokens.py` define `ASSETS_DIR = ROOT_DIR / "assets"`.
Cada tema referencia explicitamente:

```python
from core.tokens import ASSETS_DIR
capa = ASSETS_DIR / "capa-ifem.png"
fnp  = ASSETS_DIR / "logos" / "fnp-logo.png"
```

Se um asset não existir, o código cai num fallback (fundo azul sólido) — isto é
intencional para que o gerador funcione mesmo antes dos assets finais chegarem.

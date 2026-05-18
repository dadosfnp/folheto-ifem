# Folhetos FNP

Gerador unificado de folhetos institucionais da **Frente Nacional de Prefeitas e Prefeitos**.
Cada folheto compartilha a mesma identidade visual — só os **dados** e o **conteúdo** mudam.

> Identidade visual canônica: ver [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md).
> Inspiração e referências: pasta [`inspiration/`](inspiration/).

## Estrutura

```
.
├── DESIGN_SYSTEM.md            # Identidade visual (paleta, tipografia, grid)
├── inspiration/                # Referências visuais (alfabeto modular, COSIP)
├── python/
│   ├── core/                   # Núcleo reusável — NÃO duplicar em temas
│   │   ├── tokens.py           # Cores, dimensões, tamanhos de fonte
│   │   ├── fonts.py            # Registro de fontes + fallback
│   │   ├── components.py       # Primitivas visuais (KPI, ranking, tabela…)
│   │   └── base_folheto.py     # Classe-base FolhetoFNP
│   ├── temas/                  # Um arquivo por folheto/tema
│   │   ├── ifem.py             # IFEM — Índice de Financiamento de Equidade
│   │   └── cosip.py            # COSIP — Iluminação e Monitoramento
│   └── gerar.py                # CLI unificada
├── data/                       # Dados de entrada (JSON por município/tema)
│   ├── ifem/
│   └── cosip/
├── assets/                     # Logos, capas, padrões
├── fonts/                      # Barlow Condensed + Inter (.ttf)
├── output/                     # PDFs gerados
└── requirements.txt
```

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Uso

```powershell
# Listar temas registrados
python python/gerar.py --listar

# Gerar um folheto
python python/gerar.py --tema ifem  --dados data/ifem/rio_de_janeiro.json
python python/gerar.py --tema cosip --dados data/cosip/rio_de_janeiro.json

# Gerar em lote (todos os JSONs de uma pasta)
python python/gerar.py --tema ifem --lote "data/ifem/*.json"
```

PDFs saem em `output/` com nome `<TemaClasse>_<Municipio>_<UF>.pdf`.

## Adicionar um folheto novo

Roteiro em 3 passos. Toda a identidade visual já vem do núcleo — você só
escreve o **conteúdo** das páginas.

### 1. Criar `python/temas/<tema>.py`

```python
from core.base_folheto import FolhetoFNP
from core.components import (
    draw_stripe, draw_page_number, draw_header, draw_footer,
    draw_eyebrow, draw_titulo, draw_body, draw_kpi_box,
    draw_section_divider, draw_qr_page,
)
from core.tokens import PAPER, MARGIN, CONTENT_W, FS_TITLE_SECAO

class FolhetoMeuTema(FolhetoFNP):
    titulo_publicacao = "MEU TEMA · SUBTÍTULO INSTITUCIONAL"

    def construir_paginas(self):
        return [self._pag_capa, self._pag_dados, self._pag_qr]

    def _pag_capa(self, c, n):
        # ...usa primitivas de core/components.py
        ...
```

### 2. Registrar em `python/temas/__init__.py`

```python
from .meu_tema import FolhetoMeuTema

TEMAS = {
    "ifem":     FolhetoIFEM,
    "cosip":    FolhetoCOSIP,
    "meu_tema": FolhetoMeuTema,   # ← novo
}
```

### 3. Criar `data/<tema>/<municipio>.json`

Estrutura livre — você define o que `self.d` contém quando o folheto monta as páginas.

## Princípios de manutenção

- **Tokens só em `core/tokens.py`**. Cores, tamanhos, dimensões — nunca hardcodar
  em arquivos de tema. Mudou a paleta? Mexa só num lugar.
- **Componentes em `core/components.py`**. Se um padrão visual aparece em 2+ temas,
  vira componente. Não copiar/colar entre temas.
- **Temas só sabem de conteúdo**. Cada `temas/*.py` deve ler como um roteiro
  ("aqui vai a capa, depois o problema, depois os dados…") usando primitivas.
- **Dados externos em JSON**. Não hardcodar dados no código Python — o mesmo tema
  serve qualquer município, basta trocar o JSON.

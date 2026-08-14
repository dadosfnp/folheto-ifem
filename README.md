# Folhetos FNP

Gerador unificado de folhetos institucionais da **Frente Nacional de Prefeitas e Prefeitos**.
Cada folheto compartilha a mesma identidade visual — só os **dados** e o **conteúdo** mudam.

> **Primeira vez aqui?** Vá direto para [`docs/PASSO_A_PASSO.md`](docs/PASSO_A_PASSO.md) —
> guia completo do zero até o PDF na mão, incluindo o acesso ao banco.

---

## Setup em 4 passos

```powershell
# 1. Ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependências
pip install -r requirements.txt

# 3. Fontes oficiais (Barlow Condensed + Inter) — NÃO vêm no git
python tools/baixar_fontes.py

# 4. Dados dos municípios — NÃO vêm no git
python tools/sync_dados.py
```

### Por que os passos 3 e 4 existem

Duas coisas ficam fora do git de propósito, e **ambas mudam o PDF final**:

| O quê | Por que fora do git | Sem ele o PDF… |
|---|---|---|
| `fonts/*.ttf` | licença + peso | sai em Helvetica, com tipografia diferente da oficial |
| `data/ifem/dados-ifem/export_folheto/` | 5.479 arquivos, ~94 MB, regeneráveis do banco | não gera — não há município nenhum |

Pular esses passos não dá erro: o gerador **degrada e continua**. Por isso os dois
scripts acima existem, e por isso o gerador agora avisa em `stderr` quando está
usando fallback. Se aparecer `[aviso]` na saída, o PDF **não** está fiel ao oficial.

---

## Gerar folhetos

```powershell
# Listar temas registrados
python python/gerar.py --listar

# Um município
python python/gerar.py --tema ifem `
  --dados data/ifem/dados-ifem/export_folheto/3304557_rio-de-janeiro-rj.json

# Em lote — atenção: o glob abaixo gera os 5.479 municípios
python python/gerar.py --tema ifem --lote "data/ifem/dados-ifem/export_folheto/*.json"

# Lote de um estado só (ex.: Ceará)
python python/gerar.py --tema ifem --lote "data/ifem/dados-ifem/export_folheto/*-ce.json"
```

Os PDFs saem em `output/` como `<TemaClasse>_<Municipio>_<UF>.pdf`.

### Achar o arquivo de um município

Os nomes seguem `<cod_ibge>_<slug-do-municipio>-<uf>.json`:

```powershell
Get-ChildItem data/ifem/dados-ifem/export_folheto -Filter "*fortaleza*"
```

---

## Atualizar os dados

Os dados vêm do banco do **Subfinanciados** (PostgreSQL gerenciado, database `ifem`).
O ciclo completo:

```
banco ifem  ──►  exports do Subfinanciados  ──►  sync_dados.py  ──►  gerar.py  ──►  PDF
```

```powershell
# 1. No Subfinanciados — regenera os JSONs a partir do banco
cd ..\Subfinanciados
python export_folheto_municipios.py        # 1 JSON por município + _metodologia.json
python export_folheto_complementares.py    # _medias_receitas.json
python validate_export_folheto.py          # confere o schema do lote

# 2. De volta aqui — traz os JSONs para dentro deste repo
cd "..\Folhetos FNP"
python tools/sync_dados.py
```

O passo detalhado (credenciais, o que cada script faz, o que checar) está em
[`docs/PASSO_A_PASSO.md`](docs/PASSO_A_PASSO.md).

> **`_problema.json` é a exceção.** É texto editorial — nenhum export o gera.
> Ele vive versionado em [`data/ifem/_problema.json`](data/ifem/_problema.json)
> e o `sync_dados.py` o injeta no lote. Para mudar o texto da página "O Problema",
> edite esse arquivo e commite.

---

## Publicar (PDFs + landing page)

Os PDFs são hospedados como assets de **GitHub Release** — não vão para o repo:

```powershell
# 1. Sobe os PDFs de output/ numa release
gh release create v2 output/FolhetoIFEM_*.pdf `
  --title "Folhetos IFEM v2" --notes "Lote atualizado."

# 2. Regenera o índice que a landing lê
python tools/build_site.py --release-tag v2
```

`tools/build_site.py` só reescreve `docs/folhetos.json` com as URLs da release —
o GitHub Pages serve `docs/index.html`.

> Nomes de arquivo com acento são descartados pelo GitHub Releases. O gerador já
> normaliza os nomes; não renomeie na mão.

---

## Estrutura

```
.
├── DESIGN_SYSTEM.md            # Identidade visual (paleta, tipografia, grid)
├── docs/
│   ├── PASSO_A_PASSO.md        # Guia do zero ao PDF (comece por aqui)
│   ├── index.html              # Landing page (GitHub Pages)
│   └── folhetos.json           # Índice gerado por tools/build_site.py
├── inspiration/                # Referências visuais (alfabeto modular, COSIP)
├── python/
│   ├── core/                   # Núcleo reusável — NÃO duplicar em temas
│   │   ├── tokens.py           # Cores, dimensões, tamanhos de fonte
│   │   ├── fonts.py            # Registro de fontes + fallback (avisa se faltar)
│   │   ├── components.py       # Primitivas visuais (KPI, ranking, tabela…)
│   │   └── base_folheto.py     # Classe-base FolhetoFNP
│   ├── temas/                  # Um arquivo por folheto/tema
│   │   ├── ifem.py             # IFEM — Índice de Financiamento e Equidade Municipal
│   │   └── cosip.py            # COSIP — Iluminação e Monitoramento
│   └── gerar.py                # CLI unificada
├── tools/
│   ├── baixar_fontes.py        # Setup: baixa Barlow Condensed + Inter
│   ├── sync_dados.py           # Setup: traz os JSONs do Subfinanciados
│   └── build_site.py           # Publicação: índice da landing
├── data/
│   ├── ifem/
│   │   ├── SCHEMA.md           # Contrato dos JSONs de entrada
│   │   ├── _problema.json      # Texto editorial (versionado)
│   │   └── dados-ifem/         # JSONs do export (NÃO versionado)
│   └── cosip/
├── assets/                     # Logos, capas, padrões
├── fonts/                      # Barlow Condensed + Inter (NÃO versionado)
├── output/                     # PDFs gerados
└── requirements.txt
```

---

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

Arquivos começando com `_` na pasta de dados são tratados como **companheiros
compartilhados** e injetados em todos os municípios do tema (ver `gerar.py`).

---

## Princípios de manutenção

- **Tokens só em `core/tokens.py`**. Cores, tamanhos, dimensões — nunca hardcodar
  em arquivos de tema. Mudou a paleta? Mexa só num lugar.
- **Componentes em `core/components.py`**. Se um padrão visual aparece em 2+ temas,
  vira componente. Não copiar/colar entre temas.
- **Temas só sabem de conteúdo**. Cada `temas/*.py` deve ler como um roteiro
  ("aqui vai a capa, depois o problema, depois os dados…") usando primitivas.
- **Dados externos em JSON**. Não hardcodar dados no código Python — o mesmo tema
  serve qualquer município, basta trocar o JSON.
- **Degradação é sempre barulhenta**. Fonte ausente, companheiro ausente, dado
  faltando: o gerador continua, mas avisa em `stderr`. Nunca transforme um aviso
  desses em silêncio — foi exatamente assim que PDFs divergentes circularam.

> Identidade visual canônica: [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md).
> Contrato dos dados IFEM: [`data/ifem/SCHEMA.md`](data/ifem/SCHEMA.md).

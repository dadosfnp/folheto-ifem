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

# 4. Configuração: copie o template e ajuste os caminhos
Copy-Item .env.example .env

# 5. Dados dos municípios — gerados das planilhas oficiais
python tools/planilhas_para_json.py --todos

# 6. Risco climático (AdaptaBrasil) — enriquece os JSONs do passo 5
python tools/adapta_para_json.py --injetar --todos
```

### Por que os passos 3, 5 e 6 existem

Três coisas ficam fora do git de propósito, e **todas mudam o PDF final**:

| O quê | Por que fora do git | Sem ele o PDF… |
|---|---|---|
| `fonts/*.ttf` | licença + peso | sai em Helvetica, com tipografia diferente da oficial |
| `data/ifem/dados-ifem/` | 5.440 arquivos, ~94 MB, regeneráveis | não gera — não há município nenhum |
| bloco `risco_climatico` | derivado, mora dentro do lote acima | sai com 2 páginas a menos: a seção de Risco Climático some inteira |

Pular esses passos não dá erro: o gerador **degrada e continua**. Por isso os dois
scripts acima existem, e por isso o gerador avisa em `stderr` quando está usando
fallback. Se aparecer `[aviso]` na saída, o PDF **não** está fiel ao oficial.

### De onde vêm os dados

`tools/planilhas_para_json.py` lê as planilhas oficiais em
`<Subfinanciados>/base_datas/` — a **mesma fonte** que popula o banco do IFEM em
produção — e escreve os JSONs que o gerador consome.

Não precisa de banco, de rede, nem de credencial. O caminho das planilhas fica em
`PLANILHAS_DIR` no `.env`; a rastreabilidade completa está em
[`data/ifem/PROVENIENCIA.md`](data/ifem/PROVENIENCIA.md).

> **Alternativa:** se você tiver acesso ao banco (só de dentro da VPC da
> DigitalOcean), `python tools/sync_dados.py` traz o lote gerado pelos exports do
> Subfinanciados. Os dois caminhos produzem o mesmo resultado.

`tools/adapta_para_json.py` faz o mesmo com `indicadores_adapta_brasil.xlsx` — a
planilha que alimenta a tabela `AdaptaBrasil` do banco. Com `--injetar` ele grava
o bloco `risco_climatico` dentro dos JSONs do passo 5 (é idempotente) e escreve
os agregados nacionais em `data/clima/_panorama_nacional.json`, o único arquivo
de dados versionado. Rastreabilidade em
[`data/clima/PROVENIENCIA.md`](data/clima/PROVENIENCIA.md).

> ⚠️ **A escala do risco é invertida em relação ao IFEM.** No IFEM, valor alto =
> município bem financiado. No AdaptaBrasil, o índice mede exposição: valor alto
> = pior, e `ranking_nacional.posicao == 1` é o município **mais** exposto do
> país. As páginas de risco têm o próprio mapa de cores por isso.

### Ano de referência

O ano impresso nos folhetos vem de `ANO_REF` no `.env` — **nunca** de um literal
no código. Para virar o ano:

1. Confirme que existe `receitas_correntes_<ANO>.xlsx` em `base_datas/`
2. Atualize `ANO_REF` no `.env`
3. `python tools/planilhas_para_json.py --todos`
4. `python tools/recalcular_problema.py --aplicar` (números da página "O Problema")

As **chaves** dos JSONs mantêm o sufixo `_2024` (`sintese_fiscal_2000_2024`,
`posicao_historica.ano_2024`) mesmo com dados mais novos — é contrato interno
herdado do Subfinanciados. Não derive o ano delas.

---

## Gerar folhetos

```powershell
# Listar temas registrados
python python/gerar.py --listar

# Um município
python python/gerar.py --tema ifem `
  --dados data/ifem/dados-ifem/export_folheto/3304557_rio-de-janeiro-rj.json

# Recorte publicado: municípios acima de 80 mil habitantes (417)
python python/gerar.py --tema ifem `
  --lote "data/ifem/dados-ifem/export_folheto/*.json" --pop-minima 80000

# Um estado só (ex.: Ceará)
python python/gerar.py --tema ifem --lote "data/ifem/dados-ifem/export_folheto/*-ce.json"

# Todos os 5.440 — demora bastante e ocupa vários GB
python python/gerar.py --tema ifem --lote "data/ifem/dados-ifem/export_folheto/*.json"
```

Os PDFs saem em `output/` como `<TemaClasse>_<Municipio>_<UF>.pdf`.

### Achar o arquivo de um município

Os nomes seguem `<cod_ibge>_<slug-do-municipio>-<uf>.json`:

```powershell
Get-ChildItem data/ifem/dados-ifem/export_folheto -Filter "*fortaleza*"
```

---

## Atualizar os dados

O ciclo completo, sem banco:

```
planilhas (base_datas/*.xlsx)  ──►  planilhas_para_json.py  ──►  gerar.py  ──►  PDF
```

```powershell
# 1. Regenera os JSONs a partir das planilhas oficiais
python tools/planilhas_para_json.py --todos

# 2. Atualiza os números da página "O Problema" (mostra antes/depois)
python tools/recalcular_problema.py            # confere
python tools/recalcular_problema.py --aplicar  # grava

# 3. Gera o recorte publicado
python python/gerar.py --tema ifem `
  --lote "data/ifem/dados-ifem/export_folheto/*.json" --pop-minima 80000
```

O passo a passo detalhado está em [`docs/PASSO_A_PASSO.md`](docs/PASSO_A_PASSO.md).

> **Dois companheiros são conteúdo editorial** — nenhum script os gera do zero, e
> por isso vivem versionados no repo:
> [`data/ifem/_problema.json`](data/ifem/_problema.json) e
> [`data/ifem/_metodologia.json`](data/ifem/_metodologia.json). Os scripts de
> setup copiam essa versão para o lote a cada execução, e a cópia do repo **vence**
> a que vier de export: é ela a fonte da verdade do texto.
>
> No caso do `_problema.json`, o `recalcular_problema.py` atualiza os **números**;
> o **texto corrido** que cita valores por extenso precisa de revisão humana — o
> script aponta quais frases ficaram inconsistentes, mas não as reescreve.

### Validar o lote

O Subfinanciados tem um validador de schema que serve para conferir qualquer lote:

```powershell
# aponte EXPORT_DIR para data/ifem/dados-ifem/export_folheto/ numa cópia do script
python validate_export_folheto.py
```

Ele checa as chaves de topo, `supera_pct_nacional` (0–100) em todas as rubricas,
a hierarquia 4/14/28 e a consistência referencial.

### Validar os PDFs antes de publicar

```powershell
python tools/verificar_arte.py output/
```

Mede, no PDF gerado, se a arte decorativa do rodapé cobre texto ou gráfico —
defeito que não gera erro nenhum (o arquivo abre, o texto continua extraível) e
só aparece para quem olha a página. Sai com código 1 se achar qualquer colisão.
Rodar **sempre** antes do `gh release create`.

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
│   │   ├── _metodologia.json   # Texto editorial (versionado)
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

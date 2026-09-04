# Folhetos FNP

Gerador unificado de folhetos institucionais da **Frente Nacional de Prefeitas e Prefeitos**.
Cada folheto compartilha a mesma identidade visual — só os **dados** e o **conteúdo** mudam.

> **Primeira vez aqui?** Vá direto para [`docs/PASSO_A_PASSO.md`](docs/PASSO_A_PASSO.md) —
> guia completo do zero até o PDF na mão, incluindo o acesso ao banco.
>
> **Vai mexer no folheto?** [`docs/COMO_ALTERAR_O_FOLHETO.md`](docs/COMO_ALTERAR_O_FOLHETO.md) —
> onde fica cada página, como mudar texto, cor, tabela, e o que quebra em silêncio.

## O caminho completo, do zero ao ar

Tudo abaixo roda sem depender de ninguém. As três armadilhas conhecidas estão
marcadas com ⚠️ — são silenciosas: o PDF sai, só sai **errado**.

| # | Etapa | Onde |
|---|---|---|
| 1 | Clonar os dois repos, venv, dependências, fontes, `.env` | [Setup](#setup) |
| 2 | ⚠️ Conferir a versão da planilha do AdaptaBrasil | [Duas versões](#a-planilha-do-adaptabrasil-tem-duas-versões) |
| 3 | Gerar os JSONs das planilhas | [Setup](#setup), passo 6 |
| 4 | ⚠️ Injetar o risco climático — sem isso faltam 2 páginas | [Setup](#setup), passo 7 |
| 5 | Gerar o recorte de 417 municípios | [Gerar folhetos](#gerar-folhetos) |
| 6 | ⚠️ Gerar os 7 que não declararam — eles **não** saem no lote | [Gerar folhetos](#gerar-folhetos) |
| 7 | Validar os 424 PDFs antes de subir | [Validar os PDFs](#validar-os-pdfs-antes-de-publicar) |
| 8 | Release + reindexar + **merge na main** | [Publicar](#publicar-pdfs-e-landing-page) |

**Se algo sair estranho, comece por aqui:** todo erro conhecido deste projeto é
de degradação silenciosa — fonte faltando, companheiro faltando, risco faltando,
município faltando. Nenhum deles derruba o gerador. Rode
`python tools/verificar_arte.py output/`, confira se `output/` tem 424 PDFs e se
um folheto qualquer tem 14 ou 15 páginas (12 significa que o risco climático não
entrou).

---

## Setup

```powershell
# 1. Os dois repositórios, lado a lado. O Subfinanciados é só leitura aqui:
#    é dele que saem as planilhas com TODOS os números dos folhetos.
git clone git@github.com:dadosfnp/folheto-ifem.git
git clone <url-do-Subfinanciados>

cd folheto-ifem

# 2. Ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Dependências
pip install -r requirements.txt

# 4. Fontes oficiais (Barlow Condensed + Inter) — NÃO vêm no git
python tools/baixar_fontes.py

# 5. Configuração: copie o template e ajuste PLANILHAS_DIR para a SUA máquina
Copy-Item .env.example .env
notepad .env

# 6. Dados dos municípios — gerados das planilhas oficiais
python tools/planilhas_para_json.py --todos

# 7. Risco climático — enriquece os JSONs do passo 6.
#    Aborta se a planilha do AdaptaBrasil for a versão errada (ver seção abaixo).
python tools/adapta_para_json.py --injetar --todos
```

> O passo 5 é o único que **precisa** ser editado à mão: o `.env.example` traz o
> caminho da máquina de quem escreveu. Aponte `PLANILHAS_DIR` para o
> `base_datas/` do **seu** clone do Subfinanciados.

### A planilha do AdaptaBrasil tem duas versões

Circulam duas versões do `indicadores_adapta_brasil.xlsx` no Subfinanciados, com
um dia de diferença — e a branch de trabalho costuma vir com a **incompleta**:

| Versão | Colunas | Serve? |
|---|---|---|
| 06/08 | `geocod_ibge` + os 12 indicadores | ❌ |
| 07/08 | `cod_ibge`, `pontuacao_risco_norm_pond`, `quintil`, `decil` + os 12 | ✅ |

`pontuacao_risco_norm_pond` é a média ponderada de risco: dela saem a nota grande
da faixa de destaque, a classe de risco e os rankings nacional e estadual. Ela
**não** é a média dos 12 indicadores (difere até 0,34), então não há como
recalcular a partir da versão incompleta.

Se você estiver com a errada, o script aborta e explica. Para trocar:

```powershell
cd <Subfinanciados>
git log --all --oneline -- base_datas/indicadores_adapta_brasil.xlsx
git checkout <commit-que-tem-cod_ibge> -- base_datas/indicadores_adapta_brasil.xlsx
```

**Não ignore este passo.** Sem ele o `--injetar` falha, o lote fica sem o bloco
`risco_climatico`, e **todo folheto sai com 2 páginas a menos** — o PDF abre
normalmente e nada mais avisa.

### Por que os passos 4, 6 e 7 existem

Três coisas ficam fora do git de propósito, e **todas mudam o PDF final**:

| O quê | Por que fora do git | Sem ele o PDF… |
|---|---|---|
| `fonts/*.ttf` | licença + peso | sai em Helvetica, com tipografia diferente da oficial |
| `data/ifem/dados-ifem/` | 5.440 arquivos, ~94 MB, regeneráveis | não gera — não há município nenhum |
| bloco `risco_climatico` | derivado, mora dentro do lote acima | sai com 2 páginas a menos: a seção de Risco Climático some inteira |

Pular esses passos não dá erro: o gerador **degrada e continua**. Por isso os dois
scripts acima existem, e por isso o gerador avisa em `stderr` quando está usando
fallback. Se aparecer `[aviso]` na saída, o PDF **não** está fiel ao oficial.

**A exceção:** [`data/ifem/fallback_2024/`](data/ifem/fallback_2024/) é dado de
município e mesmo assim vai para o git. São os 7 do recorte que não declararam
receita de 2025, e o dado de 2024 deles **não é regenerável** — `base_datas/` só
tem `receitas_correntes_2000.xlsx` e `receitas_correntes_2025.xlsx`. Vale a regra
da casa: o que nenhum script recria tem que estar versionado.

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
o bloco `risco_climatico` dentro dos JSONs do passo 6 (é idempotente) e escreve
os agregados nacionais em `data/clima/_panorama_nacional.json`, o único arquivo
de dados versionado. Rastreabilidade em
[`data/clima/PROVENIENCIA.md`](data/clima/PROVENIENCIA.md).

> ⚠️ **A escala do risco é invertida em relação ao IFEM.** No IFEM, valor alto =
> município bem financiado. No AdaptaBrasil, o índice mede exposição: valor alto
> = pior, e `ranking_nacional.posicao == 1` é o município **mais** exposto do
> país. As páginas de risco têm o próprio mapa de cores por isso.

> ⚠️ Esta planilha tem **duas versões** no Subfinanciados e só uma serve — ver
> [A planilha do AdaptaBrasil tem duas versões](#a-planilha-do-adaptabrasil-tem-duas-versões).

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

# Os 7 que não declararam no ano: saem com o dado de 2024 + ressalva (total 424)
python tools/gerar_sem_declaracao.py

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

```powershell
python tools/verificar_texto.py output/
```

Checa a convenção tipográfica da publicação: nenhum travessão (—) em texto
impresso. A meia-risca (–) de intervalo, como em "2000–2025", é permitida e não
é acusada.

Rodar os dois **sempre** antes do `gh release create`.

---

## Publicar (PDFs e landing page)

Os PDFs são hospedados como assets de **GitHub Release** — não vão para o repo.
A landing (`docs/index.html`, servida pelo GitHub Pages a partir da `main`) lê o
`docs/folhetos.json`, que aponta para os assets da release.

### Antes: o que você precisa ter

```powershell
gh auth status      # precisa de escrita em dadosfnp/folheto-ifem
```

Sem isso, `gh release create` falha com 403. Se falhar, peça acesso de escrita ao
repositório — não há como publicar sem ele.

### O lote completo, do zero ao ar

```powershell
# 1. Gera os 424: o recorte (417) + os que não declararam (7)
python python/gerar.py --tema ifem `
  --lote "data/ifem/dados-ifem/export_folheto/*.json" --pop-minima 80000
python tools/gerar_sem_declaracao.py

# 2. VALIDE antes de subir (1,5 GB de upload é caro de refazer)
python tools/verificar_arte.py output/
(Get-ChildItem output/*.pdf).Count      # tem que dar 424

# 3. Sobe os PDFs numa tag nova (não reaproveite tag publicada)
gh release create v6 --title "Folhetos IFEM 2025" --notes "Lote atualizado."
gh release upload v6 output/FolhetoIFEM_*.pdf

# 4. Reindexa a landing para a tag nova
python tools/build_site.py --release-tag v6

# 5. Confira o que o índice ficou apontando
python -c "import json;d=json.load(open('docs/folhetos.json',encoding='utf-8'));print(d['release_tag'],d['total'])"

# 6. Publica o índice (a landing só muda quando isto entra na main)
git checkout -b chore/reindexa-v6
git add docs/folhetos.json
git commit -m "chore(site): reindexa o folhetos.json para a release v6"
git push -u origin chore/reindexa-v6
gh pr create --base main --fill
gh pr merge --merge --delete-branch
```

> **Esse último passo não é opcional.** A release nova não muda nada sozinha: enquanto o
> `folhetos.json` da `main` apontar para a tag antiga, a landing continua
> entregando os PDFs velhos.

### Conferir que subiu

```powershell
# assets na release: tem que dar 424
gh release view v6 --json assets --jq '.assets | length'

# a landing está servindo o índice novo?
$j = Invoke-RestMethod "https://dadosfnp.github.io/folheto-ifem/folhetos.json"
"$($j.release_tag) $($j.total)"      # esperado: v6 424
```

O Pages leva um ou dois minutos para publicar depois do merge.

> Se o `gh release upload` engasgar com 424 arquivos de uma vez, suba em lotes de
> ~40. Nomes com acento são normalizados pelo gerador (`Anápolis` → `Anapolis`) e
> o `build_site.py` já monta as URLs nessa forma — **não renomeie nada à mão**,
> ou a landing dá 404.

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
│   │   ├── fallback_2024/      # Dado 2024 dos que não declararam (versionado:
│   │   │                       #   não é regenerável — ver README de lá)
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

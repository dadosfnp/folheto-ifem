# Passo a passo — do zero ao folheto

Guia completo para gerar folhetos IFEM a partir dos dados que já estão no banco.
Do clone até o PDF na mão. Feito para quem nunca rodou este projeto.

**Tempo estimado:** ~15 minutos na primeira vez.

---

## Antes de começar

Você vai precisar de:

| Item | Como conferir |
|---|---|
| Python 3.10+ | `python --version` |
| Git | `git --version` |
| Acesso ao banco `ifem` | senha da role `ifem_app` — peça ao Pedro |
| `gh` CLI (só para publicar) | `gh --version` |

E de **dois repositórios**, que fazem coisas diferentes:

| Repositório | Papel |
|---|---|
| [`dadosfnp/Subfinanciados`](https://github.com/dadosfnp/Subfinanciados) | fala com o banco e **exporta** os JSONs |
| [`dadosfnp/folheto-ifem`](https://github.com/dadosfnp/folheto-ifem) | lê os JSONs e **gera** os PDFs |

> ⚠️ Existe um repositório antigo chamado `dadosfnp/folheto_ifem` (com **underscore**),
> parado desde janeiro/2026. Não é esse. O certo é **`folheto-ifem`**, com hífen.

O fluxo inteiro:

```
banco ifem ──► export_folheto_municipios.py ──► export_folheto/*.json
                                                        │
                                              sync_dados.py
                                                        ▼
                                              gerar.py ──► output/*.pdf
```

---

## Parte 1 — Clonar os dois repositórios

Clone os dois **lado a lado, na mesma pasta pai**. O `sync_dados.py` procura o
Subfinanciados como repositório irmão — se você mudar isso, vai precisar apontar
o caminho na mão depois.

```powershell
cd C:\seus\projetos

git clone git@github.com:dadosfnp/Subfinanciados.git
git clone git@github.com:dadosfnp/folheto-ifem.git "Folhetos FNP"
```

Resultado esperado:

```
C:\seus\projetos\
├── Subfinanciados\
└── Folhetos FNP\
```

---

## Parte 2 — Configurar o Subfinanciados

### 2.1 Ambiente e dependências

```powershell
cd C:\seus\projetos\Subfinanciados

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2.2 Apontar para o banco

Copie o template e edite:

```powershell
Copy-Item .env.example .env
notepad .env
```

No `.env`, **descomente** a linha `DATABASE_URL` e preencha a senha:

```ini
DATABASE_URL=postgresql://ifem_app:SENHA_AQUI@fnp-database-do-user-37776190-0.k.db.ondigitalocean.com:25060/ifem?sslmode=require
```

Preencha também as chaves obrigatórias do Django (`DJANGO_SECRET_KEY`,
`DJANGO_DEBUG=True`, `ALLOWED_HOSTS=localhost`).

> 🔒 **A senha nunca entra no git.** O `.env` já está no `.gitignore` do
> Subfinanciados — confirme com `git status` que ele não aparece antes de commitar
> qualquer coisa. Peça a senha da role `ifem_app` ao Pedro por canal privado.

> Se `DATABASE_URL` ficar comentada, o Django cai em **SQLite local vazio** e os
> exports geram zero municípios. Esse é o modo "rodar sem banco" — não serve aqui.

### 2.3 Testar a conexão

```powershell
python check_db.py
```

Se conectar, você está pronto. Se der erro de SSL ou timeout, veja
[Problemas comuns](#problemas-comuns).

---

## Parte 3 — Exportar os dados do banco

Ainda dentro do `Subfinanciados`, com a venv ativa:

```powershell
# 1. Um JSON por município + _metodologia.json  (demora alguns minutos)
python export_folheto_municipios.py

# 2. Médias e medianas de receita por rubrica -> _medias_receitas.json
python export_folheto_complementares.py

# 3. Confere se o lote saiu no schema esperado
python validate_export_folheto.py
```

Isso cria `Subfinanciados/export_folheto/` com:

```
export_folheto/
├── _metodologia.json                       ← texto da metodologia
├── _medias_receitas.json                   ← médias/medianas por rubrica
├── 1100015_alta-floresta-d-oeste-ro.json   ← 1 por município
├── 3304557_rio-de-janeiro-rj.json
└── … (5.479 municípios no total)
```

### Exportar só alguns municípios

Os dois scripts aceitam filtros — útil para testar rápido sem esperar o lote todo:

```powershell
python export_folheto_municipios.py --limit 10
python export_folheto_municipios.py --cod_ibge 3304557,2304400
```

> Se usar `--limit` ou `--cod_ibge`, rode os **dois** scripts com o mesmo filtro,
> senão os arquivos complementares ficam fora de sincronia com os municipais.

---

## Parte 4 — Configurar o gerador de folhetos

```powershell
cd "C:\seus\projetos\Folhetos FNP"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4.1 Baixar as fontes oficiais

```powershell
python tools/baixar_fontes.py
```

Saída esperada:

```
Barlow Condensed (google/fonts):
  + BarlowCondensed-Bold.ttf (107 KB)
  + BarlowCondensed-SemiBold.ttf (106 KB)
  + BarlowCondensed-Regular.ttf (100 KB)

Inter (rsms/inter v4.1):
  . baixando Inter-4.1.zip (~32 MB) para extrair 3 arquivo(s)...
  + Inter-Regular.ttf (401 KB)
  + Inter-SemiBold.ttf (409 KB)
  + Inter-Bold.ttf (410 KB)

Baixados agora: 6 | No disco: 6/6
Fontes completas — os PDFs sairão com a tipografia oficial FNP.
```

**Este passo não é opcional.** As fontes não vêm no git. Sem elas o gerador não
quebra — ele troca tudo por Helvetica e o folheto sai com outra cara. Foi assim
que dois PDFs diferentes já saíram do mesmo commit.

### 4.2 Trazer os dados exportados

```powershell
python tools/sync_dados.py
```

Ele acha o `Subfinanciados` sozinho se os repositórios forem irmãos. Se você
clonou em outro lugar:

```powershell
python tools/sync_dados.py --origem "D:\outro\caminho\Subfinanciados"
```

Saída esperada:

```
Encontrados: 5479 municípios + 3 arquivo(s) compartilhado(s)
Copiados: 5482 | Inalterados: 0
```

---

## Parte 5 — Gerar folhetos

### Um município

```powershell
python python/gerar.py --tema ifem `
  --dados data/ifem/dados-ifem/export_folheto/3304557_rio-de-janeiro-rj.json
```

O PDF sai em `output/FolhetoIFEM_Rio_de_Janeiro_RJ.pdf`.

### Achar o arquivo do município que você quer

O padrão é `<codigo_ibge>_<slug>-<uf>.json`:

```powershell
Get-ChildItem data/ifem/dados-ifem/export_folheto -Filter "*fortaleza*"
```

### Em lote

```powershell
# Um estado inteiro (ex.: Ceará)
python python/gerar.py --tema ifem --lote "data/ifem/dados-ifem/export_folheto/*-ce.json"

# Todos os 5.479 municípios — demora bastante e enche o disco
python python/gerar.py --tema ifem --lote "data/ifem/dados-ifem/export_folheto/*.json"
```

No modo lote, um município que falhe não derruba os outros: o erro vai para
`stderr` e a geração continua.

### ✅ Como saber que deu certo

A saída de um folheto correto é **só** isto:

```
[OK] C:\...\output\FolhetoIFEM_Rio_de_Janeiro_RJ.pdf
```

**Qualquer linha `[aviso]` significa que o PDF saiu incompleto ou fora do padrão
visual.** Não distribua — resolva o aviso primeiro (veja abaixo).

---

## Parte 6 — Publicar (opcional)

Os PDFs ficam em GitHub Releases, não no repositório:

```powershell
gh release create v2 output/FolhetoIFEM_*.pdf `
  --title "Folhetos IFEM v2" --notes "Lote atualizado."

python tools/build_site.py --release-tag v2
```

Depois commite o `docs/folhetos.json` atualizado — é ele que a landing page lê.

---

## Problemas comuns

### `[aviso] N de 6 fontes ausentes … usando Helvetica no lugar`

Você pulou o passo 4.1. Rode `python tools/baixar_fontes.py`.
O PDF gerado antes disso está com a tipografia errada — refaça.

### `[aviso] _problema.json não encontrado`

A página "O Problema" vai sair vazia. Esse arquivo é texto editorial, não sai de
nenhum export — ele é versionado em `data/ifem/_problema.json` e o `sync_dados.py`
o injeta no lote. Rode `python tools/sync_dados.py` de novo.

### `Nenhum .json em … — os exports rodaram?`

A pasta `Subfinanciados/export_folheto/` está vazia. Volte para a Parte 3.

### `Pasta de origem não encontrada`

Os repositórios não estão lado a lado. Use
`python tools/sync_dados.py --origem "<caminho do Subfinanciados>"`.

### Exports geram 0 municípios

`DATABASE_URL` está comentada ou errada no `.env` — o Django está usando o SQLite
local vazio. Confira a Parte 2.2 e rode `python check_db.py`.

### Erro de SSL ao conectar no banco

A URL precisa terminar com `?sslmode=require`. O banco gerenciado recusa conexão
sem TLS.

### `FileNotFoundError: Arquivo de dados não encontrado`

Caminho do `--dados` errado. Confirme com o `Get-ChildItem` da Parte 5. No
PowerShell, use aspas em caminhos com espaço.

### O PDF saiu diferente do de outra pessoa

Confira, nesta ordem:

1. **Fontes** — `Get-ChildItem fonts/*.ttf` deve listar **6** arquivos nas duas máquinas.
2. **Commit** — `git log -1 --oneline` deve bater.
3. **Data dos dados** — se um exportou o lote antes de uma atualização do banco,
   os números divergem. Rode a Parte 3 de novo dos dois lados.

---

## Referências

- [`README.md`](../README.md) — visão geral e comandos do dia a dia
- [`data/ifem/SCHEMA.md`](../data/ifem/SCHEMA.md) — contrato dos JSONs de entrada
- [`DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md) — paleta, tipografia e grid

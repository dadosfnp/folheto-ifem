# Passo a passo — do zero ao folheto

Guia completo para gerar folhetos IFEM. Do clone até o PDF na mão.
Feito para quem nunca rodou este projeto.

**Tempo estimado:** ~10 minutos na primeira vez. Não precisa de banco de dados.

---

## Antes de começar

| Item | Como conferir |
|---|---|
| Python 3.10+ | `python --version` |
| Git | `git --version` |
| Acesso ao repo Subfinanciados | é de lá que vêm as planilhas |
| `gh` CLI (só para publicar) | `gh --version` |

E de **dois repositórios**:

| Repositório | Papel |
|---|---|
| [`dadosfnp/Subfinanciados`](https://github.com/dadosfnp/Subfinanciados) | guarda as **planilhas oficiais** em `base_datas/` |
| [`dadosfnp/folheto-ifem`](https://github.com/dadosfnp/folheto-ifem) | lê as planilhas e **gera** os PDFs |

> ⚠️ Existe um repositório antigo `dadosfnp/folheto_ifem` (com **underscore**),
> parado desde janeiro/2026. Não é esse. O certo é **`folheto-ifem`**, com hífen.

> 🔒 **O Subfinanciados é somente leitura neste fluxo.** Nada é escrito lá dentro.

O fluxo inteiro:

```
base_datas/*.xlsx  ──►  planilhas_para_json.py  ──►  JSONs  ──►  gerar.py  ──►  PDF
```

---

## Parte 1 — Clonar os dois repositórios

Lado a lado, na mesma pasta pai:

```powershell
cd C:\seus\projetos

git clone git@github.com:dadosfnp/Subfinanciados.git
git clone git@github.com:dadosfnp/folheto-ifem.git "Folhetos FNP"
```

Resultado:

```
C:\seus\projetos\
├── Subfinanciados\        <- planilhas em base_datas/
└── Folhetos FNP\          <- você trabalha aqui
```

O Subfinanciados é pesado. Se quiser só as planilhas:

```powershell
git clone --depth 1 --filter=blob:none --sparse git@github.com:dadosfnp/Subfinanciados.git
cd Subfinanciados
git sparse-checkout set base_datas
```

---

## Parte 2 — Preparar o gerador

```powershell
cd "C:\seus\projetos\Folhetos FNP"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2.1 Fontes oficiais

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
  + Inter-Regular.ttf (401 KB)
  + Inter-SemiBold.ttf (409 KB)
  + Inter-Bold.ttf (410 KB)

Baixados agora: 6 | No disco: 6/6
Fontes completas — os PDFs sairão com a tipografia oficial FNP.
```

**Não é opcional.** Sem as fontes o gerador não quebra: ele troca tudo por
Helvetica e o folheto sai com outra cara. Foi assim que dois PDFs diferentes já
saíram do mesmo commit.

### 2.2 Configuração

```powershell
Copy-Item .env.example .env
notepad .env
```

Ajuste `PLANILHAS_DIR` para o caminho do **seu** clone do Subfinanciados:

```ini
PLANILHAS_DIR=C:\seus\projetos\Subfinanciados\base_datas
ANO_REF=2025
```

`ANO_REF` é o ano impresso nos folhetos. Precisa existir
`receitas_correntes_<ANO_REF>.xlsx` na pasta das planilhas.

---

## Parte 3 — Gerar os dados

```powershell
python tools/planilhas_para_json.py --todos
```

Saída esperada:

```
Ano de referência: 2025

Lendo planilhas...
  pop     5,570 linhas
  rec     5,440 linhas
  rec00   5,305 linhas
  n1      5,440 linhas
  n2      5,440 linhas
  perc0   5,440 linhas
  perc1   5,440 linhas
  perc2   5,440 linhas
  rm      1,397 municípios com região metropolitana

Base consolidada: 5,570 municípios
Médias nacionais 2000->2025: receita 316.74% | população 16.04%
Calculando percentis por rubrica...
  5,440 municípios com percentis

Gerando 5,440 JSONs...

_problema.json sincronizado a partir de data/ifem/ (versionado)

_metodologia.json sincronizado a partir de data/ifem/ (versionado)

Gerando _medias_receitas.json...
  43 rubricas | 27 UFs | 8 portes | ano 2025

------------------------------------------------------------
Gerados: 5,440 | Erros: 0
```

Isso escreve em `data/ifem/dados-ifem/export_folheto/`:

```
export_folheto/
├── _medias_receitas.json                   ← médias/medianas por rubrica (calculado)
├── _metodologia.json                       ← texto da metodologia (editorial, copiado de data/ifem/)
├── _problema.json                          ← página "O Problema" (editorial, copiado de data/ifem/)
├── 1100015_alta-floresta-d-oeste-ro.json   ← 1 por município
└── … (5.440 municípios)
```

As duas linhas `sincronizado a partir de data/ifem/` só aparecem quando a cópia do
lote está diferente da versionada. Numa pasta recém-criada aparecem sempre — e
**precisam** aparecer: são elas que garantem as páginas "O Problema" e
"Metodologia". Se faltarem numa pasta nova, confira se os dois arquivos existem em
`data/ifem/`.

### Só alguns municípios

```powershell
python tools/planilhas_para_json.py --cod-ibge 3304557,2304400
python tools/planilhas_para_json.py --dry-run     # não escreve, só relata
```

---

## Parte 4 — Gerar folhetos

### Um município

```powershell
python python/gerar.py --tema ifem `
  --dados data/ifem/dados-ifem/export_folheto/3304557_rio-de-janeiro-rj.json
```

Sai em `output/FolhetoIFEM_Rio_de_Janeiro_RJ.pdf`.

### Achar o arquivo de um município

Padrão: `<codigo_ibge>_<slug>-<uf>.json`

```powershell
Get-ChildItem data/ifem/dados-ifem/export_folheto -Filter "*fortaleza*"
```

### O recorte publicado (acima de 80 mil habitantes)

```powershell
python python/gerar.py --tema ifem `
  --lote "data/ifem/dados-ifem/export_folheto/*.json" --pop-minima 80000
```

São **417 municípios**. Leva ~15 minutos.

### Outros recortes

```powershell
# Um estado
python python/gerar.py --tema ifem --lote "data/ifem/dados-ifem/export_folheto/*-ce.json"

# Todos os 5.440 (horas, vários GB)
python python/gerar.py --tema ifem --lote "data/ifem/dados-ifem/export_folheto/*.json"
```

No modo lote, um município que falhe não derruba os outros.

### ✅ Como saber que deu certo

A saída de um folheto correto é **só** isto:

```
[OK] C:\...\output\FolhetoIFEM_Rio_de_Janeiro_RJ.pdf
```

**Qualquer linha `[aviso]` significa PDF incompleto ou fora do padrão visual.**
Não distribua — resolva o aviso primeiro.

---

## Parte 5 — Virar o ano

Quando sair a base do ano seguinte:

```powershell
# 1. Confirme que a planilha nova existe
Get-ChildItem $env:PLANILHAS_DIR -Filter "receitas_correntes_*.xlsx"

# 2. Atualize ANO_REF no .env
notepad .env

# 3. Regenere os dados
python tools/planilhas_para_json.py --todos

# 4. Atualize os números da página "O Problema"
python tools/recalcular_problema.py             # mostra antes/depois
python tools/recalcular_problema.py --aplicar   # grava

# 5. Regenere os folhetos
python python/gerar.py --tema ifem `
  --lote "data/ifem/dados-ifem/export_folheto/*.json" --pop-minima 80000
```

> O passo 4 mostra quais **frases** do texto editorial citam números por extenso
> ("cerca de 40,5 milhões de pessoas"). O script atualiza os campos numéricos,
> mas **não reescreve o texto** — isso é revisão humana.

### Um detalhe que confunde

Os dados são de 2025, mas várias coisas ainda se chamam "2024":

| Onde | O que acontece |
|---|---|
| `Municipio.rc_2024` (Subfinanciados) | property de compatibilidade; devolve `rc_atual` |
| `ano_referencia=2024` nos scripts de carga | gravado fixo, com valores do ano corrente |
| `sintese_fiscal_2000_2024` (chave do JSON) | contrato interno; lido por `ifem.py` |

**Os dados estão certos; os rótulos é que são legado.** Por isso o ano impresso
vem de `ANO_REF`, nunca dessas chaves. Ver
[`data/ifem/PROVENIENCIA.md`](../data/ifem/PROVENIENCIA.md).

---

## Parte 6 — Publicar

PDFs ficam em GitHub Releases, não no repositório:

```powershell
gh release create v2 output/FolhetoIFEM_*.pdf `
  --title "Folhetos IFEM 2025" --notes "Dados de 2025, municípios acima de 80 mil."

python tools/build_site.py --release-tag v2
```

Depois commite o `docs/folhetos.json` atualizado — é ele que a landing lê.

> Nomes com acento são descartados pelo GitHub Releases. O gerador já normaliza.

---

## Problemas comuns

### `[aviso] N de 6 fontes ausentes … usando Helvetica`

Pulou a Parte 2.1. Rode `python tools/baixar_fontes.py` e refaça os PDFs.

### `Pasta de planilhas não encontrada`

`PLANILHAS_DIR` errado no `.env`. Aponte para `<Subfinanciados>/base_datas`.

### `Planilha obrigatória ausente: receitas_correntes_2025.xlsx`

O `ANO_REF` do `.env` não corresponde a nenhuma planilha. Veja quais existem:

```powershell
Get-ChildItem "<Subfinanciados>\base_datas" -Filter "receitas_correntes_*.xlsx"
```

### O folheto saiu com o ano errado

`ANO_REF` no `.env`. Confirme e regenere os JSONs **e** os PDFs — o ano é gravado
nos dois momentos.

### Os números da página "O Problema" não batem com o ano

Rode `python tools/recalcular_problema.py --aplicar` e regenere os PDFs. Se ainda
divergir, confira se `data/ifem/dados-ifem/export_folheto/_problema.json` não é
uma cópia velha: o gerador prefere a cópia local ao arquivo versionado em
`data/ifem/`.

### `[aviso] _metodologia.json não encontrado` (ou `_problema.json`)

A página correspondente sai **vazia** — no caso da metodologia, só a imagem à
direita, sem texto à esquerda. Os dois arquivos são editoriais e vivem versionados
em `data/ifem/`; o gerador cai neles quando não acha companheiro ao lado do
`--dados`. Se o aviso apareceu:

```powershell
Get-ChildItem data/ifem/_problema.json, data/ifem/_metodologia.json
```

Faltando algum, você está num commit anterior ao fix — atualize a branch. Os dois
presentes e o aviso persistindo significa que o `--dados` aponta para fora do repo.

### `FileNotFoundError: Arquivo de dados não encontrado`

Caminho do `--dados` errado. No PowerShell, use aspas em caminhos com espaço.

### O PDF saiu diferente do de outra pessoa

1. **Fontes** — `Get-ChildItem fonts/*.ttf` deve listar **6** nas duas máquinas
2. **`ANO_REF`** — precisa ser o mesmo `.env` nos dois lados
3. **Commit** — `git log -1 --oneline` deve bater
4. **Planilhas** — se um regenerou depois de uma atualização da base, divergem

---

## Referências

- [`README.md`](../README.md) — comandos do dia a dia
- [`data/ifem/PROVENIENCIA.md`](../data/ifem/PROVENIENCIA.md) — de onde vem cada número
- [`data/ifem/SCHEMA.md`](../data/ifem/SCHEMA.md) — contrato dos JSONs
- [`DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md) — paleta, tipografia e grid

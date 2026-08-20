# Schema — IFEM (Índice de Financiamento e Equidade Municipal)

Contrato entre o **sistema externo** (`export_folheto_municipios.py` no projeto
Subfinanciados) e o **gerador de folhetos**. O sistema gera 1 JSON por município
+ arquivos compartilhados (`_metodologia.json`, `_medias_receitas.json`).

> **Identidade fixa em todo folheto FNP**: capa, última página e padrão modular
> não dependem deste schema. Só o miolo é específico do IFEM.

## Localização

Os exports do Subfinanciados escrevem em `<Subfinanciados>/export_folheto/`.
Dentro deste repo, o lote fica em `data/ifem/dados-ifem/export_folheto/` —
a cópia entre os dois é feita por `python tools/sync_dados.py`
(passo a passo em [`docs/PASSO_A_PASSO.md`](../../docs/PASSO_A_PASSO.md)).

```
export_folheto/
├── _metodologia.json                       ← compartilhado (texto da metodologia)
├── _medias_receitas.json                   ← compartilhado (médias/medianas por rubrica)
├── _problema.json                          ← compartilhado (página "O Problema")
├── 1100015_alta-floresta-d-oeste-ro.json   ← 1 por município
├── 3304557_rio-de-janeiro-rj.json
└── … (5.479 municípios)
```

Nome do arquivo: `<cod_ibge>_<slug-uf>.json`.

### Origem de cada compartilhado

| Arquivo | Gerado por |
|---|---|
| `_metodologia.json` | `export_folheto_municipios.py` |
| `_medias_receitas.json` | `export_folheto_complementares.py` |
| `_problema.json` | **ninguém** — é editorial, versionado em `data/ifem/_problema.json` |

## Como gerar o folheto

Os compartilhados são carregados automaticamente: primeiro da pasta do `--dados`,
e como fallback de `data/<tema>/` (é assim que o `_problema.json` versionado
chega ao folheto mesmo num lote recém-exportado):

```powershell
# 1 município
python python/gerar.py --tema ifem `
  --dados "C:/Users/pedro.ivo/Documents/Projetos-Git/Subfinanciados/export_folheto/3304557_rio-de-janeiro-rj.json"

# Todos
python python/gerar.py --tema ifem `
  --lote "C:/Users/pedro.ivo/Documents/Projetos-Git/Subfinanciados/export_folheto/*.json"
```

PDF sai em `output/FolhetoIFEM_<Municipio>_<UF>.pdf`.

## Layout do folheto (9 páginas, estilo revista)

```
┌─────┐        ┌─────┬─────┐    ┌─────┬─────┐    ┌─────┬─────┐    ┌─────┬─────┐
│  1  │   →    │  2  │  3  │ →  │  4  │  5  │ →  │  6  │  7  │ →  │  8  │  9  │
│CAPA │        │PROB.│RESU.│    │ESTR.│DETA.│    │SÍNT.│MET. │    │QR   │ÚLT. │
└─────┘        └─────┴─────┘    └─────┴─────┘    └─────┴─────┘    └─────┴─────┘
```

Stripe lateral sempre na **borda externa** (esq nas páginas pares, dir nas ímpares).
Numeração com lettermark `ifem` em letras modulares no rodapé do stripe.

| #  | Página                | Lado  | Origem do conteúdo                                          |
|----|-----------------------|-------|-------------------------------------------------------------|
| 01 | Capa                  | dir   | `identificacao`, `percentil`                                |
| 02 | O Problema            | esq   | `_problema.json` (titulo, resumo, composição, paradoxo)     |
| 03 | Resumo do Município   | dir   | `populacao`, `receita_corrente`, `sus_dependente`, `cadunico`, `percentil`, `identificacao.porte` |
| 04 | Estrutura da Receita  | esq   | `estrutura_receita_resumo` (4 grupos)                       |
| 05 | Detalhamento + Ranking| dir   | `estrutura_receita_detalhada.nivel_2_categorias`, `receita_corrente.ranking_por_per_capita` |
| 06 | Síntese Fiscal 2000–24| esq   | `sintese_fiscal_2000_2024`, `posicao_historica`             |
| 07 | Metodologia           | dir   | `_metodologia.json` (resumo, topicos)                       |
| 08 | Conheça o IFEM (QR)   | esq   | URL pública (default `https://ifem.onrender.com`)           |
| 09 | Última (padrão FNP)   | dir   | identidade visual pura (grid modular + FNP)                 |

## JSON por município

```jsonc
{
  "identificacao": {
    "cod_ibge": "3304557",
    "municipio": "Rio De Janeiro",       // tema aplica title case BR ("Rio de Janeiro")
    "uf": "RJ",
    "regiao": "Sudeste",
    "regiao_metropolitana": "RM do Rio de Janeiro (RJ)",
    "porte": "Acima de 500 mil",         // mapeado pra chip curto ("500k+", "100k-500k", …)
    "coordenadas": { "x": -43.46, "y": -22.93 }   // não usado no folheto
  },

  "populacao": {
    "ano": 2024,
    "valor": 6729894,
    "ranking_nacional": { "posicao": 2, "total": 5570 },
    "ranking_estadual":  { "posicao": 1, "total": 92 },
    "ranking_por_porte": { "posicao": 2, "total": 48 }
  },

  "receita_corrente": {
    "ano": 2024,
    "valor_absoluto": 37227244132.72,   // R$
    "per_capita":      5531.62,         // R$/hab
    "ranking_por_per_capita": {
      "nacional": { "posicao": 4299, "total": 5479 },
      "estadual": { "posicao": 76,   "total": 91 },
      "por_porte":{ "posicao": 27,   "total": 48 }
    }
  },

  "sus_dependente": { "percentual_populacao": 54.3 },

  "cadunico": {
    "qtd_pessoas_cadastradas": 2106794,
    "ranking_nacional": { "posicao": 4947, "total": 5570 },
    "ranking_estadual": { "posicao": 89,  "total": 92 },
    "ranking_por_porte":{ "posicao": 30,  "total": 48 }
  },

  "percentil": {
    "ano": 2024,
    "percentil_label": "22º percentil",
    "percentil_numero": 22,
    "quintil": "2º quintil",
    "decil": "3º decil"
  },

  // Cada rubrica/categoria inclui `supera_pct_nacional` = percentil 0-100
  // (% de municípios com per_capita ESTRITAMENTE menor naquela rubrica).
  // Ex.: supera_pct_nacional=76 → "supera 76% dos municípios do país".
  "estrutura_receita_resumo": [
    // 4 grupos principais, ordenados por valor desc.
    { "rubrica": "Impostos, Taxas e Contribuições de Melhoria",
      "field": "imposto_taxas_contribuicoes",
      "valor_absoluto": 17876279031.64, "per_capita": 2656.25,
      "supera_pct_nacional": 98, "total_municipios_comparados": 5479 },
    { "rubrica": "Transferências Correntes",
      "field": "transferencias_correntes",
      "valor_absoluto": 13999487930.10, "per_capita": 2080.19,
      "supera_pct_nacional": 0, "total_municipios_comparados": 5479 },
    …
  ],

  "estrutura_receita_detalhada": {
    "nivel_2_categorias": [           // 12 categorias do nível 2 (ex.: Impostos, Taxas, Contribuições Sociais…)
      { "rubrica": "Impostos", "field": "imposto",
        "valor_absoluto": 17046721574.81, "per_capita": 2532.99,
        "supera_pct_nacional": 98, "total_municipios_comparados": 5479 },
      …
    ],
    "nivel_3_rubricas": [             // 21 rubricas do nível 3 (IPTU, ISS, FPM, ICMS…)
      { "rubrica": "IPTU", "field": "iptu",
        "valor_absoluto": 4946593936.34, "per_capita": 735.02,
        "supera_pct_nacional": 95, "total_municipios_comparados": 5479 },
      …
    ]
  },

  // Mapeamento pai↔filho para agrupar nivel_2 sob nivel_1, nivel_3 sob nivel_2.
  // Usado pelo folheto para construir cards aninhados estilo landing IFEM.
  "hierarquia_receitas": {
    "nivel_1": [{ "field": "imposto_taxas_contribuicoes", "label": "Impostos, Taxas e Contribuições de Melhoria" }, …],
    "nivel_2": [{ "field": "imposto", "label": "Impostos", "parent_field": "imposto_taxas_contribuicoes" }, …],
    "nivel_3": [{ "field": "iptu",    "label": "IPTU",     "parent_field": "imposto" }, …]
  },

  "sintese_fiscal_2000_2024": {
    "delta_receita_per_capita_pct":               78.4,
    "delta_populacao_pct":                         6.61,
    "media_nacional_delta_receita_per_capita_pct": 316.74,
    "media_nacional_delta_populacao_pct":           16.04,
    "observacao": "Valores financeiros corrigidos pela inflação para 2024."
  },

  "posicao_historica": {
    "ano_2000": {
      "populacao": 6312372,
      "receita_corrente_absoluta": 19572527796.55,
      "receita_per_capita":         3100.66,
      "quintil": "5º quintil", "decil": "9º decil",
      "percentil_label": "86º percentil", "percentil_numero": 86,
      "ranking_nacional": { "posicao":  765, "total": 5305 }
    },
    "ano_2024": {
      "populacao": 6729894,
      "receita_corrente_absoluta": 37227244132.72,
      "receita_per_capita":         5531.62,
      "quintil": "2º quintil", "decil": "3º decil",
      "percentil_label": "22º percentil", "percentil_numero": 22,
      "ranking_nacional": { "posicao": 4299, "total": 5479 }
    }
  }
}
```

## `_problema.json` (compartilhado)

```jsonc
{
  "titulo": "O Problema: o dinheiro na contramão",
  "resumo": "O sistema de transferência para municípios brasileiros apoia-se em regras da década de 60. …",
  "composicao_receita_municipal": {
    "transferencias_pct": 67,
    "arrecadacao_propria_pct": 33
  },
  "paradoxo_do_crescimento": [
    "O modelo atual aumenta a receita per capita onde a população estagna…",
    "Cidades com até 30 mil habitantes tiveram ganhos reais de receita acima de 30%; …"
    // tema usa apenas os 2 primeiros itens nos cards
  ]
  // Demais campos disponíveis mas não consumidos pelo folheto atual:
  // diagnostico, populacao_por_quintil_de_receita, descompasso, raiz_da_distorcao,
  // crescimento_populacional_por_porte_2000_2024_pct,
  // crescimento_receita_per_capita_vs_media_nacional_2000_2024_pct,
  // participacao_populacao_por_porte_pct
}
```

## `_metodologia.json` (compartilhado, **versionado** em `data/ifem/`)

Conteúdo editorial: nenhuma planilha o origina. Vive em
[`_metodologia.json`](_metodologia.json) e os scripts de setup copiam de lá para
o lote — igual ao `_problema.json`. A versão do repo vence a que vier de export.

```jsonc
{
  "titulo": "Indicadores de Financiamento e Equidade Municipal (IFEM)",
  "resumo": "Para comparar contextos tão distintos, o IFEM utiliza um método simples e justo…",
  "topicos": [
    { "pergunta": "Qual a base de dados utilizada?", "resposta": "…" },
    { "pergunta": "Por que 'per capita'?",            "resposta": "…" },
    { "pergunta": "Como os grupos são divididos?",    "resposta": "…" }
  ],
  "passos": [
    // Presente por fidelidade ao contrato do export oficial, mas NÃO consumido
    // pelo folheto: a página 13 desenha esse passo a passo com metodologia.png.
    { "ordem": 1, "titulo": "Ordenamos todos os municípios", "descricao": "…" },
    { "ordem": 2, "titulo": "Distribuímos em grupos iguais", "descricao": "…",
      "grupos": { "quintis": [/* 5 */], "decis": [/* 10 */] } }
  ]
}
```

> O texto que vem do export oficial (`export_folheto_municipios.py`, dict
> `METODOLOGIA`) é **sem acentuação** — literal ASCII no fonte. A versão
> versionada aqui corrige isso; palavra por palavra é o mesmo texto.

## Notas de implementação

- **Title case BR**: tema aplica em `identificacao.municipio` ("Rio De Janeiro" → "Rio de Janeiro").
- **Porte chip**: `_PORTE_CURTO` em `temas/ifem.py` mapeia strings longas pra chips curtos. Fallback usa primeira palavra.
- **Seed do padrão decorativo**: `cod_ibge % 100_000`. Mesmo município = mesmo desenho.
- **URL do QR**: se o JSON do município trouxer `url`, prevalece. Senão usa `https://ifem.onrender.com`.
- **Vírgula decimal**: formato BR (`78,4%`) em texto narrativo. Tabelas seguem o que vier da fonte.
- **Lettermark "ifem"**: desenhado em letras modulares (do alfabeto FNP) no rodapé do stripe de toda página interna (2-8). Capa e última usam só número.

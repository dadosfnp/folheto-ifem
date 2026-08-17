# Proveniência dos dados — IFEM

De onde vem cada número impresso nos folhetos. Documento de rastreabilidade:
se alguém perguntar "de onde saiu esse valor?", a resposta está aqui.

## Fonte primária

Todos os números vêm das planilhas oficiais em:

```
<Subfinanciados>/base_datas/*.xlsx
```

O caminho da sua máquina fica em `PLANILHAS_DIR`, no `.env` (veja `.env.example`).

**É a mesma base que alimenta o banco do IFEM em produção.** O site
(ifem.onrender.com) e os folhetos saem da mesma origem — os scripts de carga do
Subfinanciados leem essas planilhas e populam o PostgreSQL; o gerador de folhetos
lê as planilhas diretamente. Não há uma segunda fonte de verdade.

## Ano de referência

**2025**, definido em `ANO_REF` no `.env`.

Entrou no Subfinanciados pelo commit `bf68b6a` (04/08/2026), PR #85
`atualizacao-ifem-2025`, que substituiu `receitas_correntes_2024.xlsx` por
`receitas_correntes_2025.xlsx` e atualizou as demais planilhas.

> ⚠️ **Atenção ao ler o código do Subfinanciados.** Os nomes ficaram no ano
> antigo: `Municipio.rc_2024` é uma *property de compatibilidade* que devolve
> `rc_atual`, e os scripts de carga gravam `ano_referencia=2024` mesmo com
> valores de 2025. Os dados estão certos; os rótulos é que são legado. Por isso
> o ano impresso no folheto vem de `ANO_REF`, nunca de um literal no código.

## Planilha por seção do folheto

| Planilha | Alimenta |
|---|---|
| `receitas_correntes_2025.xlsx` | receita corrente, per capita, quintil, decil, percentil, rankings (nacional/UF/porte) |
| `receitas_correntes_2000.xlsx` | série histórica de 2000 (síntese fiscal, posição histórica) |
| `populacao.xlsx` | identificação, população 2025 e 2000, porte, região, coordenadas, CadÚnico, dependência do SUS |
| `receitas_correntes_detalhamento*.xlsx` | estrutura de receita (níveis 1, 2 e 3) |
| `percentil_detalhamento_*.xlsx` | `supera_pct_nacional` por rubrica |
| `media_*.xlsx` / `mediana_*.xlsx` | médias e medianas nacional / por UF / por porte |
| `percentis_limites.xlsx` | cortes de percentil |
| `crescimento_medio_*.xlsx` | crescimento médio de população e receita por UF e porte |

## Cobertura

| Planilha | Linhas |
|---|---|
| `receitas_correntes_2025.xlsx` | 5.440 municípios |
| `populacao.xlsx` | 5.570 municípios |

A diferença (130) são municípios sem dado de receita declarado. O gerador trata
ausência de dado explicitamente — não preenche com zero.

## Recorte publicado

Os folhetos publicados cobrem **612 municípios**, listados em
[`docs/folhetos.json`](../../docs/folhetos.json). O recorte é o mesmo desde o
release `v1`; o que muda entre releases é o ano dos dados.

## Conteúdo editorial

[`_problema.json`](_problema.json) é texto redacional, **não** sai de planilha
nenhuma. Os números citados nele (população por quintil, % de transferências)
vêm de análise agregada e precisam ser revisados a cada mudança de ano de
referência — não são atualizados por nenhum script.

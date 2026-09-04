# Fallback 2024 — dado dos municípios que não declararam em 2025

Estes JSONs estão **versionados de propósito**, ao contrário do resto de
`data/ifem/dados-ifem/` (que é ignorado por volume e regenerável).

## Por que estão aqui

`tools/planilhas_para_json.py` descarta quem não tem receita no `ANO_REF` — em
2025 foram 130 municípios, 7 deles acima de 80 mil habitantes. Para esses, o
folheto sai com o dado do ano anterior mais uma tarja de ressalva
(`tools/gerar_sem_declaracao.py`).

O problema: **o dado de 2024 não é regenerável.** Em `base_datas/` existem
`receitas_correntes_2000.xlsx` e `receitas_correntes_2025.xlsx` — não há
planilha de 2024, e as de detalhamento e percentil não têm recorte por ano.
Rodar o gerador com `ANO_REF=2024` morre em "Planilha obrigatória ausente".

Antes disso o único lugar com esse dado era `data/ifem/dados-ifem/_backup_2024/`,
que o `.gitignore` exclui. Quem clonava o repo não conseguia gerar esses 7
folhetos e não recebia erro nenhum: o município simplesmente não aparecia no
lote. Vale a regra que já está em `tasks/lessons.md` — **se um script não
consegue regenerar o arquivo, ele tem que estar versionado.**

## O que tem aqui

| Arquivo | O que é |
|---|---|
| `<cod_ibge>_<slug>-<uf>.json` | dado cru de 2024 dos 7 municípios do recorte publicado |
| `_medias_receitas.json` | médias de **2024** — as de 2025 comparariam o município contra o ano errado |
| `_problema.json` | números da página "O Problema" em 2024 |

O dado é **cru**: sem `aviso_dados` e sem `risco_climatico`. Os dois são
injetados na hora — a ressalva pelo `gerar_sem_declaracao.py` (o texto cita o
`ANO_REF` corrente, então versioná-lo pronto o deixaria errado na virada do ano)
e o risco pelo `adapta_para_json.py --injetar`.

`_metodologia.json` não está aqui porque é byte-idêntico ao versionado em
`data/ifem/`, que o `gerar.py` já usa como fallback.

## Para cobrir mais municípios

O recorte publicado hoje é > 80 mil habitantes. Se ele descer, basta copiar os
JSONs correspondentes de um lote de 2024 para cá — o script varre a pasta, não
tem lista de códigos no código:

```powershell
Copy-Item data/ifem/dados-ifem/_backup_2024/<cod_ibge>_*.json data/ifem/fallback_2024/
```

Dos 130 municípios sem declaração em 2025, 101 têm dado de 2024 disponível. Os
outros 29 não têm em ano nenhum e ficam de fora por falta de dado — o
`gerar_sem_declaracao.py` os lista nominalmente em vez de omiti-los.

## Na virada do ano

Com `ANO_REF=2026`, o script passa a procurar `data/ifem/fallback_2025/`. O lote
de 2025 é regenerável pelas planilhas enquanto `receitas_correntes_2025.xlsx`
existir em `base_datas/` — se ela sair, os municípios que dependerem dela viram
o mesmo caso e precisam ser versionados aqui do mesmo jeito.

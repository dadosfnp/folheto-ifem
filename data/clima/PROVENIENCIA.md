# Proveniência dos dados — Risco Climático (AdaptaBrasil)

De onde vem cada número das páginas de Risco Climático. Mesmo contrato de
rastreabilidade de [`data/ifem/PROVENIENCIA.md`](../ifem/PROVENIENCIA.md).

## Fonte primária

```
<Subfinanciados>/base_datas/indicadores_adapta_brasil.xlsx
```

O caminho da sua máquina fica em `PLANILHAS_DIR`, no `.env`.

É a mesma planilha que o comando `home/management/commands/10_adapta_brasil.py`
carrega na tabela `AdaptaBrasil` do banco do IFEM em produção. O gerador de
folhetos lê a planilha direto — não há segunda fonte de verdade, e nenhum passo
precisa de banco ou de rede.

Os nomes de município, UF e região vêm de `populacao.xlsx`, casados por
`cod_ibge`. A planilha do AdaptaBrasil só traz o código.

## Cobertura

| | |
|---|---|
| Municípios na planilha | 5.570 |
| Com quintil do IFEM | 5.440 |
| Sem quintil do IFEM | 130 |

Os 130 sem quintil ficam **fora do gráfico** da página de panorama (não há
coluna onde empilhá-los) mas **dentro** de todos os outros números — média
nacional, distribuição por classe, rankings. O total excluído é impresso na
legenda do gráfico, e sai no JSON em `municipios_sem_quintil_ifem`.

## Os 12 indicadores

Cada coluna da planilha é a abreviação do próprio setor estratégico e subsetor.
O mapa está em `tools/adapta_para_json.py::INDICADORES`:

| Coluna | Setor estratégico | Subsetor |
|---|---|---|
| `bio_int_bio` | Biodiversidade | Integridade da biodiversidade |
| `des_des_ter` | Desastres geo-hidrológicos | Deslizamentos de terra |
| `des_in_enx_ala` | Desastres geo-hidrológicos | Inundações, enxurradas e alagamentos |
| `rec_ris_est_hid` | Recursos hídricos | Risco de estresse hídrico |
| `sau_arb` | Saúde | Arboviroses |
| `sau_lei_teg_ame` | Saúde | Leishmaniose tegumentar americana |
| `sau_lei_vis` | Saúde | Leishmaniose visceral |
| `sau_mal` | Saúde | Malária |
| `seg_ali_ace_con_ali` | Segurança alimentar | Acesso e consumo de alimentos |
| `seg_ali_dis` | Segurança alimentar | Disponibilidade de alimentos |
| `seg_ene_ace` | Segurança energética | Acesso à energia |
| `seg_ene_dis` | Segurança energética | Disponibilidade de energia |

A **média geral** impressa em destaque é a coluna `pontuacao_risco_norm_pond` —
a média ponderada já calculada na planilha, gravada como `media_ponderada` no
banco. **Não** é a média aritmética dos 12 indicadores: a aritmética dá 0,42 de
média nacional, a ponderada dá 0,56. Recalcular no folheto produziria um número
diferente do que o painel publica.

## As cinco classes de risco

A planilha traz o índice contínuo de 0 a 1, sem a classe. O corte é em faixas de
0,2:

| Classe | Faixa | Municípios |
|---|---|---|
| Muito alto | 0,8 – 1,0 | 380 |
| Alto | 0,6 – 0,8 | 1.949 |
| Médio | 0,4 – 0,6 | 2.192 |
| Baixo | 0,2 – 0,4 | 1.013 |
| Muito baixo | 0,0 – 0,2 | 36 |

**Como o corte foi confirmado:** reclassificando a planilha com essas faixas e
cruzando com a coluna `quintil` chega-se célula a célula à mesma tabela que o
painel do IFEM publica — 1º quintil com 207 / 593 / 258 / 30 / 0, 5º quintil com
10 / 118 / 417 / 514 / 29, todos os quintis com exatamente 1.088 municípios. É
essa tabela que a página de panorama desenha.

## Escala invertida em relação ao IFEM

No IFEM, valor alto = município **bem** financiado, e a paleta vai de vermelho
(pior) a verde (melhor) conforme o valor **sobe**. Aqui é o contrário: o índice
mede exposição, então valor alto = **pior**, e a paleta é aplicada ao contrário.

Duas consequências que o código respeita e nenhum leitor deve descobrir sozinho:

- `ranking_nacional.posicao == 1` significa **maior risco do país** — o oposto da
  convenção do IFEM. Por isso a ressalva "1º = município mais exposto do recorte"
  é impressa junto dos rankings.
- `supera_pct_nacional` lê-se "tem risco maior que X% dos municípios", e não
  "supera X%" como nos cards de receita.

## Regeneração

```powershell
python tools/adapta_para_json.py                 # só o recorte de docs/folhetos.json
python tools/adapta_para_json.py --todos         # os 5.570 municípios
python tools/adapta_para_json.py --cod-ibge 3304557,2303709
```

Saída: `data/clima/_panorama_nacional.json` (versionado) e
`data/clima/<cod>_<slug>.json` (ignorado pelo git, como o lote do IFEM).

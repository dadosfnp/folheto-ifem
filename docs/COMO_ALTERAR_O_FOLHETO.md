# Como alterar o folheto

Guia para mudar o que sai impresso: textos, cores, tamanhos, tabelas, páginas
inteiras. Assume que você já consegue gerar um folheto — se ainda não, comece
pelo [PASSO_A_PASSO.md](PASSO_A_PASSO.md).

> **A regra que vale para tudo aqui:** altere → gere **um** município → abra o
> PDF → só então rode o lote. O ciclo de um município leva 3 segundos; o do lote,
> 15 minutos. Nunca descubra um erro depois de 424 PDFs.

---

## O ciclo de trabalho

```powershell
# 1. Altere o código (veja o mapa abaixo)

# 2. Gere UM município e abra
python python/gerar.py --tema ifem `
  --dados data/ifem/dados-ifem/export_folheto/3304557_rio-de-janeiro-rj.json
Invoke-Item output/FolhetoIFEM_Rio_de_Janeiro_RJ.pdf

# 3. Gostou? Teste em casos extremos ANTES do lote (veja "Municípios de teste")

# 4. Valide e rode o lote
python tools/verificar_arte.py output/
python python/gerar.py --tema ifem `
  --lote "data/ifem/dados-ifem/export_folheto/*.json" --pop-minima 80000
```

### Municípios de teste

Um município "normal" esconde a maioria dos bugs de layout. Estes quatro cobrem
os extremos que já quebraram o folheto antes:

| Município | JSON | Por que testar |
|---|---|---|
| São Paulo/SP | `3550308_sao-paulo-sp.json` | números maiores (R$ bilhões, 8 dígitos) |
| Rio de Janeiro/RJ | `3304557_rio-de-janeiro-rj.json` | caso de referência, muitas rubricas |
| Balneário Camboriú/SC | `4202008_balneario-camboriu-sc.json` | nome longo, estoura título |
| Almirante Tamandaré/PR | `data/ifem/fallback_2024/4100400_...` | tarja de ressalva em todas as páginas |

Para o último, use o `gerar_sem_declaracao.py` — ele precisa rodar com o ano do
dado, não com o corrente.

---

## Mapa: onde fica cada página

Tudo do IFEM está em [`python/temas/ifem.py`](../python/temas/ifem.py). A ordem
das páginas é montada em `construir_paginas()`.

| Página | Método | O que tem |
|---|---|---|
| 1 | `_pag_capa` | capa: mapa, nome do município, marca |
| 2 | `_pag_problema` | "O Problema" — texto editorial + números |
| 3 | `_pag_sintese` | Síntese Fiscal 2000→hoje |
| 4 | `_pag_variacoes` | gráficos de receita e população |
| 5 | `_pag_resumo` | KPIs e rankings do município |
| 6 | `_pag_estrutura` | pizza: composição da receita em % |
| 7 | `_pag_receita_n12` | tabela de rubricas, níveis 1 e 2 |
| 8+ | `_pag_receita_n3` | tabela nível 3 (1 ou 2 páginas, conforme o município) |
| — | `_pag_metodologia` | metodologia (peça móvel: acerta a paridade) |
| — | `_pag_risco_panorama` | Risco Climático: panorama nacional |
| — | `_pag_risco_municipio` | Risco Climático: as 12 notas do município |
| −3 | `_pag_mapa_brasil` | mapa IFEM do país |
| −2 | `_pag_convite` | QR code |
| −1 | `_pag_ultima` | verso padrão FNP |

> **Por que a metodologia se move:** o spread de Risco Climático só se lê aberto
> se começar em página par. A metodologia é a única peça que pode trocar de lugar
> sem prejuízo, então é ela quem acerta a paridade. Não tente resolver isso
> encolhendo conteúdo.

---

## Mudar texto

### Texto que vem de arquivo (preferir sempre)

Dois textos são **editoriais** e vivem em JSON versionado — mudar ali não exige
tocar em código:

| Arquivo | O que controla |
|---|---|
| [`data/ifem/_problema.json`](../data/ifem/_problema.json) | toda a página "O Problema" |
| [`data/ifem/_metodologia.json`](../data/ifem/_metodologia.json) | a página de metodologia |

Depois de editar, sincronize para o lote:

```powershell
python tools/planilhas_para_json.py --todos     # copia a versão do repo por cima
```

> A cópia do repo **vence** a que estiver no lote. Se você editar direto em
> `data/ifem/dados-ifem/export_folheto/_problema.json`, o próximo
> `planilhas_para_json.py` apaga sua alteração.

Se o texto cita valores por extenso ("R$ 2,1 bilhões"), rode também:

```powershell
python tools/recalcular_problema.py             # mostra o que ficou inconsistente
python tools/recalcular_problema.py --aplicar   # atualiza os números
```

Ele atualiza **números**, não reescreve frases — o texto corrido continua sendo
revisão humana.

### Texto que está no código

Títulos de seção, rótulos de coluna e frases fixas estão em `ifem.py`, dentro do
método da página. Procure pelo texto:

```powershell
Select-String -Path python/temas/ifem.py -Pattern "As 12 notas"
```

```python
# ifem.py, dentro de _pag_risco_municipio
draw_eyebrow(c, "As 12 notas do município", x, y)
```

> ⚠️ **Travessão (—) é proibido em qualquer texto impresso.** Vale para copy
> nova, texto dos JSONs e placeholder de valor ausente (use `n/d`, nunca um traço
> solto: num KPI o leitor confunde com sinal de menos). Onde a frase pedia
> travessão, use vírgula, dois-pontos ou ponto final. Para separar rótulos
> curtos, o separador da casa é o ponto médio (`·`).

---

## Mudar cor, fonte ou tamanho

**Nunca escreva uma cor ou um tamanho direto no `ifem.py`.** Tudo vem de
[`python/core/tokens.py`](../python/core/tokens.py) — mudar lá muda em todos os
folhetos de uma vez, que é o ponto.

```python
# tokens.py
BLUE_DARK   = colors.HexColor("#122747")   # títulos, texto de ênfase
BLUE        = colors.HexColor("#1B3A6B")   # cor institucional (stripe, headers)
YELLOW      = colors.HexColor("#FFC72C")   # acento
CREAM       = colors.HexColor("#F4EFE6")   # fundo de card
MUTED       = colors.HexColor("#6B6B6B")   # texto secundário

FS_TITLE_SECAO = 30    # título de página de conteúdo
FS_BODY        = 12    # texto corrido
FS_EYEBROW     = 10.5  # chapéu acima do título

FONT_NUM_BOLD  = "BarlowCondensed-Bold"    # números grandes, caixa alta
FONT_TEXTO     = "Inter-Regular"           # texto corrido
```

Duas famílias, e cada uma tem papel: **Barlow Condensed** para números e rótulos
curtos em caixa alta, **Inter** para texto corrido. Não introduza uma terceira.

### As paletas não são intercambiáveis

`FNP_Q1..Q5` (vermelho → verde) significam *bom ou ruim* e só podem ser usadas
onde existe ordem — quintil de receita, classe de risco. Um gráfico que apenas
separa grupos (a pizza da estrutura de receita) usa a família azul mais um
amarelo de acento.

Já aconteceu de verde significar "Transferências" numa página e "supera muitos
municípios" duas páginas depois, no mesmo folheto. É o tipo de erro que ninguém
percebe revisando página por página.

> **A escala do risco é invertida.** No IFEM, valor alto = município bem
> financiado. No AdaptaBrasil, valor alto = mais exposto, e `posicao == 1` é o
> **pior**. As páginas de risco têm o próprio mapa de cores (`_cor_risco`) por
> isso — não reaproveite o do IFEM.

---

## Mexer numa tabela

As três tabelas do folheto (receita níveis 1-2, nível 3, e as 12 notas de risco)
compartilham as **mesmas larguras de coluna** — é o que faz as páginas lerem como
um sistema só. As constantes ficam juntas no topo da seção de tabelas do
`ifem.py`:

```python
COL_ROTULO   # largura da coluna do nome da rubrica
COL_MUNI     # coluna do município (barra + valor)
COL_CAIXA    # cada uma das duas caixas de média (UF e Brasil)
CAIXA_W      # largura da caixinha dentro da coluna
HEAD_H       # altura do cabeçalho azul
```

Mudou uma? Confira as **três** tabelas, não só a que você estava olhando.

Cada linha é desenhada por um método `_linha_*` (`_linha_risco`, por exemplo).
A altura da linha é a variável `row_h` no topo do método.

> **Regras que não são negociáveis** (estão no
> [DESIGN_SYSTEM.md §5.7](../DESIGN_SYSTEM.md)): o percentil fica colado à
> esquerda da barra e na cor dela; barra de valor zero recebe traço mínimo de
> 2,5pt (largura zero o leitor lê como dado faltando); a unidade é decidida por
> linha, nunca por célula; estado antes do Brasil.

---

## Adicionar ou remover uma página

Em `construir_paginas()`:

```python
antes = [
    self._pag_capa,
    self._pag_problema,
    self._pag_minha_pagina_nova,   # ← entra aqui
    ...
]
```

E o método, seguindo o esqueleto de qualquer página interna:

```python
def _pag_minha_pagina_nova(self, c, n):
    lado = self._moldura_pagina(c, n, f"{self.nome} · {self.uf}")  # fundo, stripe, header, footer
    x = self._content_x(lado)                    # X do conteúdo, já desviando do stripe
    y = self._cabecalho(c, x, "Título da Seção") # título grande + nome do município

    c.setFillColor(INK)
    c.setFont(F(FONT_TEXTO), FS_BODY)
    c.drawString(x, y, "Seu conteúdo aqui.")
```

Três coisas que o esqueleto resolve e você não deve refazer à mão: o stripe
alterna de lado conforme a página é par ou ímpar, o número da página e a tarja de
ressalva (quando o município não declarou no ano).

### O espaço vertical tem limites

```python
SAFE_TOP    = 512   # abaixo do header
SAFE_BOTTOM = 56    # acima do footer
```

Tudo tem que caber entre os dois. Se sobrar espaço no rodapé, chame a decoração —
**passando onde o conteúdo terminou**, que ela mede sozinha se cabe:

```python
self._decorar_rodape(c, lado, y)   # y = onde seu conteúdo parou
```

Não faça a conta de "cabe?" no seu código. Foi exatamente isso — cada página com
a própria conta — que cobriu a última linha das tabelas em 424 folhetos.

---

## Antes de rodar o lote: o checklist

```powershell
# 1. Gerou e conferiu pelo menos 2 municípios de teste?

# 2. Nenhuma arte cobrindo conteúdo
python tools/verificar_arte.py output/

# 3. Nenhum travessão no texto impresso
python tools/verificar_texto.py output/

# 4. Contagem de páginas plausível (14 ou 15; 12 = risco climático não entrou)
python -c "import fitz,glob; p=glob.glob('output/*.pdf')[0]; print(len(fitz.open(p)),'paginas')"
```

O checklist completo de exportação está no fim do
[DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md).

---

## Coisas que quebram em silêncio

Nenhuma delas derruba o gerador. O PDF sai, abre normalmente, e está errado.

| Sintoma | Causa | Conserto |
|---|---|---|
| Tipografia diferente da oficial | `fonts/*.ttf` ausentes | `python tools/baixar_fontes.py` |
| Folheto com 12 páginas | bloco `risco_climatico` ausente | `python tools/adapta_para_json.py --injetar --todos` |
| Página "O Problema" ou "Metodologia" vazia | companheiro editorial ausente no lote | `python tools/planilhas_para_json.py --todos` |
| Município não aparece no lote | não declarou receita no ano | `python tools/gerar_sem_declaracao.py` |
| Última linha da tabela sumiu | arte do rodapé por cima | `python tools/verificar_arte.py output/` |

Se aparecer `[aviso]` em qualquer script, o PDF **não** está fiel ao oficial —
leia o aviso antes de seguir.

---

## Onde não mexer sem pensar duas vezes

- **`python/core/`** — é compartilhado por todos os temas (IFEM, COSIP e os
  próximos). Mudança ali muda folheto que você não está olhando.
- **As chaves dos JSONs** (`sintese_fiscal_2000_2024`, `posicao_historica.ano_2024`)
  mantêm o sufixo `_2024` mesmo com dados mais novos. É contrato herdado do
  Subfinanciados; renomear quebra o gerador sem ganho nenhum. **O ano impresso
  não vem daí** — vem de `ANO_REF` no `.env`.
- **`docs/folhetos.json`** — é gerado por `tools/build_site.py`. Editar à mão é
  perder a alteração na próxima publicação.

---

## Registrando o que você aprendeu

Se algo te pegou de surpresa, escreva em [`../tasks/lessons.md`](../tasks/lessons.md):
o que aconteceu, por que passou, e a regra para não repetir. Metade das
armadilhas listadas neste guia está lá porque alguém tropeçou nelas primeiro.

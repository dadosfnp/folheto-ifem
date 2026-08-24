# Design System — Folhetos FNP

Sistema visual unificado para todos os folhetos da Frente Nacional de Prefeitas e Prefeitos.
Cada folheto novo (COSIP, IFEM, e os próximos) reusa esta linguagem — **só dados e textos mudam**.

> Referências visuais canônicas: pasta [`inspiration/`](inspiration/).
> Folheto modelo: **COSIP — "O Futuro da COSIP: Transformar, Monitorar e Conectar"** (16 páginas).

---

## 1. Princípio fundador: sistema modular

Toda a identidade nasce de **um vocabulário gráfico mínimo** aplicado em cima de uma grade de quadrados de mesma dimensão. Existem apenas 4 operações dentro de cada módulo:

| Operação              | Aparência                              | Uso                              |
|-----------------------|----------------------------------------|----------------------------------|
| Quadrado vazio        | linha externa apenas                   | respiro, ritmo                   |
| Quadrado preenchido   | bloco sólido de cor                    | ênfase, peso visual              |
| ¼ de círculo          | quarto de disco em qualquer canto      | direção, dinamismo               |
| ½ círculo             | semicírculo em qualquer aresta         | suavidade, pontuação             |

Combinando essas 4 formas a FNP construiu:
- O **padrão geométrico de fundo** (capa COSIP, contracapa, página 16).
- O **alfabeto modular** (referências em `inspiration/`) — usado como tratamento de letreiro especial em capas e divisórias quando o título pede destaque pictórico.

**Regra de ouro:** se uma decoração nova precisar ser criada, ela deve sair desse vocabulário. Não introduzir formas estranhas (triângulos, hexágonos, ondas) sem aprovação.

---

## 2. Paleta de cores

| Token         | Hex        | Uso primário                                        |
|---------------|------------|-----------------------------------------------------|
| `BLUE_DARK`   | `#122747`  | Títulos, texto de ênfase, faixas escuras            |
| `BLUE`        | `#1B3A6B`  | Cor institucional FNP — fundos, bordas, headers     |
| `BLUE_MID`    | `#3D6FA8`  | Gráficos secundários, hover, variação de azul       |
| `YELLOW`      | `#FFC72C`  | Acento, headlines de seção, aspas, gráficos         |
| `YELLOW_DARK` | `#C99A1F`  | Ranking (números grandes), variação de amarelo      |
| `GREEN`       | `#2A8F5C`  | Pontos fortes, contornos do alfabeto modular        |
| `RED_BURNT`   | `#C04A1A`  | Pontos de atenção (uso pontual)                     |
| `CREAM`       | `#F4EFE6`  | Fundo de cards, fundo neutro quente                 |
| `PAPER`       | `#FBF8F2`  | Fundo de páginas internas                           |
| `RULE`        | `#D9D2C3`  | Linhas divisórias, bordas sutis                     |
| `MUTED`       | `#6B6B6B`  | Texto secundário, fonte/captions                    |
| `INK`         | `#1A1A1A`  | Texto corrido                                       |

**Combinações canônicas:**
- Capa: foto + faixa `BLUE` inferior + título `BLUE_DARK` ou branco sobre azul.
- Conteúdo: fundo `PAPER` + cards brancos + bordas `RULE` + headings `BLUE_DARK`.
- Divisória de seção: fundo `BLUE` cheio + capítulo em `YELLOW` + título branco.

---

## 3. Tipografia

| Função              | Fonte                          | Peso        | Tamanho típico |
|---------------------|--------------------------------|-------------|----------------|
| Título de capa      | Barlow Condensed Bold          | 700         | 38–54pt        |
| Headline de seção   | Barlow Condensed Bold          | 700         | 24–32pt (caixa alta) |
| Eyebrow / capítulo  | Barlow Condensed SemiBold      | 600         | 8pt CAIXA ALTA |
| Subtítulo / KPI     | Barlow Condensed Bold          | 700         | 18–22pt        |
| Texto corrido       | Inter Regular                  | 400         | 8.5–9pt        |
| Citação / destaque  | Inter SemiBold ou Barlow Bold  | 600/700     | 11–17pt        |
| Caption / fonte     | Inter Regular                  | 400         | 6.5–7pt        |

**Headlines amarelos:** o COSIP usa muito tratamento de título amarelo (`YELLOW`) com leve **outline branco/escuro** sobre fundos claros. É marca registrada do folheto — manter.

**Paleta categórica ≠ paleta ordinal.** A paleta de quintis
(`FNP_Q1`…`FNP_Q5`) significa *bom ou ruim* e só pode ser usada onde existe
ordem. Gráfico que apenas separa grupos (a pizza da estrutura de receita, por
exemplo) usa a família azul + um amarelo de acento. Já houve o caso de verde
significar "Transferências" numa página e "supera muitos municípios" duas
páginas depois, no mesmo folheto.

**Travessão (—) é proibido em qualquer texto impresso.** Vale para copy nova,
texto editorial dos JSONs companheiros e placeholder de valor ausente (use `n/d`,
nunca um traço solto: num KPI o leitor confunde com sinal de menos). Onde a frase
pedia um travessão, use vírgula, dois-pontos ou ponto final. Para separar rótulos
curtos, o separador da casa é o ponto médio (`·`), como no cabeçalho e no rodapé.

**Fallback automático:** Helvetica Bold / Helvetica (caso Barlow/Inter não estejam instalados — já implementado em `ifem_folheto.py`).

---

## 4. Formato e grid

- **Página:** 20 cm × 20 cm (quadrado).
- **Stripe lateral:** 20pt de azul (`BLUE`) numa das laterais — alterna esquerda/direita por página, com numeração branca centralizada no rodapé do stripe (`01`, `02`...).
- **Margem útil:** 36pt (≈ 1,3 cm) no lado oposto ao stripe e nas margens superior/inferior.
- **Largura de conteúdo:** 20cm − stripe − 2×margem ≈ 16,7 cm.
- **Cabeçalho:** texto pequeno em `MUTED`, 7pt, caixa alta — ex.: `"COSIP · O FUTURO NO RIO DE JANEIRO/RJ"`.
- **Rodapé:** label da seção à esquerda + mini-logo FNP à direita.

---

## 5. Componentes recorrentes

### 5.1 Capa
- Foto/ilustração preenchendo a grade modular (módulos viram máscaras da imagem).
- Faixa azul inferior cobrindo ~25% da altura, com título em branco condensado bold.
- Logo FNP centralizado abaixo do título.
- Sub-bloco com nome do município/tema em `MUTED` claro.

### 5.2 Divisória de seção
- Fundo `BLUE` cheio.
- Decoração de quartos de círculo brancos com transparência (~8%).
- Eyebrow `"CAPÍTULO XX"` em `YELLOW` 8pt caixa alta.
- Título grande (54pt) em branco, 1–2 linhas.
- Subtítulo em `#AABBCC` (azul claro) descrevendo a seção.

### 5.3 Página de conteúdo
- Fundo `PAPER`.
- Eyebrow + título 26pt no topo.
- Corpo de texto Inter Regular 9pt.
- Cards brancos com 4pt de borda colorida no topo OU borda esquerda azul.
- Sempre rodapé com fonte/elaboração: `"Fonte: STN/Siconfi. Elaboração: FNP."` em `MUTED` 6.5pt.

### 5.4 Card de KPI
```
┌─┬──────────────────┐
│ │ LABEL EM CAIXA   │
│ │                  │
│ │ 38,2 bi          │  ← número grande Barlow Bold
│ │                  │
└─┴──────────────────┘
 ↑
 BLUE_MID 4pt borda esquerda
```

### 5.5 Citação destaque
Box `BLUE` arredondado, aspas grandes `YELLOW` (estilo COSIP páginas 2, 6).

### 5.6 Tabela
- Header `BLUE` + texto branco.
- Linhas alternadas: `WHITE` / `#F0EBE2` (creme escuro).
- Linha divisória `RULE` no fim de cada linha.
- Coluna do município/tema-foco em `BLUE_DARK` SemiBold; demais em `MUTED` Regular.

### 5.7 Tabela de rubrica (IFEM)

Uma linha por rubrica, para receita e para risco climático. As três tabelas do
folheto compartilham as MESMAS larguras de coluna — é o que faz as páginas
lerem como um sistema só, e não como três tabelas parecidas.

| Coluna | Conteúdo |
|---|---|
| Rótulo | rubrica (ou setor + subsetor no risco) |
| `SUPERA` | percentil escrito **e** a barra, ambos na cor do quintil |
| Município | o valor, na mesma cor |
| `MÉDIA` | duas caixas iguais: estado e Brasil, nessa ordem |

**Regras que não são negociáveis:**

- O percentil fica **colado à esquerda da barra e na cor dela**. Número e
  desenho são a mesma medida; separados, viram dois dados disputando atenção.
- Barra de valor zero recebe traço mínimo de 2,5pt. Zero é um valor medido;
  largura zero o leitor lê como dado faltando.
- A unidade é decidida **por linha**, nunca por célula: com `R$ 1,9 mil` ao lado
  de `R$ 769` o leitor compara 1,9 com 769 e conclui o oposto do que o dado diz.
- Estado antes do Brasil. O prefeito se compara primeiro com os vizinhos.
- O que sobra de página abaixo da tabela recebe o alfabeto modular
  (`_decorar_rodape`), nunca branco solto.

### 5.8 Bullets / lista
- Quadrado `BLUE` 8×8pt OU `■` glyph como bullet.
- NUNCA bullets redondos genéricos.

### 5.9 QR code (última página)
- 140×140pt centralizado, cor de preenchimento `#0E2447`, fundo branco, borda 2.
- Embaixo: URL em `YELLOW` Inter SemiBold (`Acesse https://...`).

---

## 6. Estrutura canônica do folheto

Modelo derivado do COSIP (16 pp.) e adaptado para IFEM (9 pp.). Usar como ponto de partida — pode haver variação por tema.

| Pág. | Função                              | Stripe | Tipo                          |
|------|-------------------------------------|--------|-------------------------------|
| 01   | Capa                                | dir    | Foto + título + logo FNP      |
| 02   | Apresentação do tema / "O problema" | dir    | Citação destaque + 4 cards    |
| 03   | Divisória de seção                  | esq    | Capítulo grande               |
| 04   | Dados / KPIs / Rankings             | dir    | Grid 3×2 + rankings           |
| 05   | Estrutura / breakdown               | esq    | Stacked bar + cards           |
| 06   | Detalhamento (tabela)               | dir    | Tabela + mini-bar comparativo |
| 07   | Síntese / diagnóstico               | esq    | Destaque + 2 colunas          |
| 08   | Metodologia                         | dir    | 5 passos numerados            |
| 09   | Encerramento + QR                   | esq    | Grade modular + QR + logos    |

> **Regra de stripe:** alternar lados a cada página (espelho) — capa e contracapa em lados opostos; no miolo seguir a alternância par/ímpar.

---

## 7. Alfabeto modular — quando usar

Existem duas variantes (ver [`inspiration/`](inspiration/)):

1. **Versão preenchida com foto** (`alfabeto-modular-foto.png`): letra-janela. Recomendado para **capas com palavras curtas** (1–4 letras) onde a tipografia em si vira ilustração.
2. **Versão em contorno colorido** (`alfabeto-modular-contorno.png`): linhas finas em `BLUE` / `GREEN` / `YELLOW`. Recomendado para **divisórias de seção** ou abertura de capítulos onde uma palavra-símbolo (ex.: `IFEM`, `RJ`, `SP`) precisa de presença sem peso visual excessivo.

**Não usar como fonte de corpo de texto.** É vocabulário ilustrado, sempre construído como artwork (vetor) — não é fonte tipográfica instalável.

---

## 8. Como gerar um folheto novo

1. **Definir o tema** (ex.: educação, segurança, mobilidade) e adaptar o título-modelo de capa.
2. **Reusar o gerador Python** (`python/ifem_folheto.py` ou similar) — só trocar:
   - função `buscar_dados_municipio()` apontando pra a base do tema novo
   - estrutura de páginas se o tema pedir mais ou menos seções
   - texto dos eyebrows e títulos
3. **Manter inalteráveis:**
   - Paleta (tokens do `DESIGN_SYSTEM.md`)
   - Grid e dimensões da página (20×20cm, stripe 20pt, margens 36pt)
   - Tipografia (Barlow Condensed + Inter)
   - Componentes (KPI box, ranking item, citação, tabela)
4. **Validar contra o COSIP** antes de fechar: abrir lado a lado e checar consistência (cores, alinhamentos, hierarquia tipográfica).

---

## 9. Checklist antes de exportar PDF

- [ ] Nenhum travessão (—) no texto do PDF (`page.get_text()` de todas as páginas).
- [ ] Stripes alternam corretamente entre páginas pares e ímpares.
- [ ] Numeração de página em branco aparece em todas as páginas (exceto se o tema pedir capa "limpa").
- [ ] Toda página interna tem cabeçalho (`IFEM · …` ou `COSIP · …`) e rodapé (label + logo FNP).
- [ ] Toda fonte de dado aparece como caption em `MUTED` 6.5pt no fim do gráfico.
- [ ] Título da capa não excede 3 linhas em 38pt.
- [ ] QR code da última página aponta para URL real e está testado.
- [ ] PDF salvo em `output/` com nome `<TEMA>_<Municipio>_<UF>.pdf`.

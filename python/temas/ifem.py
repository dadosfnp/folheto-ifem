"""
Tema IFEM — Índice de Financiamento e Equidade Municipal.

Consome o schema exportado pelo sistema externo (Subfinanciados/export_folheto_municipios.py):
ver `data/ifem/SCHEMA.md` para o contrato. Companheiros `_metodologia.json` e
`_problema.json` são injetados pelo gerar.py em `self.d["_metodologia"]` e
`self.d["_problema"]`.

Layout estilo revista: pág 1 capa (direita sozinha) + 4 spreads (2-3, 4-5, 6-7, 8-9).
Stripe lateral sempre na borda externa do spread.
"""
import json
import sys
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit, ImageReader

from core.base_folheto import FolhetoFNP
from core.tokens import (
    PAPER, BLUE, BLUE_DARK, BLUE_MID, BLUE_LIGHT, YELLOW, YELLOW_DARK,
    CREAM, CREAM_DARK, RULE, MUTED, INK, WHITE, GREEN, RED_BURNT,
    STRIPE_W, MARGIN, CONTENT_W, ASSETS_DIR, ROOT_DIR, CARD_RADIUS,
    FS_EYEBROW, FS_TITLE_SECAO, FS_BODY, FS_BODY_SMALL,
    QR_SIZE, QR_FILL_COLOR,
    FNP_Q1, FNP_Q2, FNP_Q3, FNP_Q4, FNP_Q5, FNP_QUINTIS,
    FONT_NUM_BOLD, FONT_NUM_SEMIBOLD, FONT_NUM_REGULAR,
    FONT_TEXTO, FONT_TEXTO_SEMIBOLD, FONT_TEXTO_BOLD,
    ANO_REF, ANO_BASE, PERIODO, PERIODO_HIFEN,
)
from core.fonts import F
from core.components import (
    draw_stripe, draw_page_number, draw_header, draw_footer,
    draw_eyebrow, draw_titulo, draw_body, draw_caption,
    draw_kpi_box, draw_ranking_item, draw_destaque_box, draw_card_topbar,
    draw_table, draw_stacked_bar, draw_section_divider,
    draw_categoria_card, draw_categoria_bloco, cor_status_landing,
    draw_icon_populacao, draw_icon_receita, draw_icon_sus,
    draw_icon_cadunico, draw_icon_grafico,
)
from core.capa import draw_capa_padrao
from core.ultima import draw_ultima_padrao
from core.paleta_ranking import cor_por_percentil, cor_por_quintil
from core.padrao import draw_alfabeto_decoracao
from core.asset_cache import cached_image


# ─── SAFE ZONE: limites verticais do conteúdo de qualquer página ────────────
# Header (label do tema) ocupa Y 530-560; footer (label do município) ocupa
# Y 18-44. Reservamos uma SAFE BOTTOM acima do footer para evitar sobreposição
# com a faixa do número de página e a decoração. Tudo no miolo deve ficar
# entre SAFE_TOP e SAFE_BOTTOM.
SAFE_TOP    = 512   # = H - 55 (Y inicial após header)
SAFE_BOTTOM = 56    # margem mínima acima do footer label
SAFE_HEIGHT = SAFE_TOP - SAFE_BOTTOM


# ─── Risco Climático (AdaptaBrasil/MCTI) ─────────────────────────────────────
# Dados: bloco `risco_climatico` no JSON do município + agregados nacionais em
# `data/clima/_panorama_nacional.json`. Ambos saem de tools/adapta_para_json.py;
# a rastreabilidade completa está em data/clima/PROVENIENCIA.md.
#
# ATENÇÃO À ESCALA: aqui é o inverso do resto do folheto. No IFEM, valor alto =
# município bem financiado (verde). No AdaptaBrasil, o índice mede EXPOSIÇÃO —
# valor alto = pior. Por isso estas páginas têm o próprio mapa de cores e NÃO
# usam `cor_por_percentil`: reaproveitar aquele helper pintaria de verde
# justamente o município que corre mais risco.

# Do pior para o melhor — ordem da legenda do painel oficial e ordem de
# empilhamento das barras (pior embaixo).
CLASSES_RISCO = ("Muito alto", "Alto", "Médio", "Baixo", "Muito baixo")

COR_CLASSE_RISCO = {
    "Muito alto":  FNP_Q1,   # vermelho
    "Alto":        FNP_Q2,   # laranja
    "Médio":       FNP_Q3,   # amarelo
    "Baixo":       FNP_Q4,   # verde claro
    "Muito baixo": FNP_Q5,   # verde
}

PANORAMA_CLIMA_JSON = ROOT_DIR / "data" / "clima" / "_panorama_nacional.json"


def _cor_risco(classe: str | None):
    return COR_CLASSE_RISCO.get(classe or "", MUTED)


def _nota_risco(v) -> str:
    """0.7766 -> '0,78'. Duas casas: é a precisão que o painel publica."""
    return "n/d" if v is None else f"{v:.2f}".replace(".", ",")

# ─── Tabelas de rubrica (receita e risco) ────────────────────────────────────
# Uma linha por rubrica, barra do municipio + as medias do estado e do pais.
# As tres tabelas do folheto usam as MESMAS larguras de coluna de proposito:
# e o que faz as paginas lerem como um sistema so, e nao como tres tabelas.

HEAD_H = 19                 # cabecalho em duas linhas: escopo + unidade
CAIXA_W = 46                # caixa de media (R$ nao cabe num quadrado)
PCT_W, GAP_BARRA, VAL_W = 26, 6, 56   # slots dentro da coluna do municipio
BANDA_H = 56                # faixa de destaque no topo das paginas de tabela

COL_ROTULO = 168
COL_CAIXA = 50
COL_MUNI = CONTENT_W - COL_ROTULO - COL_CAIXA * 2


def _cor_supera(pct):
    """Paleta de quintis aplicada ao percentil de uma rubrica.

    Supera POUCOS municipios = vermelho (mal financiado); supera muitos = verde.
    E o oposto de `_cor_risco`, onde valor alto e ruim — por isso os dois mapas
    sao funcoes separadas e nunca se cruzam.
    """
    if pct is None:
        return MUTED
    for limite, cor in zip((20, 40, 60, 80), FNP_QUINTIS):
        if pct <= limite:
            return cor
    return FNP_QUINTIS[4]


def _reais(v, em_mil=False, cifrao=True):
    """R$/hab das tabelas.

    A unidade e decidida por LINHA, nunca por celula: com "1,9 mil" ao lado de
    "769" o leitor compara 1,9 com 769 e conclui o oposto do que o dado diz.
    """
    if v is None:
        return "n/d"
    if em_mil:
        txt = f"{v/1000:.1f}".replace(".", ",") + " mil"
    elif v >= 10:
        txt = _fmt_int(v)
    else:
        txt = f"{v:.1f}".replace(".", ",")
    return f"R$ {txt}" if cifrao else txt


# ─── Helpers ─────────────────────────────────────────────────────────────────

_TC_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o"}

# Mapeamento sigla → nome completo da UF (usado no rótulo do quadro com a
# silhueta do estado na página do mapa IFEM).
_UF_NOMES = {
    "AC": "Acre",            "AL": "Alagoas",      "AP": "Amapá",
    "AM": "Amazonas",        "BA": "Bahia",        "CE": "Ceará",
    "DF": "Distrito Federal","ES": "Espírito Santo","GO": "Goiás",
    "MA": "Maranhão",        "MT": "Mato Grosso",  "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",    "PA": "Pará",         "PB": "Paraíba",
    "PR": "Paraná",          "PE": "Pernambuco",   "PI": "Piauí",
    "RJ": "Rio de Janeiro",  "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul","RO": "Rondônia",    "RR": "Roraima",
    "SC": "Santa Catarina",  "SP": "São Paulo",    "SE": "Sergipe",
    "TO": "Tocantins",
}


def _title_case_br(s: str) -> str:
    """Title case respeitando convenção brasileira."""
    palavras = s.split()
    out = []
    for i, w in enumerate(palavras):
        wl = w.lower()
        out.append(wl if i > 0 and wl in _TC_MINUSCULAS else wl.capitalize())
    return " ".join(out)


_PORTE_CURTO = {
    "Acima de 500 mil":   "500k+",
    "100 a 500 mil":      "100k-500k",
    "50 a 100 mil":       "50k-100k",
    "20 a 50 mil":        "20k-50k",
    "10 a 20 mil":        "10k-20k",
    "5 a 10 mil":         "5k-10k",
    "Até 5 mil":          "≤5k",
    "Até 20 mil":         "≤20k",
}

def _porte_curto(p: str) -> str:
    return _PORTE_CURTO.get(p, p.split()[0])


def _fmt_int(v):
    return f"{int(round(v)):,}".replace(",", ".")

def _fmt_money_bi(v):
    return f"R$ {v/1e9:.1f} bi"

def _fmt_money(v):
    return f"R$ {int(round(v)):,}".replace(",", ".")

def _br(v, d=1):
    """Formata float com vírgula decimal BR."""
    return f"{v:.{d}f}".replace(".", ",")


def _fmt_total_unidade(v):
    """Formata um valor monetário escolhendo a unidade legível:
        ≥ 1 bi  → 'X,Y'  unidade='bi'
        ≥ 1 mi  → 'X,Y'  unidade='mi'
        ≥ 1 mil → 'X,Y'  unidade='mil'
        senão   → '1.234' unidade=''
    Devolve (valor_str, unidade)."""
    if v is None:
        return ("n/d", "")
    if v >= 1e9:
        return (f"R$ {v/1e9:.1f}".replace(".", ","), "bi")
    if v >= 1e6:
        return (f"R$ {v/1e6:.1f}".replace(".", ","), "mi")
    if v >= 1e3:
        return (f"R$ {v/1e3:.1f}".replace(".", ","), "mil")
    return (f"R$ {int(round(v)):,}".replace(",", "."), "")


def _fmt_pop(v):
    """Formata população em unidade legível:
        ≥ 1 mi  → '6,7 mi'
        ≥ 1 mil → '254,3 mil'
        senão   → '824'
    Devolve (valor_str, unidade)."""
    if v is None:
        return ("n/d", "hab.")
    if v >= 1e6:
        return (f"{v/1e6:.1f}".replace(".", ","), "mi hab.")
    if v >= 1e3:
        return (f"{v/1e3:.0f}".replace(".", ","), "mil hab.")
    return (_fmt_int(v), "hab.")


def _so_numero(rotulo: str) -> str:
    """De '2º quintil' / '3º decil' extrai apenas '2' / '3'."""
    if not rotulo:
        return "n/d"
    return rotulo.split("º")[0].strip()


def cor_verbo_gap(fator: float):
    """Cor da frase do gap: verde se o município cresceu mais, vermelho se menos.
    Aplicada na frase '(Município cresceu Xx menos que a média)'."""
    from core.tokens import FNP_Q1, FNP_Q5
    return FNP_Q1 if abs(fator) > 1 else FNP_Q5


# ─── Tema ────────────────────────────────────────────────────────────────────

class FolhetoIFEM(FolhetoFNP):
    titulo_publicacao = "IFEM · INDICADORES DE FINANCIAMENTO E EQUIDADE MUNICIPAL"

    def __init__(self, dados: dict, output_path=None):
        super().__init__(dados, output_path)
        self._panorama_clima = None   # lazy: ver property panorama_clima

    # Atalhos
    @property
    def ident(self):  return self.d["identificacao"]
    @property
    def nome(self):   return _title_case_br(self.ident["municipio"])
    @property
    def uf(self):     return self.ident["uf"]

    def _output_name(self):
        return self.nome, self.uf

    @property
    def risco_climatico(self) -> dict:
        """Bloco AdaptaBrasil do município. Vazio quando o JSON não foi
        enriquecido — nesse caso as duas páginas de risco saem da publicação
        inteira (ver construir_paginas), em vez de imprimirem quadros vazios."""
        return self.d.get("risco_climatico") or {}

    @property
    def panorama_clima(self) -> dict:
        """Agregados nacionais do AdaptaBrasil, carregados uma vez por folheto.

        Vive fora do payload do município porque é o MESMO conteúdo para os
        5.570 — replicá-lo em cada JSON do lote custaria ~18 MB para nada.
        """
        if self._panorama_clima is None:
            if PANORAMA_CLIMA_JSON.exists():
                with PANORAMA_CLIMA_JSON.open(encoding="utf-8") as f:
                    self._panorama_clima = json.load(f)
            else:
                print(f"[aviso] {PANORAMA_CLIMA_JSON.name} não encontrado; a página de "
                      f"panorama do risco climático sairá vazia. "
                      f"        Rode: python tools/adapta_para_json.py --injetar",
                      file=sys.stderr)
                self._panorama_clima = {}
        return self._panorama_clima

    def _seed(self):
        return int(self.ident["cod_ibge"]) % 100_000

    def _lado_pagina(self, n: int) -> str:
        """Stripe no lado EXTERNO do spread.
        Convenção revista: pág 1 (capa) à direita; depois pares à esquerda, ímpares à direita."""
        if n == 1:
            return "dir"
        return "esq" if n % 2 == 0 else "dir"

    def _moldura_pagina(self, c, n: int, footer_label: str | None = None):
        """Aplica fundo, stripe (lado externo), header, footer e numeração.
        O stripe usa o azul FNP padrão (cor institucional do folheto)."""
        c.setFillColor(WHITE)
        c.rect(0, 0, self.W, self.H, fill=1, stroke=0)
        lado = self._lado_pagina(n)
        draw_stripe(c, self.W, self.H, lado, cor=BLUE)
        draw_page_number(c, self.W, n - 1, lado, lettermark="IFEM")
        draw_header(c, self.H, self.titulo_publicacao)
        draw_footer(c, self.W, footer_label or f"{self.nome} · {self.uf}")
        self._draw_aviso_dados(c, lado)
        return lado

    def _draw_aviso_dados(self, c, lado: str):
        """
        Tarja de ressalva quando o folheto não usa a base do ano corrente.

        Aparece em TODAS as páginas internas de propósito: o folheto circula
        impresso e em recortes, e uma ressalva só na capa se perde. Ocupa a
        faixa entre o footer (y=16) e o SAFE_BOTTOM (y=56), que é livre.

        O texto vem do JSON (`aviso_dados`), não do código — quem monta o lote
        decide o que ressalvar.
        """
        aviso = self.d.get("aviso_dados")
        if not aviso:
            return
        x = (STRIPE_W + MARGIN) if lado == "esq" else MARGIN
        c.setFillColor(RED_BURNT)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 6.2)
        c.drawString(x, 34, str(aviso).upper())

    def _content_x(self, lado: str) -> float:
        """X inicial do conteúdo, evitando o stripe."""
        return (STRIPE_W + MARGIN) if lado == "esq" else MARGIN

    def _draw_cabecalho(self, c, x: float, y: float, secao: str,
                         capitulo: str | None = None) -> float:
        """Cabeçalho padrão das páginas internas (em duas linhas):
              <Seção em fonte menor, azul, peso semibold>
              Rio de Janeiro - RJ              ← título grande
        O nome do capítulo é deliberadamente suprimido (sugestão do usuário:
        só nome da seção). `capitulo` permanece como parâmetro só para não
        quebrar chamadas antigas.
        """
        # Linha 1: nome da seção (pequeno, azul)
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 13)
        c.drawString(x, y, secao)

        # Linha 2: nome do município em destaque
        y -= 32
        nome_uf = f"{self.nome} - {self.uf}"
        nome_fs = FS_TITLE_SECAO
        while c.stringWidth(nome_uf, F(FONT_NUM_BOLD), nome_fs) > CONTENT_W - 12 and nome_fs > 18:
            nome_fs -= 1
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_NUM_BOLD), nome_fs)
        c.drawString(x, y, nome_uf)
        return y - 26

    # Artes decorativas do rodapé, da mais alta para a mais fina. O ratio vem
    # das dimensões reais do PNG (assets/padroes) — não estimar.
    ARTES_RODAPE = (
        ("arte2", 592 / 216),   # faixa alta
        ("arte1", 591 / 108),   # faixa fina
        ("arte0", 437 / 39),    # ultra-fina
    )
    # Abaixo disso a arte vira um carimbo perdido no meio da página: melhor
    # descer para a próxima mais fina ou não desenhar nada.
    LARGURA_MIN_ARTE = 0.6

    def _decorar_rodape(self, c, lado: str, y_max: float, seed_offset: int = 0,
                        forcar_fina: bool = False, arte: str | None = None):
        """Preenche o espaço vazio do rodapé com um dos padrões decorativos.

        `y_max` é o Y do último traço de conteúdo da página: a arte é sempre
        desenhada ABAIXO dele, e é este método — não o chamador — quem garante
        isso. Uma arte que não cabe no espaço livre é substituída pela próxima
        mais fina; se nenhuma couber, a página fica sem decoração.

        `arte` fixa a preferência ('arte0' | 'arte1' | 'arte2') e `forcar_fina`
        começa a busca na arte1. Em ambos os casos a preferência é o teto, não
        uma garantia: a busca só desce a lista, nunca sobe para uma arte mais
        alta do que a pedida.
        """
        FOOTER_Y = 36
        # A tarja de ressalva (`aviso_dados`) mora na faixa do footer; quando
        # existe, a arte precisa começar acima dela.
        base_y = 46 if self.d.get("aviso_dados") else FOOTER_Y + 4
        h_disp = y_max - base_y
        if h_disp < 20:
            return

        x0 = STRIPE_W + MARGIN if lado == "esq" else MARGIN
        w_disp = CONTENT_W
        padroes_dir = ASSETS_DIR / "padroes"

        preferida = arte or ("arte1" if forcar_fina else "arte2")
        inicio = next((i for i, (nome, _) in enumerate(self.ARTES_RODAPE)
                       if nome == preferida), 0)

        for nome, ratio in self.ARTES_RODAPE[inicio:]:
            img_path = padroes_dir / f"{nome}.png"
            if not img_path.exists():
                continue
            h_cheia = w_disp / ratio
            if h_cheia <= h_disp:
                # Cabe inteira: largura total do conteúdo, que é o encaixe
                # mais elegante e o que já está impresso hoje.
                w_fit, h_fit = w_disp, h_cheia
            else:
                # Não cabe: encolhe preservando o ratio, mas só até o limite em
                # que ainda lê como faixa. Abaixo disso, tenta a próxima.
                h_fit = h_disp
                w_fit = h_fit * ratio
                if w_fit < w_disp * self.LARGURA_MIN_ARTE:
                    continue
            img_x = x0 + (w_disp - w_fit) / 2
            c.drawImage(cached_image(img_path), img_x, base_y,
                        width=w_fit, height=h_fit,
                        preserveAspectRatio=True, mask="auto")
            return

    def construir_paginas(self):
        """Ordem narrativa: O PROBLEMA, a trajetória do município, e só então o
        detalhamento da receita — agora em tabela, não mais em cards."""
        antes = [
            self._pag_capa,             # 1
            self._pag_problema,         # 2
            self._pag_sintese,          # 3  Síntese Fiscal 2000–2024
            self._pag_variacoes,        # 4  gráficos receita + população
            self._pag_resumo,           # 5
            self._pag_estrutura,        # 6  pizza: composição em %, outra pergunta
            self._pag_receita_n12,      # 7  tabela: níveis 1 e 2
        ]
        # O nível 3 ocupa quantas páginas precisar. Dos 424 do recorte, 355
        # cabem em uma e 62 pedem duas — medido, não estimado.
        for i, blocos in enumerate(self._paginas_n3()):
            antes.append(lambda c, n, b=blocos, pr=(i == 0):
                         self._pag_receita_n3(c, n, b, pr))

        # O spread de risco só se lê aberto se começar em página PAR. A
        # metodologia é a única peça móvel do miolo, então é ela quem acerta a
        # paridade — e não o conteúdo, que não pode encolher para caber.
        #
        # Sem o bloco `risco_climatico` no JSON a seção some inteira, em vez de
        # imprimir quadros vazios. É o caso de todo lote gerado antes de
        # `tools/adapta_para_json.py --injetar`.
        if not self.risco_climatico:
            miolo = antes + [self._pag_metodologia]
        elif (len(antes) + 1) % 2 == 0:
            miolo = antes + [self._pag_risco_panorama, self._pag_risco_municipio,
                             self._pag_metodologia]
        else:
            miolo = antes + [self._pag_metodologia,
                             self._pag_risco_panorama, self._pag_risco_municipio]

        return miolo + [
            self._pag_mapa_brasil,      # mapa IFEM dos 5.479 municípios
            self._pag_convite,          # QR code
            self._pag_ultima,           # verso do folheto — padrão FNP
        ]

    # ─── 1. Capa ────────────────────────────────────────────────────────────

    def _pag_capa(self, c, n):
        d = self.d
        pop_rk = d["populacao"]["ranking_nacional"]
        rec_rk = d["receita_corrente"]["ranking_por_per_capita"]["nacional"]
        # Versão "_clean" é o PNG com o texto baked-in mascarado (mantém só
        # mapa + logo FNP). Gerado em data/ifem/ via tools/regerar_capa.py.
        mapa_clean = ASSETS_DIR.parent / "data" / "ifem" / "indicadores_fnp_mapa_vivo_clean.png"
        mapa = mapa_clean if mapa_clean.exists() else \
               ASSETS_DIR.parent / "data" / "ifem" / "indicadores_fnp_mapa_vivo.png"
        draw_capa_padrao(
            c, self.W, self.H, n,
            tema_label=self.titulo_publicacao,
            municipio_nome=self.nome,
            uf=self.uf,
            ranking_pop=(pop_rk["posicao"],     pop_rk["total"]),
            ranking_rec_pc=(rec_rk["posicao"],  rec_rk["total"]),
            mapa_path=mapa,
            seed=self._seed(),
        )

    # ─── 2. Problema (dados de _problema.json) ──────────────────────────────

    def _pag_problema(self, c, n):
        prob = self.d.get("_problema") or {}
        lado = self._moldura_pagina(c, n, "O Problema")
        x = self._content_x(lado)
        y = SAFE_TOP

        # Título grande "O dinheiro na contramão da população."
        # com "contramão" destacado em amarelo dourado.
        title_fs = 28
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_NUM_BOLD), title_fs)
        c.drawString(x, y, "O dinheiro na")
        w1 = c.stringWidth("O dinheiro na ", F(FONT_NUM_BOLD), title_fs)
        c.setFillColor(YELLOW_DARK)
        c.drawString(x + w1, y, "contramão")
        c.setFillColor(BLUE_DARK)
        y -= title_fs + 6
        c.drawString(x, y, "da população.")
        # Mais respiro entre o título principal e o parágrafo descritivo
        # (pedido: a página tava muito comprimida no topo).
        y -= 40

        # Frase narrativa (fonte 12pt, line-height generoso → 2-3 linhas)
        resumo = prob.get("resumo") or (
            "O sistema de transferência para municípios brasileiros apoia-se "
            "em regras da década de 60. O Brasil mudou, o contexto das cidades "
            "mudou, mas as regras de financiamento não acompanharam essas mudanças."
        )
        y = draw_body(c, resumo, x, y, CONTENT_W, size=12) - 22

        # Card "O DESCOMPASSO" — maior, com fonte legível
        descompasso = prob.get("descompasso", "")
        if descompasso:
            from reportlab.lib.utils import simpleSplit as _sp
            font = F(FONT_TEXTO)
            fs = 10
            inner_w = CONTENT_W - 32
            linhas = _sp(descompasso, font, fs, inner_w)
            line_h = fs * 1.50
            card_h = 38 + len(linhas) * line_h
            cy = y - card_h
            c.setFillColor(BLUE_DARK)
            c.roundRect(x, cy, CONTENT_W, card_h, 6, fill=1, stroke=0)
            # Filete amarelo lateral à esquerda — destaca o card
            c.setFillColor(YELLOW)
            c.rect(x, cy, 4, card_h, fill=1, stroke=0)
            # Eyebrow amarelo grande
            c.setFillColor(YELLOW)
            c.setFont(F(FONT_NUM_BOLD), 12)
            c.drawString(x + 16, cy + card_h - 18, "O DESCOMPASSO")
            # Texto branco
            c.setFillColor(WHITE)
            c.setFont(font, fs)
            for i, linha in enumerate(linhas):
                c.drawString(x + 16, cy + card_h - 36 - i * line_h, linha)
            y = cy - 22

        # Gráfico cruzado (X invertido) ajusta altura ao espaço restante.
        pop_q = prob.get("populacao_por_quintil_de_receita") or {}
        menor = pop_q.get("menor_renda_1q")
        maior = pop_q.get("maior_renda_5q")
        if menor and maior:
            # Espaço para o gráfico + legenda quintil (h≈32) + folga acima do
            # footer. Reserva mínima: 32 (legenda) + 32 (folga) = 64.
            graf_h = max(150, y - SAFE_BOTTOM - 64)
            graf_h = min(graf_h, 190)
            self._draw_grafico_cruzado(c, x, y, CONTENT_W, graf_h, menor, maior)
            y -= graf_h + 8

            # Legenda combinada embaixo
            legenda = (
                "1º Quintil = 20% dos municípios com a menor receita corrente por "
                "habitante.   5º Quintil = 20% com a maior."
            )
            self._draw_legenda_quintil_combinada(c, x, y, CONTENT_W, legenda)
            y -= 26

        # Decoração no rodapé com arte1. Quem mede o espaço é o
        # `_decorar_rodape`: aqui só informamos onde o conteúdo terminou.
        self._decorar_rodape(c, lado, y, seed_offset=1, forcar_fina=True)

    def _draw_grafico_cruzado(self, c, x, y_top, w, h, menor, maior):
        """Gráfico 'X invertido' (tese do IFEM): 2 linhas cruzando entre 2000
        e 2024. Linha vermelha sobe (mais população em municípios pobres),
        linha verde cai (menos em municípios ricos)."""
        y_bot = y_top - h

        # Card branco com borda
        c.setFillColor(WHITE)
        c.roundRect(x, y_bot, w, h, 6, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.roundRect(x, y_bot, w, h, 6, fill=0, stroke=1)

        # Título (eyebrow + subtítulo) ocupando largura toda — legenda no rodapé
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 9)
        c.drawString(x + 14, y_top - 16, "POPULAÇÃO POR QUINTIL DE RECEITA")
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_NUM_BOLD), 13)
        c.drawString(x + 14, y_top - 32, "O dinheiro foi na direção oposta da população")

        # Área de plot (deixa espaço inferior para legenda)
        plot_x = x + 56
        plot_y = y_bot + 50
        plot_w = w - 72
        plot_h = h - 96

        # Y representa milhões de pessoas
        max_val = max(menor["ano_2000_milhoes"], menor["ano_2024_milhoes"],
                       maior["ano_2000_milhoes"], maior["ano_2024_milhoes"])
        max_val = (int(max_val // 20) + 1) * 20

        # Grid horizontal sutil + labels Y
        c.setStrokeColor(colors.HexColor("#EEEAE0"))
        c.setLineWidth(0.4)
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 7.5)
        for i in range(5):
            yy = plot_y + (i / 4) * plot_h
            c.line(plot_x, yy, plot_x + plot_w, yy)
            label = f"{int(i / 4 * max_val)}"
            c.drawRightString(plot_x - 6, yy - 2, label)
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 7)
        c.drawString(plot_x - 18, plot_y + plot_h + 8, "mi hab.")

        x_2000 = plot_x + plot_w * 0.10
        x_2024 = plot_x + plot_w * 0.90

        def _yp(v):
            return plot_y + (v / max_val) * plot_h

        y1a, y1b = _yp(menor["ano_2000_milhoes"]), _yp(menor["ano_2024_milhoes"])
        y5a, y5b = _yp(maior["ano_2000_milhoes"]), _yp(maior["ano_2024_milhoes"])

        # Linha 1º quintil (vermelha — sobe)
        c.setStrokeColor(FNP_Q1)
        c.setLineWidth(2.6)
        c.line(x_2000, y1a, x_2024, y1b)
        c.setFillColor(FNP_Q1)
        c.circle(x_2000, y1a, 4.5, fill=1, stroke=0)
        c.circle(x_2024, y1b, 4.5, fill=1, stroke=0)

        # Linha 5º quintil (verde — cai)
        c.setStrokeColor(FNP_Q5)
        c.setLineWidth(2.6)
        c.line(x_2000, y5a, x_2024, y5b)
        c.setFillColor(FNP_Q5)
        c.circle(x_2000, y5a, 4.5, fill=1, stroke=0)
        c.circle(x_2024, y5b, 4.5, fill=1, stroke=0)

        # Rótulos dos pontos — em 2000, alterna acima/abaixo se Y próximos
        def _label_pt(px, py, txt, cor, lado, dy=0):
            c.setFillColor(cor)
            c.setFont(F(FONT_NUM_BOLD), 10)
            if lado == "esq":
                c.drawRightString(px - 8, py - 3 + dy, txt)
            else:
                c.drawString(px + 8, py - 3 + dy, txt)

        # Se em 2000 os 2 valores são próximos (≤ 8mi diferença), separa labels verticalmente
        proximos_2000 = abs(menor["ano_2000_milhoes"] - maior["ano_2000_milhoes"]) < 8
        dy_v, dy_g = (-8, 8) if proximos_2000 and menor["ano_2000_milhoes"] < maior["ano_2000_milhoes"] else (
                      (8, -8) if proximos_2000 else (0, 0))

        _label_pt(x_2000, y1a, f"{_br(menor['ano_2000_milhoes'])} mi", FNP_Q1, "esq", dy_v)
        _label_pt(x_2024, y1b, f"{_br(menor['ano_2024_milhoes'])} mi", FNP_Q1, "dir")
        _label_pt(x_2000, y5a, f"{_br(maior['ano_2000_milhoes'])} mi", FNP_Q5, "esq", dy_g)
        _label_pt(x_2024, y5b, f"{_br(maior['ano_2024_milhoes'])} mi", FNP_Q5, "dir")

        # Labels do eixo X
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 9)
        c.drawCentredString(x_2000, plot_y - 12, "2000")
        c.drawCentredString(x_2024, plot_y - 12, str(ANO_REF))

        # Legenda na parte inferior do card (não no topo, evita sobrepor título)
        leg_y = y_bot + 14
        leg_text_1 = "Pop. em municípios de menor renda (1º quintil)"
        leg_text_2 = "Pop. em municípios de maior renda (5º quintil)"
        c.setFont(F(FONT_TEXTO), 8.5)
        w_1 = c.stringWidth(leg_text_1, F(FONT_TEXTO), 8.5)
        w_2 = c.stringWidth(leg_text_2, F(FONT_TEXTO), 8.5)
        gap_mid = 30
        total = 14 + w_1 + 26 + w_2
        start = x + (w - total) / 2
        # Marcador 1
        c.setFillColor(FNP_Q1)
        c.rect(start, leg_y, 12, 3, fill=1, stroke=0)
        c.circle(start + 6, leg_y + 1.5, 3, fill=1, stroke=0)
        c.setFillColor(INK)
        c.drawString(start + 16, leg_y - 1, leg_text_1)
        # Marcador 2
        x2 = start + 16 + w_1 + 14
        c.setFillColor(FNP_Q5)
        c.rect(x2, leg_y, 12, 3, fill=1, stroke=0)
        c.circle(x2 + 6, leg_y + 1.5, 3, fill=1, stroke=0)
        c.setFillColor(INK)
        c.drawString(x2 + 16, leg_y - 1, leg_text_2)

    def _draw_legenda_quintil_combinada(self, c, x, y, w, texto):
        from reportlab.lib.utils import simpleSplit as _sp
        font = F(FONT_TEXTO)
        fs = 8.5
        inner_w = w - 16
        linhas = _sp(texto, font, fs, inner_w)
        h = 12 + len(linhas) * fs * 1.30
        cy = y - h
        c.setFillColor(CREAM)
        c.roundRect(x, cy, w, h, 3, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(font, fs)
        for i, linha in enumerate(linhas):
            c.drawString(x + 10, cy + h - 11 - i * (fs * 1.30), linha)

    def _draw_legenda_quintil(self, c, x, y, w, cor, texto):
        """Card pequeno com filete colorido + texto curto explicativo do quintil."""
        from reportlab.lib.utils import simpleSplit as _sp
        font = F(FONT_TEXTO)
        fs = 8
        inner_w = w - 16
        linhas = _sp(texto, font, fs, inner_w)
        h = 14 + len(linhas) * fs * 1.30
        cy = y - h
        c.setFillColor(CREAM)
        c.roundRect(x, cy, w, h, 3, fill=1, stroke=0)
        c.setFillColor(cor)
        c.rect(x, cy, 3, h, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(font, fs)
        for i, linha in enumerate(linhas):
            c.drawString(x + 10, cy + h - 11 - i * (fs * 1.30), linha)

    def _draw_grafico_pop(self, c, dados: dict, label_curto: str,
                          x: float, y: float, w: float, cor_bar):
        """Renderiza um mini-bloco "População vivendo em municípios de X renda"
        com barra 2000 (cinza) + barra 2024 (colorida) + pílula de variação."""
        h = 100
        cy = y - h
        c.setFillColor(WHITE)
        c.roundRect(x, cy, w, h, 4, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.roundRect(x, cy, w, h, 4, fill=0, stroke=1)

        v2000 = dados["ano_2000_milhoes"]
        v2024 = dados["ano_2024_milhoes"]
        var   = dados["variacao_pct"]
        maximo = max(v2000, v2024) or 1

        # Título do bloco
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_NUM_BOLD), 10)
        c.drawString(x + 10, cy + h - 16, "População em municípios")
        c.drawString(x + 10, cy + h - 28, f"de {label_curto}")

        # Pílula de variação (canto superior direito, fora do espaço das barras)
        sinal = "▲" if var >= 0 else "▼"
        var_str = f"{sinal} {_br(abs(var), 2)}%"
        pill_w = 56
        pill_h = 14
        px = x + w - pill_w - 8
        py = cy + h - 20
        c.setFillColor(cor_bar)
        c.roundRect(px, py, pill_w, pill_h, 7, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 7.5)
        c.drawCentredString(px + pill_w/2, py + 4, var_str)

        # Área das barras: deixar espaço pro valor à direita
        bar_x = x + 38
        bar_w_max = w - 60 - 38
        bar_h = 7

        # 2000 (cinza claro)
        b1_y = cy + 36
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 6.5)
        c.drawString(x + 10, b1_y + 1, "2000")
        c.setFillColor(colors.HexColor("#E0DACE"))
        bw1 = bar_w_max * (v2000 / maximo)
        c.rect(bar_x, b1_y, bw1, bar_h, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(F(FONT_NUM_BOLD), 10)
        c.drawRightString(x + w - 10, b1_y, f"{_br(v2000)} mi")

        # 2024 (colorida)
        b2_y = cy + 14
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 6.5)
        c.drawString(x + 10, b2_y + 1, str(ANO_REF))
        c.setFillColor(cor_bar)
        bw2 = bar_w_max * (v2024 / maximo)
        c.rect(bar_x, b2_y, bw2, bar_h, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(F(FONT_NUM_BOLD), 10)
        c.drawRightString(x + w - 10, b2_y, f"{_br(v2024)} mi")

    # ─── 3. Resumo do município ─────────────────────────────────────────────

    def _pag_resumo(self, c, n):
        d = self.d
        pop = d["populacao"]
        rec = d["receita_corrente"]
        sus = d["sus_dependente"]
        cad = d["cadunico"]
        pct = d["percentil"]
        rec_pc_nac = rec["ranking_por_per_capita"]["nacional"]
        cor_quintil = cor_por_quintil(pct["quintil"])

        lado = self._moldura_pagina(c, n, f"{self.nome} · {self.uf}")
        x = self._content_x(lado)
        y = self._draw_cabecalho(c, x, SAFE_TOP, secao="Resumo do Município")

        # Frase descritiva (cor do quintil) — "Possui receita…"
        rec_pc_pct = 100 * (rec_pc_nac["total"] - rec_pc_nac["posicao"]) / rec_pc_nac["total"]
        if rec_pc_pct >= 50:
            frase = (
                f"Possui uma receita por habitante "
                f"superior a {int(round(rec_pc_pct))}% dos municípios do país"
            )
        else:
            frase = (
                f"Possui uma receita por habitante "
                f"inferior a {int(round(100 - rec_pc_pct))}% dos municípios do país"
            )
        # Card creme grande: frase + régua integrada dentro
        card_h = self._draw_card_status_municipio(
            c, x, y, CONTENT_W, frase, cor_quintil,
            quintil_str=pct["quintil"], decil_str=pct["decil"],
        )
        y -= card_h + 12

        # 5 KPIs em grid (linha 1: 3 KPIs / linha 2: 2 KPIs). Quintil saiu
        # — vira régua horizontal logo abaixo dos KPIs.
        cad_pct = 100 * cad["qtd_pessoas_cadastradas"] / pop["valor"] if pop["valor"] else 0
        rec_total_valor, rec_total_uni = _fmt_total_unidade(rec["valor_absoluto"])
        pop_valor, pop_unid = _fmt_pop(pop["valor"])
        kpis = [
            ("População",           pop_valor,                 pop_unid,     draw_icon_populacao),
            ("Receita Total",       rec_total_valor,           rec_total_uni, draw_icon_receita),
            ("Receita p/hab",       _fmt_money(rec["per_capita"]), "/hab",   draw_icon_receita),
            ("Pop. SUS Dependente", _br(sus["percentual_populacao"]), "%",   draw_icon_sus),
            ("Pop. CadÚnico",       _br(cad_pct),              "% pop.",     draw_icon_cadunico),
        ]
        kpi_w = (CONTENT_W - 16) / 3
        kpi_h = 64
        # Linha 1 (3 KPIs)
        for i in range(3):
            lbl, val, uni, ico = kpis[i]
            draw_kpi_box(c, lbl, val, uni,
                         x + i*(kpi_w+8), y - kpi_h,
                         w=kpi_w, h=kpi_h, icone=ico, upper=False)
        # Linha 2 (2 KPIs): centralizados
        off2 = (CONTENT_W - (2 * kpi_w + 8)) / 2
        for i in range(2):
            lbl, val, uni, ico = kpis[3 + i]
            draw_kpi_box(c, lbl, val, uni,
                         x + off2 + i*(kpi_w+8),
                         y - kpi_h*2 - 8,
                         w=kpi_w, h=kpi_h, icone=ico, upper=False)
        y -= kpi_h*2 + 8 + 14

        # Divisória sutil entre KPIs e rankings (régua de quintil agora fica
        # no canto superior direito do header — não ocupa espaço no miolo).
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(x, y, x + CONTENT_W, y)
        y -= 12

        # Posicionamento: 2 categorias (População / Receita per habitante) × 3
        # escopos (Nacional / Estadual / Por porte).
        rec_rk = rec["ranking_por_per_capita"]
        linhas = [
            ("Ranking de população",          pop["ranking_nacional"], pop["ranking_estadual"], pop["ranking_por_porte"]),
            ("Ranking de receita por habitante", rec_rk["nacional"],   rec_rk["estadual"],      rec_rk["por_porte"]),
        ]
        # Chips de ranking mais compactos pra caber a página inteira com
        # rodapé visível. Mantém respiro interno mas reduz altura total.
        chip_w = (CONTENT_W - 16) / 3
        chip_h = 70
        cat_label_h = 16
        gap_row = 10

        for ri, (cat_label, r_nac, r_est, r_por) in enumerate(linhas):
            y_cat = y - ri * (chip_h + cat_label_h + gap_row)

            # Divisória horizontal entre os dois rankings (a partir do 2º).
            if ri > 0:
                c.setStrokeColor(RULE)
                c.setLineWidth(0.6)
                c.line(x, y_cat + cat_label_h - 2, x + CONTENT_W, y_cat + cat_label_h - 2)

            # Rótulo da categoria com filete colorido à esquerda
            c.setFillColor(BLUE)
            c.rect(x, y_cat - 14, 4, 14, fill=1, stroke=0)
            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_NUM_BOLD), 12)
            c.drawString(x + 10, y_cat - 11, cat_label.upper())

            # Chips
            for ci, (escopo, r) in enumerate([("NACIONAL", r_nac),
                                              ("ESTADUAL", r_est),
                                              ("POR PORTE", r_por)]):
                cx = x + ci * (chip_w + 8)
                cy = y_cat - cat_label_h - chip_h
                self._draw_chip_ranking(c, cx, cy, chip_w, chip_h,
                                         escopo, r["posicao"], r["total"])

        # Y depois de todos os chips
        y_after = y - len(linhas) * (chip_h + cat_label_h + gap_row)
        # arte0 (ultra-fina) no rodapé do Resumo — assinatura visual sutil.
        self._decorar_rodape(c, lado, y_after, seed_offset=0, arte="arte0")

    def _draw_regua_quintil_mini(self, c, x_right, y_top, w,
                                  quintil_str: str, decil_str: str) -> None:
        """Régua de quintil estilo metodologia: 5 quadradinhos coloridos
        numerados (1º a 5º), seta acima do quintil do município, labels
        "menor receita" / "maior receita" embaixo das pontas. Compacto.

        Layout (~36pt de altura):
                  ▼
            ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐
            │1°│ │2°│ │3°│ │4°│ │5°│
            └─┘ └─┘ └─┘ └─┘ └─┘
           menor              maior
           receita            receita
        """
        quintil_n = _so_numero(quintil_str)
        try:
            quintil_idx = int(quintil_n) - 1
        except (ValueError, TypeError):
            quintil_idx = 2

        x_left = x_right - w

        # 5 quadradinhos com cantos arredondados. O quintil do município é
        # DESTACADO: quadrado maior, com borda branca e número em fonte maior.
        box_normal = 18
        box_destaque = 26     # +8pt maior que os demais
        gap = 6
        # Bloco com quadrados de tamanhos diferentes
        bloco_x = x_left + (w - (4 * box_normal + box_destaque + 4 * gap)) / 2
        bloco_y_base = y_top - 30      # baseline (parte inferior dos box normais)

        cur_x = bloco_x
        marker_cx = None
        for i, cor_seg in enumerate(FNP_QUINTIS):
            is_destaque = (i == quintil_idx)
            bs = box_destaque if is_destaque else box_normal
            # Alinha pelo centro vertical (destaque maior fica centralizado)
            bx = cur_x
            by = bloco_y_base - (bs - box_normal) / 2
            # Sombra discreta para o destacado
            if is_destaque:
                c.setFillColor(colors.HexColor("#D9D2C3"))
                c.roundRect(bx + 1.5, by - 1.5, bs, bs, 4, fill=1, stroke=0)
            c.setFillColor(cor_seg)
            c.roundRect(bx, by, bs, bs, 3 if not is_destaque else 4, fill=1, stroke=0)
            # Borda branca pro destacado (anel)
            if is_destaque:
                c.setStrokeColor(WHITE)
                c.setLineWidth(1.5)
                c.roundRect(bx + 1.5, by + 1.5, bs - 3, bs - 3, 3, fill=0, stroke=1)
                marker_cx = bx + bs / 2
                marker_top = by + bs
            # Número 1º..5º em branco no centro do quadrado
            c.setFillColor(WHITE)
            num_fs = 12 if is_destaque else 9
            c.setFont(F(FONT_NUM_BOLD), num_fs)
            c.drawCentredString(bx + bs / 2, by + bs / 2 - num_fs * 0.35,
                                 f"{i+1}º")
            cur_x += bs + gap

        # Seta apontando pra baixo, acima do quintil destacado (maior + visível)
        if marker_cx is not None:
            c.setFillColor(BLUE_DARK)
            p = c.beginPath()
            p.moveTo(marker_cx,     marker_top + 2)
            p.lineTo(marker_cx - 6, marker_top + 11)
            p.lineTo(marker_cx + 6, marker_top + 11)
            p.close()
            c.drawPath(p, fill=1, stroke=0)

        # Labels embaixo das pontas
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 7.5)
        c.drawCentredString(bloco_x + box_normal / 2,
                            bloco_y_base - 10, "MENOR RECEITA")
        c.drawCentredString(cur_x - gap - box_normal / 2,
                            bloco_y_base - 10, "MAIOR RECEITA")

    def _draw_chip_ranking(self, c, x, y, w, h, escopo: str, pos: int, tot: int):
        """Chip retangular grande: rótulo do escopo no topo + posição grande
        + 'de N municípios' embaixo. Filete superior colorido pelo percentil."""
        cor = cor_por_percentil(pos, tot)
        c.setFillColor(WHITE)
        c.roundRect(x, y, w, h, 3, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.roundRect(x, y, w, h, 3, fill=0, stroke=1)
        c.setFillColor(cor)
        c.rect(x, y + h - 5, w, 5, fill=1, stroke=0)

        # Layout interno: rótulo no topo, posição grande no meio, "de N
        # municípios" no rodapé do chip — proporcional ao chip_h=70.
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 9)
        c.drawString(x + 12, y + h - 20, escopo)

        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_NUM_BOLD), 26)
        c.drawString(x + 12, y + 24, f"{pos:,}º".replace(",", "."))

        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 8.5)
        c.drawString(x + 12, y + 10, f"de {tot:,} municípios".replace(",", "."))

    def _draw_card_status_municipio(self, c, x, y_top, w, frase, cor,
                                     quintil_str: str, decil_str: str) -> float:
        """Card creme: frase à esquerda (2 linhas, quebra antes de 'dos')
        + régua mini de quintil à direita com quadrado destacado."""
        h = 56
        c.setFillColor(CREAM)
        c.roundRect(x, y_top - h, w, h, 6, fill=1, stroke=0)
        c.setFillColor(cor)
        c.rect(x, y_top - h, 4, h, fill=1, stroke=0)

        frase_area_w = w * 0.52
        font_reg = F(FONT_TEXTO)
        font_bold = F(FONT_TEXTO_BOLD)
        import re

        # Quebra explícita: força "dos municípios do país" para a 2ª linha.
        # Linha 1: "Possui uma receita por habitante inferior a 78%"
        # Linha 2: "dos municípios do país."
        m = re.search(r"(superior|inferior) a (\d+)%", frase)
        if m:
            linha1 = frase[:m.end()]          # tudo até "inferior a 78%"
            linha2 = frase[m.end():].strip()  # "dos municípios do país..."
        else:
            linha1, linha2 = frase, ""

        # Linha 1 — com destaque colorido em "inferior a X%"
        ty1 = y_top - 22
        if m:
            antes = linha1[:m.start()]
            destaque = m.group(0)
            cur_x = x + 14
            c.setFillColor(INK); c.setFont(font_reg, 10)
            c.drawString(cur_x, ty1, antes)
            cur_x += c.stringWidth(antes, font_reg, 10)
            c.setFillColor(cor); c.setFont(font_bold, 10)
            c.drawString(cur_x, ty1, destaque)
        else:
            c.setFillColor(INK); c.setFont(font_reg, 10)
            c.drawString(x + 14, ty1, linha1)

        # Linha 2 — "dos municípios do país."
        if linha2:
            c.setFillColor(INK); c.setFont(font_reg, 10)
            c.drawString(x + 14, ty1 - 13, linha2)

        # Régua mini de quintil à direita (com quadrado do município
        # AUMENTADO para destacar visualmente)
        self._draw_regua_quintil_mini(
            c, x_right=x + w - 14, y_top=y_top - 4,
            w=w - frase_area_w - 16,
            quintil_str=quintil_str, decil_str=decil_str,
        )
        return h

    def _draw_frase_destaque(self, c, x, y, w, frase, cor):
        """Card pílula horizontal com filete colorido na esquerda + frase em
        destaque. Coloriza 'superior a X%' / 'inferior a X%' com a cor do quintil."""
        h = 30
        c.setFillColor(CREAM)
        c.roundRect(x, y - h, w, h, 6, fill=1, stroke=0)
        c.setFillColor(cor)
        c.rect(x, y - h, 4, h, fill=1, stroke=0)

        import re
        m = re.search(r"(superior|inferior) a (\d+)%", frase)
        ty = y - h/2 - 3
        font_reg = F(FONT_TEXTO)
        font_bold = F(FONT_TEXTO_BOLD)
        if m:
            antes = frase[:m.start()]
            destaque = m.group(0)
            depois = frase[m.end():]
            # Calcula largura total para centralizar horizontalmente
            wA = c.stringWidth(antes,    font_reg,  10.5)
            wB = c.stringWidth(destaque, font_bold, 10.5)
            wC = c.stringWidth(depois,   font_reg,  10.5)
            total = wA + wB + wC
            tx = x + (w - total) / 2
            c.setFillColor(INK);  c.setFont(font_reg, 10.5);  c.drawString(tx, ty, antes);    tx += wA
            c.setFillColor(cor);  c.setFont(font_bold, 10.5); c.drawString(tx, ty, destaque); tx += wB
            c.setFillColor(INK);  c.setFont(font_reg, 10.5);  c.drawString(tx, ty, depois)
        else:
            c.setFillColor(INK)
            c.setFont(font_reg, 10.5)
            c.drawCentredString(x + w/2, ty, frase)

    # ─── 4. Estrutura da receita ────────────────────────────────────────────

    def _cores_estrutura(self):
        """Paleta dos 4 grupos da pizza: tons de azul + um amarelo de acento.

        Categorica de proposito. A paleta antiga usava verde/amarelo/laranja/
        vermelho — exatamente as cores dos quintis — e entao verde significava
        "Transferencias" numa pagina e "supera muitos municipios" na seguinte.
        Aqui a pizza responde "qual grupo?" e o resto do folheto responde
        "bom ou ruim?": escalas diferentes, paletas diferentes.
        """
        return {
            "transferencias_correntes":    BLUE,
            "imposto_taxas_contribuicoes": BLUE_MID,
            "outras_receita":              BLUE_LIGHT,
            "contribuicoes":               YELLOW_DARK,
        }

    def _pag_estrutura(self, c, n):
        d = self.d
        grupos = d["estrutura_receita_resumo"]
        medias_nac = self._medias_nacionais_por_field()
        medias_uf  = self._medias_estaduais_por_field()

        lado = self._moldura_pagina(c, n)
        x = self._content_x(lado)
        y = self._draw_cabecalho(c, x, SAFE_TOP, secao="Estrutura da Receita")

        y = draw_body(
            c,
            "Distribuição dos 4 principais grupos de receita corrente.",
            x, y, CONTENT_W, size=FS_BODY,
        )
        y -= 14

        total = sum(g["valor_absoluto"] for g in grupos) or 1
        # Cor por field do grupo (categoria), conforme padrão da landing IFEM:
        #   Impostos/Taxas/Contribuições de Melhoria → azul
        #   Transferências Correntes                 → verde
        #   Contribuições                            → laranja
        #   Outras Receitas                          → vermelho
        cor_grupo = self._cores_estrutura()
        segs = [{"categoria": g["rubrica"],
                 "field":     g.get("field"),
                 "valor_bi":  g["valor_absoluto"] / 1e9,
                 "pct":       100 * g["valor_absoluto"] / total}
                for g in grupos]
        cores = [cor_grupo.get(s["field"], BLUE) for s in segs]

        # Gráfico de PIZZA à esquerda + legenda à direita
        pie_h = 210
        pie_r = 80
        pie_cx = x + pie_r + 6
        pie_cy = y - pie_h/2
        self._draw_pizza(c, pie_cx, pie_cy, pie_r, segs, cores)

        # Legenda à direita: nome + percentual + valor
        leg_x = x + 2 * pie_r + 26
        leg_y = y - 14
        for i, seg in enumerate(segs):
            row_y = leg_y - i * 48
            c.setFillColor(cores[i])
            c.roundRect(leg_x, row_y - 12, 11, 11, 2, fill=1, stroke=0)
            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_TEXTO_BOLD), 10.5)
            cat_nome = seg["categoria"]
            if c.stringWidth(cat_nome, F(FONT_TEXTO_BOLD), 10.5) > CONTENT_W - (leg_x - x) - 6:
                palavras = cat_nome.split()
                meio = len(palavras) // 2
                l1 = " ".join(palavras[:meio])
                l2 = " ".join(palavras[meio:])
                c.drawString(leg_x + 18, row_y - 3, l1)
                c.drawString(leg_x + 18, row_y - 14, l2)
                row_pct_y = row_y - 30
            else:
                c.drawString(leg_x + 18, row_y - 3, cat_nome)
                row_pct_y = row_y - 18
            c.setFillColor(cores[i])
            c.setFont(F(FONT_NUM_BOLD), 16)
            pct_str = f"{seg['pct']:.1f}%".replace(".", ",")
            c.drawString(leg_x + 18, row_pct_y, pct_str)
            wp = c.stringWidth(pct_str, F(FONT_NUM_BOLD), 16)
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), 9)
            c.drawString(leg_x + 18 + wp + 6, row_pct_y + 4,
                         f"R$ {seg['valor_bi']:.1f} bi".replace(".", ","))

        y -= pie_h + 12

        # arte1 (padrão modular) no rodapé — substitui a tabela comparativa
        # de R$/hab, que já está disponível detalhada nas páginas 5 a 8.
        draw_caption(c, "Fonte: STN/Siconfi. Elaboração: FNP.", x, y)
        y -= 16
        self._decorar_rodape(c, lado, y, seed_offset=0, arte="arte1")

    def _draw_pizza(self, c, cx, cy, r, segmentos, cores):
        """Desenha gráfico de pizza simples. segmentos: lista de dicts com 'pct'.
        Usa Wedge para cada fatia."""
        from reportlab.graphics.shapes import Drawing
        from reportlab.lib import colors as rl_colors

        total = sum(s["pct"] for s in segmentos) or 1
        start = 90.0    # começa pelo topo
        for i, seg in enumerate(segmentos):
            ang = 360 * (seg["pct"] / total)
            end = start - ang
            cor = cores[i % len(cores)]
            # Desenha wedge como path
            self._draw_wedge(c, cx, cy, r, start, end, cor)
            start = end

        # Furo central pra ficar tipo donut elegante
        c.setFillColor(WHITE)
        c.circle(cx, cy, r * 0.45, fill=1, stroke=0)

    def _draw_wedge(self, c, cx, cy, r, start_deg, end_deg, cor):
        """Desenha uma fatia de pizza (path triangular + arco aproximado por
        polygon com muitos pontos)."""
        import math
        c.setFillColor(cor)
        p = c.beginPath()
        p.moveTo(cx, cy)
        n_steps = max(8, int(abs(start_deg - end_deg) / 3))
        for i in range(n_steps + 1):
            t = i / n_steps
            ang = math.radians(start_deg + (end_deg - start_deg) * t)
            px = cx + r * math.cos(ang)
            py = cy + r * math.sin(ang)
            p.lineTo(px, py)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    # ─── 5. Detalhamento das Receitas — categorias-mãe (estilo landing) ────

    def _medias_nacionais_por_field(self):
        """Atalho: retorna { field: media_R$/hab } extraído de _medias_receitas."""
        medias = self.d.get("_medias_receitas") or {}
        return (medias.get("nacional") or {}).get("media") or {}

    def _pag_detalhamento(self, c, n):
        """Página 5: 4 cards-mãe (nivel_1) no estilo landing IFEM.
        Inclui Município + Média Nacional + Média Estadual em cada card."""
        d = self.d
        grupos = d["estrutura_receita_resumo"]
        medias_nac = self._medias_nacionais_por_field()
        medias_uf  = self._medias_estaduais_por_field()

        lado = self._moldura_pagina(c, n)
        x = self._content_x(lado)
        y = self._draw_cabecalho(c, x, SAFE_TOP, secao="Detalhamento das Receitas")

        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 10)
        c.drawString(x, y, "Posição do município em cada categoria principal de receita corrente por habitante.")
        y -= 16

        # Espaço útil para os 4 cards-mãe — divide igualmente.
        # 4 cards + 3 gaps (6pt cada). Garante caber até SAFE_BOTTOM.
        gap = 6
        card_h = min(108, (y - SAFE_BOTTOM - 3 * gap) / 4)
        for g in grupos:
            field = g.get("field")
            y = self._draw_card_categoria_pleno(
                c, x=x, y_top=y, w=CONTENT_W,
                titulo=g["rubrica"],
                supera_pct=g.get("supera_pct_nacional"),
                municipio_valor=g["per_capita"],
                medias=[
                    ("Média Nacional", medias_nac.get(field)),
                    ("Média Estadual", medias_uf.get(field)),
                ],
                size="full",
                custom_h=card_h,
            )
            y -= gap - 6   # compensa o respiro embutido no card

    # ─── 6/7. Detalhamento das Receitas — subcategorias (nivel_2) ─────────

    def _filhos_por_pai(self):
        """Mapeia field do pai (nivel_1) → lista de filhos (nivel_2) já no
        formato esperado por draw_categoria_bloco."""
        d = self.d
        nivel_2 = d["estrutura_receita_detalhada"]["nivel_2_categorias"]
        hierarquia = d.get("hierarquia_receitas") or {}
        parent_de = {n2["field"]: n2.get("parent_field")
                     for n2 in hierarquia.get("nivel_2", [])}
        medias_nac = self._medias_nacionais_por_field()

        filhos_por_pai = {}
        for n2 in nivel_2:
            pai = parent_de.get(n2.get("field"))
            if not pai or n2["valor_absoluto"] <= 0:
                continue
            filhos_por_pai.setdefault(pai, []).append({
                "titulo":     n2["rubrica"],
                "supera_pct": n2.get("supera_pct_nacional"),
                "per_capita": n2["per_capita"],
                "media":      medias_nac.get(n2.get("field")),
            })
        return filhos_por_pai

    # ─── Médias por UF/porte (componentes auxiliares) ────────────────────

    def _medias_estaduais_por_field(self):
        medias = self.d.get("_medias_receitas") or {}
        return ((medias.get("por_uf") or {}).get(self.uf) or {}).get("media") or {}

    def _medias_porte_por_field(self):
        medias = self.d.get("_medias_receitas") or {}
        porte = self.ident.get("porte", "")
        return ((medias.get("por_porte") or {}).get(porte) or {}).get("media") or {}

    def _draw_pag_categoria(self, c, n: int, grupo: dict,
                              filtro_filhos: list[str] | None = None,
                              secao_titulo: str | None = None):
        """Página dedicada a UMA categoria-mãe (ou um subconjunto dela).
        `filtro_filhos`: lista de `field` das subcategorias a mostrar; None=todas.
        `secao_titulo`: rótulo da seção (default = grupo["rubrica"]).
        """
        filhos_por_pai = self._filhos_por_pai_completo()
        netos_por_pai  = self._netos_por_pai_n2()
        medias_nac = self._medias_nacionais_por_field()
        medias_uf  = self._medias_estaduais_por_field()

        lado = self._moldura_pagina(c, n)
        x = self._content_x(lado)
        y = self._draw_cabecalho(c, x, SAFE_TOP,
                                  secao=secao_titulo or grupo["rubrica"])

        # Card-mãe (NÍVEL 1) — altura adaptativa baseada na qtd total de
        # netos visíveis (considerando o filtro).
        field = grupo.get("field")
        filhos_temp = filhos_por_pai.get(field, [])
        if filtro_filhos is not None:
            filhos_temp = [f for f in filhos_temp if f.get("field") in filtro_filhos]
        netos_total = sum(len(netos_por_pai.get(f.get("field")) or []) for f in filhos_temp)
        if netos_total >= 10:
            mae_h = 72
        elif netos_total >= 6:
            mae_h = 82
        else:
            mae_h = 96

        y = self._draw_card_categoria_pleno(
            c, x=x, y_top=y, w=CONTENT_W,
            titulo=grupo["rubrica"],
            supera_pct=grupo.get("supera_pct_nacional"),
            municipio_valor=grupo["per_capita"],
            medias=[
                ("Média Nacional", medias_nac.get(field)),
                ("Média Estadual", medias_uf.get(field)),
            ],
            size="full",
            custom_h=mae_h,
        )
        y -= 4

        filhos = filhos_por_pai.get(field) or []
        if filtro_filhos is not None:
            filhos = [f for f in filhos if f.get("field") in filtro_filhos]
        if not filhos:
            return

        # Espaço útil entre a categoria-mãe (já desenhada) e a SAFE_BOTTOM.
        # ALGORITMO RESPONSIVO:
        # 1. Tenta perfis do mais espaçoso ao mais compacto
        # 2. Se nem o mais compacto cabe, reduz max_netos progressivamente
        # 3. Como último recurso, força o ultra-compact + min netos
        #
        # Reserva 28pt extras quando alguma subcategoria tem nível 3 (haverá
        # tabela com pílula colorida → precisa caber a nota de rodapé).
        tem_netos_prev = any(netos_por_pai.get(f.get("field")) for f in filhos)
        reserva_nota = 28 if tem_netos_prev else 0
        espaco_disp = y - SAFE_BOTTOM - reserva_nota
        respiro = 4   # entre subcategorias

        def _est_altura(card_h, line_h, header_h, max_netos=10):
            total = 0
            for f in filhos:
                netos = netos_por_pai.get(f.get("field")) or []
                total += card_h + 2
                if netos:
                    total += header_h + min(len(netos), max_netos) * line_h + 2
                total += respiro
            return total

        # Perfis de densidade.
        perfis = [
            (96, 20, 17, 10),
            (90, 19, 16, 10),
            (84, 17, 15, 9),
            (78, 15, 13, 8),
            (74, 14, 13, 7),
            (70, 13, 12, 6),
            (66, 12, 11, 5),
            (62, 11, 11, 4),
        ]
        card_h, line_h, header_h, max_netos = perfis[-1]   # default = mínimo

        # Procura o perfil MAIOR que ainda cabe.
        for ch, lh, hh, mn in perfis:
            if _est_altura(ch, lh, hh, max_netos=mn) <= espaco_disp:
                card_h, line_h, header_h, max_netos = ch, lh, hh, mn
                break
        else:
            # Nenhum perfil padrão coube — usa o mais compacto e CORTA netos.
            for mn in (6, 5, 4, 3, 2, 1):
                if _est_altura(card_h, line_h, header_h, mn) <= espaco_disp:
                    max_netos = mn
                    break
            else:
                max_netos = 1  # extremo: 1 neto só por subcategoria

        # Hierarquia visual: subcategorias INDENTADAS à direita (16pt) e
        # com largura reduzida — reforça que estão SOB a categoria-mãe.
        INDENT_SUB = 16
        sub_x = x + INDENT_SUB
        sub_w = CONTENT_W - INDENT_SUB

        for f in filhos:
            n2_field = f.get("field")
            netos = netos_por_pai.get(n2_field) or []
            if len(netos) > max_netos:
                netos = netos[:max_netos]

            y = self._draw_card_categoria_pleno(
                c, x=sub_x, y_top=y, w=sub_w,
                titulo=f["titulo"],
                supera_pct=f.get("supera_pct"),
                municipio_valor=f["per_capita"],
                medias=[
                    ("Média Nacional", medias_nac.get(n2_field)),
                    ("Média Estadual", medias_uf.get(n2_field)),
                ],
                size="compact",
                custom_h=card_h,
            )
            y -= 2

            if netos:
                # Nível 3 indenta ainda mais à direita
                y = self._draw_lista_nivel3(c, sub_x, y, sub_w, netos,
                                             medias_nac, medias_uf,
                                             line_h=line_h, header_h=header_h)
            y -= respiro

            if y < SAFE_BOTTOM:
                break

        # Nota de rodapé explicando o significado da pílula %.
        # Aparece em TODAS as páginas com listas nível 3 (Impostos,
        # Transferências da União, Transf. dos Estados, Contribuições, …) —
        # categorias COM netos. O espaço foi pré-reservado em `reserva_nota`.
        tem_netos = any(netos_por_pai.get(f.get("field")) for f in filhos)
        if tem_netos:
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), 7.5)
            nota = (
                "* A porcentagem na pílula colorida indica em quantos % dos "
                "municípios do país este município supera (receita por habitante) "
                "para esse dado."
            )
            from reportlab.lib.utils import simpleSplit as _sp
            linhas_nota = _sp(nota, F(FONT_TEXTO), 7.5, CONTENT_W - 4)
            for i, ln in enumerate(linhas_nota):
                c.drawString(x, y - i * 10 - 8, ln)
            y -= len(linhas_nota) * 10 + 10

        # Decora o rodapé com arte1 quando sobra espaço — a medida é feita
        # dentro do `_decorar_rodape`.
        self._decorar_rodape(c, lado, y, seed_offset=2, forcar_fina=True)

    def _netos_por_pai_n2(self):
        """Mapeia field do pai (nivel_2) → lista de filhos (nivel_3) ordenada
        por per_capita desc, ignorando zerados."""
        d = self.d
        nivel_3 = d["estrutura_receita_detalhada"]["nivel_3_rubricas"]
        hierarquia = d.get("hierarquia_receitas") or {}
        parent_de = {n3["field"]: n3.get("parent_field")
                     for n3 in hierarquia.get("nivel_3", [])}
        netos = {}
        for n3 in nivel_3:
            pai = parent_de.get(n3.get("field"))
            if not pai or n3.get("per_capita", 0) <= 0:
                continue
            netos.setdefault(pai, []).append({
                "titulo":     n3["rubrica"],
                "field":      n3.get("field"),
                "supera_pct": n3.get("supera_pct_nacional"),
                "per_capita": n3["per_capita"],
            })
        for k in netos:
            netos[k].sort(key=lambda r: r["per_capita"], reverse=True)
        return netos

    def _draw_lista_nivel3(self, c, x, y, w, netos, medias_nac, medias_uf,
                            line_h=18, header_h=14):
        """Lista nível 3 com 4 colunas (sem Média Porte): nome + município +
        média nacional + média estadual + pílula. Zebra alternada."""
        from core.components import cor_status_landing, _fmt_money_br as _money

        indent = 18
        # Fontes proporcionais à altura da linha
        if   line_h >= 18: font_size, hdr_fs = 10,   8.5
        elif line_h >= 16: font_size, hdr_fs = 9.5,  8
        elif line_h >= 14: font_size, hdr_fs = 9,    7.5
        elif line_h >= 13: font_size, hdr_fs = 8.5,  7.5
        else:              font_size, hdr_fs = 8,    7

        # Layout: nome + 3 colunas de valor + 1 coluna reservada para a pílula.
        # A pílula NÃO sobrepõe a coluna Méd. Estadual porque tem seu próprio
        # espaço à direita.
        col_pill_w  = (w - indent) * 0.10
        col_nome_w  = (w - indent) * 0.42
        col_kpi_w   = (w - indent) * 0.16
        col_xs = [
            x + indent,                                          # nome
            x + indent + col_nome_w,                             # município
            x + indent + col_nome_w + col_kpi_w,                 # nacional
            x + indent + col_nome_w + col_kpi_w * 2,             # estadual
        ]
        table_x_left  = x + indent
        table_x_right = x + w - 6
        table_w = table_x_right - table_x_left
        pill_col_x_start = table_x_right - col_pill_w

        # Header
        c.setFillColor(colors.HexColor("#E8EEF7"))
        c.rect(table_x_left, y - header_h, table_w, header_h, fill=1, stroke=0)
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), hdr_fs)
        hdrs = ["DETALHAMENTO", "MUNICÍPIO", "NACIONAL", "ESTADUAL"]
        hdr_baseline = y - header_h + (header_h - hdr_fs) / 2 + 1
        c.drawString(col_xs[0] + 6, hdr_baseline, hdrs[0])
        c.drawRightString(col_xs[1] + col_kpi_w - 6, hdr_baseline, hdrs[1])
        c.drawRightString(col_xs[2] + col_kpi_w - 6, hdr_baseline, hdrs[2])
        # MÉD. ESTADUAL alinha à borda da coluna da pílula
        c.drawRightString(pill_col_x_start - 6, hdr_baseline, hdrs[3])
        y -= header_h

        for ri, r in enumerate(netos):
            row_bot = y - line_h
            # Zebra
            c.setFillColor(WHITE if ri % 2 == 0 else colors.HexColor("#F7F4ED"))
            c.rect(table_x_left, row_bot, table_w, line_h, fill=1, stroke=0)
            # Linha divisória sutil
            c.setStrokeColor(RULE)
            c.setLineWidth(0.25)
            c.line(table_x_left, row_bot, table_x_right, row_bot)

            txt_y = row_bot + (line_h - font_size) / 2 + 1
            c.setFillColor(INK)
            c.setFont(F(FONT_TEXTO), font_size)
            c.drawString(col_xs[0] + 6, txt_y, r["titulo"])

            # Cada valor traz um sufixo "/hab" pequeno colado à direita.
            # Como a coluna é alinhada à direita, desenhamos "/hab" no X
            # final e o valor logo à esquerda dele.
            sufixo = "/hab"
            suf_fs = max(5.5, font_size - 2.5)
            suf_font = F(FONT_TEXTO)

            def _drawValHab(right_x, valor_str, cor_valor, font_val, fs_val):
                w_suf = c.stringWidth(sufixo, suf_font, suf_fs)
                c.setFillColor(MUTED)
                c.setFont(suf_font, suf_fs)
                c.drawString(right_x - w_suf, txt_y + 1, sufixo)
                c.setFillColor(cor_valor)
                c.setFont(font_val, fs_val)
                c.drawRightString(right_x - w_suf - 1, txt_y, valor_str)

            _drawValHab(col_xs[1] + col_kpi_w - 6, _money(r["per_capita"]),
                        BLUE_DARK, F(FONT_TEXTO_BOLD), font_size)
            _drawValHab(col_xs[2] + col_kpi_w - 6,
                        _money(medias_nac.get(r.get("field"))),
                        MUTED, F(FONT_TEXTO), font_size)
            _drawValHab(pill_col_x_start - 6,
                        _money(medias_uf.get(r.get("field"))),
                        MUTED, F(FONT_TEXTO), font_size)

            # Pílula com supera % centralizada na sua coluna reservada
            pct = r.get("supera_pct")
            if pct is not None:
                cor = cor_status_landing(pct)
                pill_str = f"{pct}%"
                pill_fs = max(7.5, font_size - 0.5)
                pill_w_v = c.stringWidth(pill_str, F(FONT_TEXTO_BOLD), pill_fs) + 12
                pill_h_v = min(line_h - 3, 14)
                pill_x = pill_col_x_start + (col_pill_w - pill_w_v) / 2
                pill_y = row_bot + (line_h - pill_h_v) / 2
                c.setFillColor(cor)
                c.roundRect(pill_x, pill_y, pill_w_v, pill_h_v, pill_h_v/2, fill=1, stroke=0)
                c.setFillColor(WHITE)
                c.setFont(F(FONT_TEXTO_BOLD), pill_fs)
                c.drawCentredString(pill_x + pill_w_v/2, pill_y + (pill_h_v - pill_fs)/2 + 1,
                                     pill_str)
            y -= line_h
        return y

    def _filhos_por_pai_completo(self):
        """Como _filhos_por_pai mas inclui o `field` em cada filho (necessário
        para olhar médias UF/porte)."""
        d = self.d
        nivel_2 = d["estrutura_receita_detalhada"]["nivel_2_categorias"]
        hierarquia = d.get("hierarquia_receitas") or {}
        parent_de = {n2["field"]: n2.get("parent_field")
                     for n2 in hierarquia.get("nivel_2", [])}
        medias_nac = self._medias_nacionais_por_field()
        filhos_por_pai = {}
        for n2 in nivel_2:
            pai = parent_de.get(n2.get("field"))
            if not pai or n2["valor_absoluto"] <= 0:
                continue
            filhos_por_pai.setdefault(pai, []).append({
                "titulo":     n2["rubrica"],
                "field":      n2.get("field"),
                "supera_pct": n2.get("supera_pct_nacional"),
                "per_capita": n2["per_capita"],
                "media":      medias_nac.get(n2.get("field")),
            })
        return filhos_por_pai

    def _draw_card_categoria_pleno(self, c, *, x, y_top, w,
                                    titulo, supera_pct, municipio_valor,
                                    medias, size="full", custom_h=None):
        """Card no estilo landing IFEM com 3 KPIs internos:
        [Município] | [Média Nacional] | [Média Estadual]
        Quando `size='compact'` reduz altura e fonte para subcards.
        Em cards muito compactos (h<68), suprime a frase 'Supera X%' para
        evitar sobreposição com os KPIs — o quadradinho de status já indica."""
        from core.components import (
            cor_status_landing, _fmt_money_br as _money,
        )
        cor = cor_status_landing(supera_pct)
        mostra_frase = True

        if size == "compact":
            h = custom_h or 92
            # Perfis com frase sempre visível + KPI sem sobreposição.
            if h >= 96:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 40, 12.5, 10, 15.5, 7.5, 11
            elif h >= 88:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 36, 12, 9.5, 14.5, 7, 10
            elif h >= 80:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 34, 11.5, 9, 13.5, 6.5, 9
            elif h >= 72:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 32, 11, 8.5, 12.5, 6, 8
            elif h >= 66:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 28, 10.5, 8, 11.5, 5.5, 7
            else:
                # h ≥ 62: ultra-compacto
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 24, 10, 7.5, 11, 5, 7
        else:
            h = custom_h or 92
            # Internos proporcionais à altura (size=full também aceita custom_h)
            if h >= 100:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 44, 14.5, 11, 19, 7.5, 12
            elif h >= 92:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 40, 14, 10.5, 18, 7.5, 12
            elif h >= 86:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 38, 13.5, 10, 17, 7, 11
            elif h >= 80:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 34, 13, 9.5, 16, 7, 10
            else:
                kpi_h, title_fs, frase_fs, valor_fs, label_fs, pad_t = 30, 12.5, 9.5, 15, 6.5, 9

        y_bot = y_top - h
        c.setFillColor(WHITE)
        c.roundRect(x, y_bot, w, h, 4, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.roundRect(x, y_bot, w, h, 4, fill=0, stroke=1)

        # Status box + título
        pad_l = 12
        c.setFillColor(cor)
        c.rect(x + pad_l, y_top - pad_t - 9, 9, 9, fill=1, stroke=0)
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_NUM_BOLD), title_fs)
        c.drawString(x + pad_l + 16, y_top - pad_t - 8, titulo)

        # Frase "Supera X% dos municípios" SEMPRE visível abaixo do título.
        # Mesmo padrão visual em todos os cards (full e compact).
        if supera_pct is not None:
            frase_y = y_top - pad_t - 22
            verbo = ("Supera apenas " if supera_pct < 60 else "Supera ") + f"{supera_pct}%"
            c.setFillColor(cor)
            c.setFont(F(FONT_TEXTO_SEMIBOLD), frase_fs)
            c.drawString(x + pad_l, frase_y, verbo)
            wv = c.stringWidth(verbo, F(FONT_TEXTO_SEMIBOLD), frase_fs)
            c.setFillColor(INK)
            c.setFont(F(FONT_TEXTO), frase_fs)
            c.drawString(x + pad_l + wv, frase_y, " dos municípios")

        # 3 KPIs: município + médias (variável). Caixas mais largas.
        kpi_y = y_bot + 8
        gap = 8
        n_kpis = 1 + len(medias)
        kpi_w = (w - pad_l*2 - gap*(n_kpis - 1)) / n_kpis

        def _kpi(kx, label, valor, destaque=False):
            bg = CREAM_DARK if destaque else CREAM
            c.setFillColor(bg)
            c.roundRect(kx, kpi_y, kpi_w, kpi_h, 3, fill=1, stroke=0)
            # Label COLADO no topo (baseline = topo - label_fs - 1).
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), label_fs)
            label_y = kpi_y + kpi_h - label_fs - 2
            c.drawCentredString(kx + kpi_w/2, label_y, label.upper())
            # Valor + sufixo "/hab" pequeno (à direita do valor, baseline um
            # pouco acima). Conjunto valor+sufixo é centralizado horizontal.
            valor_str = _money(valor)
            valor_y = kpi_y + 4
            valor_font = F(FONT_NUM_BOLD)
            sufixo_str = "/hab"
            sufixo_fs = max(5.5, label_fs - 0.5)
            sufixo_font = F(FONT_TEXTO)
            w_valor = c.stringWidth(valor_str, valor_font, valor_fs)
            w_sufixo = c.stringWidth(" " + sufixo_str, sufixo_font, sufixo_fs)
            total_w = w_valor + w_sufixo
            start_x = kx + (kpi_w - total_w) / 2
            c.setFillColor(BLUE_DARK if destaque else INK)
            c.setFont(valor_font, valor_fs)
            c.drawString(start_x, valor_y, valor_str)
            c.setFillColor(MUTED)
            c.setFont(sufixo_font, sufixo_fs)
            c.drawString(start_x + w_valor, valor_y + 1, " " + sufixo_str)

        _kpi(x + pad_l, "Município", municipio_valor, destaque=True)
        for i, (lbl, val) in enumerate(medias):
            _kpi(x + pad_l + (i+1)*(kpi_w + gap), lbl, val)

        return y_bot - 6

    def _grupo_por_field(self, field: str) -> dict | None:
        """Busca em estrutura_receita_resumo o grupo pelo `field` (chave estável).
        A ordem do array varia por município (geralmente ordenado por valor),
        então NÃO confiar em índice posicional."""
        for g in self.d.get("estrutura_receita_resumo") or []:
            if g.get("field") == field:
                return g
        return None

    def _pag_detalhamento_subs_a(self, c, n):
        g = self._grupo_por_field("imposto_taxas_contribuicoes")
        if g:
            self._draw_pag_categoria(c, n, g)

    def _pag_detalhamento_subs_b(self, c, n):
        g = self._grupo_por_field("transferencias_correntes")
        if g:
            self._draw_pag_categoria(c, n, g)

    def _pag_transf_uniao(self, c, n):
        """Página dedicada a Transferências da União (filho da categoria
        'Transferências Correntes'). Permite mais espaço para nível 3."""
        g = self._grupo_por_field("transferencias_correntes")
        if g:
            self._draw_pag_categoria(
                c, n, g,
                filtro_filhos=["tranferencias_uniao"],
                secao_titulo="Transferências da União",
            )

    def _pag_transf_estados(self, c, n):
        """Página dedicada a Transferências dos Estados + Outras Transferências."""
        g = self._grupo_por_field("transferencias_correntes")
        if g:
            self._draw_pag_categoria(
                c, n, g,
                filtro_filhos=["tranferencias_estados", "outras_tranferencias"],
                secao_titulo="Transferências dos Estados e Outras",
            )

    def _pag_detalhamento_subs_c(self, c, n):
        g = self._grupo_por_field("outras_receita")
        if g:
            self._draw_pag_categoria(c, n, g)

    def _pag_detalhamento_subs_d(self, c, n):
        g = self._grupo_por_field("contribuicoes")
        if g:
            self._draw_pag_categoria(c, n, g)

    # ─── 8. Principais rubricas (nível 3 — IPTU, ISS, FPM, ICMS, FUNDEB…) ──

    def _pag_principais_rubricas(self, c, n):
        """Página 8: top rubricas de nível 3 ordenadas por per_capita do
        município. Mostra IPTU, ISS, FPM, ICMS, FUNDEB etc — onde está,
        concretamente, o dinheiro que entra no caixa municipal."""
        d = self.d
        rubricas = d["estrutura_receita_detalhada"]["nivel_3_rubricas"]
        medias_nac = self._medias_nacionais_por_field()

        lado = self._moldura_pagina(c, n)
        x = self._content_x(lado)
        y = self._draw_cabecalho(c, x, SAFE_TOP,
                                  capitulo="Cap. 3 · Detalhamento",
                                  secao="Principais Rubricas")

        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 10)
        c.drawString(x, y, "As 10 rubricas com maior valor por habitante no município.")
        y -= 20

        # Pega top 10 por per_capita desc, ignorando zerados
        top = sorted(
            [r for r in rubricas if r.get("per_capita", 0) > 0],
            key=lambda r: r["per_capita"], reverse=True,
        )[:10]

        # Linhas em formato compact (1 linha por rubrica):
        #   [statusBox] Rubrica          municipio R$X    /  média R$Y    [pct chip]
        ROW_H = 38
        for i, r in enumerate(top):
            field = r.get("field")
            pct = r.get("supera_pct_nacional")
            media = medias_nac.get(field)
            row_y = y - i * (ROW_H + 4)
            self._draw_rubrica_row(
                c, x, row_y, CONTENT_W, ROW_H,
                titulo=r["rubrica"],
                supera_pct=pct,
                per_capita=r["per_capita"],
                media=media,
            )

        # Caption final (se sobrar espaço)
        y_after = y - len(top) * (ROW_H + 4) - 8
        if y_after > 60:
            draw_caption(c, "Fonte: STN/Siconfi. Elaboração: FNP. Valores em R$/hab.", x, y_after)

    def _draw_rubrica_row(self, c, x, y_top, w, h, titulo, supera_pct,
                           per_capita, media):
        """Linha compacta de rubrica: status box + nome + município + média + pílula %."""
        from core.components import cor_status_landing, _fmt_money_br as _money
        cor = cor_status_landing(supera_pct)
        y_bot = y_top - h
        # Fundo branco com borda
        c.setFillColor(WHITE)
        c.roundRect(x, y_bot, w, h, 3, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.roundRect(x, y_bot, w, h, 3, fill=0, stroke=1)

        # Status box (esquerda)
        c.setFillColor(cor)
        c.rect(x + 10, y_top - 18, 9, 9, fill=1, stroke=0)

        # Título
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 10)
        c.drawString(x + 26, y_top - 17, titulo)

        # Subtítulo: município R$X  /  média R$Y
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 8.5)
        sub_y = y_top - 30
        c.drawString(x + 26, sub_y, "Município: ")
        wp = c.stringWidth("Município: ", F(FONT_TEXTO), 8.5)
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_TEXTO_BOLD), 8.5)
        muni_str = _money(per_capita)
        c.drawString(x + 26 + wp, sub_y, muni_str)
        wm = c.stringWidth(muni_str, F(FONT_TEXTO_BOLD), 8.5)
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 8.5)
        c.drawString(x + 26 + wp + wm, sub_y, "  ·  Média nacional: ")
        wq = c.stringWidth("  ·  Média nacional: ", F(FONT_TEXTO), 8.5)
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_TEXTO_BOLD), 8.5)
        c.drawString(x + 26 + wp + wm + wq, sub_y, _money(media))

        # Pílula percentil à direita
        if supera_pct is not None:
            pill_str = f"supera {supera_pct}%"
            pill_w = c.stringWidth(pill_str, F(FONT_TEXTO_BOLD), 9) + 14
            pill_h = 18
            pill_x = x + w - pill_w - 12
            pill_y = y_top - h/2 - pill_h/2
            c.setFillColor(cor)
            c.roundRect(pill_x, pill_y, pill_w, pill_h, pill_h/2, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont(F(FONT_TEXTO_BOLD), 9)
            c.drawCentredString(pill_x + pill_w/2, pill_y + 5, pill_str)

    # ─── 7. Síntese fiscal com linha do tempo 2000-2024 ─────────────────────

    def _pag_sintese(self, c, n):
        d = self.d
        s = d["sintese_fiscal_2000_2024"]
        h2000 = d["posicao_historica"]["ano_2000"]
        h2024 = d["posicao_historica"]["ano_2024"]

        lado = self._moldura_pagina(c, n)
        x = self._content_x(lado)
        y = self._draw_cabecalho(c, x, SAFE_TOP, secao=f"Síntese Fiscal {PERIODO}")
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 9.5)
        c.drawString(x, y, f"Trajetória entre {ANO_BASE} e {ANO_REF} (valores corrigidos pela inflação).")
        y -= 24

        # 2 blocos de variação no formato exato da landing IFEM:
        #
        #   [ícone azul circular]  A <Termo destacado> cresceu  [+78,4%]  entre 2000 e 2024.
        #                          No mesmo período, a média dos municípios variou 316,7%.
        #
        # Receita usa pílula verde (variação positiva); População usa pílula azul.
        rec_mun = s["delta_receita_per_capita_pct"]
        rec_nac = s["media_nacional_delta_receita_per_capita_pct"]
        pop_mun = s["delta_populacao_pct"]
        pop_nac = s["media_nacional_delta_populacao_pct"]

        # Verbo de população depende do sinal — pra municípios sem dado de 2000
        # (emancipações pós-1999), usar "variou" como fallback neutro.
        if pop_mun is None:
            verbo_pop = "variou"
        elif pop_mun >= 0:
            verbo_pop = "aumentou"
        else:
            verbo_pop = "caiu"

        blocos = [
            {
                "icone":       self._icone_receita_circ,
                "destaque":    "Receita por Habitante",
                "verbo":       "cresceu" if rec_mun is not None else "variou",
                "tail":        f"entre {ANO_BASE} e {ANO_REF}.",
                "var_mun":     rec_mun,
                "var_nac":     rec_nac,
                "pill_bg":     colors.HexColor("#D1F2DC"),   # verde claro pastel
                "pill_text":   colors.HexColor("#1C7E3F"),   # verde escuro
                "comp_tpl":    "No mesmo período, a média dos municípios variou ",
            },
            {
                "icone":       self._icone_populacao_circ,
                "destaque":    "População",
                "verbo":       verbo_pop,
                "tail":        "neste intervalo de tempo.",
                "var_mun":     pop_mun,
                "var_nac":     pop_nac,
                "pill_bg":     colors.HexColor("#DCEAF7"),   # azul claro pastel
                "pill_text":   colors.HexColor("#1B3A6B"),   # azul escuro
                "comp_tpl":    "Enquanto o crescimento populacional médio dos municípios foi de ",
            },
        ]

        body_fs = 11
        comp_fs = 10
        pill_fs = 10.5
        icone_sz = 26       # diâmetro do círculo do ícone
        text_x   = x + icone_sz + 12

        # Pílula cinza pra valores indisponíveis (município sem dado em 2000).
        PILL_ND_BG   = colors.HexColor("#ECEAE0")
        PILL_ND_TEXT = colors.HexColor("#6E6B5E")

        for bl in blocos:
            var_mun_ok = bl["var_mun"] is not None
            var_nac_ok = bl["var_nac"] is not None
            sinal_m = "+" if var_mun_ok and bl["var_mun"] >= 0 else ""
            sinal_n = "+" if var_nac_ok and bl["var_nac"] >= 0 else ""

            # Ícone circular azul à esquerda (centro alinhado à 1ª linha)
            bl["icone"](c, x + icone_sz/2, y + 2, size=icone_sz)

            # Frase principal: "A <destaque> <verbo>  [pílula]  <tail>"
            cur = text_x
            c.setFillColor(INK)
            c.setFont(F(FONT_TEXTO), body_fs)
            c.drawString(cur, y, "A ")
            cur += c.stringWidth("A ", F(FONT_TEXTO), body_fs)
            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_TEXTO_BOLD), body_fs)
            c.drawString(cur, y, bl["destaque"])
            cur += c.stringWidth(bl["destaque"], F(FONT_TEXTO_BOLD), body_fs)
            c.setFillColor(INK)
            c.setFont(F(FONT_TEXTO), body_fs)
            verbo_str = f" {bl['verbo']} "
            c.drawString(cur, y, verbo_str)
            cur += c.stringWidth(verbo_str, F(FONT_TEXTO), body_fs)

            # Pílula município — cinza com "n/d" se não houver dado de 2000.
            if var_mun_ok:
                var_str   = f"{sinal_m}{_br(bl['var_mun'])}%"
                pill_bg   = bl["pill_bg"]
                pill_text = bl["pill_text"]
            else:
                var_str   = "n/d"
                pill_bg   = PILL_ND_BG
                pill_text = PILL_ND_TEXT
            pill_w = c.stringWidth(var_str, F(FONT_TEXTO_BOLD), pill_fs) + 16
            pill_h = 18
            c.setFillColor(pill_bg)
            c.roundRect(cur, y - 4, pill_w, pill_h, pill_h/2, fill=1, stroke=0)
            c.setFillColor(pill_text)
            c.setFont(F(FONT_TEXTO_BOLD), pill_fs)
            c.drawCentredString(cur + pill_w/2, y + 1, var_str)
            cur += pill_w + 6

            c.setFillColor(INK)
            c.setFont(F(FONT_TEXTO), body_fs)
            c.drawString(cur, y, bl["tail"])

            y -= 18

            # Comparativo (média nacional em negrito)
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), comp_fs)
            c.drawString(text_x, y, bl["comp_tpl"])
            wp = c.stringWidth(bl["comp_tpl"], F(FONT_TEXTO), comp_fs)
            media_str = f"{sinal_n}{_br(bl['var_nac'])}%" if var_nac_ok else "n/d"
            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_TEXTO_BOLD), comp_fs + 0.5)
            c.drawString(text_x + wp, y, media_str)
            wm = c.stringWidth(media_str, F(FONT_TEXTO_BOLD), comp_fs + 0.5)
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), comp_fs)
            c.drawString(text_x + wp + wm, y, ".")
            y -= 14

            # Gap explícito (sugestão 2): "Município cresceu X× menos/mais"
            # Só faz sentido com sinais iguais, magnitudes positivas e ambos os dados disponíveis.
            if var_mun_ok and var_nac_ok and (bl["var_mun"] * bl["var_nac"]) > 0 and abs(bl["var_mun"]) > 0.5 and abs(bl["var_nac"]) > 0.5:
                fator = bl["var_nac"] / bl["var_mun"]
                if abs(fator) >= 1.5:   # só destaca quando o gap é relevante
                    direcao = "menos" if abs(fator) > 1 else "mais"
                    fator_disp = fator if abs(fator) > 1 else 1 / fator
                    gap_str = f"({self.nome} cresceu {_br(abs(fator_disp), 1)}× {direcao} que a média.)"
                    c.setFillColor(cor_verbo_gap(fator))
                    c.setFont(F(FONT_TEXTO_SEMIBOLD), comp_fs)
                    c.drawString(text_x, y, gap_str)
                    y -= 14

            y -= 10   # respiro entre blocos

        # Evolução percentil (estilo landing) — altura ajustada para não
        # sobrepor o footer. Limita ao máximo de espaço útil acima da SAFE_BOTTOM.
        card_h = min(270, y - SAFE_BOTTOM - 4)
        self._draw_evolucao_percentil(c, x, y - card_h, CONTENT_W, card_h,
                                       h2000, h2024, self.nome)

    def _draw_evolucao_indisponivel(self, c, x, y, w, h):
        """
        Card de fallback quando o município não tem série histórica de 2000.

        Preenche o espaço com uma explicação em vez de deixar um buraco branco:
        o leitor precisa saber que o dado falta, não achar que houve erro de
        diagramação. O card externo já foi desenhado pelo chamador.
        """
        cx = x + w / 2
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 10)
        c.drawCentredString(cx, y + h / 2 + 6, "Série histórica indisponível")
        c.setFont(F(FONT_TEXTO), 8.5)
        c.drawCentredString(
            cx, y + h / 2 - 8,
            f"Este município não possui receita declarada em {ANO_BASE}."
        )
        c.drawCentredString(
            cx, y + h / 2 - 20,
            "A comparação de posição no ranking não pôde ser calculada."
        )

    # ─── Ícones circulares (Síntese Fiscal — estilo landing) ────────────────

    def _icone_receita_circ(self, c, cx, cy, size=26):
        """Círculo azul-claro com pictograma de cofrinho/cifrão (Receita)."""
        r = size / 2
        c.setFillColor(colors.HexColor("#DCEAF7"))
        c.circle(cx, cy, r, fill=1, stroke=0)
        # Cifrão azul escuro no centro
        c.setFillColor(colors.HexColor("#1B3A6B"))
        c.setFont(F(FONT_NUM_BOLD), size * 0.62)
        c.drawCentredString(cx, cy - size * 0.18, "$")

    def _icone_populacao_circ(self, c, cx, cy, size=26):
        """Círculo azul-claro com pictograma de 2 pessoas (População)."""
        r = size / 2
        c.setFillColor(colors.HexColor("#DCEAF7"))
        c.circle(cx, cy, r, fill=1, stroke=0)
        # 2 silhuetas estilizadas em azul escuro (cabeças + ombros)
        cor = colors.HexColor("#1B3A6B")
        c.setFillColor(cor)
        c.setStrokeColor(cor)
        c.setLineWidth(size * 0.06)
        rh = size * 0.10
        # Cabeças
        c.circle(cx - size*0.13, cy + size*0.10, rh,         fill=1, stroke=0)
        c.circle(cx + size*0.13, cy + size*0.06, rh * 1.05,  fill=1, stroke=0)
        # Ombros (arcos)
        c.setLineWidth(size * 0.16)
        c.line(cx - size*0.24, cy - size*0.10, cx - size*0.02, cy - size*0.10)
        c.line(cx + size*0.02, cy - size*0.14, cx + size*0.26, cy - size*0.14)
        c.setLineWidth(0.6)

    def _draw_evolucao_percentil(self, c, x: float, y: float, w: float, h: float,
                                  h2000: dict, h2024: dict, nome: str):
        """Evolução do ranking — visual replicando a landing IFEM:
        área superior com 2 bolinhas em alturas diferentes (eixo Y = percentil)
        ligadas por linha tracejada; card inferior em creme com a frase
        descritiva (filete colorido pelo verbo CAIU/SUBIU); barra gradiente
        horizontal com markers de cada ano.
        """
        # Card externo branco com borda sutil
        c.setFillColor(WHITE)
        c.roundRect(x, y, w, h, 6, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.roundRect(x, y, w, h, 6, fill=0, stroke=1)

        # Dados base. A série de 2000 cobre menos municípios que a atual
        # (5.305 contra 5.440): quem não declarou receita naquele ano não tem
        # ranking histórico. Sem esta guarda o folheto inteiro estourava com
        # TypeError, derrubando 14 páginas válidas por causa de um card.
        rk2000 = (h2000 or {}).get("ranking_nacional")
        rk2024 = (h2024 or {}).get("ranking_nacional")
        if not rk2000 or not rk2024:
            self._draw_evolucao_indisponivel(c, x, y, w, h)
            return

        pos2000 = rk2000["posicao"]
        tot2000 = rk2000["total"]
        pos2024 = rk2024["posicao"]
        tot2024 = rk2024["total"]
        cor2000 = cor_por_quintil(h2000["quintil"])
        cor2024 = cor_por_quintil(h2024["quintil"])
        tot_max = max(tot2000, tot2024)

        delta_pos = pos2024 - pos2000
        if delta_pos > 0:
            verbo = "CAIU"; cor_verbo = FNP_Q1
        elif delta_pos < 0:
            verbo = "SUBIU"; cor_verbo = FNP_Q5
        else:
            verbo = "MANTEVE-SE"; cor_verbo = MUTED

        def _br_int(v): return f"{v:,}".replace(",", ".")

        # ── 1. Área gráfica superior (bolinhas + linha) ────────────────────
        # Layout balanceado: bolinhas no terço superior, frase no meio, barra
        # no terço inferior — tudo centralizado verticalmente no card.
        graf_top    = y + h - 44      # mais espaço acima das bolinhas
        graf_bottom = y + 160         # piso do gráfico mais alto
        graf_h      = graf_top - graf_bottom

        r = 24
        x_2000 = x + 100
        x_2024 = x + w - 100

        frac2000 = max(0.08, min(0.92, (tot2000 - pos2000) / tot2000)) if tot2000 else 0.5
        frac2024 = max(0.08, min(0.92, (tot2024 - pos2024) / tot2024)) if tot2024 else 0.5
        y_circ_2000 = graf_bottom + frac2000 * graf_h
        y_circ_2024 = graf_bottom + frac2024 * graf_h

        # Linhas guia horizontais sutis
        c.setStrokeColor(colors.HexColor("#EEEAE0"))
        c.setLineWidth(0.4)
        for frac in (0.0, 0.33, 0.66, 1.0):
            yy = graf_bottom + frac * graf_h
            c.line(x + 50, yy, x + w - 50, yy)

        # Linha tracejada conectando as duas bolinhas
        c.setStrokeColor(colors.HexColor("#B8C2CC"))
        c.setLineWidth(0.8)
        c.setDash(4, 3)
        c.line(x_2000, y_circ_2000, x_2024, y_circ_2024)
        c.setDash()

        # Bolinhas com label "ANO" acima em fonte SemiBold
        for ano, pos, cx, cy, cor in [
            ("2000", pos2000, x_2000, y_circ_2000, cor2000),
            (str(ANO_REF), pos2024, x_2024, y_circ_2024, cor2024),
        ]:
            # Label ano acima
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO_SEMIBOLD), 9)
            c.drawCentredString(cx, cy + r + 8, ano)
            # Sombra (offset)
            c.setFillColor(colors.HexColor("#D9D2C3"))
            c.circle(cx + 1.2, cy - 1.2, r, fill=1, stroke=0)
            # Bolinha colorida
            c.setFillColor(cor)
            c.circle(cx, cy, r, fill=1, stroke=0)
            # Posição em branco no centro
            c.setFillColor(WHITE)
            c.setFont(F(FONT_NUM_BOLD), 15)
            c.drawCentredString(cx, cy - 5, f"{pos:,}º".replace(",", "."))

        # ── 2. Sub-card creme com a frase descritiva (filete colorido) ─────
        # Texto colorido por segmento. Se não couber em 1 linha (cidade com
        # nome longo, números de 4 dígitos), quebra automaticamente em 2.
        parts = [
            ("Em 2000, ",     INK,        F(FONT_TEXTO),  10),
            (nome,            BLUE_DARK,  F(FONT_TEXTO_SEMIBOLD), 10),
            (" estava no ",   INK,        F(FONT_TEXTO),  10),
            (f"{_br_int(pos2000)}º", BLUE_DARK, F(FONT_TEXTO_SEMIBOLD), 10),
            (f" lugar de {_br_int(tot2000)} e ", INK, F(FONT_TEXTO), 10),
            (verbo,           cor_verbo,  F(FONT_TEXTO_SEMIBOLD), 10.5),
            (" para a posição ", INK,     F(FONT_TEXTO),  10),
            (f"{_br_int(pos2024)}º", cor_verbo, F(FONT_TEXTO_SEMIBOLD), 10),
            (f" de {_br_int(tot2024)} no ano de {ANO_REF}, em termos de receita por habitante.", INK, F(FONT_TEXTO), 10),
        ]
        sub_x = x + 14
        sub_w = w - 28
        inner_w = sub_w - 32
        linhas = self._quebrar_parts(c, parts, inner_w)
        line_h = 14
        sub_h = max(36, 12 + len(linhas) * line_h)
        sub_y = y + 94
        c.setFillColor(CREAM)
        c.roundRect(sub_x, sub_y, sub_w, sub_h, 6, fill=1, stroke=0)
        c.setFillColor(cor_verbo)
        c.rect(sub_x, sub_y, 4, sub_h, fill=1, stroke=0)

        # Centraliza verticalmente o bloco de texto dentro do sub-card.
        bloc_h = len(linhas) * line_h
        top_text_y = sub_y + sub_h - (sub_h - bloc_h)/2 - 11
        for li, linha in enumerate(linhas):
            total_lw = sum(c.stringWidth(t, fnt, fs) for t, _, fnt, fs in linha)
            cur_x = sub_x + (sub_w - total_lw) / 2
            line_y = top_text_y - li * line_h
            for t, cor, font, fs in linha:
                c.setFillColor(cor)
                c.setFont(font, fs)
                c.drawString(cur_x, line_y, t)
                cur_x += c.stringWidth(t, font, fs)

        # ── 3. Barra gradiente horizontal contínua (estilo landing) ────────
        # Em vez de 5 retângulos chapados, desenhamos um gradiente suave
        # interpolando entre os 5 quintis FNP. Marker = pequeno chevron cinza.
        bar_y = y + 42
        bar_h = 8
        bar_x = x + 50
        bar_w = w - 100
        self._draw_gradient_bar(c, bar_x, bar_y, bar_w, bar_h)

        # Labels "0" e total alinhados verticalmente ao centro da barra
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 9)
        c.drawRightString(bar_x - 8, bar_y + 1, "0")
        c.drawString(bar_x + bar_w + 8, bar_y + 1, _br_int(tot_max))

        # Markers: pequena seta cinza sutil + label "POS (ANO)" embaixo
        marker_info = []
        for ano, pos, tot, cor in [("2000", pos2000, tot2000, cor2000),
                                    (str(ANO_REF), pos2024, tot2024, cor2024)]:
            frac = max(0.0, min(1.0, (tot - pos) / tot)) if tot else 0
            mx = bar_x + frac * bar_w
            marker_info.append((ano, pos, cor, mx))

        marker_info.sort(key=lambda mi: mi[3])

        # Quando os dois marcadores estão muito próximos no eixo X, o layout
        # horizontal "POS (ANO)" sobrepõe os labels. Em vez de empilhar ambos
        # do mesmo lado (que continua sobrepondo se a distância for ~zero),
        # separamos verticalmente: o 1º marker vai ACIMA da barra, o 2º ABAIXO.
        # Pra estimar largura do label "POS (ANO)" usamos uma medição rápida.
        c.setFont(F(FONT_NUM_BOLD), 11.5)
        largura_max_label = max(
            c.stringWidth(f"{m[1]:,}º (ANO)".replace(",", "."), F(FONT_NUM_BOLD), 11.5)
            for m in marker_info
        )
        # Se a distância entre os centros for menor que a metade da soma das
        # larguras dos dois labels (+ folga), eles colidem se ficarem do mesmo lado.
        sobrepoem = abs(marker_info[0][3] - marker_info[1][3]) < (largura_max_label + 12)

        for i, (ano, pos, cor, mx) in enumerate(marker_info):
            pos_str = f"{pos:,}º".replace(",", ".")
            ano_str = f"({ano})"

            # Quando colidem: 1º marker (mais à esquerda) embaixo, 2º em cima.
            # Quando não colidem: ambos embaixo, como antes (layout padrão).
            label_acima = sobrepoem and i == 1

            c.setFont(F(FONT_NUM_BOLD), 11.5)
            w_pos = c.stringWidth(pos_str, F(FONT_NUM_BOLD), 11.5)
            c.setFont(F(FONT_TEXTO), 9)
            w_ano = c.stringWidth(" " + ano_str, F(FONT_TEXTO), 9)
            total_w = w_pos + w_ano
            text_start_x = mx - total_w / 2

            if label_acima:
                label_y = bar_y + bar_h + 12   # acima da barra
                chev_top = bar_y + bar_h       # base do chevron grudado na barra
                chev_bot = label_y - 2         # ponta do chevron sob o label
                chev_aponta_baixo = False      # aponta pra CIMA aqui? Não, aponta da barra ao label
            else:
                label_y = bar_y - 14           # embaixo da barra (padrão)
                chev_top = label_y + 10        # topo do chevron logo acima do label
                chev_bot = bar_y               # ponta do chevron na barra
                chev_aponta_baixo = True

            c.setFillColor(cor)
            c.setFont(F(FONT_NUM_BOLD), 11.5)
            c.drawString(text_start_x, label_y, pos_str)
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), 9)
            c.drawString(text_start_x + w_pos, label_y + 1, " " + ano_str)

            # Chevron triangular ligando label e barra.
            c.setFillColor(BLUE_DARK)
            p = c.beginPath()
            if chev_aponta_baixo:
                # Triângulo apontando pra baixo: base em cima, ponta na barra.
                p.moveTo(mx,     chev_bot)
                p.lineTo(mx - 4, chev_top)
                p.lineTo(mx + 4, chev_top)
            else:
                # Triângulo apontando pra cima: base embaixo, ponta no label.
                p.moveTo(mx,     chev_bot)
                p.lineTo(mx - 4, chev_top)
                p.lineTo(mx + 4, chev_top)
            p.close()
            c.drawPath(p, fill=1, stroke=0)

    def _quebrar_parts(self, c, parts, max_w):
        """Quebra uma lista de segmentos (txt, cor, fonte, size) em múltiplas
        linhas, sem cortar palavras. Cada elemento de `parts` é tratado como
        bloco indivisível se for número/posição, ou quebrado por palavras
        para textos comuns."""
        linhas = [[]]
        cur_w = 0.0

        def width(t, fnt, fs):
            return c.stringWidth(t, fnt, fs)

        for txt, cor, fnt, fs in parts:
            # Divide o segmento por palavras (preservando os espaços iniciais)
            palavras = txt.split(" ")
            for j, pal in enumerate(palavras):
                p = pal if j == 0 else " " + pal
                if not p:
                    continue
                pw = width(p, fnt, fs)
                if cur_w + pw > max_w and linhas[-1]:
                    linhas.append([])
                    cur_w = 0.0
                    # remove o espaço inicial ao iniciar nova linha
                    p = pal
                    pw = width(p, fnt, fs)
                linhas[-1].append((p, cor, fnt, fs))
                cur_w += pw
        return linhas

    def _draw_gradient_bar(self, c, x, y, w, h):
        """Barra gradiente contínua: interpola entre os 5 quintis FNP por
        amostragem fina (1pt) em vez de 5 blocos chapados. Reproduz o visual
        suave da landing IFEM."""
        cores = [
            (0xA8, 0x1C, 0x21),  # FNP_Q1
            (0xE4, 0x73, 0x26),  # FNP_Q2
            (0xF4, 0xD0, 0x1D),  # FNP_Q3
            (0x6A, 0xC0, 0x74),  # FNP_Q4
            (0x1C, 0x91, 0x48),  # FNP_Q5
        ]
        # Cantos arredondados sutis (mascara com fundo)
        # 1) Desenha o gradient como série de tiras verticais finas
        n_seg = len(cores) - 1
        n_strips = int(w)
        for i in range(n_strips):
            t = i / (n_strips - 1) if n_strips > 1 else 0
            seg_i = min(int(t * n_seg), n_seg - 1)
            seg_t = (t * n_seg) - seg_i
            r0, g0, b0 = cores[seg_i]
            r1, g1, b1 = cores[seg_i + 1]
            r = int(r0 + (r1 - r0) * seg_t)
            g = int(g0 + (g1 - g0) * seg_t)
            b = int(b0 + (b1 - b0) * seg_t)
            c.setFillColorRGB(r/255, g/255, b/255)
            c.rect(x + i, y, 1.05, h, fill=1, stroke=0)
        # Arredonda as pontas da barra com pequenos pixels brancos
        c.setFillColor(WHITE)
        for cx, cy in [(x, y), (x, y + h - 1),
                       (x + w - 1, y), (x + w - 1, y + h - 1)]:
            c.rect(cx, cy, 1, 1, fill=1, stroke=0)

    # ─── 8. Variações 2000-2024: receita p/c e população vs média nacional ──

    def _pag_variacoes(self, c, n):
        d = self.d
        s = d["sintese_fiscal_2000_2024"]

        lado = self._moldura_pagina(c, n)
        x = self._content_x(lado)
        y = self._draw_cabecalho(c, x, SAFE_TOP, secao=f"Variações {PERIODO}")

        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 8)
        c.drawString(x, y, f"Comparativo de {self.nome}/{self.uf} com a média dos municípios brasileiros.")
        y -= 18

        # 2 cards (um abaixo do outro) com gráfico de barras
        card_h = 180
        gap = 14
        self._draw_card_variacao(
            c, x, y - card_h, CONTENT_W, card_h,
            titulo=f"VARIAÇÃO DA RECEITA POR HABITANTE ({PERIODO_HIFEN})",
            valor_mun=s["delta_receita_per_capita_pct"],
            valor_nac=s["media_nacional_delta_receita_per_capita_pct"],
            cor_mun=BLUE_DARK,
            label_mun=self.nome.upper(),
        )
        y -= card_h + gap

        self._draw_card_variacao(
            c, x, y - card_h, CONTENT_W, card_h,
            titulo=f"VARIAÇÃO DA POPULAÇÃO ({PERIODO_HIFEN})",
            valor_mun=s["delta_populacao_pct"],
            valor_nac=s["media_nacional_delta_populacao_pct"],
            cor_mun=YELLOW_DARK,
            label_mun=self.nome.upper(),
        )

    def _draw_card_variacao(self, c, x, y, w, h, titulo, valor_mun, valor_nac,
                             cor_mun, label_mun):
        """Card branco com gráfico de barras Município vs Média Nacional.
        Réplica do estilo da landing IFEM (eixo Y % com grid, 2 barras lado a lado)."""
        c.setFillColor(WHITE)
        c.roundRect(x, y, w, h, 4, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.roundRect(x, y, w, h, 4, fill=0, stroke=1)

        # Header
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 7)
        c.drawString(x + 14, y + h - 16, titulo)

        # Sem dado do município (ex.: emancipações pós-2000) — mostra mensagem
        # no centro do card e pula o gráfico.
        if valor_mun is None or valor_nac is None:
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), 10.5)
            c.drawCentredString(x + w/2, y + h/2 + 6, "Sem dados de 2000 para este município")
            c.setFillColor(colors.HexColor("#A09D90"))
            c.setFont(F(FONT_TEXTO), 8.5)
            c.drawCentredString(x + w/2, y + h/2 - 8,
                                "(município emancipado ou sem registro fiscal naquele ano)")
            return

        # Área do gráfico
        chart_x = x + 50
        chart_y = y + 38
        chart_w = w - 70
        chart_h = h - 70

        # Eixo Y: determinar escala arredondando pro próximo múltiplo de 50
        max_val = max(abs(valor_mun), abs(valor_nac), 50)
        # Arredonda pra cima ao próximo múltiplo de 50
        y_max = ((int(max_val) // 50) + 1) * 50

        # Grid horizontal + labels do eixo Y
        c.setStrokeColor(colors.HexColor("#EEEAE0"))
        c.setLineWidth(0.4)
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 6.5)
        n_ticks = 6
        for i in range(n_ticks + 1):
            yy = chart_y + (i / n_ticks) * chart_h
            c.line(chart_x, yy, chart_x + chart_w, yy)
            label = f"{int(i / n_ticks * y_max)}%"
            c.drawRightString(chart_x - 4, yy - 2, label)

        # 2 barras: município (cor_mun) e nacional (gray)
        bar_w = 56
        gap_x = chart_w / 2
        bar_x_mun = chart_x + chart_w * 0.30 - bar_w / 2
        bar_x_nac = chart_x + chart_w * 0.70 - bar_w / 2

        cor_nac = colors.HexColor("#6B7A85")

        for bar_x, val, cor, lbl in [
            (bar_x_mun, valor_mun, cor_mun, label_mun),
            (bar_x_nac, valor_nac, cor_nac, "MÉDIA DOS MUNICÍPIOS (NACIONAL)"),
        ]:
            bar_h = (val / y_max) * chart_h if val > 0 else 0
            c.setFillColor(cor)
            c.rect(bar_x, chart_y, bar_w, bar_h, fill=1, stroke=0)

            # Label do valor acima da barra
            sinal = "+" if val >= 0 else ""
            val_str = f"{sinal}{_br(val)}%"
            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_NUM_BOLD), 12)
            c.drawCentredString(bar_x + bar_w / 2, chart_y + bar_h + 4, val_str)

        # Legenda no rodapé
        leg_y = y + 14
        # Marcador município
        c.setFillColor(cor_mun)
        c.rect(x + 14, leg_y, 8, 8, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(F(FONT_TEXTO), 7.5)
        c.drawString(x + 26, leg_y + 1, label_mun)
        w_label_mun = c.stringWidth(label_mun, F(FONT_TEXTO), 7.5)
        # Marcador média
        leg_x2 = x + 26 + w_label_mun + 16
        c.setFillColor(cor_nac)
        c.rect(leg_x2, leg_y, 8, 8, fill=1, stroke=0)
        c.setFillColor(INK)
        c.drawString(leg_x2 + 12, leg_y + 1, "MÉDIA DOS MUNICÍPIOS (NACIONAL)")

    # ─── 9. Metodologia ─────────────────────────────────────────────────────

    def _pag_metodologia(self, c, n):
        m = self.d.get("_metodologia") or {}
        lado = self._moldura_pagina(c, n)
        x = self._content_x(lado)
        y = self._draw_cabecalho(c, x, SAFE_TOP,
                                  secao="Metodologia do IFEM")

        # Layout em 2 colunas: texto à ESQUERDA (45%), infográfico à DIREITA (52%).
        # A imagem cresce o quanto puder verticalmente; o texto usa fontes
        # maiores (resumo 9pt, tópicos 8.5pt) para legibilidade.
        col_text_w = CONTENT_W * 0.45
        col_img_w  = CONTENT_W * 0.52
        gap_x      = CONTENT_W * 0.03

        # ── Coluna esquerda: resumo + tópicos numerados ─────────────────
        text_x = x
        ty = y
        if m.get("resumo"):
            ty = draw_body(c, m["resumo"], text_x, ty, col_text_w, size=9)
            ty -= 14

        topicos = m.get("topicos") or []
        for i, t in enumerate(topicos):
            if ty < 80:
                break
            c.setFillColor(YELLOW_DARK)
            c.setFont(F(FONT_NUM_BOLD), 22)
            c.drawString(text_x, ty - 6, f"{i+1:02d}")
            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_NUM_BOLD), 11)
            c.drawString(text_x + 30, ty - 4, t.get("pergunta", "").upper())
            ty -= 18
            ty_after = draw_body(c, t.get("resposta", ""),
                                 text_x + 30, ty, col_text_w - 30, size=8.5)
            ty = ty_after - 8
            c.setStrokeColor(RULE)
            c.setLineWidth(0.4)
            c.line(text_x, ty, text_x + col_text_w, ty)
            ty -= 10

        # ── Coluna direita: infográfico GRANDE da metodologia ────────────
        img_path = ROOT_DIR / "data" / "ifem" / "metodologia.png"
        if img_path.exists():
            img_x_left = x + col_text_w + gap_x
            img_top    = self.H - 90
            img_bottom = 56
            avail_h    = img_top - img_bottom

            # metodologia.png é retrato (ratio h/w = 498/351 ≈ 1.42).
            ratio_hw = 498 / 351
            img_w_fit = col_img_w
            img_h_fit = col_img_w * ratio_hw
            if img_h_fit > avail_h:
                img_h_fit = avail_h
                img_w_fit = avail_h / ratio_hw

            # Alinha ao topo da coluna (não centraliza), para o título não ficar
            # solto e a imagem usar todo o espaço disponível.
            draw_x = img_x_left + (col_img_w - img_w_fit) / 2
            draw_y = img_top - img_h_fit

            c.drawImage(cached_image(img_path), draw_x, draw_y,
                        width=img_w_fit, height=img_h_fit,
                        preserveAspectRatio=True, mask="auto")

    # ─── 8. Página de convite (QR para ifem.onrender.com) ───────────────────

    def _pag_convite(self, c, n):
        lado = self._moldura_pagina(c, n, "Conheça o IFEM")
        x = self._content_x(lado)
        y = self.H - 55

        draw_eyebrow(c, "Próximo passo", x, y); y -= 26
        draw_titulo(c, "Conheça o IFEM\nno site", x, y, size=FS_TITLE_SECAO); y -= 56

        y = draw_body(
            c,
            "Acesse o painel completo com dados de 5.479 municípios "
            "brasileiros, comparações por porte e UF, e a metodologia detalhada.",
            x, y, CONTENT_W, size=FS_BODY,
        )

        # QR centralizado vertical e horizontalmente no espaço útil restante.
        url = self.d.get("url") or "https://ifem.onrender.com"
        try:
            import qrcode as qr_lib
            qr = qr_lib.QRCode(version=1, box_size=4, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color=QR_FILL_COLOR, back_color="white")
            buf = BytesIO()
            qr_img.save(buf, format="PNG")
            buf.seek(0)

            # Bloco completo = QR + URL + caption. Centralizado vertical no espaço útil.
            URL_GAP = 22
            CAP_GAP = 18
            block_h = QR_SIZE + URL_GAP + CAP_GAP
            avail_h = y - 60
            block_top = 60 + (avail_h + block_h) / 2

            qr_y = block_top - QR_SIZE
            qr_x = (self.W - QR_SIZE) / 2
            c.drawImage(ImageReader(buf), qr_x, qr_y,
                        width=QR_SIZE, height=QR_SIZE)

            # URL e legenda abaixo do QR
            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_NUM_BOLD), 14)
            c.drawCentredString(self.W / 2, qr_y - URL_GAP + 4, url)

            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), 8.5)
            c.drawCentredString(self.W / 2, qr_y - URL_GAP - CAP_GAP + 6,
                                "Aponte a câmera do celular para o QR Code.")
        except ImportError:
            pass

    # ─── 9. Última página ───────────────────────────────────────────────────

    def _pag_mapa_brasil(self, c, n):
        """Página do mapa IFEM (5.479 municípios coloridos por quintil).
        Header simplificado (sem nome do município); UF do município ao lado
        esquerdo (se disponível em data/ifem/regioes/{UF}.png) e legenda
        sobreposta no canto INFERIOR direito do mapa."""
        lado = self._moldura_pagina(c, n)
        x = self._content_x(lado)

        # Header enxuto: título da seção em azul + frase descritiva.
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 13)
        c.drawString(x, SAFE_TOP, "Os Municípios no IFEM")
        y = SAFE_TOP - 22

        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 10)
        c.drawString(x, y,
                     "Cada ponto colorido representa um município brasileiro "
                     "e sua posição no IFEM.")
        y -= 18

        # Área disponível para conteúdo gráfico.
        area_top    = y - 6
        area_bottom = SAFE_BOTTOM
        avail_h = area_top - area_bottom
        avail_w = CONTENT_W

        # Mapa do Brasil centralizado em toda a largura útil.
        # Reduzido a 90% da altura disponível para deixar respiro vertical e
        # garantir que a UF (canto inferior esquerdo) e a legenda (canto
        # inferior direito) caibam sobrepostas sem invadir a área central.
        mapa_path = ROOT_DIR / "data" / "ifem" / "mapa_IFEM.png"
        map_x = map_y = map_w = map_h = None
        if mapa_path.exists():
            ratio_wh = 749 / 766  # w/h do mapa_IFEM.png
            target_h = avail_h * 0.92
            map_h = target_h
            map_w = map_h * ratio_wh
            if map_w > avail_w:
                map_w = avail_w
                map_h = map_w / ratio_wh

            map_x = x + (avail_w - map_w) / 2
            map_y = area_bottom + (avail_h - map_h) / 2
            c.drawImage(cached_image(mapa_path), map_x, map_y,
                        width=map_w, height=map_h,
                        preserveAspectRatio=True, mask="auto")

        # UF do município no CANTO INFERIOR ESQUERDO (silhueta do estado),
        # envolta por um quadro branco com a sigla + nome completo no topo.
        # Só renderiza se houver PNG/JPEG correspondente em data/ifem/regioes/.
        uf_path = None
        for ext in (".png", ".jpeg", ".jpg"):
            cand = ROOT_DIR / "data" / "ifem" / "regioes" / f"{self.uf}{ext}"
            if cand.exists():
                uf_path = cand
                break
        if uf_path:
            from PIL import Image as _PILImg
            with _PILImg.open(uf_path) as _im:
                uf_ow, uf_oh = _im.size
            ratio_uf = uf_ow / uf_oh

            # Dimensões do quadro: largura fixa, altura calculada da imagem +
            # cabeçalho do título.
            box_w = avail_w * 0.32
            pad   = 6
            header_h = 18
            img_w_fit = box_w - 2 * pad
            img_h_fit = img_w_fit / ratio_uf
            box_h = header_h + img_h_fit + 2 * pad

            box_x = x
            box_y = area_bottom

            # Fundo branco + borda fina cinza.
            c.setFillColor(WHITE)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.6)
            c.roundRect(box_x, box_y, box_w, box_h, 4, fill=1, stroke=1)

            # Título "SP · São Paulo" centralizado no topo do quadro.
            uf_nome = _UF_NOMES.get(self.uf, self.uf)
            titulo = f"{self.uf} · {uf_nome}"
            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_TEXTO_SEMIBOLD), 9)
            c.drawCentredString(box_x + box_w / 2,
                                box_y + box_h - header_h + 4, titulo)

            # Silhueta do estado dentro do quadro.
            img_x = box_x + pad
            img_y = box_y + pad
            c.drawImage(cached_image(uf_path), img_x, img_y,
                        width=img_w_fit, height=img_h_fit,
                        preserveAspectRatio=True, mask="auto")

        # Legenda no CANTO INFERIOR DIREITO do mapa do Brasil.
        legenda_path = ROOT_DIR / "data" / "ifem" / "legenda_mapa.png"
        if legenda_path.exists() and map_x is not None:
            leg_orig_w, leg_orig_h = 188, 255
            leg_h = 120
            leg_w = leg_h * (leg_orig_w / leg_orig_h)
            leg_x = x + avail_w - leg_w
            leg_y = area_bottom
            c.drawImage(cached_image(legenda_path), leg_x, leg_y,
                        width=leg_w, height=leg_h,
                        preserveAspectRatio=True, mask="auto")

    def _pag_ultima(self, c, n):
        """Última página padrão FNP — verso do folheto (impressão fechada)."""
        url = self.d.get("url") or "https://ifem.onrender.com"
        draw_ultima_padrao(c, self.W, self.H, n,
                           url=url, seed=self._seed(),
                           lado=self._lado_pagina(n))

    # ─── 14. Risco climático: o tema e o panorama nacional ──────────────────

    def _pag_risco_panorama(self, c, n):
        pan = self.panorama_clima
        lado = self._moldura_pagina(c, n, "Risco Climático")
        x = self._content_x(lado)
        w = CONTENT_W

        y = SAFE_TOP
        draw_eyebrow(c, "AdaptaBrasil · MCTI", x, y)

        y -= 30
        draw_titulo(c, "Risco climático", x, y, size=FS_TITLE_SECAO)

        y -= 20
        # draw_body já devolve y um interlinhamento abaixo da última baseline;
        # somar outro respiro aqui abriria um buraco visível antes da faixa.
        y = draw_body(
            c,
            "O AdaptaBrasil mede a exposição de cada município brasileiro a 12 riscos "
            "climáticos, reunidos em 6 setores estratégicos. Cada indicador vai de 0 a 1: "
            "quanto mais alto, maior o risco.",
            x, y, w, size=FS_BODY_SMALL,
        )

        y = self._draw_kpis_risco(c, x, y - 2, w)

        # ─ Gráfico: distribuição por classe de risco × quintil do IFEM ─
        y -= 22
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 10)
        c.drawString(x, y, "Municípios por classe de risco e quintil do IFEM")

        y -= 15
        y = self._draw_legenda_risco(c, x, y, w)

        y -= 10
        y = self._draw_grafico_risco_quintis(c, x, y, w, 164, pan)

        y -= 14
        draw_caption(c, "Fonte: AdaptaBrasil (MCTI) e IFEM/FNP.", x, y)

        # ─ A leitura que o gráfico permite ─
        self._draw_conclusao_risco(c, x, y - 18, w, 52, pan)

    def _draw_kpis_risco(self, c, x, y_top, w, h: float = 50) -> float:
        """Três números do panorama em uma faixa creme. Retorna y abaixo."""
        pan = self.panorama_clima
        y_bot = y_top - h
        c.setFillColor(CREAM)
        c.roundRect(x, y_bot, w, h, CARD_RADIUS, fill=1, stroke=0)

        classes = {cl["nome"]: cl["total"] for cl in pan.get("classes", [])}
        expostos = classes.get("Muito alto", 0) + classes.get("Alto", 0)
        total = pan.get("total_municipios", 0) or 1

        itens = [
            (_br(pan.get("media_nacional", 0), 2), "de 1,00", "média nacional do índice"),
            (_fmt_int(expostos), f"({_br(expostos / total * 100, 1)}%)",
             "em risco alto ou muito alto"),
        ]

        cell_w = w / len(itens)
        for i, (valor, unidade, label) in enumerate(itens):
            cx = x + i * cell_w + 14
            if i:
                c.setStrokeColor(RULE)
                c.setLineWidth(0.6)
                c.line(x + i * cell_w, y_bot + 10, x + i * cell_w, y_top - 10)

            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_NUM_BOLD), 21)
            c.drawString(cx, y_bot + 20, valor)
            if unidade:
                c.setFillColor(MUTED)
                c.setFont(F(FONT_TEXTO), 8)
                c.drawString(cx + c.stringWidth(valor, F(FONT_NUM_BOLD), 21) + 4,
                             y_bot + 22, unidade)

            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), 7.5)
            c.drawString(cx, y_bot + 9, label)

        return y_bot

    def _draw_legenda_risco(self, c, x, y, w) -> float:
        """Legenda horizontal das 5 classes. Retorna y abaixo da linha."""
        cx = x
        for classe in CLASSES_RISCO:
            c.setFillColor(_cor_risco(classe))
            c.rect(cx, y - 1, 7, 7, fill=1, stroke=0)
            c.setFillColor(INK)
            c.setFont(F(FONT_TEXTO), 7.5)
            c.drawString(cx + 10, y, classe)
            cx += 10 + c.stringWidth(classe, F(FONT_TEXTO), 7.5) + 16
        return y - 6

    def _draw_grafico_risco_quintis(self, c, x, y_top, w, h, pan) -> float:
        """Barras empilhadas: um grupo por quintil do IFEM, empilhado por classe
        de risco (pior embaixo). Reproduz o gráfico do painel IFEM.

        Rótulo de segmento fino (< ~8pt) não cabe dentro da barra. Ele sai ao
        LADO, na altura do próprio segmento e ligado por um traço-guia — nunca
        acima da barra: um "44" de risco muito alto (que mora embaixo) flutuando
        no topo faz o leitor atribuí-lo à classe errada.
        """
        grupos = pan.get("por_quintil_ifem", [])
        if not grupos:
            return y_top - h

        EIXO_MAX = 1200          # folga sobre os 1.088 de cada quintil
        PASSO = 300
        LABEL_W = 26             # coluna dos rótulos do eixo Y
        AXIS_H = 16              # faixa dos rótulos "1º quintil" etc.
        MIN_LABEL_H = 8.5        # altura mínima para caber número dentro

        plot_x = x + LABEL_W
        plot_w = w - LABEL_W
        y_base = y_top - h + AXIS_H
        plot_h = h - AXIS_H - 10          # 10pt de respiro no topo

        def _py(valor):
            return y_base + plot_h * (valor / EIXO_MAX)

        # Grade horizontal + rótulos do eixo Y
        c.setLineWidth(0.5)
        for v in range(0, EIXO_MAX + 1, PASSO):
            gy = _py(v)
            c.setStrokeColor(RULE)
            c.line(plot_x, gy, plot_x + plot_w, gy)
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), 6.5)
            c.drawRightString(plot_x - 5, gy - 2, _fmt_int(v))

        slot = plot_w / len(grupos)
        bar_w = min(56, slot * 0.44)

        for i, g in enumerate(grupos):
            bx = plot_x + i * slot + (slot - bar_w) / 2
            cursor = y_base
            finos = []   # (classe, qtd, y do meio do segmento)

            for classe in CLASSES_RISCO:
                qtd = g["classes"].get(classe, 0)
                if not qtd:
                    continue
                seg_h = plot_h * (qtd / EIXO_MAX)
                c.setFillColor(_cor_risco(classe))
                c.rect(bx, cursor, bar_w, seg_h, fill=1, stroke=0)

                if seg_h >= MIN_LABEL_H:
                    c.setFillColor(WHITE if classe in ("Muito alto", "Muito baixo") else INK)
                    c.setFont(F(FONT_NUM_SEMIBOLD), 7.5)
                    c.drawCentredString(bx + bar_w / 2, cursor + seg_h / 2 - 2.5, _fmt_int(qtd))
                else:
                    finos.append((classe, qtd, cursor + seg_h / 2))
                cursor += seg_h

            # Rótulos externos. O último grupo joga para a esquerda: à direita
            # dele só existe a margem da página.
            para_esquerda = i == len(grupos) - 1
            ocupados = []
            for classe, qtd, ym in finos:
                while any(abs(ym - u) < 8 for u in ocupados):
                    ym += 8
                ocupados.append(ym)
                c.setStrokeColor(_cor_risco(classe))
                c.setLineWidth(0.7)
                c.setFillColor(_cor_risco(classe))
                c.setFont(F(FONT_NUM_SEMIBOLD), 6.5)
                if para_esquerda:
                    c.line(bx - 4, ym, bx, ym)
                    c.drawRightString(bx - 6, ym - 2, _fmt_int(qtd))
                else:
                    c.line(bx + bar_w, ym, bx + bar_w + 4, ym)
                    c.drawString(bx + bar_w + 6, ym - 2, _fmt_int(qtd))

            c.setFillColor(BLUE_DARK)
            c.setFont(F(FONT_TEXTO_SEMIBOLD), 7.5)
            c.drawCentredString(bx + bar_w / 2, y_base - 11, f"{g['quintil']}º quintil")

        return y_top - h

    def _draw_conclusao_risco(self, c, x, y_top, w, h, pan) -> float:
        """Caixa azul com a leitura do gráfico. O número é calculado, nunca
        escrito à mão: se a base mudar, o texto acompanha."""
        grupos = {g["quintil"]: g for g in pan.get("por_quintil_ifem", [])}
        if not grupos:
            return y_top - h

        def _pct_expostos(q):
            g = grupos.get(q, {})
            tot = g.get("total") or 1
            alto = g["classes"].get("Muito alto", 0) + g["classes"].get("Alto", 0)
            return alto / tot * 100

        y_bot = y_top - h
        c.setFillColor(BLUE)
        c.roundRect(x, y_bot, w, h, CARD_RADIUS, fill=1, stroke=0)
        c.setFillColor(YELLOW)
        c.rect(x, y_bot, 4, h, fill=1, stroke=0)

        c.setFillColor(YELLOW)
        c.setFont(F(FONT_NUM_SEMIBOLD), 8.5)
        c.drawString(x + 14, y_top - 14, "MENOS RECEITA, MAIS RISCO")

        texto = (
            f"No 1º quintil do IFEM, que reúne os municípios com menos receita "
            f"por habitante, {_br(_pct_expostos(1), 1)}% estão em risco climático "
            f"alto ou muito alto. "
            f"No 5º quintil, {_br(_pct_expostos(5), 1)}%."
        )
        c.setFillColor(WHITE)
        c.setFont(F(FONT_TEXTO), 8.5)
        for i, linha in enumerate(simpleSplit(texto, F(FONT_TEXTO), 8.5, w - 28)):
            c.drawString(x + 14, y_top - 27 - i * 11, linha)
        return y_bot

    def _cabecalho(self, c, x, secao):
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 12)
        c.drawString(x, SAFE_TOP, secao)
        nome_uf = f"{self.nome} - {self.uf}"
        fs = 26
        while c.stringWidth(nome_uf, F(FONT_NUM_BOLD), fs) > CONTENT_W and fs > 16:
            fs -= 1
        c.setFont(F(FONT_NUM_BOLD), fs)
        c.drawString(x, SAFE_TOP - 26, nome_uf)
        return SAFE_TOP - 44

    def _head_tabela(self, c, x, y_top, rot_esq, unidade, col_pct=True):
        """Cabecalho de duas camadas.

        "MÉDIA" sai uma vez so, como rotulo que cobre as duas colunas, com MA e
        BRASIL embaixo. Repetir a palavra em cada coluna a fazia aparecer tres
        vezes na pagina de risco, junto com "MÉDIA GERAL DE RISCO" da faixa.
        De quebra, a unidade tambem passa a ser escrita uma vez para as duas.
        """
        x_uf = x + COL_ROTULO + COL_MUNI
        x_br = x_uf + COL_CAIXA
        c.setFillColor(BLUE)
        c.rect(x, y_top - HEAD_H, CONTENT_W, HEAD_H, fill=1, stroke=0)

        c.setFillColor(WHITE)
        c.setFont(F(FONT_NUM_SEMIBOLD), 7.2)
        c.drawString(x + 8, y_top - 8.5, rot_esq)

        if col_pct:
            # O percentil ganha coluna com nome. Solto ao lado do valor em R$
            # viravam dois numeros sem hierarquia; nomeado, ele e a resposta a
            # "supera quanto?" e o R$ responde "quanto entra?".
            c.drawString(x + COL_ROTULO + 8, y_top - 8.5, "SUPERA")
            c.setFillColor(BLUE_LIGHT)
            c.setFont(F(FONT_TEXTO), 5.6)
            c.drawString(x + COL_ROTULO + 8, y_top - 16, "% dos municípios do país")
            c.setFillColor(WHITE)
            c.setFont(F(FONT_NUM_SEMIBOLD), 7.2)
            c.drawRightString(x + COL_ROTULO + COL_MUNI - 8, y_top - 8.5, "MUNICÍPIO")
            c.setFillColor(BLUE_LIGHT)
            c.setFont(F(FONT_TEXTO), 5.6)
            c.drawRightString(x + COL_ROTULO + COL_MUNI - 8, y_top - 16, unidade)
        else:
            c.drawString(x + COL_ROTULO + 8, y_top - 8.5, "MUNICÍPIO")
            c.setFillColor(BLUE_LIGHT)
            c.setFont(F(FONT_TEXTO), 5.6)
            c.drawString(x + COL_ROTULO + 8, y_top - 16, unidade)

        # Rotulo unico cobrindo as duas colunas de media, com fio de amarracao.
        centro = x_uf + COL_CAIXA
        c.setFillColor(WHITE)
        c.setFont(F(FONT_NUM_SEMIBOLD), 7.2)
        c.drawCentredString(centro, y_top - 8.5, f"MÉDIA · {unidade}")
        c.setFillColor(BLUE_LIGHT)
        c.rect(x_uf + 8, y_top - 11.5, COL_CAIXA * 2 - 16, 0.5, fill=1, stroke=0)

        c.setFillColor(WHITE)
        c.setFont(F(FONT_NUM_SEMIBOLD), 7.2)
        c.drawCentredString(x_uf + COL_CAIXA / 2, y_top - 17, self.uf.upper())
        c.drawCentredString(x_br + COL_CAIXA / 2, y_top - 17, "BRASIL")
        return y_top - HEAD_H

    def _fechar_tabela(self, c, x, y, lado):
        """Fio de fechamento + arte do alfabeto no espaco que sobrar.

        Uma pagina de continuacao pode terminar com 3 linhas e meia pagina em
        branco. `_decorar_rodape` ja e o mecanismo da casa para isso e escolhe
        sozinho entre as artes conforme a altura disponivel — abaixo de 20pt de
        folga ele nao desenha nada, entao as paginas cheias seguem intactas.
        """
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(x, y, x + CONTENT_W, y)
        self._decorar_rodape(c, lado, y - 10, seed_offset=0)

    def _caixas(self, c, x, y_top, row_h, val_uf, val_br, em_mil, fs, altura,
                cifrao=True):
        x_uf = x + COL_ROTULO + COL_MUNI
        x_br = x_uf + COL_CAIXA
        for cx, cor_col, val in ((x_uf, BLUE_MID, val_uf), (x_br, BLUE_DARK, val_br)):
            qx = cx + (COL_CAIXA - CAIXA_W) / 2
            qy = y_top - (row_h + altura) / 2
            c.setFillColor(WHITE)
            c.setStrokeColor(cor_col)
            c.setLineWidth(0.8)
            c.roundRect(qx, qy, CAIXA_W, altura, 2, fill=1, stroke=1)
            c.setFillColor(cor_col)
            c.setFont(F(FONT_NUM_SEMIBOLD), fs)
            c.drawCentredString(qx + CAIXA_W / 2, qy + altura / 2 - 2.5,
                                _reais(val, em_mil, cifrao))

    # ─── 7. Receita: niveis 1 e 2 ───────────────────────────────────────────

    def _linhas_n12(self):
        d = self.d
        n1 = {r["field"]: r for r in d["estrutura_receita_resumo"]}
        parent = {n["field"]: n.get("parent_field")
                  for n in (d.get("hierarquia_receitas") or {}).get("nivel_2", [])}
        filhos = {}
        for n2 in d["estrutura_receita_detalhada"]["nivel_2_categorias"]:
            if n2["valor_absoluto"] > 0:
                filhos.setdefault(parent.get(n2.get("field")), []).append(n2)

        nac, uf = self._medias_nacionais_por_field(), self._medias_estaduais_por_field()
        out = []
        for pai in sorted(n1.values(), key=lambda r: -r["valor_absoluto"]):
            f = pai["field"]
            out.append((0, pai["rubrica"], pai["per_capita"],
                        pai.get("supera_pct_nacional"), uf.get(f), nac.get(f)))
            irmaos = sorted(filhos.get(f, []), key=lambda r: -r["valor_absoluto"])
            # Filho unico com o mesmo valor do pai e a mesma linha duas vezes:
            # "Contribuicoes R$ 253" seguido de "Contribuicoes Sociais R$ 253".
            # Some so quando os valores batem — filho unico com valor diferente
            # existiria por arredondamento e a) seria noticia, b) precisa sair.
            if len(irmaos) == 1 and abs(irmaos[0]["per_capita"] - pai["per_capita"]) < 0.01:
                continue
            for n2 in irmaos:
                g = n2["field"]
                out.append((1, n2["rubrica"], n2["per_capita"],
                            n2.get("supera_pct_nacional"), uf.get(g), nac.get(g)))
        return out

    def _pag_receita_n12(self, c, n):
        lado = self._moldura_pagina(c, n, f"{self.nome} · {self.uf}")
        x = self._content_x(lado)
        y = self._cabecalho(c, x, "Estrutura da Receita")
        y = self._faixa_receita(c, x, y, CONTENT_W)

        y -= 12
        draw_eyebrow(c, "De onde vem a receita", x, y)
        y -= 11
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 6.5)
        c.drawString(x, y, "A barra e o % mostram quanto dos municípios do país este "
                           "supera naquela rubrica: vermelho supera poucos, verde supera muitos.")

        y -= 10
        y = self._head_tabela(c, x, y, "RUBRICA", "por habitante")
        for i, linha in enumerate(self._linhas_n12()):
            if linha[0] == 0 and i > 0:
                y -= 4          # respiro entre as 4 rubricas principais
            y = self._linha_receita(c, x, y, linha)
        self._fechar_tabela(c, x, y, lado)

    def _linha_receita(self, c, x, y_top, linha) -> float:
        nivel, rubrica, per_capita, pct, m_uf, m_nac = linha
        row_h = 21.5 if nivel == 0 else 19.5
        y_bot = y_top - row_h
        cor = _cor_supera(pct)

        # Rubrica principal: fundo creme + fio azul no topo. Sem isso as 14
        # linhas viram um bloco unico e nao se ve onde comeca cada grupo.
        if nivel == 0:
            c.setFillColor(CREAM_DARK)
            c.rect(x, y_bot, CONTENT_W, row_h, fill=1, stroke=0)
            c.setFillColor(BLUE_DARK)
            c.rect(x, y_top - 1.2, CONTENT_W, 1.2, fill=1, stroke=0)
        else:
            c.setFillColor(WHITE)
            c.rect(x, y_bot, CONTENT_W, row_h, fill=1, stroke=0)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.4)
            c.line(x + 14, y_bot, x + CONTENT_W, y_bot)
        c.setFillColor(cor)
        c.rect(x, y_bot, 4 if nivel == 0 else 2, row_h, fill=1, stroke=0)

        tx = x + 10 + nivel * 12
        fonte = FONT_TEXTO_SEMIBOLD if nivel == 0 else FONT_TEXTO
        fs = 8.5 if nivel == 0 else 7.5
        while c.stringWidth(rubrica, F(fonte), fs) > COL_ROTULO - (tx - x) - 8 and fs > 6.0:
            fs -= 0.25
        c.setFillColor(BLUE_DARK if nivel == 0 else INK)
        c.setFont(F(fonte), fs)
        c.drawString(tx, y_top - 14, rubrica)

        em_mil = max(v for v in (per_capita, m_nac, m_uf) if v is not None) >= 1000
        self._barra_valor(c, x, y_top, row_h, pct, cor,
                          _reais(per_capita, em_mil),
                          12 if nivel == 0 else 10, 7 if nivel == 0 else 5)
        self._caixas(c, x, y_top, row_h, m_uf, m_nac, em_mil,
                     7.5 if nivel == 0 else 7, 17)
        return y_bot

    def _barra_valor(self, c, x, y_top, row_h, frac_pct, cor, texto, fs_num, bar_h):
        """Barra do percentil + o percentil escrito + o valor do municipio.

        O numero do percentil tem slot proprio, alinhado, em vez de flutuar na
        ponta da barra: assim a coluna toda se le de cima a baixo, e uma rubrica
        com 95% nao empurra o rotulo para dentro do valor em R$. Sem ele, a
        barra media o percentil e nao dizia qual — era a frase "supera X% dos
        municipios" dos cards antigos, perdida na virada para tabela.
        """
        pct_x = x + COL_ROTULO + 8
        bar_x = pct_x + PCT_W + GAP_BARRA
        bar_w = COL_MUNI - 8 - PCT_W - GAP_BARRA - VAL_W - 8
        bar_y = y_top - (row_h + bar_h) / 2
        meio = y_top - row_h / 2

        # Percentil colado a esquerda da barra e na cor dela: numero e desenho
        # sao a mesma medida, entao andam juntos. O R$ fica na outra ponta.
        if frac_pct is not None:
            c.setFillColor(cor)
            c.setFont(F(FONT_NUM_SEMIBOLD), 7.5)
            c.drawRightString(pct_x + PCT_W, meio - 2.6, f"{frac_pct}%")

        c.setFillColor(CREAM_DARK)
        c.rect(bar_x, bar_y, bar_w, bar_h, fill=1, stroke=0)
        if frac_pct is not None:
            # Traco minimo: um valor medido de 0 nao pode virar buraco branco.
            c.setFillColor(cor)
            c.rect(bar_x, bar_y, max(bar_w * (frac_pct / 100), 2.5), bar_h, fill=1, stroke=0)

        c.setFillColor(cor)
        c.setFont(F(FONT_NUM_BOLD), fs_num)
        c.drawRightString(x + COL_ROTULO + COL_MUNI - 8, meio - 3.5, texto)

    # ─── 8. Receita: nivel 3 ────────────────────────────────────────────────

    ALT_GRUPO_N3, ALT_LINHA_N3 = 13, 15.5

    def _blocos_n3(self):
        """Blocos do nivel 3 na ordem de leitura: faixa de grupo + suas linhas."""
        d = self.d
        n3 = [i for i in d["estrutura_receita_detalhada"]["nivel_3_rubricas"]
              if i.get("valor_absoluto", 0) > 0]
        parent = {i["field"]: i.get("parent_field")
                  for i in d["hierarquia_receitas"]["nivel_3"]}
        rotulo = {i["field"]: i["label"] for i in d["hierarquia_receitas"]["nivel_2"]}
        nac, uf = self._medias_nacionais_por_field(), self._medias_estaduais_por_field()

        grupos = {}
        for item in n3:
            grupos.setdefault(parent.get(item["field"]), []).append(item)

        blocos = []
        for pai, itens in grupos.items():
            blocos.append(("grupo", str(rotulo.get(pai, "")).upper()))
            for item in sorted(itens, key=lambda r: -r["valor_absoluto"]):
                f = item["field"]
                blocos.append(("linha", (item["rubrica"], item["per_capita"],
                                         item.get("supera_pct_nacional"),
                                         uf.get(f), nac.get(f))))
        return blocos

    def _paginas_n3(self):
        """Reparte os blocos em paginas que cabem de verdade.

        Acailandia tem 19 rubricas de nivel 3 e cabe em uma pagina; a base tem
        municipios com mais. Sem esta conta a tabela transbordava por baixo do
        rodape sem erro nenhum na saida — o pior tipo de falha num lote de 424.

        Uma faixa de grupo nunca fica orfa no pe da pagina: se nao houver espaco
        para ela e ao menos uma linha, o grupo inteiro vai para a proxima.
        """
        util_primeira = (SAFE_TOP - 44) - 21 - HEAD_H - SAFE_BOTTOM
        util_demais = SAFE_TOP - 21 - HEAD_H - SAFE_BOTTOM

        paginas, atual, resta = [], [], util_primeira
        blocos = self._blocos_n3()
        for i, (tipo, dado) in enumerate(blocos):
            alt = self.ALT_GRUPO_N3 if tipo == "grupo" else self.ALT_LINHA_N3
            if tipo == "grupo":
                alt += self.ALT_LINHA_N3          # grupo carrega a 1a linha junto
            if alt > resta and atual:
                paginas.append(atual)
                atual, resta = [], util_demais
            atual.append((tipo, dado))
            resta -= self.ALT_GRUPO_N3 if tipo == "grupo" else self.ALT_LINHA_N3
        if atual:
            paginas.append(atual)
        return paginas

    def _pag_receita_n3(self, c, n, blocos, primeira):
        lado = self._moldura_pagina(c, n, f"{self.nome} · {self.uf}")
        x = self._content_x(lado)

        if primeira:
            y = self._cabecalho(c, x, "Receita em detalhe")
            draw_eyebrow(c, "Cada rubrica por dentro", x, y)
            y -= 11
            c.setFillColor(MUTED)
            c.setFont(F(FONT_TEXTO), 6.5)
            c.drawString(x, y, "O terceiro nível da receita, agrupado pela rubrica de "
                               "origem. Mesma leitura da página anterior.")
            y -= 10
        else:
            y = SAFE_TOP
            draw_eyebrow(c, "Cada rubrica por dentro · continuação", x, y)
            y -= 21

        y = self._head_tabela(c, x, y, "RUBRICA DETALHADA", "por habitante")
        for tipo, dado in blocos:
            if tipo == "grupo":
                c.setFillColor(CREAM_DARK)
                c.rect(x, y - self.ALT_GRUPO_N3, CONTENT_W, self.ALT_GRUPO_N3,
                       fill=1, stroke=0)
                c.setFillColor(BLUE_DARK)
                c.rect(x, y - 1, CONTENT_W, 1, fill=1, stroke=0)
                c.setFont(F(FONT_NUM_SEMIBOLD), 7.2)
                c.drawString(x + 10, y - 9.5, dado)
                y -= self.ALT_GRUPO_N3
            else:
                y = self._linha_n3(c, x, y, *dado)

        self._fechar_tabela(c, x, y, lado)

    def _linha_n3(self, c, x, y_top, rubrica, per_capita, pct, m_uf, m_nac) -> float:
        row_h = 15.5
        y_bot = y_top - row_h
        cor = _cor_supera(pct)

        c.setFillColor(WHITE)
        c.rect(x, y_bot, CONTENT_W, row_h, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.line(x + 14, y_bot, x + CONTENT_W, y_bot)
        c.setFillColor(cor)
        c.rect(x, y_bot, 2, row_h, fill=1, stroke=0)

        fs = 7.5
        while c.stringWidth(rubrica, F(FONT_TEXTO), fs) > COL_ROTULO - 30 and fs > 5.8:
            fs -= 0.25
        c.setFillColor(INK)
        c.setFont(F(FONT_TEXTO), fs)
        c.drawString(x + 22, y_top - 11, rubrica)

        em_mil = max(v for v in (per_capita, m_nac, m_uf) if v is not None) >= 1000
        self._barra_valor(c, x, y_top, row_h, pct, cor,
                          _reais(per_capita, em_mil), 9, 4.5)
        self._caixas(c, x, y_top, row_h, m_uf, m_nac, em_mil, 6.5, 13)
        return y_bot

    # ─── 11. Risco climatico: tabela ────────────────────────────────────────

    def _pag_risco_municipio(self, c, n):
        lado = self._moldura_pagina(c, n, f"{self.nome} · {self.uf}")
        x = self._content_x(lado)
        y = self._cabecalho(c, x, "Risco Climático")
        y = self._faixa_risco(c, x, y, CONTENT_W)

        y -= 12
        draw_eyebrow(c, "As 12 notas do município", x, y)
        y -= 11
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 6.5)
        c.drawString(x, y, "Do maior para o menor risco. Todas as notas vão de 0 a 1: "
                           "quanto mais alto, maior o risco.")

        y -= 10
        y = self._head_tabela(c, x, y, "RISCO CLIMÁTICO", "nota de 0 a 1", col_pct=False)

        inds = sorted(self.risco_climatico.get("indicadores") or [],
                      key=lambda i: i.get("valor") or 0.0, reverse=True)
        for i, ind in enumerate(inds):
            y = self._linha_risco(c, x, y, i, ind)
        self._fechar_tabela(c, x, y, lado)

    def _linha_risco(self, c, x, y_top, i, ind) -> float:
        row_h = 24.5
        y_bot = y_top - row_h
        cor = _cor_risco(ind.get("classe"))

        c.setFillColor(WHITE if i % 2 == 0 else CREAM)
        c.rect(x, y_bot, CONTENT_W, row_h, fill=1, stroke=0)
        c.setFillColor(cor)
        c.rect(x, y_bot, 3, row_h, fill=1, stroke=0)

        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 5.5)
        c.drawString(x + 10, y_top - 9, str(ind["setor"]).upper())
        sub, fs = str(ind["subsetor"]), 8.0
        while c.stringWidth(sub, F(FONT_TEXTO_SEMIBOLD), fs) > COL_ROTULO - 18 and fs > 6.2:
            fs -= 0.25
        c.setFillColor(INK)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), fs)
        c.drawString(x + 10, y_top - 19, sub)

        valor = ind.get("valor")
        val_w = 40
        bar_x = x + COL_ROTULO + 8
        bar_w = COL_MUNI - 16 - val_w
        bar_y = y_top - 16
        c.setFillColor(CREAM_DARK if i % 2 == 0 else WHITE)
        c.rect(bar_x, bar_y, bar_w, 7, fill=1, stroke=0)
        if valor is not None:
            c.setFillColor(cor)
            c.rect(bar_x, bar_y, max(bar_w * min(max(valor, 0.0), 1.0), 2.5), 7,
                   fill=1, stroke=0)
        c.setFillColor(cor)
        c.setFont(F(FONT_NUM_BOLD), 13)
        c.drawRightString(x + COL_ROTULO + COL_MUNI - 8, y_top - 17, _nota_risco(valor))

        # Aqui a caixa mostra nota 0-1, nao R$: formatador proprio.
        x_uf = x + COL_ROTULO + COL_MUNI
        x_br = x_uf + COL_CAIXA
        for cx, cor_col, val in ((x_uf, BLUE_MID, ind.get("media_estadual")),
                                 (x_br, BLUE_DARK, ind.get("media_nacional"))):
            qx = cx + (COL_CAIXA - CAIXA_W) / 2
            qy = y_top - (row_h + 19) / 2
            c.setFillColor(WHITE)
            c.setStrokeColor(cor_col)
            c.setLineWidth(0.8)
            c.roundRect(qx, qy, CAIXA_W, 19, 2, fill=1, stroke=1)
            c.setFillColor(cor_col)
            c.setFont(F(FONT_NUM_SEMIBOLD), 8)
            c.drawCentredString(qx + CAIXA_W / 2, qy + 19 / 2 - 2.8, _nota_risco(val))
        return y_bot

    # ─── Faixas de destaque ─────────────────────────────────────────────────

    def _faixa_receita(self, c, x, y_top, w):
        rc = self.d["receita_corrente"]
        perc = self.d.get("percentil") or {}
        pct = perc.get("percentil_numero")
        cor = _cor_supera(pct)
        y_bot = y_top - BANDA_H

        c.setFillColor(BLUE_DARK)
        c.roundRect(x, y_bot, w, BANDA_H, CARD_RADIUS, fill=1, stroke=0)
        c.setFillColor(cor)
        c.rect(x, y_top - 4, w, 4, fill=1, stroke=0)

        pad = 14
        c.setFillColor(YELLOW)
        c.setFont(F(FONT_NUM_SEMIBOLD), 8.5)
        c.drawString(x + pad, y_top - 18, "RECEITA CORRENTE POR HABITANTE")
        valor = "R$ " + _fmt_int(rc["per_capita"])
        c.setFillColor(WHITE)
        c.setFont(F(FONT_NUM_BOLD), 34)
        c.drawString(x + pad, y_top - 47, valor)
        vw = c.stringWidth(valor, F(FONT_NUM_BOLD), 34)

        quintil = perc.get("quintil")
        if quintil:
            txt = quintil.upper()
            tw = c.stringWidth(txt, F(FONT_NUM_SEMIBOLD), 8.5)
            cx = x + pad + vw + 14
            c.setFillColor(cor)
            c.roundRect(cx, y_top - 46, tw + 16, 15, 2, fill=1, stroke=0)
            c.setFillColor(BLUE_DARK if quintil.startswith("3") else WHITE)
            c.setFont(F(FONT_NUM_SEMIBOLD), 8.5)
            c.drawString(cx + 8, y_top - 41.5, txt)

        self._lado_direito(
            c, x, y_top, w,
            frase=f"Supera {pct}% dos municípios do país" if pct is not None else "",
            ressalva="1º = maior receita/hab.",
            faixas=FNP_QUINTIS, marcador=(pct / 100) if pct is not None else None,
            rankings=((rc["ranking_por_per_capita"]["nacional"], "no país"),
                      (rc["ranking_por_per_capita"].get("estadual"), "no estado")))
        return y_bot

    def _faixa_risco(self, c, x, y_top, w):
        m = self.risco_climatico.get("media_geral") or {}
        classe = m.get("classe")
        cor = _cor_risco(classe)
        y_bot = y_top - BANDA_H

        c.setFillColor(BLUE_DARK)
        c.roundRect(x, y_bot, w, BANDA_H, CARD_RADIUS, fill=1, stroke=0)
        c.setFillColor(cor)
        c.rect(x, y_top - 4, w, 4, fill=1, stroke=0)

        pad = 14
        c.setFillColor(YELLOW)
        c.setFont(F(FONT_NUM_SEMIBOLD), 8.5)
        c.drawString(x + pad, y_top - 18, "MÉDIA GERAL DE RISCO")
        valor = _nota_risco(m.get("valor"))
        c.setFillColor(WHITE)
        c.setFont(F(FONT_NUM_BOLD), 34)
        c.drawString(x + pad, y_top - 47, valor)
        vw = c.stringWidth(valor, F(FONT_NUM_BOLD), 34)
        c.setFillColor(BLUE_LIGHT)
        c.setFont(F(FONT_TEXTO), 8.5)
        c.drawString(x + pad + vw + 5, y_top - 47, "de 1,00")
        vw += 5 + c.stringWidth("de 1,00", F(FONT_TEXTO), 8.5)

        if classe:
            txt = f"RISCO {classe.upper()}"
            tw = c.stringWidth(txt, F(FONT_NUM_SEMIBOLD), 8.5)
            cx = x + pad + vw + 14
            c.setFillColor(cor)
            c.roundRect(cx, y_top - 46, tw + 16, 15, 2, fill=1, stroke=0)
            c.setFillColor(WHITE if classe in ("Muito alto", "Muito baixo") else BLUE_DARK)
            c.setFont(F(FONT_NUM_SEMIBOLD), 8.5)
            c.drawString(cx + 8, y_top - 41.5, txt)

        pct = m.get("supera_pct_nacional")
        self._lado_direito(
            c, x, y_top, w,
            frase=f"Risco maior que {pct}% dos municípios" if pct is not None else "",
            ressalva="1º = mais exposto",
            # Regua invertida: no risco, verde e a ponta boa e fica a ESQUERDA.
            faixas=list(reversed(FNP_QUINTIS)),
            marcador=m.get("valor"),
            rankings=((m.get("ranking_nacional"), "no país"),
                      (m.get("ranking_estadual"), "no estado")))
        return y_bot

    def _lado_direito(self, c, x, y_top, w, frase, ressalva, faixas, marcador, rankings):
        """Metade direita das faixas: frase, regua de 5 faixas e rankings."""
        pad = 14
        rx = x + w * 0.52
        fs_res = 6.3
        while (c.stringWidth(frase, F(FONT_TEXTO), 8) + 10
               + c.stringWidth(ressalva, F(FONT_TEXTO), fs_res) > (x + w - pad) - rx
               and fs_res > 5.0):
            fs_res -= 0.25
        if frase:
            c.setFillColor(BLUE_LIGHT)
            c.setFont(F(FONT_TEXTO), 8)
            c.drawString(rx, y_top - 16, frase)
        # BLUE_LIGHT, nunca MUTED: cinza medio sobre azul escuro tem contraste
        # de 1.8:1 e some no impresso. Mesmo erro ja corrigido na faixa de risco.
        c.setFillColor(BLUE_LIGHT)
        c.setFont(F(FONT_TEXTO), fs_res)
        c.drawRightString(x + w - pad, y_top - 16, ressalva)

        gx, gw, gh, gy = rx, w - (rx - x) - pad, 7, y_top - 36
        for i, q in enumerate(faixas):
            c.setFillColor(q)
            c.rect(gx + i * gw / 5, gy, gw / 5, gh, fill=1, stroke=0)
        if marcador is not None:
            mx = min(max(gx + gw * min(max(marcador, 0.0), 1.0), gx + 4), gx + gw - 4)
            p = c.beginPath()
            p.moveTo(mx, gy + gh + 1)
            p.lineTo(mx - 4, gy + gh + 7)
            p.lineTo(mx + 4, gy + gh + 7)
            p.close()
            c.setFillColor(WHITE)
            c.drawPath(p, fill=1, stroke=0)

        cx = rx
        for rk, escopo in rankings:
            if not rk:
                continue
            pos = f"{_fmt_int(rk['posicao'])}º"
            c.setFillColor(WHITE)
            c.setFont(F(FONT_NUM_BOLD), 11)
            c.drawString(cx, y_top - 51, pos)
            cx += c.stringWidth(pos, F(FONT_NUM_BOLD), 11) + 4
            resto = f"de {_fmt_int(rk['total'])} {escopo}"
            c.setFillColor(BLUE_LIGHT)
            c.setFont(F(FONT_TEXTO), 7.5)
            c.drawString(cx, y_top - 50, resto)
            cx += c.stringWidth(resto, F(FONT_TEXTO), 7.5) + 12

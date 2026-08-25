"""
Componentes visuais reusáveis.

Cada função recebe um `canvas` ReportLab e desenha um elemento padronizado
(stripe, KPI, tabela, divisória de seção...). Toda primitiva visual usada
por mais de uma página vive aqui — temas individuais não devem reimplementar.
"""
from io import BytesIO
from reportlab.lib.utils import simpleSplit, ImageReader

from .tokens import (
    BLUE, BLUE_DARK, BLUE_MID, BLUE_LIGHT, YELLOW, YELLOW_DARK,
    CREAM_DARK, PAPER, RULE, MUTED, INK, WHITE,
    STRIPE_W, MARGIN, CONTENT_W, ASSETS_DIR,
    FS_EYEBROW, FS_HEADER_FOOTER, FS_BODY, FS_TITLE_CAPA, FS_TITLE_DIVISOR,
    FS_HEADLINE, FS_CAPTION, FS_SUBTITLE,
    CARD_RADIUS, CARD_TOP_BAR, ROW_HEIGHT,
    QR_SIZE, QR_FILL_COLOR,
    FNP_Q1, FNP_Q3, FNP_Q5,
    FONT_NUM_BOLD, FONT_NUM_SEMIBOLD, FONT_NUM_REGULAR,
    FONT_TEXTO, FONT_TEXTO_SEMIBOLD, FONT_TEXTO_BOLD,
    STATUS_OK_PCT, STATUS_ALERTA_PCT,
)


# ─── Helper: cor de status pela landing IFEM ─────────────────────────────────

def cor_status_landing(supera_pct: int | None):
    """Cor do quadradinho de status reproduzindo o critério da landing IFEM.
    Thresholds vêm de tokens.STATUS_OK_PCT / STATUS_ALERTA_PCT."""
    if supera_pct is None:
        return MUTED
    if supera_pct >= STATUS_OK_PCT:
        return FNP_Q5
    if supera_pct >= STATUS_ALERTA_PCT:
        return FNP_Q3
    return FNP_Q1


# ─── Ícones vetoriais (estilo line-art) — Resumo do município ────────────────
# Todos com stroke fino e cantos arredondados. Reproduzem o conjunto exibido
# no painel da landing IFEM.

def _line_setup(c, cor, w):
    c.setStrokeColor(cor)
    c.setLineWidth(w)
    c.setLineCap(1)   # round
    c.setLineJoin(1)  # round


def draw_icon_populacao(c, cx, cy, size=14, cor=None):
    """Duas pessoas (silhuetas line-art): cabeça redonda + ombros em arco.
    Pessoa esquerda fica atrás e ligeiramente acima."""
    cor = cor or BLUE_DARK
    sw = max(0.8, size * 0.085)
    _line_setup(c, cor, sw)
    s = size * 0.5
    # Pessoa de trás (esquerda)
    rh = s * 0.34
    cx1, cy1 = cx - s*0.32, cy + s*0.18
    c.circle(cx1, cy1, rh, fill=0, stroke=1)
    p = c.beginPath()
    p.moveTo(cx1 - rh*1.4, cy1 - rh*1.0)
    p.curveTo(cx1 - rh*1.4, cy1 - rh*2.4,
              cx1 + rh*1.4, cy1 - rh*2.4,
              cx1 + rh*1.4, cy1 - rh*1.0)
    c.drawPath(p, fill=0, stroke=1)
    # Pessoa da frente (direita)
    rh2 = s * 0.38
    cx2, cy2 = cx + s*0.28, cy + s*0.04
    c.setFillColor(WHITE)
    c.circle(cx2, cy2, rh2, fill=1, stroke=1)
    p = c.beginPath()
    p.moveTo(cx2 - rh2*1.45, cy2 - rh2*1.1)
    p.curveTo(cx2 - rh2*1.45, cy2 - rh2*2.6,
              cx2 + rh2*1.45, cy2 - rh2*2.6,
              cx2 + rh2*1.45, cy2 - rh2*1.1)
    c.drawPath(p, fill=0, stroke=1)


def draw_icon_receita(c, cx, cy, size=14, cor=None):
    """Cifrão `$` em line-art. Sem círculo externo (estilo limpo do site)."""
    cor = cor or BLUE_DARK
    c.setFillColor(cor)
    c.setFont(F(FONT_NUM_BOLD), size * 1.05)
    c.drawCentredString(cx, cy - size * 0.30, "$")


def draw_icon_sus(c, cx, cy, size=14, cor=None):
    """Linha de batimento cardíaco (heartbeat). Estilo monitor de pulso."""
    cor = cor or BLUE_DARK
    sw = max(0.9, size * 0.10)
    _line_setup(c, cor, sw)
    s = size * 0.50
    # Curva tipo: __/\__/\__
    p = c.beginPath()
    p.moveTo(cx - s,           cy)
    p.lineTo(cx - s * 0.55,    cy)
    p.lineTo(cx - s * 0.30,    cy + s * 0.55)
    p.lineTo(cx - s * 0.05,    cy - s * 0.55)
    p.lineTo(cx + s * 0.18,    cy + s * 0.18)
    p.lineTo(cx + s * 0.40,    cy)
    p.lineTo(cx + s,           cy)
    c.drawPath(p, fill=0, stroke=1)


def draw_icon_cadunico(c, cx, cy, size=14, cor=None):
    """Documento line-art: retângulo com canto dobrado + linhas de texto."""
    cor = cor or BLUE_DARK
    sw = max(0.9, size * 0.09)
    _line_setup(c, cor, sw)
    s = size * 0.48
    x0, y0 = cx - s * 0.75, cy - s
    x1, y1 = cx + s * 0.75, cy + s
    fold = s * 0.32
    # Contorno com canto dobrado superior-direito
    p = c.beginPath()
    p.moveTo(x0, y0)
    p.lineTo(x0, y1)
    p.lineTo(x1 - fold, y1)
    p.lineTo(x1, y1 - fold)
    p.lineTo(x1, y0)
    p.close()
    c.setFillColor(WHITE)
    c.drawPath(p, fill=1, stroke=1)
    # Dobra do canto (triangulinho)
    p2 = c.beginPath()
    p2.moveTo(x1 - fold, y1)
    p2.lineTo(x1 - fold, y1 - fold)
    p2.lineTo(x1, y1 - fold)
    c.drawPath(p2, fill=0, stroke=1)
    # 3 linhas internas (texto fictício)
    for frac in (0.35, 0.05, -0.30):
        c.line(x0 + s*0.25, cy + s*frac, x1 - s*0.25, cy + s*frac)


def draw_icon_grafico(c, cx, cy, size=14, cor=None):
    """Gráfico de linha ascendente com pontinhos nos vértices (estilo site)."""
    cor = cor or BLUE_DARK
    sw = max(0.9, size * 0.10)
    _line_setup(c, cor, sw)
    s = size * 0.50
    # Pontos do polyline (asc) — 4 vértices, 2 sobem 1 desce 1 sobe
    pts = [
        (cx - s,        cy - s*0.55),
        (cx - s*0.30,   cy + s*0.05),
        (cx + s*0.20,   cy - s*0.20),
        (cx + s,        cy + s*0.55),
    ]
    p = c.beginPath()
    p.moveTo(*pts[0])
    for px, py in pts[1:]:
        p.lineTo(px, py)
    c.drawPath(p, fill=0, stroke=1)
    # Bolinhas nos vértices
    c.setFillColor(cor)
    for px, py in pts:
        c.circle(px, py, sw * 1.6, fill=1, stroke=0)


def _fmt_money_br(v: float) -> str:
    """Formata R$ no padrão da landing: separador BR de milhar.
    Valores < R$ 10 ganham 2 decimais (ex: R$ 0,50) para evitar "R$ 0" enganoso.
    """
    if v is None:
        return "n/d"
    if abs(v) < 10 and v != 0:
        return "R$ " + f"{v:.2f}".replace(".", ",")
    return "R$ " + f"{int(round(v)):,}".replace(",", ".")
from .fonts import F


# ─── Estrutura: stripe + numeração + header + footer ─────────────────────────

def draw_stripe(c, page_w, page_h, lado: str = "dir", cor=None):
    """Borda lateral colorida. lado ∈ {'dir', 'esq'}.
    `cor` opcional: quando o tema passa a cor do quintil do município,
    o stripe inteiro reflete o status fiscal (verde/amarelo/vermelho/azul)."""
    c.setFillColor(cor or BLUE)
    x = page_w - STRIPE_W if lado == "dir" else 0
    c.rect(x, 0, STRIPE_W, page_h, fill=1, stroke=0)


def draw_page_number(c, page_w, n: int, lado: str = "dir",
                     lettermark: str | None = None):
    """Número de página + lettermark IFEM vertical (imagem) no stripe.
    Quando `lettermark="IFEM"`, desenha a imagem pré-processada do alfabeto
    estilizado em branco-com-transparência, rotacionada na lateral."""
    cx = page_w - STRIPE_W / 2 if lado == "dir" else STRIPE_W / 2

    # Número
    c.setFillColor(WHITE)
    c.setFont(F(FONT_NUM_BOLD), 11)
    c.drawCentredString(cx, 14, f"{n:02d}")

    # Lettermark IFEM vertical (imagem dedicada, mais nítida que vetor).
    if lettermark == "IFEM":
        from .ifem_assets import ifem_lettermark_vertical_path
        img_path = ifem_lettermark_vertical_path()
        if img_path is not None:
            # Stripe = 20pt wide. Imagem rotacionada tem ratio ~120/400 = 0.30.
            # Largura útil dentro do stripe = 14pt (centro), altura = 14/0.30 ≈ 46pt.
            img_w = 14
            img_h = 46
            c.drawImage(str(img_path),
                        cx - img_w / 2, 32,
                        width=img_w, height=img_h,
                        preserveAspectRatio=True, mask="auto")


def draw_header(c, page_h, titulo_publicacao: str):
    """Cabeçalho discreto com o nome da publicação."""
    c.setFillColor(MUTED)
    c.setFont(F(FONT_NUM_SEMIBOLD), FS_HEADER_FOOTER)
    c.drawString(STRIPE_W + MARGIN, page_h - 20, titulo_publicacao.upper())


def draw_footer(c, page_w, label_secao: str):
    """Rodapé: label da seção à esquerda + logo FNP à direita."""
    c.setFillColor(MUTED)
    c.setFont(F(FONT_NUM_SEMIBOLD), FS_HEADER_FOOTER)
    c.drawString(STRIPE_W + MARGIN, 16, label_secao.upper())

    fnp_path = ASSETS_DIR / "logos" / "fnp-logo.png"
    if fnp_path.exists():
        c.drawImage(
            str(fnp_path),
            page_w - STRIPE_W - MARGIN - 60, 8,
            width=58, height=21,
            preserveAspectRatio=True, mask="auto",
        )


# ─── Texto: eyebrow, título, corpo ───────────────────────────────────────────

def draw_eyebrow(c, texto: str, x: float, y: float, color=BLUE):
    c.setFillColor(color)
    c.setFont(F(FONT_NUM_SEMIBOLD), FS_EYEBROW)
    c.drawString(x, y, texto.upper())


def draw_titulo(c, texto: str, x: float, y: float, size: int = 26, color=BLUE_DARK):
    """Suporta '\\n' como quebra manual de linha."""
    c.setFillColor(color)
    c.setFont(F(FONT_NUM_BOLD), size)
    for i, linha in enumerate(texto.split("\n")):
        c.drawString(x, y - i * (size * 0.95), linha)


def draw_body(c, texto: str, x: float, y: float, width: float,
              size: float = FS_BODY, color=INK) -> float:
    """Texto corrido com quebra automática. Retorna y final (após última linha)."""
    c.setFillColor(color)
    font = F(FONT_TEXTO)
    c.setFont(font, size)
    linhas = simpleSplit(texto, font, size, width)
    for i, linha in enumerate(linhas):
        c.drawString(x, y - i * (size * 1.5), linha)
    return y - len(linhas) * (size * 1.5)


def draw_caption(c, texto: str, x: float, y: float):
    """Fonte/elaboração. Sempre que houver gráfico ou tabela."""
    c.setFillColor(MUTED)
    c.setFont(F(FONT_TEXTO), FS_CAPTION)
    c.drawString(x, y, texto)


# ─── Componentes de bloco ────────────────────────────────────────────────────

def draw_kpi_box(c, label: str, valor, unidade: str,
                 x: float, y: float, w: float = 110, h: float = 58,
                 icone=None, upper: bool = True):
    """Card de KPI com borda esquerda azul. Layout: ícone opcional + label no
    topo, valor grande embaixo (alinhado), unidade em fonte menor à direita
    do valor com gap. `icone` deve ser uma função(c, cx, cy, size, cor).
    `upper` força ou não o label em CAIXA ALTA."""
    c.setFillColor(WHITE)
    c.roundRect(x, y, w, h, CARD_RADIUS, fill=1, stroke=0)
    c.setFillColor(BLUE_MID)
    c.rect(x, y, 4, h, fill=1, stroke=0)

    pad_l = 12
    label_y = y + h - 16
    if icone:
        icone(c, x + pad_l + 8, label_y + 6, size=15)
        label_x = x + pad_l + 22
    else:
        label_x = x + pad_l
    c.setFillColor(BLUE_DARK if not upper else MUTED)
    if upper:
        c.setFont(F(FONT_TEXTO), 8.5)
        c.drawString(label_x, label_y, label.upper())
    else:
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 10)
        c.drawString(label_x, label_y, label)

    valor_str = str(valor)
    # Reduz a fonte do valor automaticamente se passar da largura útil.
    valor_size = FS_HEADLINE
    valor_font = F(FONT_NUM_BOLD)
    inner_w = w - pad_l * 2 - 6  # reserva espaço pra unidade
    while c.stringWidth(valor_str, valor_font, valor_size) > inner_w and valor_size > 12:
        valor_size -= 1

    c.setFillColor(BLUE_DARK)
    c.setFont(valor_font, valor_size)
    valor_y = y + 14  # baseline com mais espaço do fundo
    c.drawString(x + pad_l, valor_y, valor_str)

    if unidade:
        c.setFont(F(FONT_TEXTO), 9)
        c.setFillColor(MUTED)
        c.drawString(
            x + pad_l + c.stringWidth(valor_str, valor_font, valor_size) + 4,
            valor_y + 2, unidade,
        )


def draw_ranking_item(c, pos: int, label: str, total: int,
                      x: float, y: float, w: float = 300):
    """Linha de ranking: posição grande em amarelo + label + 'de N'."""
    c.setFillColor(WHITE)
    c.rect(x, y, w, 30, fill=1, stroke=0)
    c.setStrokeColor(RULE)
    c.rect(x, y, w, 30, fill=0, stroke=1)

    c.setFillColor(YELLOW_DARK)
    pos_font = F(FONT_NUM_BOLD)
    pos_size = 20
    c.setFont(pos_font, pos_size)
    pos_str = f"{pos:,}º".replace(",", ".")
    c.drawString(x + 8, y + 8, pos_str)
    pos_w = c.stringWidth(pos_str, pos_font, pos_size)

    c.setFillColor(INK)
    c.setFont(F(FONT_TEXTO), 9.5)
    c.drawString(x + 16 + pos_w, y + 12, label)

    c.setFillColor(MUTED)
    c.setFont(F(FONT_TEXTO), 8)
    c.drawRightString(x + w - 8, y + 12, f"de {total:,}".replace(",", "."))


def draw_destaque_box(c, eyebrow: str, texto: str,
                      x: float, y: float, w: float, h: float = 60,
                      font_size: float = 16):
    """Box azul com eyebrow no topo + texto abaixo. Quebra automática se necessário."""
    c.setFillColor(BLUE)
    c.roundRect(x, y, w, h, CARD_RADIUS, fill=1, stroke=0)
    c.setFillColor(BLUE_MID)
    c.rect(x, y, 4, h, fill=1, stroke=0)

    # Eyebrow no topo do box (baseline a 10pt do topo).
    eyebrow_y = y + h - 12
    c.setFillColor(YELLOW)
    c.setFont(F(FONT_NUM_SEMIBOLD), FS_EYEBROW)
    c.drawString(x + 10, eyebrow_y, eyebrow.upper())

    # Texto abaixo do eyebrow, com gap de 4pt. Reduz fonte se passar de 2 linhas.
    c.setFillColor(WHITE)
    font = F(FONT_NUM_BOLD)
    inner_w = w - 20
    while True:
        linhas = simpleSplit(texto, font, font_size, inner_w)
        if len(linhas) <= 2 or font_size <= 11:
            break
        font_size -= 1
    c.setFont(font, font_size)
    text_top_y = eyebrow_y - 6 - font_size
    for i, linha in enumerate(linhas[:2]):
        c.drawString(x + 10, text_top_y - i * (font_size * 1.1), linha)


def draw_card_topbar(c, titulo: str, descricao: str,
                     x: float, y: float, w: float, h: float,
                     top_color=BLUE):
    """Card branco com barra colorida no topo. Usado em listas de pontos."""
    c.setFillColor(WHITE)
    c.roundRect(x, y, w, h, CARD_RADIUS, fill=1, stroke=0)
    c.setStrokeColor(RULE)
    c.roundRect(x, y, w, h, CARD_RADIUS, fill=0, stroke=1)

    c.setFillColor(top_color)
    c.rect(x, y + h - CARD_TOP_BAR, w, CARD_TOP_BAR, fill=1, stroke=0)

    c.setFillColor(BLUE_DARK)
    c.setFont(F(FONT_NUM_BOLD), FS_SUBTITLE)
    c.drawString(x + 10, y + h - 20, titulo.upper())

    draw_body(c, descricao, x + 10, y + h - 36, w - 20, size=FS_BODY)


def draw_table(c, headers: list[str], rows: list[list[str]],
               col_widths: list[float], x: float, y: float,
               row_h: float = ROW_HEIGHT, highlight_col: int = 1):
    """
    Tabela padrão FNP: header azul + zebra creme.
    `highlight_col` recebe destaque BLUE_DARK SemiBold; demais ficam MUTED Regular.
    Retorna y final (após última linha).
    """
    total_w = sum(col_widths)

    # Header
    c.setFillColor(BLUE)
    c.rect(x, y - row_h, total_w, row_h, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(F(FONT_NUM_SEMIBOLD), FS_EYEBROW)
    cx = x
    for i, h in enumerate(headers):
        if i == 0:
            c.drawString(cx + 4, y - 13, h)
        else:
            c.drawRightString(cx + col_widths[i] - 4, y - 13, h)
        cx += col_widths[i]
    y -= row_h

    # Linhas
    for ri, row in enumerate(rows):
        bg = WHITE if ri % 2 == 0 else CREAM_DARK
        c.setFillColor(bg)
        c.rect(x, y - row_h, total_w, row_h, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.line(x, y - row_h, x + total_w, y - row_h)

        cx = x
        for i, v in enumerate(row):
            if i == 0:
                c.setFillColor(INK)
                c.setFont(F(FONT_TEXTO), 8)
                c.drawString(cx + 4, y - 13, str(v))
            elif i == highlight_col:
                c.setFillColor(BLUE_DARK)
                c.setFont(F(FONT_TEXTO_SEMIBOLD), 8)
                c.drawRightString(cx + col_widths[i] - 4, y - 13, str(v))
            else:
                c.setFillColor(MUTED)
                c.setFont(F(FONT_TEXTO), 8)
                c.drawRightString(cx + col_widths[i] - 4, y - 13, str(v))
            cx += col_widths[i]
        y -= row_h

    return y


def draw_stacked_bar(c, segmentos: list[dict], x: float, y: float,
                     w: float, h: float = 32,
                     cores=(BLUE, BLUE_MID, YELLOW, YELLOW_DARK)):
    """
    Barra empilhada horizontal. Segmentos: [{'pct': float, 'categoria': str, ...}, ...].
    Retorna y abaixo da barra (já com 10pt de respiro).
    """
    total = sum(s["pct"] for s in segmentos)
    cur_x = x
    for i, seg in enumerate(segmentos):
        seg_w = w * (seg["pct"] / total)
        c.setFillColor(cores[i % len(cores)])
        c.rect(cur_x, y - h, seg_w, h, fill=1, stroke=0)
        if seg_w > 30:
            c.setFillColor(WHITE if i < 2 else BLUE_DARK)
            c.setFont(F(FONT_TEXTO), 7)
            c.drawCentredString(cur_x + seg_w / 2, y - h / 2 - 3, f"{seg['pct']:.1f}%")
        cur_x += seg_w
    return y - h - 10


# ─── Páginas-padrão completas ────────────────────────────────────────────────

def draw_section_divider(c, page_w, page_h, capitulo: str, titulo: str,
                         subtitulo: str, n_pagina: int, lado: str = "esq"):
    """Página divisória de seção: fundo azul cheio + capítulo grande."""
    c.setFillColor(BLUE)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Acento sutil: quarto de círculo translúcido no canto
    c.setFillColor(WHITE)
    c.setFillAlpha(0.08)
    c.circle(page_w if lado == "esq" else 0, 0, 300, fill=1, stroke=0)
    c.setFillAlpha(1.0)

    draw_stripe(c, page_w, page_h, lado)
    draw_page_number(c, page_w, n_pagina, lado)

    x = STRIPE_W + MARGIN if lado == "esq" else MARGIN
    y = page_h / 2 + 60

    c.setFillColor(YELLOW)
    c.setFont(F(FONT_NUM_SEMIBOLD), FS_EYEBROW)
    c.drawString(x, y + 55, capitulo.upper())

    c.setFillColor(WHITE)
    c.setFont(F(FONT_NUM_BOLD), FS_TITLE_DIVISOR)
    for i, linha in enumerate(titulo.split("\n")):
        c.drawString(x, y - i * (FS_TITLE_DIVISOR * 0.95), linha)

    c.setFillColor(BLUE_LIGHT)
    c.setFont(F(FONT_TEXTO), 10)
    c.drawString(x, y - 82, subtitulo)


def draw_qr_page(c, page_w, page_h, url: str, n_pagina: int,
                 lado: str = "esq", imagem_fundo: str | None = None):
    """Última página: imagem de fundo opcional + QR + URL."""
    if imagem_fundo:
        from pathlib import Path
        img_path = Path(imagem_fundo)
        if img_path.exists():
            c.drawImage(
                str(img_path), STRIPE_W if lado == "esq" else 0, 0,
                width=page_w - STRIPE_W, height=page_h,
                preserveAspectRatio=False, mask="auto",
            )
        else:
            c.setFillColor(BLUE_DARK)
            c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    else:
        c.setFillColor(BLUE_DARK)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # QR real
    try:
        import qrcode as qr_lib
        qr = qr_lib.QRCode(version=1, box_size=4, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=QR_FILL_COLOR, back_color="white")
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        buf.seek(0)
        c.drawImage(
            ImageReader(buf),
            page_w / 2 - QR_SIZE / 2, page_h / 2 - QR_SIZE / 2,
            width=QR_SIZE, height=QR_SIZE,
        )
    except ImportError:
        # qrcode não instalado: mantém fundo limpo (placeholder textual).
        c.setFillColor(WHITE)
        c.setFont(F(FONT_NUM_BOLD), 12)
        c.drawCentredString(page_w / 2, page_h / 2, url)

    # URL embaixo do QR
    c.setFillColor(YELLOW)
    c.setFont(F(FONT_TEXTO_SEMIBOLD), 9)
    c.drawCentredString(page_w / 2, page_h / 2 - QR_SIZE / 2 - 18, f"Acesse  {url}")

    draw_stripe(c, page_w, page_h, lado)
    draw_page_number(c, page_w, n_pagina, lado)


# ─── Cards estilo landing IFEM (categoria + sub-cards aninhados) ─────────────

def draw_categoria_card(c, *, x: float, y_top: float, w: float,
                        titulo: str,
                        municipio_nome: str,
                        supera_pct: int | None,
                        valor_per_capita: float,
                        media_nacional: float | None,
                        size: str = "full") -> float:
    """Card estilo landing IFEM: quadradinho de status + título + frase
    "supera X% dos municípios" + duas caixas (Valor por Habitante / Média).

    Tamanhos:
      - size="full":    altura 100pt (KPIs grandes, fonte 12-16pt)
      - size="compact": altura  80pt (KPIs menores, para sub-cards aninhados)

    Retorna a coordenada Y abaixo do card (y_top - altura - 6pt de respiro).
    """
    if size == "compact":
        h = 78
        kpi_h = 28
        title_size = 11
        frase_size = 9
        valor_size = 13
        label_size = 6
        pad_t_ext = 10
    else:
        h = 96
        kpi_h = 40
        title_size = 13
        frase_size = 10.5
        valor_size = 17
        label_size = 7
        pad_t_ext = 12

    y_bot = y_top - h

    # Fundo do card
    c.setFillColor(WHITE)
    c.roundRect(x, y_bot, w, h, CARD_RADIUS, fill=1, stroke=0)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.roundRect(x, y_bot, w, h, CARD_RADIUS, fill=0, stroke=1)

    # Header: quadradinho colorido + título
    cor = cor_status_landing(supera_pct)
    pad_l = 12
    pad_t = pad_t_ext
    box_size = 9
    box_x = x + pad_l
    box_y = y_top - pad_t - box_size
    c.setFillColor(cor)
    c.rect(box_x, box_y, box_size, box_size, fill=1, stroke=0)

    # Título
    c.setFillColor(BLUE_DARK)
    c.setFont(F(FONT_NUM_BOLD), title_size)
    c.drawString(box_x + box_size + 7, box_y + 1, titulo)

    # Frase "Supera X% dos municípios" (colorizado, sem nome do município)
    frase_y = box_y - 14
    if supera_pct is not None:
        verbo_txt = ("Supera apenas " if supera_pct < 60 else "Supera ") + f"{supera_pct}%"
        c.setFillColor(cor)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), frase_size)
        c.drawString(x + pad_l, frase_y, verbo_txt)
        w_verbo = c.stringWidth(verbo_txt, F(FONT_TEXTO_SEMIBOLD), frase_size)

        c.setFillColor(INK)
        c.setFont(F(FONT_TEXTO), frase_size)
        c.drawString(x + pad_l + w_verbo, frase_y, " dos municípios")

    # Duas caixinhas inferiores: VALOR POR HABITANTE | MÉDIA DOS MUNICÍPIOS (NACIONAL)
    kpi_y = y_bot + 8
    gap = 8
    kpi_w = (w - pad_l * 2 - gap) / 2

    def _kpi(kx, label, valor):
        c.setFillColor(CREAM_DARK)
        c.roundRect(kx, kpi_y, kpi_w, kpi_h, 2, fill=1, stroke=0)
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), label_size)
        c.drawCentredString(kx + kpi_w / 2, kpi_y + kpi_h - 11, label.upper())
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_NUM_BOLD), valor_size)
        c.drawCentredString(kx + kpi_w / 2, kpi_y + 6, valor)

    # Labels: no card compact (sub) usamos rótulo curto pra não estourar a largura.
    label_media = "Média nacional" if size == "compact" else "Média dos municípios (nacional)"
    _kpi(x + pad_l,                "Valor por habitante", _fmt_money_br(valor_per_capita))
    _kpi(x + pad_l + kpi_w + gap,  label_media,           _fmt_money_br(media_nacional))

    return y_bot - 4


def draw_categoria_bloco(c, *, x: float, y_top: float, w: float,
                          mae_titulo: str,
                          mae_supera_pct: int | None,
                          municipio_nome: str,
                          mae_per_capita: float,
                          mae_media: float | None,
                          filhos: list[dict]) -> float:
    """Bloco da página 6: card-mãe (compact) + subcards filhos em 2 colunas
    abaixo. Cada filho é um dict com keys:
      {titulo, supera_pct, per_capita, media}

    Retorna y abaixo do bloco completo.
    """
    y_cur = draw_categoria_card(
        c, x=x, y_top=y_top, w=w,
        titulo=mae_titulo,
        municipio_nome=municipio_nome,
        supera_pct=mae_supera_pct,
        valor_per_capita=mae_per_capita,
        media_nacional=mae_media,
        size="compact",
    )
    if not filhos:
        return y_cur

    gap = 5
    sub_w = (w - gap) / 2
    SUB_H = 78
    n = len(filhos)
    # Se sobrar um filho ímpar na última linha, ele ocupa a largura toda
    # (evita um card "órfão" pequeno num canto).
    ultimo_full = (n % 2) == 1
    rows = (n + 1) // 2
    for i, f in enumerate(filhos):
        eh_ultimo_impar = ultimo_full and i == n - 1
        if eh_ultimo_impar:
            sx = x
            cw = w
            sy = y_cur - (rows - 1) * (SUB_H + gap)
        else:
            col, row = i % 2, i // 2
            sx = x + col * (sub_w + gap)
            cw = sub_w
            sy = y_cur - row * (SUB_H + gap)
        draw_categoria_card(
            c, x=sx, y_top=sy, w=cw,
            titulo=f["titulo"],
            municipio_nome=municipio_nome,
            supera_pct=f.get("supera_pct"),
            valor_per_capita=f["per_capita"],
            media_nacional=f.get("media"),
            size="compact",
        )
    return y_cur - rows * (SUB_H + gap) - 4

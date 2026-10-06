"""
Capa do folheto IFEM — minimalista, em A5 retrato.

A arte de origem é quadrada: `indicadores_fnp_mapa_vivo_clean.png` (versão de
`indicadores_fnp_mapa_vivo.png` com a banda do município mascarada por
`tools/regerar_capa.py`). Ela traz o mosaico de fotos em cima e o logo FNP no
pé. No A5 ela não é desenhada inteira — esticada, os quartos de círculo virariam
ovais —, mas em dois recortes (`draw_recorte`) remontados na vertical:

    ┌──────────────┐
    │   mosaico    │  recorte 1, largura total menos margem
    │              │
    │  logo IFEM   │  `IFEM - MARCA-03.png`
    │ ──────────── │
    │  Município   │  nome + 2 rankings coloridos pelo percentil
    │  rk    rk    │
    │   logo FNP   │  recorte 2
    └──────────────┘
"""
from .tokens import (
    BLUE_DARK, MUTED, PAPER, WHITE, ROOT_DIR,
    FONT_NUM_BOLD, FONT_TEXTO, FONT_TEXTO_SEMIBOLD,
)
from .fonts import F
from .paleta_ranking import cor_por_percentil
from .asset_cache import cached_image
from .components import draw_recorte


# Geometria da arte de origem, em pixels (origem no canto superior esquerdo).
# Medida no PNG — se a arte mudar, medir de novo (o --preview do
# tools/regerar_capa.py ajuda a ver as bandas).
CAPA_PX = (1018, 1024)
MOSAICO_PX = (44, 49, 974, 731)       # mosaico + o contorno dos tiles da borda
LOGO_FNP_PX = (395, 945, 625, 1005)   # logo FNP do rodapé da arte

_IFEM_MARCA = ROOT_DIR / "data" / "ifem" / "IFEM - MARCA-03.png"
_IFEM_MARCA_RATIO = 4459 / 1891       # w/h do PNG


def _br_int(v) -> str:
    return f"{int(v):,}".replace(",", ".")


def draw_capa_padrao(c, page_w: float, page_h: float, n_pagina: int,
                     tema_label: str,
                     municipio_nome: str,
                     uf: str,
                     ranking_pop: tuple = None,
                     ranking_rec_pc: tuple = None,
                     mapa_path = None,
                     seed: int = 13,
                     **_unused):
    # Branco sob a arte (o fundo do PNG é branco); PAPER só no fallback sem arte.
    c.setFillColor(WHITE if (mapa_path and mapa_path.exists()) else PAPER)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    margem = 24
    cx = page_w / 2

    # 1) Mosaico no topo, na largura da página menos a margem.
    y = page_h - margem
    if mapa_path and mapa_path.exists():
        mos_w = page_w - 2 * margem
        x0, y0, x1, y1 = MOSAICO_PX
        mos_h = mos_w * (y1 - y0) / (x1 - x0)
        y -= mos_h
        draw_recorte(c, mapa_path, CAPA_PX, MOSAICO_PX, margem, y, mos_w)

    # 2) Logo FNP no pé — desenhado antes do bloco de texto para que o bloco
    #    saiba até onde pode descer.
    fnp_w = 118
    fnp_y = 26
    if mapa_path and mapa_path.exists():
        fnp_h = draw_recorte(c, mapa_path, CAPA_PX, LOGO_FNP_PX,
                             cx - fnp_w / 2, fnp_y, fnp_w)
    else:
        fnp_h = 0

    # 3) Logo IFEM centralizada logo abaixo do mosaico.
    y -= 22
    if _IFEM_MARCA.exists():
        ifem_h = 70
        ifem_w = ifem_h * _IFEM_MARCA_RATIO
        y -= ifem_h
        c.drawImage(cached_image(_IFEM_MARCA), cx - ifem_w / 2, y,
                    width=ifem_w, height=ifem_h,
                    preserveAspectRatio=True, mask="auto")

    # Fio separador entre a marca da publicação e o bloco do município.
    y -= 14
    c.setStrokeColor(BLUE_DARK)
    c.setLineWidth(0.6)
    c.line(cx - 90, y, cx + 90, y)

    if not (ranking_pop and ranking_rec_pc):
        return

    # 4) Nome do município em destaque, centralizado.
    texto_w = page_w - 2 * (margem + 16)
    nome_fs = 24
    while c.stringWidth(municipio_nome, F(FONT_NUM_BOLD), nome_fs) > texto_w and nome_fs > 14:
        nome_fs -= 1
    y -= 12 + nome_fs
    c.setFillColor(BLUE_DARK)
    c.setFont(F(FONT_NUM_BOLD), nome_fs)
    c.drawCentredString(cx, y, municipio_nome)

    # 5) Os dois rankings lado a lado, cada um centrado na sua metade.
    y -= 26
    col_w = texto_w / 2
    for i, (rotulo, (pos, tot)) in enumerate((
            ("RANKING POR POPULAÇÃO", ranking_pop),
            ("RANKING POR RECEITA POR HABITANTE", ranking_rec_pc))):
        ccx = margem + 16 + col_w * (i + 0.5)
        rot_fs = 7.5
        while c.stringWidth(rotulo, F(FONT_TEXTO_SEMIBOLD), rot_fs) > col_w - 8 and rot_fs > 6:
            rot_fs -= 0.25
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), rot_fs)
        c.drawCentredString(ccx, y, rotulo)

        pos_str = f"{_br_int(pos)}ª"
        resto = f"de {_br_int(tot)} municípios"
        w_pos = c.stringWidth(pos_str, F(FONT_NUM_BOLD), 16)
        w_resto = c.stringWidth(resto, F(FONT_TEXTO), 8.5)
        lx = ccx - (w_pos + 5 + w_resto) / 2
        c.setFillColor(cor_por_percentil(pos, tot))
        c.setFont(F(FONT_NUM_BOLD), 16)
        c.drawString(lx, y - 18, pos_str)
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 8.5)
        c.drawString(lx + w_pos + 5, y - 15, resto)


def _quebrar_parts_capa(c, parts, max_w):
    linhas = [[]]
    cur_w = 0.0
    for txt, cor, fnt, fs in parts:
        palavras = txt.split(" ")
        for j, pal in enumerate(palavras):
            p = pal if j == 0 else " " + pal
            if not p:
                continue
            pw = c.stringWidth(p, fnt, fs)
            if cur_w + pw > max_w and linhas[-1]:
                linhas.append([])
                cur_w = 0.0
                p = pal
                pw = c.stringWidth(p, fnt, fs)
            linhas[-1].append((p, cor, fnt, fs))
            cur_w += pw
    return linhas

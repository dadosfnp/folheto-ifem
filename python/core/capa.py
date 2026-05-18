"""
Capa do folheto IFEM — minimalista.

Usa o PNG ORIGINAL `indicadores_fnp_mapa_vivo.png` como fundo full bleed.
Esse PNG já traz:
  - Mapa do Brasil em mosaico
  - Título "Indicadores de Financiamento e Equidade Municipal" (esquerda)
  - Logo FNP (centro-rodapé)
  - Texto de município baked-in (à direita) — MASCARADO pelo script
    `tools/regerar_capa.py` (versão `_clean`).

Aqui apenas:
  1. Desenha o PNG _clean como fundo.
  2. Sobrepõe a logo IFEM nova à direita do título IFEM (cantinho).
  3. Escreve a frase do município no lugar do texto baked-in mascarado.
"""
from reportlab.lib import colors

from .tokens import (
    BLUE_DARK, INK, MUTED, WHITE, PAPER, RULE,
    STRIPE_W, ASSETS_DIR, ROOT_DIR,
    FONT_NUM_BOLD, FONT_TEXTO, FONT_TEXTO_BOLD, FONT_TEXTO_SEMIBOLD,
)
from .fonts import F
from .paleta_ranking import cor_por_percentil
from .asset_cache import cached_image


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
    # 1) Fundo: PNG original mascarado (full bleed). Já contém mapa, título
    #    "Indicadores de Financiamento e Equidade Municipal" e logo FNP.
    if mapa_path and mapa_path.exists():
        c.drawImage(cached_image(mapa_path), 0, 0,
                    width=page_w, height=page_h,
                    preserveAspectRatio=False, mask="auto")
    else:
        c.setFillColor(PAPER)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # 2) Logo IFEM AUMENTADA, centralizada na metade esquerda da banda.
    ifem_path = ROOT_DIR / "data" / "ifem" / "IFEM - MARCA-03.png"
    if ifem_path.exists():
        ifem_h = 84
        ifem_w = ifem_h * (200 / 80)
        ifem_cx = page_w * 0.24
        ifem_cy = page_h * 0.18
        c.drawImage(cached_image(ifem_path),
                    ifem_cx - ifem_w / 2, ifem_cy - ifem_h / 2,
                    width=ifem_w, height=ifem_h,
                    preserveAspectRatio=True, mask="auto")

    # Separador vertical fino entre logo IFEM (esquerda) e frase (direita).
    # Mantido dentro da banda branca mascarada (0.102H–0.277H).
    c.setStrokeColor(BLUE_DARK)
    c.setLineWidth(0.6)
    c.line(page_w * 0.48, page_h * 0.13, page_w * 0.48, page_h * 0.27)

    # 3) Frase do município na área direita da banda inferior, onde antes
    #    havia o texto baked-in (mascarado em branco pelo regerar_capa.py).
    if ranking_pop and ranking_rec_pc:
        pos_pop, _ = ranking_pop
        pos_rec, _ = ranking_rec_pc
        cor_pop = cor_por_percentil(pos_pop, ranking_pop[1])
        cor_rec = cor_por_percentil(pos_rec, ranking_rec_pc[1])

        # Layout direita: nome do município em DESTAQUE GRANDE no topo,
        # seguido de 2 linhas de "Ranking" com posição/escopo em cada.
        text_x_start = page_w * 0.52
        text_w = page_w - text_x_start - page_w * 0.04

        # Nome do município em Barlow Bold grande
        nome_fs = 18
        while c.stringWidth(municipio_nome, F(FONT_NUM_BOLD), nome_fs) > text_w and nome_fs > 12:
            nome_fs -= 1
        c.setFillColor(BLUE_DARK)
        c.setFont(F(FONT_NUM_BOLD), nome_fs)
        # nome_y subido de 0.22 → 0.245 e gaps internos reduzidos para o bloco
        # caber inteiro DENTRO da banda branca (0.102H–0.277H) e a última linha
        # ficar bem afastada da logo FNP do rodapé.
        nome_y = page_h * 0.245
        c.drawString(text_x_start, nome_y, municipio_nome)

        # Linha 1: "Ranking em população"
        rk_y = nome_y - 18
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 8.5)
        c.drawString(text_x_start, rk_y, "RANKING POR POPULAÇÃO")
        c.setFillColor(cor_pop)
        c.setFont(F(FONT_NUM_BOLD), 16)
        pos_str_pop = f"{_br_int(pos_pop)}ª"
        c.drawString(text_x_start, rk_y - 14, pos_str_pop)
        wp = c.stringWidth(pos_str_pop, F(FONT_NUM_BOLD), 16)
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 9.5)
        c.drawString(text_x_start + wp + 6, rk_y - 10,
                     f"de {_br_int(ranking_pop[1])} municípios")

        # Linha 2: "Ranking em receita por habitante"
        rk_y -= 32
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO_SEMIBOLD), 8.5)
        c.drawString(text_x_start, rk_y, "RANKING POR RECEITA POR HABITANTE")
        c.setFillColor(cor_rec)
        c.setFont(F(FONT_NUM_BOLD), 16)
        pos_str_rec = f"{_br_int(pos_rec)}ª"
        c.drawString(text_x_start, rk_y - 14, pos_str_rec)
        wr = c.stringWidth(pos_str_rec, F(FONT_NUM_BOLD), 16)
        c.setFillColor(MUTED)
        c.setFont(F(FONT_TEXTO), 9.5)
        c.drawString(text_x_start + wr + 6, rk_y - 10,
                     f"de {_br_int(ranking_rec_pc[1])} municípios")


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

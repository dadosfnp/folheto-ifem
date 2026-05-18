"""
Padrão modular FNP — tiles (quadrado, quarto de círculo, círculo) que compõem
o "alfabeto" visual da identidade. Usado em capas e na última página padrão.

Vetor puro (ReportLab primitives) — escala sem perder qualidade.
"""
import random

from .tokens import BLUE_DARK, BLUE, BLUE_MID, YELLOW_DARK


TILE_PALETTE = [BLUE_DARK, BLUE, BLUE_MID, YELLOW_DARK]

# Pesos do sorteio de tile no grid denso. "empty" deixa respiro visual.
TILE_WEIGHTS_DENSO = {
    "square":   30,
    "qc_ne":    16,
    "qc_nw":    16,
    "qc_se":    16,
    "qc_sw":    16,
    "circle":   3,
    "empty":    3,
}


def _draw_square(c, x, y, s, color, lw):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.rect(x, y, s, s, fill=0, stroke=1)


def _draw_qc(c, x, y, s, color, corner, lw):
    """Quarto de círculo dentro da célula. corner ∈ {ne,nw,se,sw} indica o
    canto onde o centro do círculo se apoia (o arco bojuda para o canto oposto)."""
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    # Bounding box do círculo completo (raio = s) centrado no canto.
    if corner == "ne":   # centro em (x+s, y+s), arco no quadrante SW da circ.
        c.arc(x - s, y - s, x + s, y + s, startAng=0,   extent=90)
    elif corner == "nw": # centro em (x, y+s), arco no quadrante SE da circ.
        c.arc(x,     y - s, x + 2*s, y + s, startAng=90,  extent=90)
    elif corner == "se": # centro em (x+s, y), arco no quadrante NW da circ.
        c.arc(x - s, y,     x + s,   y + 2*s, startAng=270, extent=90)
    elif corner == "sw": # centro em (x, y), arco no quadrante NE da circ.
        c.arc(x,     y,     x + 2*s, y + 2*s, startAng=180, extent=90)


def _draw_circle(c, x, y, s, color, lw):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.circle(x + s/2, y + s/2, s/2 * 0.92, fill=0, stroke=1)


def draw_tile(c, kind: str, x: float, y: float, s: float, color, lw: float = 1.2):
    """Desenha um tile do alfabeto modular em (x,y) com lado s."""
    if kind == "square":
        _draw_square(c, x, y, s, color, lw)
    elif kind.startswith("qc_"):
        _draw_qc(c, x, y, s, color, kind[3:], lw)
    elif kind == "circle":
        _draw_circle(c, x, y, s, color, lw)
    # "empty" não desenha nada


def _weighted_choice(rng: random.Random, weights: dict):
    total = sum(weights.values())
    pick = rng.uniform(0, total)
    acc = 0
    for k, w in weights.items():
        acc += w
        if pick <= acc:
            return k
    return list(weights.keys())[-1]


def draw_grid_modular(c, x: float, y: float, w: float, h: float,
                      cell: float = 22, lw: float = 1.2,
                      seed: int = 7,
                      weights: dict = None,
                      palette: list = None):
    """
    Grid denso de tiles modulares preenchendo o retângulo (x, y, w, h).

    `seed` torna o padrão determinístico — mesmo município = mesmo desenho.
    """
    rng = random.Random(seed)
    weights = weights or TILE_WEIGHTS_DENSO
    palette = palette or TILE_PALETTE

    cols = int(w // cell)
    rows = int(h // cell)
    off_x = x + (w - cols * cell) / 2
    off_y = y + (h - rows * cell) / 2

    for r in range(rows):
        for col in range(cols):
            kind = _weighted_choice(rng, weights)
            if kind == "empty":
                continue
            color = palette[rng.randrange(len(palette))]
            draw_tile(c, kind,
                      off_x + col * cell,
                      off_y + r * cell,
                      cell, color, lw)


# ─── Alfabeto modular: composição de letras com primitivas ───────────────────
#
# Cada letra é uma grade de células onde cada célula tem um tile (ou está vazia).
# Inspirado no Folheto_Alfabeto.jpeg — letras existentes no alfabeto original
# usam a mesma composição; letras inventadas (ex.: E maiúsculo, que não está no
# alfabeto da inspiração) seguem o mesmo vocabulário visual.
#
# Formato: dict[letra] = list de linhas (top→bottom), cada linha = list de tiles.
# Tile = "square" | "qc_ne" | "qc_nw" | "qc_se" | "qc_sw" | "circle" | None.

LETRAS_MODULARES = {
    # I: círculo em cima, quadrado embaixo (igual ao alfabeto original).
    "I": [["circle"],
          ["square"]],
    # F: 2 colunas; topo cheio, meio só esquerda + travessão, base só esquerda.
    "F": [["square", "square"],
          ["square", None],
          ["square", None]],
    # E: F com base completa (inventado em estilo coerente).
    "E": [["square", "square"],
          ["square", None],
          ["square", "square"]],
    # M: 2 QCs no topo abrindo pra fora, 2 quadrados na base (igual original).
    "M": [["qc_se", "qc_sw"],
          ["square", "square"]],
    # i minúsculo: círculo pequeno + quadrado.
    "i": [["circle"],
          ["square"]],
    # f minúsculo: barra vertical + travessão. Aproximação modular.
    "f": [["qc_se", None],
          ["square", None],
          ["square", None]],
    # e minúsculo: QC superior + travessão + base com QC.
    "e": [["qc_se", "qc_sw"],
          ["square", "square"]],
    # m minúsculo: 2 QCs + 2 quadrados (igual M).
    "m": [["qc_se", "qc_sw"],
          ["square", "square"]],
}


def draw_letra(c, letra: str, x: float, y: float, cell: float = 8, lw: float = 1.0,
               color = None):
    """Desenha uma letra modular ancorada em (x, y) = canto inferior-esquerdo.
    Retorna a largura da letra para encadear na próxima."""
    grid = LETRAS_MODULARES.get(letra)
    if grid is None:
        return 0
    cor = color or BLUE_DARK
    rows = len(grid)
    cols = max(len(r) for r in grid)
    for ri, linha in enumerate(grid):
        for ci, tile in enumerate(linha):
            if tile is None:
                continue
            cx = x + ci * cell
            cy = y + (rows - 1 - ri) * cell  # primeira linha vai pro topo
            draw_tile(c, tile, cx, cy, cell, cor, lw)
    return cols * cell


def draw_lettermark(c, texto: str, x: float, y: float, cell: float = 8,
                    lw: float = 1.0, color = None, espaco: float = 3):
    """Desenha uma palavra com letras modulares lado a lado.
    (x, y) = canto inferior-esquerdo da primeira letra. Retorna largura total."""
    cur_x = x
    for letra in texto:
        if letra == " ":
            cur_x += cell * 1.5
            continue
        w = draw_letra(c, letra, cur_x, y, cell=cell, lw=lw, color=color)
        cur_x += w + espaco
    return cur_x - x


def draw_lettermark_vertical(c, texto: str, x: float, y: float, cell: float = 4,
                             lw: float = 0.7, color = None, espaco: float = 4):
    """Desenha as letras de uma palavra empilhadas verticalmente.
    (x, y) = canto inferior-esquerdo da letra DE BAIXO. As letras sobem.
    Cada letra é centralizada horizontalmente em x (x = centro da coluna).
    Retorna altura total."""
    cur_y = y
    for letra in reversed(texto):  # desenhar de baixo pra cima
        if letra == " ":
            cur_y += cell * 1.5
            continue
        grid = LETRAS_MODULARES.get(letra)
        if grid is None:
            continue
        rows = len(grid)
        cols = max(len(r) for r in grid)
        # Centralizar a letra na coluna `x`.
        letra_x = x - (cols * cell) / 2
        draw_letra(c, letra, letra_x, cur_y, cell=cell, lw=lw, color=color)
        cur_y += rows * cell + espaco
    return cur_y - y


def draw_alfabeto_decoracao(c, x: float, y: float, w: float, h: float,
                            n_pecas: int = 14,
                            tamanho: float = 38,
                            lw: float = 1.6,
                            seed: int = 11,
                            palette: list = None,
                            evitar_rect: tuple = None):
    """
    Espalha peças soltas do alfabeto pela região (x, y, w, h).
    `evitar_rect = (rx, ry, rw, rh)` impede colisão com bloco de título.
    """
    rng = random.Random(seed)
    palette = palette or TILE_PALETTE
    kinds = ["square", "qc_ne", "qc_nw", "qc_se", "qc_sw", "circle"]

    colocados = []
    tentativas = 0
    while len(colocados) < n_pecas and tentativas < n_pecas * 30:
        tentativas += 1
        s = tamanho * rng.uniform(0.7, 1.25)
        px = x + rng.uniform(0, w - s)
        py = y + rng.uniform(0, h - s)

        if evitar_rect:
            rx, ry, rw, rh = evitar_rect
            # margem de respiro de 8pt
            if not (px + s < rx - 8 or px > rx + rw + 8 or
                    py + s < ry - 8 or py > ry + rh + 8):
                continue

        # evitar sobreposição entre peças
        colide = False
        for (ox, oy, os_) in colocados:
            if not (px + s < ox - 6 or px > ox + os_ + 6 or
                    py + s < oy - 6 or py > oy + os_ + 6):
                colide = True
                break
        if colide:
            continue

        kind = kinds[rng.randrange(len(kinds))]
        color = palette[rng.randrange(len(palette))]
        draw_tile(c, kind, px, py, s, color, lw)
        colocados.append((px, py, s))

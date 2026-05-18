"""
Mascara o PNG da capa (`data/ifem/indicadores_fnp_mapa_vivo.png`) removendo
o texto baked-in do município que aparece no canto direito inferior, e gera
`data/ifem/indicadores_fnp_mapa_vivo_clean.png` — usado por `core/capa.py`.

Quando regerar:
- O PNG original mudou (novo template/arte).
- A capa precisa preservar o logo FNP e o título da publicação à esquerda.

Uso:
    python tools/regerar_capa.py            # regera com as coords padrão
    python tools/regerar_capa.py --preview  # mostra a banda inferior para validar
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "data" / "ifem" / "indicadores_fnp_mapa_vivo.png"
DST  = ROOT / "data" / "ifem" / "indicadores_fnp_mapa_vivo_clean.png"


def regerar(preview: bool = False):
    if not SRC.exists():
        raise FileNotFoundError(f"PNG original não encontrado: {SRC}")

    src = Image.open(SRC).convert("RGB")
    W, H = src.size
    out = src.copy()
    draw = ImageDraw.Draw(out)

    # 1) Mascara a BANDA INFERIOR INTEIRA (título IFEM antigo + texto do
    #    município + separador vertical). O título IFEM é substituído pelo
    #    PNG `IFEM - MARCA-03.png` (logo nova) desenhado pelo tema.
    draw.rectangle([0, 740, W, 920], fill=(255, 255, 255))

    # 2) Restaura a região do LOGO FNP (Y 0.91-0.99H, X 0.395-0.605W).
    logo_box = (int(W * 0.395), int(H * 0.911), int(W * 0.605), int(H * 0.99))
    out.paste(src.crop(logo_box), logo_box[:2])

    out.save(DST)
    print(f"[ok] {DST}  ({W}x{H})")

    if preview:
        band = out.crop((0, int(H * 0.70), W, H))
        prev = ROOT / "data" / "ifem" / "_preview_capa_clean.png"
        band.save(prev)
        print(f"[preview] {prev}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--preview", action="store_true",
                   help="Salva também a banda inferior para inspeção visual.")
    args = p.parse_args()
    regerar(preview=args.preview)

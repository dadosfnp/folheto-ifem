"""
Renderiza páginas de um folheto como PNG para a landing mostrar um modelo.

POR QUE
Quem chega na landing não sabe o que vai baixar. Um "Baixar PDF" sem prévia
exige um download de 3,5 MB só para descobrir se o material serve. Três páginas
representativas resolvem isso em dois segundos.

As imagens ficam em docs/preview/ e são versionadas — precisam viajar junto com
o GitHub Pages, e o peso é pequeno perto de resolver a dúvida do visitante.

USO
    python tools/gerar_preview_landing.py
    python tools/gerar_preview_landing.py --municipio 2304400 --paginas 1,3,6
"""
import argparse
import io
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT_DIR / "docs" / "preview"

# São Paulo: maior município, o exemplo mais neutro possível.
COD_PADRAO = "3550308"

# Capa, síntese fiscal (o gráfico que resume a tese) e estrutura da receita.
PAGINAS_PADRAO = "1,3,6"

LARGURA_ALVO = 720   # suficiente para leitura em tela sem inflar o repositório


def garantir_pypdfium():
    try:
        import pypdfium2  # noqa: F401
        return
    except ImportError:
        pass
    print("instalando pypdfium2...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pypdfium2"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"falha ao instalar pypdfium2: {r.stderr[:300]}")


def achar_pdf(cod: str) -> Path:
    """Localiza o PDF pelo código IBGE, via JSON correspondente."""
    import json

    for pasta in ("export_folheto", "_sem_declaracao"):
        d = ROOT_DIR / "data" / "ifem" / "dados-ifem" / pasta
        for j in d.glob(f"{cod}_*.json"):
            ident = json.loads(j.read_text(encoding="utf-8"))["identificacao"]
            tc_min = {"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o"}
            nome = " ".join(
                w.lower() if i > 0 and w.lower() in tc_min else w.lower().capitalize()
                for i, w in enumerate(ident["municipio"].split())
            ).replace(" ", "_")
            pdf = ROOT_DIR / "output" / f"FolhetoIFEM_{nome}_{ident['uf']}.pdf"
            if pdf.exists():
                return pdf
    sys.exit(f"PDF do município {cod} não encontrado em output/ — gere-o primeiro.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera PNGs de prévia para a landing")
    ap.add_argument("--municipio", default=COD_PADRAO, help="código IBGE")
    ap.add_argument("--paginas", default=PAGINAS_PADRAO, help="ex.: 1,3,6")
    args = ap.parse_args()

    garantir_pypdfium()
    import pypdfium2 as pdfium
    from PIL import Image

    pdf = achar_pdf(args.municipio)
    paginas = [int(p.strip()) for p in args.paginas.split(",") if p.strip()]
    print(f"origem: {pdf.name}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(pdf)

    gerados = []
    for num in paginas:
        if num < 1 or num > len(doc):
            print(f"  [aviso] página {num} fora do intervalo (1-{len(doc)})", file=sys.stderr)
            continue
        pagina = doc[num - 1]
        # Escala derivada da largura alvo, não fixa: o formato é 20x20 cm, mas
        # deixar isso implícito quebraria se o tamanho da página mudar.
        escala = LARGURA_ALVO / pagina.get_width()
        img = pagina.render(scale=escala).to_pil().convert("RGB")

        # JPEG em vez de PNG: a capa traz um mapa raster e sai com 493 KB em PNG
        # contra 116 KB em JPEG q85, sem perda visível a 720 px. WebP seria ainda
        # menor (81 KB), mas JPEG não depende de suporte do navegador — numa
        # página institucional isso vale mais que os 35 KB economizados.
        destino = OUT_DIR / f"pagina-{num}.jpg"
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True, progressive=True)
        destino.write_bytes(buf.getvalue())
        gerados.append((destino, img.size, len(buf.getvalue())))
        print(f"  + {destino.name}  {img.size[0]}x{img.size[1]}px  "
              f"{len(buf.getvalue()) / 1024:,.0f} KB")

    doc.close()

    total = sum(g[2] for g in gerados)
    print(f"\n{len(gerados)} imagem(ns), {total / 1024:,.0f} KB no total")
    print(f"destino: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

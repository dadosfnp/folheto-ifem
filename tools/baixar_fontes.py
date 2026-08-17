"""
Baixa as fontes oficiais do folheto FNP para `fonts/`.

Por que este script existe: os .ttf não são versionados (licença + peso), e o
gerador cai em Helvetica silenciosamente quando não os encontra. Resultado
prático: duas pessoas geram PDFs tipograficamente diferentes a partir do mesmo
commit. Este script torna o setup reprodutível em um comando.

Origens:
  - Barlow Condensed  -> repositório google/fonts (arquivos estáticos, download direto)
  - Inter             -> release oficial rsms/inter (o google/fonts só publica a
                         variable font, que o ReportLab não sabe instanciar por peso;
                         os estáticos vivem dentro de `extras/ttf/` no zip)

Uso:
    python tools/baixar_fontes.py           # baixa só o que falta
    python tools/baixar_fontes.py --force   # rebaixa tudo
"""
import argparse
import io
import sys
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Falta a dependência 'requests'. Rode: pip install -r requirements.txt")

ROOT_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT_DIR / "fonts"

_BARLOW_BASE = "https://github.com/google/fonts/raw/main/ofl/barlowcondensed"
FONTES_DIRETAS = {
    "BarlowCondensed-Bold.ttf":     f"{_BARLOW_BASE}/BarlowCondensed-Bold.ttf",
    "BarlowCondensed-SemiBold.ttf": f"{_BARLOW_BASE}/BarlowCondensed-SemiBold.ttf",
    "BarlowCondensed-Regular.ttf":  f"{_BARLOW_BASE}/BarlowCondensed-Regular.ttf",
}

INTER_ZIP_URL = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
INTER_NO_ZIP = {
    "Inter-Regular.ttf":  "extras/ttf/Inter-Regular.ttf",
    "Inter-SemiBold.ttf": "extras/ttf/Inter-SemiBold.ttf",
    "Inter-Bold.ttf":     "extras/ttf/Inter-Bold.ttf",
}

TIMEOUT = 60
TAMANHO_MINIMO = 10 * 1024  # abaixo disso é página de erro HTML, não fonte


def _valida_ttf(conteudo: bytes, origem: str) -> None:
    """
    Garante que o download é mesmo um TrueType antes de gravar.

    Sem esta checagem, uma página de erro do GitHub (HTTP 200 com HTML) seria
    salva como .ttf e só estouraria lá na frente, dentro do ReportLab, com uma
    mensagem que não aponta pra causa.
    """
    if len(conteudo) < TAMANHO_MINIMO:
        raise ValueError(f"{origem}: só {len(conteudo)} bytes — provável página de erro")
    # sfnt version: 0x00010000 (TrueType) ou 'OTTO' (CFF/OpenType).
    if conteudo[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"):
        raise ValueError(f"{origem}: assinatura inválida {conteudo[:4]!r} — não é TTF/OTF")


def _baixar(url: str) -> bytes:
    resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    return resp.content


def baixar_barlow(force: bool) -> tuple[int, list[str]]:
    """Baixa os estáticos do Barlow Condensed. Retorna (baixados, erros)."""
    baixados, erros = 0, []
    for nome, url in FONTES_DIRETAS.items():
        destino = FONTS_DIR / nome
        if destino.exists() and not force:
            print(f"  = {nome} (já existe)")
            continue
        try:
            conteudo = _baixar(url)
            _valida_ttf(conteudo, nome)
            destino.write_bytes(conteudo)
            print(f"  + {nome} ({len(conteudo) // 1024} KB)")
            baixados += 1
        except Exception as e:
            erros.append(f"{nome}: {e}")
            print(f"  x {nome}: {e}", file=sys.stderr)
    return baixados, erros


def baixar_inter(force: bool) -> tuple[int, list[str]]:
    """
    Extrai os estáticos do Inter do zip oficial (~32 MB).

    O zip é baixado uma única vez em memória e só quando falta algum arquivo —
    não vale a pena pagar 32 MB pra rebaixar uma fonte que já está no disco.
    """
    pendentes = {
        nome: caminho
        for nome, caminho in INTER_NO_ZIP.items()
        if force or not (FONTS_DIR / nome).exists()
    }
    if not pendentes:
        for nome in INTER_NO_ZIP:
            print(f"  = {nome} (já existe)")
        return 0, []

    print(f"  . baixando Inter-4.1.zip (~32 MB) para extrair {len(pendentes)} arquivo(s)...")
    try:
        bruto = _baixar(INTER_ZIP_URL)
    except Exception as e:
        msg = f"download do Inter falhou: {e}"
        print(f"  x {msg}", file=sys.stderr)
        return 0, [msg]

    baixados, erros = 0, []
    try:
        with zipfile.ZipFile(io.BytesIO(bruto)) as z:
            disponiveis = set(z.namelist())
            for nome, caminho_zip in pendentes.items():
                if caminho_zip not in disponiveis:
                    erros.append(f"{nome}: '{caminho_zip}' não existe no zip (release mudou de layout?)")
                    print(f"  x {nome}: não encontrado no zip", file=sys.stderr)
                    continue
                try:
                    conteudo = z.read(caminho_zip)
                    _valida_ttf(conteudo, nome)
                    (FONTS_DIR / nome).write_bytes(conteudo)
                    print(f"  + {nome} ({len(conteudo) // 1024} KB)")
                    baixados += 1
                except Exception as e:
                    erros.append(f"{nome}: {e}")
                    print(f"  x {nome}: {e}", file=sys.stderr)
    except zipfile.BadZipFile as e:
        msg = f"zip do Inter corrompido: {e}"
        print(f"  x {msg}", file=sys.stderr)
        return baixados, [msg]

    return baixados, erros


def main() -> int:
    parser = argparse.ArgumentParser(description="Baixa as fontes oficiais do folheto FNP")
    parser.add_argument("--force", action="store_true",
                        help="rebaixa mesmo se o arquivo já existir")
    args = parser.parse_args()

    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Destino: {FONTS_DIR}\n")

    print("Barlow Condensed (google/fonts):")
    n_barlow, erros_barlow = baixar_barlow(args.force)

    print("\nInter (rsms/inter v4.1):")
    n_inter, erros_inter = baixar_inter(args.force)

    erros = erros_barlow + erros_inter
    total_esperado = len(FONTES_DIRETAS) + len(INTER_NO_ZIP)
    presentes = sum(
        1 for nome in list(FONTES_DIRETAS) + list(INTER_NO_ZIP)
        if (FONTS_DIR / nome).exists()
    )

    print(f"\n{'-' * 58}")
    print(f"Baixados agora: {n_barlow + n_inter} | No disco: {presentes}/{total_esperado}")

    if erros:
        print(f"\n{len(erros)} falha(s):", file=sys.stderr)
        for e in erros:
            print(f"  - {e}", file=sys.stderr)
        print("\nAs fontes que faltarem cairão em Helvetica na geração do PDF.",
              file=sys.stderr)
        return 1

    print("Fontes completas — os PDFs sairão com a tipografia oficial FNP.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

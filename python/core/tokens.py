"""
Tokens de design — espelho em código do DESIGN_SYSTEM.md.

Qualquer mudança aqui afeta TODOS os folhetos. Nunca alterar valores
em arquivos de tema individuais — sempre mexer aqui.
"""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.units import cm

# ─── Caminhos do projeto ─────────────────────────────────────────────────────
# Resolvidos a partir da raiz do repositório (2 níveis acima deste arquivo).

ROOT_DIR   = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
FONTS_DIR  = ROOT_DIR / "fonts"
OUTPUT_DIR = ROOT_DIR / "output"
DATA_DIR   = ROOT_DIR / "data"

# ─── Ano de referência dos dados ─────────────────────────────────────────────
# Ano impresso no folheto (eixos de gráfico, títulos de seção, texto corrido).
#
# Vem do .env porque muda a cada atualização anual da base, enquanto as CHAVES
# dos JSONs de entrada continuam com o sufixo legado `_2024`
# (`sintese_fiscal_2000_2024`, `posicao_historica.ano_2024`) — o Subfinanciados
# nunca as renomeou. Nunca derive o ano dessas chaves: elas mentem de propósito,
# para não quebrar o contrato de dados. Ver data/ifem/PROVENIENCIA.md.

def _ano_ref_do_env(padrao: int = 2025) -> int:
    """Lê ANO_REF do .env da raiz. Sem o arquivo ou com valor inválido, usa o padrão."""
    import os

    bruto = os.getenv("ANO_REF")
    if not bruto:
        env_file = ROOT_DIR / ".env"
        if env_file.exists():
            for linha in env_file.read_text(encoding="utf-8").splitlines():
                linha = linha.strip()
                if linha.startswith("ANO_REF") and "=" in linha:
                    bruto = linha.split("=", 1)[1].strip()
                    break
    try:
        return int(bruto)
    except (TypeError, ValueError):
        return padrao


ANO_REF = _ano_ref_do_env()
ANO_BASE = 2000                       # início da série histórica
PERIODO = f"{ANO_BASE}–{ANO_REF}"     # travessão, para títulos de seção
PERIODO_HIFEN = f"{ANO_BASE}-{ANO_REF}"  # hífen, para títulos em caixa alta

# ─── Página ──────────────────────────────────────────────────────────────────

PAGE_SIZE = (20 * cm, 20 * cm)   # 20×20 cm — formato canônico FNP

STRIPE_W  = 20    # largura da borda lateral azul (pt)
MARGIN    = 36    # margem interna (pt)
CONTENT_W = (20 * cm) - STRIPE_W - MARGIN * 2   # largura útil de conteúdo

# ─── Paleta ──────────────────────────────────────────────────────────────────

BLUE_DARK   = colors.HexColor("#122747")
BLUE        = colors.HexColor("#1B3A6B")
BLUE_MID    = colors.HexColor("#3D6FA8")
BLUE_LIGHT  = colors.HexColor("#AABBCC")   # subtítulos sobre fundo azul
YELLOW      = colors.HexColor("#FFC72C")
YELLOW_DARK = colors.HexColor("#C99A1F")
GREEN       = colors.HexColor("#2A8F5C")
RED_BURNT   = colors.HexColor("#C04A1A")

# Paleta oficial FNP — 5 quintis (do pior pro melhor financiado).
FNP_Q1 = colors.HexColor("#A81C21")  # vermelho   — 0-20% (menor receita)
FNP_Q2 = colors.HexColor("#E47326")  # laranja    — 20-40%
FNP_Q3 = colors.HexColor("#F4D01D")  # amarelo    — 40-60%
FNP_Q4 = colors.HexColor("#6AC074")  # verde claro — 60-80%
FNP_Q5 = colors.HexColor("#1C9148")  # verde      — 80-100% (maior receita)
FNP_QUINTIS = [FNP_Q1, FNP_Q2, FNP_Q3, FNP_Q4, FNP_Q5]

# Paleta dos 10 decis (gradiente mais fino).
FNP_DECIS = [
    colors.HexColor("#960E16"), colors.HexColor("#CF3026"),
    colors.HexColor("#EB6630"), colors.HexColor("#F8A555"),
    colors.HexColor("#FCE182"), colors.HexColor("#DDEC88"),
    colors.HexColor("#9DD57D"), colors.HexColor("#60BA69"),
    colors.HexColor("#2D964D"), colors.HexColor("#076931"),
]
CREAM       = colors.HexColor("#F4EFE6")
CREAM_DARK  = colors.HexColor("#F0EBE2")   # zebra de tabela
PAPER       = colors.HexColor("#FBF8F2")
RULE        = colors.HexColor("#D9D2C3")
MUTED       = colors.HexColor("#6B6B6B")
INK         = colors.HexColor("#1A1A1A")
WHITE       = colors.white

# ─── Tipografia ──────────────────────────────────────────────────────────────
# Tamanhos canônicos (pt). Mudar aqui = mudar em todos os folhetos.

FS_TITLE_CAPA      = 42    # título de capa
FS_TITLE_DIVISOR   = 58    # título de divisória de seção
FS_TITLE_SECAO     = 30    # título de página de conteúdo
FS_HEADLINE        = 26    # números grandes (KPI, ranking)
FS_SUBTITLE        = 14    # subtítulos de card
FS_BODY            = 12    # texto corrido
FS_BODY_SMALL      = 11
FS_EYEBROW         = 10.5  # capítulo / chapéu
FS_HEADER_FOOTER   = 9.5   # cabeçalho e rodapé
FS_CAPTION         = 9     # fonte / elaboração

# ─── Famílias tipográficas (papel × uso) ─────────────────────────────────────
# Padronizamos para 2 famílias:
#   FONT_NUM*   — Barlow Condensed (números grandes, rótulos curtos em caixa alta)
#   FONT_TEXTO* — Inter (texto corrido, frases narrativas, labels longos)
# Sempre referenciar via constantes em vez de hard-coded em cada drawString.
FONT_NUM_BOLD       = "BarlowCondensed-Bold"
FONT_NUM_SEMIBOLD   = "BarlowCondensed-SemiBold"
FONT_NUM_REGULAR    = "BarlowCondensed-Regular"
FONT_TEXTO          = "Inter-Regular"
FONT_TEXTO_SEMIBOLD = "Inter-SemiBold"
FONT_TEXTO_BOLD     = "Inter-Bold"

# ─── Status de comparação (cor por percentil) ────────────────────────────────
# Threshold único para os cards estilo landing IFEM (verde / amarelo / vermelho).
# Município que supera ≥ STATUS_OK_PCT% dos demais → verde;
# entre STATUS_ALERTA_PCT% e STATUS_OK_PCT → amarelo; abaixo → vermelho.
STATUS_OK_PCT       = 60
STATUS_ALERTA_PCT   = 30

# ─── Constantes de layout ────────────────────────────────────────────────────

CARD_RADIUS    = 3       # raio dos cards
CARD_TOP_BAR   = 4       # altura da barra colorida no topo de cards
KPI_HEIGHT     = 58      # altura padrão do KPI box
ROW_HEIGHT     = 18      # altura de linha de tabela
QR_SIZE        = 140     # lado do QR code (pt)
QR_FILL_COLOR  = "#0E2447"

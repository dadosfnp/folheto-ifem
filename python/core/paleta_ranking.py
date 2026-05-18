"""
Mapeamento de posição (ranking) para a paleta FNP de 5 quintis.

Regra oficial (definida no IFEM):
  percentil_relativo = (total - rank) / total * 100
    ≤ 20% → Q1 (vermelho)
    ≤ 40% → Q2 (laranja)
    ≤ 60% → Q3 (amarelo)
    ≤ 80% → Q4 (verde claro)
    > 80% → Q5 (verde)

"Bem colocado" = recursos altos por habitante (Q5).
"Mal colocado" = recursos baixos por habitante (Q1).
"""
from .tokens import FNP_Q1, FNP_Q2, FNP_Q3, FNP_Q4, FNP_Q5, FNP_QUINTIS, FNP_DECIS


def cor_por_percentil(pos: int, total: int):
    """Recebe (posição, total) e retorna a cor FNP correspondente.
    Posição 1 = melhor (mais alto valor); total = pior."""
    if not total:
        return FNP_Q3
    pct = (total - pos) / total * 100
    if pct <= 20:   return FNP_Q1
    if pct <= 40:   return FNP_Q2
    if pct <= 60:   return FNP_Q3
    if pct <= 80:   return FNP_Q4
    return FNP_Q5


def cor_por_quintil(quintil_str: str):
    """Recebe '1º quintil' ... '5º quintil' e retorna a cor FNP correspondente."""
    if not quintil_str:
        return FNP_Q3
    s = str(quintil_str).strip()
    n = "".join(ch for ch in s if ch.isdigit())
    if not n:
        return FNP_Q3
    i = max(1, min(5, int(n))) - 1
    return FNP_QUINTIS[i]


def cor_por_decil(decil_str: str):
    """Recebe '1º decil' ... '10º decil' e retorna a cor FNP correspondente."""
    if not decil_str:
        return FNP_DECIS[4]
    s = str(decil_str).strip()
    n = "".join(ch for ch in s if ch.isdigit())
    if not n:
        return FNP_DECIS[4]
    i = max(1, min(10, int(n))) - 1
    return FNP_DECIS[i]

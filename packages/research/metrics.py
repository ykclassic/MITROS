from collections.abc import Sequence
from decimal import Decimal

def max_drawdown(equity: Sequence[Decimal], initial: Decimal) -> Decimal:
    peak = initial
    worst = Decimal("0")
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst

def win_rate(returns: Sequence[Decimal]) -> Decimal:
    if not returns:
        return Decimal("0")
    return Decimal(sum(r > 0 for r in returns)) / Decimal(len(returns))

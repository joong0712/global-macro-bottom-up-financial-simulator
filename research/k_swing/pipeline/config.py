"""K-SWING v24 fixed (preregistered) settings. See V24_PROTOCOL.md.

Changing any value here after results exist requires a new protocol version.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

MARCAP_REF = "94c138df4bf7376be8d28f979edb14020e2a547a"
DATA_YEARS = tuple(range(2016, 2026))  # 2016-17 warm-up only; 2026 is never read
LOCKED_FROM = pd.Timestamp("2026-01-01")

DEV = ("2018-01-02", "2022-12-29")
VALIDATION = ("2023-01-02", "2025-12-30")  # last signal is trimmed so exits stay <= 2025-12-30

HYPOTHESES = ("REV5", "HIGH52", "LOWVOL")
HORIZONS = (5, 10)

ADJUST_TOLERANCE = 0.001  # |base/prev_close - 1| above this is a corporate-action adjustment
LIMIT_BAND = 0.295        # within 0.5%p of the +/-30% daily price limit
EXCLUDED_DEPT_KEYWORDS = ("SPAC", "관리종목", "투자주의환기", "외국기업")
EXCLUDED_NAME_KEYWORDS = ("스팩", "리츠")
COMMON_SHARE_CODE = r"^\d{5}0$"

# Sell-side securities transaction tax incl. rural special tax, KOSPI = KOSDAQ totals.
# (start date inclusive, rate)
SELL_TAX_SCHEDULE = (
    ("1900-01-01", 0.0030),
    ("2019-05-30", 0.0025),
    ("2021-01-01", 0.0023),
    ("2023-01-01", 0.0020),
    ("2024-01-01", 0.0018),
    ("2025-01-01", 0.0015),
    ("2026-01-01", 0.0020),
)
COMMISSION = 0.00015  # each side
# (minimum 20-day average turnover in KRW, one-way slippage)
SLIPPAGE_TIERS = ((10e9, 0.0010), (3e9, 0.0020), (0.0, 0.0030))

BOOTSTRAP_BLOCK = 20
BOOTSTRAP_DRAWS = 5000
BOOTSTRAP_SEED = 20261123
NEWEY_WEST_LAG = 10
ALPHA = 0.05


@dataclass(frozen=True)
class Settings:
    top_n: int = 20
    min_turnover: float = 1e9        # 20-day average KRW turnover
    min_price: float = 1000.0
    min_active_days: int = 15         # of the last 20 sessions
    min_history: int = 252
    cost_multiplier: float = 1.0
    zero_cost: bool = False           # diagnostic only: no commission, slippage or tax

    def with_(self, **kwargs) -> "Settings":
        return replace(self, **kwargs)


PRIMARY = Settings()
SENSITIVITY = {
    "N10": PRIMARY.with_(top_n=10),
    "N50": PRIMARY.with_(top_n=50),
    "turnover_5e8": PRIMARY.with_(min_turnover=5e8),
    "turnover_3e9": PRIMARY.with_(min_turnover=3e9),
    "cost_x2": PRIMARY.with_(cost_multiplier=2.0),
}
GROSS = PRIMARY.with_(zero_cost=True)


def sell_tax(date: pd.Timestamp) -> float:
    rate = SELL_TAX_SCHEDULE[0][1]
    for start, value in SELL_TAX_SCHEDULE:
        if date >= pd.Timestamp(start):
            rate = value
    return rate


def slippage(avg_turnover: float) -> float:
    for floor, value in SLIPPAGE_TIERS:
        if avg_turnover >= floor:
            return value
    return SLIPPAGE_TIERS[-1][1]

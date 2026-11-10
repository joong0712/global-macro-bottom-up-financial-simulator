"""Historical execution sensitivity policy; no 2026, no certified PnL."""
from research.k_swing.real_execution_v08 import (
    FROZEN_FACTORS,TOPK,HORIZONS,COST_BPS
)


def test_fixed_scenario_matrix_and_no_selection_mining():
    assert len(FROZEN_FACTORS)==2
    assert TOPK==(3,10)
    assert HORIZONS==(5,10)
    assert COST_BPS==(20,50,100,200)
    assert "ta__atr_wilder_pct_7" in FROZEN_FACTORS

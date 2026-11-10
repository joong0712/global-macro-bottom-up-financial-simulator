"""The actual formula study may never open the 2023 or 2026 market data."""
from pathlib import Path
import pytest
from research.k_swing.candidate_train_eval_v08 import train_data


def test_missing_year_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        train_data(tmp_path,modulus=16)


def test_invalid_modulus_rejected(tmp_path):
    with pytest.raises(ValueError,match="modulus"):
        train_data(tmp_path,modulus=0)

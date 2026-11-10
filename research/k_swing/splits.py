"""Chronological training/validation/test with a label-overlap embargo."""
import pandas as pd


def assign_splits(panel: pd.DataFrame, calendar: pd.DatetimeIndex,
                  train_end: str | None = None, valid_end: str | None = None,
                  embargo_sessions: int = 10) -> tuple[pd.DataFrame, dict]:
    if len(calendar) < 60:
        raise ValueError("최소 60거래일 이상 필요합니다.")
    n = len(calendar)
    if train_end is None and valid_end is None:
        cut_train, cut_valid = int(n * .60) - 1, int(n * .80) - 1
    elif train_end is not None and valid_end is not None:
        a, b = pd.Timestamp(train_end), pd.Timestamp(valid_end)
        cut_train = calendar.searchsorted(a, side="right") - 1
        cut_valid = calendar.searchsorted(b, side="right") - 1
    else:
        raise ValueError("--train-end와 --valid-end를 함께 지정해야 합니다.")
    if not (0 <= cut_train < cut_valid < n - 1):
        raise ValueError("시계열 분할 경계가 잘못되었습니다.")
    row_ix = panel["date"].map(pd.Series(range(n), index=calendar))
    if row_ix.isna().any():
        raise ValueError("거래일 달력에 없는 데이터가 있습니다.")
    i = row_ix.astype(int)
    train = i + embargo_sessions <= cut_train
    validation = (i > cut_train) & (i + embargo_sessions <= cut_valid)
    test = (i > cut_valid) & (i + embargo_sessions < n)
    out = panel.copy()
    out["split"] = "embargo_or_incomplete"
    out.loc[train, "split"] = "train"
    out.loc[validation, "split"] = "validation"
    out.loc[test, "split"] = "test"
    metadata = {
        "train_end": calendar[cut_train].strftime("%Y-%m-%d"),
        "validation_end": calendar[cut_valid].strftime("%Y-%m-%d"),
        "embargo_sessions": embargo_sessions,
        "split_observations": {k: int(v) for k, v in out["split"].value_counts().items()},
    }
    return out, metadata

"""K-SWING v25 runner (V25_PROTOCOL.md).

Stage 1 (default): seen-data pre-check on 2018-2025. Never reads 2026.
Stage 2: --open-2026-holdout with KSWING_OPEN_2026_HOLDOUT=ONE_SHOT_APPROVED and a stage-1 JSON.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, panel as panel_mod, signals, stats
from .buffer import BUFFER_K, TOP_N, run_buffer

TESTS = {"V25A": "HIGH52", "V25B": "LOWVOL"}
PRECHECK = ("2018-01-02", "2025-12-29")
SUBPERIODS = {"2018_22": ("2018-01-01", "2022-12-31"), "2023_25": ("2023-01-01", "2025-12-31")}
HOLDOUT_TOKEN = "ONE_SHOT_APPROVED"
HOLDOUT_ALPHA = 0.10


def describe(res) -> dict:
    out = stats.summarize(res.daily, res.trades)
    out["counters"] = res.counters
    out["turnover_one_way_per_year"] = res.turnover_one_way_per_year
    if len(res.trades):
        held = (pd.to_datetime(res.trades["exit_date"]) - pd.to_datetime(res.trades["entry_date"])).dt.days
        out["avg_calendar_days_held"] = float(held.mean())
    out["avg_names"] = float(res.daily["names"].mean())
    return out


def sub(daily: pd.DataFrame, start: str, end: str) -> dict:
    d = daily.loc[start:end]
    return {"excess_mean_ann_pct": 100 * 252 * d["excess"].mean(),
            "strategy_mean_ann_pct": 100 * 252 * d["strategy"].mean(), "sessions": len(d)}


def load(marcap_dir: Path, years, allow_holdout=False):
    files = [marcap_dir / f"marcap-{y}.parquet" for y in years]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    return panel_mod.build_panel(panel_mod.read_marcap(files, allow_holdout=allow_holdout))


def precheck(pnl) -> dict:
    eligible = panel_mod.universe(pnl, config.PRIMARY)
    turnover = panel_mod.average_turnover(pnl)
    report = {}
    for test, score_name in TESTS.items():
        score = signals.SCORES[score_name](pnl)
        main = run_buffer(pnl, score, eligible, turnover, *PRECHECK, mode="close")
        entry = {"main_close_entry": describe(main),
                 "subperiods": {k: sub(main.daily, *v) for k, v in SUBPERIODS.items()}}
        gross = run_buffer(pnl, score, eligible, turnover, *PRECHECK, mode="close", zero_cost=True)
        entry["zero_cost_close_entry_excess_ann_pct"] = 100 * 252 * gross.daily["excess"].mean()
        nxt = run_buffer(pnl, score, eligible, turnover, *PRECHECK, mode="next_open")
        entry["next_open_same_buffer"] = {"excess_mean_ann_pct": 100 * 252 * nxt.daily["excess"].mean(),
                                          "subperiods": {k: sub(nxt.daily, *v) for k, v in SUBPERIODS.items()}}
        s = entry["main_close_entry"]
        entry["passes_precheck"] = bool(
            s["excess_mean_ann_pct"] > 0 and all(v["excess_mean_ann_pct"] > 0 for v in entry["subperiods"].values()))
        report[test] = entry
    passed = [k for k, v in report.items() if v["passes_precheck"]]
    return {"stage": "1_seen_data_precheck_not_evidence", "tests": report, "passed": passed,
            "decision": "ELIGIBLE_FOR_2026_HOLDOUT_IF_USER_APPROVES" if passed else "NO_GO_DO_NOT_OPEN_2026",
            "settings": {"top_n": TOP_N, "buffer_k": BUFFER_K, "fill": "T close (after-hours closing price)"},
            "holdout_2026_read": False}


def holdout(pnl, passed: list[str]) -> dict:
    sessions_2026 = pnl.sessions[pnl.sessions >= config.LOCKED_FROM]
    if len(sessions_2026) < 40:
        raise ValueError("too few 2026 sessions")
    start, end = str(sessions_2026[0].date()), str(sessions_2026[-1].date())
    eligible = panel_mod.universe(pnl, config.PRIMARY)
    turnover = panel_mod.average_turnover(pnl)
    results = {}
    for test in passed:
        res = run_buffer(pnl, signals.SCORES[TESTS[test]](pnl), eligible, turnover, start, end, mode="close")
        results[test] = describe(res)
    holm = stats.holm({k: v["excess_p_bootstrap"] for k, v in results.items()}, alpha=HOLDOUT_ALPHA)
    passing = [k for k, v in results.items() if holm[k]["reject"] and v["excess_mean_ann_pct"] > 0
               and v["strategy_mean_ann_pct"] > 0]
    return {"stage": "2_holdout_2026_one_shot", "window": [start, end], "tests": results, "holm": holm,
            "passed": passed, "weak_evidence_pass": passing,
            "decision": "WEAK_EVIDENCE_NEXT_PAPER_TRADING" if passing else "NO_GO"}


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 6)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--marcap-dir", type=Path, required=True)
    ap.add_argument("--public-output", type=Path, required=True)
    ap.add_argument("--open-2026-holdout", action="store_true")
    ap.add_argument("--precheck-json", type=Path)
    a = ap.parse_args(argv)
    a.public_output.mkdir(parents=True, exist_ok=True)
    if not a.open_2026_holdout:
        report = precheck(load(a.marcap_dir, config.DATA_YEARS))
        name = "v25_precheck.json"
    else:
        if os.environ.get("KSWING_OPEN_2026_HOLDOUT") != HOLDOUT_TOKEN:
            raise SystemExit("2026 holdout is locked: set KSWING_OPEN_2026_HOLDOUT=ONE_SHOT_APPROVED")
        if a.precheck_json is None:
            raise SystemExit("--precheck-json from stage 1 is required")
        passed = json.loads(a.precheck_json.read_text())["passed"]
        if not passed:
            raise SystemExit("stage 1 passed nothing; protocol forbids opening 2026")
        marker = a.public_output / "HOLDOUT_2026_OPENED"
        if marker.exists():
            raise SystemExit("2026 holdout already opened once; protocol forbids a second look")
        marker.write_text("opened\n")
        report = holdout(load(a.marcap_dir, (*config.DATA_YEARS, 2026), allow_holdout=True), passed)
        name = "v25_holdout_2026.json"
    report = clean(report)
    (a.public_output / name).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({"decision": report["decision"], "passed": report.get("passed")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

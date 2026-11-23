"""K-SWING v24 runner: python -m research.k_swing.pipeline.run --marcap-dir DIR --private-output DIR --public-output DIR

Reads marcap-YYYY.parquet (2016-2025) unchanged, never 2026. Private output holds trade
lists; public output holds aggregate JSON/Markdown only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, config, panel as panel_mod, signals, stats


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def evaluate(pnl: panel_mod.Panel, settings: config.Settings, periods: dict[str, tuple[str, str]],
             private: Path | None, label: str) -> dict:
    eligible = panel_mod.universe(pnl, settings)
    turnover = panel_mod.average_turnover(pnl)
    data_end = pd.Timestamp(config.VALIDATION[1])
    out: dict = {"universe_median_names": float(eligible.loc[config.DEV[0]:].sum(axis=1).median())}
    for hyp in config.HYPOTHESES:
        score = signals.SCORES[hyp](pnl)
        picks = signals.select(score, eligible, settings.top_n)
        for h in config.HORIZONS:
            for period, (start, end) in periods.items():
                res = backtest.run(pnl, picks, h, start, end, eligible, turnover, settings, data_end=data_end)
                key = f"{hyp}_H{h}"
                summary = stats.summarize(res.daily, res.trades)
                summary["counters"] = res.counters
                out.setdefault(period, {})[key] = summary
                if private is not None:
                    res.trades.to_csv(private / f"trades_{label}_{period}_{key}.csv.gz", index=False)
                    res.daily.to_csv(private / f"daily_{label}_{period}_{key}.csv.gz")
    return out


def verdict(primary: dict) -> dict:
    dev = primary["dev"]
    dev_holm = stats.holm({k: v["excess_p_bootstrap"] for k, v in dev.items()})
    dev_pass = [k for k, v in dev_holm.items() if v["reject"] and dev[k]["excess_mean_ann_pct"] > 0]
    val = primary["validation"]
    val_holm = stats.holm({k: val[k]["excess_p_bootstrap"] for k in dev_pass}) if dev_pass else {}
    val_pass = []
    for k in dev_pass:
        v = val[k]
        years = v["yearly_pct"]
        positive_years = sum(1 for y in (2023, 2024, 2025) if y in years and years[y]["excess_mean_ann"] > 0)
        if (val_holm[k]["reject"] and v["excess_mean_ann_pct"] > 0 and positive_years >= 2
                and v["strategy_mean_ann_pct"] > 0):
            val_pass.append(k)
    return {"dev_holm": dev_holm, "dev_pass": dev_pass, "validation_holm": val_holm,
            "validation_pass": val_pass,
            "decision": ("ASK_USER_TO_OPEN_2026_HOLDOUT_ONCE" if val_pass else "NO_GO"),
            "holdout_2026_read": False}


def markdown(report: dict) -> str:
    p = report["primary"]
    lines = ["# K-SWING v24 aggregate results (generated)", "",
             f"Decision: **{report['verdict']['decision']}**", "",
             "| Period | Test | Net excess ann. % | 95% CI | p (boot) | Holm p | NW t | Strategy CAGR % | EW universe CAGR % | Trades | Cost/trade % |",
             "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    holm_by_period = {"dev": report["verdict"]["dev_holm"], "validation": report["verdict"]["validation_holm"]}
    for period in ("dev", "validation"):
        for key, s in p[period].items():
            holm = holm_by_period[period].get(key, {}).get("p_holm")
            lo, hi = s["excess_ci95_ann_pct"]
            lines.append(
                f"| {period} | {key} | {s['excess_mean_ann_pct']:+.2f} | [{lo:+.1f}, {hi:+.1f}] | {s['excess_p_bootstrap']:.3f} | "
                f"{'-' if holm is None else f'{holm:.3f}'} | {s['excess_t_newey_west']:+.2f} | {s['strategy_cagr_pct']:+.2f} | "
                f"{s['benchmark_cagr_pct']:+.2f} | {s['trades']} | {s.get('cost_per_trade_pct', float('nan')):.2f} |")
    g = report["gross_diagnostic"]
    lines += ["", "## Zero-cost diagnostic (excess ann. % before any cost; not used for the decision)", "",
              "| Period | " + " | ".join(p["dev"]) + " |", "|---|" + "---:|" * len(p["dev"])]
    for period in ("dev", "validation"):
        lines.append(f"| {period} | " + " | ".join(f"{g[period][k]['excess_mean_ann_pct']:+.2f}" for k in p["dev"]) + " |")
    lines += ["", "## Sensitivity (net excess ann. %, not used for the decision)", "",
              "| Setting | Period | " + " | ".join(p["dev"]) + " |", "|---|---|" + "---:|" * len(p["dev"])]
    for name, block in report["sensitivity"].items():
        for period in ("dev", "validation"):
            lines.append(f"| {name} | {period} | " + " | ".join(
                f"{block[period][k]['excess_mean_ann_pct']:+.2f}" for k in p["dev"]) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--marcap-dir", type=Path, required=True)
    ap.add_argument("--private-output", type=Path, required=True)
    ap.add_argument("--public-output", type=Path, required=True)
    ap.add_argument("--skip-sensitivity", action="store_true")
    args = ap.parse_args(argv)

    files = [args.marcap_dir / f"marcap-{y}.parquet" for y in config.DATA_YEARS]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    args.private_output.mkdir(parents=True, exist_ok=True)
    args.public_output.mkdir(parents=True, exist_ok=True)

    raw = panel_mod.read_marcap(files)
    pnl = panel_mod.build_panel(raw)
    del raw
    periods = {"dev": config.DEV, "validation": config.VALIDATION}

    adj_events = int((pnl.factor.loc[config.DEV[0]:] != 1.0).to_numpy().sum())
    big_moves = panel_mod.daily_adjusted_returns(pnl).abs().gt(0.31).to_numpy().sum()
    report = {
        "protocol": "V24_PROTOCOL.md",
        "source": {"marcap_ref": config.MARCAP_REF,
                   "files": {f.name: sha256(f) for f in files}},
        "data_checks": {"sessions": len(pnl.sessions), "codes": pnl.close.shape[1],
                        "adjustment_events_2018_2025": adj_events,
                        "adjusted_daily_moves_over_31pct": int(big_moves)},
        "primary": evaluate(pnl, config.PRIMARY, periods, args.private_output, "primary"),
    }
    report["verdict"] = verdict(report["primary"])
    report["gross_diagnostic"] = evaluate(pnl, config.GROSS, periods, None, "gross")
    report["sensitivity"] = {} if args.skip_sensitivity else {
        name: evaluate(pnl, s, periods, None, name) for name, s in config.SENSITIVITY.items()}

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.floating, float)):
            return None if not np.isfinite(o) else round(float(o), 6)
        if isinstance(o, np.integer):
            return int(o)
        return o

    report = clean(report)
    (args.public_output / "v24_aggregate.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    (args.public_output / "v24_aggregate.md").write_text(markdown(report))
    print(json.dumps({"decision": report["verdict"]["decision"], "dev_pass": report["verdict"]["dev_pass"],
                      "validation_pass": report["verdict"]["validation_pass"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

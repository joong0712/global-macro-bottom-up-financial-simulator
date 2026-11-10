"""K-SWING research CLI. Run with python -m research.k_swing.cli --help."""
import argparse
import json
from pathlib import Path

from .data import load_prices, load_calendar
from .targets import build_panel
from .splits import assign_splits
from .evaluation import run_evaluation
from .factors import FACTOR_NAMES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="K-SWING v0.1 factor analysis (research only)")
    parser.add_argument("--input", required=True, help="CSV: date,ticker,open,high,low,close,volume,turnover")
    parser.add_argument("--calendar", help="verified KRX session calendar (date column)")
    parser.add_argument("--output", required=True, help="output directory for CSV/JSON")
    parser.add_argument("--train-end", help="last training-calendar date (YYYY-MM-DD)")
    parser.add_argument("--valid-end", help="last validation-calendar date (YYYY-MM-DD)")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--roundtrip-bps", type=float, default=20., help="approximate total buy+sell costs")
    parser.add_argument("--min-cross-section", type=int, default=5)
    parser.add_argument("--min-train-ic-days", type=int, default=20)
    args = parser.parse_args(argv)
    if args.top_k < 1 or args.min_cross_section < 5 or args.roundtrip_bps < 0 or args.min_train_ic_days < 1:
        parser.error("top-k>=1, min-cross-section>=5, roundtrip-bps>=0, min-train-ic-days>=1")

    raw = load_prices(args.input)
    calendar = load_calendar(args.calendar, raw)
    panel = build_panel(raw, calendar)
    panel, splits = assign_splits(panel, calendar, args.train_end, args.valid_end, embargo_sessions=10)
    metrics, ranking = run_evaluation(
        panel, top_k=args.top_k, roundtrip_bps=args.roundtrip_bps,
        min_cross_section=args.min_cross_section, min_train_ic_days=args.min_train_ic_days,
    )
    dest = Path(args.output)
    dest.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(dest / "factor_metrics.csv", index=False, encoding="utf-8-sig")
    ranking.to_csv(dest / "train_factor_ranking.csv", index=False, encoding="utf-8-sig")
    panel.to_csv(dest / "research_panel.csv", index=False, encoding="utf-8-sig")
    summary = {
        "project": "K-SWING v0.1 exploratory research (not a trading system)",
        "input_path": str(args.input),
        "calendar_source": "provided" if args.calendar else "provisional_union_of_observed_dates",
        "symbol_count": int(raw["ticker"].nunique()),
        "observations": len(raw),
        "calendar_sessions": len(calendar),
        "date_from": calendar[0].strftime("%Y-%m-%d"),
        "date_to": calendar[-1].strftime("%Y-%m-%d"),
        "factors": list(FACTOR_NAMES),
        "split": splits,
        "label_definition": "Signal T close; enter T+1 open; exit T+H close. Invalid/missing session => unlabeled.",
        "costs": "Approximate total roundtrip bps subtracted from cohort mean return only.",
        "warnings": [
            "This is NOT an executable portfolio backtest: no fill model, capital, overlap, or tax-by-period calculation.",
            "Historical KRX calendar and survivor-free universe should be supplied for actual research.",
            "Corporate action and adjusted price methodology must be verified.",
            "Repeated tests on validation/test periods cause selection bias.",
            "Synthetic demo results have no predictive meaning for real markets.",
            "Accounting point-in-time joins are not supported by this CSV contract.",
        ],
    }
    (dest / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "output": str(dest),
        "symbols": summary["symbol_count"],
        "sessions": summary["calendar_sessions"],
        "factors": len(FACTOR_NAMES),
        "split_observations": splits["split_observations"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

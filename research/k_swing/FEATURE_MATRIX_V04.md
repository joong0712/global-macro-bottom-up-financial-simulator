# K-SWING v0.4 — comprehensive technical feature matrix

New `factor_matrix_v04.py` connects all **170** expanded causal technical features (plus **18** previously studied baseline features) to the screened market data and existing 5/10-session forward-return label generator.

Run from the repository root on YOUR authorized local machine:

    python -m research.k_swing.factor_matrix_v04 \
      --prices research/k_swing/_local_data/_private/kswing_screened_2019.csv.gz research/k_swing/_local_data/_private/kswing_screened_2020.csv.gz \
      --calendar research/k_swing/_local_data/_private/krx_observed_sessions.csv \
      --output research/k_swing/_local_data/feature_matrix --signal-start 2019-01-01 --signal-end 2020-12-31

Warm-up: include earlier screened annual files (e.g. 2017–2018) when starting research in 2019; without past context, 200-day moving averages and 26-session Ichimoku cloud will be unavailable initially. Include subsequent periods solely for forward return labels; **never use future OHLCV in any T feature**.

Outputs remain in gitignored private storage as `factor_matrix_part_XXXX.parquet` plus a JSON manifest.

This is the *input matrix* for research, NOT an evaluated or tradable signal. The 2026 signal dates are **locked by default** and require an explicit `--allow-2026-confirmation` flag in a later finalized research plan. Opening 2026 while tuning invalidates its confirmation value.

Security-point-in-time universes, corporate-action-adjusted return series and actual foreign/institutional/macro data must still be sourced and validated separately.

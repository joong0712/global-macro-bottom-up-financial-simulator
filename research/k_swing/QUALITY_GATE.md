# K-SWING v0.2 — conservative quality gate

The code deliberately detects **candidates, not confirmed corporate actions or delistings**.
All raw market data and event-level records remain in a local gitignored folder.

## Local use

Run these commands from repository root:

    python -m pip install -r research/k_swing/requirements.txt
    python -m pytest -q research/k_swing/tests
    python -m research.k_swing.marcap_ingest --start-year 2017 --end-year 2026 --keep-raw --output research/k_swing/_local_data
    python -m research.k_swing.quality_audit --start-year 2017 --end-year 2026 --data research/k_swing/_local_data

Outputs: private/kswing_screened_YYYY.csv.gz (same 8 OHLCV columns + unsafe_session) and market_structure_quality.json.
Input snapshots must not be published. Raw/yearly/derived price data can be deleted after verification.

## Guardrails

- Consecutive trading-date close returns exceeding 35% are flagged, not called splits.
- Consecutive outstanding share counts that change by over 25% are flagged.
- Name or market changes are flagged as identity-continuity risks.
- A suspect session invalidates indicators with rolling history up to 26 sessions and any 5/10-session future return window crossing that date.
- Missing symbol observations remain gaps; they are not forward-filled.
- Comparing observed dates to XKRX is NOT equivalent to official calendar certification. Flagged mismatch must be checked against official KRX/KIS trading days.
- Securities disappearing before the end are possible inactive symbols, not verified delisted securities.
- Historical common stock, corporate action adjustments and executable portfolios remain unverified.

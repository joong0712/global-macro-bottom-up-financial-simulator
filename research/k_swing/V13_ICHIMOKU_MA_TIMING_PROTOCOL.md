# K-SWING v1.3 — Ichimoku and moving-average timing

**Exploratory only. No verified investable profit.** Test exactly five new entry conditions using only Ichimoku 9/26/52 and SMA 5/20/60, plus the previous v1.1 VCR+trend control.

## Entry on signal-day T close

| Frozen method | Signal rule |
|---|---|
| ichi_cloud_breakout | Close crosses above the upper edge of the *visible* cloud; Tenkan > Kijun and displayed cloud A >= B |
| ichi_kijun_reclaim | Close crosses above Kijun 26 and sits above visible cloud; Tenkan >= Kijun |
| ma_5x20 | SMA5 crosses above SMA20; SMA20 > SMA60 and close > SMA60 |
| ma20_reclaim | Close recovers SMA20 from below; SMA20>SMA60 and SMA60 has risen across 5 sessions |
| ichi_ma_confirm | Same cloud breakout, also SMA20>SMA60 and close>SMA20 |
| vcr_trend_control | Existing VCR compressed breakout, 60-session gain >=10%, close >=80% of previous 252-session highest high; same 253-safe-session gate |

### Very important: no look-ahead from Ichimoku

Tenkan = midpoint(highest high, lowest low) over last 9 bars. Kijun likewise over 26. Senkou A=(Tenkan+Kijun)/2 and Senkou B=52-bar midpoint. Both are drawn **26 sessions into the future**, so the cloud displayed at day T is calculated from values **26 sessions before T**, not from future days. The algorithm uses the past-shifted displayed cloud at T; Chikou is excluded as a predictive feature. Unit tests ensure changing tomorrow cannot change yesterday's cloud or signal.

## Independent, frozen 6-by-2-by-2 timing matrix

- Six methods in parallel jobs. For each one: entry at T+1 **or T+2** opening print, chosen mechanically before seeing any T+1 price action.
- For each entry: simulate a maximum holding of **5 or 10 actual trading sessions from entry**, exiting at that last session close unless -3% stop or +8% target occurs first.
- T+1/T+2 entry print is simulated, never guaranteed. If both stop and target touch one OHLC bar, stop takes precedence; overnight stop gaps fill at opening print. Round-trip trading friction 50bp assumption.
- Common 100m KRW cash, 5m KRW per purchase, max 10 open holdings, max top 10 signals per session.
- Separate 2019-01-01..2020-12-15 and 2021-01-01..2022-12-15 experiment windows. **Both previously inspected, neither clean OOS.** 2017–2018 input warmup only, full history must stop 2022. No 2023–2026 access.
- Deterministic 1/16 ticker-hash sample of screened Korean prices; price >=1000 KRW, T turnover and preceding 20-session mean turnover each >= 3bn KRW, 253 consecutive screened OHLCV market sessions.
- Eight cases per method, 48 aggregate outcomes. Missing holding data or unresolved suspicious corporate actions blocks PnL and MDD; do not drop questionable trades after observing outcomes.

## Decision policy

Require both exploratory periods have positive hypothetical **after-cost account return**, >=30 closed trades each, and zero blocked held position, otherwise **NO PROFITABLE ENTRY TIMING**. Rank surviving entry-delay/holding combinations by their worse subperiod net return, examine MDD and exposure stability second. This is only a hypothesis comparison: lower cash exposure could explain better account returns. Further clean security universe, real corporate actions, delistings, market execution and effective fees/taxes and one-shot independent data confirmation are needed before any live order.

Technical reference: https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/ichimoku-cloud

Historical charts do not prove alpha; independent predictive performance is unknown.

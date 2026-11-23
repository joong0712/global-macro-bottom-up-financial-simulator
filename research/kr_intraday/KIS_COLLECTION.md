# Korean historical minute-data acquisition

Official source: KIS [domestic stock historical intraday API](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_time_dailychartprice/inquire_time_dailychartprice.py).

- Endpoint: `/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice`
- TR: `FHKST03010230`
- Real-account API documentation says max 120 rows per call and up to one year retained, **not guaranteed** for every symbol/date.
- Do not use the same-day-only endpoint `inquire-time-itemchartprice` for historical research.

## Local execution

Use a KIS account with API access, and store secrets in local environment variables, not GitHub.

```bash
export KIS_APP_KEY='YOUR_KEY'
export KIS_APP_SECRET='YOUR_SECRET'
python -m research.kr_intraday.collect_kis --symbols 005930 000660 --start 2026-11-16 --end 2026-11-20
```

The collector stores raw responses under `data/private/kis_minutes/` and skips existing files. Four intraday cutoffs are queried per symbol/day. **This is a prototype, not a proven complete downloader**: 120-row windows may leave gaps, response timestamps may denote bar end rather than start, KIS may return holidays/no data, and adjustments must be verified. Run the completeness audit only after a verified raw-to-normalized conversion. No credentials or downloaded data are in the repository. Check the provider's API and storage terms before collecting at scale.

Do not upload private market-data files or credentials to GitHub. Do not make live orders.

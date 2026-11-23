"""Download raw historical minute responses from official KIS API.

Requires user-supplied credentials in environment; never commits tokens or
market data. Saves raw responses because minute timestamp conventions and
adjustments must be audited before normalization.
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HOST = "https://openapi.koreainvestment.com:9443"
ENDPOINT = "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
TR_ID = "FHKST03010230"


def request_json(url, *, headers=None, body=None):
    req = urllib.request.Request(url, headers=headers or {}, data=body)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def access_token(app_key, app_secret):
    response = request_json(
        HOST + "/oauth2/tokenP",
        headers={"content-type": "application/json"},
        body=json.dumps({"grant_type": "client_credentials",
                         "appkey": app_key, "appsecret": app_secret}).encode(),
    )
    return response["access_token"]


def fetch_page(symbol, day, hhmmss, token, app_key, app_secret):
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": symbol,
        "FID_INPUT_HOUR_1": hhmmss,
        "FID_INPUT_DATE_1": day,
        "FID_PW_DATA_INCU_YN": "N",
        "FID_FAKE_TICK_INCU_YN": "",
    }
    url = HOST + ENDPOINT + "?" + urllib.parse.urlencode(params)
    return request_json(url, headers={
        "authorization": "Bearer " + token,
        "appkey": app_key, "appsecret": app_secret,
        "tr_id": TR_ID, "custtype": "P",
    })


def collect(symbols, days, directory, delay=0.5):
    app_key = os.environ.get("KIS_APP_KEY")
    app_secret = os.environ.get("KIS_APP_SECRET")
    if not app_key or not app_secret:
        raise RuntimeError("Set KIS_APP_KEY and KIS_APP_SECRET locally; never commit credentials")
    token = access_token(app_key, app_secret)
    directory = Path(directory)
    for day in days:
        for symbol in symbols:
            if len(symbol) != 6 or not symbol.isdigit():
                raise ValueError("symbol must be a six-digit Korean stock code")
            folder = directory / day
            folder.mkdir(parents=True, exist_ok=True)
            for hhmmss in ("110000", "130000", "150000", "153000"):
                path = folder / f"{symbol}_{hhmmss}.json"
                if path.exists():
                    continue
                response = fetch_page(symbol, day, hhmmss, token, app_key, app_secret)
                if str(response.get("rt_cd", "0")) != "0":
                    raise RuntimeError(f"KIS returned error for {symbol}/{day}/{hhmmss}: {response.get('msg_cd')} {response.get('msg1')}")
                path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
                print("saved", path)
                time.sleep(delay)


def dates(start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first:
        raise ValueError("end before start")
    if (last-first).days > 31:
        raise ValueError("limit each run to at most 32 calendar days")
    current = first
    while current <= last:
        if current.weekday() < 5:
            yield current.strftime("%Y%m%d")
        current += timedelta(days=1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--output-dir", default="data/private/kis_minutes")
    p.add_argument("--delay", type=float, default=0.5)
    a = p.parse_args()
    if a.delay < 0.2:
        raise ValueError("delay must be >= 0.2 seconds")
    collect(a.symbols, dates(a.start, a.end), a.output_dir, a.delay)


if __name__ == "__main__":
    main()

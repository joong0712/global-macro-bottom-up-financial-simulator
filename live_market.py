"""KIS 국내주식과 Twelve Data 환율 실시간 WebSocket 수신기."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import websocket
from dotenv import load_dotenv


load_dotenv()

KST = ZoneInfo("Asia/Seoul")
KIS_INTRADAY_URL = (
    "/uapi/domestic-stock/v1/quotations/"
    "inquire-time-itemchartprice"
)
KIS_CURRENT_PRICE_URL = (
    "/uapi/domestic-stock/v1/quotations/inquire-price"
)
_KIS_REST_LOCK = threading.Lock()
_KIS_REST_TOKEN: str | None = None
_KIS_REST_TOKEN_EXPIRES_AT: datetime | None = None


def _kis_credentials() -> tuple[str, str]:
    app_key = os.getenv("KIS_APP_KEY") or os.getenv("APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET") or os.getenv("APP_SECRET")
    if not app_key or not app_secret:
        raise ValueError("KIS_APP_KEY와 KIS_APP_SECRET을 설정해 주세요.")
    return app_key, app_secret


def _kis_rest_base_url() -> str:
    environment = os.getenv("KIS_ENV", "prod").strip().lower()
    if environment in {"demo", "vps", "virtual", "mock"}:
        return "https://openapivts.koreainvestment.com:29443"
    return "https://openapi.koreainvestment.com:9443"


def _kis_rest_access_token() -> str:
    """프로세스 안에서 재사용하는 KIS REST 접근토큰을 반환한다."""
    global _KIS_REST_TOKEN, _KIS_REST_TOKEN_EXPIRES_AT
    now = datetime.now(KST)
    with _KIS_REST_LOCK:
        if (
            _KIS_REST_TOKEN
            and _KIS_REST_TOKEN_EXPIRES_AT
            and now < _KIS_REST_TOKEN_EXPIRES_AT - timedelta(minutes=1)
        ):
            return _KIS_REST_TOKEN

        app_key, app_secret = _kis_credentials()
        response = requests.post(
            f"{_kis_rest_base_url()}/oauth2/tokenP",
            headers={"content-type": "application/json"},
            json={
                "grant_type": "client_credentials",
                "appkey": app_key,
                "appsecret": app_secret,
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()
        token = result.get("access_token")
        if not token:
            raise RuntimeError(
                result.get("error_description", "KIS 접근토큰 발급 실패")
            )
        expires_in = int(result.get("expires_in", 86_400))
        _KIS_REST_TOKEN = token
        _KIS_REST_TOKEN_EXPIRES_AT = now + timedelta(seconds=expires_in)
        return token


def _request_kis_intraday_page(
    stock_code: str,
    input_time: str,
) -> list[dict]:
    app_key, app_secret = _kis_credentials()
    response = requests.get(
        f"{_kis_rest_base_url()}{KIS_INTRADAY_URL}",
        headers={
            "authorization": f"Bearer {_kis_rest_access_token()}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHKST03010200",
            "custtype": "P",
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_HOUR_1": input_time,
            "FID_PW_DATA_INCU_YN": "Y",
            "FID_ETC_CLS_CODE": "",
        },
        timeout=15,
    )
    response.raise_for_status()
    result = response.json()
    if str(result.get("rt_cd", "0")) != "0":
        raise RuntimeError(result.get("msg1", "KIS 당일 분봉 조회 실패"))
    return result.get("output2") or []


def get_kis_intraday_stock_ohlc(stock_code: str) -> pd.DataFrame:
    """KIS에서 최근 영업일의 당일 1분 OHLC를 시간순으로 반환한다.

    공식 API가 한 번에 최대 30건만 반환하므로 가장 최근 시점부터
    09:00까지 역방향으로 이어서 조회한다. 전일 분봉은 제공되지 않는다.
    """
    stock_code = stock_code.strip()
    if not stock_code:
        raise ValueError("종목코드가 필요합니다.")

    rows: list[dict] = []
    input_time = "160000"
    previous_oldest: str | None = None
    is_demo = _kis_rest_base_url().startswith("https://openapivts")

    # 09:00~16:00은 양 끝을 포함하면 최대 421개 분 시점이므로
    # 페이지당 30건 기준 최대 15페이지가 필요하다.
    for _ in range(15):
        page = _request_kis_intraday_page(stock_code, input_time)
        if not page:
            break
        rows.extend(page)
        times = sorted(
            str(row.get("stck_cntg_hour", ""))
            for row in page
            if str(row.get("stck_cntg_hour", "")).isdigit()
        )
        if not times:
            break
        oldest = times[0].zfill(6)
        if oldest <= "090000" or oldest == previous_oldest:
            break
        previous_oldest = oldest
        next_time = datetime.strptime(oldest, "%H%M%S") - timedelta(minutes=1)
        input_time = next_time.strftime("%H%M%S")
        time.sleep(0.55 if is_demo else 0.07)

    if not rows:
        return pd.DataFrame(columns=["날짜", "시가", "고가", "저가", "종가"])

    frame = pd.DataFrame(rows)
    required = {
        "stck_bsop_date",
        "stck_cntg_hour",
        "stck_oprc",
        "stck_hgpr",
        "stck_lwpr",
        "stck_prpr",
    }
    if not required.issubset(frame.columns):
        raise RuntimeError("KIS 분봉 응답 형식이 예상과 다릅니다.")

    frame["날짜"] = pd.to_datetime(
        frame["stck_bsop_date"].astype(str)
        + frame["stck_cntg_hour"].astype(str).str.zfill(6),
        format="%Y%m%d%H%M%S",
        errors="coerce",
    )
    frame = frame.rename(
        columns={
            "stck_oprc": "시가",
            "stck_hgpr": "고가",
            "stck_lwpr": "저가",
            "stck_prpr": "종가",
        }
    )
    for column in ("시가", "고가", "저가", "종가"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    latest_business_date = frame["날짜"].dt.date.max()
    return (
        frame.loc[frame["날짜"].dt.date.eq(latest_business_date)]
        [["날짜", "시가", "고가", "저가", "종가"]]
        .dropna()
        .drop_duplicates("날짜", keep="first")
        .sort_values("날짜")
        .reset_index(drop=True)
    )


def get_kis_stock_snapshot(stock_code: str) -> dict[str, float | None]:
    """KIS 현재가 조회에서 시뮬레이션용 종목 기본정보를 반환한다."""
    stock_code = stock_code.strip()
    if not stock_code:
        raise ValueError("종목코드가 필요합니다.")

    app_key, app_secret = _kis_credentials()
    response = requests.get(
        f"{_kis_rest_base_url()}{KIS_CURRENT_PRICE_URL}",
        headers={
            "authorization": f"Bearer {_kis_rest_access_token()}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHKST01010100",
            "custtype": "P",
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        },
        timeout=15,
    )
    response.raise_for_status()
    result = response.json()
    if str(result.get("rt_cd", "0")) != "0":
        raise RuntimeError(result.get("msg1", "KIS 종목 기본정보 조회 실패"))
    output = result.get("output") or {}

    def numeric(field: str) -> float | None:
        value = pd.to_numeric(output.get(field), errors="coerce")
        return float(value) if pd.notna(value) else None

    return {
        "listed_shares": numeric("lstn_stcn"),
        "price": numeric("stck_prpr"),
        "market_cap_100m_krw": numeric("hts_avls"),
    }


def _kis_reconnect_delay(backoff: int) -> int:
    """국내 장외에는 KIS 재접속 빈도를 낮춘다."""
    now = datetime.now(KST)
    minutes = now.hour * 60 + now.minute
    is_market_window = (
        now.weekday() < 5
        and 8 * 60 + 20 <= minutes <= 16 * 60 + 10
    )
    return backoff if is_market_window else max(300, backoff)


@dataclass(frozen=True)
class LivePrice:
    price: float
    received_at: datetime
    change: float | None = None
    change_rate: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None


@dataclass(frozen=True)
class MarketState:
    label: str
    detail: str
    is_live: bool = False


def _age_text(received_at: datetime, now: datetime) -> str:
    age = max(0, int((now - received_at).total_seconds()))
    if age < 3:
        return "방금 수신"
    if age < 60:
        return f"{age}초 전 수신"
    if received_at.date() == now.date():
        return f"{age // 60}분 전 수신"
    return f"마지막 수신 {received_at:%Y-%m-%d %H:%M:%S} KST"


def domestic_market_state(
    received_at: datetime | None,
    error: str | None = None,
) -> MarketState:
    """국내 정규장 시간과 마지막 틱 시각으로 표시 상태를 판정한다."""
    now = datetime.now(KST)
    minutes = now.hour * 60 + now.minute
    is_weekday = now.weekday() < 5
    is_regular_market = is_weekday and 9 * 60 <= minutes <= 15 * 60 + 30

    if not is_weekday:
        detail = (
            _age_text(received_at, now)
            if received_at
            else "국내 정규장 휴장"
        )
        return MarketState("휴장", detail)

    if is_regular_market:
        if received_at and received_at.date() == now.date():
            age = max(0, (now - received_at).total_seconds())
            if age <= 15:
                return MarketState(
                    "장중 · 실시간",
                    _age_text(received_at, now),
                    True,
                )
            return MarketState("시세 지연", _age_text(received_at, now))
        if error:
            return MarketState("연결 오류", error)
        return MarketState("장중 · 연결 중", "실시간 시세를 기다리는 중")

    detail = (
        _age_text(received_at, now)
        if received_at
        else "국내 정규장 마감"
    )
    return MarketState("장 마감", detail)


def forex_market_state(
    received_at: datetime,
    *,
    has_live_tick: bool,
    error: str | None = None,
) -> MarketState:
    """USD/KRW 데이터의 실시간 여부와 신선도를 표시한다."""
    now = datetime.now(KST).replace(tzinfo=None)
    received = received_at.replace(tzinfo=None)
    age = max(0, (now - received).total_seconds())
    # 뉴욕 금요일 마감부터 월요일 아시아 개장 전까지의 근사 구간.
    is_weekend_closed = (
        (now.weekday() == 5 and now.hour >= 7)
        or now.weekday() == 6
        or (now.weekday() == 0 and now.hour < 7)
    )
    if is_weekend_closed:
        return MarketState("외환시장 휴장", _age_text(received, now))
    if has_live_tick and age <= 15:
        return MarketState(
            "외환시장 · 실시간",
            _age_text(received, now),
            True,
        )
    if age <= 180:
        return MarketState("최신 1분봉", _age_text(received, now))
    if error:
        return MarketState("환율 연결 오류", error)
    return MarketState("환율 시세 지연", _age_text(received, now))


class _KisStockStream:
    def __init__(self, stock_code: str):
        self.stock_code = stock_code
        self.latest: LivePrice | None = None
        self.error: str | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _credentials(self) -> tuple[str, str]:
        app_key = os.getenv("KIS_APP_KEY") or os.getenv("APP_KEY")
        app_secret = os.getenv("KIS_APP_SECRET") or os.getenv("APP_SECRET")
        if not app_key or not app_secret:
            raise ValueError("KIS_APP_KEY와 KIS_APP_SECRET을 설정해 주세요.")
        return app_key, app_secret

    def _approval_key(self) -> str:
        app_key, app_secret = self._credentials()
        response = requests.post(
            "https://openapi.koreainvestment.com:9443/oauth2/Approval",
            json={
                "grant_type": "client_credentials",
                "appkey": app_key,
                "secretkey": app_secret,
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()
        approval_key = result.get("approval_key")
        if not approval_key:
            raise RuntimeError(result.get("msg1", "KIS 접속키 발급 실패"))
        return approval_key

    def _run(self) -> None:
        reconnect_backoff = 5
        while not self._stop.is_set():
            ws = None
            try:
                approval_key = self._approval_key()
                app_key, app_secret = self._credentials()
                ws = websocket.create_connection(
                    "ws://ops.koreainvestment.com:21000",
                    timeout=20,
                )
                ws.send(
                    json.dumps(
                        {
                            "header": {
                                "approval_key": approval_key,
                                "custtype": "P",
                                "tr_type": "1",
                                "content-type": "utf-8",
                            },
                            "body": {
                                "input": {
                                    "tr_id": "H0STCNT0",
                                    "tr_key": self.stock_code,
                                }
                            },
                        }
                    )
                )
                self.error = None
                while not self._stop.is_set():
                    message = ws.recv()
                    if not isinstance(message, str):
                        continue
                    if message.startswith("0|H0STCNT0|"):
                        fields = message.split("|", 3)[3].split("^")
                        self.latest = LivePrice(
                            price=float(fields[2]),
                            change=float(fields[4]),
                            change_rate=float(fields[5]),
                            open=float(fields[7]),
                            high=float(fields[8]),
                            low=float(fields[9]),
                            received_at=datetime.now(KST),
                        )
                    elif message.startswith("{"):
                        payload = json.loads(message)
                        if payload.get("header", {}).get("tr_id") == "PINGPONG":
                            ws.send(message)
                        elif payload.get("body", {}).get("rt_cd") not in (None, "0"):
                            self.error = payload["body"].get("msg1", "KIS 구독 오류")
            except Exception as error:
                self.error = str(error)
                self._stop.wait(5)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass


class _KisIndexStream(_KisStockStream):
    """KIS 국내지수 실시간체결(H0UPCNT0) 수신기."""

    def _run(self) -> None:
        while not self._stop.is_set():
            ws = None
            try:
                approval_key = self._approval_key()
                ws = websocket.create_connection(
                    "ws://ops.koreainvestment.com:21000",
                    timeout=20,
                )
                ws.send(
                    json.dumps(
                        {
                            "header": {
                                "approval_key": approval_key,
                                "custtype": "P",
                                "tr_type": "1",
                                "content-type": "utf-8",
                            },
                            "body": {
                                "input": {
                                    "tr_id": "H0UPCNT0",
                                    "tr_key": self.stock_code,
                                }
                            },
                        }
                    )
                )
                self.error = None
                while not self._stop.is_set():
                    message = ws.recv()
                    if not isinstance(message, str):
                        continue
                    if message.startswith("0|H0UPCNT0|"):
                        fields = message.split("|", 3)[3].split("^")
                        self.latest = LivePrice(
                            price=float(fields[2]),
                            change=float(fields[4]),
                            change_rate=float(fields[9]),
                            open=float(fields[10]),
                            high=float(fields[11]),
                            low=float(fields[12]),
                            received_at=datetime.now(KST),
                        )
                    elif message.startswith("{"):
                        payload = json.loads(message)
                        if payload.get("header", {}).get("tr_id") == "PINGPONG":
                            ws.send(message)
                        elif payload.get("body", {}).get("rt_cd") not in (None, "0"):
                            self.error = payload["body"].get("msg1", "KIS 지수 구독 오류")
            except Exception as error:
                self.error = str(error)
                self._stop.wait(5)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass


class _KisMarketStream(_KisStockStream):
    """하나의 KIS 연결에서 주식과 국내지수를 함께 구독한다."""

    def __init__(self):
        self.latest_stocks: dict[str, LivePrice] = {}
        self.latest_indices: dict[str, LivePrice] = {}
        self.stock_codes: set[str] = set()
        self.index_codes: set[str] = set()
        self.error: str | None = None
        self._ws = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @staticmethod
    def _request(approval_key: str, tr_id: str, tr_key: str) -> str:
        return json.dumps(
            {
                "header": {
                    "approval_key": approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8",
                },
                "body": {"input": {"tr_id": tr_id, "tr_key": tr_key}},
            }
        )

    def subscribe_stock(self, code: str) -> LivePrice | None:
        with self._lock:
            is_new = code not in self.stock_codes
            self.stock_codes.add(code)
            ws = self._ws
            approval_key = getattr(self, "_current_approval_key", None)
        if is_new and ws is not None and approval_key:
            try:
                ws.send(self._request(approval_key, "H0STCNT0", code))
            except Exception:
                pass
        return self.latest_stocks.get(code)

    def subscribe_index(self, code: str) -> LivePrice | None:
        with self._lock:
            is_new = code not in self.index_codes
            self.index_codes.add(code)
            ws = self._ws
            approval_key = getattr(self, "_current_approval_key", None)
        if is_new and ws is not None and approval_key:
            try:
                ws.send(self._request(approval_key, "H0UPCNT0", code))
            except Exception:
                pass
        return self.latest_indices.get(code)

    def _run(self) -> None:
        while not self._stop.is_set():
            ws = None
            try:
                approval_key = self._approval_key()
                ws = websocket.create_connection(
                    "ws://ops.koreainvestment.com:21000",
                    timeout=20,
                )
                with self._lock:
                    self._ws = ws
                    self._current_approval_key = approval_key
                    stocks = tuple(self.stock_codes)
                    indices = tuple(self.index_codes)
                for code in stocks:
                    ws.send(self._request(approval_key, "H0STCNT0", code))
                for code in indices:
                    ws.send(self._request(approval_key, "H0UPCNT0", code))
                self.error = None
                reconnect_backoff = 5
                while not self._stop.is_set():
                    try:
                        message = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        # 장 마감 등으로 체결이 없어도 정상 연결로 간주한다.
                        # 프로토콜 Ping만 보내 연결 상태를 확인한다.
                        ws.ping()
                        continue
                    if not isinstance(message, str):
                        continue
                    if message.startswith("0|H0STCNT0|"):
                        fields = message.split("|", 3)[3].split("^")
                        self.latest_stocks[fields[0]] = LivePrice(
                            price=float(fields[2]),
                            change=float(fields[4]),
                            change_rate=float(fields[5]),
                            open=float(fields[7]),
                            high=float(fields[8]),
                            low=float(fields[9]),
                            received_at=datetime.now(KST),
                        )
                    elif message.startswith("0|H0UPCNT0|"):
                        fields = message.split("|", 3)[3].split("^")
                        self.latest_indices[fields[0]] = LivePrice(
                            price=float(fields[2]),
                            change=float(fields[4]),
                            change_rate=float(fields[9]),
                            open=float(fields[10]),
                            high=float(fields[11]),
                            low=float(fields[12]),
                            received_at=datetime.now(KST),
                        )
                    elif message.startswith("{"):
                        payload = json.loads(message)
                        if payload.get("header", {}).get("tr_id") == "PINGPONG":
                            ws.send(message)
                        elif payload.get("body", {}).get("rt_cd") not in (None, "0"):
                            self.error = payload["body"].get("msg1", "KIS 구독 오류")
            except Exception as error:
                if not self.error:
                    self.error = str(error)
                delay = _kis_reconnect_delay(reconnect_backoff)
                self._stop.wait(delay)
                reconnect_backoff = min(reconnect_backoff * 2, 60)
            finally:
                with self._lock:
                    self._ws = None
                    self._current_approval_key = None
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass


class _TwelveForexStream:
    def __init__(self):
        self.ticks: deque[tuple[datetime, float]] = deque(maxlen=3600)
        self.error: str | None = None
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def snapshot(self) -> list[tuple[datetime, float]]:
        with self._lock:
            return list(self.ticks)

    def _run(self) -> None:
        key = os.getenv("TWELVE_DATA_API_KEY") or os.getenv("TWELVE_API_KEY")
        if not key:
            self.error = "TWELVE_DATA_API_KEY가 설정되지 않았습니다."
            return
        reconnect_backoff = 5
        while True:
            ws = None
            try:
                ws = websocket.create_connection(
                    f"wss://ws.twelvedata.com/v1/quotes/price?apikey={key}",
                    timeout=20,
                )
                ws.settimeout(10)
                ws.send(
                    json.dumps(
                        {
                            "action": "subscribe",
                            "params": {"symbols": "USD/KRW"},
                        }
                    )
                )
                self.error = None
                reconnect_backoff = 5
                while True:
                    try:
                        raw_message = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        ws.send(json.dumps({"action": "heartbeat"}))
                        continue
                    message = json.loads(raw_message)
                    if (
                        message.get("status") == "error"
                        or message.get("event") == "error"
                    ):
                        self.error = message.get(
                            "message",
                            "Twelve Data WebSocket 구독 권한 오류",
                        )
                        return
                    if message.get("event") != "price":
                        continue
                    timestamp = datetime.fromtimestamp(
                        float(message["timestamp"]), tz=KST
                    ).replace(tzinfo=None)
                    with self._lock:
                        self.ticks.append((timestamp, float(message["price"])))
            except Exception as error:
                self.error = str(error)
                time.sleep(reconnect_backoff)
                reconnect_backoff = min(reconnect_backoff * 2, 60)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass


_LOCK = threading.Lock()
_KIS_STREAM: _KisMarketStream | None = None
_FOREX_STREAM: _TwelveForexStream | None = None


def get_live_stock(stock_code: str) -> tuple[LivePrice | None, str | None]:
    global _KIS_STREAM
    with _LOCK:
        if _KIS_STREAM is None:
            _KIS_STREAM = _KisMarketStream()
        stream = _KIS_STREAM
    return stream.subscribe_stock(stock_code), stream.error


def get_live_index(index_code: str) -> tuple[LivePrice | None, str | None]:
    global _KIS_STREAM
    with _LOCK:
        if _KIS_STREAM is None:
            _KIS_STREAM = _KisMarketStream()
        stream = _KIS_STREAM
    return stream.subscribe_index(index_code), stream.error


def get_live_usd_krw_ticks() -> tuple[list[tuple[datetime, float]], str | None]:
    global _FOREX_STREAM
    with _LOCK:
        if _FOREX_STREAM is None:
            _FOREX_STREAM = _TwelveForexStream()
        stream = _FOREX_STREAM
    return stream.snapshot(), stream.error

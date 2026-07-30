"""KIS 국내주식과 Twelve Data 환율 실시간 WebSocket 수신기."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import websocket
from dotenv import load_dotenv


load_dotenv()

KST = ZoneInfo("Asia/Seoul")


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

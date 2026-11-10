# K-SWING v0.1 — 독립적인 한국 주식 스윙 지표 연구

현재 코드에는 기존 금융 시뮬레이터의 웹 UI 변경, 실제 주문, 투자 추천 기능이 없습니다.
연구용 폴더만 사용하며 기존 app.py, pages/, 루트 requirements.txt, Dockerfile은 수정하지 않습니다.

## 연구 목적

거래일 T 정규장 마감까지 알 수 있는 지표로 T+1 시가에 진입할 때의 5일 및 10일 보유 수익률과의 관계를 탐색합니다.
상한가 예측 대신 1~2주 스윙을 연구하며 실제 수익성은 아직 검증되지 않았습니다.

## 빠른 시작 (저장소 최상위에서 실행)

    python -m pip install -r research/k_swing/requirements.txt
    python -m pytest -q research/k_swing/tests
    python -m research.k_swing.examples.make_synthetic_data --output /tmp/kswing_fake.csv
    python -m research.k_swing.cli --input /tmp/kswing_fake.csv --output /tmp/kswing_demo

위 생성기는 완전한 합성 데이터이며 어떤 성과도 실제 금융시장 성과를 의미하지 않습니다.

## 실제 CSV 사용 예시

    python -m research.k_swing.cli --input /path/krx_ohlcv.csv --calendar /path/krx_sessions.csv --output /tmp/kswing_results --train-end 2022-12-29 --valid-end 2024-12-30 --top-k 10

데이터 입력 열 (순서는 자유): date,ticker,open,high,low,close,volume,turnover
date는 YYYY-MM-DD, ticker는 6자리 숫자 종목코드, 가격은 KRW, volume은 주식 수, turnover는 KRW입니다.
동일 종목·날짜는 한 행만 허용하며 거래대금/거래량과 OHLC의 숫자 형식 및 누락을 검사합니다.

달력 CSV는 date 열에 한국거래소 정규 거래일을 담습니다.
--calendar 없이는 관측된 종목들의 날짜 합집합을 임시 달력으로 쓰므로 신뢰성 있는 연구에는 부적절할 수 있습니다.
기업행위(분할·증자 등)의 조정 기준이 일관된 시세를 별도로 확보해야 합니다.
현재 코드는 **자동 시세 수집 기능이 없으며**, 상장폐지 종목 이력과 공시 공개 시점 정합성도 입력 데이터 제공자에게 의존합니다.

## 수익률 라벨

신호: T일 장 마감 / 매수: 다음 거래일 T+1의 시가 / 매도: T+H의 종가 (H=5, 10).
T+1 ~ T+H의 보유기간 중 일봉이나 거래량이 하나라도 빠지면 해당 수익률 라벨을 계산하지 않습니다.
MFE/MAE는 향후 H일의 고가/저가로 계산한 사후적 이론값이며 실현 가능한 손절/익절 수익률이 아닙니다.

## 연구 지표

18개 지표: 1/5/10/20일 과거 수익률, 5/20일 이동평균 이격도, EMA 12/26 비율,
RSI14, ATR14 대비 종가, 볼린저 밴드 폭20, 연율화 변동성20, 거래량/거래대금 20일 기준 비율,
거래대금 Z-score, 종가 위치, 윗꼬리 비율, OBV 유사 10일 순매수 흐름, 20일 고점 돌파율.

이동평균, 표준편차 및 모든 기술적 지표는 T 시점까지의 데이터만 사용합니다.
거래정지나 결측 일봉은 빠뜨리지 않고 누락된 값으로 처리합니다.

## 출력

- factor_metrics.csv: train/validation/test × 지표 × 보유기간별 Rank IC, Top-K 평균 사후 수익률
- train_factor_ranking.csv: 학습 데이터로만 결정한 지표 방향 및 학습 IC 순위
- research_panel.csv: 거래일·종목별 입력/지표/향후 수익률/구간
- summary.json: 데이터 범위, 가정, 테스트 구간, 주의사항

시간순 60/20/20 분할을 사용하고 학습 및 검증 종료 시점에 10 거래일의 정보 누수 방지 간격을 적용합니다.
일별 Rank IC는 해당 날짜 종목 간 스피어만 순위상관계수입니다.

주의: Top-K 평균 향후 수익률은 포트폴리오 매매 결과가 아닙니다.
중복보유, 자본 배분, 가격제한폭, 유동성·체결 가능성, 종목 상장폐지, 세금 및 시계열 검증 편향을 모두 해결한 백테스트가 아닙니다.
출력의 net_return_approx는 왕복 비용 bps를 단순 차감한 설명용 근사치입니다.

## 다음 작업

1. 공식/허가된 KRX 정규 거래일과 전 종목 장기 OHLCV 데이터 품질 검증
2. 상장폐지·기업행위 시점 반영, 공시/수급 데이터의 이용가능 시점 결합
3. 워크포워드 평가, 다중 검정 및 과적합 통제
4. 실제 체결을 고려하는 포트폴리오 백테스트
5. 이후 기호회귀/유전프로그래밍을 이용한 신규 수식 탐색

이 단계의 코드는 탐색 연구를 위한 첫 버전이며 실제 주식에서 유효한 알파를 확인한 것이 아닙니다.

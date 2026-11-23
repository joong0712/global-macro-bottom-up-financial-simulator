# K-SWING 연구 색인 — 어디서 시작할까

**지금 기준 코드는 `pipeline/` 하나다.** v04–v23 모듈과 워크플로는 기록용으로 남겨두며 새 연구에 쓰지 않는다
(기존 워크플로는 각자의 브랜치 push에만 반응하므로 이 브랜치에서는 돌지 않는다).

## 흐름 요약

| 단계 | 질문 | 결론 | 문서 |
|---|---|---|---|
| v0.1–v0.9 | 18→188개 기술적 지표의 Rank IC·후보 수식 | 탐색 단계, 실거래 근거 없음 | `REAL_FACTOR_STUDY_V03.md`, `FEATURE_MATRIX_V04.md`, `GO_NO_GO_V09.md` |
| v10–v15 | VCR, 수익 우선 레짐·ML, 일목+이평 진입 타이밍, 조기 청산, 동일 진입 비교 | 모두 NO-GO (두 기간 모두 양수인 조합 없음) | `VCR_RESULTS_AUDIT_V10.md`, `V12_PARALLEL_RESULTS_AUDIT.md`, `V13_TIMING_RESULTS_AUDIT.md`, `V14_EXIT_RESULTS_AUDIT.md`, `V15_PAIRED_RESULTS_AUDIT.md` |
| v16–v18 | 공식 종목 식별·기업행위·FSC 데이터 게이트 | 공식 데이터 권한 미확보 | `V16_EVIDENCE_PROTOCOL.md`, `V17_OFFICIAL_IDENTITY_PROTOCOL.md`, `V18_FSC_INGEST_PROTOCOL.md` |
| v19 | 비용 0이면 살아나나 | 아니오 — NO-GO | `V19_COST_FRONTIER_AUDIT.md` |
| v20–v22 | 오른 종목의 공통 지표 | 고변동성(=크게 움직이는 종목) | `V22_OBSERVED_WINNER_FACTOR_RESULTS.md` |
| v23 | 고변동성의 상승 vs 하락 꼬리 | 하락 꼬리가 더 큼 — NO-GO | `V23_RESULTS_AUDIT.md` |
| **v24** | 전 종목·수정주가·실제 비용 포트폴리오, 사전등록 가설 3개 | **NO-GO**. 비용 장벽 연 15–32%, 비용 0이어도 개발 구간 음수. 수익이 야간에 몰리는 구조 발견 | `V24_PROTOCOL.md`, `V24_RESULTS.md`, `reports/V24_AGGREGATE.md` |

## 이미 본 데이터 (재사용 시 검증이 아님)

- 2019–2022: v1–v23에서 반복 사용. 2018–2022: v24 개발.
- 2023–2025: v0.3 기본 지표 IC, v24 검증.
- **2026: 아직 아무도 보지 않음.** 한 번만 연다.

## 실행

    python -m pip install -r research/k_swing/requirements.txt
    python -m pytest -q research/k_swing/tests
    # marcap-2016..2025.parquet (고정 커밋 94c138d)를 비공개 폴더에 두고
    python -m research.k_swing.pipeline.run --marcap-dir DIR --private-output PRIVATE --public-output PUBLIC

GitHub Actions: `K-SWING v2.4 unified pipeline` → Run workflow → `full_study` 체크 시 같은 연구를 재실행하고 집계만 남긴다.

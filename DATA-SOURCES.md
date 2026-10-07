# 조회·스크리닝 시스템

**목적:** 종목·ETF 목록과 재무제표를 기계가 조회·필터하고, 해석과 판단만 사람·AI가 한다.
**출력은 전부 마크다운 표 + CSV.** 대시보드를 만들지 않는다 — 원장에 바로 붙고 Claude가 읽을 수 있어야 한다.

```
scripts/        수집·스크리닝
data/           출력 (CSV, 날짜 스탬프)
```

## 검증된 데이터 소스 (2026-10-07 실측)

| 소스 | 엔드포인트 | 얻는 것 | 키 | 상태 |
|---|---|---|---|---|
| 네이버 ETF 목록 | `finance.naver.com/api/sise/etfItemList.nhn` | **전체 ETF 1,171종** + 시세·NAV·순자산·3개월수익 | 불필요 | ✅ |
| 네이버 ETF 상세 | `m.stock.naver.com/api/stock/{code}/integration` → `etfKeyIndicator` | **총보수 · 1년/3개월 수익 · 괴리율 · 배당수익률 · 순자산** | 불필요 | ✅ |
| 네이버 전종목 | `m.stock.naver.com/api/stocks/marketValue/{KOSPI\|KOSDAQ}?page=&pageSize=` | 시총 순 전종목 | 불필요 | ✅ |
| 네이버 재무제표 | `m.stock.naver.com/api/stock/{code}/finance/{annual\|quarter}` | **매출·영업이익·순이익·ROE·부채비율·당좌비율·EPS·PER·BPS·PBR·배당** 3년+컨센서스 | 불필요 | ✅ |
| 네이버 지표 | `m.stock.naver.com/api/stock/{code}/integration` → `totalInfos` | PER·EPS·추정PER·52주·외국인소진율 | 불필요 | ✅ |
| **SEC EDGAR** | `data.sec.gov/api/xbrl/companyconcept/CIK{10자리}/us-gaap/{태그}.json` | 미국 기업 원본 XBRL (현금, 주식수 등) | 불필요 (User-Agent에 이메일) | ✅ |
| KRX 정보데이터 | `data.krx.co.kr/comm/bldAttendant/getJsonData.cmd` | — | 세션 필요 | ❌ LOGOUT |
| DART OpenAPI | `opendart.fss.or.kr` | 국내 원본 재무·주식총수·공시 | **무료 키 필요** | 미적용 |
| 금투협 공시 | `dis.kofia.or.kr` | ETF 실부담비용 | POST/동적 | 미적용 |

## 실행

```bash
# UI (권장)
python -m pip install streamlit pandas     # 최초 1회
streamlit run app.py               # → http://localhost:8501

# CLI
python fetch_etf.py "S&P500"          # ETF 목록 + 파생·테마 제외 필터
python compare_etf.py 360750 379800   # 후보 비교 (총보수·1년수익·괴리율·순자산)
python fetch_stock.py list KOSPI 50   # 시총 상위
python fetch_stock.py fin 005930      # 연간 재무제표 (quarter = 분기)
python fetch_stock.py ind 005930      # 핵심지표
```

**`data/*.csv`는 UTF-8 BOM으로 저장된다 — 엑셀·구글시트에서 한글 깨짐 없이 바로 열린다.**
정렬·필터·조건부서식이 필요하면 UI보다 스프레드시트가 빠를 때가 많다.

## 경계 — 지킬 것

```
fetch_*.py  →  data/*.csv  →  app.py / 스프레드시트 / Claude
 (수집)         (경계)           (표시·분석)
```

`app.py`는 **표시만 한다.** 수집 로직을 UI에 넣지 않는다.
이유: ① UI가 죽어도 데이터 레이어는 산다 ② 나중에 Next.js로 바꿀 때 거의 공짜 ③ 같은 CSV를 Claude가 읽고 분석할 수 있다.

## ★ 데이터 해석 주의 — 실측으로 확인된 함정

**1. 총보수는 비용 지표가 아니다.**
동일 지수를 추종하는 S&P500 ETF 10종 실측 결과, **총보수가 같은데 1년 수익률이 0.6%p 차이났다.**
SOL(총보수 0.0047%, 최저)이 1년 수익률은 -0.60%p 뒤졌고, RISE(같은 0.0047%)가 1위였다.
→ **같은 지수면 1년 수익률 차이 = 실부담비용 + 추적오차.** 이게 유일하게 정직한 비용 지표다.
→ `compare_etf.py`의 `실질차_%p` 컬럼이 이 계산이다.

**2. 이름 검색만으로는 쓰레기가 섞인다.**
"S&P500" 검색 시 30종이 걸리는데 대부분 **커버드콜·채권혼합·레버리지·섹터·ESG 변종**이다.
순수 광범위 지수는 상위 6종뿐. → `fetch_etf.py`의 `EXCLUDE` 리스트로 거른다. 새 변종이 나오면 추가한다.

**3. 컨센서스(E) 컬럼을 신뢰하지 않는다.**
삼성전자 2026.12 컨센서스가 매출 727조·영업이익 380조로 조회됐다 — **2025년 실적의 2~9배로 비현실적.**
→ **(E) 컬럼은 참고만 하고, 판정에는 확정 실적만 쓴다.** 컨센서스가 필요하면 1차 자료로 교차 확인.

**4. 네이버는 2차 가공 데이터다.**
빠르고 편하지만 원본이 아니다. **F1(현금 런웨이)·F2(발행주식수)는 네이버에 없다.**
→ 국내는 **DART**, 미국은 **SEC EDGAR**가 1차다. 매수 심사(F5)에서는 1차 자료를 직접 확인한다.

## 다음에 만들 것

- [ ] **DART OpenAPI 연동** — 무료 키 발급(`opendart.fss.or.kr`) → `현금및현금성자산`, `주식총수`
      → **F1(런웨이)·F2(희석) 자동화.** 네이버로는 불가능한 부분
- [ ] **SEC EDGAR 래퍼** — 미국 종목 F1·F2 자동화 (엔드포인트 검증 완료)
- [ ] **`screen.py`** — F1~F6 기계 적용. F3·F4는 판단이므로 질문만 출력
- [ ] 금투협 실부담비용 (선택 — 위 함정 1번 때문에 우선도 낮다. 1년 수익률이 더 정확하다)

**만들지 않을 것:** 대시보드·UI, 실시간 시세, 백테스팅 엔진. 의사결정을 바꾸지 않는다.

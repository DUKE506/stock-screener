#!/usr/bin/env python3
"""종목·ETF 조회 스크리너 (Streamlit).

실행:  streamlit run scripts/app.py
원칙:  수집 로직은 fetch_*.py에 있고 이 파일은 표시만 한다. 경계를 지킨다.
"""
import sys, os, json, urllib.request
from datetime import date
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_etf, fetch_stock

st.set_page_config(page_title="자산 스크리너", layout="wide")
DATA = os.path.join(os.getcwd(), "data")   # 실행 위치 기준. 클론 후 리포 루트에서 실행하면 리포 안에 생성된다
os.makedirs(DATA, exist_ok=True)
TTL = 1800  # 30분 캐시 — API를 반복 호출하지 않는다


# ---------- 데이터 (캐시) ----------
@st.cache_data(ttl=TTL, show_spinner="ETF 목록 수집 중...")
def etf_all():
    rows = fetch_etf.fetch()
    df = pd.DataFrame([{
        "종목명": e["itemname"], "코드": e["itemcode"],
        "현재가": fetch_etf.num(e.get("nowVal")),
        "순자산_억": fetch_etf.num(e.get("marketSum")),
        "NAV": fetch_etf.num(e.get("nav")),
        "3개월_%": e.get("threeMonthEarnRate"),
        "거래대금_백만": fetch_etf.num(e.get("amonut")),
    } for e in rows])
    df["괴리율_%"] = ((df["현재가"] - df["NAV"]) / df["NAV"] * 100).round(3)
    return df


@st.cache_data(ttl=TTL, show_spinner="상세 지표 조회 중...")
def etf_detail(codes):
    out = []
    for c in codes:
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(
                f"https://m.stock.naver.com/api/stock/{c}/integration",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
            ), timeout=25).read().decode("utf-8"))
            k = d.get("etfKeyIndicator") or {}
            g = lambda x: float(k[x]) if k.get(x) not in (None, "") else None
            out.append({"종목명": d.get("stockName"), "코드": c,
                        "총보수_%": g("totalFee"), "1년수익_%": g("returnRate1y"),
                        "3개월_%": g("returnRate3m"), "괴리율_%": g("deviationRate"),
                        "배당수익_%": g("dividendYieldTtm"), "순자산": k.get("totalNav")})
        except Exception as e:
            out.append({"종목명": f"ERR {c}", "코드": c})
    df = pd.DataFrame(out)
    if "1년수익_%" in df and df["1년수익_%"].notna().any():
        df["실질차_%p"] = (df["1년수익_%"] - df["1년수익_%"].max()).round(3)
    return df


@st.cache_data(ttl=TTL, show_spinner="종목 목록 수집 중...")
def stock_list(mkt, n):
    return pd.DataFrame(fetch_stock.stock_list(mkt, n))


@st.cache_data(ttl=TTL, show_spinner="재무제표 조회 중...")
def finance(code, period):
    rows, titles, cons = fetch_stock.finance(code, period)
    return pd.DataFrame(rows), cons


@st.cache_data(ttl=TTL)
def indicators(code):
    return fetch_stock.indicators(code)


def save(df, name):
    p = os.path.join(DATA, f"{name}-{date.today().isoformat()}.csv")
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return p


# ---------- 사이드바 ----------
st.sidebar.title("자산 스크리너")
st.sidebar.caption(f"캐시 {TTL//60}분 · 출처: 네이버 금융 API")
if st.sidebar.button("캐시 비우고 새로 수집"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**데이터 함정** (scripts/README.md)\n\n"
    "1. 총보수는 비용 지표가 아니다 — 같은 지수면 **1년수익 차이**가 실측 비용\n"
    "2. 이름 검색엔 커버드콜·레버리지 변종이 섞인다\n"
    "3. **컨센서스(E)를 신뢰하지 않는다**\n"
    "4. F1(현금)·F2(주식수)는 여기 없다 → DART/SEC"
)

t1, t2, t3, t4 = st.tabs(["ETF 스크리너", "종목 스크리너", "재무 분석", "내 포트폴리오"])

# ---------- Tab 1: ETF ----------
with t1:
    df = etf_all()
    c1, c2, c3 = st.columns([2, 1, 1])
    kw = c1.text_input("이름 검색", "S&P500", help="예: S&P500, 나스닥, 배당, 반도체")
    min_nav = c2.number_input("최소 순자산(억)", 0, 300000, 1000, step=500,
                              help="1조=10000억. 작은 ETF는 청산 리스크")
    c3.metric("전체 ETF", f"{len(df):,}")

    o1, o2 = st.columns(2)
    ex_deriv = o1.checkbox("파생·테마 변종 제외", True,
                           help=f"제외: {', '.join(fetch_etf.EXCLUDE)}")
    ex_hedge = o2.checkbox("환헤지(H) 제외", True, help="장기 보유에선 헤지 비용이 누적된다")

    v = df.copy()
    k = kw.replace(" ", "").lower()
    if k:
        v = v[v["종목명"].str.replace(" ", "").str.lower().str.contains(k, regex=False)]
    if ex_deriv:
        v = v[~v["종목명"].str.contains("|".join(fetch_etf.EXCLUDE), regex=True)]
    if ex_hedge:
        v = v[~v["종목명"].str.contains(r"\(H\)|환헤지", regex=True)]
    v = v[v["순자산_억"] >= min_nav].sort_values("순자산_억", ascending=False)

    st.caption(f"{len(v)}종목 — 열 제목을 눌러 정렬")
    st.dataframe(v, use_container_width=True, hide_index=True)

    st.markdown("#### 후보 비교 — 총보수·1년수익·실질차")
    st.caption("같은 지수를 추종하면 **1년 수익률 차이 = 실부담비용 + 추적오차.** 총보수보다 정직하다.")
    picks = st.multiselect("비교할 종목", v["종목명"].tolist(), v["종목명"].tolist()[:6])
    if picks:
        codes = v[v["종목명"].isin(picks)]["코드"].tolist()
        d = etf_detail(tuple(codes)).sort_values("1년수익_%", ascending=False)
        st.dataframe(d, use_container_width=True, hide_index=True)
        if "1년수익_%" in d and d["1년수익_%"].notna().any():
            st.bar_chart(d.set_index("종목명")["1년수익_%"], height=260)
        if st.button("CSV 저장", key="s1"):
            st.success(save(d, "etf-compare"))

# ---------- Tab 2: 종목 ----------
with t2:
    c1, c2 = st.columns([1, 1])
    mkt = c1.selectbox("시장", ["KOSPI", "KOSDAQ"])
    n = c2.slider("시총 상위 N", 20, 500, 100, step=20)
    s = stock_list(mkt, n)
    keep = [c for c in ["stockName", "itemCode", "closePrice", "marketValue",
                        "fluctuationsRatio", "per", "pbr", "roe", "accumulatedTradingVolume"]
            if c in s.columns]
    ren = {"stockName": "종목명", "itemCode": "코드", "closePrice": "현재가",
           "marketValue": "시가총액_백만", "fluctuationsRatio": "등락률_%",
           "per": "PER", "pbr": "PBR", "roe": "ROE", "accumulatedTradingVolume": "거래량"}
    view = s[keep].rename(columns=ren)
    for col in ("시가총액_백만", "현재가", "PER", "PBR", "ROE"):
        if col in view:
            view[col] = pd.to_numeric(view[col].astype(str).str.replace(",", ""), errors="coerce")
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.caption("※ 여기 PER·PBR은 2차 가공치다. 판정에는 재무 분석 탭의 확정 실적을 쓴다.")
    if st.button("CSV 저장", key="s2"):
        st.success(save(view, f"stocks-{mkt}"))

# ---------- Tab 3: 재무 ----------
with t3:
    c1, c2 = st.columns([1, 1])
    code = c1.text_input("종목코드", "005930")
    period = c2.radio("기간", ["annual", "quarter"], horizontal=True)
    if code:
        try:
            ind, name = indicators(code)
            st.subheader(f"{name} ({code})")
            cols = st.columns(6)
            for i, key in enumerate(["PER", "EPS", "추정PER", "시총", "52주 최고", "52주 최저"]):
                if key in ind:
                    cols[i % 6].metric(key, ind[key])

            fin, cons = finance(code, period)
            est = [t for t, c in cons.items() if c == "Y"]
            if est:
                st.warning(f"**컨센서스 컬럼 주의** — {', '.join(str(e) for e in est)}는 추정치다. "
                           "삼성전자 실측에서 비현실적 값이 확인됐다. **판정에는 확정 실적만 쓴다.**")
            st.dataframe(fin, use_container_width=True, hide_index=True)

            long = fin.set_index("항목").T
            pick = [x for x in ["매출액", "영업이익", "당기순이익"] if x in long.columns]
            if pick:
                ch = long[pick].apply(lambda s: pd.to_numeric(
                    s.astype(str).str.replace(",", ""), errors="coerce"))
                st.markdown("##### 매출·이익 추세 (억원)")
                st.line_chart(ch, height=300)
            pick2 = [x for x in ["ROE", "영업이익률", "부채비율"] if x in long.columns]
            if pick2:
                ch2 = long[pick2].apply(lambda s: pd.to_numeric(
                    s.astype(str).str.replace(",", ""), errors="coerce"))
                st.markdown("##### 수익성·안정성 (%)")
                st.line_chart(ch2, height=300)
            if st.button("CSV 저장", key="s3"):
                st.success(save(fin, f"fin-{code}-{period}"))
        except Exception as e:
            st.error(f"조회 실패: {e}")

# ---------- Tab 4: 포트폴리오 ----------
with t4:
    # 실제 보유는 data/portfolio.csv 에서 읽는다 (git 추적 제외).
    # 파일이 없으면 샘플로 시작한다 — 개인 데이터를 소스코드에 넣지 않는다.
    PF = os.path.join(DATA, "portfolio.csv")
    SAMPLE = pd.DataFrame([
        {"종목": "예시 지수ETF", "섹터": "글로벌 지수", "원금_만": 1000, "평가_만": 1000, "분류": "코어"},
        {"종목": "예시 개별주A", "섹터": "섹터A", "원금_만": 300, "평가_만": 260, "분류": "새틀라이트"},
        {"종목": "예시 개별주B", "섹터": "섹터B", "원금_만": 200, "평가_만": 230, "분류": "새틀라이트"},
    ])
    if os.path.exists(PF):
        base = pd.read_csv(PF)
        st.caption(f"`data/portfolio.csv` 에서 불러옴 · F6(기존 노출 초과) 판정용")
    else:
        base = SAMPLE
        st.info("`data/portfolio.csv` 가 없어 **샘플 데이터**로 표시합니다. "
                "아래 표를 편집하고 **저장**을 누르면 그 파일로 저장됩니다 (git 추적 제외).")

    ed = st.data_editor(base, num_rows="dynamic", use_container_width=True, hide_index=True)
    if st.button("보유 내역 저장", key="pfsave"):
        ed.to_csv(PF, index=False, encoding="utf-8-sig")
        st.success(f"저장: {PF}")

    c1, c2 = st.columns(2)
    sat_cap = c1.slider("새틀라이트 상한 %", 10, 50, 25)
    loss_pct = c2.slider("1회 최대 손실 %", 1, 5, 2)

    denom = ed["원금_만"].sum()
    sat = ed[ed["분류"] == "새틀라이트"]["원금_만"].sum()
    core = ed[ed["분류"] == "코어"]["원금_만"].sum()

    m = st.columns(4)
    m[0].metric("분모 (누적 투입)", f"{denom:,.0f}만")
    m[1].metric("코어", f"{core:,.0f}만", f"{core/denom*100:.1f}%" if denom else None)
    m[2].metric("새틀라이트", f"{sat:,.0f}만",
                f"{sat/denom*100:.1f}% (상한 {sat_cap}%)" if denom else None,
                delta_color="inverse")
    m[3].metric("새틀 상한액", f"{denom*sat_cap/100:,.0f}만")

    if denom:
        cap_sat = denom * sat_cap / 100
        st.markdown("##### 섹터 비중 — 새틀라이트 한도의 1/2 초과 여부")
        sec = (ed[ed["분류"] == "새틀라이트"].groupby("섹터")["원금_만"].sum()
               .reset_index().sort_values("원금_만", ascending=False))
        sec["비중_%"] = (sec["원금_만"] / denom * 100).round(1)
        sec["상한_만"] = round(cap_sat / 2)
        sec["판정"] = sec["원금_만"].apply(lambda x: "초과 ✗" if x > cap_sat / 2 else "통과 ✓")
        st.dataframe(sec, use_container_width=True, hide_index=True)

        st.markdown("##### 포지션 사이징 — 손절 거리가 금액을 정한다")
        sz = pd.DataFrame([{"손절거리_%": d,
                            "포지션상한_만": round(denom * loss_pct / 100 / (d / 100))}
                           for d in (20, 30, 40, 50)])
        sz["새틀상한_적용"] = sz["포지션상한_만"].apply(lambda x: min(x, round(cap_sat / 4)))
        st.dataframe(sz, use_container_width=True, hide_index=True)
        st.caption(f"포지션 = (분모 {denom:,.0f}만 × {loss_pct}%) ÷ 손절거리. "
                   f"종목 상한(새틀 한도 1/4 = {cap_sat/4:,.0f}만)과 비교해 **더 작은 값**을 쓴다.")

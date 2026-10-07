#!/usr/bin/env python3
"""국내 상장 ETF 전체 목록 수집 + 스크리닝.
출처: 네이버 금융 ETF API (1차 시세 데이터). 비용은 fetch_etf_fee.py 로 별도 수집.
사용: python scripts/fetch_etf.py "S&P500"
"""
import json, sys, csv, urllib.request, os
from datetime import date

URL = "https://finance.naver.com/api/sise/etfItemList.nhn"

# 코어 후보에서 제외할 파생·테마 키워드 (L2-1: 광범위 지수만)
EXCLUDE = ("커버드콜","채권혼합","레버리지","인버스","액티브","ESG","타겟데일리",
           "테크","헬스케어","배당","동일가중","OTM","선물","양분","플러스커버","목표전환")

def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent":"Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read()
    for enc in ("euc-kr","cp949","utf-8"):
        try: return json.loads(raw.decode(enc))["result"]["etfItemList"]
        except Exception: continue
    raise SystemExit("decode failed")

def num(v): return v if isinstance(v,(int,float)) else 0

def screen(lst, kw, exclude_hedged=True):
    out=[]
    for e in lst:
        n=e["itemname"]
        if kw.lower() not in n.lower().replace(" ",""): continue
        if any(x in n for x in EXCLUDE): continue
        if exclude_hedged and ("(H)" in n or "환헤지" in n): continue
        nav=num(e.get("nav")); now=num(e.get("nowVal"))
        out.append({
            "종목명":n, "코드":e["itemcode"], "현재가":now,
            "순자산_억":num(e.get("marketSum")),
            "괴리율_%": round((now-nav)/nav*100,3) if nav else None,
            "3개월수익_%": e.get("threeMonthEarnRate"),
            "거래량":num(e.get("quant")),
            "거래대금_백만":num(e.get("amonut")),
        })
    out.sort(key=lambda r:-r["순자산_억"])
    return out

if __name__=="__main__":
    kw = sys.argv[1] if len(sys.argv)>1 else "S&P500"
    lst = fetch()
    rows = screen(lst, kw.replace(" ",""))
    os.makedirs("data", exist_ok=True)
    stamp=date.today().isoformat()
    path=f"data/etf-{kw.replace('&','').replace(' ','')}-{stamp}.csv"
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    print(f"# ETF 스크리닝: {kw}   ({stamp}, 전체 {len(lst)}종목 중)\n")
    print(f"제외 키워드 적용: 파생·테마 {len(EXCLUDE)}종 + 환헤지\n")
    hdr=["종목명","코드","현재가","순자산(억)","괴리율%","3개월%","거래대금(백만)"]
    print("| "+" | ".join(hdr)+" |")
    print("|"+"---|"*len(hdr))
    for r in rows:
        print("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["종목명"], r["코드"], f'{r["현재가"]:,}', f'{r["순자산_억"]:,}',
            r["괴리율_%"], r["3개월수익_%"], f'{r["거래대금_백만"]:,}'))
    print(f"\n→ 저장: {path}")
    print("→ 실부담비용은 금융투자협회 공시에서 별도 확인 (이 API에 없음)")

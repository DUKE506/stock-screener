#!/usr/bin/env python3
"""ETF 후보 비교: 총보수 + 1년 수익률 + 괴리율 + 순자산.
핵심: 같은 지수를 추종하면 1년 수익률 차이 = 실부담비용 + 추적오차.
      공시 총보수보다 이것이 정직한 비용 지표다.
사용: python scripts/compare_etf.py 360750 379800 360200 ...
"""
import json, sys, urllib.request, csv, os
from datetime import date

def get(code):
    u=f"https://m.stock.naver.com/api/stock/{code}/integration"
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0",
        "Referer":"https://m.stock.naver.com/"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode("utf-8"))

def f(v):
    try: return float(v)
    except (TypeError,ValueError): return None

rows=[]
for code in sys.argv[1:]:
    try:
        d=get(code); k=d.get("etfKeyIndicator") or {}
        rows.append({
            "종목명": d.get("stockName"), "코드": code,
            "총보수_%": f(k.get("totalFee")),
            "1년수익_%": f(k.get("returnRate1y")),
            "3개월_%": f(k.get("returnRate3m")),
            "괴리율_%": f(k.get("deviationRate")),
            "배당수익_%": f(k.get("dividendYieldTtm")),
            "순자산": k.get("totalNav"),
        })
    except Exception as e:
        rows.append({"종목명":f"ERR {code}: {e}","코드":code})

ok=[r for r in rows if r.get("1년수익_%") is not None]
if ok:
    best=max(r["1년수익_%"] for r in ok)
    for r in ok: r["실질차_%p"]=round(r["1년수익_%"]-best,3)
ok.sort(key=lambda r:-(r["1년수익_%"] or -99))

os.makedirs("data",exist_ok=True)
stamp=date.today().isoformat()
p=f"data/etf-compare-{stamp}.csv"
if ok:
    with open(p,"w",newline="",encoding="utf-8-sig") as fh:
        w=csv.DictWriter(fh,fieldnames=list(ok[0].keys())); w.writeheader(); w.writerows(ok)

hdr=["종목명","코드","총보수%","1년수익%","실질차%p","3개월%","괴리율%","배당%","순자산"]
print("| "+" | ".join(hdr)+" |")
print("|"+"---|"*len(hdr))
for r in ok:
    print("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        r["종목명"], r["코드"], r["총보수_%"], r["1년수익_%"], r.get("실질차_%p"),
        r["3개월_%"], r["괴리율_%"], r["배당수익_%"], r["순자산"]))
for r in rows:
    if r.get("1년수익_%") is None: print("|", r["종목명"], "|")
print(f"\n기준일 {stamp} · 저장 {p}")
print("※ 1년수익 차이 = 실부담비용 + 추적오차. 같은 지수 추종이므로 이것이 실측 비용 지표다.")

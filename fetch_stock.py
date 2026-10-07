#!/usr/bin/env python3
"""국내 주식 조회: 전종목 목록 / 재무제표 / 핵심지표.
사용:
  python scripts/fetch_stock.py list KOSPI 50        # 시총 상위 50
  python scripts/fetch_stock.py fin 005930           # 연간 재무제표
  python scripts/fetch_stock.py fin 005930 quarter   # 분기
  python scripts/fetch_stock.py ind 005930           # 핵심지표
"""
import json, sys, csv, os, urllib.request
from datetime import date

H={"User-Agent":"Mozilla/5.0","Referer":"https://m.stock.naver.com/"}
B="https://m.stock.naver.com/api"

def get(u):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u,headers=H),timeout=30).read().decode("utf-8"))

def stock_list(market="KOSPI", n=50):
    out=[]; page=1
    while len(out)<n:
        d=get(f"{B}/stocks/marketValue/{market}?page={page}&pageSize=100")
        s=d.get("stocks") or []
        if not s: break
        out+=s; page+=1
    return out[:n]

def finance(code, period="annual"):
    d=get(f"{B}/stock/{code}/finance/{period}")
    fi=d.get("financeInfo") or {}
    cols=[c["key"] for c in fi.get("trTitleList",[])]
    titles={c["key"]:c["title"] for c in fi.get("trTitleList",[])}
    cons={c["key"]:c.get("isConsensus") for c in fi.get("trTitleList",[])}
    rows=[]
    for r in fi.get("rowList",[]):
        rows.append({"항목":r["title"], **{titles[k]:(r["columns"].get(k) or {}).get("value")
                      for k in cols}})
    return rows, titles, cons

def indicators(code):
    d=get(f"{B}/stock/{code}/integration")
    return {x.get("key"):x.get("value") for x in d.get("totalInfos",[])}, d.get("stockName")

if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "list"
    os.makedirs("data",exist_ok=True); stamp=date.today().isoformat()

    if cmd=="list":
        mkt=sys.argv[2] if len(sys.argv)>2 else "KOSPI"
        n=int(sys.argv[3]) if len(sys.argv)>3 else 50
        rows=stock_list(mkt,n)
        p=f"data/stocks-{mkt}-{stamp}.csv"
        keep=["stockName","itemCode","closePrice","marketValue","fluctuationsRatio","per","pbr","roe"]
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(keep)
            for s in rows: w.writerow([s.get(k) for k in keep])
        print(f"| # | 종목명 | 코드 | 현재가 | 시가총액(백만) |")
        print("|---|---|---|---|---|")
        for i,s in enumerate(rows,1):
            print(f'| {i} | {s.get("stockName")} | {s.get("itemCode")} | {s.get("closePrice")} | {s.get("marketValue")} |')
        print(f"\n저장: {p}  (총 {len(rows)}종목)")

    elif cmd=="fin":
        code=sys.argv[2]; period=sys.argv[3] if len(sys.argv)>3 else "annual"
        rows,titles,cons=finance(code,period)
        hdrs=list(rows[0].keys()) if rows else []
        print("| "+" | ".join(h+("(E)" if cons.get([k for k,v in titles.items() if v==h] [0] if h in titles.values() else "")=="Y" else "") if False else h for h in hdrs)+" |")
        print("|"+"---|"*len(hdrs))
        for r in rows: print("| "+" | ".join(str(r.get(h) or "-") for h in hdrs)+" |")
        p=f"data/fin-{code}-{period}-{stamp}.csv"
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=hdrs); w.writeheader(); w.writerows(rows)
        print(f"\n단위 억원 · (E)=컨센서스 · 저장 {p}")

    elif cmd=="ind":
        code=sys.argv[2]; ind,name=indicators(code)
        print(f"## {name} ({code})\n")
        for k,v in ind.items(): print(f"- {k}: {v}")

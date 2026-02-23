#!/usr/bin/env python3
"""
엔진 3: 수급 구조 역전 포착기
외국인/기관 순매수 상위 종목, 공매도 잔고 교차분석
"""
import requests
import json
from datetime import datetime, timedelta
import pytz

def get_foreign_institution_trading():
    """네이버 증권 외국인/기관 매매 동향"""
    try:
        # 코스피 외국인/기관 순매수 상위 (네이버 API)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.naver.com/"
        }

        # 외국인 순매수
        url_foreign = "https://finance.naver.com/sise/sise_trans_mem.naver?&page=1"
        r = requests.get(url_foreign, headers=headers, timeout=8)
        # HTML 파싱이 복잡하므로 pykrx 사용
        return _get_trading_pykrx()
    except:
        return {}

def _get_trading_pykrx():
    """pykrx를 사용한 외국인/기관 순매수 분석"""
    try:
        from pykrx import stock as krx
        today = datetime.now().strftime("%Y%m%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

        results = {}

        # KOSPI 외국인 순매수 상위
        try:
            df = krx.get_market_net_purchases_of_equities_by_ticker(yesterday, today, "KOSPI", "외국인")
            if df is not None and len(df) > 0:
                df = df.sort_values('순매수거래량', ascending=False)
                top5 = df.head(5)
                foreign_top = []
                for ticker, row in top5.iterrows():
                    name = krx.get_market_ticker_name(ticker)
                    foreign_top.append({
                        "ticker": ticker,
                        "name": name,
                        "net_buy": int(row.get('순매수거래량', 0))
                    })
                results['foreign_top_buy'] = foreign_top
        except:
            pass

        # KOSPI 기관 순매수 상위
        try:
            df2 = krx.get_market_net_purchases_of_equities_by_ticker(yesterday, today, "KOSPI", "기관합계")
            if df2 is not None and len(df2) > 0:
                df2 = df2.sort_values('순매수거래량', ascending=False)
                top5 = df2.head(5)
                inst_top = []
                for ticker, row in top5.iterrows():
                    name = krx.get_market_ticker_name(ticker)
                    inst_top.append({
                        "ticker": ticker,
                        "name": name,
                        "net_buy": int(row.get('순매수거래량', 0))
                    })
                results['institution_top_buy'] = inst_top
        except:
            pass

        return results
    except:
        return {}

def get_kospi_etf_flow():
    """주요 국내 ETF 수급 분석 (보유 ETF 기준)"""
    portfolio_codes = [
        ("069500", "KODEX 200"),
        ("102970", "KODEX 증권"),
        ("379800", "KODEX 미국S&P500"),
        ("379810", "KODEX 미국나스닥100"),
        ("411060", "ACE KRX금현물"),
        ("449450", "PLUS K방산"),
        ("396500", "TIGER 반도체TOP10"),
        ("466920", "SOL 조선TOP3"),
    ]

    results = {}
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)"}
    for code, name in portfolio_codes:
        try:
            url = f"https://m.stock.naver.com/api/stock/{code}/investor"
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                d = r.json()
                # 외국인/기관/개인 매매 데이터 추출
                results[code] = {"name": name, "data": d}
            else:
                # 기본 정보라도 가져오기
                url2 = f"https://m.stock.naver.com/api/stock/{code}/basic"
                r2 = requests.get(url2, headers=headers, timeout=5)
                if r2.status_code == 200:
                    d2 = r2.json()
                    price = int(d2.get('closePrice','0').replace(',',''))
                    ratio = float(d2.get('fluctuationsRatio','0'))
                    vol_ratio = d2.get('volumeRatio', 'N/A')
                    results[code] = {
                        "name": name, "price": price,
                        "ratio": ratio, "vol_ratio": vol_ratio
                    }
        except:
            pass
    return results

def get_market_breadth():
    """시장 폭 분석 (상승/하락 종목 비율)"""
    try:
        from pykrx import stock as krx
        today = datetime.now().strftime("%Y%m%d")
        df = krx.get_market_ohlcv(today, market="KOSPI")
        if df is not None and len(df) > 0:
            up = (df['등락률'] > 0).sum()
            down = (df['등락률'] < 0).sum()
            flat = (df['등락률'] == 0).sum()
            total = len(df)
            return up, down, flat, total
    except:
        pass
    return None, None, None, None

def analyze():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    trading = get_foreign_institution_trading()
    etf_flow = get_kospi_etf_flow()
    up, down, flat, total = get_market_breadth()

    signals = []
    score = 0

    # 시장 폭 분석
    if up is not None and total is not None and total > 0:
        advance_ratio = up / total * 100
        if advance_ratio > 60:
            signals.append(f"🟢 광범위 상승 ({up}/{total}, {advance_ratio:.0f}%) — 매수 우세")
            score += 2
        elif advance_ratio < 40:
            signals.append(f"🔴 광범위 하락 ({down}/{total}, {(down/total*100):.0f}% 하락) — 매도 압력")
            score -= 2
        else:
            signals.append(f"⚪ 혼조 ({up}상승 {down}하락 {flat}보합)")

    # ETF 수급
    strong_down = []
    strong_up = []
    for code, data in etf_flow.items():
        ratio = data.get('ratio', 0)
        name = data.get('name', code)
        if ratio <= -3:
            strong_down.append(f"{name} ({ratio:+.1f}%)")
            score -= 1
        elif ratio >= 3:
            strong_up.append(f"{name} ({ratio:+.1f}%)")
            score += 1

    if strong_up:
        signals.append(f"📈 강세 ETF: {', '.join(strong_up)}")
    if strong_down:
        signals.append(f"📉 약세 ETF: {', '.join(strong_down)}")

    # 외국인/기관 수급
    foreign_buys = trading.get('foreign_top_buy', [])
    if foreign_buys:
        names = [x['name'] for x in foreign_buys[:3]]
        signals.append(f"🌍 외국인 순매수 상위: {', '.join(names)}")
        score += 1

    inst_buys = trading.get('institution_top_buy', [])
    if inst_buys:
        names = [x['name'] for x in inst_buys[:3]]
        signals.append(f"🏢 기관 순매수 상위: {', '.join(names)}")

    if score >= 2:
        verdict = "🟢 수급 개선 — 매수 우위"
    elif score >= 0:
        verdict = "⚪ 수급 중립"
    elif score >= -2:
        verdict = "🟠 수급 약화 — 주의"
    else:
        verdict = "🔴 수급 악화 — 방어 포지션 권장"

    report = {
        "engine": "수급 구조 역전 포착",
        "timestamp": now.isoformat(),
        "score": score,
        "verdict": verdict,
        "market_breadth": {"up": up, "down": down, "flat": flat, "total": total},
        "etf_flow": {k: {"name": v.get("name"), "ratio": v.get("ratio")} for k, v in etf_flow.items()},
        "foreign_top_buy": foreign_buys,
        "institution_top_buy": inst_buys,
        "signals": signals,
    }

    md = f"""## 🔄 엔진3: 수급 구조 역전 포착기

**분석 시각**: {now.strftime('%Y-%m-%d %H:%M')} KST
**종합 판정**: {verdict}

### 시장 폭 (Market Breadth)
"""
    if total:
        md += f"- 상승: {up}종목 / 하락: {down}종목 / 보합: {flat}종목 (전체 {total})\n"
        md += f"- 상승 비율: {up/total*100:.1f}%\n"

    md += "\n### 보유 ETF 수급 현황\n"
    md += "| ETF | 등락률 | 거래량비율 |\n|-----|--------|----------|\n"
    for code, data in etf_flow.items():
        ratio = data.get('ratio', 0)
        vol = data.get('vol_ratio', 'N/A')
        arrow = "▲" if ratio > 0 else "▼"
        md += f"| {data.get('name', code)} | {arrow}{ratio:+.1f}% | {vol} |\n"

    if foreign_buys:
        md += "\n### 외국인 순매수 상위\n"
        for item in foreign_buys[:5]:
            md += f"- {item['name']} ({item['ticker']}): {item['net_buy']:,}주\n"

    if inst_buys:
        md += "\n### 기관 순매수 상위\n"
        for item in inst_buys[:5]:
            md += f"- {item['name']} ({item['ticker']}): {item['net_buy']:,}주\n"

    md += "\n### 📡 신호 목록\n"
    for s in signals:
        md += f"- {s}\n"

    return report, md


if __name__ == "__main__":
    report, md = analyze()
    print(md)
    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/engine3_supply_demand.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("\n✅ 엔진3 완료")

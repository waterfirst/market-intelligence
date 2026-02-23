#!/usr/bin/env python3
"""
엔진 2: 밸류에이션 왜곡 탐지기
코스피 섹터별 PER/PBR, 미국 주요지수 밸류에이션 분석
"""
import yfinance as yf
import requests
import json
from datetime import datetime
import pytz

def get_kospi_sector_valuation():
    """코스피 주요 섹터 ETF를 통한 밸류에이션 추정"""
    sector_etfs = {
        "반도체": ("091160", "KODEX반도체"),
        "자동차": ("091180", "KODEX자동차"),
        "금융": ("139270", "KODEX금융"),
        "바이오": ("244580", "KODEX바이오"),
        "에너지": ("117460", "KODEX에너지화학"),
    }

    results = {}
    for sector, (code, name) in sector_etfs.items():
        try:
            url = f"https://m.stock.naver.com/api/stock/{code}/basic"
            headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)"}
            r = requests.get(url, headers=headers, timeout=5)
            d = r.json()
            price = int(d.get('closePrice','0').replace(',',''))
            per = d.get('per', 'N/A')
            pbr = d.get('pbr', 'N/A')
            ratio = float(d.get('fluctuationsRatio', '0'))
            results[sector] = {
                "name": name, "price": price,
                "per": per, "pbr": pbr, "ratio": ratio
            }
        except:
            pass
    return results

def get_us_market_valuation():
    """미국 시장 주요 지표"""
    tickers = {
        "S&P500": "^GSPC",
        "나스닥": "^IXIC",
        "러셀2000": "^RUT",
    }
    results = {}
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev_5 = hist['Close'].iloc[0]
                chg = (curr - prev_5) / prev_5 * 100
                results[name] = {"price": curr, "5d_chg": chg}
        except:
            pass
    return results

def get_buffett_indicator():
    """버핏 지표 대리 변수 - Wilshire5000/GDP 근사치
    실제 데이터 대신 SPY 시가총액 기반 추정"""
    try:
        # 미국 GDP 대비 주식시장 지표 (근사)
        spy = yf.Ticker("SPY")
        info = spy.fast_info
        spy_price = info.last_price if hasattr(info, 'last_price') else None

        # SP500 P/E는 별도로 알려진 근사값 사용
        # 실시간으로 구하기 어려우니 CAPE(Shiller P/E) 근사값 제공
        # 2024년 기준 CAPE ~35 (역사적 평균 ~17)
        cape_note = "역사적 평균 ~17, 현재 추정 ~33-37 (과고평가 구간)"

        return spy_price, cape_note
    except:
        return None, None

def get_gold_ratio():
    """금/S&P500 비율 (방어 선호도 지표)"""
    try:
        gold = yf.Ticker("GLD")
        spy = yf.Ticker("SPY")
        gh = gold.history(period="30d")
        sh = spy.history(period="30d")
        if len(gh) > 0 and len(sh) > 0:
            g_curr = gh['Close'].iloc[-1]
            g_prev = gh['Close'].iloc[0]
            s_curr = sh['Close'].iloc[-1]
            s_prev = sh['Close'].iloc[0]
            gold_30d = (g_curr - g_prev) / g_prev * 100
            spy_30d = (s_curr - s_prev) / s_prev * 100
            return gold_30d, spy_30d
    except:
        pass
    return None, None

def analyze():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    kospi_sectors = get_kospi_sector_valuation()
    us_markets = get_us_market_valuation()
    spy_price, cape_note = get_buffett_indicator()
    gold_30d, spy_30d = get_gold_ratio()

    signals = []
    score = 0

    # 금 vs 주식 비교
    if gold_30d is not None and spy_30d is not None:
        if gold_30d > spy_30d + 3:
            signals.append(f"🥇 금 강세 vs 주식 ({gold_30d:+.1f}% vs {spy_30d:+.1f}%) — 방어 심리 강화")
            score -= 1
        elif spy_30d > gold_30d + 3:
            signals.append(f"📈 주식 강세 vs 금 ({spy_30d:+.1f}% vs {gold_30d:+.1f}%) — 위험선호")
            score += 1
        else:
            signals.append(f"⚖️ 금/주식 균형 (금:{gold_30d:+.1f}%, 주식:{spy_30d:+.1f}%)")

    # CAPE 경고
    signals.append(f"📊 Shiller CAPE: {cape_note}")

    # 코스피 섹터 신호
    for sector, data in kospi_sectors.items():
        ratio = data.get('ratio', 0)
        if abs(ratio) >= 2:
            arrow = "▲" if ratio > 0 else "▼"
            signals.append(f"{'🟢' if ratio > 0 else '🔴'} {sector}: {arrow}{ratio:+.1f}%")

    if score >= 2:
        verdict = "🟢 밸류에이션 매력적 — 매수 기회"
    elif score >= 0:
        verdict = "⚪ 밸류에이션 중립 — 선별적 접근"
    elif score >= -1:
        verdict = "🟠 밸류에이션 주의 — 고평가 구간"
    else:
        verdict = "🔴 밸류에이션 과도 — 매수 신중"

    report = {
        "engine": "밸류에이션 왜곡 탐지",
        "timestamp": now.isoformat(),
        "score": score,
        "verdict": verdict,
        "us_markets": us_markets,
        "kospi_sectors": kospi_sectors,
        "cape_note": cape_note,
        "gold_vs_spy_30d": {"gold": gold_30d, "spy": spy_30d},
        "signals": signals,
    }

    md = f"""## 📊 엔진2: 밸류에이션 왜곡 탐지기

**분석 시각**: {now.strftime('%Y-%m-%d %H:%M')} KST
**종합 판정**: {verdict}

### 미국 시장
"""
    for name, data in us_markets.items():
        chg = data.get('5d_chg', 0)
        arrow = "▲" if chg > 0 else "▼"
        md += f"- {name}: {data['price']:,.0f} ({arrow}{chg:+.1f}% 5일)\n"

    md += "\n### 코스피 섹터 ETF\n"
    md += "| 섹터 | ETF | 등락률 | PER | PBR |\n|------|-----|--------|-----|-----|\n"
    for sector, data in kospi_sectors.items():
        ratio = data.get('ratio', 0)
        arrow = "▲" if ratio > 0 else "▼"
        md += f"| {sector} | {data['name']} | {arrow}{ratio:+.1f}% | {data.get('per','N/A')} | {data.get('pbr','N/A')} |\n"

    md += f"""
### 밸류에이션 지표
- **Shiller CAPE(P/E10)**: {cape_note}
- **금 30일 수익률**: {f'{gold_30d:+.1f}%' if gold_30d else 'N/A'}
- **S&P500 30일 수익률**: {f'{spy_30d:+.1f}%' if spy_30d else 'N/A'}

### 📡 신호 목록
"""
    for s in signals:
        md += f"- {s}\n"

    return report, md


if __name__ == "__main__":
    report, md = analyze()
    print(md)
    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/engine2_valuation.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("\n✅ 엔진2 완료")

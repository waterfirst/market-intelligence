#!/usr/bin/env python3
"""
엔진 6: 거시 시나리오 확률 게임
금리인하가속 / 스태그플레이션 / 경기침체 / 연착륙 시나리오 확률 산출
"""
import yfinance as yf
import requests
import json
from datetime import datetime, timedelta
import pytz

SCENARIOS = {
    "연착륙": {
        "desc": "인플레 안정 + 성장 유지",
        "portfolio_impact": "주식 보유 유지, 모든 섹터 호조",
        "best_etf": ["KODEX 200", "KODEX 미국S&P500", "KODEX 미국나스닥100"],
    },
    "금리인하가속": {
        "desc": "경기 냉각 → Fed 빠른 금리 인하",
        "portfolio_impact": "성장주·채권 강세, 금융주 약세",
        "best_etf": ["KODEX 미국나스닥100", "KODEX 200미국채혼합"],
    },
    "스태그플레이션": {
        "desc": "경기 둔화 + 물가 재상승",
        "portfolio_impact": "금·원자재 강세, 성장주 약세",
        "best_etf": ["ACE KRX금현물"],
    },
    "경기침체": {
        "desc": "본격 침체, 실업 급증",
        "portfolio_impact": "전반적 하락, 현금·금·채권 방어",
        "best_etf": ["ACE KRX금현물", "KODEX 200미국채혼합"],
    },
}

def get_macro_indicators():
    """거시경제 지표 수집"""
    indicators = {}

    # 10Y-2Y 금리차
    try:
        t10 = yf.Ticker("^TNX")
        t2 = yf.Ticker("^IRX")
        h10 = t10.history(period="5d")
        h2 = t2.history(period="5d")
        if len(h10) > 0 and len(h2) > 0:
            rate10 = h10['Close'].iloc[-1]
            rate2 = h2['Close'].iloc[-1] / 10
            indicators['yield_spread'] = rate10 - rate2
            indicators['rate_10y'] = rate10
            indicators['rate_2y'] = rate2
    except:
        pass

    # 원/달러
    try:
        krw = yf.Ticker("KRW=X")
        hist = krw.history(period="30d")
        if len(hist) >= 2:
            indicators['krw_usd'] = hist['Close'].iloc[-1]
            indicators['krw_30d_chg'] = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] * 100
    except:
        pass

    # 유가
    try:
        oil = yf.Ticker("CL=F")
        hist = oil.history(period="30d")
        if len(hist) >= 2:
            indicators['oil_price'] = hist['Close'].iloc[-1]
            indicators['oil_30d_chg'] = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] * 100
    except:
        pass

    # 구리 (경기선행)
    try:
        copper = yf.Ticker("HG=F")
        hist = copper.history(period="30d")
        if len(hist) >= 2:
            indicators['copper_price'] = hist['Close'].iloc[-1]
            indicators['copper_30d_chg'] = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] * 100
    except:
        pass

    # VIX
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if len(hist) > 0:
            indicators['vix'] = hist['Close'].iloc[-1]
    except:
        pass

    # 공포탐욕
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = r.json()['data'][0]
        indicators['fear_greed'] = int(data['value'])
        indicators['fear_greed_label'] = data['value_classification']
    except:
        pass

    return indicators

def calculate_scenario_probabilities(indicators):
    """지표 기반 시나리오 확률 계산"""
    probs = {
        "연착륙": 35,       # 기본값
        "금리인하가속": 25,
        "스태그플레이션": 20,
        "경기침체": 20,
    }

    spread = indicators.get('yield_spread')
    oil_chg = indicators.get('oil_30d_chg', 0)
    copper_chg = indicators.get('copper_30d_chg', 0)
    krw_chg = indicators.get('krw_30d_chg', 0)
    vix = indicators.get('vix', 20)
    fg = indicators.get('fear_greed', 50)

    reasons = []

    # 금리차 역전 → 경기침체/금리인하 확률 증가
    if spread is not None:
        if spread < -0.5:
            probs["경기침체"] += 15
            probs["금리인하가속"] += 10
            probs["연착륙"] -= 15
            probs["스태그플레이션"] -= 10
            reasons.append(f"장단기 금리 역전({spread:+.2f}%p) → 침체 신호")
        elif spread < 0:
            probs["경기침체"] += 8
            probs["금리인하가속"] += 5
            probs["연착륙"] -= 8
            probs["스태그플레이션"] -= 5
            reasons.append(f"금리차 축소({spread:+.2f}%p) → 주의")
        elif spread > 1.5:
            probs["연착륙"] += 10
            probs["경기침체"] -= 10
            reasons.append(f"정상 수익률곡선({spread:+.2f}%p) → 연착륙 지지")

    # 유가 급등 → 스태그플레이션
    if oil_chg > 10:
        probs["스태그플레이션"] += 15
        probs["연착륙"] -= 10
        probs["금리인하가속"] -= 5
        reasons.append(f"유가 급등({oil_chg:+.1f}%) → 스태그 우려")
    elif oil_chg < -10:
        probs["스태그플레이션"] -= 10
        probs["경기침체"] += 5
        probs["연착륙"] += 5
        reasons.append(f"유가 급락({oil_chg:+.1f}%) → 수요 둔화 or 인플레 완화")

    # 구리 = 경기 선행
    if copper_chg > 5:
        probs["연착륙"] += 8
        probs["경기침체"] -= 8
        reasons.append(f"구리 강세({copper_chg:+.1f}%) → 경기 회복 시그널")
    elif copper_chg < -5:
        probs["경기침체"] += 10
        probs["연착륙"] -= 10
        reasons.append(f"구리 약세({copper_chg:+.1f}%) → 경기 둔화 경고")

    # VIX
    if vix > 30:
        probs["경기침체"] += 10
        probs["연착륙"] -= 10
        reasons.append(f"VIX 고공비행({vix:.0f}) → 시장 공포")
    elif vix < 15:
        probs["연착륙"] += 5
        probs["금리인하가속"] += 3
        reasons.append(f"VIX 안정({vix:.0f}) → 시장 안도")

    # 원/달러 (한국 특수)
    if krw_chg > 3:  # 원화 약세
        probs["경기침체"] += 5
        probs["스태그플레이션"] += 5
        probs["연착륙"] -= 5
        reasons.append(f"원화 약세({krw_chg:+.1f}%) → 외국인 이탈 우려")

    # 확률 정규화 (합이 100이 되도록)
    total = sum(probs.values())
    probs = {k: max(5, round(v / total * 100)) for k, v in probs.items()}

    # 재정규화
    total2 = sum(probs.values())
    diff = 100 - total2
    probs["연착륙"] += diff

    return probs, reasons

def analyze():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    indicators = get_macro_indicators()
    probs, reasons = calculate_scenario_probabilities(indicators)

    # 최고 확률 시나리오
    top_scenario = max(probs, key=probs.get)
    top_prob = probs[top_scenario]
    top_info = SCENARIOS[top_scenario]

    signals = []
    for reason in reasons:
        signals.append(reason)

    if top_prob >= 40:
        verdict = f"🎯 {top_scenario} 시나리오 우세 ({top_prob}%) — {top_info['desc']}"
    else:
        # 1위/2위 차이가 적으면
        sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        verdict = f"🔀 혼재 시나리오 (1위: {sorted_probs[0][0]} {sorted_probs[0][1]}%, 2위: {sorted_probs[1][0]} {sorted_probs[1][1]}%)"

    report = {
        "engine": "거시 시나리오 확률 게임",
        "timestamp": now.isoformat(),
        "scenario_probabilities": probs,
        "top_scenario": top_scenario,
        "verdict": verdict,
        "indicators": {k: round(v, 3) if isinstance(v, float) else v for k, v in indicators.items()},
        "reasons": reasons,
        "signals": signals,
    }

    md = f"""## 🎲 엔진6: 거시 시나리오 확률 게임

**분석 시각**: {now.strftime('%Y-%m-%d %H:%M')} KST
**종합 판정**: {verdict}

### 📊 시나리오 확률 분포
"""
    # 확률 바 차트 (텍스트)
    for scenario, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * (prob // 5) + "░" * (20 - prob // 5)
        info = SCENARIOS[scenario]
        md += f"\n**{scenario}** ({prob}%)\n"
        md += f"`{bar}` {prob}%\n"
        md += f"  → {info['desc']}\n"
        md += f"  → 영향: {info['portfolio_impact']}\n"

    md += f"""
### 주요 거시지표
| 지표 | 값 | 신호 |
|------|-----|------|
| 10Y-2Y 금리차 | {f"{indicators.get('yield_spread', 0):+.2f}%p" if indicators.get('yield_spread') else 'N/A'} | {'⚠️역전' if indicators.get('yield_spread', 0) < 0 else '✅정상'} |
| 유가(WTI) | {f"${indicators.get('oil_price', 0):.1f} ({indicators.get('oil_30d_chg', 0):+.1f}%)" if indicators.get('oil_price') else 'N/A'} | |
| 구리 | {f"${indicators.get('copper_price', 0):.2f} ({indicators.get('copper_30d_chg', 0):+.1f}%)" if indicators.get('copper_price') else 'N/A'} | |
| 원/달러 | {f"{indicators.get('krw_usd', 0):,.0f}원 ({indicators.get('krw_30d_chg', 0):+.1f}%)" if indicators.get('krw_usd') else 'N/A'} | |
| VIX | {f"{indicators.get('vix', 0):.1f}" if indicators.get('vix') else 'N/A'} | |
| 공포&탐욕 | {f"{indicators.get('fear_greed', 0)} ({indicators.get('fear_greed_label', '')})" if indicators.get('fear_greed') else 'N/A'} | |

### 🏆 최우선 시나리오 대응 전략
- **시나리오**: {top_scenario} ({top_prob}%)
- **특성**: {SCENARIOS[top_scenario]['desc']}
- **portfolio 영향**: {SCENARIOS[top_scenario]['portfolio_impact']}
- **유리한 ETF**: {', '.join(SCENARIOS[top_scenario]['best_etf'])}

### 📡 근거 목록
"""
    for r in reasons:
        md += f"- {r}\n"

    return report, md


if __name__ == "__main__":
    report, md = analyze()
    print(md)
    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/engine6_macro_scenarios.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("\n✅ 엔진6 완료")

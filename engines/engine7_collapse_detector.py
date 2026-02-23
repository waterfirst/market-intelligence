#!/usr/bin/env python3
"""
엔진 7: 붕괴 가능성 탐지기
시장 전반 & 개별 보유 ETF의 급락/붕괴 조기 경보 시스템
영업현금흐름, 단기차입금, 이자보상배율, 기술적 붕괴 신호
"""
import requests
import yfinance as yf
import json
from datetime import datetime, timedelta
import pytz

# 붕괴 위험 모니터링 대상 (보유 ETF 기반)
MONITOR_ASSETS = {
    "KODEX 200": {"code": "069500", "type": "krx"},
    "KODEX 증권": {"code": "102970", "type": "krx"},
    "KODEX 미국S&P500": {"code": "379800", "type": "krx"},
    "KODEX 미국나스닥100": {"code": "379810", "type": "krx"},
    "ACE KRX금현물": {"code": "411060", "type": "krx"},
    "PLUS K방산": {"code": "449450", "type": "krx"},
    "TIGER 반도체TOP10": {"code": "396500", "type": "krx"},
    "SOL 조선TOP3": {"code": "466920", "type": "krx"},
}

# 글로벌 시스템 리스크 지표
SYSTEMIC_INDICATORS = {
    "S&P500": "^GSPC",
    "VIX": "^VIX",
    "HYG (하이일드채권)": "HYG",  # 크레딧 스프레드 대리
    "TLT (장기국채)": "TLT",
    "GLD (금)": "GLD",
    "달러인덱스": "DX-Y.NYB",
}

def get_krx_technical_signal(code):
    """국내 ETF 기술적 붕괴 신호 감지"""
    try:
        from pykrx import stock as krx
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        df = krx.get_market_ohlcv(start, end, code)
        df = df[df['거래량'] > 0].copy()
        if len(df) < 20:
            return None

        closes = df['종가']
        curr = closes.iloc[-1]
        ma20 = closes.rolling(20).mean().iloc[-1]
        ma60 = closes.rolling(60).mean().iloc[-1] if len(df) >= 60 else None

        # RSI
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - 100 / (1 + rs)).iloc[-1]

        # 볼린저 밴드
        ma20_ser = closes.rolling(20).mean()
        std20 = closes.rolling(20).std().iloc[-1]
        lower_band = ma20 - 2 * std20
        upper_band = ma20 + 2 * std20
        boll_pct = (curr - lower_band) / (upper_band - lower_band) * 100

        # 최근 5일 낙폭
        prev5 = closes.iloc[-5] if len(df) >= 5 else closes.iloc[0]
        drop5d = (curr - prev5) / prev5 * 100

        collapse_signals = []
        risk_score = 0

        # RSI 과매도
        if rsi < 25:
            collapse_signals.append(f"🟢 RSI {rsi:.0f} — 역발상 매수 구간")
            risk_score -= 1  # 매수 기회
        elif rsi < 35:
            collapse_signals.append(f"🟡 RSI {rsi:.0f} — 하락 압력")
            risk_score += 1

        # 볼린저 하단 이탈
        if boll_pct < 0:
            collapse_signals.append(f"🔴 볼린저 하단 이탈 ({boll_pct:.0f}%) — 붕괴 구간")
            risk_score += 2
        elif boll_pct < 10:
            collapse_signals.append(f"🟠 볼린저 하단 근접 ({boll_pct:.0f}%)")
            risk_score += 1

        # MA20 하단
        if curr < ma20 * 0.95:
            collapse_signals.append(f"📉 MA20 5% 이상 이탈 — 하락 추세")
            risk_score += 2
        elif curr < ma20:
            collapse_signals.append(f"⬇️ MA20 하단 ({(curr/ma20-1)*100:+.1f}%)")
            risk_score += 1

        # 5일 낙폭
        if drop5d < -5:
            collapse_signals.append(f"⚡ 5일 급락 ({drop5d:+.1f}%) — 매도 폭탄")
            risk_score += 2

        return {
            "price": curr, "rsi": round(rsi, 1),
            "boll_pct": round(boll_pct, 1), "ma20": round(ma20, 0),
            "drop_5d": round(drop5d, 1),
            "risk_score": risk_score,
            "signals": collapse_signals,
        }
    except:
        return None

def get_global_systemic_risk():
    """글로벌 시스템 리스크 분석"""
    results = {}
    for name, ticker in SYSTEMIC_INDICATORS.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="30d")
            if len(hist) >= 5:
                curr = hist['Close'].iloc[-1]
                prev5 = hist['Close'].iloc[-5]
                prev30 = hist['Close'].iloc[0]
                chg5d = (curr - prev5) / prev5 * 100
                chg30d = (curr - prev30) / prev30 * 100
                results[name] = {"price": curr, "5d": chg5d, "30d": chg30d}
        except:
            pass
    return results

def calculate_crash_probability(etf_results, systemic):
    """종합 붕괴 확률 계산"""
    total_risk = 0
    max_risk = 0

    for name, data in etf_results.items():
        if data:
            total_risk += max(0, data.get('risk_score', 0))
            max_risk += 5  # 최대 위험점수

    # VIX 반영
    vix_data = systemic.get("VIX", {})
    vix = vix_data.get('price', 20)
    if vix > 35:
        total_risk += 5
        max_risk += 5
    elif vix > 25:
        total_risk += 2
        max_risk += 5

    # HYG (신용시장) 반영
    hyg_data = systemic.get("HYG (하이일드채권)", {})
    hyg_5d = hyg_data.get('5d', 0)
    if hyg_5d < -2:
        total_risk += 3
        max_risk += 3

    crash_prob = (total_risk / max_risk * 100) if max_risk > 0 else 0
    return min(crash_prob, 95), total_risk

def analyze():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    # ETF별 기술적 리스크
    etf_results = {}
    for name, info in MONITOR_ASSETS.items():
        result = get_krx_technical_signal(info['code'])
        etf_results[name] = result

    # 글로벌 시스템 리스크
    systemic = get_global_systemic_risk()

    # 종합 붕괴 확률
    crash_prob, total_risk = calculate_crash_probability(etf_results, systemic)

    # 가장 위험한 ETF
    high_risk_etfs = []
    for name, data in etf_results.items():
        if data and data.get('risk_score', 0) >= 3:
            high_risk_etfs.append((name, data['risk_score'], data.get('drop_5d', 0)))
    high_risk_etfs.sort(key=lambda x: x[1], reverse=True)

    # 가장 건전한 ETF (역발상 매수 기회)
    buy_opportunity_etfs = []
    for name, data in etf_results.items():
        if data and data.get('risk_score', 0) <= -1 and data.get('rsi', 50) < 35:
            buy_opportunity_etfs.append((name, data['risk_score'], data.get('rsi', 0)))

    signals = []
    if crash_prob > 60:
        signals.append(f"🚨 시장 붕괴 위험 높음 ({crash_prob:.0f}%) — 현금 비중 확대 검토")
    elif crash_prob > 35:
        signals.append(f"⚠️ 중간 위험 ({crash_prob:.0f}%) — 손절선 점검")
    else:
        signals.append(f"✅ 위험 낮음 ({crash_prob:.0f}%) — 정상 시장")

    for name, risk, drop in high_risk_etfs[:3]:
        signals.append(f"🔴 [{name}] 리스크 점수: {risk}, 5일 낙폭: {drop:+.1f}%")

    for name, risk, rsi in buy_opportunity_etfs[:2]:
        signals.append(f"💎 역발상 기회: [{name}] RSI {rsi:.0f} 과매도")

    if crash_prob > 60:
        verdict = "🚨 붕괴 경보 — 즉시 포지션 점검"
    elif crash_prob > 35:
        verdict = "⚠️ 조정 국면 — 손절선 확인 필요"
    elif crash_prob > 20:
        verdict = "🟡 주의 구간 — 모니터링 강화"
    else:
        verdict = "✅ 안정 구간 — 정상 보유 유지"

    report = {
        "engine": "붕괴 가능성 탐지",
        "timestamp": now.isoformat(),
        "crash_probability": round(crash_prob, 1),
        "verdict": verdict,
        "etf_risk_summary": {
            k: {"risk_score": v.get('risk_score', 0), "drop_5d": v.get('drop_5d', 0), "rsi": v.get('rsi', 0)}
            if v else None for k, v in etf_results.items()
        },
        "systemic_indicators": {k: {"5d": round(v['5d'], 2), "30d": round(v['30d'], 2)} for k, v in systemic.items()},
        "high_risk": high_risk_etfs,
        "buy_opportunities": buy_opportunity_etfs,
        "signals": signals,
    }

    vix_val = systemic.get('VIX', {}).get('price', 0)
    hyg_5d = systemic.get('HYG (하이일드채권)', {}).get('5d', 0)

    md = f"""## 🚨 엔진7: 붕괴 가능성 탐지기

**분석 시각**: {now.strftime('%Y-%m-%d %H:%M')} KST
**종합 판정**: {verdict}
**붕괴 확률**: {crash_prob:.0f}%

### 🌍 글로벌 시스템 리스크 지표
| 지표 | 현재가 | 5일 | 30일 |
|------|--------|-----|-----|
"""
    for name, data in systemic.items():
        price = data.get('price', 0)
        c5d = data.get('5d', 0)
        c30d = data.get('30d', 0)
        md += f"| {name} | {price:.1f} | {c5d:+.1f}% | {c30d:+.1f}% |\n"

    md += "\n### 📊 보유 ETF 리스크 현황\n"
    md += "| ETF | RSI | 5일낙폭 | 볼밴% | 위험점수 |\n|-----|-----|--------|------|--------|\n"
    for name, data in etf_results.items():
        if data:
            risk = data.get('risk_score', 0)
            risk_emoji = "🔴" if risk >= 3 else "🟠" if risk >= 2 else "🟡" if risk >= 1 else "🟢" if risk <= -1 else "⚪"
            md += f"| {name[:12]} | {data.get('rsi', 0):.0f} | {data.get('drop_5d', 0):+.1f}% | {data.get('boll_pct', 0):.0f}% | {risk_emoji}{risk} |\n"

    if high_risk_etfs:
        md += "\n### ⚠️ 고위험 ETF (즉시 점검)\n"
        for name, risk, drop in high_risk_etfs:
            md += f"- **{name}**: 리스크점수 {risk}, 5일낙폭 {drop:+.1f}%\n"
            if etf_results.get(name):
                for sig in etf_results[name].get('signals', [])[:3]:
                    md += f"  - {sig}\n"

    if buy_opportunity_etfs:
        md += "\n### 💎 역발상 매수 기회\n"
        for name, risk, rsi in buy_opportunity_etfs:
            md += f"- **{name}**: RSI {rsi:.0f} 과매도 — 반등 가능성\n"

    md += "\n### 📡 신호 목록\n"
    for s in signals:
        md += f"- {s}\n"

    return report, md


if __name__ == "__main__":
    report, md = analyze()
    print(md)
    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/engine7_collapse.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("\n✅ 엔진7 완료")

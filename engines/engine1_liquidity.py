#!/usr/bin/env python3
"""
엔진 1: 유동성 방향 감지 엔진
M2증가율, 실질금리, 장단기금리차, 달러인덱스, ETF자금 유입 분석
"""
import yfinance as yf
import requests
import json
from datetime import datetime, timedelta
import pytz

def get_yield_curve():
    """미국 국채 장단기 금리차 (10Y - 2Y)"""
    try:
        t10 = yf.Ticker("^TNX")
        t2 = yf.Ticker("^IRX")
        h10 = t10.history(period="5d")
        h2 = t2.history(period="5d")
        if len(h10) > 0 and len(h2) > 0:
            rate10 = h10['Close'].iloc[-1]
            rate2 = h2['Close'].iloc[-1] / 10  # IRX는 %*10 단위
            spread = rate10 - rate2
            return rate10, rate2, spread
    except:
        pass
    return None, None, None

def get_dxy():
    """달러 인덱스"""
    try:
        dxy = yf.Ticker("DX-Y.NYB")
        hist = dxy.history(period="5d")
        if len(hist) >= 2:
            curr = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2]
            chg = (curr - prev) / prev * 100
            return curr, chg
    except:
        pass
    return None, None

def get_global_etf_flows():
    """주요 ETF 자금 흐름 (SPY, QQQ, EEM, GLD)"""
    etfs = {
        "SPY (S&P500)": "SPY",
        "QQQ (나스닥)": "QQQ",
        "EEM (신흥국)": "EEM",
        "GLD (금)": "GLD",
        "TLT (장기채)": "TLT",
    }
    results = {}
    for name, ticker in etfs.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-5] if len(hist) >= 5 else hist['Close'].iloc[0]
                chg5d = (curr - prev) / prev * 100
                results[name] = (curr, chg5d)
        except:
            pass
    return results

def get_fear_greed():
    """공포&탐욕 지수"""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=2", timeout=5)
        data = r.json()['data']
        curr_val = int(data[0]['value'])
        curr_cls = data[0]['value_classification']
        prev_val = int(data[1]['value'])
        return curr_val, curr_cls, prev_val
    except:
        return None, None, None

def get_vix():
    """VIX 공포지수"""
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if len(hist) >= 2:
            curr = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2]
            chg = curr - prev
            return curr, chg
    except:
        return None, None

def analyze():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    rate10, rate2, spread = get_yield_curve()
    dxy, dxy_chg = get_dxy()
    etf_flows = get_global_etf_flows()
    fg_val, fg_cls, fg_prev = get_fear_greed()
    vix, vix_chg = get_vix()

    # 유동성 방향 판단
    signals = []
    score = 0  # 양수=유동성 공급, 음수=유동성 흡수

    if spread is not None:
        if spread < 0:
            signals.append(f"⚠️ 장단기금리 역전 ({spread:+.2f}%p) — 경기침체 경고")
            score -= 2
        elif spread > 0.5:
            signals.append(f"✅ 정상 수익률 곡선 ({spread:+.2f}%p) — 유동성 양호")
            score += 1
        else:
            signals.append(f"🔶 금리차 축소 ({spread:+.2f}%p) — 주의 필요")

    if dxy is not None:
        if dxy_chg > 0.5:
            signals.append(f"📉 달러 강세 ({dxy:.1f}, {dxy_chg:+.2f}%) — 신흥국 자금 이탈 우려")
            score -= 1
        elif dxy_chg < -0.5:
            signals.append(f"📈 달러 약세 ({dxy:.1f}, {dxy_chg:+.2f}%) — 위험자산 유리")
            score += 1
        else:
            signals.append(f"➡️ 달러 보합 ({dxy:.1f}, {dxy_chg:+.2f}%)")

    if vix is not None:
        if vix > 30:
            signals.append(f"🔴 VIX 공포 구간 ({vix:.1f}) — 시장 극도 불안")
            score -= 2
        elif vix > 20:
            signals.append(f"🟠 VIX 경계 구간 ({vix:.1f}) — 변동성 주의")
            score -= 1
        elif vix < 15:
            signals.append(f"🟢 VIX 안정 구간 ({vix:.1f}) — 위험선호 환경")
            score += 1
        else:
            signals.append(f"🔵 VIX 정상 ({vix:.1f})")

    if fg_val is not None:
        if fg_val < 25:
            signals.append(f"😱 공포&탐욕: {fg_val} '{fg_cls}' — 역발상 매수 구간")
            score += 2
        elif fg_val > 75:
            signals.append(f"🤑 공포&탐욕: {fg_val} '{fg_cls}' — 과열 경고")
            score -= 1
        else:
            signals.append(f"😐 공포&탐욕: {fg_val} '{fg_cls}'")

    if score >= 3:
        verdict = "🟢🟢 강한 유동성 공급 — 위험자산 매수 유리"
    elif score >= 1:
        verdict = "🟢 유동성 우호적 — 점진적 매수 고려"
    elif score <= -3:
        verdict = "🔴🔴 강한 유동성 긴축 — 현금 비중 확대"
    elif score <= -1:
        verdict = "🔴 유동성 주의 — 방어적 포지션 권장"
    else:
        verdict = "⚪ 유동성 중립 — 선별적 접근"

    # 결과 구성
    report = {
        "engine": "유동성 방향 감지",
        "timestamp": now.isoformat(),
        "score": score,
        "verdict": verdict,
        "data": {
            "10Y_rate": rate10,
            "2Y_rate": rate2,
            "yield_spread": spread,
            "DXY": dxy,
            "DXY_5d_chg": dxy_chg,
            "VIX": vix,
            "fear_greed": fg_val,
            "fear_greed_label": fg_cls,
        },
        "etf_flows": etf_flows,
        "signals": signals,
    }

    # 마크다운 리포트
    md = f"""## 💧 엔진1: 유동성 방향 감지 엔진

**분석 시각**: {now.strftime('%Y-%m-%d %H:%M')} KST
**종합 판정**: {verdict}
**유동성 점수**: {score:+d}

### 주요 지표
| 지표 | 값 | 해석 |
|------|-----|------|
| 미국 10Y 국채 | {f'{rate10:.2f}%' if rate10 else 'N/A'} | |
| 미국 2Y 국채 | {f'{rate2:.2f}%' if rate2 else 'N/A'} | |
| 장단기 금리차 | {f'{spread:+.2f}%p' if spread else 'N/A'} | {'역전(위험)' if spread and spread < 0 else '정상'} |
| 달러 인덱스(DXY) | {f'{dxy:.1f} ({dxy_chg:+.2f}%)' if dxy else 'N/A'} | |
| VIX 공포지수 | {f'{vix:.1f}' if vix else 'N/A'} | |
| 공포&탐욕 지수 | {f'{fg_val} ({fg_cls})' if fg_val else 'N/A'} | |

### 📡 신호 목록
"""
    for s in signals:
        md += f"- {s}\n"

    md += "\n### 🌍 글로벌 ETF 5일 수익률\n"
    for name, (price, chg5d) in etf_flows.items():
        arrow = "▲" if chg5d > 0 else "▼"
        md += f"- {name}: {arrow}{chg5d:+.1f}%\n"

    return report, md


if __name__ == "__main__":
    report, md = analyze()
    print(md)
    # JSON 저장
    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/engine1_liquidity.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("\n✅ 엔진1 완료")

#!/usr/bin/env python3
"""
엔진 4: 산업 사이클 위치 진단
반도체/자동차/보험/조선/원자력 섹터 사이클 분석
"""
import requests
import yfinance as yf
import json
from datetime import datetime, timedelta
import pytz

# 섹터별 대표 ETF/종목 (한국)
SECTOR_ETF_MAP = {
    "반도체": {
        "code": "091160",  # KODEX 반도체
        "desc": "메모리·파운드리 수출 사이클",
        "cycle_indicator": "DRAM 가격, 삼성/SK 재고",
        "portfolio": ["396500"],  # TIGER 반도체TOP10
    },
    "조선": {
        "code": "466920",  # SOL 조선TOP3
        "desc": "LNG선/탱커 수주 사이클",
        "cycle_indicator": "Clarkson 신조선가, 수주잔고",
        "portfolio": ["466920"],
    },
    "방산": {
        "code": "449450",  # PLUS K방산
        "desc": "NATO 국방비 증가 사이클",
        "cycle_indicator": "국방예산, 수출계약",
        "portfolio": ["449450"],
    },
    "AI/인프라": {
        "code": "487230",  # KODEX AI전력인프라
        "desc": "AI 데이터센터 투자 사이클",
        "cycle_indicator": "빅테크 CAPEX, 전력수요",
        "portfolio": ["487230"],
    },
    "금융/증권": {
        "code": "102970",  # KODEX 증권
        "desc": "금리·주가지수 연동 사이클",
        "cycle_indicator": "증시거래대금, 금리",
        "portfolio": ["102970"],
    },
}

# 미국 섹터 ETF
US_SECTORS = {
    "반도체": "SOXX",
    "에너지": "XLE",
    "금융": "XLF",
    "헬스케어": "XLV",
    "테크": "XLK",
    "유틸리티": "XLU",
    "산업재": "XLI",
}

def get_sector_performance(code, is_krx=True):
    """섹터 ETF 성과 분석"""
    try:
        if is_krx:
            headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)"}
            url = f"https://m.stock.naver.com/api/stock/{code}/basic"
            r = requests.get(url, headers=headers, timeout=5)
            d = r.json()
            price = int(d.get('closePrice','0').replace(',',''))
            ratio = float(d.get('fluctuationsRatio','0'))
            return price, ratio
        else:
            t = yf.Ticker(code)
            hist = t.history(period="30d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[0]
                chg = (curr - prev) / prev * 100
                return curr, chg
    except:
        pass
    return None, None

def get_semiconductor_data():
    """반도체 관련 글로벌 지표"""
    results = {}
    # 필라델피아 반도체 지수
    try:
        sox = yf.Ticker("^SOX")
        hist = sox.history(period="30d")
        if len(hist) >= 2:
            curr = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[0]
            results['SOX_30d'] = (curr - prev) / prev * 100
            results['SOX_curr'] = curr
    except:
        pass

    # NVIDIA (AI 사이클 대표)
    try:
        nvda = yf.Ticker("NVDA")
        hist = nvda.history(period="30d")
        if len(hist) >= 2:
            curr = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[0]
            results['NVDA_30d'] = (curr - prev) / prev * 100
    except:
        pass

    return results

def get_us_sector_rotation():
    """미국 섹터 순환 분석"""
    results = {}
    for name, ticker in US_SECTORS.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="30d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[0]
                chg = (curr - prev) / prev * 100
                results[name] = {"ticker": ticker, "30d_chg": chg, "price": curr}
        except:
            pass
    return results

def determine_cycle_phase(sector_data):
    """섹터별 사이클 단계 판단"""
    # 30일 수익률 기반 단순 분류
    phases = {}
    for sector, data in sector_data.items():
        chg = data.get('30d_chg', 0)
        if chg > 10:
            phases[sector] = ("🚀 확장 후기", "차익 실현 검토")
        elif chg > 3:
            phases[sector] = ("📈 확장 중기", "보유 유지")
        elif chg > -3:
            phases[sector] = ("➡️ 횡보/전환", "방향 확인 후 진입")
        elif chg > -10:
            phases[sector] = ("📉 수축 중기", "저가 매수 대기")
        else:
            phases[sector] = ("🩸 수축 후기", "역발상 매수 기회")
    return phases

def analyze():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    # 한국 섹터 ETF 분석
    kr_sectors = {}
    for sector, info in SECTOR_ETF_MAP.items():
        price, ratio = get_sector_performance(info['code'])
        kr_sectors[sector] = {
            "price": price, "daily_ratio": ratio,
            "desc": info['desc'], "indicator": info['cycle_indicator']
        }

    # 미국 섹터 순환
    us_sectors = get_us_sector_rotation()

    # 반도체 상세
    semi_data = get_semiconductor_data()

    # 사이클 단계
    us_phases = determine_cycle_phase(us_sectors)

    signals = []
    score = 0

    # 강한 섹터 vs 약한 섹터
    strong = [(k, v['30d_chg']) for k, v in us_sectors.items() if v.get('30d_chg', 0) > 5]
    weak = [(k, v['30d_chg']) for k, v in us_sectors.items() if v.get('30d_chg', 0) < -5]

    if strong:
        strong.sort(key=lambda x: x[1], reverse=True)
        signals.append(f"🟢 강한 섹터: {', '.join([f'{k}({v:+.1f}%)' for k,v in strong[:3]])}")
        score += 1

    if weak:
        weak.sort(key=lambda x: x[1])
        signals.append(f"🔴 약한 섹터: {', '.join([f'{k}({v:+.1f}%)' for k,v in weak[:3]])}")
        score -= 1

    # 반도체 사이클 (보유 비중 크므로 중요)
    sox_30d = semi_data.get('SOX_30d')
    if sox_30d is not None:
        if sox_30d > 10:
            signals.append(f"🔥 반도체 사이클 확장 (SOX +{sox_30d:.1f}%/30일)")
            score += 2
        elif sox_30d < -10:
            signals.append(f"❄️ 반도체 사이클 수축 (SOX {sox_30d:.1f}%/30일) — 저가 매수 시점 접근")
            score -= 1

    # 방산 모멘텀 (PLUS K방산 보유)
    defense_data = kr_sectors.get("방산", {})
    if defense_data.get('daily_ratio'):
        if defense_data['daily_ratio'] > 2:
            signals.append(f"🛡️ K방산 강세 (일간 {defense_data['daily_ratio']:+.1f}%) — 지정학적 리스크 반영")
            score += 1

    if score >= 2:
        verdict = "🟢 우호적 사이클 — 성장 섹터 비중 확대"
    elif score >= 0:
        verdict = "⚪ 사이클 중립 — 현 포지션 유지"
    else:
        verdict = "🔴 사이클 조정 — 방어 섹터 관심"

    report = {
        "engine": "산업 사이클 위치 진단",
        "timestamp": now.isoformat(),
        "score": score,
        "verdict": verdict,
        "kr_sectors": kr_sectors,
        "us_sectors": us_sectors,
        "semiconductor": semi_data,
        "us_phases": {k: v[0] for k, v in us_phases.items()},
        "signals": signals,
    }

    md = f"""## 🔄 엔진4: 산업 사이클 위치 진단

**분석 시각**: {now.strftime('%Y-%m-%d %H:%M')} KST
**종합 판정**: {verdict}

### 한국 보유 섹터 현황
| 섹터 | 일간 등락 | 특성 |
|------|---------|------|
"""
    for sector, data in kr_sectors.items():
        ratio = data.get('daily_ratio', 0) or 0
        arrow = "▲" if ratio > 0 else "▼"
        md += f"| {sector} | {arrow}{ratio:+.1f}% | {data['desc']} |\n"

    md += "\n### 미국 섹터 30일 수익률 & 사이클 단계\n"
    md += "| 섹터 | 30일 | 단계 | 전략 |\n|------|------|------|------|\n"
    for sector, data in us_sectors.items():
        chg = data.get('30d_chg', 0)
        phase, strategy = us_phases.get(sector, ("N/A", ""))
        arrow = "▲" if chg > 0 else "▼"
        md += f"| {sector} | {arrow}{chg:+.1f}% | {phase} | {strategy} |\n"

    sox = semi_data.get('SOX_30d')
    nvda = semi_data.get('NVDA_30d')
    md += f"""
### 반도체 사이클 핵심 지표
- **필라델피아 반도체지수(SOX) 30일**: {f'{sox:+.1f}%' if sox else 'N/A'}
- **NVIDIA 30일**: {f'{nvda:+.1f}%' if nvda else 'N/A'}

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
    with open("reports/engine4_industry_cycle.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("\n✅ 엔진4 완료")

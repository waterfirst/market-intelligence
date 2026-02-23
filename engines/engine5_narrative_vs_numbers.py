#!/usr/bin/env python3
"""
엔진 5: 서사 vs 숫자 괴리 분석
뉴스 노출 상위 테마와 실제 재무 지표 비교
핫한 테마가 과열인지 / 조용한 테마가 기회인지
"""
import requests
import feedparser
import yfinance as yf
import json
from datetime import datetime
import pytz
import re

# 모니터링 테마 (보유 종목 관련)
THEMES = {
    "AI/반도체": {
        "keywords": ["AI", "인공지능", "반도체", "엔비디아", "HBM"],
        "etf": "SOXX",
        "narrative": "AI 붐 → 반도체 슈퍼사이클",
    },
    "K방산": {
        "keywords": ["방산", "국방", "무기", "K9", "폴란드"],
        "etf": None,
        "narrative": "NATO 재무장 → 한국 방산 수주 급증",
    },
    "조선": {
        "keywords": ["조선", "LNG선", "수주", "HD현대", "삼성중공업"],
        "etf": None,
        "narrative": "친환경선 교체 → 조선 슈퍼사이클",
    },
    "금/귀금속": {
        "keywords": ["금", "골드", "금리", "안전자산"],
        "etf": "GLD",
        "narrative": "지정학·달러약세 → 금 강세",
    },
    "미국증시": {
        "keywords": ["나스닥", "S&P", "미국주식", "월가"],
        "etf": "QQQ",
        "narrative": "미국 빅테크 AI 독주",
    },
}

def get_news_coverage(keywords):
    """Google News RSS에서 키워드 노출 횟수 측정"""
    try:
        query = "+".join(keywords[:2])
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(url)
        count = len(feed.entries)
        titles = [e.get('title', '').split(' - ')[0] for e in feed.entries[:3]]
        return count, titles
    except:
        return 0, []

def get_theme_performance(etf_ticker):
    """테마 ETF 실제 성과"""
    if not etf_ticker:
        return None, None
    try:
        t = yf.Ticker(etf_ticker)
        hist = t.history(period="30d")
        if len(hist) >= 5:
            curr = hist['Close'].iloc[-1]
            prev_30d = hist['Close'].iloc[0]
            prev_5d = hist['Close'].iloc[-5]
            chg_30d = (curr - prev_30d) / prev_30d * 100
            chg_5d = (curr - prev_5d) / prev_5d * 100
            return chg_30d, chg_5d
    except:
        pass
    return None, None

def calculate_hype_score(news_count, perf_30d):
    """과열도 점수 계산
    뉴스 많음 + 수익률 낮음 = 과열 서사 (실망 가능성)
    뉴스 적음 + 수익률 좋음 = 숨은 기회
    """
    if news_count is None or perf_30d is None:
        return 0, "데이터 부족"

    # 정규화 (뉴스 10개 = 보통, 성과 0% = 보통)
    news_norm = min(news_count / 10, 3)  # 0~3
    perf_norm = perf_30d / 10  # -3~3 정도

    # 서사 과열 = 뉴스 많은데 성과 없음
    divergence = news_norm - perf_norm

    if divergence > 2:
        return divergence, "⚠️ 서사 과열 — 실제 성과 미흡 (매도 주의)"
    elif divergence > 1:
        return divergence, "🟠 서사 약간 과열 — 신중한 접근"
    elif divergence < -1:
        return divergence, "💎 숨은 기회 — 뉴스 적지만 성과 좋음 (매수 검토)"
    else:
        return divergence, "✅ 서사-성과 균형"

def get_hot_news_today():
    """오늘 가장 핫한 뉴스 3개"""
    try:
        feeds = [
            "https://news.google.com/rss/search?q=주식+투자+시장+급등&hl=ko&gl=KR&ceid=KR:ko",
            "https://news.google.com/rss/search?q=코스피+외국인+기관&hl=ko&gl=KR&ceid=KR:ko",
        ]
        all_news = []
        for url in feeds:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.get('title', '').split(' - ')[0]
                all_news.append(title)
        return all_news[:5]
    except:
        return []

def analyze():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    theme_results = {}
    signals = []
    score = 0

    for theme, info in THEMES.items():
        news_count, titles = get_news_coverage(info['keywords'])
        perf_30d, perf_5d = get_theme_performance(info.get('etf'))

        hype_score, hype_label = calculate_hype_score(news_count, perf_30d)

        theme_results[theme] = {
            "news_count": news_count,
            "top_news": titles,
            "perf_30d": perf_30d,
            "perf_5d": perf_5d,
            "hype_score": hype_score,
            "hype_label": hype_label,
            "narrative": info['narrative'],
        }

        if "과열" in hype_label:
            signals.append(f"⚠️ [{theme}] {hype_label} (뉴스:{news_count}건)")
            score -= 1
        elif "숨은 기회" in hype_label:
            signals.append(f"💎 [{theme}] {hype_label}")
            score += 2

    hot_news = get_hot_news_today()

    if score >= 2:
        verdict = "💎 서사-숫자 괴리에서 기회 발견"
    elif score >= 0:
        verdict = "⚪ 서사-숫자 균형적"
    else:
        verdict = "⚠️ 과열 서사 다수 — 냉정한 검토 필요"

    report = {
        "engine": "서사 vs 숫자 괴리 분석",
        "timestamp": now.isoformat(),
        "score": score,
        "verdict": verdict,
        "themes": theme_results,
        "hot_news": hot_news,
        "signals": signals,
    }

    md = f"""## 📰 엔진5: 서사 vs 숫자 괴리 분석

**분석 시각**: {now.strftime('%Y-%m-%d %H:%M')} KST
**종합 판정**: {verdict}

> 💡 **분석 철학**: 뉴스가 많은데 성과가 없으면 과열, 조용한데 성과가 좋으면 기회

### 테마별 서사-성과 괴리도
| 테마 | 뉴스건수 | 30일성과 | 5일성과 | 괴리 판정 |
|------|--------|--------|--------|--------|
"""
    for theme, data in theme_results.items():
        perf30 = f"{data['perf_30d']:+.1f}%" if data['perf_30d'] is not None else "N/A"
        perf5 = f"{data['perf_5d']:+.1f}%" if data['perf_5d'] is not None else "N/A"
        md += f"| {theme} | {data['news_count']}건 | {perf30} | {perf5} | {data['hype_label'][:20]} |\n"

    md += "\n### 테마별 서사 & 최신 뉴스\n"
    for theme, data in theme_results.items():
        md += f"\n**{theme}** — {data['narrative']}\n"
        for title in data['top_news'][:2]:
            md += f"  - {title}\n"

    if hot_news:
        md += "\n### 🔥 오늘 핫한 뉴스\n"
        for news in hot_news[:5]:
            md += f"- {news}\n"

    md += "\n### 📡 신호 목록\n"
    for s in signals:
        md += f"- {s}\n"

    return report, md


if __name__ == "__main__":
    report, md = analyze()
    print(md)
    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/engine5_narrative.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("\n✅ 엔진5 완료")

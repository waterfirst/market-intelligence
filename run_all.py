#!/usr/bin/env python3
"""
마켓 인텔리전스 오케스트레이터
7개 엔진 실행 → 통합 리포트 생성 → GitHub Push → Telegram 전송
"""
import sys
import os
import json
import requests
import subprocess
from datetime import datetime
import pytz

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'engines'))

# 설정 파일에서 토큰 로드 (보안 - 파일에는 토큰 미포함)
_CONFIG_FILE = os.path.expanduser("~/.config/market-intelligence/config.json")
try:
    with open(_CONFIG_FILE) as _f:
        _cfg = json.load(_f)
except Exception:
    _cfg = {}

TELEGRAM_TOKEN = _cfg.get("telegram_token", os.environ.get("TELEGRAM_TOKEN", ""))
CHAT_ID = _cfg.get("chat_id", os.environ.get("CHAT_ID", ""))
GITHUB_TOKEN = _cfg.get("github_token", os.environ.get("GITHUB_TOKEN", ""))
GITHUB_REPO = _cfg.get("github_repo", "waterfirst/market-intelligence")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram 전송 실패: {e}")

def run_engine(engine_module):
    """엔진 실행 및 결과 반환"""
    try:
        module = __import__(engine_module)
        report, md = module.analyze()
        return report, md, None
    except Exception as e:
        return None, None, str(e)

def git_push_reports(kst_now):
    """Git add/commit/push"""
    try:
        date_str = kst_now.strftime('%Y-%m-%d')
        time_str = kst_now.strftime('%H:%M')

        os.chdir(BASE_DIR)

        # git add all
        subprocess.run(['git', 'add', '-A'], check=True)

        # 변경사항 확인
        result = subprocess.run(['git', 'status', '--porcelain'],
                                capture_output=True, text=True)
        if not result.stdout.strip():
            print("변경사항 없음, push 생략")
            return True

        # git commit
        commit_msg = f"🤖 야간 분석 리포트 [{date_str} {time_str} KST]\n\n7개 엔진 자동 분석 완료"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True)

        # git push (with token)
        remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
        subprocess.run(['git', 'push', remote_url, 'main'], check=True)

        print(f"✅ GitHub push 완료: {date_str} {time_str}")
        return True
    except Exception as e:
        print(f"❌ Git push 실패: {e}")
        return False

def create_summary_report(all_reports, all_mds, kst_now):
    """통합 요약 리포트 생성"""
    date_str = kst_now.strftime('%Y-%m-%d')

    # 리포트 디렉토리
    report_dir = os.path.join(BASE_DIR, 'reports', date_str)
    os.makedirs(report_dir, exist_ok=True)

    # 각 엔진 마크다운 저장
    engine_names = [
        "01_liquidity", "02_valuation", "03_supply_demand",
        "04_industry_cycle", "05_narrative", "06_macro_scenarios", "07_collapse"
    ]

    for i, (name, md) in enumerate(zip(engine_names, all_mds)):
        if md:
            filepath = os.path.join(report_dir, f"engine{name}.md")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md)

    # 통합 점수 계산
    scores = {}
    verdicts = {}
    for report in all_reports:
        if report:
            engine_name = report.get('engine', '?')
            scores[engine_name] = report.get('score', 0)
            verdicts[engine_name] = report.get('verdict', 'N/A')

    # 종합 시장 판단
    total_score = sum(scores.values())
    if total_score >= 5:
        overall = "🟢🟢 강한 매수 환경"
    elif total_score >= 2:
        overall = "🟢 우호적 시장"
    elif total_score >= -2:
        overall = "⚪ 중립 시장"
    elif total_score >= -5:
        overall = "🔴 주의 시장"
    else:
        overall = "🔴🔴 위험 시장"

    # 통합 마크다운
    master_md = f"""# 📊 Market Intelligence Report
> {date_str} | Claude Code 야간 자동 분석

## 종합 판정: {overall}
**종합 점수**: {total_score:+d}점

---

"""
    for md in all_mds:
        if md:
            master_md += md + "\n\n---\n\n"

    master_md += f"\n> *자동 생성: {kst_now.strftime('%Y-%m-%d %H:%M')} KST | Claude Code @ EC2*\n"

    master_path = os.path.join(report_dir, "MASTER_REPORT.md")
    with open(master_path, 'w', encoding='utf-8') as f:
        f.write(master_md)

    # 최상위 README 업데이트
    readme_path = os.path.join(BASE_DIR, 'README.md')
    readme = f"""# 📊 Market Intelligence System

> waterfirst의 시장 분석 자동화 엔진 - Claude Code가 매일 밤 실행

## 최신 분석: {date_str}

### 종합 판정: {overall}

### 엔진 구성
| 엔진 | 목적 |
|------|------|
| 1. 유동성 방향 감지 | M2, 금리차, 달러, VIX, 공포탐욕 |
| 2. 밸류에이션 왜곡 탐지 | PER/PBR, CAPE, 금/주식 비율 |
| 3. 수급 구조 역전 포착 | 외국인/기관 순매수, 시장폭 |
| 4. 산업 사이클 위치 | 반도체/조선/방산/AI 섹터 사이클 |
| 5. 서사 vs 숫자 괴리 | 뉴스 과열 vs 실제 성과 비교 |
| 6. 거시 시나리오 확률 | 4개 시나리오 확률 산출 |
| 7. 붕괴 가능성 탐지 | 기술적 붕괴 조기 경보 |

### 판정 이력
| 날짜 | 종합판정 | 점수 |
|------|--------|------|
| {date_str} | {overall} | {total_score:+d} |

---
*자동 업데이트: {kst_now.strftime('%Y-%m-%d %H:%M')} KST*
"""
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme)

    return overall, total_score, scores, verdicts

def build_telegram_message(overall, total_score, scores, verdicts, all_reports, kst_now):
    """텔레그램 요약 메시지 구성"""
    crash_report = None
    scenario_report = None
    for r in all_reports:
        if r and r.get('engine') == '붕괴 가능성 탐지':
            crash_report = r
        if r and r.get('engine') == '거시 시나리오 확률 게임':
            scenario_report = r

    msg = f"""🤖 <b>야간 시장 분석 완료</b> | {kst_now.strftime('%m/%d %H:%M')} KST

<b>종합 판정: {overall}</b>
종합 점수: {total_score:+d}점

━━━━━━━━━━━━━━━━━
"""
    # 엔진별 판정 요약
    engine_labels = {
        "유동성 방향 감지": "💧유동성",
        "밸류에이션 왜곡 탐지": "📊밸류",
        "수급 구조 역전 포착": "🔄수급",
        "산업 사이클 위치 진단": "🏭사이클",
        "서사 vs 숫자 괴리 분석": "📰서사",
        "거시 시나리오 확률 게임": "🎲시나리오",
        "붕괴 가능성 탐지": "🚨붕괴탐지",
    }

    for engine, verdict in verdicts.items():
        label = engine_labels.get(engine, engine[:5])
        score = scores.get(engine, 0)
        msg += f"  {label}: {verdict[:25]}\n"

    # 시나리오 top
    if scenario_report:
        top = scenario_report.get('top_scenario', '')
        probs = scenario_report.get('scenario_probabilities', {})
        if top and probs:
            msg += f"\n━━━━━━━━━━━━━━━━━\n"
            msg += f"🎲 <b>시나리오 확률</b>\n"
            for sc, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
                bar = "█" * (prob // 10)
                msg += f"  {sc}: {bar} {prob}%\n"

    # 붕괴 위험도
    if crash_report:
        cp = crash_report.get('crash_probability', 0)
        msg += f"\n━━━━━━━━━━━━━━━━━\n"
        msg += f"🚨 <b>붕괴 위험도</b>: {cp:.0f}%\n"
        for sig in crash_report.get('signals', [])[:2]:
            msg += f"  {sig}\n"

    msg += f"\n🔗 github.com/{GITHUB_REPO}\n"
    msg += f"<i>— Claude Code 야간 분석 🌙</i>"

    return msg

def main():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    print(f"\n🚀 마켓 인텔리전스 시작: {now.strftime('%Y-%m-%d %H:%M')} KST")

    os.chdir(BASE_DIR)

    engines = [
        "engine1_liquidity",
        "engine2_valuation",
        "engine3_supply_demand",
        "engine4_industry_cycle",
        "engine5_narrative_vs_numbers",
        "engine6_macro_scenarios",
        "engine7_collapse_detector",
    ]

    all_reports = []
    all_mds = []

    for engine in engines:
        print(f"  ▶ {engine} 실행 중...")
        report, md, error = run_engine(engine)
        if error:
            print(f"    ❌ 오류: {error}")
            all_reports.append(None)
            all_mds.append(None)
        else:
            print(f"    ✅ 완료")
            all_reports.append(report)
            all_mds.append(md)

    # 통합 리포트 생성
    overall, total_score, scores, verdicts = create_summary_report(all_reports, all_mds, now)
    print(f"\n📝 통합 리포트 생성 완료 | {overall}")

    # GitHub Push
    git_push_reports(now)

    # Telegram 전송
    msg = build_telegram_message(overall, total_score, scores, verdicts, all_reports, now)
    send_telegram(msg)
    print(f"📱 텔레그램 전송 완료")

    print(f"\n✅ 마켓 인텔리전스 완료: {datetime.now(kst).strftime('%H:%M')} KST\n")


if __name__ == "__main__":
    main()

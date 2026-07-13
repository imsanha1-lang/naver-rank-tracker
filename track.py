"""추적 대상(docs/data/targets.json)을 읽어 순위를 수집하고
결과를 docs/data/rankings.json 에 append 한다.

GitHub Actions 가 매일 12시(KST)에 이 스크립트를 실행한다.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import scraper

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "docs", "data")
TARGETS_PATH = os.path.join(DATA_DIR, "targets.json")
RANKINGS_PATH = os.path.join(DATA_DIR, "rankings.json")

KST = timezone(timedelta(hours=9))


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    targets = load_json(TARGETS_PATH, [])
    if not targets:
        print("추적 대상이 없습니다. docs/data/targets.json 을 확인하세요.")
        return 0

    rankings = load_json(RANKINGS_PATH, [])
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    datetime_str = now.strftime("%Y-%m-%d %H:%M")

    headless = os.environ.get("HEADLESS", "true").lower() == "true"
    driver = None
    try:
        driver = scraper.build_driver(headless=headless)
        for t in targets:
            keyword = t.get("keyword", "").strip()
            place_name = t.get("place_name", "").strip()
            if not keyword or not place_name:
                continue
            print(f"[수집] {keyword} / {place_name}")
            result = scraper.find_rank(keyword, place_name, driver=driver, headless=headless)
            record = {
                "keyword": keyword,
                "place_name": place_name,
                "rank": result["rank"],
                "rank_with_ads": result["rank_with_ads"],
                "total_found": result["total_found"],
                "note": result["note"],
                "date": date_str,
                "datetime": datetime_str,
            }
            print("   ->", record["rank_with_ads"], "위 /", result["note"])
            rankings.append(record)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    save_json(RANKINGS_PATH, rankings)
    print(f"저장 완료: 총 {len(rankings)}개 기록 -> {RANKINGS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

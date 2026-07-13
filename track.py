"""추적 대상(docs/data/targets.json)을 읽어 순위를 수집하고
결과를 docs/data/rankings.json 에 append 한다.

효율화: 같은 키워드는 딱 한 번만 검색하고, 그 결과 목록에서 해당 키워드에
연결된 모든 매장의 순위를 한꺼번에 계산한다. (검색 횟수 = 고유 키워드 수)

targets.json 형식 (둘 다 지원)
  1) 매장별 묶음:  { "place_name": "OO헤어", "keywords": ["강남역 미용실", "..."] }
  2) 단일 쌍:      { "keyword": "강남역 미용실", "place_name": "OO헤어" }

GitHub Actions 가 매일 12시(KST)에 이 스크립트를 실행한다.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import scraper

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "docs", "data")
TARGETS_PATH = os.path.join(DATA_DIR, "targets.json")
RANKINGS_PATH = os.path.join(DATA_DIR, "rankings.json")

KST = timezone(timedelta(hours=9))

# 키워드 검색 사이 간격(초). 네이버 차단 위험 완화용.
DELAY_BETWEEN_KEYWORDS = float(os.environ.get("DELAY_BETWEEN_KEYWORDS", "4"))
# 히스토리 최대 보관 개수 (파일 비대화 방지)
MAX_RECORDS = int(os.environ.get("MAX_RECORDS", "200000"))


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


def build_keyword_map(targets):
    """targets 를 {키워드: [매장명, ...]} 로 정규화."""
    kw_map = {}
    for t in targets:
        place = (t.get("place_name") or "").strip()
        if not place:
            continue
        keywords = t.get("keywords")
        if not keywords:
            single = (t.get("keyword") or "").strip()
            keywords = [single] if single else []
        for kw in keywords:
            kw = (kw or "").strip()
            if not kw:
                continue
            kw_map.setdefault(kw, [])
            if place not in kw_map[kw]:
                kw_map[kw].append(place)
    return kw_map


def main():
    targets = load_json(TARGETS_PATH, [])
    kw_map = build_keyword_map(targets)
    if not kw_map:
        print("추적 대상이 없습니다. docs/data/targets.json 을 확인하세요.")
        return 0

    total_pairs = sum(len(v) for v in kw_map.values())
    print(f"고유 키워드 {len(kw_map)}개 / (키워드-매장) 쌍 {total_pairs}개 수집 시작")

    rankings = load_json(RANKINGS_PATH, [])
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    datetime_str = now.strftime("%Y-%m-%d %H:%M")

    headless = os.environ.get("HEADLESS", "true").lower() == "true"
    driver = None
    try:
        driver = scraper.build_driver(headless=headless)
        for i, (keyword, places) in enumerate(kw_map.items(), start=1):
            print(f"[{i}/{len(kw_map)}] 검색: {keyword}  (매장 {len(places)}개)")
            try:
                all_names = scraper.collect_places(keyword, driver)
                err = None
            except Exception as e:
                all_names = []
                err = str(e)
                print(f"   ! 검색 오류: {err[:120]}")

            for place in places:
                if err:
                    result = {"rank": None, "rank_with_ads": None,
                              "total_found": 0, "note": f"오류: {err[:100]}"}
                else:
                    result = scraper.rank_of(all_names, place)
                rankings.append({
                    "keyword": keyword,
                    "place_name": place,
                    "rank": result["rank"],
                    "rank_with_ads": result["rank_with_ads"],
                    "total_found": result["total_found"],
                    "note": result["note"],
                    "date": date_str,
                    "datetime": datetime_str,
                })
                print(f"     - {place}: {result['rank_with_ads']}위 {result['note']}")

            if i < len(kw_map):
                time.sleep(DELAY_BETWEEN_KEYWORDS)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    if len(rankings) > MAX_RECORDS:
        rankings = rankings[-MAX_RECORDS:]
    save_json(RANKINGS_PATH, rankings)
    print(f"저장 완료: 총 {len(rankings)}개 기록 -> {RANKINGS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

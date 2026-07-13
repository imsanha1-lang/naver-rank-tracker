"""네이버 지도 순위 스크래퍼 (GitHub Actions / 로컬 공용).

키워드로 네이버 지도를 검색해 대상 매장의 노출 순위를 찾는다.

- CI(리눅스 headless)에서는 일반 selenium + Selenium Manager 로 크롬을 구동한다.
- 로컬에서는 undetected-chromedriver 를 우선 시도한다.
네이버는 DOM 클래스명이 자주 바뀌므로 선택자는 여러 후보를 시도한다.
"""
import os
import time
import urllib.parse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# 매장명 후보 선택자. 네이버가 해시 클래스명을 바꿔도, 못 찾으면
# 항목의 '첫 줄 텍스트'로 자동 폴백하므로 어느 정도 견딘다.
NAME_SELECTORS = [
    "span.O_Uah",        # 2026 기준 매장명
    "span.YwYLL",
    "span.place_bluelink",
    "span.TYaxT",
    "span.CMy2_",
]
# 광고는 span.place_blind 의 텍스트가 '광고' (스크래퍼 내부에서 직접 처리)
AD_SELECTORS = [
    "span.place_blind",
]
MAX_PAGES = 5
SCROLL_PAUSE = 0.6


def build_driver(headless=True, prefer_uc=None):
    """크롬 드라이버 생성.

    prefer_uc=None 이면 환경에 따라 자동 선택(로컬=uc, CI=plain).
    uc 실패 시 일반 selenium 으로 폴백한다.
    """
    if prefer_uc is None:
        prefer_uc = os.environ.get("CI", "").lower() != "true"

    # 1) undetected-chromedriver 시도
    if prefer_uc:
        try:
            import undetected_chromedriver as uc  # noqa
            try:
                import setuptools  # noqa: F401
            except ImportError:
                pass
            options = uc.ChromeOptions()
            _common_args(options, headless)
            return uc.Chrome(options=options)
        except Exception as e:
            print(f"[scraper] undetected-chromedriver 실패, 일반 selenium 으로 전환: {e}")

    # 2) 일반 selenium (Selenium Manager 가 드라이버 자동 관리)
    from selenium import webdriver
    options = webdriver.ChromeOptions()
    _common_args(options, headless)
    return webdriver.Chrome(options=options)


def _common_args(options, headless):
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1200,900")
    options.add_argument("--lang=ko-KR")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    if headless:
        options.add_argument("--headless=new")


def _match(name, target):
    a = name.replace(" ", "").lower()
    b = target.replace(" ", "").lower()
    return b in a or a in b


# 한 페이지의 (이름, 광고여부) 목록을 브라우저 안에서 한 번에 추출하는 JS.
# - 이름: span.O_Uah 우선, 없으면 항목의 첫 줄 텍스트(구조 변경에 강함)
# - 광고: span.place_blind 의 textContent 가 '광고'
_EXTRACT_JS = r"""
const nameSel = arguments[0];
const nodes = document.querySelectorAll('#_pcmap_list_scroll_container li, ul li');
const out = [];
const seen = new Set();
nodes.forEach(li => {
  let name = '';
  for (const s of nameSel) {
    const el = li.querySelector(s);
    if (el && el.textContent.trim()) { name = el.textContent.trim(); break; }
  }
  if (!name) {
    const t = (li.innerText || '').trim();
    if (t) name = t.split('\n')[0].trim();
  }
  if (!name) return;
  if (/^\d+$/.test(name) || name.length < 2) return;  // 페이지 번호 등 제외
  let isAd = false;
  li.querySelectorAll('span.place_blind').forEach(s => {
    if (s.textContent.trim() === '광고') isAd = true;
  });
  out.push({ name: name, isAd: isAd });
});
return out;
"""


def _collect_names_on_page(driver):
    try:
        container = driver.find_element(By.CSS_SELECTOR, "#_pcmap_list_scroll_container")
    except Exception:
        container = None

    last_count = -1
    stable = 0
    for _ in range(40):
        items = driver.find_elements(By.CSS_SELECTOR, "#_pcmap_list_scroll_container li, ul li")
        count = len(items)
        if count == last_count:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        last_count = count
        if items:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'end'});", items[-1])
            except Exception:
                pass
        if container is not None:
            try:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
            except Exception:
                pass
        time.sleep(SCROLL_PAUSE)

    try:
        rows = driver.execute_script(_EXTRACT_JS, NAME_SELECTORS)
    except Exception:
        rows = []
    return [(r["name"], bool(r["isAd"])) for r in rows if r.get("name")]


def _goto_next_page(driver, page_number):
    candidates = driver.find_elements(By.CSS_SELECTOR, "a.mBN2s, a.zRM9F, div.zRM9F a")
    for btn in candidates:
        try:
            if btn.text.strip() == str(page_number):
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)
                return True
        except Exception:
            continue
    for sel in ["a.eUTV2", "a.NKY5o", "button.eUTV2"]:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            if btn.is_enabled():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)
                return True
        except Exception:
            continue
    return False


def find_rank(keyword, place_name, driver=None, headless=True, max_pages=MAX_PAGES):
    own_driver = False
    if driver is None:
        driver = build_driver(headless=headless)
        own_driver = True

    all_names = []
    note = ""
    try:
        url = "https://map.naver.com/p/search/" + urllib.parse.quote(keyword)
        driver.get(url)
        time.sleep(3)

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#searchIframe"))
        )
        driver.switch_to.frame("searchIframe")
        time.sleep(2)

        for page in range(1, max_pages + 1):
            all_names.extend(_collect_names_on_page(driver))
            if not _goto_next_page(driver, page + 1):
                break
            time.sleep(1)

        rank_with_ads = None
        rank_organic = None
        organic_pos = 0
        for idx, (name, is_ad) in enumerate(all_names, start=1):
            if not is_ad:
                organic_pos += 1
            if _match(name, place_name):
                rank_with_ads = idx
                rank_organic = None if is_ad else organic_pos
                break

        total_found = len(all_names)
        if rank_with_ads is None:
            note = f"검색결과 {total_found}개 중 미발견"
        return {
            "rank": rank_organic,
            "rank_with_ads": rank_with_ads,
            "total_found": total_found,
            "note": note,
        }
    except Exception as e:
        return {
            "rank": None,
            "rank_with_ads": None,
            "total_found": len(all_names),
            "note": f"오류: {e}",
        }
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        if own_driver:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "강남역 미용실"
    pl = sys.argv[2] if len(sys.argv) > 2 else "박승철헤어스투디오"
    print(find_rank(kw, pl, headless=False))

import re
import sys
import threading
import time
import queue
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\libs")

import config

COOKIE_PROFILE = Path(__file__).parent / "hh_browser_profile"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

AVITO_CITY_URL = {
    "spb": "sankt-peterburg",
    "petrozavodsk": "petrozavodsk",
    "yaroslavl": "yaroslavl",
}
AVITO_CATEGORY = "kurerskaya_dostavka-ASgBAgICAUSUC7ao1gI"

KEYWORDS = ["курьер", "доставк", "велокурьер", "вело", "самокат", "пеший", "экспедитор"]

_worker_q = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def _contains_keyword(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in KEYWORDS)


def _start_browser():
    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(EDGE_PATH)
    co.set_user_data_path(str(COOKIE_PROFILE))
    co.headless()
    co.set_argument("--disable-gpu")
    co.set_argument("--log-level=3")
    return Chromium(co)


def _fetch_resumes(browser, city_key: str) -> list[dict]:
    """Fetch freshest courier resumes from Avito for a city (blocking)."""
    city_slug = AVITO_CITY_URL.get(city_key, "sankt-peterburg")
    url = f"https://www.avito.ru/{city_slug}/rezume/{AVITO_CATEGORY}?s=104"
    tab = browser.latest_tab
    tab.get(url)
    time.sleep(5)

    items = []
    cards = tab.eles("css:[data-marker='item']")
    for card in cards:
        link_el = card.ele("css:a[data-marker='item-title']")
        if not link_el:
            continue
        title = (link_el.text or "").strip()
        if not title:
            continue

        href = link_el.attr("href") or ""
        if href.startswith("/"):
            href = "https://www.avito.ru" + href
        href = href.split("?")[0]

        m = re.search(r"_(\d+)$", href)
        item_id = m.group(1) if m else href

        if not _contains_keyword(title):
            continue

        card_text = (card.text or "").replace("\n", " | ")

        price = ""
        pm = re.findall(r"(\d[\d\s]{1,6})\s*₽", card_text)
        if pm:
            price = pm[0].strip()

        age = ""
        am = re.search(r"(\d+)\s*год(?:а|ы|лет)", card_text)
        if am:
            age = am.group(1)

        area = ""
        city_n = config.CITY_NAMES.get(city_key, "")
        if city_n:
            cm = re.search(re.escape(city_n) + r"\s*[·•]?\s*([^|]*?)(?:\||$)", card_text)
            if cm:
                area = cm.group(1).strip()

        updated = ""
        um = re.search(r"Обновлено\s+(.+?)(?:\||$)", card_text)
        if um:
            updated = um.group(1).strip()

        items.append({
            "id": item_id,
            "title": title,
            "url": href,
            "price": price,
            "age": age,
            "area": area,
            "updated": updated,
            "city": city_n,
            "location": city_n,
            "description": (card_text or "")[:250],
        })

    return items


def start_browser_worker():
    """Single persistent browser thread (DrissionPage is not thread-safe)."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    def worker():
        browser = _start_browser()
        while True:
            task = _worker_q.get()
            if task is None:
                break
            cities, result_q = task
            try:
                result_q.put((True, {c: _fetch_resumes(browser, c) for c in cities}))
            except Exception as e:
                result_q.put((False, e))

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def fetch_avito(cities: list[str]) -> dict[str, list[dict]]:
    """Call from async code via asyncio.to_thread. Returns {city: items}."""
    start_browser_worker()
    result_q = queue.Queue()
    _worker_q.put((cities, result_q))
    ok, result = result_q.get(timeout=120)
    if not ok:
        raise result
    return result


def close_browser():
    _worker_q.put(None)


if __name__ == "__main__":
    start_browser_worker()
    res = fetch_avito(["spb", "petrozavodsk", "yaroslavl"])
    for ck, its in res.items():
        print(f"=== {ck}: {len(its)} ===", flush=True)
        for i in its[:10]:
            print(" -", i["title"][:50], "|", i["price"], "|", i["age"], "|", i["area"], "|", i["updated"], flush=True)
    close_browser()
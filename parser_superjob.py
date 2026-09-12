import re
import sys
import os
import threading
import time
import queue
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\libs")

import config

COOKIE_PROFILE = Path(__file__).parent / "superjob_browser_profile"
_edge = os.getenv("EDGE_PATH")
EDGE_PATH = _edge if _edge and os.path.exists(_edge) else ""

# поддомен города на superjob: spb, petrozavodsk, yaroslavl
SJ_CITY_SUBDOMAIN = {
    "spb": "spb",
    "petrozavodsk": "petrozavodsk",
    "yaroslavl": "yaroslavl",
}

_worker_q = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def _start_browser():
    """Пытается запустить браузер. Возвращает browser или None если не удалось."""
    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(EDGE_PATH)
    co.set_user_data_path(str(COOKIE_PROFILE))
    co.headless()
    co.set_argument("--disable-gpu")
    co.set_argument("--log-level=3")
    try:
        browser = Chromium(co)
        return browser
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Браузер не доступен, SuperJob/Rabota будут пропущены: %s", e)
        return None


def _parse_resumes(browser, city_key: str, cat_key: str) -> list[dict]:
    cat = config.SUPERJOB_CATEGORIES.get(cat_key)
    if not cat:
        return []
    sub = SJ_CITY_SUBDOMAIN.get(city_key, "spb")
    slug = cat["slug"]
    url = f"https://{sub}.superjob.ru/resume/{slug}.html?period=1"
    tab = browser.latest_tab
    tab.get(url)
    time.sleep(5)

    items = []
    cards = tab.eles("css:.f-test-search-result-item") or []
    for card in cards:
        text = re.sub(r"\s+", " ", (card.text or "")).strip()
        if "Обновлено" not in text or "Резюме с контактами" in text:
            continue

        # id из класса f-test-resume-snippet-{id}
        rid = ""
        m_cls = re.search(r"f-test-resume-snippet-(\d+)", card.html or "")
        if m_cls:
            rid = m_cls.group(1)
        if not rid:
            m_url = re.search(r"/resume/[a-z0-9-]+-(\d+)\.html", card.html or "")
            if m_url:
                rid = m_url.group(1)
        if not rid:
            continue

        updated = ""
        m_upd = re.search(r"Обновлено\s+(.+)", text)
        if m_upd:
            raw = m_upd.group(1)
            upd = re.split(r"\s+(?:Online|Был|Была)\s", raw)[0].strip()
            if re.match(r"^в\s+\d{1,2}:\d{2}", upd):
                upd = "сегодня " + upd.replace("в ", "")
            updated = upd

        # название резюме + город + зарплата + ссылка из первого анкора карточки
        title = ""
        city = ""
        price = ""
        card_url = ""
        anchors = card.eles("css:a") if hasattr(card, "eles") else []
        for a in anchors:
            h = (a.attr("href") or "")
            if "/resume/" in h:
                if h.startswith("http"):
                    card_url = h
                elif h.startswith("/"):
                    card_url = "https://" + sub + ".superjob.ru" + h
                atext = re.sub(r"\s+", " ", (a.text or "")).strip()
                if atext:
                    lines = [ln.strip() for ln in atext.split("\n") if ln.strip()]
                    if lines:
                        title = lines[0]
                    m_price = re.search(r"([\d\s]{2,})\s*₽", atext)
                    if m_price:
                        price = m_price.group(1).strip()
                    known = list(config.CITY_NAMES.values()) + ["Петрозаводск", "Ярославль"]
                    for kn in known:
                        if kn in atext:
                            city = kn
                            break
                    if not city:
                        m_city = re.search(r"\n([А-ЯЁ][а-яё]+(?:[ -][А-ЯЁ][а-яё]+)+)", atext)
                        if m_city:
                            city = m_city.group(1).strip()
                break
        if not title:
            title = text[:60]

        if not price:
            m_price = re.search(r"([\d\s]{2,})\s*₽", text)
            if m_price:
                price = m_price.group(1).strip()
        if not price and "По договорённости" in text:
            price = "По договорённости"

        # возраст
        age = ""
        m_age = re.search(r"(\d{1,2})\s+(?:лет|год|года)", text)
        if m_age:
            age = m_age.group(1)

        if not city:
            for probe in config.CITY_NAMES.values():
                if probe in text:
                    city = probe
                    break

        url = card_url or f"https://{sub}.superjob.ru/resume/from-snippet-{rid}.html"
        items.append({
            "id": rid,
            "title": title,
            "url": url,
            "price": price,
            "age": age,
            "area": "",
            "updated": updated,
            "city": city,
            "location": city,
            "description": text[:250],
        })
    return items


def start_browser_worker():
    """Один персистентный поток браузера (DrissionPage не thread-safe)."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    def worker():
        browser = None
        try:
            browser = _start_browser()
        except Exception as e:
            _worker_q.put(("error", e))
            return
        while True:
            task = _worker_q.get()
            if task is None:
                break
            fn, result_q = task
            try:
                result_q.put((True, fn(browser)))
            except Exception as e:
                result_q.put((False, e))

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def fetch_superjob(cities: list[str], categories: list[str]) -> dict[str, dict[str, list[dict]]]:
    """Возвращает {city: {cat: [items]}}."""
    start_browser_worker()
    result_q = queue.Queue()
    _worker_q.put((lambda b: _fetch_all(b, cities, categories), result_q))
    ok, result = result_q.get(timeout=180)
    if not ok:
        raise result
    return result


def _fetch_all(browser, cities, categories):
    out = {}
    for ck in cities:
        out[ck] = {}
        for cat in categories:
            try:
                out[ck][cat] = _parse_resumes(browser, ck, cat)
            except Exception as e:
                out[ck][cat] = []
                print(f"SJ {ck}/{cat} failed: {e}", flush=True)
    return out


def close_browser():
    _worker_q.put(None)


if __name__ == "__main__":
    res = fetch_superjob(["spb", "petrozavodsk", "yaroslavl"], list(config.SUPERJOB_CATEGORIES))
    for ck, cats in res.items():
        for cat, items in cats.items():
            print(f"=== {ck}/{cat}: {len(items)} ===", flush=True)
            for i in items[:5]:
                print(" -", i["title"][:40], "|", i["price"], "|", i["age"], "|", i["city"], "|", i["updated"], flush=True)
    close_browser()
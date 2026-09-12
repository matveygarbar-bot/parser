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

COOKIE_PROFILE = Path(__file__).parent / "rabota_browser_profile"
_edge = os.getenv("EDGE_PATH")
EDGE_PATH = _edge if _edge and os.path.exists(_edge) else ""

# Поддомены городов: СПб и Ярославль работают; Петрозаводска на Rabota нет
RAB_CITY_SUBDOMAIN = {
    "spb": "spb",
    "petrozavodsk": None,  # редиректит на другой город — пропускаем
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
        logger.warning("Браузер не доступен, Rabota будет пропущена: %s", e)
        return None


def _parse_resumes(browser, city_key: str, cat_key: str) -> list[dict]:
    cat = config.RABOTA_CATEGORIES.get(cat_key)
    if not cat:
        return []
    sub = RAB_CITY_SUBDOMAIN.get(city_key)
    if not sub:
        return []
    slug = cat["slug"]
    url = f"https://{sub}.rabota.ru/resume/{slug}/"
    tab = browser.latest_tab
    tab.get(url)
    time.sleep(5)

    items = []
    links = tab.eles("css:a[href*='/resume-search/']") or []
    seen = set()
    for link in links:
        href = link.attr("href") or ""
        if "contacts=true" in href:
            continue
        m = re.search(r"/resume-search/(\d+)", href)
        if not m:
            continue
        rid = m.group(1)
        if rid in seen:
            continue
        seen.add(rid)

        node = link
        card = None
        for _ in range(10):
            try:
                node = node.parent()
            except Exception:
                break
            if node is None:
                break
            t = node.text or ""
            if "Обновлено" in t and len(t) < 900:
                card = node
                break
        text = re.sub(r"\s+", " ", (card.text if card else link.text or "")).strip()
        if not text or "Обновлено" not in text:
            continue

        # структура: Title Цена | Показать контакты | Мужчина, 27 лет, Город | ... | Обновлено ...
        price = ""
        title = ""
        # ищем цену после названия: в конце блоков «Title 70 000 ₽» / «Title договорная»
        blocks = re.split(r"\s+Показать контакты\s+", text)
        head = blocks[0] if blocks else text
        m_price = re.search(r"([\d\s]{2,})\s*₽|договорная", head)
        if m_price:
            price = m_price.group(1).strip() if "₽" in m_price.group(0) else "По договорённости"
            title = head[: m_price.start()].strip()
        if not title:
            for kw in ["курьер", "разнорабоч"]:
                idx = text.lower().find(kw)
                if idx >= 0:
                    title = text[max(0, idx - 20): idx + 40].strip()
                    break
        if not title:
            title = text[:60]

        age = ""
        m_age = re.search(r"(Мужчина|Женщина), (\d{1,2}) (?:лет|год|года)", text)
        if m_age:
            age = m_age.group(2)

        city = ""
        m_city = re.search(r"(Мужчина|Женщина), \d{1,2} (?:лет|год|года), ([А-ЯЁ][^ ]*(?:[ -][А-ЯЁ][^ ]*)*)", text)
        if m_city:
            city = re.sub(r"\s+Стаж.*", "", m_city.group(2)).strip()

        updated = ""
        m_upd = re.search(r"Обновлено\s+(.+?)(?:\s+[А-ЯЁ]|$)", text)
        if m_upd:
            updated = m_upd.group(1).strip()
            if updated == "сегодня":
                m_t = re.search(r"Обновлено сегодня в (\d{1,2}:\d{2})", text)
                updated = f"сегодня {m_t.group(1)}" if m_t else "сегодня"
            elif updated == "вчера":
                m_t = re.search(r"Обновлено вчера в (\d{1,2}:\d{2})", text)
                updated = f"вчера {m_t.group(1)}" if m_t else "вчера"

        items.append({
            "id": rid,
            "title": title,
            "url": f"https://{sub}.rabota.ru/resume-search/{rid}",
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


def fetch_rabota(cities: list[str], categories: list[str]) -> dict[str, dict[str, list[dict]]]:
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
                print(f"Rabota {ck}/{cat} failed: {e}", flush=True)
    return out


def close_browser():
    _worker_q.put(None)


if __name__ == "__main__":
    res = fetch_rabota(["spb", "petrozavodsk", "yaroslavl"], list(config.RABOTA_CATEGORIES))
    for ck, cats in res.items():
        for cat, items in cats.items():
            print(f"=== {ck}/{cat}: {len(items)} ===", flush=True)
            for i in items[:8]:
                print(" -", i["title"][:45], "|", i["price"], "|", i["age"], "|", i["city"], "|", i["updated"], flush=True)
    close_browser()
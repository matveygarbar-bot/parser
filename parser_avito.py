import asyncio
import re
import json
import cloudscraper
from bs4 import BeautifulSoup

AVITO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

def _create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
        delay=10
    )
    scraper.trust_env = False
    scraper.proxies = {}
    return scraper

async def fetch_avito(url: str) -> list[dict]:
    loop = asyncio.get_running_loop()
    def _fetch():
        scraper = _create_scraper()
        resp = scraper.get(url, headers=AVITO_HEADERS, timeout=20)
        if resp.status_code == 429:
            import time
            time.sleep(30)
            resp = scraper.get(url, headers=AVITO_HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    html = await loop.run_in_executor(None, _fetch)
    return _parse_avito_html(html, url)


def _parse_avito_html(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items = []
    for card in soup.select("[data-item-id]"):
        item_id = card.get("data-item-id", "")
        if not item_id or not item_id.isdigit():
            continue
        title_tag = card.select_one("a[title]")
        if not title_tag:
            title_tag = card.select_one("div.jNGxV span.snk")
        title = title_tag.get("title") or title_tag.get_text(strip=True) if title_tag else "Без названия"
        link_tag = card.select_one("a[href]")
        href = link_tag["href"] if link_tag else ""
        if href and not href.startswith("http"):
            href = "https://www.avito.ru" + href
        price_tag = card.select_one("[data-marker='item-price']")
        price = price_tag.get_text(strip=True) if price_tag else ""
        date_tag = card.select_one("[data-marker='item-date']")
        date_text = date_tag.get_text(strip=True) if date_tag else ""
        location_tag = card.select_one("[data-marker='item-location']")
        location = location_tag.get_text(strip=True) if location_tag else ""
        desc_tag = card.select_one("div.jNGxV span.snk")
        description = desc_tag.get_text(strip=True) if desc_tag else ""
        if item_id and href:
            items.append({"id": item_id, "title": title, "url": href, "price": price, "date": date_text, "location": location, "description": description[:200]})
    if not items:
        items = _parse_avito_json_ld(soup)
    return items

def _parse_avito_json_ld(soup: BeautifulSoup) -> list[dict]:
    items = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "ItemList":
                for elem in data.get("itemListElement", []):
                    item = elem.get("item", {})
                    url = item.get("url", "")
                    m = re.search(r"/(\d+)", url)
                    item_id = m.group(1) if m else ""
                    if item_id:
                        items.append({"id": item_id, "title": item.get("name", ""), "url": url, "price": "", "date": "", "location": "", "description": ""})
        except Exception:
            continue
    return items

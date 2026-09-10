from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
import re

HH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Referer": "https://spb.hh.ru/",
}


async def fetch_hh_vacancies(area: int, text: str, city_name: str) -> list[dict]:
    base_url = "https://spb.hh.ru/search/vacancy"
    params = f"?text={text}"
    if area:
        params += f"&area={area}"
    url = base_url + params

    resp = curl_requests.get(url, headers=HH_HEADERS, impersonate="chrome", timeout=20)
    resp.raise_for_status()
    html = resp.content.decode('utf-8', errors='replace')
    return _parse_hh_html(html, city_name)


def _parse_hh_html(html: str, city_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items = []

    for card in soup.select("[data-qa='vacancy-serp__vacancy']"):
        title_tag = card.select_one("a[href*='/vacancy/']")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        if href and not href.startswith("http"):
            href = "https://spb.hh.ru" + href

        salary_tag = card.select_one("[data-qa='vacancy-serp__vacancy-compensation']")
        salary = salary_tag.get_text(strip=True) if salary_tag else ""

        employer_tag = card.select_one("[data-qa='vacancy-serp__vacancy-employer'] a")
        employer = employer_tag.get_text(strip=True) if employer_tag else ""

        date_tag = card.select_one("[data-qa='vacancy-serp__vacancy-publication-date']")
        date_text = date_tag.get_text(strip=True) if date_tag else ""

        vacancy_id_match = re.search(r'/(\d+)', href)
        vacancy_id = vacancy_id_match.group(1) if vacancy_id_match else ""

        if vacancy_id:
            items.append({
                "id": vacancy_id,
                "title": title,
                "url": href,
                "price": salary,
                "date": date_text,
                "location": city_name,
                "description": employer,
                "city": city_name,
            })

    return items

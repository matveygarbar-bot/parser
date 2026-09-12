import re
import time
from datetime import date

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    import requests as curl_requests

HH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

HH_DOMAIN = {
    "spb": "spb.hh.ru",
    "petrozavodsk": "spb.hh.ru",
    "yaroslavl": "yaroslavl.hh.ru",
}

HH_AREA = {
    "spb": 2,
    "petrozavodsk": 63,
    "yaroslavl": 44,
}


def fetch_hh_resumes(area: int, cat_key: str) -> list[dict]:
    """Получает резюме с hh.ru для заданного area и категории."""
    # Здесь должна быть логика парсинга hh.ru
    # Заглушка для совместимости
    return []


def enrich_resume(item: dict) -> dict:
    """Обогащает резюме дополнительными данными (город, зарплата и т.д.)."""
    # Заглушка для совместимости
    return item


def parse_updated_days(updated: str) -> int | None:
    """Возвращает сколько дней назад обновлено резюме, или None если не распознано."""
    s = (updated or "").strip().lower()
    if not s:
        return None
    if s.startswith("сегодня"):
        return 0
    if s.startswith("вчера"):
        return 1
    m = re.search(r"(\d{1,2})\s+([а-яё]+)(?:[^\d]*(\d{4}))?", s)
    if not m:
        return None
    day, month_word, year_s = int(m.group(1)), m.group(2), m.group(3)
    RUS_MONTHS = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5,
        "июня": 6, "июля": 7, "августа": 8, "сентября": 9, "октября": 10,
        "ноября": 11, "декабря": 12,
    }
    month = RUS_MONTHS.get(month_word)
    if month is None:
        return None
    today = date.today()
    year = int(year_s) if year_s else today.year
    try:
        d = date(year, month, day)
    except ValueError:
        return None
    if d > today:
        d = date(year - 1, month, day)
    return (today - d).days


def is_fresh(updated: str, max_days: int = 2) -> bool:
    """True если резюме не старше max_days; при нераспознанной дате — True."""
    days = parse_updated_days(updated)
    if days is None:
        return True
    return days <= max_days
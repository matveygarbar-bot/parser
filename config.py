import os

TELEGRAM_TOKEN = os.getenv("TG_TOKEN", "")
CHAT_IDS = [int(x.strip()) for x in os.getenv("TG_CHAT_IDS", "").split(",") if x.strip()]

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "45"))

SOCKS_PROXY = os.getenv("SOCKS_PROXY", "")

CITIES = {
    "spb": {
        "name": "Санкт-Петербург",
        "avito_url": "https://www.avito.ru/search?q=%D0%BA%D1%83%D1%80%D1%8C%D0%B5%D1%80&region=2",
        "hh_area": 2,
    },
    "petrozavodsk": {
        "name": "Петрозаводск",
        "avito_url": "https://www.avito.ru/search?q=%D0%BA%D1%83%D1%80%D1%8C%D0%B5%D1%80&region=109",
        "hh_area": 63,
    },
    "yaroslavl": {
        "name": "Ярославль",
        "avito_url": "https://www.avito.ru/search?q=%D0%BA%D1%83%D1%80%D1%8C%D0%B5%D1%80&region=76",
        "hh_area": 44,
    },
}

HH_SEARCH_TEXT = "курьер"
SEEN_FILE = "seen.json"

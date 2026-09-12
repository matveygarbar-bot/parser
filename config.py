import os

TELEGRAM_TOKEN = os.getenv("TG_TOKEN", "8490088875:AAGPthvjS1VFygOIRKN89A_V-i_IG5Joo1c")
CHAT_IDS = [int(x.strip()) for x in os.getenv("TG_CHAT_IDS", "5046734592,5020987929").split(",") if x.strip()]

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))

# Авито: города и категория резюме курьеров
AVITO_ENABLED = os.getenv("AVITO_ENABLED", "1") == "1"
AVITO_CITIES = ["spb", "petrozavodsk", "yaroslavl"]
# Первый запуск: НЕ слать спам-историю, пометить всё seen и слать только новые
# =0: молча сидируем стартовый батч; =1: стартовый батч уже засижен — слать всё свежее
AVITO_SEND_FIRST_BATCH = os.getenv("AVITO_SEND_FIRST_BATCH", "1") == "1"

SOCKS_PROXY = os.getenv("SOCKS_PROXY", "socks5://127.0.0.1:10808")

# Региональные домены hh.ru для городов
HH_DOMAIN = {
    "spb": "spb.hh.ru",
    "petrozavodsk": "spb.hh.ru",
    "yaroslavl": "yaroslavl.hh.ru",
}

# area_id в hh.ru: 2 - СПб, 63 - Карелия/Петрозаводск, 44 - Ярославль
HH_AREA = {
    "spb": 2,
    "petrozavodsk": 63,
    "yaroslavl": 44,
}

# Города: название для уведомлений
CITY_NAMES = {
    "spb": "Санкт-Петербург",
    "petrozavodsk": "Петрозаводск",
    "yaroslavl": "Ярославль",
}

# Фильтр городов для резюме (по городу из страницы кандидата)
CITY_FILTERS = ["Санкт-Петербург", "Петрозаводск", "Ярославль"]

# Категории резюме на hh.ru.
# slug-страницы ИГНОРИРУЮТ area= — выдают топ-20 по всей России, city определяется потом.
# Поэтому fetch_hh_resumes(area) вызывается с area=2 (СПб) как формальность.
RESUME_CATEGORIES = {
    "courier": {"slug": "kurer", "label": "Курьер", "keywords": ["курьер", "доставк", "курьером"]},
    "courier_personal": {"slug": "kurer-na-lichnom-avto", "label": "Курьер (личн. авто)", "keywords": ["курьер", "доставк"]},
    "courier_auto": {"slug": "voditel-kurer-s-lichnym-avtomobilem", "label": "Водитель-курьер", "keywords": []},
    "ekspeditor": {"slug": "ekspeditor", "label": "Экспедитор", "keywords": []},
    "order_picker": {"slug": "komplektovshik", "label": "Сборщик заказов", "keywords": []},
    "general_worker": {"slug": "raznorabochiy", "label": "Разнорабочий", "keywords": []},
    "beginner": {"slug": "kurer?experience=noExperience", "label": "Без опыта", "keywords": ["курьер", "доставк"]},
}

# SuperJob.ru: парсер резюме (slug-страницы /resume/{slug}.html?period=1)
SUPERJOB_ENABLED = os.getenv("SUPERJOB_ENABLED", "1") == "1"
SUPERJOB_CITIES = ["spb", "petrozavodsk", "yaroslavl"]
SUPERJOB_CATEGORIES = {
    "courier": {"slug": "kurer", "label": "Курьер"},
    "courier_personal": {"slug": "voditel-kurer-s-lichnym-avtomobilem", "label": "Курьер (личн. авто)"},
    "ekspeditor": {"slug": "ekspeditor", "label": "Экспедитор"},
    "order_picker": {"slug": "komplektovschik", "label": "Сборщик заказов"},
    "general_worker": {"slug": "raznorabochij", "label": "Разнорабочий"},
}

# Rabota.ru (только spb/yaroslavl — Петрозаводска нет, редиректит на другой город)
RABOTA_ENABLED = os.getenv("RABOTA_ENABLED", "1") == "1"
RABOTA_CATEGORIES = {
    "courier": {"slug": "Курьер", "label": "Курьер"},
    "general_worker": {"slug": "Разнорабочий", "label": "Разнорабочий"},
}

# =1: первый запуск SJ/Rabota сразу слать всё свежее (≤2 дней, их десятки — потенциальный спам)
# =0: молча сидируем стартовый батч (как Авито), слать только новые появления
SITE_SEND_FIRST_BATCH = os.getenv("SITE_SEND_FIRST_BATCH", "0") == "1"

SEEN_FILE = "seen.json"
PORT = os.getenv("PORT", "8080")
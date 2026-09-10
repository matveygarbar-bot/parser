# Courier Watcher Bot — Бот-парсер резюме курьеров

Отслеживает свежие объявления о работе «Курьер» в **Санкт-Петербурге, Петрозаводске и Ярославле** и отправляет ссылки в Telegram.

## Города
- 🏙️ СанктПетербург (hh.ru area=2)
- 🏙️ Петрозаводск (hh.ru area=63)
- 🏙️ Ярославль (hh.ru area=44)

## Запуск на ноутбуке

```
D:\parser\start_bot.bat
```

## Запуск на хостинге (Render.com — бесплатно 750ч/мес)

1. Загрузи проект на GitHub
2. Зайди на https://render.com → Sign up (через GitHub)
3. New → Worker → подключи репозиторий
4. Настрой env переменные:

| Переменная | Значение |
|-----------|----------|
| `TG_TOKEN` | Токен Telegram бота |
| `TG_CHAT_IDS` | `5046734592,5020987929` |
| `SOCKS_PROXY` | Оставить пустым |
| `CHECK_INTERVAL` | `45` |

5. Deploy → бот запустится

## Запуск через Docker

```bash
docker build -t courier-bot .
docker run -e TG_TOKEN=... -e TG_CHAT_IDS=... courier-bot
```

## Структура

```
config.py          — Настройки (через env)
parser_hh.py       — Парсинг hh.ru
parser_avito.py    — Парсинг Авито (cloudscraper)
notifier.py        — Telegram бот
storage.py         — Дедупликация
main.py            — Основной цикл
Dockerfile         — Для Docker деплоя
render.yaml        — Для Render.com
```

## Telegram

Отправь `/start` боту в Telegram, чтобы получать уведомления.

## Авито

Cloudflare может блокировать IP. Бот автоматически повторяет запрос через 30 сек при 429.

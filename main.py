import asyncio
import logging
from datetime import datetime

import config
from parser_avito import fetch_avito
from parser_hh import fetch_hh_vacancies
from storage import SeenStorage
from notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def check_avito(storage: SeenStorage, notifier: TelegramNotifier):
    for key, city in config.CITIES.items():
        try:
            await asyncio.sleep(5)
            items = await fetch_avito(city["avito_url"])
            new_count = 0
            for item in items:
                k = f"avito_{key}_{item['id']}"
                if not storage.is_seen(k):
                    storage.mark_seen(k)
                    new_count += 1
                    item["city"] = city["name"]
                    await notifier.send_new_item("avito", item)
                    logger.info("New Avito item [%s]: %s", city["name"], item["title"][:50])
            if new_count == 0:
                logger.info("Avito [%s]: no new items", city["name"])
            else:
                logger.info("Avito [%s]: %d new items", city["name"], new_count)
                storage.save()
        except Exception as e:
            logger.error("Avito [%s] check failed: %s", city["name"], e)


async def check_hh(storage: SeenStorage, notifier: TelegramNotifier):
    for key, city in config.CITIES.items():
        try:
            items = await fetch_hh_vacancies(city["hh_area"], config.HH_SEARCH_TEXT, city["name"])
            new_count = 0
            for item in items:
                k = f"hh_{key}_{item['id']}"
                if not storage.is_seen(k):
                    storage.mark_seen(k)
                    new_count += 1
                    item["city"] = city["name"]
                    await notifier.send_new_item("hh", item)
                    logger.info("New HH item [%s]: %s", city["name"], item["title"][:50])
            if new_count == 0:
                logger.info("HH [%s]: no new items", city["name"])
            else:
                logger.info("HH [%s]: %d new items", city["name"], new_count)
                storage.save()
        except Exception as e:
            logger.error("HH [%s] check failed: %s", city["name"], e)


async def main():
    logger.info("Starting courier watcher bot for SPb, Petrozavodsk, Yaroslavl...")

    storage = SeenStorage(config.SEEN_FILE)
    notifier = TelegramNotifier(config.TELEGRAM_TOKEN, config.CHAT_IDS)

    await notifier.send("🤖 Бот запущен. Отслеживаю вакансии курьеров в СПб, Петрозаводске, Ярославле...")

    while True:
        now = datetime.now().strftime("%H:%M:%S")
        logger.info("--- Check cycle at %s ---", now)

        await asyncio.gather(
            check_avito(storage, notifier),
            check_hh(storage, notifier),
        )

        await asyncio.sleep(config.CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")

import asyncio
import logging
from aiohttp import web

import config
from parser_hh import fetch_hh_resumes, enrich_resume, is_fresh
from parser_avito import fetch_avito, start_browser_worker
from parser_superjob import fetch_superjob
from parser_rabota import fetch_rabota
from storage import SeenStorage
from notifier import TelegramNotifier
from cookie_loader import load_hh_cookies, save_hh_cookies

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")],
)
logger = logging.getLogger(__name__)

_lock_avito = asyncio.Lock()
_enrich_sem = asyncio.Semaphore(3)  # до 3 параллельных enrich-запросов (стабильнее для hh)


async def _enrich_one(item: dict) -> dict:
    async with _enrich_sem:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(enrich_resume, item), timeout=25
            )
        except asyncio.TimeoutError:
            logger.warning("enrich timeout for %s", item.get("id"))
            return item  # без города отправлять не будем (отфильтруется)


async def _process_hh_category(cat_key: str, storage: SeenStorage, notifier: TelegramNotifier):
    """Fetch one hh.ru category, enrich new, send immediately."""
    try:
        items = await asyncio.wait_for(asyncio.to_thread(fetch_hh_resumes, 2, cat_key), timeout=40)
        new_items = []
        for item in items:
            k = f"hh_{cat_key}_{item['id']}"
            if storage.is_seen(k):
                continue
            item["category"] = cat_key
            new_items.append(item)

        if not new_items:
            return

        # Параллельный enrich всех новых
        enriched = await asyncio.gather(*[_enrich_one(it) for it in new_items])
        sent = 0
        for item in enriched:
            k = f"hh_{cat_key}_{item['id']}"
            res_city = item.get("city") or ""
            if not is_fresh(item.get("updated")):
                storage.mark_stale(k)
                storage.save()
                logger.info("Skip stale (updated %s): %s", item.get("updated"), item["title"][:40])
                continue
            wanted = config.CITY_FILTERS
            if wanted and not any(w.lower() in res_city.lower() for w in wanted):
                storage.mark_seen(k)
                storage.save()
                logger.debug("Skip (city %s): %s", res_city, item["title"][:40])
                continue
            sent += 1
            await notifier.send_new_item("hh", item)
            storage.mark_seen(k)
            storage.save()
            logger.info("New resume [%s]: %s (%s)", cat_key, item["title"][:50], res_city)
        if sent:
            logger.info("Category %s: %d new resumes sent", cat_key, sent)
    except asyncio.TimeoutError:
        logger.error("HH [%s] timeout (>40s)", cat_key)
    except Exception as e:
        logger.error("HH [%s] failed: %s", cat_key, e)


async def check_hh_resumes(storage: SeenStorage, notifier: TelegramNotifier):
    """Check hh.ru categories: fetch sequential (hh rate-limits), enrich parallel."""
    for cat_key in config.RESUME_CATEGORIES:
        try:
            await _process_hh_category(cat_key, storage, notifier)
        except Exception as e:
            logger.error("HH [%s] unexpected: %s", cat_key, e)
        await asyncio.sleep(1)


async def check_avito_resumes(storage: SeenStorage, notifier: TelegramNotifier):
    """Check Avito resume listings for couriers in wanted cities."""
    async with _lock_avito:
        try:
            result = await asyncio.to_thread(fetch_avito, config.AVITO_CITIES)
            for ck, items in result.items():
                new_count = 0
                for item in items:
                    k = f"avito_{ck}_{item['id']}"
                    if storage.is_seen(k):
                        continue
                    item["category"] = "avito"
                    if not config.AVITO_SEND_FIRST_BATCH:
                        # 1-й запуск: молча сеяем стартовый батч, слать только новые
                        storage.mark_seen(k)
                        storage.save()
                        continue
                    if not is_fresh(item.get("updated")):
                        storage.mark_stale(k)
                        storage.save()
                        logger.info("Skip stale avito (updated %s): %s", item.get("updated"), item["title"][:40])
                        continue
                    new_count += 1
                    await notifier.send_new_item("avito", item)
                    storage.mark_seen(k)
                    storage.save()
                    logger.info("New avito [%s]: %s", ck, item["title"][:50])
                if new_count:
                    logger.info("Avito %s: %d new", ck, new_count)
        except Exception as e:
            logger.error("Avito check failed: %s", e)


async def _process_site_item(source: str, item: dict, storage: SeenStorage, notifier: TelegramNotifier) -> bool:
    """Один резюме с SJ/Rabota: фильтр свежести+города, отправка, пометка. True если отправлено."""
    k = f"{source}_{item['id']}"
    if storage.is_seen(k):
        return False
    if not config.SITE_SEND_FIRST_BATCH:
        # 1-й запуск: молча сеяем стартовый батч, слать только новые
        storage.mark_seen(k)
        storage.save()
        return False
    if not is_fresh(item.get("updated")):
        storage.mark_stale(k)
        storage.save()
        logger.info("Skip stale %s (updated %s): %s", source, item.get("updated"), item["title"][:40])
        return False
    res_city = item.get("city") or ""
    if config.CITY_FILTERS and not any(w.lower() in res_city.lower() for w in config.CITY_FILTERS):
        storage.mark_seen(k)
        storage.save()
        logger.debug("Skip %s (city %s): %s", source, res_city, item["title"][:40])
        return False
    await notifier.send_new_item(source, item)
    storage.mark_seen(k)
    storage.save()
    logger.info("New %s: %s (%s)", source, item["title"][:50], res_city)
    return True


async def check_superjob_resumes(storage: SeenStorage, notifier: TelegramNotifier):
    """Check SuperJob resume categories for wanted cities (period=1, свежие)."""
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(fetch_superjob, config.SUPERJOB_CITIES, list(config.SUPERJOB_CATEGORIES)),
            timeout=180,
        )
        sent = 0
        for cats in result.values():
            for cat_key, items in cats.items():
                for item in items:
                    item["category"] = cat_key
                    if await _process_site_item("superjob", item, storage, notifier):
                        sent += 1
        if sent:
            logger.info("SuperJob: %d new resumes sent", sent)
    except asyncio.TimeoutError:
        logger.error("SuperJob scan timed out (>180s)")
    except Exception as e:
        logger.error("SuperJob check failed: %s", e)


async def check_rabota_resumes(storage: SeenStorage, notifier: TelegramNotifier):
    """Check Rabota.ru resume categories (spb/yaroslavl; Петрозаводска нет)."""
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(fetch_rabota, ["spb", "yaroslavl"], list(config.RABOTA_CATEGORIES)),
            timeout=180,
        )
        sent = 0
        for cats in result.values():
            for cat_key, items in cats.items():
                for item in items:
                    item["category"] = cat_key
                    if await _process_site_item("rabota", item, storage, notifier):
                        sent += 1
        if sent:
            logger.info("Rabota: %d new resumes sent", sent)
    except asyncio.TimeoutError:
        logger.error("Rabota scan timed out (>180s)")
    except Exception as e:
        logger.error("Rabota check failed: %s", e)


async def health(request):
    return web.Response(text="ok")


async def avito_loop(storage: SeenStorage, notifier: TelegramNotifier):
    while True:
        await check_avito_resumes(storage, notifier)
        logger.info("Avito cycle done, next in %ss", config.CHECK_INTERVAL)
        await asyncio.sleep(config.CHECK_INTERVAL)


async def hh_loop(storage: SeenStorage, notifier: TelegramNotifier):
    while True:
        await check_hh_resumes(storage, notifier)
        logger.info("HH cycle done, next in %ss", config.CHECK_INTERVAL)
        await asyncio.sleep(config.CHECK_INTERVAL)


async def superjob_loop(storage: SeenStorage, notifier: TelegramNotifier):
    while True:
        await check_superjob_resumes(storage, notifier)
        logger.info("SuperJob cycle done, next in %ss", config.CHECK_INTERVAL)
        await asyncio.sleep(config.CHECK_INTERVAL)


async def rabota_loop(storage: SeenStorage, notifier: TelegramNotifier):
    while True:
        await check_rabota_resumes(storage, notifier)
        logger.info("Rabota cycle done, next in %ss", config.CHECK_INTERVAL)
        await asyncio.sleep(config.CHECK_INTERVAL)


async def run_bot():
    cookies, source = load_hh_cookies()
    if cookies:
        save_hh_cookies(cookies, source)
        logger.info("hh.ru cookies loaded: %s", source)
    else:
        logger.warning("No hh.ru cookies found. Log in first (hh_login.py).")

    storage = SeenStorage(config.SEEN_FILE)
    notifier = TelegramNotifier(config.TELEGRAM_TOKEN, config.CHAT_IDS)
    if config.AVITO_ENABLED:
        start_browser_worker()
        logger.info("Avito browser worker started (headless Edge)")
    sources = [("hh.ru", config.RESUME_CATEGORIES)]
    if config.SUPERJOB_ENABLED:
        sources.append(("SuperJob", config.SUPERJOB_CATEGORIES))
    if config.RABOTA_ENABLED:
        sources.append(("Rabota.ru", config.RABOTA_CATEGORIES))
    await notifier.send(
        "✅ Бот запущен.\n"
        + "\n".join(f"📂 {name}: {len(cats)} категорий ({', '.join(cats.keys())})" for name, cats in sources)
        + f"\n🏙 Города: {', '.join(config.CITY_FILTERS)}\n"
        f"⏱ Интервал: {config.CHECK_INTERVAL} сек"
    )

    tasks = []
    if config.AVITO_ENABLED:
        tasks.append(asyncio.create_task(avito_loop(storage, notifier)))
    tasks.append(asyncio.create_task(hh_loop(storage, notifier)))
    if config.SUPERJOB_ENABLED:
        tasks.append(asyncio.create_task(superjob_loop(storage, notifier)))
    if config.RABOTA_ENABLED:
        tasks.append(asyncio.create_task(rabota_loop(storage, notifier)))
    await asyncio.gather(*tasks)


async def main():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(config.PORT))
    await site.start()
    logger.info("Health server started on port %s", config.PORT)
    await run_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")

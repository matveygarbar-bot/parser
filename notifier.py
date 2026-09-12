import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

import config

logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "courier": "📦 Курьер",
    "courier_personal": "🛵 Курьер (личн. авто)",
    "courier_auto": "🚗 Водитель-курьер",
    "ekspeditor": "🚚 Экспедитор",
    "order_picker": "📦 Сборщик заказов",
    "general_worker": "🧰 Разнорабочий",
    "beginner": "🌱 Без опыта",
    "avito": "🟠 Авито",
}

SOURCE_EMOJI = {
    "hh": "🔵",
    "avito": "🟠",
    "superjob": "🟣",
    "rabota": "🟡",
}


class TelegramNotifier:
    def __init__(self, token: str, chat_ids: list[int]):
        session = AiohttpSession(proxy=config.SOCKS_PROXY) if config.SOCKS_PROXY else None
        self.bot = Bot(token=token, session=session, parse_mode=ParseMode.HTML)
        self.chat_ids = chat_ids

    async def send(self, text: str):
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(chat_id=chat_id, text=text)
                logger.info("Sent to %s", chat_id)
            except Exception as e:
                logger.error("Failed to send to %s: %s", chat_id, e)

    async def send_new_item(self, source: str, item: dict):
        text = self.format_new_item(source, item)
        await self.send(text)

    @staticmethod
    def format_new_item(source: str, item: dict) -> str:
        source_emoji = SOURCE_EMOJI.get(source, "📄")
        city = item.get("city") or item.get("location", "")
        cat = CATEGORY_LABELS.get(item.get("category"), "📄 Резюме")
        updated = (item.get("updated") or "").strip()
        is_fresh = "сегодня" in updated.lower()
        header = "🔥 <b>СВЕЖИЙ</b> " if is_fresh else ""
        text = (
            f"{source_emoji} <b>НОВОЕ РЕЗЮМЕ</b>{header}— {cat}\n"
            f"📍 {city}\n\n"
            f"📋 <b>{item['title']}</b>\n"
        )
        if item.get("age"):
            text += f"🎂 {item['age']}\n"
        if item.get("status"):
            text += f"🏷 {item['status']}\n"
        if item.get("area"):
            text += f"🗺 {item['area']}\n"
        if updated:
            text += f"🕒 {updated}\n"
        if item.get("phone"):
            text += f"📞 {item['phone']}\n"
        if item.get("price"):
            price = item["price"]
            if "₽" not in price:
                price += " ₽"
            text += f"💰 {price}\n"
        if item.get("description"):
            text += f"ℹ️ {item['description']}\n"
        text += f"\n🔗 <a href=\"{item['url']}\">Открыть резюме</a>"
        return text
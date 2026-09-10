import logging
from aiogram import Bot
from aiogram.enums import ParseMode

import config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: str, chat_ids: list[int]):
        if config.SOCKS_PROXY:
            from aiogram.client.session.aiohttp import AiohttpSession
            session = AiohttpSession(proxy=config.SOCKS_PROXY)
            self.bot = Bot(token=token, session=session, parse_mode=ParseMode.HTML)
        else:
            self.bot = Bot(token=token, parse_mode=ParseMode.HTML)
        self.chat_ids = chat_ids

    async def send(self, text: str):
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(chat_id=chat_id, text=text)
                logger.info("Sent to %s", chat_id)
            except Exception as e:
                logger.error("Failed to send to %s: %s", chat_id, e)

    async def send_new_item(self, source: str, item: dict):
        source_emoji = "🟠" if source == "avito" else "🔵"
        city = item.get("city", "")
        text = (
            f"{source_emoji} <b>Новое резюме ({source.upper()}) {city}</b>\n\n"
            f"📋 {item['title']}\n"
        )
        if item.get("location"):
            text += f"📍 {item['location']}\n"
        if item.get("price"):
            text += f"💰 {item['price']}\n"
        if item.get("date"):
            text += f"🕐 {item['date']}\n"
        if item.get("description"):
            text += f"\n{item['description'][:150]}\n"
        text += f"\n🔗 <a href=\"{item['url']}\">Открыть</a>"
        await self.send(text)

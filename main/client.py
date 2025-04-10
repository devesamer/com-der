from telethon import TelegramClient
from main.config import Config
import asyncio

async def start_bot():
    bot = TelegramClient('bot', Config.API_ID, Config.API_HASH)
    await bot.start(bot_token=Config.TOKEN)
    return bot

bot = asyncio.run(start_bot())

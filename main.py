import asyncio
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Данные бота
TELEGRAM_BOT_TOKEN = "8811178509:AAHqCF3BIODntZfIM50d66t8nOGIIIyBVdU"
MY_USER_ID = os.getenv("MY_USER_ID")  # Твой ID из userinfobot
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_MINUTES", "30")) * 60
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
posted_ids = set()

async def fetch_space_news():
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=3"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("results", [])
    return []

# Реакция на команду /start в личке
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("🚀 Привет! Я космический бот. Буду присылать тебе свежие новости о космосе!")

async def check_and_post():
    if not MY_USER_ID:
        print("⚠️ Ошибка: MY_USER_ID не указан в Environment на Render!")
        return
        
    articles = await fetch_space_news()
    for article in reversed(articles):
        article_id = article.get("id")
        if article_id not in posted_ids:
            title = article.get("title", "")
            summary = article.get("summary", "")
            url = article.get("url", "")
            
            text = f"<b>{title}</b>\n\n{summary}\n\n🔗 <a href='{url}'>Читать источник</a>"
            
            try:
                await bot.send_message(
                    chat_id=MY_USER_ID,
                    text=text,
                    parse_mode="HTML"
                )
                posted_ids.add(article_id)
                print(f"Отправлено пользователю {MY_USER_ID}: {title}")
            except Exception as e:
                print(f"Ошибка отправки: {e}")

async def news_loop():
    while True:
        try:
            await check_and_post()
        except Exception as e:
            print(f"Ошибка в цикле: {e}")
        await asyncio.sleep(FETCH_INTERVAL)

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    print("🚀 Старт сервера и бота...")
    
    # Веб-сервер для Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    # Фоновая задача автопостинга
    asyncio.create_task(news_loop())
    
    # Запуск обработки команд (например /start)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

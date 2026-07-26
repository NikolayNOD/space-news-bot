import asyncio
import os
import aiohttp
from aiohttp import web
from aiogram import Bot

# Токен твоего бота
TELEGRAM_BOT_TOKEN = "8811178509:AAHqCF3BIODntZfIM50d66t8nOGIIIyBVdU"

# Переменные из Render
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@tanyaspacelove_bot")
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_MINUTES", "30")) * 60
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
posted_ids = set()

async def fetch_space_news():
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=3"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("results", [])
    return []

async def check_and_post():
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
                    chat_id=TELEGRAM_CHANNEL_ID,
                    text=text,
                    parse_mode="HTML"
                )
                posted_ids.add(article_id)
                print(f"Опубликовано: {title}")
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
    
    # Создаем веб-сервер для Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    # Запускаем фоновую задачу проверки новостей
    asyncio.create_task(news_loop())
    
    # Держим процесс активным
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

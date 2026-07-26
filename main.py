import os
import asyncio
import logging
import json
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from groq import AsyncGroq

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", "30"))

DB_FILE = "published_news.json"

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
groq_client = AsyncGroq(api_key=GROQ_API_KEY)


def load_published_ids() -> set:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_published_id(article_id: int):
    published = load_published_ids()
    published.add(article_id)
    if len(published) > 500:
        published = set(list(published)[-500:])
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(list(published), f)


async def fetch_latest_space_news():
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=5"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("results", [])
            return []


async def generate_post_with_ai(title: str, summary: str, news_url: str) -> str:
    prompt = f"""
Ты — профессиональный космический журналист. Напиши увлекательный пост для Telegram-канала.

Данные новости:
- Заголовок: {title}
- Описание: {summary}
- Ссылка: {news_url}

Требования к оформлению:
1. Заголовок: Завлекающий, с тематическими эмодзи (🚀, 🌌 и т.д.).
2. Перевод и адаптация (на русском): Интересный, простой для чтения пересказ новости.
3. Оригинальный фрагмент (на английском): Вставь 1-2 предложения цитаты из оригинала.
4. Ссылка: В конце укажи прямую ссылку на первоисточник.
5. Использовать ТОЛЬКО теги HTML (<b>, <i>, <a href="...">).

Верни ТОЛЬКО готовый текст поста.
"""
    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Ошибка AI: {e}")
        return None


async def process_and_send_news():
    logging.info("Проверка новых новостей...")
    articles = await fetch_latest_space_news()
    published_ids = load_published_ids()

    articles.reverse()

    for article in articles:
        article_id = article.get("id")
        if article_id in published_ids:
            continue

        title = article.get("title")
        summary = article.get("summary")
        url = article.get("url")
        image_url = article.get("image_url")

        post_text = await generate_post_with_ai(title, summary, url)
        if not post_text:
            continue

        try:
            if image_url:
                await bot.send_photo(
                    chat_id=TELEGRAM_CHANNEL_ID,
                    photo=image_url,
                    caption=post_text
                )
            else:
                await bot.send_message(
                    chat_id=TELEGRAM_CHANNEL_ID,
                    text=post_text
                )

            save_published_id(article_id)
            logging.info(f"Опубликовано: ID {article_id}")
            await asyncio.sleep(5)

        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")


async def news_scheduler():
    while True:
        try:
            await process_and_send_news()
        except Exception as e:
            logging.error(f"Ошибка планировщика: {e}")
        await asyncio.sleep(INTERVAL_MINUTES * 60)


async def main():
    logging.basicConfig(level=logging.INFO)
    print("🚀 Бот автопостинга космоса запущен...")
    asyncio.create_task(news_scheduler())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TELEGRAM_BOT_TOKEN = "8811178509:AAHqCF3BIODntZfIM50d66t8nOGIIIyBVdU"
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Хранилище последних новостей для каждого пользователя
user_last_article = {}

# Главные кнопки выбора категории (внизу экрана)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🇷🇺 Новости космоса России")],
        [KeyboardButton(text="🌍 Новости космоса Мира")]
    ],
    resize_keyboard=True
)

# Инлайн-кнопки действия под самой новостью
def get_article_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Преобразовать в пост", callback_data="make_post"),
                InlineKeyboardButton(text="🌐 Перевести оригинал", callback_data="translate_full")
            ]
        ]
    )

async def translate_text(text: str, target_lang="ru") -> str:
    """Автоматический перевод текста через MyMemory API"""
    if not text:
        return ""
    url = f"https://api.mymemory.translated.net/get?q={text[:500]}&langpair=en|{target_lang}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    translated = data.get("responseData", {}).get("translatedText", "")
                    return translated if translated else text
    except Exception as e:
        print(f"Ошибка перевода: {e}")
    return text

async def fetch_world_space_news():
    """Загрузка мировых новостей космоса"""
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=5"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("results", [])
    return []

# 1. При приветствии отправляем кнопки выбора
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🚀 **Привет! Я космический бот. Буду присылать тебе свежие новости о космосе!**\n\n"
        "Выбери, какие новости тебя интересуют:",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

# 2. Обработка нажатия «🌍 Новости космоса Мира»
@dp.message(F.text == "🌍 Новости космоса Мира")
async def world_news_handler(message: types.Message):
    await message.answer("🛸 Поиск мировых космических новостей...")
    articles = await fetch_world_space_news()
    if not articles:
        await message.answer("❌ К сожалению, свежих мировых новостей пока не найдено.")
        return

    article = articles[0]
    title = article.get("title", "")
    summary = article.get("summary", "")
    url = article.get("url", "")

    translated_title = await translate_text(title)
    translated_summary = await translate_text(summary)

    user_last_article[message.from_user.id] = {
        "raw_title": title,
        "raw_summary": summary,
        "title": translated_title,
        "summary": translated_summary,
        "url": url,
        "category": "Мир"
    }

    text = (
        f"🌍 **МИРОВЫЕ НОВОСТИ КОСМОСА**\n\n"
        f"🌌 **{translated_title}**\n\n"
        f"{translated_summary}\n\n"
        f"🔗 **Источник:** [Читать оригинал]({url})"
    )
    await message.answer(text, reply_markup=get_article_inline_keyboard(), parse_mode="Markdown")

# 3. Обработка нажатия «🇷🇺 Новости космоса России»
@dp.message(F.text == "🇷🇺 Новости космоса России")
async def russia_news_handler(message: types.Message):
    await message.answer("🛸 Поиск космических новостей России (Роскосмос)...")
    articles = await fetch_world_space_news()
    
    # Находим новость с упоминанием Роскосмоса/России, или берем актуальную космическую
    selected = None
    for art in articles:
        text_full = (art.get("title", "") + art.get("summary", "")).lower()
        if "russia" in text_full or "roscosmos" in text_full or "soyuz" in text_full:
            selected = art
            break
    
    if not selected:
        selected = articles[0] if articles else None

    if not selected:
        await message.answer("❌ Новостей пока не найдено.")
        return

    title = selected.get("title", "")
    summary = selected.get("summary", "")
    url = selected.get("url", "")

    translated_title = await translate_text(title)
    translated_summary = await translate_text(summary)

    user_last_article[message.from_user.id] = {
        "raw_title": title,
        "raw_summary": summary,
        "title": translated_title,
        "summary": translated_summary,
        "url": url,
        "category": "Россия"
    }

    text = (
        f"🇷🇺 **НОВОСТИ КОСМОСА РОССИИ И РОСКОСМОСА**\n\n"
        f"🚀 **{translated_title}**\n\n"
        f"{translated_summary}\n\n"
        f"🔗 **Источник:** [Читать источник]({url})"
    )
    await message.answer(text, reply_markup=get_article_inline_keyboard(), parse_mode="Markdown")

# Кнопка «📝 Преобразовать в пост»
@dp.callback_query(F.data == "make_post")
async def make_post_callback(callback: types.CallbackQuery):
    data = user_last_article.get(callback.from_user.id)
    if not data:
        await callback.answer("Пожалуйста, выбери новость заново!", show_alert=True)
        return

    post_text = (
        f"🚀 **НОВОСТИ КОСМОСА ({data['category'].upper()})**\n\n"
        f"✨ **{data['title']}**\n\n"
        f"📌 {data['summary']}\n\n"
        f"💬 *Что вы думаете об этом космическом событии?*\n\n"
        f"🔗 [Первоисточник]({data['url']})"
    )
    await callback.message.answer(f"📝 **Готовый пост для публикации:**\n\n{post_text}", parse_mode="Markdown")
    await callback.answer()

# Кнопка «🌐 Перевести оригинал»
@dp.callback_query(F.data == "translate_full")
async def translate_full_callback(callback: types.CallbackQuery):
    data = user_last_article.get(callback.from_user.id)
    if not data:
        await callback.answer("Пожалуйста, выбери новость заново!", show_alert=True)
        return

    full_translation = (
        f"🌐 **Точный перевод статьи:**\n\n"
        f"**Заголовок:** {data['title']}\n"
        f"*(Оригинал: {data['raw_title']})*\n\n"
        f"**Текст:** {data['summary']}\n\n"
        f"🔗 **Ссылка:** {data['url']}"
    )
    await callback.message.answer(full_translation, parse_mode="Markdown")
    await callback.answer()

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    print("🚀 Бот запустился...")
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

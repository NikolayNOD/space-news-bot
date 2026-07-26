import asyncio
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TELEGRAM_BOT_TOKEN = "8811178509:AAHqCF3BIODntZfIM50d66t8nOGIIIyBVdU"
MY_USER_ID = os.getenv("MY_USER_ID")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Хранилище временных данных о последней найденной новости
user_last_article = {}

# Главное меню с кнопкой «Найти новости»
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔍 Найти новости")]],
    resize_keyboard=True
)

# Инлайн-кнопки под сообщением с новостью
def get_article_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Преобразовать в пост", callback_data="make_post"),
                InlineKeyboardButton(text="🌐 Перевести оригинал", callback_data="translate_full")
            ]
        ]
    )

async def fetch_latest_space_news():
    """Загрузка свежих новостей космоса со всего мира"""
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=5"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("results", [])
    return []

async def translate_text(text: str, target_lang="ru") -> str:
    """Бесплатный автоперевод текста через MyMemory API"""
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

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🚀 **Привет! Я твой космический ассистент.**\n\n"
        "Нажимай кнопку **«🔍 Найти новости»**, чтобы я собрал самые интересные события о космосе со всего мира!",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔍 Найти новости")
async def search_news_handler(message: types.Message):
    await message.answer("🛸 Сканирую космические источники со всего мира... Ожидай!")
    
    articles = await fetch_latest_space_news()
    if not articles:
        await message.answer("❌ К сожалению, свежих новостей пока не найдено.")
        return

    # Берем самую свежую новость
    article = articles[0]
    title = article.get("title", "")
    summary = article.get("summary", "")
    url = article.get("url", "")
    
    # Переводим заголовок и краткое описание
    translated_title = await translate_text(title)
    translated_summary = await translate_text(summary)
    
    # Сохраняем в память для кнопок поста/перевода
    user_last_article[message.from_user.id] = {
        "raw_title": title,
        "raw_summary": summary,
        "title": translated_title,
        "summary": translated_summary,
        "url": url
    }
    
    text = (
        f"🌌 **{translated_title}**\n\n"
        f"{translated_summary}\n\n"
        f"🔗 **Источник:** [Читать оригинал]({url})"
    )
    
    await message.answer(text, reply_markup=get_article_inline_keyboard(), parse_mode="Markdown", disable_web_page_preview=False)

@dp.callback_query(F.data == "make_post")
async def make_post_callback(callback: types.CallbackQuery):
    data = user_last_article.get(callback.from_user.id)
    if not data:
        await callback.answer("Новость устарела, найди новую!", show_alert=True)
        return

    post_text = (
        f"🚀 **ПОСЛЕДНИЕ НОВОСТИ КОСМОСА**\n\n"
        f"✨ **{data['title']}**\n\n"
        f"📌 {data['summary']}\n\n"
        f"💬 *А что вы думаете об этом открытии? Пишите в комментариях!*\n\n"
        f"🔗 [Ссылка на первоисточник]({data['url']})"
    )
    
    await callback.message.answer(f"📝 **Готовый пост для публикации:**\n\n{post_text}", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "translate_full")
async def translate_full_callback(callback: types.CallbackQuery):
    data = user_last_article.get(callback.from_user.id)
    if not data:
        await callback.answer("Новость устарела, найди новую!", show_alert=True)
        return

    full_translation = (
        f"🌐 **Точный перевод оригинала:**\n\n"
        f"**Заголовок:** {data['title']}\n"
        f"*(Оригинал: {data['raw_title']})*\n\n"
        f"**Описание:** {data['summary']}\n\n"
        f"🔗 **Ссылка на статью:** {data['url']}"
    )
    
    await callback.message.answer(full_translation, parse_mode="Markdown")
    await callback.answer()

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    print("🚀 Старт сервера и обновленного бота...")
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

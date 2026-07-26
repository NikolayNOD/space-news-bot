import asyncio
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Токен твоего бота
TELEGRAM_BOT_TOKEN = "8811178509:AAHqCF3BIODntZfIM50d66t8nOGIIIyBVdU"
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Хранилище последних новостей (оставим, но для кнопок будем использовать другой метод)
user_last_article = {}

# Главное меню с кнопкой «Найти новости»
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔍 Найти новости про космос")]],
    resize_keyboard=True
)

# Инлайн-кнопки под сообщением с новостью (мы убрали "make_post" и "translate_full", т.к. они вызывали сбой)
# Теперь эти кнопки будут ссылками на специальные команды, которые мы обработаем
def get_article_inline_keyboard(article_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Преобразовать в пост", callback_data=f"post_{article_id}"),
                InlineKeyboardButton(text="🌐 Перевести оригинал", callback_data=f"trans_{article_id}")
            ]
        ]
    )

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

async def fetch_latest_space_news():
    """Загрузка свежих новостей космоса со всего мира"""
    # Мы берем 10 новостей, чтобы было из чего выбрать, если Render перезапустится
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=10"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("results", [])
    return []

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🚀 **Привет! Я твой космический ассистент.**\n\n"
        "Нажимай кнопку **«🔍 Найти новости про космос»**, чтобы я собрал самые интересные события со всего мира!",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔍 Найти новости про космос")
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
    article_id = article.get("id") # Важный ID новости
    
    # Переводим заголовок и краткое описание
    translated_title = await translate_text(title)
    translated_summary = await translate_text(summary)
    
    # Сохраняем в память (на всякий случай, но кнопки теперь надежнее)
    user_last_article[message.from_user.id] = article
    
    # Формируем текст сообщения
    text = (
        f"🌌 **{translated_title}**\n\n"
        f"{translated_summary}\n\n"
        f"🔗 **Источник:** [Читать оригинал]({url})\n"
        f"*(Оригинальный заголовок: {title})*"
    )
    
    # Отправляем сообщение с кнопками, которые привязаны к ID новости
    await message.answer(text, reply_markup=get_article_inline_keyboard(article_id), parse_mode="Markdown", disable_web_page_preview=False)

# --- НОВЫЕ ХЕНДЛЕРЫ ДЛЯ КНОПОК, КОТОРЫЕ НЕ СБОЯТ ---

# 1. Хендлер для кнопки "Преобразовать в пост"
@dp.callback_query(F.data.startswith("post_"))
async def make_post_callback_fixed(callback: types.CallbackQuery):
    # Получаем ID новости из даты кнопки
    article_id = callback.data.split("_")[1]
    
    # Пытаемся найти эту новость в последних загруженных (это быстро)
    # Это надежнее, чем хранить в user_last_article
    articles = await fetch_latest_space_news()
    article = next((a for a in articles if str(a.get("id")) == article_id), None)

    if not article:
        # Если новость совсем старая и ушла из списка 10 последних, мы её не восстановим
        await callback.answer("Упс! Эта новость слишком старая, я её больше не вижу в источниках. Найди новую!", show_alert=True)
        return

    # Если нашли, делаем пост
    title = article.get("title", "")
    summary = article.get("summary", "")
    url = article.get("url", "")
    
    translated_title = await translate_text(title)
    translated_summary = await translate_text(summary)

    post_text = (
        f"🚀 **ПОСЛЕДНИЕ НОВОСТИ КОСМОСА**\n\n"
        f"✨ **{translated_title}**\n\n"
        f"📌 {translated_summary}\n\n"
        f"💬 *А что вы думаете об этом открытии? Пишите в комментариях!*\n\n"
        f"🔗 [Ссылка на первоисточник]({url})"
    )
    
    # Отправляем готовый пост новым сообщением
    await callback.message.answer(f"📝 **Готовый пост для публикации:**\n\n{post_text}", parse_mode="Markdown")
    # Обязательно отвечаем на колбэк, чтобы кнопка перестала "часики" крутить
    await callback.answer()

# 2. Хендлер для кнопки "Перевести оригинал"
@dp.callback_query(F.data.startswith("trans_"))
async def translate_full_callback_fixed(callback: types.CallbackQuery):
    # Получаем ID новости
    article_id = callback.data.split("_")[1]
    
    # Ищем новость
    articles = await fetch_latest_space_news()
    article = next((a for a in articles if str(a.get("id")) == article_id), None)

    if not article:
        await callback.answer("Упс! Эта новость слишком старая, я её больше не вижу в источниках. Найди новую!", show_alert=True)
        return

    # Если нашли, делаем полный перевод
    title = article.get("title", "")
    summary = article.get("summary", "")
    url = article.get("url", "")
    
    translated_title = await translate_text(title)
    translated_summary = await translate_text(summary)

    full_translation = (
        f"🌐 **Точный перевод оригинала:**\n\n"
        f"**Заголовок:** {translated_title}\n"
        f"*(Оригинал: {title})*\n\n"
        f"**Описание:** {translated_summary}\n\n"
        f"🔗 **Ссылка на статью:** {url}"
    )
    
    # Отправляем перевод новым сообщением
    await callback.message.answer(full_translation, parse_mode="Markdown")
    await callback.answer()

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    print("🚀 Старт сервера и обновленного бота...")
    
    # Веб-сервер для Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    # Запуск обработки команд
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Токен Telegram
TELEGRAM_BOT_TOKEN = "8811178509:AAHqCF3BIODntZfIM50d66t8nOGIIIyBVdU"
# Ключ Groq API для нейросети (если есть свой - вставь в Environment, либо бот будет использовать встроенную логику)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Кэш новостей пользователей
user_news_cache = {}
user_seen_ids = {}

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚀 Найти космический тренд")]],
    resize_keyboard=True
)

def get_article_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 ИИ-Генерация SMM-поста", callback_data="generate_ai_post"),
                InlineKeyboardButton(text="🌐 Перевод оригинала", callback_data="translate_full")
            ],
            [
                InlineKeyboardButton(text="➡️ Следующая новость", callback_data="next_news")
            ]
        ]
    )

async def translate_with_ai(text: str, mode: str = "translate") -> str:
    """Генерация текстов и качественный перевод через нейросеть Groq или запасной API"""
    if not text:
        return ""

    # Если добавлен ключ Groq API, используем полноценную нейросеть
    if GROQ_API_KEY:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        system_prompt = (
            "Ты — топовый SMM-специалист космического медиа. "
            "Твоя задача — писать вирусные, безупречные посты на русском языке про космос и астрономию."
            if mode == "smm" else
            "Ты профессиональный переводчик. Переведи текст о космосе на естественный и красивый русский язык."
        )

        user_prompt = (
            f"Сделай из этой новости про космос крутой SMM-пост для Telegram с эмодзи, цепляющим заголовком и структурой:\n\n{text}"
            if mode == "smm" else
            f"Переведи этот текст на русский язык:\n\n{text}"
        )

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=12) as resp:
                    if resp.status == 200:
                        res_data = await resp.json()
                        return res_data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Ошибка ИИ: {e}")

    # Резервный автоперевод, если ключа ИИ нет или сеть недоступна
    chunk = text[:600]
    fallback_url = f"https://api.mymemory.translated.net/get?q={chunk}&langpair=en|ru"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(fallback_url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    trans = data.get("responseData", {}).get("translatedText", "")
                    if trans and "MYMEMORY WARNING" not in trans:
                        return trans
    except Exception:
        pass

    return text

async def fetch_space_news():
    """Сбор мировых новостей"""
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=20"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("results", [])
    except Exception as e:
        print(f"Ошибка получения новостей: {e}")
    return []

async def send_news_item(user_id: int, message_or_callback):
    articles = user_news_cache.get(user_id, [])
    seen = user_seen_ids.get(user_id, set())

    selected_article = None
    for art in articles:
        if art.get("id") not in seen:
            selected_article = art
            break

    if not selected_article:
        txt = "🎉 Ты просмотрел все свежие космические тренды! Нажми кнопку снова чуть позже."
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(txt)
        else:
            await message_or_callback.message.answer(txt)
            await message_or_callback.answer()
        return

    seen.add(selected_article.get("id"))
    user_seen_ids[user_id] = seen

    title = selected_article.get("title", "")
    summary = selected_article.get("summary", "")
    url = selected_article.get("url", "")
    image_url = selected_article.get("image_url", "")
    site = selected_article.get("news_site", "World Space News")

    ru_title = await translate_with_ai(title, mode="translate")
    ru_summary = await translate_with_ai(summary, mode="translate")

    user_news_cache[f"{user_id}_current"] = {
        "raw_title": title,
        "raw_summary": summary,
        "ru_title": ru_title,
        "ru_summary": ru_summary,
        "url": url,
        "image_url": image_url,
        "site": site
    }

    caption_text = (
        f"🌌 **{ru_title}**\n\n"
        f"📖 {ru_summary}\n\n"
        f"📡 **Источник:** {site}\n"
        f"🔗 [Первоисточник]({url})"
    )

    target_msg = message_or_callback if isinstance(message_or_callback, types.Message) else message_or_callback.message

    try:
        if image_url:
            await target_msg.answer_photo(
                photo=image_url,
                caption=caption_text,
                reply_markup=get_article_inline_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await target_msg.answer(
                text=caption_text,
                reply_markup=get_article_inline_keyboard(),
                parse_mode="Markdown"
            )
    except Exception:
        await target_msg.answer(
            text=caption_text,
            reply_markup=get_article_inline_keyboard(),
            parse_mode="Markdown"
        )

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.answer()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🚀 **Привет! Я твой ИИ-SMM ассистент по космосу.**\n\n"
        "Я собираю тренды из мира космонавтики и астрономии и превращаю их в готовый контент для твоих соцсетей!\n\n"
        "Нажми кнопку ниже 👇",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "🚀 Найти космический тренд")
async def search_news_handler(message: types.Message):
    await message.answer("🛸 Нейросеть сканирует мировые новости и астрономические базы...")
    articles = await fetch_space_news()
    if not articles:
        await message.answer("❌ Ошибка загрузки. Попробуй еще раз!")
        return

    user_news_cache[message.from_user.id] = articles
    await send_news_item(message.from_user.id, message)

@dp.callback_query(F.data == "next_news")
async def next_news_callback(callback: types.CallbackQuery):
    await send_news_item(callback.from_user.id, callback)

@dp.callback_query(F.data == "generate_ai_post")
async def generate_ai_post_callback(callback: types.CallbackQuery):
    data = user_news_cache.get(f"{callback.from_user.id}_current")
    if not data:
        await callback.answer("Выбери новость заново!", show_alert=True)
        return

    await callback.message.answer("🤖 *ИИ пишет готовый SMM-пост... Минутку!*", parse_mode="Markdown")

    raw_text = f"Title: {data['raw_title']}\nSummary: {data['raw_summary']}"
    ai_smm_post = await translate_with_ai(raw_text, mode="smm")

    # Если ИИ ключ не был добавлен, форматируем в красивый шаблон
    if not GROQ_API_KEY or "Title:" in ai_smm_post:
        ai_smm_post = (
            f"🚨 **ГЛАВНОЕ В КОСМОСЕ: {data['ru_title'].upper()}**\n\n"
            f"✨ {data['ru_summary']}\n\n"
            f"💡 **Почему это важно?**\n"
            f"Это открытие развивает наше понимание Вселенной и задает новый тренд в космической отрасли!\n\n"
            f"💬 *Что вы думаете по этому поводу? Делитесь в комментариях!* 👇\n\n"
            f"📌 #космос #астрономия #наука #технологии\n"
            f"🔗 [Читать оригинал]({data['url']})"
        )

    if data.get("image_url"):
        try:
            await callback.message.answer_photo(
                photo=data["image_url"],
                caption=f"📝 **ГОТОВЫЙ ПОСТ ДЛЯ СОЦСЕТЕЙ:**\n\n{ai_smm_post}",
                parse_mode="Markdown"
            )
        except Exception:
            await callback.message.answer(f"📝 **ГОТОВЫЙ ПОСТ ДЛЯ СОЦСЕТЕЙ:**\n\n{ai_smm_post}", parse_mode="Markdown")
    else:
        await callback.message.answer(f"📝 **ГОТОВЫЙ ПОСТ ДЛЯ СОЦСЕТЕЙ:**\n\n{ai_smm_post}", parse_mode="Markdown")

    await callback.answer()

@dp.callback_query(F.data == "translate_full")
async def translate_full_callback(callback: types.CallbackQuery):
    data = user_news_cache.get(f"{callback.from_user.id}_current")
    if not data:
        await callback.answer("Выбери новость заново!", show_alert=True)
        return

    translation_text = (
        f"🌐 **ПОЛНЫЙ ПЕРЕВОД ИСТОЧНИКА:**\n\n"
        f"📌 **Заголовок:** {data['ru_title']}\n"
        f"*(Оригинал: {data['raw_title']})*\n\n"
        f"📝 **Описание:** {data['ru_summary']}\n\n"
        f"🔗 **Ссылка:** {data['url']}"
    )
    await callback.message.answer(translation_text, parse_mode="Markdown")
    await callback.answer()

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    print("🚀 Старт ИИ-бота...")
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

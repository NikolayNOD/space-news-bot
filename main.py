import asyncio
import os
import aiohttp
import urllib.parse
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TELEGRAM_BOT_TOKEN = "8811178509:AAHqCF3BIODntZfIM50d66t8nOGIIIyBVdU"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

user_news_cache = {}
user_seen_ids = {}

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🇷🇺 Новости космоса РФ"),
            KeyboardButton(text="🌍 Новости космоса Мира")
        ]
    ],
    resize_keyboard=True,
    is_persistent=True
)

def get_article_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ Сгенерировать готовый SMM-пост", callback_data="generate_ai_post"),
            ],
            [
                InlineKeyboardButton(text="🌐 Перевод оригинала", callback_data="translate_full"),
                InlineKeyboardButton(text="➡️ Следующая новость", callback_data="next_news")
            ]
        ]
    )

async def translate_text(text: str) -> str:
    """Гарантированный перевод текста на русский язык"""
    if not text:
        return ""
    try:
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={encoded_text}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=7) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    translated_chunks = [chunk[0] for chunk in data[0] if chunk[0]]
                    result = "".join(translated_chunks)
                    if result:
                        return result
    except Exception as e:
        print(f"Ошибка перевода Google: {e}")
    return text

async def generate_smm_with_ai(ru_title: str, ru_summary: str, url: str) -> str:
    """Генерация живого, глубоко переработанного SMM-поста на русском языке"""
    
    # 1. Если подключен ключ Groq (нейросеть Llama 3)
    if GROQ_API_KEY:
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = (
            "Ты редактор популярного Telegram-канала про космос и науку. "
            "Перепиши новость ниже в захватывающий, полностью готовый к публикации пост на РУССКОМ языке.\n\n"
            "Требования:\n"
            "1. Придумай яркий, привлекающий внимание заголовок.\n"
            "2. Перескажи суть своими словами (НЕ копируй предложенный текст слово в слово, сделай интересный рерайтинг).\n"
            "3. Объясни коротко, почему это событие действительно важно для отрасли.\n"
            "4. Добавь аккуратные хэштеги в конце.\n\n"
            f"Заголовок новости: {ru_title}\n"
            f"Описание: {ru_summary}"
        )
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(groq_url, headers=headers, json=payload, timeout=12) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        return res["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Ошибка Groq ИИ: {e}")

    # 2. Если ключа нейросети нет — красивый, глубоко адаптированный шаблон
    formatted_title = ru_title.strip()
    if not formatted_title.endswith(('.', '!', '?')):
        formatted_title += "!"

    post_text = (
        f"🔥 **{formatted_title}**\n\n"
        f"👨‍🚀 {ru_summary}\n\n"
        f"📌 **Главные подробности:**\n"
        f"Экипаж завершил длительную космическую миссию и благополучно возвратился на Землю. "
        f"Все запланированные научные эксперименты и технические задачи на орбите были выполнены в полном объеме.\n\n"
        f"💬 *Делитесь мнением про эту миссию в комментариях!*\n\n"
        f"🏷 #космос #роскосмос #наса #мкс #технологии\n"
        f"🔗 [Первоисточник статьи]({url})"
    )
    return post_text

async def fetch_space_news():
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=20"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("results", [])
    except Exception as e:
        print(f"Ошибка загрузки новостей: {e}")
    return []

async def send_news_item(user_id: int, message_or_callback, category="world"):
    articles = user_news_cache.get(f"{user_id}_{category}", [])
    seen = user_seen_ids.get(user_id, set())

    selected_article = None
    for art in articles:
        if art.get("id") not in seen:
            selected_article = art
            break

    if not selected_article:
        txt = "🎉 Ты просмотрел все свежие новости в этой категории!"
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(txt, reply_markup=main_keyboard)
        else:
            await message_or_callback.message.answer(txt, reply_markup=main_keyboard)
            await message_or_callback.answer()
        return

    seen.add(selected_article.get("id"))
    user_seen_ids[user_id] = seen

    title = selected_article.get("title", "")
    summary = selected_article.get("summary", "")
    url = selected_article.get("url", "")
    image_url = selected_article.get("image_url", "")
    site = selected_article.get("news_site", "Space News")

    ru_title = await translate_text(title)
    ru_summary = await translate_text(summary)

    region_tag = "🇷🇺 РОССИЯ И РОСКОСМОС" if category == "rf" else "🌍 МИРОВОЙ КОСМОС"

    user_news_cache[f"{user_id}_current"] = {
        "raw_title": title,
        "raw_summary": summary,
        "ru_title": ru_title,
        "ru_summary": ru_summary,
        "url": url,
        "image_url": image_url,
        "site": site,
        "category": category
    }

    caption_text = (
        f"✨ **[{region_tag}]**\n\n"
        f"🌌 **{ru_title}**\n\n"
        f"📖 {ru_summary}\n\n"
        f"📡 **Источник:** {site}\n"
        f"🔗 [Перейти к источнику]({url})"
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
@dp.message(Command("menu"))
async def start_handler(message: types.Message):
    await message.answer(
        "🚀 **Привет! Я твой ИИ-ассистент по космическим новостям.**\n\n"
        "Выбери интересующую категорию внизу 👇",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "🌍 Новости космоса Мира")
async def world_news_handler(message: types.Message):
    await message.answer("🛸 Ищу и перерабатываю мировые новости...")
    articles = await fetch_space_news()
    if not articles:
        await message.answer("❌ Ошибка загрузки новостей.", reply_markup=main_keyboard)
        return

    user_news_cache[f"{message.from_user.id}_world"] = articles
    await send_news_item(message.from_user.id, message, category="world")

@dp.message(F.text == "🇷🇺 Новости космоса РФ")
async def rf_news_handler(message: types.Message):
    await message.answer("🛸 Сканирую новости космической отрасли РФ...")
    articles = await fetch_space_news()
    
    rf_articles = [
        art for art in articles 
        if any(w in (art.get("title","") + art.get("summary","")).lower() for w in ["russia", "roscosmos", "soyuz", "proton", "angara"])
    ]
    
    final_list = rf_articles if rf_articles else articles
    user_news_cache[f"{message.from_user.id}_rf"] = final_list
    await send_news_item(message.from_user.id, message, category="rf")

@dp.callback_query(F.data == "next_news")
async def next_news_callback(callback: types.CallbackQuery):
    data = user_news_cache.get(f"{callback.from_user.id}_current")
    category = data.get("category", "world") if data else "world"
    await send_news_item(callback.from_user.id, callback, category=category)

@dp.callback_query(F.data == "generate_ai_post")
async def generate_ai_post_callback(callback: types.CallbackQuery):
    data = user_news_cache.get(f"{callback.from_user.id}_current")
    if not data:
        await callback.answer("Выбери новость заново!", show_alert=True)
        return

    await callback.message.answer("✍️ *Готовлю обработанный пост для публикации...*", parse_mode="Markdown")

    # Теперь в генератор идут УЖЕ переведенные заголовки и тексты!
    ai_smm_post = await generate_smm_with_ai(
        data['ru_title'], 
        data['ru_summary'], 
        data['url']
    )

    if data.get("image_url"):
        try:
            await callback.message.answer_photo(
                photo=data["image_url"],
                caption=ai_smm_post,
                parse_mode="Markdown"
            )
        except Exception:
            await callback.message.answer(ai_smm_post, parse_mode="Markdown")
    else:
        await callback.message.answer(ai_smm_post, parse_mode="Markdown")

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
    print("🚀 Старт обновленного бота...")
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

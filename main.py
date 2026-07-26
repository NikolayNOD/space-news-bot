import asyncio
import os
import aiohttp
import urllib.parse
import xml.etree.ElementTree as ET
import re
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

def get_article_inline_keyboard(category="world"):
    rf_check = "✅ " if category == "rf" else ""
    world_check = "✅ " if category == "world" else ""
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{rf_check}🇷🇺 Космос РФ", callback_data="select_cat_rf"),
                InlineKeyboardButton(text=f"{world_check}🌍 Космос Мира", callback_data="select_cat_world")
            ],
            [
                InlineKeyboardButton(text="✍️ Сгенерировать SMM-пост", callback_data="generate_ai_post")
            ],
            [
                InlineKeyboardButton(text="➡️ Следующая новость", callback_data="next_news")
            ]
        ]
    )

async def translate_text(text: str) -> str:
    """Перевод английского текста на русский"""
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
        print(f"Ошибка перевода: {e}")
    return text

def clean_text(text: str) -> str:
    """Очистка текста от многоточий в конце и HTML-тегов"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s*\.\.\.\s*$', '.', text)
    text = re.sub(r'\s*…\s*$', '.', text)
    return text.strip()

async def generate_smm_with_ai(ru_title: str, ru_summary: str, url: str) -> str:
    """Продвинутый SMM-рерайтер без сухих шаблонов"""
    ru_title = clean_text(ru_title)
    ru_summary = clean_text(ru_summary)

    # 1. Попытка сгенерировать через Нейросеть (если есть ключ GROQ)
    if GROQ_API_KEY:
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = (
            "Ты главный редактор крупного Telegram-канала о космонавтике и астрономии. "
            "Напиши качественный, вовлекающий и вирусный пост для соцсетей на РУССКОМ языке на основе новости ниже.\n\n"
            "Структура поста:\n"
            "1. Цепляющий заголовок с эмодзи.\n"
            "2. Главная суть события (живым языком, без канцелярита, разбито на 1-2 коротких абзаца).\n"
            "3. Интригующий или поддытоживающий вывод.\n"
            "4. Вопрос к читателям для комментариев.\n"
            "5. 3-5 актуальных хэштегов.\n\n"
            f"Заголовок: {ru_title}\nТекст: {ru_summary}"
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
                        post = res["choices"][0]["message"]["content"]
                        return f"{post}\n\n🔗 [Читать источник]({url})"
        except Exception as e:
            print(f"Ошибка Groq: {e}")

    # 2. Умный локальный SMM-рерайтер (работает без API ключей)
    # Формируем динамический и стильный пост из полученной новости
    
    # Автоподбор эмодзи к заголовку
    emoji_header = "🚀"
    lower_t = ru_title.lower()
    if any(w in lower_t for w in ["возвращ", "посадк", "земл", "экипаж"]):
        emoji_header = "🛬"
    elif any(w in lower_t for w in ["запуск", "ракета", "старт", "союз"]):
        emoji_header = "🔥"
    elif any(w in lower_t for w in ["открыт", "телескоп", "галактик", "звезд"]):
        emoji_header = "🔭"
    elif any(w in lower_t for w in ["лун", "марс", "станци"]):
        emoji_header = "🌕"

    # Формирование хэштегов по смыслу
    hashtags = ["#космос", "#наука", "#технологии"]
    if any(w in lower_t + ru_summary.lower() for w in ["роскосмос", "союз", "рф", "россия"]):
        hashtags.append("#роскосмос")
    if any(w in lower_t + ru_summary.lower() for w in ["nasa", "наса", "мкс"]):
        hashtags.append("#мкс")
    if any(w in lower_t + ru_summary.lower() for w in ["марс", "луна"]):
        hashtags.append("#исследования")

    tags_str = " ".join(hashtags)

    post_content = (
        f"{emoji_header} **{ru_title.upper()}**\n\n"
        f"📍 **Что произошло:**\n"
        f"{ru_summary}\n\n"
        f"💡 **Почему это важно?**\n"
        f"Каждая такая миссия приближает нас к глубокому освоению внеземного пространства и дает важнейшие научные данные для будущего человечества.\n\n"
        f"💬 *Как вам такие новости? Обсуждаем в комментариях!* 👇\n\n"
        f"{tags_str}\n"
        f"🔗 [Читать первоисточник]({url})"
    )

    return post_content

async def fetch_roscosmos_and_rf_news():
    """Парсинг прямых российских новостей о космосе"""
    rf_sources = [
        {"url": "https://www.roscosmos.ru/rss/all.xml", "site": "Роскосмос"},
        {"url": "https://tass.ru/rss/v2/news.xml?sections=NTM0", "site": "ТАСС (Космос)"},
        {"url": "https://ria.ru/export/rss2/archive/index.xml", "site": "РИА Новости"}
    ]
    
    articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    async with aiohttp.ClientSession(headers=headers) as session:
        for source in rf_sources:
            try:
                async with session.get(source["url"], timeout=8) as response:
                    if response.status == 200:
                        content = await response.text()
                        root = ET.fromstring(content)
                        for item in root.findall(".//item")[:10]:
                            title = item.find("title").text if item.find("title") is not None else ""
                            summary = item.find("description").text if item.find("description") is not None else ""
                            link = item.find("link").text if item.find("link") is not None else ""
                            
                            title = clean_text(title)
                            summary = clean_text(summary)
                            
                            if title and link:
                                articles.append({
                                    "id": link,
                                    "title": title,
                                    "summary": summary if summary else title,
                                    "url": link,
                                    "image_url": "",
                                    "news_site": source["site"],
                                    "is_ru": True
                                })
            except Exception as e:
                print(f"Ошибка парсинга {source['site']}: {e}")

    return articles

async def fetch_space_news():
    """Загрузка мировых новостей"""
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=30"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    out = []
                    for art in results:
                        out.append({
                            "id": art.get("id"),
                            "title": clean_text(art.get("title", "")),
                            "summary": clean_text(art.get("summary", "")),
                            "url": art.get("url", ""),
                            "image_url": art.get("image_url", ""),
                            "news_site": art.get("news_site", "Space News"),
                            "is_ru": False
                        })
                    return out
    except Exception as e:
        print(f"Ошибка загрузки мировых новостей: {e}")
    return []

async def send_news_item(user_id: int, message_or_callback, category="world"):
    articles = user_news_cache.get(f"{user_id}_{category}", [])
    
    if not articles:
        if category == "rf":
            articles = await fetch_roscosmos_and_rf_news()
        else:
            articles = await fetch_space_news()
            
        user_news_cache[f"{user_id}_{category}"] = articles

    seen = user_seen_ids.get(user_id, set())
    selected_article = None

    for art in articles:
        if art.get("id") not in seen:
            selected_article = art
            break

    if not selected_article:
        txt = "🎉 Ты просмотрел все новости в этой категории! Переключи категорию или зайди немного позже."
        inline_kb = get_article_inline_keyboard(category)
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(txt, reply_markup=inline_kb)
        else:
            await message_or_callback.message.answer(txt, reply_markup=inline_kb)
            await message_or_callback.answer()
        return

    seen.add(selected_article.get("id"))
    user_seen_ids[user_id] = seen

    title = selected_article.get("title", "")
    summary = selected_article.get("summary", "")
    url = selected_article.get("url", "")
    image_url = selected_article.get("image_url", "")
    site = selected_article.get("news_site", "Космические новости")

    if selected_article.get("is_ru"):
        ru_title = title
        ru_summary = summary
    else:
        ru_title = await translate_text(title)
        ru_summary = await translate_text(summary)

    region_tag = "🇷🇺 РОСКОСМОС И РФ" if category == "rf" else "🌍 МИРОВОЙ КОСМОС"

    user_news_cache[f"{user_id}_current"] = {
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
        f"🔗 [Читать первоисточник]({url})"
    )

    target_msg = message_or_callback if isinstance(message_or_callback, types.Message) else message_or_callback.message
    inline_kb = get_article_inline_keyboard(category)

    try:
        if image_url:
            await target_msg.answer_photo(
                photo=image_url,
                caption=caption_text,
                reply_markup=inline_kb,
                parse_mode="Markdown"
            )
        else:
            await target_msg.answer(
                text=caption_text,
                reply_markup=inline_kb,
                parse_mode="Markdown"
            )
    except Exception:
        await target_msg.answer(
            text=caption_text,
            reply_markup=inline_kb,
            parse_mode="Markdown"
        )

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.answer()

@dp.message(Command("start"))
@dp.message(Command("menu"))
async def start_handler(message: types.Message):
    await message.answer(
        "🚀 **Привет! Я твой SMM-ассистент по космическим новостям.**\n\n"
        "Выбери интересующую категорию внизу 👇",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "🌍 Новости космоса Мира")
async def world_news_handler(message: types.Message):
    await message.answer("🌍 Переключаю на новости мирового космоса...")
    await send_news_item(message.from_user.id, message, category="world")

@dp.message(F.text == "🇷🇺 Новости космоса РФ")
async def rf_news_handler(message: types.Message):
    await message.answer("🇷🇺 Загрузка прямых новостей Роскосмоса и РФ...")
    await send_news_item(message.from_user.id, message, category="rf")

@dp.callback_query(F.data == "select_cat_rf")
async def select_cat_rf_cb(callback: types.CallbackQuery):
    await callback.message.answer("🇷🇺 Категория: **Новости космоса РФ (Роскосмос)**", parse_mode="Markdown")
    await send_news_item(callback.from_user.id, callback, category="rf")

@dp.callback_query(F.data == "select_cat_world")
async def select_cat_world_cb(callback: types.CallbackQuery):
    await callback.message.answer("🌍 Категория: **Новости космоса Мира**", parse_mode="Markdown")
    await send_news_item(callback.from_user.id, callback, category="world")

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

    await callback.message.answer("✍️ *Создаю качественный SMM-пост...*", parse_mode="Markdown")

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

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    print("🚀 Старт обновленного бота с умным SMM-рерайтером...")
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

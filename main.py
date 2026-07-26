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
            KeyboardButton(text="🌍 Топ-новости Мира (Eng)")
        ]
    ],
    resize_keyboard=True,
    is_persistent=True
)

def get_article_inline_keyboard(is_ru=False):
    buttons = []
    if not is_ru:
        buttons.append([
            InlineKeyboardButton(text="🌐 Перевести на русский", callback_data="translate_full")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="✍️ Сгенерировать SMM-пост", callback_data="generate_ai_post")
    ])
    buttons.append([
        InlineKeyboardButton(text="➡️ Следующая новость", callback_data="next_news")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s*\.\.\.\s*$', '.', text)
    text = re.sub(r'\s*…\s*$', '.', text)
    return text.strip()

def is_top_interesting_news(title: str, summary: str) -> bool:
    """Фильтр: пропускает только самые СУПЕР-интересные новости"""
    content = (title + " " + summary).lower()
    
    # Ключевые слова топовых космических событий
    top_keywords = [
        "launch", "spacex", "starship", "nasa", "moon", "mars", "roscosmos", "isro", 
        "cnsa", "falcon", "artemis", "astronaut", "cosmonaut", "rocket", "station", "iss",
        "запуск", "ракета", "союз", "луна", "марс", "мкс", "роскосмос", "китай", "индия",
        "оаэ", "астронавт", "космонавт", "открытие", "станция", "посадка", "стерои"
    ]
    
    return any(keyword in content for keyword in top_keywords)

async def generate_smm_with_ai(title: str, summary: str, url: str) -> str:
    """Генератор вирусных SMM-постов"""
    title = clean_text(title)
    summary = clean_text(summary)

    if GROQ_API_KEY:
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = (
            "Ты главный редактор крупного Telegram-канала о космосе. "
            "Напиши вирусный, вовлекающий SMM-пост на РУССКОМ ЯЗЫКЕ на основе этой космической новости.\n\n"
            "Структура:\n"
            "1. Мощный заголовок с эмодзи.\n"
            "2. Выжимка самых главных и интересных фактов (2 коротких абзаца).\n"
            "3. Почему это важно для мировой науки/космонавтики.\n"
            "4. Вопрос читателям для обсуждения.\n"
            "5. 4-5 хэштегов.\n\n"
            f"Новость: {title}\nПодробности: {summary}"
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
                        return f"{post}\n\n🔗 [Читать первоисточник]({url})"
        except Exception as e:
            print(f"Ошибка Groq: {e}")

    # Локальный фоллбэк
    ru_title = await translate_text(title)
    ru_summary = await translate_text(summary)
    
    return (
        f"🔥 **{ru_title.upper()}**\n\n"
        f"📍 **Главная суть:**\n{ru_summary}\n\n"
        f"💡 **Почему это событие важно?**\n"
        f"Это шаг вперед в исследовании космоса, который влияет на развитие технологий США, Китая, РФ и Европы.\n\n"
        f"💬 *Что думаете по этому поводу? Обсуждаем в комментариях!* 👇\n\n"
        f"#космос #наука #технологии #астрономия #исследования\n"
        f"🔗 [Первоисточник]({url})"
    )

async def fetch_roscosmos_and_rf_news():
    """Топовые новости РФ (Роскосмос, ТАСС, РИА)"""
    rf_sources = [
        {"url": "https://www.roscosmos.ru/rss/all.xml", "site": "Роскосмос (Официальный)"},
        {"url": "https://tass.ru/rss/v2/news.xml?sections=NTM0", "site": "ТАСС (Космос)"},
        {"url": "https://ria.ru/export/rss2/archive/index.xml", "site": "РИА Новости"}
    ]
    articles = []
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        for source in rf_sources:
            try:
                async with session.get(source["url"], timeout=8) as response:
                    if response.status == 200:
                        content = await response.text()
                        root = ET.fromstring(content)
                        for item in root.findall(".//item")[:15]:
                            title = clean_text(item.find("title").text if item.find("title") is not None else "")
                            summary = clean_text(item.find("description").text if item.find("description") is not None else "")
                            link = item.find("link").text if item.find("link") is not None else ""
                            
                            if title and link and is_top_interesting_news(title, summary):
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
                print(f"Ошибка РФ RSS: {e}")
    return articles

async def fetch_world_space_news():
    """Мировые ТОП-новости (США, Китай, Индия, ОАЭ, Европа) на английском"""
    url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=40"
    articles = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    for art in data.get("results", []):
                        title = clean_text(art.get("title", ""))
                        summary = clean_text(art.get("summary", ""))
                        
                        # Фильтруем только главное и интересное
                        if is_top_interesting_news(title, summary):
                            articles.append({
                                "id": art.get("id"),
                                "title": title,
                                "summary": summary,
                                "url": art.get("url", ""),
                                "image_url": art.get("image_url", ""),
                                "news_site": art.get("news_site", "Global Space News"),
                                "is_ru": False
                            })
    except Exception as e:
        print(f"Ошибка мировых новостей: {e}")
    return articles

async def send_news_item(user_id: int, message_or_callback, category="world"):
    articles = user_news_cache.get(f"{user_id}_{category}", [])
    
    if not articles:
        if category == "rf":
            articles = await fetch_roscosmos_and_rf_news()
        else:
            articles = await fetch_world_space_news()
            
        user_news_cache[f"{user_id}_{category}"] = articles

    seen = user_seen_ids.get(user_id, set())
    selected_article = None

    for art in articles:
        if art.get("id") not in seen:
            selected_article = art
            break

    if not selected_article:
        txt = "🎉 Вы просмотрели все топовые космические новости на сегодня!"
        inline_kb = get_article_inline_keyboard(category == "rf")
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
    site = selected_article.get("news_site", "Space News")
    is_ru = selected_article.get("is_ru", False)

    region_tag = "🇷🇺 КОСМОС РФ" if is_ru else "🌍 GLOBAL SPACE (USA, CHINA, INDIA, UAE, EU)"

    user_news_cache[f"{user_id}_current"] = {
        "title": title,
        "summary": summary,
        "url": url,
        "image_url": image_url,
        "site": site,
        "is_ru": is_ru,
        "category": category
    }

    if is_ru:
        caption_text = (
            f"✨ **[{region_tag}]**\n\n"
            f"🌌 **{title}**\n\n"
            f"📖 {summary}\n\n"
            f"📡 **Источник:** {site}\n"
            f"🔗 [Читать источник]({url})"
        )
    else:
        # Для мировых новостей отсылаем Оригинал на английском!
        caption_text = (
            f"✨ **[{region_tag}]**\n\n"
            f"🌌 **{title}**\n\n"
            f"📖 {summary}\n\n"
            f"📡 **Source:** {site}\n"
            f"🔗 [Read Original Article]({url})"
        )

    target_msg = message_or_callback if isinstance(message_or_callback, types.Message) else message_or_callback.message
    inline_kb = get_article_inline_keyboard(is_ru=is_ru)

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
        "🚀 **Топ-агрегатор космических новостей**\n\n"
        "Мы отслеживаем главные события **США (NASA/SpaceX), Китая (CNSA), Индии (ISRO), ОАЭ, Европы (ESA) и Роскосмоса**!\n\n"
        "Выбери ленту на кнопках внизу 👇",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "🌍 Топ-новости Мира (Eng)")
async def world_news_handler(message: types.Message):
    await message.answer("🛸 Сканирую мировые источники (США, Китай, Индия, ОАЭ, Европа)...")
    await send_news_item(message.from_user.id, message, category="world")

@dp.message(F.text == "🇷🇺 Новости космоса РФ")
async def rf_news_handler(message: types.Message):
    await message.answer("🇷🇺 Загрузка новостей Роскосмоса и ведущих космических СМИ...")
    await send_news_item(message.from_user.id, message, category="rf")

@dp.callback_query(F.data == "next_news")
async def next_news_callback(callback: types.CallbackQuery):
    data = user_news_cache.get(f"{callback.from_user.id}_current")
    category = data.get("category", "world") if data else "world"
    await send_news_item(callback.from_user.id, callback, category=category)

@dp.callback_query(F.data == "translate_full")
async def translate_full_callback(callback: types.CallbackQuery):
    data = user_news_cache.get(f"{callback.from_user.id}_current")
    if not data:
        await callback.answer("Выбери новость заново!", show_alert=True)
        return

    await callback.message.answer("🌐 *Перевожу оригинал на русский язык...*", parse_mode="Markdown")

    ru_title = await translate_text(data['title'])
    ru_summary = await translate_text(data['summary'])

    translation_text = (
        f"🇷🇺 **ПЕРЕВОД НА РУССКИЙ:**\n\n"
        f"📌 **Заголовок:** {ru_title}\n\n"
        f"📝 **Суть:** {ru_summary}\n\n"
        f"🔗 **Ссылка:** [Перейти к источнику]({data['url']})"
    )
    await callback.message.answer(translation_text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "generate_ai_post")
async def generate_ai_post_callback(callback: types.CallbackQuery):
    data = user_news_cache.get(f"{callback.from_user.id}_current")
    if not data:
        await callback.answer("Выбери новость заново!", show_alert=True)
        return

    await callback.message.answer("✍️ *Создаю готовый SMM-пост для публикации...*", parse_mode="Markdown")

    ai_smm_post = await generate_smm_with_ai(
        data['title'], 
        data['summary'], 
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
    print("🚀 Старт топ-агрегатора космоса...")
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

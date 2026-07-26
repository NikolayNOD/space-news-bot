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
    """Очистка текста от HTML-тегов и обрывов на конце"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s*\.\.\.\s*$', '.', text)
    text = re.sub(r'\s*…\s*$', '.', text)
    return text.strip()

def is_strictly_space_news(title: str, summary: str) -> bool:
    """ЖЕСТКИЙ ФИЛЬТР: Пропускает ТОЛЬКО новости про космос"""
    content = (title + " " + summary).lower()
    
    space_keywords = [
        "космос", "роскосмос", "орбита", "ракета", "спутник", "мкс", "запуск", 
        "космонавт", "астронавт", "луна", "марс", "союз", "ангара", "главкосмос",
        "телескоп", "астрономия", "астероид", "гравитация", "ики ран", "астрофизик",
        "launch", "spacex", "starship", "nasa", "moon", "mars", "isro", 
        "cnsa", "falcon", "artemis", "astronaut", "cosmonaut", "rocket", "station", "iss", "esa"
    ]
    
    return any(keyword in content for keyword in space_keywords)

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
            "Ты главный редактор популярного Telegram-канала о космосе. "
            "Напиши крутой, яркий и вовлекающий SMM-пост на РУССКОМ ЯЗЫКЕ на основе этой космической новости.\n\n"
            "Требования к посту:\n"
            "1. Заголовок с эмодзи.\n"
            "2. Выжимка главных фактов без сложной терминологии (2 небольших абзаца).\n"
            "3. Интригующий вывод о значимости события.\n"
            "4. Вопрос к аудитории для обсуждения в комментариях.\n"
            "5. 4-5 актуальных хэштегов.\n\n"
            f"Заголовок новости: {title}\nТекст: {summary}"
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
            print(f"Ошибка Groq API: {e}")

    # Локальный запасной генератор
    ru_title = await translate_text(title)
    ru_summary = await translate_text(summary)
    
    return (
        f"🚀 **{ru_title.upper()}**\n\n"
        f"📍 **Главное к этому часу:**\n{ru_summary}\n\n"
        f"💡 **Почему это важно?**\n"
        f"Каждый такой шаг приближает нас к новым открытиям во Вселенной и освоению околоземного пространства.\n\n"
        f"💬 *Что думаете по этому поводу? Делитесь в комментариях!* 👇\n\n"
        f"#космос #наука #технологии #астрономия\n"
        f"🔗 [Читать первоисточник]({url})"
    )

async def fetch_roscosmos_and_rf_news():
    """Чистый парсинг ТОЛЬКО профильных космических источников РФ"""
    rf_sources = [
        {"url": "https://www.roscosmos.ru/rss/all.xml", "site": "Роскосмос (Официальный)"},
        {"url": "https://procosmos.ru/rss", "site": "Pro Cosmos"},
        {"url": "https://tass.ru/rss/v2/news.xml?sections=NTM1", "site": "ТАСС Наука"}
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
                        for item in root.findall(".//item")[:20]:
                            title = clean_text(item.find("title").text if item.find("title") is not None else "")
                            summary = clean_text(item.find("description").text if item.find("description") is not None else "")
                            link = item.find("link").text if item.find("link") is not None else ""
                            
                            # Строгий контроль тематики
                            if title and link and is_strictly_space_news(title, summary):
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

async def fetch_world_space_news():
    """Загрузка мировых космических новостей (США, Китай, Индия, ОАЭ, ЕКА)"""
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
                        
                        if is_strictly_space_news(title, summary):
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
        print(f"Ошибка загрузки мировых новостей: {e}")
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
        txt = "🎉 Вы просмотрели все актуальные космические новости в этом разделе!"
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

    region_tag = "🇷🇺 КОСМОС РФ" if is_ru else "🌍 GLOBAL SPACE NEWS"

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
            f"🔗 [Читать первоисточник]({url})"
        )
    else:
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
        "🚀 **Агрегатор космических новостей**\n\n"
        "Выбери нужный раздел на кнопках ниже 👇",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "🌍 Топ-новости Мира (Eng)")
async def world_news_handler(message: types.Message):
    await message.answer("🛸 Загружаю мировые космические новости...")
    await send_news_item(message.from_user.id, message, category="world")

@dp.message(F.text == "🇷🇺 Новости космоса РФ")
async def rf_news_handler(message: types.Message):
    await message.answer("🇷🇺 Загружаю профильные новости Роскосмоса и науки...")
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
        await callback.answer("Новость не найдена, выбери заново!", show_alert=True)
        return

    await callback.message.answer("🌐 *Перевожу на русский...*", parse_mode="Markdown")

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
        await callback.answer("Новость не найдена, выбери заново!", show_alert=True)
        return

    await callback.message.answer("✍️ *Формирую SMM-пост...*", parse_mode="Markdown")

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
    print("🚀 Старт очищенного космического бота...")
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

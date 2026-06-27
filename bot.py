import asyncio
import json
import re
import random
import time
import os
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== НАСТРОЙКИ =====
TELEGRAM_TOKEN = "8863731938:AAHAAPlB8OWW36ikxOwZ7h834EytbvY34P0"
GROQ_API_KEY = "gsk_5jfYtMw1oXAYw9fwtLfWgdyb3FYfweblrPK1I1UHKvtVY7iFRrv"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

MODEL_NAME = "llama-3.1-8b-instant"
print(f"🔧 Модель Groq: {MODEL_NAME}")

def clean_json(text):
    if not text:
        return ""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = re.sub(r'`\s*', '', text)
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and start < end:
        text = text[start:end+1]
    else:
        return ""
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clean_rp_text(text):
    if not text:
        return ""
    text = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def format_rp_response(text):
    if not text:
        return "*Мастер молчит...*"
    text = clean_rp_text(text)
    lines = text.split('\n')
    formatted = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('*') or line.startswith('-') or line.startswith('~'):
            formatted.append(line)
            continue
        if any(word in line for word in ['говорит', 'сказал', 'спросил', 'кричит', 'шепчет', 'отвечает']):
            formatted.append(f"- {line}")
        else:
            formatted.append(f"*{line}*")
    if not formatted or len(formatted) == 1:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        formatted = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if any(word in sent for word in ['говорит', 'сказал', 'спросил', 'кричит', 'шепчет', 'отвечает']):
                formatted.append(f"- {sent}")
            else:
                formatted.append(f"*{sent}*")
    if not formatted:
        return "*Мастер молчит...*"
    return '\n'.join(formatted)

def ask_ai(prompt, retries=3):
    if not GROQ_API_KEY:
        return None
    for attempt in range(retries):
        try:
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": """Ты - Мастер RP. Отвечай в формате:
*действие*
- речь

Правила:
1. Каждое действие начинай с *
2. Каждую реплику начинай с -
3. Каждое действие и реплика - с новой строки
4. Используй ТОЛЬКО русский язык
5. НЕ используй китайские символы
6. НЕ предлагай варианты действий"""},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.9,
                "max_tokens": 600,
                "top_p": 0.95
            }
            response = requests.post(GROQ_URL, headers=GROQ_HEADERS, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
        except:
            pass
        if attempt < retries - 1:
            time.sleep(2)
    return None

def log_message(user_id, username, text, direction="IN"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*70}")
    print(f"{'📩 ВХОДЯЩЕЕ' if direction == 'IN' else '📤 ИСХОДЯЩЕЕ'} [{timestamp}] @{username}")
    print(f"📝 {text}")
    print(f"{'='*70}")

def log_error(error, context=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*70}")
    print(f"❌ [{timestamp}] ОШИБКА: {context}")
    print(f"📝 {error}")
    print(f"{'='*70}")

def log_action(action, details=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*70}")
    print(f"🔧 [{timestamp}] {action}")
    if details:
        print(f"📌 {details}")
    print(f"{'='*70}")

games = {}

def load_save(user_id):
    filename = f"save_{user_id}.json"
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "без_ника"
    log_message(user_id, username, "/start", "IN")
    keyboard = [
        [InlineKeyboardButton("🌟 Новая история", callback_data="new_game")],
        [InlineKeyboardButton("📖 Продолжить", callback_data="continue_game")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    saved_text = "💾 Есть сохранение!" if load_save(user_id) else ""
    response = (
        f"🎭 Добро пожаловать в мир ролевых игр!\n\n"
        f"⚡ **Бот работает на Groq AI**\n"
        f"• 30-50 запросов в минуту (БЕСПЛАТНО)\n"
        f"• Молниеносная скорость\n"
        f"{saved_text}\n\n"
        f"Выбери действие:"
    )
    await update.message.reply_text(response, reply_markup=reply_markup)

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "без_ника"
    log_message(user_id, username, "/new", "IN")
    if user_id in games:
        del games[user_id]
    filename = f"save_{user_id}.json"
    if os.path.exists(filename):
        os.remove(filename)
        log_action(f"Удалено сохранение для {username}", f"Файл: {filename}")
    response = (
        "🌟 Создаем новую историю!\n\n"
        "Опиши сценарий:\n"
        "• Где происходит действие?\n"
        "• Кто твой персонаж?\n"
        "• Какая атмосфера?\n\n"
        "Примеры:\n"
        "👉 Летний лагерь, я приехал на смену\n"
        "👉 Новая школа, первый день\n"
        "👉 Зима, война викингов\n\n"
        "Напиши свой сценарий!"
    )
    await update.message.reply_text(response)
    context.user_data['state'] = 'setting_world'

async def load_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "без_ника"
    log_message(user_id, username, "/load", "IN")
    saved_game = load_save(user_id)
    if saved_game:
        games[user_id] = saved_game
        log_action(f"Загружено сохранение для {username}", f"ID: {user_id}")
        char = saved_game.get('character', {})
        world = saved_game.get('world', {})
        response = (
            f"💾 **Игра загружена!**\n\n"
            f"🌍 Мир: {world.get('name', 'Неизвестно')}\n"
            f"📛 Персонаж: {char.get('name', 'Неизвестно')}\n"
            f"📍 Место: {char.get('location', 'Неизвестно')}\n\n"
            f"Можешь продолжать игру!"
        )
        await update.message.reply_text(response)
        context.user_data['state'] = 'rp_mode'
    else:
        await update.message.reply_text("❌ Нет сохранённой игры!")

async def save_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "без_ника"
    log_message(user_id, username, "/save", "IN")
    game = games.get(user_id)
    if not game:
        await update.message.reply_text("❌ Нет игры для сохранения!")
        return
    try:
        filename = f"save_{user_id}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(game, f, ensure_ascii=False, indent=2)
        log_action(f"Сохранение игры для {username}", f"Файл: {filename}")
        await update.message.reply_text("✅ Игра сохранена!")
    except Exception as e:
        log_error(e, f"Ошибка сохранения для {username}")
        await update.message.reply_text(f"❌ Ошибка сохранения: {e}")

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "без_ника"
    log_message(user_id, username, "/roll", "IN")
    game = games.get(user_id)
    if not game:
        saved_game = load_save(user_id)
        if saved_game:
            games[user_id] = saved_game
            game = games[user_id]
            await update.message.reply_text("💾 Загружено сохранение!")
        else:
            await update.message.reply_text("❌ Создай историю! /start")
            return
    roll_result = random.randint(1, 20)
    char = game.get('character', {})
    char_name = char.get('name', 'Герой')
    if roll_result >= 20:
        result = "💥 КРИТИЧЕСКИЙ УСПЕХ!"
    elif roll_result >= 15:
        result = "✅ Успех!"
    elif roll_result >= 10:
        result = "📊 Нормально"
    elif roll_result >= 5:
        result = "⚠️ Неудача"
    else:
        result = "💀 КРИТИЧЕСКАЯ НЕУДАЧА!"
    response = f"🎲 {char_name} бросает кубик...\n\nРезультат: {roll_result} (d20)\n{result}"
    await update.message.reply_text(response)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "без_ника"
    log_message(user_id, username, "/status", "IN")
    game = games.get(user_id)
    if not game:
        saved_game = load_save(user_id)
        if saved_game:
            games[user_id] = saved_game
            game = games[user_id]
            await update.message.reply_text("💾 Загружено сохранение!")
        else:
            await update.message.reply_text("❌ Создай историю! /start")
            return
    char = game.get('character', {})
    world = game.get('world', {})
    response = (
        f"📊 **Твой персонаж**\n\n"
        f"📛 Имя: {char.get('name', 'Неизвестно')}\n"
        f"🎂 Возраст: {char.get('age', '?')} лет\n"
        f"💭 Характер: {char.get('personality', 'Неизвестно')}\n"
        f"🎨 Внешность: {char.get('appearance', 'Неизвестно')}\n"
        f"📍 Место: {char.get('location', 'Неизвестно')}\n"
        f"🌍 Мир: {world.get('name', 'Неизвестно')}"
    )
    await update.message.reply_text(response)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    username = query.from_user.username or "без_ника"
    data = query.data
    if data == "new_game":
        await query.edit_message_text("🌟 Опиши свой сценарий:")
        context.user_data['state'] = 'setting_world'
    elif data == "continue_game":
        saved_game = load_save(user_id)
        if saved_game:
            games[user_id] = saved_game
            log_action(f"Загружено сохранение для {username}", f"ID: {user_id}")
            await start_rp(query, user_id)
        else:
            await query.edit_message_text("❌ Нет сохранённой игры! Создай новую.")
    elif data == "help":
        guide = (
            "🎭 **Правила RP**\n\n"
            "*действие* — описание действия\n"
            "Пример: *подошел ближе и улыбнулся*\n\n"
            "- речь — диалог персонажа\n"
            "Пример: - Привет! Как дела?\n\n"
            "~мысли~ — внутренние переживания\n"
            "Пример: ~Как же я волнуюсь...~\n\n"
            "// текст — OOC (выход из роли)\n"
            "Пример: // Может, пойдем в кафе?\n\n"
            "💡 **Бот отвечает только текстом**\n"
            "Просто продолжай диалог!\n\n"
            "📌 **Команды:**\n"
            "/start - Главное меню\n"
            "/new - Новая игра\n"
            "/load - Загрузить сохранение\n"
            "/save - Сохранить игру\n"
            "/roll - Бросить кубик\n"
            "/status - Информация о персонаже"
        )
        await query.edit_message_text(guide)
    elif data == "ready_to_start":
        guide = (
            "🎭 **Начинаем отыгровку!**\n\n"
            "📌 Формат:\n"
            "*действие*\n"
            "- речь\n\n"
            "⚡ **Без кнопок — просто диалог!**\n"
            "Пиши свои действия и реплики в чат.\n\n"
            "Начинай! 🚀"
        )
        await query.edit_message_text(guide)
        context.user_data['state'] = 'rp_mode'

async def start_rp(query, user_id):
    game = games.get(user_id)
    if not game:
        await query.edit_message_text("❌ Ошибка! Игра не найдена.")
        return
    char = game.get('character', {})
    world = game.get('world', {})
    history = game.get('history', [])
    if not history:
        prompt = f"""Ты - Мастер RP в мире: {world['name']}
Персонаж: {char.get('name', 'Герой')}, {char.get('age', '?')} лет
Характер: {char.get('personality', 'Обычный')}
Напиши вступление (3-4 предложения) в строгом формате:
*действие*
- речь
*действие*
- речь
Используй ТОЛЬКО русский язык. НЕ используй игровые термины. НЕ предлагай варианты действий. НЕ используй английские слова."""
        try:
            response_text = ask_ai(prompt)
            if response_text:
                scene = format_rp_response(response_text)
            else:
                scene = "*огляделся по сторонам*\n- Здесь так интересно!"
            game['history'] = [scene]
        except Exception as e:
            log_error(e, "Ошибка вступления")
            scene = "*огляделся по сторонам*\n- Здесь так интересно!"
            game['history'] = [scene]
    else:
        scene = history[-1]
    await query.edit_message_text(f"📖 {scene}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "без_ника"
    text = update.message.text
    log_message(user_id, username, text, "IN")
    state = context.user_data.get('state')
    if text.strip().startswith('//'):
        await update.message.reply_text(f"💬 [OOC] {text[2:].strip()}")
        return
    if state == 'setting_world':
        await create_world(update, user_id, text, context)
    elif state == 'creating_character':
        await create_character(update, user_id, text, context)
    elif state == 'rp_mode':
        await process_rp_message(update, user_id, text)
    else:
        if user_id in games and games[user_id]:
            await process_rp_message(update, user_id, text)
        else:
            saved_game = load_save(user_id)
            if saved_game:
                games[user_id] = saved_game
                await update.message.reply_text("💾 Загружено сохранение!")
                context.user_data['state'] = 'rp_mode'
                await process_rp_message(update, user_id, text)
            else:
                await update.message.reply_text("❌ Создай историю командой /start!")

async def create_world(update, user_id, description, context):
    username = update.effective_user.username or "без_ника"
    log_action(f"Создание мира для {username}", f"Описание: {description[:100]}...")
    await update.message.reply_text("🌍 Создаю мир...")
    prompt = f"""Создай мир для RP по описанию: {description}
Ответ ТОЛЬКО в формате JSON:
{{
    "name": "Название места",
    "genre": "Жанр",
    "description": "Описание (2 предложения)",
    "locations": ["Место 1", "Место 2", "Место 3"]
}}
Используй ТОЛЬКО русский язык. НЕ используй игровые термины и английские слова."""
    try:
        response_text = ask_ai(prompt)
        if not response_text:
            await update.message.reply_text("❌ Ошибка. Попробуй ещё раз.")
            return
        clean_text = clean_json(response_text)
        if not clean_text:
            await update.message.reply_text("❌ Ошибка парсинга JSON. Попробуй ещё раз.")
            return
        world = json.loads(clean_text)
        games[user_id] = {'world': world, 'character': None, 'history': []}
        response = (
            f"🌍 **Мир создан!**\n\n"
            f"📛 {world['name']}\n"
            f"🎭 {world['genre']}\n"
            f"📖 {world['description']}\n"
            f"📍 {', '.join(world['locations'])}\n\n"
            f"👤 **Теперь создай персонажа!**\n\n"
            f"Опиши его:\n"
            f"• Имя и возраст\n"
            f"• Внешность\n"
            f"• Характер\n\n"
            f"Пример: Анна, 17 лет, высокая брюнетка\n\n"
            f"Напиши описание:"
        )
        await update.message.reply_text(response)
        context.user_data['state'] = 'creating_character'
    except Exception as e:
        log_error(e, f"Ошибка создания мира для {username}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}\n\nПопробуй описать понятнее.")

async def create_character(update, user_id, description, context):
    username = update.effective_user.username or "без_ника"
    log_action(f"Создание персонажа для {username}", f"Описание: {description[:100]}...")
    game = games.get(user_id)
    if not game:
        await update.message.reply_text("❌ Сначала создай мир!")
        return
    await update.message.reply_text("🧙 Создаю персонажа...")
    world = game['world']
    prompt = f"""Создай RP персонажа для мира "{world['name']}".
Описание: {description}
Ответ ТОЛЬКО в формате JSON:
{{
    "name": "Имя",
    "age": "Возраст",
    "gender": "Пол",
    "personality": "Характер (2-3 слова)",
    "appearance": "Внешность (кратко)",
    "interests": ["Интерес 1", "Интерес 2"]
}}
Используй ТОЛЬКО русский язык. НЕ используй игровые термины и английские слова."""
    try:
        response_text = ask_ai(prompt)
        if not response_text:
            await update.message.reply_text("❌ Ошибка. Попробуй ещё раз.")
            return
        clean_text = clean_json(response_text)
        if not clean_text:
            await update.message.reply_text("❌ Ошибка парсинга JSON. Попробуй ещё раз.")
            return
        char = json.loads(clean_text)
        char['location'] = world['locations'][0] if world.get('locations') else 'Город'
        game['character'] = char
        intro_prompt = f"""Ты - Мастер RP в мире: {world['name']}
Персонаж: {char['name']}, {char['age']} лет
Характер: {char['personality']}
Напиши короткое вступление (2-3 предложения) в строгом формате:
*действие*
- речь"""
        intro_response = ask_ai(intro_prompt)
        if intro_response:
            intro = format_rp_response(intro_response)
        else:
            intro = "*огляделся по сторонам*\n- Интересно, что здесь будет?"
        game['history'] = [intro]
        response = (
            f"🎉 **Персонаж создан!**\n\n"
            f"📛 {char['name']}\n"
            f"🎂 {char['age']} лет\n"
            f"👤 {char['gender']}\n"
            f"💭 {char['personality']}\n"
            f"🎨 {char['appearance']}\n\n"
            f"📖 {intro}\n\n"
            f"🚀 Пиши в чат — и история продолжится!"
        )
        await update.message.reply_text(response)
        context.user_data['state'] = 'rp_mode'
    except Exception as e:
        log_error(e, f"Ошибка создания персонажа для {username}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def process_rp_message(update, user_id, text):
    username = update.effective_user.username or "без_ника"
    log_action(f"RP от {username}", f"Текст: {text[:100]}...")
    game = games.get(user_id)
    if not game:
        saved_game = load_save(user_id)
        if saved_game:
            games[user_id] = saved_game
            game = games[user_id]
            await update.message.reply_text("💾 Загружено сохранение!")
        else:
            await update.message.reply_text("❌ Создай историю! /start")
            return
    await update.message.reply_text("⏳ Думаю...")
    char = game.get('character', {})
    world = game.get('world', {})
    has_ooc = '//' in text
    if has_ooc:
        parts = text.split('//')
        rp_part = parts[0].strip()
        ooc_part = parts[1].strip() if len(parts) > 1 else ""
    else:
        rp_part = text
        ooc_part = ""
    prompt = f"""Ты - Мастер RP в мире: {world['name']}
Персонаж: {char.get('name', 'Герой')}
Действие: {rp_part}
Опиши реакцию мира в строгом формате:
*действие*
- речь
*действие*
- речь
Ответь кратко (3-5 предложений).
Используй ТОЛЬКО русский язык. НЕ используй игровые термины. НЕ используй английские слова. НЕ предлагай варианты действий — просто продолжай сцену."""
    try:
        response_text = ask_ai(prompt)
        if not response_text:
            await update.message.reply_text("❌ Ошибка. Попробуй ещё раз.")
            return
        formatted = format_rp_response(response_text)
        if ooc_part:
            formatted += f"\n\n💬 [OOC] {ooc_part}"
        game['history'] = game.get('history', []) + [formatted]
        await update.message.reply_text(formatted)
    except Exception as e:
        log_error(e, f"Ошибка RP от {username}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

def main():
    if not GROQ_API_KEY:
        print("❌ Ошибка: Нет ключа Groq!")
        return
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_game))
    app.add_handler(CommandHandler("load", load_game))
    app.add_handler(CommandHandler("save", save_game))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("=" * 70)
    print("🎭 RP-бот на GROQ AI запущен!")
    print(f"🔧 Модель: {MODEL_NAME}")
    print("⚡ Лимит: 30-50 запросов в минуту (БЕСПЛАТНО)")
    print("📋 Команды: /start, /new, /load, /save, /roll, /status")
    print("💬 Только русский язык, без кнопок")
    print("=" * 70)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

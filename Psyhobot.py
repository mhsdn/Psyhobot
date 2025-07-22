import json
import os
import logging
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Загружаем переменные окружения из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

USER_DATA_FILE = "user_data.json"

def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Вопросы и варианты ответов для диагностики
questions = [
    "Как часто вы испытываете мало интереса или удовольствия от занятий, которые обычно доставляют радость?",
    "Как часто вы чувствуете себя усталым или без сил?",
    "Как часто вам трудно засыпать или слишком рано просыпаться?",
    "Как часто вы ощущаете, что всё в жизни теряет смысл?",
    "Как часто вы чувствуете себя нервным или беспокойным?",
    "Как часто вы чувствуете себя беспомощным или одиноким?"
]

answer_options = ["Никогда", "Несколько дней", "Более половины времени", "Практически каждый день"]

scores_map = {"Никогда": 0, "Несколько дней": 1, "Более половины времени": 2, "Практически каждый день": 3}

user_answers = {}

# --- Функции обработки команд и логики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    name = user_data.get(str(user_id), {}).get("name", "друг")

    keyboard = [
        [KeyboardButton("📝 Диагностика"), KeyboardButton("📔 Дневник настроения")],
        [KeyboardButton("🧘‍♂️ Релаксация"), KeyboardButton("💬 Цитаты")],
        [KeyboardButton("⏰ Напоминания"), KeyboardButton("🎯 Цели")],
        [KeyboardButton("❓ FAQ"), KeyboardButton("🚨 Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"Привет, {name}! Я твой личный психолог-бот.\nВыбери одну из опций в меню ниже:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Вот что я могу сделать:\n"
        "- Провести экспресс-диагностику состояния\n"
        "- Отслеживать твой прогресс\n"
        "- Сохранять твои баллы\n"
        "- Показывать график изменений\n"
        "- Вести дневник настроения\n"
        "- Подсказывать техники релаксации\n"
        "- Мотивировать цитатами\n"
        "- Устанавливать напоминания\n"
        "- Устанавливать имя: /setname Иван\n"
        "- Начать диагностику: /diagnosis\n\n"
        "Или воспользуйся меню кнопок."
    )

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = " ".join(context.args)

    if name:
        user_data = load_user_data()
        if str(user_id) not in user_data:
            user_data[str(user_id)] = {}
        user_data[str(user_id)]["name"] = name
        save_user_data(user_data)
        await update.message.reply_text(f"Приятно познакомиться, {name}!")
    else:
        await update.message.reply_text("Пожалуйста, укажи своё имя после команды, например: /setname Иван")

# --- Диагностика ---

async def start_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answers[user_id] = []
    await ask_question(update, context, user_id, 0)

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, question_number: int):
    if question_number < len(questions):
        question = questions[question_number]
        keyboard = [
            [InlineKeyboardButton(option, callback_data=f"answer_{user_id}_{question_number}_{option}")]
            for option in answer_options
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text(question, reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.message.reply_text(question, reply_markup=reply_markup)
    else:
        await evaluate_answers(update, context, user_id)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_parts = query.data.split("_")
    user_id = int(data_parts[1])
    question_number = int(data_parts[2])
    answer = "_".join(data_parts[3:])

    user_answers[user_id].append(answer)

    if question_number + 1 < len(questions):
        await ask_question(update, context, user_id, question_number + 1)
    else:
        await evaluate_answers(update, context, user_id)

async def evaluate_answers(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    total_score = sum(scores_map[answer] for answer in user_answers[user_id])

    if total_score <= 5:
        result = "Ваше состояние в порядке."
    elif 6 <= total_score <= 10:
        result = "Есть признаки стресса. Попробуйте отдохнуть."
    elif 11 <= total_score <= 15:
        result = "Возможно умеренная депрессия. Подумайте о разговоре с психологом."
    else:
        result = "Вы можете испытывать тяжёлую депрессию. Рекомендуется обратиться за помощью."

    user_data = load_user_data()
    history = user_data.get(str(user_id), {}).get("history", [])
    history.append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": total_score
    })
    user_data[str(user_id)] = {"history": history, **user_data.get(str(user_id), {})}
    save_user_data(user_data)

    await generate_progress_graph(user_id, history)

    await update.callback_query.message.edit_text(
        f"Ваши результаты:\n\nОбщий балл: {total_score}\n\n{result}\n\nВот ваш прогресс:"
    )
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(f"progress_{user_id}.png", "rb"))

async def generate_progress_graph(user_id: int, history: list):
    scores = [entry["score"] for entry in history]
    dates = [entry["date"] for entry in history]

    plt.figure(figsize=(8, 6))
    plt.plot(dates, scores, marker='o', linestyle='-', color='blue')
    plt.title(f"Прогресс пользователя {user_id}")
    plt.xlabel("Дата")
    plt.ylabel("Баллы")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"progress_{user_id}.png")
    plt.close()

# --- Дневник настроения ---

async def mood_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пожалуйста, опишите, как вы себя чувствуете сегодня.")

async def mood_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mood_text = update.message.text

    user_data = load_user_data()
    mood_history = user_data.get(str(user_id), {}).get("mood_history", [])
    mood_history.append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mood": mood_text
    })
    user_data[str(user_id)] = {"mood_history": mood_history, **user_data.get(str(user_id), {})}
    save_user_data(user_data)

    await update.message.reply_text("Спасибо, ваш дневник настроения обновлен!")

# --- Релаксация ---

relax_text = (
    "Техника релаксации:\n"
    "1. Найдите спокойное место.\n"
    "2. Закройте глаза и глубоко вдохните.\n"
    "3. Медленно выдыхайте, расслабляя мышцы.\n"
    "4. Повторите несколько раз.\n"
    "5. Попробуйте сосредоточиться на ощущениях тела."
)

async def relax(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(relax_text)

# --- Цитаты ---

quotes = [
    "Жизнь — это 10% того, что с вами происходит, и 90% того, как вы на это реагируете. — Чарльз Р. Свиндолл",
    "Счастье не в том, чтобы иметь всё, а в умении радоваться тому, что есть. — Конфуций",
    "Не бойтесь идти медленно, бойтесь стоять на месте.",
    "Каждый день — новый шанс изменить свою жизнь."
]

import random

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(quotes))

# --- Напоминания ---

async def reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /reminder <минуты> <сообщение>")
        return
    try:
        minutes = int(args[0])
        message = " ".join(args[1:])
        await update.message.reply_text(f"Напоминание установлено через {minutes} минут.")
    except ValueError:
        await update.message.reply_text("Пожалуйста, укажите время в минутах (целым числом).")
        return

    # Отложенный вызов через job queue
    context.job_queue.run_once(reminder_callback, minutes * 60, data=(update.effective_chat.id, message))

async def reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    chat_id, message = context.job.data
    await context.bot.send_message(chat_id=chat_id, text=f"Напоминание: {message}")

# --- FAQ ---

faq_text = (
    "Часто задаваемые вопросы:\n"
    "1. Как установить имя? /setname Иван\n"
    "2. Как начать диагностику? /diagnosis\n"
    "3. Как вести дневник настроения? Просто напишите его после выбора меню.\n"
    "4. Как установить напоминание? /reminder <минуты> <сообщение>"
)

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(faq_text)

# --- Экстренная помощь ---

help_text = (
    "Если вам нужна экстренная помощь, обратитесь по этим номерам:\n"
    "Телефон доверия: 8-800-2000-122\n"
    "Психологическая помощь: 112\n"
    "В критической ситуации звоните 103."
)

async def helpme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(help_text)

# --- Обработка выбора из меню ---

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == """📝"""

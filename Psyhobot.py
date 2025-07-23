import json
import os
import logging
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv
import random

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

# Загрузка .env переменных
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
USER_DATA_FILE = "user_data.json"

# --- Данные и словари ---
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

# --- Работа с файлами пользователя ---
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- Команды ---
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
        "- /setname Иван — установить имя\n"
        "- /diagnosis — начать диагностику\n"
        "- /reminder 5 Пить воду — напоминание\n"
        "- Просто напиши, чтобы добавить в дневник настроения"
    )

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = " ".join(context.args)
    if not name:
        await update.message.reply_text("Укажи имя после команды: /setname Иван")
        return

    user_data = load_user_data()
    user_data.setdefault(str(user_id), {})["name"] = name
    save_user_data(user_data)
    await update.message.reply_text(f"Приятно познакомиться, {name}!")

# --- Диагностика ---
async def start_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answers[user_id] = []
    await ask_question(update, context, user_id, 0)

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, question_number: int):
    if question_number < len(questions):
        keyboard = [
            [InlineKeyboardButton(opt, callback_data=f"answer_{user_id}_{question_number}_{opt}")]
            for opt in answer_options
        ]
        markup = InlineKeyboardMarkup(keyboard)
        question = questions[question_number]
        if update.message:
            await update.message.reply_text(question, reply_markup=markup)
        elif update.callback_query:
            await update.callback_query.message.reply_text(question, reply_markup=markup)
    else:
        await evaluate_answers(update, context, user_id)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, uid, qn, *ans_parts = query.data.split("_")
    user_id = int(uid)
    question_number = int(qn)
    answer = "_".join(ans_parts)

    user_answers[user_id].append(answer)

    if question_number + 1 < len(questions):
        await ask_question(update, context, user_id, question_number + 1)
    else:
        await evaluate_answers(update, context, user_id)

async def evaluate_answers(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    total = sum(scores_map[a] for a in user_answers[user_id])
    if total <= 5:
        result = "Ваше состояние в порядке."
    elif total <= 10:
        result = "Есть признаки стресса. Попробуйте отдохнуть."
    elif total <= 15:
        result = "Возможно умеренная депрессия. Подумайте о разговоре с психологом."
    else:
        result = "Вы можете испытывать тяжёлую депрессию. Обратитесь за помощью."

    user_data = load_user_data()
    history = user_data.get(str(user_id), {}).get("history", [])
    history.append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "score": total})
    user_data[str(user_id)] = {"history": history, **user_data.get(str(user_id), {})}
    save_user_data(user_data)

    await generate_progress_graph(user_id, history)

    await update.callback_query.message.edit_text(
        f"Ваш результат: {total}\n\n{result}\n\nВот ваш прогресс:"
    )
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(f"progress_{user_id}.png", "rb"))

async def generate_progress_graph(user_id, history):
    dates = [entry["date"] for entry in history]
    scores = [entry["score"] for entry in history]

    plt.figure(figsize=(8, 6))
    plt.plot(dates, scores, marker='o', color='blue')
    plt.title("Прогресс состояния")
    plt.xlabel("Дата")
    plt.ylabel("Баллы")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(True)
    plt.savefig(f"progress_{user_id}.png")
    plt.close()

# --- Дневник ---
async def mood_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Опиши, как ты себя чувствуешь.")

async def mood_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    user_data = load_user_data()
    mood_history = user_data.get(str(user_id), {}).get("mood_history", [])
    mood_history.append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "mood": text})
    user_data[str(user_id)] = {"mood_history": mood_history, **user_data.get(str(user_id), {})}
    save_user_data(user_data)

    await update.message.reply_text("Спасибо! Запись добавлена в дневник настроения.")

# --- Релаксация ---
relax_text = (
    "Техника релаксации:\n"
    "1. Найдите спокойное место.\n"
    "2. Закройте глаза и глубоко вдохните.\n"
    "3. Медленно выдохните, расслабляя тело.\n"
    "4. Повторите 5 раз.\n"
    "5. Почувствуйте спокойствие."
)

async def relax(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(relax_text)

# --- Цитаты ---
quotes = [
    "Счастье — это когда то, что ты думаешь, говоришь и делаешь — в гармонии. — Махатма Ганди",
    "Ты сильнее, чем тебе кажется.",
    "Каждый день — шанс начать заново.",
    "Ты — главный герой своей жизни, а не жертва."
]

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
        msg = " ".join(args[1:])
        await update.message.reply_text(f"Напоминание установлено через {minutes} мин.")
        context.job_queue.run_once(reminder_callback, minutes * 60, data=(update.effective_chat.id, msg))
    except ValueError:
        await update.message.reply_text("Пожалуйста, укажите целое число минут.")

async def reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    chat_id, msg = context.job.data
    await context.bot.send_message(chat_id=chat_id, text=f"🔔 Напоминание: {msg}")

# --- FAQ ---
faq_text = (
    "Часто задаваемые вопросы:\n"
    "1. Как установить имя? /setname Иван\n"
    "2. Как начать диагностику? /diagnosis\n"
    "3. Как вести дневник? Просто напишите текст.\n"
    "4. Как установить напоминание? /reminder 10 Пить воду"
)

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(faq_text)

# --- Экстренная помощь ---
help_text = (
    "🚨 Экстренная помощь:\n"
    "📞 Телефон доверия: 8-800-2000-122\n"
    "📞 Психологическая помощь: 112\n"
    "📞 В экстренных случаях звоните: 103"
)

async def helpme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(help_text)

# --- Меню кнопок ---
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📝 Диагностика":
        await start_diagnosis(update, context)
    elif text == "📔 Дневник настроения":
        await mood_start(update, context)
    elif text == "🧘‍♂️ Релаксация":
        await relax(update, context)
    elif text == "💬 Цитаты":
        await quote(update, context)
    elif text == "⏰ Напоминания":
        await update.message.reply_text("Установи напоминание командой: /reminder <минуты> <текст>")
    elif text == "🎯 Цели":
        await update.message.reply_text("Функционал целей в разработке.")
    elif text == "❓ FAQ":
        await faq(update, context)
    elif text == "🚨 Помощь":
        await helpme(update, context)
    else:
        await mood_save(update, context)

# --- Запуск приложения ---
def main():
    print("TOKEN:", repr(TOKEN))
    if not TOKEN or not TOKEN.startswith("1") or ":" not in TOKEN:
        raise ValueError("❌ Токен не загружен или имеет неправильный формат!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setname", set_name))
    app.add_handler(CommandHandler("diagnosis", start_diagnosis))
    app.add_handler(CommandHandler("reminder", reminder))
    app.add_handler(CommandHandler("faq", faq))
    app.add_handler(CommandHandler("helpme", helpme))

    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()

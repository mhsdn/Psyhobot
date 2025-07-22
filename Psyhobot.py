import json
import os
import logging
import matplotlib.pyplot as plt
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv
import random
import asyncio

load_dotenv()  # Загружаем переменные окружения из .env

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

USER_DATA_FILE = "user_data.json"

# Загрузка и сохранение данных пользователей
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
scores = {"Никогда": 0, "Несколько дней": 1, "Более половины времени": 2, "Практически каждый день": 3}

user_answers = {}

# Состояния для ConversationHandler
GOAL_INPUT = range(1)
MOOD_INPUT = range(1)

# --- Команды ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    name = user_data.get(str(user_id), {}).get("name", "друг")
    await update.message.reply_text(
        f"Привет, {name}! Я твой личный психолог-бот.\n"
        "Вот команды, которые я понимаю:\n"
        "/help — помощь\n"
        "/setname <имя> — установить имя\n"
        "/diagnosis — экспресс-диагностика\n"
        "/mood — записать настроение\n"
        "/relax — техника релаксации\n"
        "/quote — мотивационная цитата\n"
        "/reminder <минуты> <сообщение> — установить напоминание\n"
        "/goals — личные цели\n"
        "/faq — часто задаваемые вопросы\n"
        "/helpme — экстренные службы поддержки\n"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start — приветствие\n"
        "/setname <имя> — установить имя\n"
        "/diagnosis — пройти опрос\n"
        "/mood — записать настроение с комментарием\n"
        "/relax — получить технику релаксации\n"
        "/quote — получить мотивационную цитату\n"
        "/reminder <минуты> <сообщение> — установить напоминание\n"
        "/goals — посмотреть и добавить цели\n"
        "/faq — вопросы и ответы\n"
        "/helpme — экстренные службы поддержки\n"
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
    total_score = sum(scores[answer] for answer in user_answers[user_id])
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
    scores_plot = [entry["score"] for entry in history]
    dates = [entry["date"] for entry in history]

    plt.figure(figsize=(8, 6))
    plt.plot(dates, scores_plot, marker='o', linestyle='-', color='blue')
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
    await update.message.reply_text(
        "Какое у вас сегодня настроение? Напишите, пожалуйста, несколько слов."
    )
    return MOOD_INPUT

async def mood_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mood_text = update.message.text.strip()

    user_data = load_user_data()
    moods = user_data.get(str(user_id), {}).get("mood", [])
    moods.append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "text": mood_text
    })
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    user_data[str(user_id)]["mood"] = moods
    save_user_data(user_data)

    await update.message.reply_text("Спасибо! Ваше настроение записано.")
    return ConversationHandler.END

# --- Техники релаксации ---

RELAX_TECHNIQUES = [
    "Сделайте глубокий вдох на 4 секунды, задержите дыхание на 7 секунд и медленно выдохните в течение 8 секунд. Повторите 3 раза.",
    "Закройте глаза, сосредоточьтесь на дыхании и постарайтесь расслабить все мышцы тела по очереди.",
    "Сделайте несколько медленных глубоких вдохов, представьте спокойное место и задержитесь там мыслями на минуту."
]

async def relax(update: Update, context: ContextTypes.DEFAULT_TYPE):
    technique = random.choice(RELAX_TECHNIQUES)
    await update.message.reply_text(f"Техника релаксации:\n\n{technique}")

# --- Мотивационные цитаты ---

QUOTES = [
    "Каждый день — новый шанс изменить свою жизнь.",
    "Ты сильнее, чем думаешь.",
    "Маленькие шаги ведут к большим переменам.",
    "Не бойся просить о помощи — это признак силы.",
    "Твое ментальное здоровье важно так же, как и физическое."
]

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = random.choice(QUOTES)
    await update.message.reply_text(f"Мотивационная цитата:\n\n{q}")

# --- Напоминания ---

async def reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if len(args) < 2:
        await update.message.reply_text("Использование: /reminder <минуты> <сообщение>")
        return

    try:
        minutes = int(args[0])
        if minutes <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Пожалуйста, укажи положительное число минут.")
        return

    text = " ".join(args[1:])
    await update.message.reply_text(f"Напоминание будет через {minutes} минут.")

    async def send_reminder():
        await asyncio.sleep(minutes * 60)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⏰ Напоминание: {text}")

    asyncio.create_task(send_reminder())

# --- FAQ ---

FAQ_LIST = [
    ("Как справиться со стрессом?", "Попробуйте техники релаксации, спорт и общение с близкими."),
    ("Что делать при бессоннице?", "Соблюдайте режим сна, избегайте гаджетов перед сном и попробуйте медитацию."),
    ("Когда стоит обратиться к психологу?", "Если негативные чувства продолжаются долго и мешают жить."),
]

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Часто задаваемые вопросы:\n\n"
    for q, a in FAQ_LIST:
        text += f"❓ {q}\n💡 {a}\n\n"
    await update.message.reply_text(text)

# --- Экстренные службы ---

EMERGENCY_CONTACTS = """
Если вам нужна срочная помощь, обратитесь к следующим службам:

- Россия: Телефон доверия 8-800-2000-122
- США: National Suicide Prevention Lifeline 988
- Европа: Телефоны доверия смотрите на https://befrienders.org
- Всегда можно позвонить в скорую помощь.

Берегите себя!
"""

async def helpme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(EMERGENCY_CONTACTS)

# --- Основной запуск бота ---

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Ошибка: в .env не найден TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(token).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setname", set_name))
    app.add_handler(CommandHandler("diagnosis", start_diagnosis))
    app.add_handler(CallbackQueryHandler(button, pattern=r"^answer_"))
    app.add_handler(CommandHandler("relax", relax))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("reminder", reminder))
    app.add_handler(CommandHandler("faq", faq))
    app.add_handler(CommandHandler("helpme", helpme))

    mood_handler = ConversationHandler(
        entry_points=[CommandHandler('mood', mood_start)],
        states={
            MOOD_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mood_save)]
        },
        fallbacks=[]
    )
    app.add_handler(mood_handler)

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()

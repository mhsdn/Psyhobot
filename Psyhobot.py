import json
import os
import logging
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    JobQueue,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

USER_DATA_FILE = "user_data.json"

# --- Константы для ConversationHandler ---
ASK_MOOD, ASK_DIAGNOSIS_QUESTION, CHAT_ANSWER, GAME_ANSWER = range(4)

# --- Переводы и ресурсы ---
LANGUAGES = ["ru", "en"]

TEXTS = {
    "ru": {
        "start": "Привет, {name}! Я твой личный психолог-бот. Чем могу помочь?",
        "help": (
            "Вот что я могу сделать:\n"
            "- /diagnosis — пройти экспресс-диагностику\n"
            "- /mood — записать и просмотреть дневник настроения\n"
            "- /resources — получить полезные материалы\n"
            "- /setname Иван — установить имя\n"
            "- /chat — задать вопрос боту\n"
            "- /help_line — экстренная помощь\n"
            "- /game — игра для тренировки внимания\n"
            "- /language — сменить язык"
        ),
        "setname_success": "Приятно познакомиться, {name}!",
        "setname_fail": "Пожалуйста, укажи имя после команды, например: /setname Иван",
        "ask_mood": "Оцени своё сегодняшнее настроение от 1 (очень плохо) до 10 (отлично):",
        "mood_recorded": "Настроение на {date} записано: {score}/10.",
        "mood_history": "Твой дневник настроения:",
        "diagnosis_intro": "Начинаем диагностику. Отвечай на вопросы, выбирая вариант:",
        "stress_advice": "Есть признаки стресса. Попробуй отдохнуть или поговорить с близкими.",
        "moderate_depression_advice": "Возможно умеренная депрессия. Подумай о разговоре с психологом.",
        "severe_depression_advice": "Может быть тяжёлая депрессия. Рекомендуется обратиться за помощью.",
        "good_state": "Ваше состояние в порядке.",
        "resources_intro": "Вот полезные материалы:\n"
                           "1. Статья: Как справиться со стрессом — https://example.com/stress\n"
                           "2. Видео: Медитация для начинающих — https://example.com/meditation\n"
                           "3. Аудио: Релаксация — https://example.com/relax\n",
        "emergency_info": "Если тебе нужна срочная помощь, обратись в горячую линию:\n"
                          "Телефон доверия: 8-800-2000-122\n"
                          "Психологическая помощь: 112\n",
        "language_changed": "Язык изменён на русский.",
        "game_start": "Игра на внимание! В течение 3 секунд нажми кнопку, когда она появится.",
        "game_too_soon": "Подожди, игра начнётся через несколько секунд!",
        "game_won": "Отлично! Ты успешно прошёл игру!",
        "game_lost": "Увы, время вышло. Попробуй ещё раз /game",
        "chat_prompt": "Задай свой вопрос, я постараюсь помочь.",
        "chat_no_answer": "Извини, я пока не могу ответить на этот вопрос.",
    },
    "en": {
        # Можно добавить английские тексты
        "start": "Hi, {name}! I'm your personal psychology bot. How can I help?",
        "help": (
            "Here's what I can do:\n"
            "- /diagnosis — take a quick diagnosis\n"
            "- /mood — record and view mood diary\n"
            "- /resources — get useful materials\n"
            "- /setname John — set your name\n"
            "- /chat — ask me a question\n"
            "- /help_line — emergency help\n"
            "- /game — attention training game\n"
            "- /language — change language"
        ),
        # и так далее...
    }
}

# --- Вопросы и варианты для диагностики ---
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

# --- Хранилища в памяти ---
user_answers = {}  # Для текущей диагностики
mood_entries = {}  # Для дневника настроения
languages = {}     # Язык пользователя, по умолчанию "ru"

# --- Загрузка и сохранение данных пользователей ---
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_user_language(user_id):
    return languages.get(user_id, "ru")

def get_text(user_id, key):
    lang = get_user_language(user_id)
    return TEXTS.get(lang, TEXTS["ru"]).get(key, "")

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    name = user_data.get(str(user_id), {}).get("name", "друг")
    text = get_text(user_id, "start").format(name=name)
    await update.message.reply_text(text)

# --- Команда /help ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, "help"))

# --- Команда /setname ---
async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = " ".join(context.args)
    if name:
        user_data = load_user_data()
        if str(user_id) not in user_data:
            user_data[str(user_id)] = {}
        user_data[str(user_id)]["name"] = name
        save_user_data(user_data)
        await update.message.reply_text(get_text(user_id, "setname_success").format(name=name))
    else:
        await update.message.reply_text(get_text(user_id, "setname_fail"))

# --- Команда /language для переключения языка ---
async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current = get_user_language(user_id)
    new_lang = "en" if current == "ru" else "ru"
    languages[user_id] = new_lang
    await update.message.reply_text(TEXTS[new_lang]["language_changed"])

# --- Дневник настроения ---
async def mood_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, "ask_mood"))
    return ASK_MOOD

async def mood_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        score = int(update.message.text)
        if 1 <= score <= 10:
            user_data = load_user_data()
            user_dict = user_data.get(str(user_id), {})
            history = user_dict.get("mood_history", [])
            today = datetime.now().strftime("%Y-%m-%d")
            history.append({"date": today, "score": score})
            user_dict["mood_history"] = history
            user_data[str(user_id)] = user_dict
            save_user_data(user_data)
            await update.message.reply_text(get_text(user_id, "mood_recorded").format(date=today, score=score))
            # Показать историю
            await show_mood_history(update, context, user_id)
            return ConversationHandler.END
        else:
            await update.message.reply_text("Пожалуйста, введи число от 1 до 10.")
            return ASK_MOOD
    except ValueError:
        await update.message.reply_text("Пожалуйста, введи число от 1 до 10.")
        return ASK_MOOD

async def show_mood_history(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id=None):
    if not user_id:
        user_id = update.effective_user.id
    user_data = load_user_data()
    history = user_data.get(str(user_id), {}).get("mood_history", [])
    if not history:
        await update.message.reply_text("Дневник настроения пуст.")
        return
    text = get_text(user_id, "mood_history") + "\n"
    for entry in history[-10:]:
        text += f"{entry['date']}: {entry['score']}/10\n"
    await update.message.reply_text(text)

# --- Диагностика (расширенная) ---
async def start_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answers[user_id] = []
    await update.message.reply_text(get_text(user_id, "diagnosis_intro"))
    return await ask_question(update, context, user_id, 0)

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
        return ASK_DIAGNOSIS_QUESTION
    else:
        return await evaluate_answers(update, context, user_id)

async def diagnosis_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_parts = query.data.split("_")
    user_id = int(data_parts[1])
    question_number = int(data_parts[2])
    answer = "_".join(data_parts[3:])
    user_answers[user_id].append(answer)
    if question_number + 1 < len(questions):
        await ask_question(update, context, user_id, question_number + 1)
        return ASK_DIAGNOSIS_QUESTION
    else:
        return await evaluate_answers(update, context, user_id)

async def evaluate_answers(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    total_score = sum(scores[answer] for answer in user_answers[user_id])
    if total_score <= 5:
        result = get_text(user_id, "good_state")
    elif 6 <= total_score <= 10:
        result = get_text(user_id, "stress_advice")
    elif 11 <= total_score <= 15:
        result = get_text(user_id, "moderate_depression_advice")
    else:
        result = get_text(user_id, "severe_depression_advice")

    user_data = load_user_data()
    history = user_data.get(str(user_id), {}).get("history", [])
    history.append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": total_score
    })
    user_data[str(user_id)] = {"history": history, **user_data.get(str(user_id), {})}
    save_user_data(user_data)

    await generate_progress_graph(user_id, history)

    # Если вызвано из callback_query
    if update.callback_query:
        await update.callback_query.message.edit_text(
            f"Ваши результаты:\n\nОбщий балл: {total_score}\n\n{result}\n\nВот ваш прогресс:"
        )
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(f"progress_{user_id}.png", "rb"))
    else:
        await update.message.reply_text(
            f"Ваши результаты:\n\nОбщий балл: {total_score}\n\n{result}\n\nВот ваш прогресс:"
        )
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(f"progress_{user_id}.png", "rb"))

    return ConversationHandler.END

async def generate_progress_graph(user_id: int, history: list):
    scores_ = [entry["score"] for entry in history]
    dates = [entry["date"] for entry in history]

    plt.figure(figsize=(8, 6))
    plt.plot(dates, scores_, marker='o', linestyle='-', color='blue')
    plt.title(f"Прогресс пользователя {user_id}")
    plt.xlabel("Дата")
    plt.ylabel("Баллы")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"progress_{user_id}.png")
    plt.close()

# --- Полезные материалы ---
async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, "resources_intro"))

# --- Экстренная помощь ---
async def help_line(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, "emergency_info"))

# --- Чат-бот (простейший) ---
async def chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, "chat_prompt"))
    return CHAT_ANSWER

async def chat_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user_id = update.effective_user.id

    # Простейшая логика ответов (можно расширить)
    if "стресс" in text:
        answer = "Стресс — нормальная реакция, попробуйте расслабиться, глубоко дышать."
    elif "депрессия" in text:
        answer = "Если чувствуете депрессию долго, лучше обратиться к специалисту."
    elif "сон" in text:
        answer = "Регулярный сон важен, старайтесь ложиться и вставать в одно время."
    else:
        answer = get_text(user_id, "chat_no_answer")

    await update.message.reply_text(answer)
    return ConversationHandler.END

# --- Игра на внимание ---
import random
import asyncio

game_states = {}

async def game_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, "game_start"))
    await asyncio.sleep(3)

    keyboard = [[InlineKeyboardButton("Нажми меня!", callback_data=f"game_click_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await update.message.reply_text("Жми кнопку!", reply_markup=reply_markup)
    game_states[user_id] = {"msg_id": msg.message_id, "clicked": False}

async def game_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data_parts = query.data.split("_")
    game_user_id = int(data_parts[2])

    if user_id != game_user_id:
        await query.answer("Это не твоя игра!", show_alert=True)
        return

    state = game_states.get(user_id)
    if state and not state["clicked"]:
        state["clicked"] = True
        await query.edit_message_text(get_text(user_id, "game_won"))
    else:
        await query.answer(get_text(user_id, "game_too_soon"), show_alert=True)

# --- Главная функция запуска бота ---
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    application = ApplicationBuilder().token(token).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setname", set_name))
    application.add_handler(CommandHandler("language", change_language))
    application.add_handler(CommandHandler("resources", resources))
    application.add_handler(CommandHandler("help_line", help_line))
    application.add_handler(CommandHandler("game", game_start))

    # Диагностика через ConversationHandler
    diagnosis_conv = ConversationHandler(
        entry_points=[CommandHandler("diagnosis", start_diagnosis)],
        states={
            ASK_DIAGNOSIS_QUESTION: [CallbackQueryHandler(diagnosis_button, pattern=r"^answer_")],
        },
        fallbacks=[]

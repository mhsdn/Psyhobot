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

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

USER_DATA_FILE = "user_data.json"

# Загрузка и сохранение данных
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Вопросы диагностики и ответы
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

# Состояния для ConversationHandler
ASK_DIAGNOSIS_QUESTION = 0
ASK_MOOD = 1
CHAT_ANSWER = 2

# Хранение текущих ответов пользователей (в памяти)
user_answers = {}
user_moods = {}
user_chat_context = {}

# Команды бота

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    name = user_data.get(str(user_id), {}).get("name", "друг")
    await update.message.reply_text(f"Привет, {name}! Я твой личный психолог-бот. Чем могу помочь?")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Вот что я могу сделать:\n"
        "- Провести экспресс-диагностику состояния (/diagnosis)\n"
        "- Отслеживать твой прогресс\n"
        "- Сохранять твои баллы\n"
        "- Показывать график изменений\n"
        "- Вести дневник настроения (/mood)\n"
        "- Поговорить с ботом (/chat)\n"
        "- Играть в игру на внимание (/game)\n"
        "- Установить имя: /setname Иван"
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

# --- Диагностика с ConversationHandler ---

async def start_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answers[user_id] = []
    await ask_diagnosis_question(update, context, user_id, 0)
    return ASK_DIAGNOSIS_QUESTION

async def ask_diagnosis_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, question_number: int):
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
        await ask_diagnosis_question(update, context, user_id, question_number + 1)
        return ASK_DIAGNOSIS_QUESTION
    else:
        await evaluate_answers(update, context, user_id)
        return ConversationHandler.END

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

async def generate_progress_graph(user_id: int, history: list):
    scores_list = [entry["score"] for entry in history]
    dates = [entry["date"] for entry in history]

    plt.figure(figsize=(8, 6))
    plt.plot(dates, scores_list, marker='o', linestyle='-', color='blue')
    plt.title(f"Прогресс пользователя {user_id}")
    plt.xlabel("Дата")
    plt.ylabel("Баллы")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"progress_{user_id}.png")
    plt.close()

# --- Ведение настроения ---

async def mood_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Какое у тебя сегодня настроение? Опиши в нескольких словах.")
    return ASK_MOOD

async def mood_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mood_text = update.message.text

    user_data = load_user_data()
    moods = user_data.get(str(user_id), {}).get("moods", [])
    moods.append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "mood": mood_text})
    user_data[str(user_id)] = {"moods": moods, **user_data.get(str(user_id), {})}
    save_user_data(user_data)

    await update.message.reply_text("Спасибо! Настроение сохранено.")
    return ConversationHandler.END

# --- Простой чат с ботом (симуляция) ---

async def chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! О чём хочешь поговорить? Напиши мне что-нибудь.")
    return CHAT_ANSWER

async def chat_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.lower()

    # Простейшие ответы — можно расширить
    if "привет" in user_text or "здравствуй" in user_text:
        reply = "Привет! Рад тебя слышать."
    elif "плохо" in user_text or "грусть" in user_text:
        reply = "Мне жаль, что тебе плохо. Хочешь, я послушаю?"
    elif "спасибо" in user_text:
        reply = "Пожалуйста! Я всегда здесь, если что."
    else:
        reply = "Интересно... Расскажи подробнее."

    await update.message.reply_text(reply)
    return CHAT_ANSWER

# --- Игра на внимание (клики по кнопкам) ---

game_clicks = {}

async def game_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    game_clicks[user_id] = 0
    keyboard = [
        [InlineKeyboardButton("Кликни меня!", callback_data=f"game_click_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Игра началась! Кликайте на кнопку как можно быстрее 5 раз.", reply_markup=reply_markup)

async def game_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[-1])
    if user_id not in game_clicks:
        game_clicks[user_id] = 0
    game_clicks[user_id] += 1

    if game_clicks[user_id] < 5:
        await query.edit_message_text(
            f"Клики: {game_clicks[user_id]}/5\nКликни ещё раз!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Кликни меня!", callback_data=f"game_click_{user_id}")]])
        )
    else:
        await query.edit_message_text("Поздравляю! Вы успешно кликнули 5 раз!")

# --- Главная функция запуска бота ---

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")  # Твой токен должен быть в переменных окружения

    application = ApplicationBuilder().token(token).build()

    logger.info("Регистрируем обработчики команд")

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setname", set_name))

    # ConversationHandler для диагностики
    diagnosis_conv = ConversationHandler(
        entry_points=[CommandHandler("diagnosis", start_diagnosis)],
        states={
            ASK_DIAGNOSIS_QUESTION: [CallbackQueryHandler(diagnosis_button, pattern=r"^answer_")],
        },
        fallbacks=[],
        per_user=True,
    )

    # ConversationHandler для настроения
    mood_conv = ConversationHandler(
        entry_points=[CommandHandler("mood", mood_start)],
        states={
            ASK_MOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, mood_record)],
        },
        fallbacks=[],
        per_user=True,
    )

    # ConversationHandler для чата
    chat_conv = ConversationHandler(
        entry_points=[CommandHandler("chat", chat_start)],
        states={
            CHAT_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_answer)],
        },
        fallbacks=[],
        per_user=True,
    )

    application.add_handler(diagnosis_conv)
    application.add_handler(mood_conv)
    application.add_handler(chat_conv)

    # Игра на внимание
    application.add_handler(CommandHandler("game", game_start))
    application.add_handler(CallbackQueryHandler(game_click, pattern=r"^game_click_"))

    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()

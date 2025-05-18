from telegram import Update, ReplyKeyboardMarkup, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from core import get_best_answer, normalize_text
from quiz import get_quiz_question
import asyncio
import time
import os
import random
import json  # импорт для работы с JSON

BOT_TOKEN = '7636335819:AAHeSZJPnJDX20tv_OgVSXeltKnos7oIaGM'
IMAGE_DIR = "images"

# Загрузка вопросов из JSON один раз при старте бота
with open("train_questions.json", "r", encoding="utf-8") as f:
    questions_db = json.load(f)

# Клавиатуры
start_only_keyboard = ReplyKeyboardMarkup([['▶️ Старт']], resize_keyboard=True)
start_keyboard = ReplyKeyboardMarkup([['Простой', 'Развернутый']], resize_keyboard=True)
mode_keyboard = ReplyKeyboardMarkup([['Простой', 'Развернутый']], resize_keyboard=True)

terms_keyboard_simple = ReplyKeyboardMarkup(
    [['маржа', 'плечо'], ['имбаланс', 'ликвидность'], ['волатильность', 'своп'], ['Сменить режим', '/help']],
    resize_keyboard=True
)

terms_keyboard_detailed = ReplyKeyboardMarkup(
    [['маржа', 'плечо'], ['имбаланс', 'ликвидность'], ['волатильность', 'своп'], ['quiz', 'train'], ['Сменить режим', '/help']],
    resize_keyboard=True
)

user_last_message_time = {}

def find_image_file(query: str):
    fname = query.replace(" ", "_") + ".png"
    path = os.path.join(IMAGE_DIR, fname)
    if os.path.exists(path):
        return path
    return None

TRAIN_TOPICS = list(questions_db.keys())

train_topics_keyboard = ReplyKeyboardMarkup(
    [TRAIN_TOPICS], resize_keyboard=True, one_time_keyboard=True
)

train_control_keyboard = ReplyKeyboardMarkup(
    [["Выйти из тренинга", "Сменить тему"]],
    resize_keyboard=True,
    one_time_keyboard=False
)

def get_random_question_for_topic(topic):
    questions = questions_db.get(topic, [])
    if not questions:
        return None
    return random.choice(questions)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["started"] = False
    await update.message.reply_text(
        "👋 Добро пожаловать! Нажмите '▶️ Старт' для начала.",
        reply_markup=start_only_keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Доступные команды:\n"
        "/start - начать работу\n"
        "/help - помощь\n"
        "В простом режиме доступны базовые термины.\n"
        "В развернутом - дополнительные функции: quiz и train.\n"
        "В режиме train можно выйти командой 'Выйти из тренинга'."
    )
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time.time()
    if now - user_last_message_time.get(user_id, 0) < 1:
        await update.message.reply_text("⏳ Подождите секунду перед следующим сообщением.")
        return
    user_last_message_time[user_id] = now

    raw = update.message.text.strip()
    low = raw.lower()

    if not context.user_data.get("started"):
        if low == "▶️ старт":
            context.user_data["started"] = True
            await update.message.reply_text("✏️Выберите режим:", reply_markup=mode_keyboard)
        else:
            await update.message.reply_text("👋 Пожалуйста, нажмите '▶️ Старт' для начала.", reply_markup=start_only_keyboard)
        return

    if context.user_data.get("in_train_mode"):
        train_state = context.user_data.get("train_state", "choosing_topic")

        if low == "выйти из тренинга":
            context.user_data["in_train_mode"] = False
            for k in ["train_state", "train_topic", "train_questions", "train_index", "correct", "explanation", "answered"]:
                context.user_data.pop(k, None)
            await update.message.reply_text("Вы вышли из режима тренировки.", reply_markup=terms_keyboard_detailed)
            return

        if low == "сменить тему":
            context.user_data["train_state"] = "choosing_topic"
            for k in ["train_topic", "train_questions", "train_index", "correct", "explanation", "answered"]:
                context.user_data.pop(k, None)
            await update.message.reply_text(
                "Тема сброшена. Выберите новую тему:",
                reply_markup=train_topics_keyboard
            )
            return

        if train_state == "choosing_topic":
            if raw not in TRAIN_TOPICS:
                await update.message.reply_text("Пожалуйста, выберите тему из предложенных кнопок.", reply_markup=train_topics_keyboard)
                return

            questions = questions_db.get(raw, [])
            if not questions:
                await update.message.reply_text("Для этой темы пока нет вопросов. Выберите другую тему.", reply_markup=train_topics_keyboard)
                return

            random.shuffle(questions)

            context.user_data["train_topic"] = raw
            context.user_data["train_questions"] = questions
            context.user_data["train_index"] = 0
            context.user_data["train_state"] = "asking_question"

            await update.message.reply_text(
                f"Тема '{raw}' выбрана. Начинаем тренинг.\n\n"
                "Вы можете в любой момент выйти из тренинга или сменить тему, используя кнопки ниже.",
                reply_markup=train_control_keyboard
            )
            await send_train_question(update, context)
            return

        if train_state == "asking_question":
            # Ждем ответ через кнопки, текст игнорируем
            return

    if low == "сменить режим":
        context.user_data.clear()
        context.user_data["started"] = True
        await update.message.reply_text("Режим сброшен. Выберите новый:", reply_markup=mode_keyboard)
        return
    if low == "простой":
        context.user_data["detailed"] = False
        await update.message.reply_text("✅ Простой режим выбран.", reply_markup=terms_keyboard_simple)
        return
    if low == "развернутый":
        context.user_data["detailed"] = True
        await update.message.reply_text("✅ Развернутый режим выбран.", reply_markup=terms_keyboard_detailed)
        return
    if "detailed" not in context.user_data:
        await update.message.reply_text("Сначала нажмите /start и выберите режим.", reply_markup=start_keyboard)
        return

    if context.user_data.get("detailed") and low in ["quiz", "train"]:
        if low == "quiz":
            await handle_quiz(update, context)
        elif low == "train":
            await handle_train(update, context)
        return

    query = normalize_text(raw)
    detailed = context.user_data["detailed"]
    answer, source = get_best_answer(query, detailed=detailed)
    response = f"💭 <b>Ответ:</b>\n{answer}\n\n<i>Источник: {source}</i>"
    await update.message.reply_text(response, parse_mode=ParseMode.HTML)

    if detailed:
        img_path = find_image_file(query)
        if img_path:
            try:
                with open(img_path, "rb") as f:
                    await update.message.reply_photo(photo=InputFile(f))
            except Exception as e:
                print("Ошибка при отправке изображения:", e)

async def handle_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question_data = get_quiz_question()
    question = question_data["definition"]
    options = question_data["options"].copy()
    correct_key = question_data["correct"]
    explanation = question_data.get("explanation", "")

    # Перемешиваем варианты и запоминаем индекс правильного ответа
    shuffled_options = options.copy()
    random.shuffle(shuffled_options)
    correct_index = shuffled_options.index(correct_key)

    context.user_data["correct"] = correct_key
    context.user_data["explanation"] = explanation
    context.user_data["answered"] = False
    context.user_data["options"] = shuffled_options

    keyboard = [[InlineKeyboardButton(opt, callback_data=str(i))] for i, opt in enumerate(shuffled_options)]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(f"🧠 Угадай термин:\n\n{question}", reply_markup=reply_markup)

    async def quiz_timeout():
        await asyncio.sleep(10)
        if not context.user_data.get("answered"):
            await update.message.reply_text(
                f"⏰ Время вышло! Правильный ответ: <b>{correct_key}</b>\n\n💡 Определение термина:\n{explanation}",
                parse_mode=ParseMode.HTML
            )
            context.user_data["answered"] = True

    context.user_data["quiz_task"] = asyncio.create_task(quiz_timeout())

async def handle_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["in_train_mode"] = True
    context.user_data["train_state"] = "choosing_topic"
    await update.message.reply_text(
        "🎯Вы вошли в режим тренировки.\nВыберите тему:",
        reply_markup=train_topics_keyboard
    )

async def send_train_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = context.user_data.get("train_questions", [])
    idx = context.user_data.get("train_index", 0)

    if idx >= len(questions):
        text = "🎉 Все вопросы из выбранной темы завершены.\nВы можете сменить тему или выйти из тренинга."
        await update.message.reply_text(text, reply_markup=train_control_keyboard)
        context.user_data["train_state"] = "choosing_topic"
        return

    q = questions[idx]
    text = f"❓ Вопрос ({idx + 1}/{len(questions)}):\n{q['definition']}"

    # Перемешаем варианты ответа для тренировки
    options = q["options"].copy()
    random.shuffle(options)
    context.user_data["train_options"] = options

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(opt, callback_data=str(i))] for i, opt in enumerate(options)]
    )
    await update.message.reply_text(text, reply_markup=keyboard)

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # Обработка quiz
    if "correct" in context.user_data and not context.user_data.get("in_train_mode", False):
        if context.user_data.get("answered", False):
            await query.edit_message_text("Вы уже ответили на этот вопрос.")
            return

        correct = context.user_data["correct"]
        explanation = context.user_data.get("explanation", "")

        options = context.user_data.get("options", [])
        if not options:
            await query.edit_message_text("Ошибка: отсутствуют варианты ответа.")
            return

        selected_idx = int(data)
        correct_idx = options.index(correct) if correct in options else -1

        if selected_idx == correct_idx:
            text = f"✅ Правильно!\n💡{explanation}"
        else:
            text = f"❌ Неправильно. Правильный ответ: <b>{correct}</b>.\n\n💡{explanation}"

        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        context.user_data["answered"] = True

        # Отменяем таймер если он есть
        task = context.user_data.get("quiz_task")
        if task:
            task.cancel()
        return

    # Обработка тренинга
    if context.user_data.get("in_train_mode") and context.user_data.get("train_state") == "asking_question":
        idx = context.user_data.get("train_index", 0)
        questions = context.user_data.get("train_questions", [])
        if idx >= len(questions):
            await query.edit_message_text("Тренинг завершен. Выберите действие на клавиатуре.")
            return

        question = questions[idx]
        correct = question["correct"]
        explanation = question.get("explanation", "")

        options = context.user_data.get("train_options", question["options"])
        selected_idx = int(data)
        correct_idx = options.index(correct)

        if selected_idx == correct_idx:
            text = f"✅ Правильно!\n💡 Определение термина:\n{explanation}"
        else:
            text = f"❌ Неправильно. Правильный ответ: <b>{correct}</b>.\n\n💡 Определение термина:\n{explanation}"

        await query.edit_message_text(text, parse_mode=ParseMode.HTML)

        context.user_data["train_index"] = idx + 1
        await asyncio.sleep(1)

        if context.user_data["train_index"] < len(questions):
            # Отправляем следующий вопрос
            class DummyUpdate:
                message = query.message
            dummy_update = DummyUpdate()
            await send_train_question(dummy_update, context)
        else:
            await query.message.reply_text(
                "🎉 Тренинг завершен по этой теме.\nВыберите другую тему или выйдите из тренинга.",
                reply_markup=train_control_keyboard
            )
            context.user_data["train_state"] = "choosing_topic"
        return

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    print("Бот запущен")

    application.run_polling()
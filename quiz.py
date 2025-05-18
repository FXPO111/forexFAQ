import random
import time
from typing import Optional
from core import normalize_text
from terms import terms  # словарь term -> определение

# Пример структуры с темами и терминами в них
TOPIC_TERMS = {
    "смарт мани": ["маржа", "плечо", "ликвидность"],
    "технический анализ": ["имбаланс", "волатильность", "своп"],
    "экономика": ["инфляция", "ВВП", "дефляция"]
}

user_quiz_data = {}  # user_id -> { question, timestamp }

def get_quiz_question(topic: Optional[str] = None):
    """
    Генерируем вопрос для викторины.
    Если topic указан, берём термин из этой темы.
    Иначе - случайный термин из всех terms.
    Возвращаем словарь с 'definition', 'options', 'correct', 'explanation'.
    """

    # Получаем список терминов для выбора
    if topic and topic in TOPIC_TERMS:
        possible_terms = TOPIC_TERMS[topic]
    else:
        possible_terms = list(terms.keys())

    # Выбираем правильный термин
    key = random.choice(possible_terms)
    definition = terms.get(key, "Нет определения")

    # Формируем варианты ответа: 3 неправильных + правильный
    wrong_keys = random.sample([k for k in terms.keys() if k != key], 3)
    options = wrong_keys + [key]
    random.shuffle(options)

    # Можно добавить объяснение (если есть)
    explanation = f"Определение термина: {definition}"

    return {
        "definition": definition,
        "options": options,
        "correct": key,
        "explanation": explanation
    }

def store_quiz_for_user(user_id):
    question = get_quiz_question()
    user_quiz_data[user_id] = {
        "question": question,
        "timestamp": time.time()
    }
    return question

def check_answer(user_id, user_answer, time_limit=20):
    entry = user_quiz_data.get(user_id)
    if not entry:
        return "❗ Вопрос не найден или время вышло.", None, None

    elapsed = time.time() - entry["timestamp"]
    correct_key = entry["question"]["correct"]

    # Удаляем данные независимо от результата, чтобы не повторять один и тот же вопрос
    user_quiz_data.pop(user_id)

    if elapsed > time_limit:
        return f"⏱ Время вышло! Правильный ответ: {correct_key}", False, correct_key

    if normalize_text(user_answer) == normalize_text(correct_key):
        return "✅ Верно! Отличная работа!", True, correct_key
    else:
        return f"❌ Неверно. Правильный ответ: {correct_key}", False, correct_key

def get_definition(term):
    return terms.get(term)

from sentence_transformers import SentenceTransformer, util
import torch
import re

# Импортируем ваши модули с данными
from terms import terms as _base_terms
from detailed_terms import detailed_terms as _base_detailed
from term_aliases import term_aliases as _base_aliases

# Словарь трёх вариантов: англ → (перевод, транслит)
LANG_VARIANTS = {
    "smart money": ("умные деньги", "смарт мани"),
    "order block": ("блок ордеров", "ордер блок"),
    "market shift": ("смена рынка", "маркет шифт"),
    # добавьте сюда другие англоязычные ключи
}

# Загружаем модель один раз
model = SentenceTransformer("all-MiniLM-L6-v2")

# Стоп-фразы для очистки запросов
STOP_WORDS = [
    "что такое", "объясни", "поясни", "расскажи",
    "дай", "почему", "как", "пожалуйста", "поясни пожалуйста"
]

def normalize_text(text: str) -> str:
    """
    Нижний регистр, '_'→' ', убираем пунктуацию и стоп-фразы, нормализуем пробелы.
    """
    text = text.lower().replace("_", " ")
    text = re.sub(r'[^\w\s]', '', text)
    for stop in STOP_WORDS:
        if text.startswith(stop):
            text = text[len(stop):].strip()
    return re.sub(r'\s+', ' ', text).strip()

# 1) Нормализация базовых словарей
terms = {normalize_text(k): v for k, v in _base_terms.items()}
detailed_terms = {normalize_text(k): v for k, v in _base_detailed.items()}

# 2) Сбор и нормализация синонимов с учётом LANG_VARIANTS
aliases_clean = {}
for eng_key, v in _base_aliases.items():
    norm_key = normalize_text(eng_key)

    # Получаем базовый список синонимов
    if isinstance(v, tuple) and len(v) == 2 and isinstance(v[1], list):
        base_aliases = v[1]
    else:
        base_aliases = v if isinstance(v, list) else []

    # Автоматически добавляем перевод и транслит
    if eng_key in LANG_VARIANTS:
        rus, trans = LANG_VARIANTS[eng_key]
        base_aliases += [rus, trans]

    # Нормализуем всё и сохраняем
    aliases_clean[norm_key] = [normalize_text(a) for a in base_aliases]

term_aliases = aliases_clean

# 3) Предрасчёт эмбеддингов
keys = list(terms.keys())
key_embeddings = model.encode(keys, convert_to_tensor=True)

import re

def get_best_answer(query: str, detailed: bool = False):
    q_orig = normalize_text(query)

    # Ищем ключевой термин, точное вхождение как подстроку (с пробелами или в начале/конце)
    for term_key in keys:
        # Проверяем, что term_key есть в q_orig и окружён либо пробелами, либо стоит в начале или в конце
        pos = q_orig.find(term_key)
        if pos != -1:
            before = pos == 0 or q_orig[pos-1] == " "
            after = pos + len(term_key) == len(q_orig) or q_orig[pos+len(term_key)] == " "
            if before and after:
                q = term_key
                break
    else:
        q = q_orig

    # Далее логика как раньше
    if q in terms:
        ans = detailed_terms.get(q) if detailed else terms[q]
        if not ans:
            ans = terms[q] + "\n\n📌 Подробное описание пока не добавлено."
        return ans, "FXPO Squad"

    for key, aliases in term_aliases.items():
        if q in aliases:
            ans = detailed_terms.get(key) if detailed else terms.get(key)
            if not ans:
                fallback = terms.get(key)
                if fallback:
                    ans = fallback + "\n\n📌 Подробное описание пока не добавлено."
                else:
                    continue
            return ans, "FXPO Squad"

    query_emb = model.encode(q, convert_to_tensor=True)
    sims = util.cos_sim(query_emb, key_embeddings)[0]
    best_idx = torch.argmax(sims).item()
    best_score = sims[best_idx].item()

    if best_score < 0.5:
        top_idxs = torch.topk(sims, k=3)[1]
        suggestions = [keys[i] for i in top_idxs if sims[i] > 0.3]
        if suggestions:
            return "❓ Возможно, вы имели в виду: " + ", ".join(suggestions), "FXPO Squad"
        return "Извините, не удалось найти точный ответ.", "FXPO Squad"

    best_key = keys[best_idx]
    ans = detailed_terms.get(best_key) if detailed else terms[best_key]
    if not ans:
        ans = terms[best_key] + "\n\n📌 Подробное описание пока не добавлено."
    return ans, "FXPO Squad"

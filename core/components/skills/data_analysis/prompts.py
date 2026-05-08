"""
Чистые функции для работы с промптами и данными.

ВЫДЕЛЕНЫ ИЗ SKILL:
- render_prompt — подстановка переменных в шаблон
- format_data_as_json — форматирование данных
- estimate_chars_per_token — оценка плотности текста
"""
import json
from typing import Any, Dict, List


def render_prompt(template: str, variables: Dict[str, Any]) -> str:
    """Подстановка переменных в шаблон промпта."""
    result = template
    for key, value in variables.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def format_data_as_json(data: List[Dict[str, Any]]) -> str:
    """Форматирование данных как JSON с отступами."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def estimate_chars_per_token(text: str) -> float:
    """Оценка символов на токен для русского/английского текста."""
    if not text:
        return 3.0
    sample = text[:1000]
    cyrillic_ratio = sum(1 for c in sample if '\u0400' <= c <= '\u04FF') / max(len(sample), 1)
    if cyrillic_ratio > 0.3:
        return 2.2
    elif cyrillic_ratio > 0.1:
        return 2.5
    return 3.5


def fits_in_context(data: List[Dict[str, Any]], question: str, context_window: int = 8192, max_new_tokens: int = 2000) -> bool:
    """Проверка: влезает ли вопрос+данные в контекст LLM с запасом."""
    if not data:
        return False
    data_str = json.dumps(data, ensure_ascii=False)
    total_chars = len(question) + len(data_str) + 1000
    cpt = estimate_chars_per_token(question + data_str[:1000])
    total_tokens = total_chars / cpt
    return total_tokens < (context_window - max_new_tokens - 500) * 0.85

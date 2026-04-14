"""
Модуль для LLM-friendly форматирования ошибок валидации Pydantic.

ОТВЕТСТВЕННОСТЬ:
- Преобразование ValidationError в понятные строки
- Формат для self-correction LLM (ретраи с обратной связью)
- Поддержка вложенных путей и массивов

ПРИМЕР:
>>> error = format_validation_error(exc)
>>> error
'Field "data.items[2].price": expected float, got "abc"'
"""
from typing import Any, Dict, List
from pydantic import ValidationError


def format_validation_error(error: ValidationError) -> str:
    """
    Форматирование ValidationError в LLM-friendly строку.

    ФОРМАТ:
    Field "path.to.field": expected <type>, got <value>
    Field "items[2].price": value 150 is less than minimum 0

    ARGS:
    - error: ValidationError от Pydantic

    RETURNS:
    - str: компактное описание для ретрая LLM

    EXAMPLE:
    >>> try:
    ...     Model.model_validate({"price": "abc"})
    ... except ValidationError as e:
    ...     msg = format_validation_error(e)
    >>> msg
    'Field "price": expected float, got "abc"'
    """
    errors = error.errors()
    if not errors:
        return "Неизвестная ошибка валидации"

    messages = []
    for err in errors:
        loc = err.get("loc", [])
        msg = err.get("msg", "unknown error")
        input_val = err.get("input")

        # Формируем путь
        field_path = _format_field_path(loc)

        # Формируем понятное сообщение
        friendly_msg = _make_friendly_message(field_path, msg, input_val)
        messages.append(friendly_msg)

    return "; ".join(messages)


def format_for_llm_retry(
    error: ValidationError,
    original_response: str
) -> str:
    """
    Форматирование ошибки для промпта ретрая LLM.

    ИСПОЛЬЗОВАНИЕ:
    Добавляется в промпт при ретрае:
    "Твой предыдущий ответ содержал ошибки:\n{error_feedback}"

    ARGS:
    - error: ValidationError
    - original_response: str — оригинальный ответ LLM

    RETURNS:
    - str: инструкция для LLM

    EXAMPLE:
    >>> feedback = format_for_llm_retry(error, llm_response)
    >>> prompt = f"Исправь ошибки:\\n{feedback}"
    """
    errors = error.errors()
    
    lines = [
        "Твой предыдущий ответ содержал ошибки валидации JSON:",
        ""
    ]

    for err in errors:
        loc = err.get("loc", [])
        msg = err.get("msg", "unknown")
        input_val = err.get("input")

        field_path = _format_field_path(loc)
        friendly_msg = _make_friendly_message(field_path, msg, input_val)
        lines.append(f"  - {friendly_msg}")

    lines.extend([
        "",
        "Исправь эти ошибки и верни корректный JSON.",
        "Убедись что:",
        "  - Все типы данных соответствуют схеме",
        "  - Обязательные поля присутствуют",
        "  - Числовые значения в допустимых диапазонах"
    ])

    return "\n".join(lines)


def _format_field_path(loc: tuple) -> str:
    """
    Форматирование пути к полю в читаемый вид.

    ARGS:
    - loc: tuple от Pydantic (например: ('data', 'items', 2, 'price'))

    RETURNS:
    - str: "data.items[2].price"

    EXAMPLE:
    >>> _format_field_path(('data', 'items', 2, 'price'))
    'data.items[2].price'
    """
    parts = []
    for part in loc:
        if isinstance(part, int):
            # Индекс массива
            if parts:
                parts[-1] = f"{parts[-1]}[{part}]"
            else:
                parts.append(f"[{part}]")
        else:
            parts.append(str(part))
    
    return ".".join(parts)


def _make_friendly_message(
    field_path: str,
    error_msg: str,
    input_value: Any
) -> str:
    """
    Создание понятного сообщения об ошибке.

    ARGS:
    - field_path: str — путь к полю
    - error_msg: str — оригинальное сообщение Pydantic
    - input_value: Any — значение, вызвавшее ошибку

    RETURNS:
    - str: human-readable сообщение
    """
    # Маппинг типичных ошибок Pydantic
    error_mappings = {
        "type_error.missing": f'Field "{field_path}": required field is missing',
        "type_error.none": f'Field "{field_path}": expected value, got None',
        "float_type": f'Field "{field_path}": expected float, got "{_truncate(str(input_value), 20)}"',
        "int_type": f'Field "{field_path}": expected integer, got "{_truncate(str(input_value), 20)}"',
        "str_type": f'Field "{field_path}": expected string, got {_truncate(str(input_value), 20)}',
        "bool_type": f'Field "{field_path}": expected boolean, got "{_truncate(str(input_value), 20)}"',
        "value_error.number.not_ge": f'Field "{field_path}": value {input_value} is less than minimum allowed',
        "value_error.number.not_le": f'Field "{field_path}": value {input_value} exceeds maximum allowed',
        "value_error.any_str_min_length": f'Field "{field_path}": string is too short (min length required)',
        "value_error.any_str_max_length": f'Field "{field_path}": string is too long (max length exceeded)',
        "value_error.list.min_items": f'Field "{field_path}": array has too few items',
        "value_error.list.max_items": f'Field "{field_path}": array has too many items',
    }

    for error_type, message in error_mappings.items():
        if error_type in error_msg:
            return message

    # Fallback: оригинальное сообщение с путём
    return f'Field "{field_path}": {error_msg} (value: {_truncate(str(input_value), 30)})'


def _truncate(text: str, max_length: int) -> str:
    """Обрезка длинных значений."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

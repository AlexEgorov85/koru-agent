"""
_robust_extract_json — надёжное извлечение JSON из текста.

ОТВЕТСТВЕННОСТЬ:
- Извлечение JSON из markdown блоков с любыми языковыми метками
- Обработка обрезанных скобок (оборванный ответ LLM)
- Обработка экранирования \" внутри строк
- Устойчивость к мусору до/после JSON
- Логирование каждого шага

АРХИТЕКТУРА:
- Все статические методы (без состояния)
- Вызывается из JsonParsingService._action_extract_json
- Поддерживает вложенные структуры любой глубины
"""
import re
import json
from typing import Optional, List, Tuple


def robust_extract_json(content: str) -> Tuple[Optional[str], List[str]]:
    """
    Надёжное извлечение JSON из текста.

    АЛГОРИТМ:
    1. Markdown блоки ```[lang]...``` (любые языковые метки)
    2. Просто ```...``` без метки
    3. Поиск по балансировке скобок (устойчив к обрезанным ответам)
    4. Fallback: первая { до последней }

    ARGS:
    - content: str — текст ответа LLM

    RETURNS:
    - (json_string, steps) или (None, steps) если не найден
    """
    steps: List[str] = []

    if not content:
        steps.append("Входной текст пустой")
        return None, steps

    # Шаг 1: Markdown блоки с любыми языковыми метками
    steps.append("Поиск markdown блоков ```[lang]...```")
    markdown_pattern = r'```(?:json|javascript|python|yaml|bash|sh|shell|text|code)?\s*(.*?)\s*```'
    matches = re.findall(markdown_pattern, content, re.DOTALL | re.IGNORECASE)
    
    for idx, match in enumerate(matches):
        json_content = match.strip()
        if json_content.startswith('{') or json_content.startswith('['):
            steps.append(f"Найден markdown блок #{idx+1}: {len(json_content)} симв.")
            return json_content, steps

    # Шаг 2: Просто ```...``` без языковой метки
    steps.append("Поиск markdown блоков ```...```")
    simple_markdown = r'```\s*(.*?)\s*```'
    matches = re.findall(simple_markdown, content, re.DOTALL)
    
    for idx, match in enumerate(matches):
        json_content = match.strip()
        if json_content.startswith('{') or json_content.startswith('['):
            steps.append(f"Найден markdown блок #{idx+1}: {len(json_content)} симв.")
            return json_content, steps

    # Шаг 3: Балансировка скобок (устойчиво к обрезанным ответам)
    steps.append("Поиск по балансировке скобок")
    json_str, found = _extract_by_balancing(content)
    if found:
        steps.append(f"Извлечено по балансировке: {len(json_str)} симв.")
        return json_str, steps

    # Шаг 4: Fallback — первая { до последней }
    steps.append("Fallback: поиск по первой { и последней }")
    start = content.find('{')
    end = content.rfind('}') + 1
    if start != -1 and end > start:
        json_content = content[start:end]
        steps.append(f"Извлечено по скобкам {{}}: {len(json_content)} симв.")
        return json_content, steps

    # Шаг 5: Fallback — массив [...]
    steps.append("Fallback: поиск массива [...]")
    start = content.find('[')
    end = content.rfind(']') + 1
    if start != -1 and end > start:
        json_content = content[start:end]
        steps.append(f"Извлечён массив []: {len(json_content)} симв.")
        return json_content, steps

    steps.append("JSON не найден")
    return None, steps


def _extract_by_balancing(content: str) -> Tuple[str, bool]:
    """
    Извлечь JSON по балансировке скобок.

    Работает с обрезанными ответами LLM:
    - Идёт посимвольно
    - Считает баланс {} и []
    - Как только баланс стал 0 — нашёл конец JSON
    - Если не дошёл до 0 — добавляет недостающие скобки

    ARGS:
    - content: str — текст

    RETURNS:
    - (json_string, success)
    """
    # Найти первую { или [
    start_idx = -1
    for i, char in enumerate(content):
        if char in '{[':
            start_idx = i
            break

    if start_idx == -1:
        return "", False

    # Посимвольный проход с балансировкой
    brace_count = 0
    bracket_count = 0
    in_string = False
    escape_next = False
    last_valid_end = -1

    for i in range(start_idx, len(content)):
        char = content[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
        elif char == '[':
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1

        # Баланс достигнут — конец JSON
        if brace_count == 0 and bracket_count == 0:
            last_valid_end = i + 1
            break

    if last_valid_end != -1:
        return content[start_idx:last_valid_end], True

    # Баланс не достигнут — добавляем недостающие скобки
    return _fix_unbalanced(content[start_idx:])


def _fix_unbalanced(json_str: str) -> Tuple[str, bool]:
    """
    Исправить несбалансированные скобки в JSON.

    ARGS:
    - json_str: str — текст JSON

    RETURNS:
    - (fixed_json, success)
    """
    if not json_str:
        return "", False

    # Удалить trailing whitespace/мусор
    stripped = json_str.rstrip()

    # Найти последнюю значимую позицию
    last_meaningful_idx = -1
    for i in range(len(stripped) - 1, -1, -1):
        char = stripped[i]
        if char in '}"\'0123456789' or char.isalpha():
            last_meaningful_idx = i
            break

    if last_meaningful_idx == -1:
        return "", False

    core = stripped[:last_meaningful_idx + 1]

    # Подсчитать баланс
    brace_count = 0
    bracket_count = 0
    in_string = False
    escape_next = False

    for char in core:
        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1

    # Добавить недостающие скобки
    fixed = core

    while bracket_count > 0:
        fixed += ']'
        bracket_count -= 1

    while brace_count > 0:
        fixed += '}'
        brace_count -= 1

    return fixed, True


def validate_json_structure(json_str: str) -> Tuple[bool, Optional[dict]]:
    """
    Проверить что извлечённый JSON валиден.

    ARGS:
    - json_str: str — текст JSON

    RETURNS:
    - (is_valid, parsed_data)
    """
    try:
        parsed = json.loads(json_str)
        return True, parsed
    except json.JSONDecodeError:
        return False, None

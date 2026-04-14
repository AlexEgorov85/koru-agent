"""
JSON Parser — утилитарные функции для работы с JSON ответами LLM.

ОТВЕТСТВЕННОСТЬ:
- Извлечение JSON из markdown-обёртки
- Используется провайдерами (llama_cpp, vllm) и компонентами

НЕ ОТВЕТСТВЕННОСТЬ:
- Валидация через Pydantic модели (это JsonParsingService)
- Создание Pydantic моделей из схемы (это JsonParsingService)

ИСПОЛЬЗУЕТСЯ:
- llama_cpp_provider._extract_json_from_response()
- vllm_provider._extract_json_from_response()
- data_analysis._parse_llm_response()
"""
import re
from typing import Optional


def _fix_missing_commas(json_str: str) -> str:
    """
    Исправить отсутствующие запятые между полями JSON.
    
    ПРОБЛЕМА: LLM иногда генерирует JSON без запятых между полями.
    
    РЕШЕНИЕ: Добавить запятые там где после значения идёт новый ключ.
    """
    patterns = [
        # После закрывающей кавычки значения идёт новый ключ
        # "key": "value"\n"next_key" -> "key": "value",\n"next_key"
        (r'(")\s*\n\s*(")', r'\1,\n\2'),
        
        # После закрывающей скобки } или ] идёт новый ключ
        # }\n"key" -> },\n"key"
        (r'(\}|\])\s*\n\s*(")', r'\1,\n\2'),
        
        # После числа или true/false/null идёт новый ключ
        # 123\n"key" -> 123,\n"key"
        (r'(\d|true|false|null)\s*\n\s*(")', r'\1,\n\2'),
        
        # Объекты в массивах: }\n{ -> },\n{
        (r'(\})\s*\n\s*(\{)', r'\1,\n\2'),
    ]
    
    fixed = json_str
    for pattern, replacement in patterns:
        fixed = re.sub(pattern, replacement, fixed)
    
    return fixed


def _fix_missing_closing_brackets(json_str: str) -> str:
    """
    Исправить отсутствующие закрывающие скобки в JSON.
    
    ПРОБЛЕМА: LLM иногда зацикливается, добавляет кучу переносов/пробелов 
    или обрывает ответ, и JSON остаётся без закрывающих скобок.
    
    ПРИМЕРЫ:
    - {"key": "value"  (нет })
    - {"arr": [1, 2, 3]  (нет ])
    - {"obj": {"inner": "value"}  (нет внешнего })
    - {"key": "value"}}}}}  (лишние скобки - НЕ исправляем, это другая проблема)
    
    РЕШЕНИЕ: Подсчитать открывающие/закрывающие скобки и добавить недостающие.
    """
    # Удаляем trailing whitespace и мусор в конце
    # (переносы, пробелы, точки и т.д. после последнего символа JSON)
    stripped = json_str.rstrip()
    
    # Находим последнюю значимую позицию (последнюю } или ] или цифру или букву)
    last_meaningful_idx = -1
    for i in range(len(stripped) - 1, -1, -1):
        char = stripped[i]
        if char in '}"\'0123456789' or char.isalpha():
            last_meaningful_idx = i
            break
    
    if last_meaningful_idx == -1:
        return json_str  # Не удалось найти конец JSON
    
    # Берём часть до конца значимого контента
    core_json = stripped[:last_meaningful_idx + 1]
    
    # Подсчитываем баланс скобок
    brace_count = 0  # для {}
    bracket_count = 0  # для []
    in_string = False
    escape_next = False
    
    for char in core_json:
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\' and in_string:
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
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
    
    # Добавляем недостающие закрывающие скобки
    fixed = core_json
    
    # Сначала закрываем массивы (внутренние)
    while bracket_count > 0:
        fixed += ']'
        bracket_count -= 1
    
    # Потом закрываем объекты (внешние)
    while brace_count > 0:
        fixed += '}'
        brace_count -= 1
    
    return fixed


def _fix_json_trailing_garbage(json_str: str) -> str:
    """
    Удалить мусор в конце JSON (повторяющиеся переносы, пробелы, точки).
    
    ПРОБЛЕМА: LLM зацикливается и добавляет кучу символов после JSON.
    
    ПРИМЕР:
    - {"key": "value"}\n\n\n\n.....
    - {"key": "value"}          
    """
    # Ищем последнюю } или ] и обрезаем всё после неё
    last_brace = json_str.rfind('}')
    last_bracket = json_str.rfind(']')
    last_closing = max(last_brace, last_bracket)
    
    if last_closing != -1:
        # Проверяем что после закрывающей скобки только мусор
        after = json_str[last_closing + 1:].strip()
        if not after or all(c in '\n\r\t .,;' for c in after):
            return json_str[:last_closing + 1]
    
    return json_str


def _extract_and_fix_json(json_str: str) -> Optional[str]:
    """
    Извлечь валидный JSON из строки с мусором.
    
    ПРОБЛЕМА: LLM генерирует кучу мусора ВНУТРИ JSON, из-за чего 
    закрывающие скобки "теряются" или смещаются.
    
    ПРИМЕР:
    - {"key": "value"} extra text {"garbage": true}
    - {"key": "value"} random characters....
    - {"key": incomplete garbage
    
    РЕШЕНИЕ: Посимвольно идём по JSON, считаем баланс скобок.
    Как только баланс стал 0 - нашли конец валидного JSON.
    Обрезаем всё после него и добавляем недостающие скобки если нужно.
    
    ВОЗВРАЩАЕТ:
    - Валидный JSON строка или None если не удалось извлечь
    """
    if not json_str or not json_str.strip():
        return None
    
    # Находим первую { или [
    start_idx = -1
    for i, char in enumerate(json_str):
        if char in '{[':
            start_idx = i
            break
    
    if start_idx == -1:
        return None  # Нет открывающих скобок
    
    # Идём посимвольно и считаем баланс
    brace_count = 0
    bracket_count = 0
    in_string = False
    escape_next = False
    last_valid_end = -1
    
    for i in range(start_idx, len(json_str)):
        char = json_str[i]
        
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
        
        # Считаем скобки
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
        elif char == '[':
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1
        
        # Проверяем что баланс стал 0 (все скобки закрыты)
        if brace_count == 0 and bracket_count == 0:
            last_valid_end = i + 1
            break  # Нашли конец валидного JSON
    
    if last_valid_end == -1:
        # Не удалось найти конец - пробуем добавить скобки
        # Берём от start_idx до последнего значимого символа
        stripped = json_str[start_idx:].rstrip()
        last_meaningful = -1
        for i in range(len(stripped) - 1, -1, -1):
            if stripped[i] in '}"\'0123456789' or stripped[i].isalpha():
                last_meaningful = i
                break
        
        if last_meaningful == -1:
            return None
        
        core = stripped[:last_meaningful + 1]
        
        # Пересчитываем баланс
        b_count = br_count = 0
        in_str = esc = False
        for c in core:
            if esc:
                esc = False
                continue
            if c == '\\' and in_str:
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if not in_str:
                if c == '{': b_count += 1
                elif c == '}': b_count -= 1
                elif c == '[': br_count += 1
                elif c == ']': br_count -= 1
        
        # Добавляем недостающие
        while br_count > 0:
            core += ']'
            br_count -= 1
        while b_count > 0:
            core += '}'
            b_count -= 1
        
        return core
    
    # Нашли валидный конец - возвращаем
    return json_str[start_idx:last_valid_end]


def extract_json_from_response(content: str) -> str:
    """
    Извлечение JSON из текста ответа (если есть обёртка).

    АЛГОРИТМ:
    1. Markdown блоки ```json ... ```
    2. Markdown блоки ``` ... ```
    3. Первая { и последняя } в тексте
    4. Первый [ и последний ] в тексте

    ПАРАМЕТРЫ:
    - content: Текст ответа LLM

    ВОЗВРАЩАЕТ:
    - JSON строка (или исходный текст если JSON не найден)
    """
    # Шаг 1: Ищем markdown блоки с json (приоритет)
    markdown_json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(markdown_json_pattern, content, re.DOTALL | re.IGNORECASE)
    for match in matches:
        json_content = match.strip()
        if json_content.startswith('{') or json_content.startswith('['):
            return json_content

    # Шаг 2: Ищем просто ``` без указания языка
    markdown_pattern = r'```\s*(.*?)\s*```'
    matches = re.findall(markdown_pattern, content, re.DOTALL)
    for match in matches:
        json_content = match.strip()
        if json_content.startswith('{') or json_content.startswith('['):
            return json_content

    # Шаг 3: Ищем первую { и последнюю } в тексте
    start = content.find('{')
    end = content.rfind('}') + 1

    if start != -1 and end > start:
        return content[start:end]

    # Шаг 4: Ищем массив [...]
    start = content.find('[')
    end = content.rfind(']') + 1

    if start != -1 and end > start:
        return content[start:end]

    # Ничего не нашли - возвращаем как есть
    return content

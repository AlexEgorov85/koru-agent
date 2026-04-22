"""
Валидация результатов рассуждения для ReAct стратегии

АРХИТЕКТУРА:
- Результаты LLM валидируются через Pydantic модель из контракта
- Контракт загружается при инициализации: behavior.react.think_output_v1.0.0
- Используется self.output_contracts["behavior.react.think"].pydantic_schema

NOTE: Валидация происходит на уровне LLM провайдера (через .validate() на Pydantic модели)
или в ReActPattern при извлечении результата.
"""
import json
import re
from typing import Any, Dict, Optional

from core.infrastructure.event_bus.unified_event_bus import EventType, EventDomain, UnifiedEventBus


def _fix_missing_commas_simple(json_str: str) -> str:
    """
    Упрощённая функция для исправления отсутствующих запятых в JSON.
    """
    patterns = [
        (r'(")\s*\n\s*(")', r'\1,\n\2'),
        (r'(\}|\])\s*\n\s*(")', r'\1,\n\2'),
        (r'(\d|true|false|null)\s*\n\s*(")', r'\1,\n\2'),
        (r'(\})\s*\n\s*(\{)', r'\1,\n\2'),
    ]
    
    fixed = json_str
    for pattern, replacement in patterns:
        fixed = re.sub(pattern, replacement, fixed)
    
    return fixed


def _fix_missing_closing_brackets_simple(json_str: str) -> str:
    """
    Исправить отсутствующие закрывающие скобки в JSON.
    """
    stripped = json_str.rstrip()
    
    last_meaningful_idx = -1
    for i in range(len(stripped) - 1, -1, -1):
        char = stripped[i]
        if char in '}"\'0123456789' or char.isalpha():
            last_meaningful_idx = i
            break
    
    if last_meaningful_idx == -1:
        return json_str
    
    core_json = stripped[:last_meaningful_idx + 1]
    
    brace_count = 0
    bracket_count = 0
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
    
    fixed = core_json
    
    while bracket_count > 0:
        fixed += ']'
        bracket_count -= 1
    
    while brace_count > 0:
        fixed += '}'
        brace_count -= 1
    
    return fixed


def _fix_json_trailing_garbage_simple(json_str: str) -> str:
    """
    Удалить мусор в конце JSON.
    """
    last_brace = json_str.rfind('}')
    last_bracket = json_str.rfind(']')
    last_closing = max(last_brace, last_bracket)
    
    if last_closing != -1:
        after = json_str[last_closing + 1:].strip()
        if not after or all(c in '\n\r\t .,;' for c in after):
            return json_str[:last_closing + 1]
    
    return json_str


async def parse_llm_json_response(
    result: str,
    event_bus: Optional[UnifiedEventBus] = None,
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Парсинг JSON из строки ответа LLM.
    
    ARGS:
        result: строка ответа LLM (может содержать markdown, несколько JSON блоков)
        event_bus: опциональная шина событий для логирования
        session_id: опциональный ID сессии
        agent_id: опциональный ID агента
    
    RETURNS:
        распарсенный dict или None если не удалось распарсить
    """
    
    cleaned = result
    
    # Удаляем markdown ```json ... ``` блоки
    markdown_json_pattern = r'```json\s*(.*?)\s*```'
    markdown_matches = re.findall(markdown_json_pattern, cleaned, re.DOTALL)
    
    if markdown_matches:
        cleaned = markdown_matches[-1]
    else:
        cleaned = re.sub(r'```.*?```', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'```json', '', cleaned)
        cleaned = re.sub(r'```', '', cleaned)
    
    cleaned = cleaned.strip()
    
    # Ищем начало JSON
    json_start_patterns = [
        cleaned.find('{"'), cleaned.find('{ "'),
        cleaned.find('{\n'), cleaned.find('{\r\n'),
    ]
    json_start_idx = next((idx for idx in json_start_patterns if idx >= 0), -1)
    
    if json_start_idx < 0:
        json_start_idx = cleaned.rfind('{')
    
    if json_start_idx > 0:
        cleaned = cleaned[json_start_idx:]
    
    # Исправляем двойные скобки
    if cleaned.startswith('{{'):
        cleaned = '{' + cleaned[2:]
    
    # Находим все JSON объекты
    json_objects = []
    depth = 0
    start_idx = None
    
    for i, char in enumerate(cleaned):
        if char == '{':
            if depth == 0:
                start_idx = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start_idx is not None:
                json_objects.append(cleaned[start_idx:i+1])
                start_idx = None
    
    # Пытаемся распарсить каждый JSON с конца
    for json_str in reversed(json_objects):
        try:
            fixed_str = re.sub(r'\}\}', '}', json_str)
            fixed_str = re.sub(r'^\{\{', '{', fixed_str)
            return json.loads(fixed_str)
        except json.JSONDecodeError:
            # Попытка исправить: запятые, скобки, мусор
            try:
                fixed = json_str
                # Исправляем запятые
                fixed = _fix_missing_commas_simple(fixed)
                # Исправляем скобки
                fixed = _fix_missing_closing_brackets_simple(fixed)
                # Удаляем мусор
                fixed = _fix_json_trailing_garbage_simple(fixed)
                
                fixed_str = re.sub(r'\}\}', '}', fixed)
                fixed_str = re.sub(r'^\{\{', '{', fixed_str)
                return json.loads(fixed_str)
            except json.JSONDecodeError:
                continue
    
    if event_bus:
        await event_bus.publish(
            EventType.LOG_WARNING,
            data={"message": f"Не удалось распарсить JSON из строки: {result}."},
            session_id=session_id,
            domain=EventDomain.AGENT
        )
    return None
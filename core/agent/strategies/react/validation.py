"""
Валидация результатов рассуждения для ReAct стратегии

АРХИТЕКТУРА:
- Результаты LLM валидируются через Pydantic модель из контракта
- Контракт загружается при инициализации: behavior.react.think_output_v1.0.0
- Используется self.output_contracts["behavior.react.think"].pydantic_schema

NOTE: Валидация происходит на уровне LLM провайдера (через .validate() на Pydantic модели)
или в ReActPattern при извлечении результата.
"""
import logging
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
import json
import re
from typing import Any, Dict, Optional


def parse_llm_json_response(result: str) -> Optional[Dict[str, Any]]:
    """
    Парсинг JSON из строки ответа LLM.
    
    ARGS:
        result: строка ответа LLM (может содержать markdown, несколько JSON блоков)
    
    RETURNS:
        распарсенный dict или None если не удалось распарсить
    """
    logger = logging.getLogger(__name__)
    
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
            continue
    
    logger.warning(f"Не удалось распарсить JSON из строки: {result[:200]}...")
    return None
"""
JSON Parser для валидации структурированных ответов LLM.

ИСПОЛЬЗУЕТСЯ:
- LLMOrchestrator._validate_structured_response()
- (BaseLLMProvider — до удаления)

ПРИМЕР:
    result = validate_structured_response(raw_content, schema)
    if result['success']:
        parsed = result['parsed']
"""
import json
from typing import Dict, Any, Optional, Type, List
from pydantic import ValidationError, create_model


def validate_structured_response(
    raw_content: str,
    schema: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Валидация структурированного ответа.
    
    ПРОВЕРКИ:
    1. JSON парсинг
    2. Соответствие схеме через Pydantic (если указана)
    3. Полнота ответа (не обрезан ли)
    
    ПАРАМЕТРЫ:
    - raw_content: Сырой текст ответа
    - schema: JSON Schema для валидации (опционально)
    
    ВОЗВРАЩАЕТ:
    - Dict с полями:
      - success: bool — прошла ли валидация
      - error_type: str | None — тип ошибки
      - error_message: str | None — сообщение об ошибке
      - parsed: Any | None — распарсенные данные
    """
    # Проверка 1: JSON парсинг
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error_type": "json_error",
            "error_message": f"JSON парсинг не удался: {str(e)}",
            "parsed": None
        }
    
    # Проверка 2: Соответствие схеме через Pydantic
    if schema:
        try:
            # Создаём динамическую Pydantic модель из схемы
            DynamicModel = schema_to_pydantic_model(schema, "StructuredOutput")
            
            # Валидируем через Pydantic
            parsed_content = DynamicModel.model_validate(parsed)
            
            return {
                "success": True,
                "error_type": None,
                "error_message": None,
                "parsed": parsed_content
            }
            
        except ValidationError as e:
            error_details = []
            for error in e.errors():
                field = ".".join(str(x) for x in error.get('loc', []))
                msg = error.get('msg', 'validation error')
                error_details.append(f"{field}: {msg}")
            
            return {
                "success": False,
                "error_type": "validation_error",
                "error_message": f"Валидация схемы не пройдена: {'; '.join(error_details)}",
                "parsed": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error_type": "validation_error",
                "error_message": f"Ошибка валидации схемы: {type(e).__name__}: {str(e)}",
                "parsed": None
            }
    
    # Схема не указана — только JSON парсинг
    return {
        "success": True,
        "error_type": None,
        "error_message": None,
        "parsed": parsed
    }


def schema_to_pydantic_model(
    schema: Dict[str, Any],
    model_name: str = "DynamicModel"
) -> Type:
    """
    Создаёт Pydantic модель из JSON Schema.
    
    ПАРАМЕТРЫ:
    - schema: JSON Schema dict
    - model_name: Имя создаваемой модели
    
    ВОЗВРАЩАЕТ:
    - Pydantic model class
    """
    def schema_field_to_type(field_schema: Dict[str, Any], field_name: str = "field"):
        """Преобразует JSON Schema поле в Python тип."""
        field_type = field_schema.get('type')
        
        if field_type == 'string':
            return str
        elif field_type == 'integer':
            return int
        elif field_type == 'number':
            return float
        elif field_type == 'boolean':
            return bool
        elif field_type == 'array':
            items = field_schema.get('items', {})
            item_type = schema_field_to_type(items, f"{field_name}_item")
            return List[item_type]
        elif field_type == 'object':
            nested_model = schema_to_pydantic_model(field_schema, f"{field_name.title()}Object")
            return nested_model
        else:
            return Any
    
    properties = schema.get('properties', {})
    required = set(schema.get('required', []))
    
    fields = {}
    for field_name, field_schema in properties.items():
        field_type = schema_field_to_type(field_schema, field_name)
        is_required = field_name in required
        
        if is_required:
            fields[field_name] = (field_type, ...)
        else:
            fields[field_name] = (Optional[field_type], None)
    
    return create_model(model_name, **fields)


def extract_json_from_response(content: str) -> str:
    """
    Извлечение JSON из текста ответа (если есть обёртка).

    ПАРАМЕТРЫ:
    - content: Текст ответа LLM

    ВОЗВРАЩАЕТ:
    - JSON строка
    """
    import re
    
    # Шаг 1: Ищем markdown блоки с json (приоритет)
    markdown_json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(markdown_json_pattern, content, re.DOTALL | re.IGNORECASE)
    if matches:
        # Нашли markdown блок - берём первое совпадение
        json_content = matches[0].strip()
        # Проверяем что это валидный JSON (начинается с { или [)
        if json_content.startswith('{') or json_content.startswith('['):
            return json_content
    
    # Шаг 2: Ищем просто ``` без указания языка
    markdown_pattern = r'```\s*(.*?)\s*```'
    matches = re.findall(markdown_pattern, content, re.DOTALL)
    if matches:
        json_content = matches[0].strip()
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

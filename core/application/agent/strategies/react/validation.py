"""
Валидация результатов рассуждения для ReAct стратегии в новой архитектуре
"""
import logging
from typing import Any, Dict


def validate_reasoning_result(result: Any) -> Dict[str, Any]:
    """
    Валидирует результат структурированного рассуждения.

    ARGS:
    - result: результат рассуждения для валидации

    RETURNS:
    - Валидированный результат в виде словаря
    """
    logger = logging.getLogger(__name__)

    try:
        # Если результат уже словарь, используем его напрямую
        if isinstance(result, dict):
            validated_result = result
        # Если результат - объект Pydantic, конвертируем его в словарь
        elif hasattr(result, 'model_dump'):
            validated_result = result.model_dump()
        # Если результат - строка, пытаемся распарсить как JSON
        elif isinstance(result, str):
            import json
            import re
            
            # Очищаем строку от markdown-разметки ```json ... ```
            cleaned = re.sub(r'^```json\s*', '', result)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            cleaned = cleaned.strip()
            
            # Пытаемся найти первый полный JSON объект
            # Ищем сбалансированные фигурные скобки
            depth = 0
            start_idx = None
            json_str = None
            
            for i, char in enumerate(cleaned):
                if char == '{':
                    if depth == 0:
                        start_idx = i
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        json_str = cleaned[start_idx:i+1]
                        break
            
            if json_str:
                validated_result = json.loads(json_str)
            else:
                # Если не нашли сбалансированный JSON, пробуем распарсить всю строку
                validated_result = json.loads(cleaned)
        else:
            raise ValueError(f"Неподдерживаемый тип результата рассуждения: {type(result)}")
        
        # Нормализация результата - приводим к ожидаемому формату
        validated_result = _normalize_reasoning_result(validated_result)
        
        # Проверяем наличие обязательных полей
        if 'analysis' not in validated_result:
            validated_result['analysis'] = {
                'current_situation': 'Неизвестно',
                'progress_assessment': 'Неизвестно',
                'confidence': 0.5,
                'errors_detected': False,
                'consecutive_errors': 0,
                'execution_time': 0,
                'no_progress_steps': 0
            }

        if 'recommended_action' not in validated_result:
            validated_result['recommended_action'] = {
                'action_type': 'execute_capability',
                'capability_name': 'generic.execute',
                'parameters': {'input': 'Продолжить выполнение задачи'},
                'reasoning': 'Действие по умолчанию'
            }

        # Устанавливаем значения по умолчанию для опциональных полей
        if 'needs_rollback' not in validated_result:
            validated_result['needs_rollback'] = False

        if 'rollback_steps' not in validated_result:
            validated_result['rollback_steps'] = 1

        if 'action_type' not in validated_result:
            validated_result['action_type'] = 'execute_capability'

        logger.debug("Результат рассуждения успешно валидирован")
        return validated_result

    except Exception as e:
        logger.error(f"Ошибка при валидации результата рассуждения: {str(e)}", exc_info=True)

        # Возвращаем минимально допустимый результат в случае ошибки
        return {
            'analysis': {
                'current_situation': 'Ошибка валидации',
                'progress_assessment': 'Неизвестно',
                'confidence': 0.1,
                'errors_detected': True,
                'consecutive_errors': 1,
                'execution_time': 0,
                'no_progress_steps': 0
            },
            'recommended_action': {
                'action_type': 'execute_capability',
                'capability_name': 'generic.execute',
                'parameters': {'input': 'Продолжить выполнение задачи'},
                'reasoning': f'fallback после ошибки валидации: {str(e)}'
            },
            'needs_rollback': False,
            'rollback_steps': 1,
            'action_type': 'execute_capability'
        }


def _normalize_reasoning_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализует результат рассуждения к ожидаемому формату.
    
    LLM может возвращать разные форматы - приводим их к единому виду.
    """
    # Если recommended_action - строка, преобразуем в dict
    if isinstance(result.get('recommended_action'), str):
        action_str = result['recommended_action']
        # Пытаемся извлечь имя capability из строки
        # Например: "Выполнить действие: book_library.search_books с параметрами..."
        import re
        cap_match = re.search(r'([a-z_]+\.[a-z_]+)', action_str)
        capability_name = cap_match.group(1) if cap_match else 'generic.execute'
        
        result['recommended_action'] = {
            'action_type': 'execute_capability',
            'capability_name': capability_name,
            'parameters': {'input': action_str},
            'reasoning': action_str
        }
    
    # Если analysis - строка, преобразуем в dict
    if isinstance(result.get('analysis'), str):
        result['analysis'] = {
            'current_situation': result['analysis'],
            'progress_assessment': 'Неизвестно',
            'confidence': result.get('confidence', 0.5),
            'errors_detected': False,
            'consecutive_errors': 0,
            'execution_time': 0,
            'no_progress_steps': 0
        }
    
    # Если есть поле confidence на верхнем уровне, переносим в analysis
    if 'confidence' in result and isinstance(result.get('analysis'), dict):
        result['analysis']['confidence'] = result['confidence']
        del result['confidence']
    
    return result
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
            validated_result = json.loads(result)
        else:
            raise ValueError(f"Неподдерживаемый тип результата рассуждения: {type(result)}")
        
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
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
            
            # Пытаемся найти первый полный JSON объект (сбалансированные скобки)
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
                validated_result = json.loads(cleaned)
        else:
            raise ValueError(f"Неподдерживаемый тип результата рассуждения: {type(result)}")
        
        # Проверяем наличие обязательных полей и устанавливаем значения по умолчанию
        if 'analysis' not in validated_result:
            validated_result['analysis'] = {}
        
        analysis = validated_result['analysis']
        if 'current_situation' not in analysis:
            analysis['current_situation'] = str(analysis.get('thoughts', 'Неизвестно'))
        if 'progress_assessment' not in analysis:
            analysis['progress_assessment'] = 'Неизвестно'
        if 'confidence' not in analysis:
            analysis['confidence'] = float(analysis.get('confidence_level', 0.5))
        if 'errors_detected' not in analysis:
            analysis['errors_detected'] = False
        
        if 'recommended_action' not in validated_result:
            validated_result['recommended_action'] = {}
        
        action = validated_result['recommended_action']
        if 'capability_name' not in action:
            # Пробуем найти в action_name (старое имя поля)
            action['capability_name'] = action.get('action_name', 'generic.execute')
        if 'action_type' not in action:
            action['action_type'] = 'execute_capability'
        if 'parameters' not in action:
            action['parameters'] = action.get('parameters', {})
        if 'reasoning' not in action:
            action['reasoning'] = action.get('reason', 'Действие по умолчанию')
        
        if 'needs_rollback' not in validated_result:
            validated_result['needs_rollback'] = False
        
        if 'rollback_steps' not in validated_result:
            validated_result['rollback_steps'] = 0

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
                'errors_detected': True
            },
            'recommended_action': {
                'action_type': 'execute_capability',
                'capability_name': 'generic.execute',
                'parameters': {'input': 'Продолжить выполнение задачи'},
                'reasoning': f'fallback после ошибки валидации: {str(e)}'
            },
            'needs_rollback': False,
            'rollback_steps': 0
        }
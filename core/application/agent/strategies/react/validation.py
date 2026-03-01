"""
Валидация результатов рассуждения для ReAct стратегии в новой архитектуре
"""
import logging
from typing import Any, Dict


def validate_reasoning_result(result: Any) -> Dict[str, Any]:
    """
    Валидирует результат структурированного рассуждения.
    
    СООТВЕТСТВУЕТ КОНТРАКТУ: behavior.react.think_output_v1.0.0
    
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
        # Если результат - StructuredLLMResponse, извлекаем parsed_content
        elif hasattr(result, 'parsed_content') and hasattr(result, 'raw_response'):
            # StructuredLLMResponse — извлекаем содержимое
            parsed = result.parsed_content
            if hasattr(parsed, 'model_dump'):
                validated_result = parsed.model_dump()
            elif isinstance(parsed, dict):
                validated_result = parsed
            else:
                # Пытаемся конвертировать в dict
                validated_result = vars(parsed) if hasattr(parsed, '__dict__') else {'data': str(parsed)}
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
        
        # Проверяем наличие обязательных полей (согласно контракту)
        if 'thought' not in validated_result:
            validated_result['thought'] = 'Рассуждение не предоставлено'
        
        if 'analysis' not in validated_result:
            validated_result['analysis'] = {}
        
        analysis = validated_result['analysis']
        if 'progress' not in analysis:
            analysis['progress'] = 'Неизвестно'
        if 'current_state' not in analysis:
            analysis['current_state'] = str(analysis.get('current_situation', 'Неизвестно'))
        if 'issues' not in analysis:
            analysis['issues'] = []
        
        if 'decision' not in validated_result:
            validated_result['decision'] = {}
        
        decision = validated_result['decision']
        # next_action — это capability_name в новой архитектуре
        if 'next_action' not in decision:
            # Пробуем найти в capability_name (альтернативное имя)
            decision['next_action'] = decision.get('capability_name', 'generic.execute')
        if 'reasoning' not in decision:
            decision['reasoning'] = decision.get('reason', 'Действие по умолчанию')
        if 'parameters' not in decision:
            decision['parameters'] = decision.get('parameters', {})
        if 'expected_outcome' not in decision:
            decision['expected_outcome'] = 'Неизвестно'
        
        if 'confidence' not in validated_result:
            validated_result['confidence'] = 0.5
        
        if 'stop_condition' not in validated_result:
            validated_result['stop_condition'] = False
        
        if 'stop_reason' not in validated_result:
            validated_result['stop_reason'] = None
        
        if 'alternative_actions' not in validated_result:
            validated_result['alternative_actions'] = []

        # logger.debug("Результат рассуждения успешно валидирован")
        return validated_result

    except Exception as e:
        self.event_bus_logger.error(f"Ошибка при валидации результата рассуждения: {str(e)}", exc_info=True)

        # Возвращаем минимально допустимый результат в случае ошибки
        return {
            'thought': 'Ошибка валидации',
            'analysis': {
                'progress': 'Неизвестно',
                'current_state': 'Ошибка валидации',
                'issues': []
            },
            'decision': {
                'next_action': 'generic.execute',
                'reasoning': f'fallback после ошибки валидации: {str(e)}',
                'parameters': {'input': 'Продолжить выполнение задачи'},
                'expected_outcome': 'Неизвестно'
            },
            'confidence': 0.1,
            'stop_condition': False,
            'stop_reason': None,
            'alternative_actions': []
        }
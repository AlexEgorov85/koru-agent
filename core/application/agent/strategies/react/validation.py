"""
Валидация результатов рассуждения для ReAct стратегии в новой архитектуре

АРХИТЕКТУРА:
- Типизированные объекты вместо dict
- Dataclass для структур данных
"""
import logging
import json
import re
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AnalysisResult:
    """Результат анализа состояния."""
    progress: str = "Неизвестно"
    current_state: str = "Неизвестно"
    issues: List[str] = field(default_factory=list)
    current_situation: Optional[str] = None


@dataclass
class DecisionResult:
    """Результат решения о действии."""
    next_action: str = "generic.execute"
    reasoning: str = "Действие по умолчанию"
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = "Неизвестно"
    capability_name: Optional[str] = None  # Альтернативное имя
    reason: Optional[str] = None  # Альтернативное имя для reasoning


@dataclass
class ReasoningResult:
    """
    Типизированный результат структурированного рассуждения.
    
    СООТВЕТСТВУЕТ КОНТРАКТУ: behavior.react.think_output_v1.0.0
    
    ATTRIBUTES:
    - thought: Текст рассуждения
    - analysis: Анализ состояния
    - decision: Решение о действии
    - confidence: Уверенность (0.0-1.0)
    - stop_condition: Флаг остановки
    - stop_reason: Причина остановки
    - alternative_actions: Альтернативные действия
    - available_capabilities: Доступные capability (добавляется позже)
    """
    thought: str = "Рассуждение не предоставлено"
    analysis: Optional[AnalysisResult] = None
    decision: Optional[DecisionResult] = None
    confidence: float = 0.5
    stop_condition: bool = False
    stop_reason: Optional[str] = None
    alternative_actions: List[str] = field(default_factory=list)
    available_capabilities: List[Any] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в dict для обратной совместимости."""
        return {
            'thought': self.thought,
            'analysis': {
                'progress': self.analysis.progress if self.analysis else 'Неизвестно',
                'current_state': self.analysis.current_state if self.analysis else 'Неизвестно',
                'issues': self.analysis.issues if self.analysis else [],
            },
            'decision': {
                'next_action': self.decision.next_action if self.decision else 'generic.execute',
                'reasoning': self.decision.reasoning if self.decision else 'Действие по умолчанию',
                'parameters': self.decision.parameters if self.decision else {},
                'expected_outcome': self.decision.expected_outcome if self.decision else 'Неизвестно',
            },
            'confidence': self.confidence,
            'stop_condition': self.stop_condition,
            'stop_reason': self.stop_reason,
            'alternative_actions': self.alternative_actions,
            'available_capabilities': self.available_capabilities,
        }


def validate_reasoning_result(result: Any) -> ReasoningResult:
    """
    Валидирует результат структурированного рассуждения.

    СООТВЕТСТВУЕТ КОНТРАКТУ: behavior.react.think_output_v1.0.0

    ARGS:
    - result: результат рассуждения для валидации

    RETURNS:
    - ReasoningResult: типизированный результат валидации
    """
    logger = logging.getLogger(__name__)

    # === ДИАГНОСТИКА: Логируем что пришло ===
    logger.info(f"🔍 validate_reasoning_result: тип result = {type(result).__name__}")
    logger.info(f"📍 Вызов из:\n{''.join(traceback.format_stack()[-3:-1])}")
    if isinstance(result, str):
        logger.info(f"📝 result (строка, {len(result)} симв): {result[:300]}...")
    elif isinstance(result, dict):
        logger.info(f"📝 result (dict): ключи = {list(result.keys())}")
    else:
        logger.info(f"📝 result: {result}")

    try:
        # === 1. Извлечение данных из результата ===
        validated_dict = None
        
        # Если результат уже словарь, используем его напрямую
        if isinstance(result, dict):
            validated_dict = result
        # Если результат - StructuredLLMResponse, извлекаем parsed_content
        elif hasattr(result, 'parsed_content') and hasattr(result, 'raw_response'):
            # StructuredLLMResponse — извлекаем содержимое
            parsed = result.parsed_content
            if hasattr(parsed, 'model_dump'):
                validated_dict = parsed.model_dump()
            elif isinstance(parsed, dict):
                validated_dict = parsed
            else:
                # Пытаемся конвертировать в dict
                validated_dict = vars(parsed) if hasattr(parsed, '__dict__') else {'data': str(parsed)}
        # Если результат - объект Pydantic, конвертируем его в словарь
        elif hasattr(result, 'model_dump'):
            validated_dict = result.model_dump()
        # Если результат - строка, пытаемся распарсить как JSON
        elif isinstance(result, str):
            validated_dict = _parse_json_from_string(result, logger)
        
        # Если не удалось извлечь dict, возвращаем fallback
        if validated_dict is None:
            logger.error(f"Неподдерживаемый тип результата рассуждения: {type(result)}")
            return _create_fallback_result(f"Неподдерживаемый тип: {type(result)}", "validation_error")

        # === 2. Валидация и заполнение обязательных полей ===
        return _build_reasoning_result(validated_dict, logger)

    except Exception as e:
        logger.error(f"Ошибка при валидации результата рассуждения: {str(e)}", exc_info=True)
        return _create_fallback_result(f"Ошибка валидации: {str(e)}", "validation_error")


def _parse_json_from_string(result: str, logger: logging.Logger) -> Optional[Dict[str, Any]]:
    """Парсинг JSON из строки результата."""
    import re

    # Очищаем строку от markdown-разметки ```json ... ```
    cleaned = result
    cleaned = re.sub(r'```json', '', cleaned)
    cleaned = re.sub(r'```', '', cleaned)
    cleaned = cleaned.strip()

    # Ищем первый {", который начинает настоящий JSON ответ LLM
    json_start_patterns = [
        cleaned.find('{"'), cleaned.find('{ "'),
        cleaned.find('{{"'), cleaned.find('{{ "'),
        cleaned.find('{\n'), cleaned.find('{{\n'),
        cleaned.find('{{ \n'), cleaned.find('{{  \n'),
        cleaned.find('{\r\n'), cleaned.find('{{\r\n'),
    ]
    json_start_idx = -1
    for idx in json_start_patterns:
        if idx >= 0:
            if json_start_idx < 0 or idx < json_start_idx:
                json_start_idx = idx

    if json_start_idx < 0:
        json_start_idx = cleaned.rfind('{')

    if json_start_idx > 0:
        cleaned = cleaned[json_start_idx:]

    # Исправляем двойные скобки
    if cleaned.startswith('{{'):
        cleaned = '{' + cleaned[2:]

    # Считаем скобки и удаляем лишние закрывающие
    open_braces = cleaned.count('{')
    close_braces = cleaned.count('}')
    if close_braces > open_braces:
        excess = close_braces - open_braces
        logger.info(f"Найдено лишних закрывающих скобок: {excess}")
        cleaned_list = list(cleaned)
        removed = 0
        i = len(cleaned_list) - 1
        while i >= 0 and removed < excess:
            if cleaned_list[i] == '}':
                cleaned_list[i] = ''
                removed += 1
            i -= 1
        cleaned = ''.join(cleaned_list)

    # Находим ВСЕ JSON объекты
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
    for idx in range(len(json_objects) - 1, -1, -1):
        try:
            return json.loads(json_objects[idx])
        except json.JSONDecodeError as e:
            logger.warning(f"JSON #{idx+1} невалидный: {e}")
            continue

    # Пробуем исправить двойные скобки
    if len(json_objects) > 0:
        for idx in range(len(json_objects) - 1, -1, -1):
            json_str = json_objects[idx]
            fixed_str = re.sub(r'\}\}', '}', json_str)
            fixed_str = re.sub(r'^\{\{', '{', fixed_str)
            try:
                return json.loads(fixed_str)
            except json.JSONDecodeError:
                continue

    logger.warning(f"Не удалось распарсить JSON из строки: {result[:200]}...")
    return None


def _build_reasoning_result(validated_dict: Dict[str, Any], logger: logging.Logger) -> ReasoningResult:
    """Построение ReasoningResult из dict."""
    # Проверяем наличие обязательных полей
    thought = validated_dict.get('thought', 'Рассуждение не предоставлено')
    
    # Анализ
    analysis_dict = validated_dict.get('analysis', {})
    analysis = AnalysisResult(
        progress=analysis_dict.get('progress', 'Неизвестно'),
        current_state=analysis_dict.get('current_state', str(analysis_dict.get('current_situation', 'Неизвестно'))),
        issues=analysis_dict.get('issues', [])
    )
    
    # Решение
    decision_dict = validated_dict.get('decision', {})
    
    # next_action — проверяем на верхнем уровне
    next_action = decision_dict.get('next_action')
    if not next_action:
        # Пробуем найти в capability_name
        next_action = decision_dict.get('capability_name', 'generic.execute')
        # Или на верхнем уровне
        if 'next_action' in validated_dict:
            next_action = validated_dict['next_action']
    
    # parameters — проверяем на верхнем уровне
    parameters = decision_dict.get('parameters')
    if not parameters and 'parameters' in validated_dict:
        parameters = validated_dict['parameters']
    
    decision = DecisionResult(
        next_action=next_action,
        reasoning=decision_dict.get('reasoning', decision_dict.get('reason', 'Действие по умолчанию')),
        parameters=parameters or {},
        expected_outcome=decision_dict.get('expected_outcome', 'Неизвестно')
    )
    
    return ReasoningResult(
        thought=thought,
        analysis=analysis,
        decision=decision,
        confidence=validated_dict.get('confidence', 0.5),
        stop_condition=validated_dict.get('stop_condition', False),
        stop_reason=validated_dict.get('stop_reason'),
        alternative_actions=validated_dict.get('alternative_actions', [])
    )


def _create_fallback_result(error_msg: str, error_type: str) -> ReasoningResult:
    """Создание fallback результата при ошибке."""
    return ReasoningResult(
        thought='Ошибка валидации',
        analysis=AnalysisResult(
            progress='Неизвестно',
            current_state=error_msg,
            issues=[]
        ),
        decision=DecisionResult(
            next_action='final_answer.generate',
            reasoning=f'fallback после ошибки: {error_type}',
            parameters={'input': 'Продолжить выполнение задачи'},
            expected_outcome='Неизвестно'
        ),
        confidence=0.1,
        stop_condition=False,
        stop_reason=error_type
    )

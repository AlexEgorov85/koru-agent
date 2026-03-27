"""
Валидация результатов рассуждения для ReAct стратегии

АРХИТЕКТУРА:
- Валидация выполняется через Pydantic модель из контракта
- Контракт загружается при инициализации: behavior.react.think_output_v1.0.0
- Использует contract.pydantic_schema для валидации
"""
import logging
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
import json
import re
import traceback
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError


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
    - result: результат рассуждения для валидации (Pydantic модель или dict)

    RETURNS:
    - ReasoningResult: типизированный результат валидации
    
    ARCHITECTURE:
    - Принимает Pydantic модель напрямую (без model_dump)
    - Конвертирует в dict только для валидации полей
    - Возвращает ReasoningResult объект для типизированного доступа
    """
    logger = logging.getLogger(__name__)
      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    # === ДИАГНОСТИКА: Логируем что пришло ===
    logger.info(f"🔍 validate_reasoning_result: тип result = {type(result).__name__}")
      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    logger.info(f"📍 Вызов из:\n{''.join(traceback.format_stack()[-3:-1])}")
      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    if isinstance(result, str):
        logger.info(f"📝 result (строка, {len(result)} симв): {result[:300]}...")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    elif hasattr(result, '__class__') and hasattr(result, '__dict__'):
        # Pydantic модель или dataclass
        logger.info(f"📝 result (объект {result.__class__.__name__}): {result}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    elif isinstance(result, dict):
        logger.info(f"📝 result (dict): ключи = {list(result.keys())}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    else:
        logger.info(f"📝 result: {result}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    try:
        # === 1. Извлечение данных из результата ===
        validated_dict = None

        # Если результат уже словарь, используем его напрямую
        if isinstance(result, dict):
            validated_dict = result
        # Если результат - Pydantic модель, извлекаем данные через model_fields
        elif hasattr(result, 'model_fields') and hasattr(result, 'model_dump'):
            # ✅ ИСПРАВЛЕНО: Принимаем Pydantic модель напрямую
            # Конвертируем в dict только для валидации
            validated_dict = result.model_dump()
            logger.info(f"✅ Pydantic модель конвертирована: {list(validated_dict.keys())}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
        # Если результат - dataclass или другой объект с __dict__
        elif hasattr(result, '__dict__'):
            validated_dict = vars(result)
        # Если результат - строка, пытаемся распарсить как JSON
        elif isinstance(result, str):
            validated_dict = _parse_json_from_string(result, logger)

        # Если не удалось извлечь dict, возвращаем fallback
        if validated_dict is None:
            logger.error(f"Неподдерживаемый тип результата рассуждения: {type(result)}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return _create_fallback_result(f"Неподдерживаемый тип: {type(result)}", "validation_error")

        # === 2. Валидация и заполнение обязательных полей ===
        return _build_reasoning_result(validated_dict, logger)

    except Exception as e:
        logger.error(f"Ошибка при валидации результата рассуждения: {str(e)}", exc_info=True)
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return _create_fallback_result(f"Ошибка валидации: {str(e)}", "validation_error")


def _parse_json_from_string(result: str, logger: logging.Logger) -> Optional[Dict[str, Any]]:
    """Парсинг JSON из строки результата."""
    import re

    # === 1. УДАЛЕНИЕ MARKDOWN-РАЗМЕТКИ ===
    cleaned = result
    
    # Удаляем ```json ... ``` блоки
    markdown_json_pattern = r'```json\s*(.*?)\s*```'
    markdown_matches = re.findall(markdown_json_pattern, cleaned, re.DOTALL)
    
    if markdown_matches:
        # БЕРЁМ ПОСЛЕДНИЙ JSON блок (он обычно наиболее полный)
        cleaned = markdown_matches[-1]
        logger.info(f"Найдено {len(markdown_matches)} markdown JSON блоков, берём последний: {len(cleaned)} символов")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    else:
        # Удаляем любые ``` блоки
        cleaned = re.sub(r'```.*?```', '', cleaned, flags=re.DOTALL)
        # Очищаем от markdown-разметки
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
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
    """
    Создание fallback результата при ошибке.
    
    ВАЖНО: Fallback НЕ должен генерировать final_answer.generate,
    так как это приводит к преждевременному завершению агента без данных.
    Вместо этого возвращаем RETRY или generic.execute для продолжения работы.
    """
    return ReasoningResult(
        thought='Ошибка валидации результата рассуждения',
        analysis=AnalysisResult(
            progress='Неизвестно',
            current_state=error_msg,
            issues=[f"Тип ошибки: {error_type}"]
        ),
        decision=DecisionResult(
            next_action='generic.execute',  # ← Используем generic вместо final_answer
            reasoning=f'fallback после ошибки: {error_type}. Требуется повторная попытка рассуждения.',
            parameters={
                'input': 'Продолжить выполнение задачи. Предыдущая попытка рассуждения не удалась.',
                'context': f'Ошибка: {error_msg}'
            },
            expected_outcome='Повторная попытка рассуждения и выполнения действия'
        ),
        confidence=0.1,
        stop_condition=False,  # ← НЕ останавливаем агента
        stop_reason=error_type
    )

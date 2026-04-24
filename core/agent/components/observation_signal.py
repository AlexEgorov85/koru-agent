"""
ObservationSignal: Промежуточный DTO между ObservationPhase и AgentState.

АРХИТЕКТУРА:
- Шаг 3.3 плана рефакторинга
- Типизированный контракт для передачи результатов наблюдения
- Заменяет сырые Dict[str, Any] на границах фаз
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ObservationSignal(BaseModel):
    """
    Структурированный сигнал наблюдения.
    
    ПОЛЯ:
    - status: статус выполнения (success/error/empty/partial)
    - quality: оценка качества данных (completeness, relevance, accuracy)
    - insight: ключевое наблюдение для LLM
    - hint: рекомендация для следующего шага
    - action_name: название выполненного действия
    - parameters: параметры действия
    - error: описание ошибки (если есть)
    - rule_based: был ли использован rule-based анализ
    - metadata: дополнительные метаданные
    """
    status: str = "unknown"
    quality: Dict[str, Any] = Field(default_factory=dict)
    insight: str = ""
    hint: str = ""
    action_name: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    rule_based: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = False  # Разрешаем модификацию для обратной совместимости


class ObservationSignalService:
    """
    Сервис для построения и валидации ObservationSignal.
    
    ОТВЕТСТВЕННОСТЬ:
    - Конвертация ExecutionResult → ObservationSignal
    - Обогащение сигнала метаданными
    - Валидация контракта
    """
    
    def build_signal(
        self,
        result: Any,
        action_name: str,
        parameters: Dict[str, Any],
        observation_data: Optional[Dict[str, Any]] = None,
    ) -> ObservationSignal:
        """
        Построить ObservationSignal из результата выполнения.
        
        Args:
            result: ExecutionResult или аналогичный объект
            action_name: Название действия
            parameters: Параметры действия
            observation_data: Дополнительные данные наблюдения
            
        Returns:
            ObservationSignal: типизированный сигнал
        """
        # Извлекаем статус
        status = "unknown"
        if hasattr(result, 'status'):
            if hasattr(result.status, 'value'):
                status = result.status.value
            else:
                status = str(result.status)
        elif observation_data and 'status' in observation_data:
            status = observation_data['status']
        
        # Извлекаем данные
        data = None
        if hasattr(result, 'data'):
            data = result.data
        elif observation_data and 'data' in observation_data:
            data = observation_data['data']
        
        # Извлекаем ошибку
        error = None
        if hasattr(result, 'error'):
            error = result.error
        elif observation_data and 'error' in observation_data:
            error = observation_data['error']
        
        # Формируем качество
        quality = {}
        if observation_data and 'quality' in observation_data:
            quality = observation_data['quality'] or {}
        
        # Определяем insight и hint
        insight = ""
        hint = ""
        if observation_data:
            insight = observation_data.get('insight', observation_data.get('observation', ''))
            hint = observation_data.get('hint', observation_data.get('next_step_suggestion', ''))
        
        # Rule-based флаг
        rule_based = False
        if observation_data and '_rule_based' in observation_data:
            rule_based = observation_data['_rule_based']
        
        return ObservationSignal(
            status=status,
            quality=quality,
            insight=insight,
            hint=hint,
            action_name=action_name,
            parameters=parameters or {},
            error=str(error) if error else None,
            rule_based=rule_based,
            metadata={
                "has_data": data is not None,
                "is_empty": data in (None, {}, [], ""),
            }
        )
    
    def validate_signal(self, signal: ObservationSignal) -> bool:
        """
        Валидировать сигнал наблюдения.
        
        Returns:
            bool: True если сигнал валиден
        """
        # Минимальная валидация
        if not signal.status:
            return False
        if not signal.action_name:
            return False
        return True
    
    def to_dict(self, signal: ObservationSignal) -> Dict[str, Any]:
        """Конвертировать в dict для обратной совместимости."""
        return signal.model_dump()

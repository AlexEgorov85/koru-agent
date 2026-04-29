"""
Фаза наблюдения: унифицированный анализ результата.

АРХИТЕКТУРА:
- observation_phase.analyze() — единая точка входа
- Внутри: _should_call_llm() → _run_analysis() (регистрация в ContextUpdatePhase)
- Возвращает строго типизированный ObservationResult (Pydantic) - Шаг 2.3
- Содержит логику оценки размера данных (_is_too_large, decide_save_type)
"""

import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from core.agent.state import ObservationAnalysis
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult, ExecutionStatus


class ObservationPhase:
    """
    Унифицированная фаза наблюдения.
    
    Одна точка входа для анализа результата выполнения.
    
    ЛОГИКА СОХРАНЕНИЯ ДАННЫХ:
    - Оценивает объём сырых данных (_is_too_large, decide_save_type)
    - Решает: сохранять raw_data или summary
    """
    
    # Лимиты для оценки размера данных
    MAX_ROWS = 5
    MAX_JSON_BYTES = 1500
    MAX_TEXT_CHARS = 1500
    MAX_DICT_KEYS = 10
    
    @staticmethod
    def decide_save_type(raw_data: Any, explicit_mode: str = "auto") -> str:
        """
        Определить тип сохранения: 'raw_data' или 'summary'.
        
        ARGS:
            raw_data: данные для сохранения
            explicit_mode: явный режим ('auto', 'full', 'summary')
            
        RETURNS:
            'raw_data' если данные помещаются в пороги
            'summary' если данные слишком большие
        """
        if explicit_mode == "summary":
            return "summary"
        
        if explicit_mode == "full":
            # full означает raw_data, если данные не слишком большие
            return "raw_data" if not ObservationPhase._is_too_large(raw_data) else "summary"
        
        # auto mode
        return "summary" if ObservationPhase._is_too_large(raw_data) else "raw_data"
    
    @staticmethod
    def _is_too_large(data: Any) -> bool:
        """Проверяет, превышают ли данные пороги сохранения."""
        if isinstance(data, list):
            if not data:
                return True
            if len(data) > ObservationPhase.MAX_ROWS:
                return True
            try:
                return len(json.dumps(data, ensure_ascii=False)) > ObservationPhase.MAX_JSON_BYTES
            except (TypeError, ValueError):
                return True
        if isinstance(data, str):
            return len(data) > ObservationPhase.MAX_TEXT_CHARS
        if isinstance(data, dict):
            if len(data) > ObservationPhase.MAX_DICT_KEYS:
                return True
            try:
                return len(json.dumps(data, ensure_ascii=False)) > ObservationPhase.MAX_JSON_BYTES
            except (TypeError, ValueError):
                return True
        return True
    
    @staticmethod
    def get_size_info(data: Any) -> dict:
        """Возвращает информацию о размере данных."""
        info = {"type": type(data).__name__, "too_large": ObservationPhase._is_too_large(data)}
        
        if isinstance(data, list):
            info["row_count"] = len(data)
            try:
                info["json_size"] = len(json.dumps(data, ensure_ascii=False))
            except (TypeError, ValueError):
                info["json_size"] = None
        elif isinstance(data, str):
            info["char_count"] = len(data)
        elif isinstance(data, dict):
            info["key_count"] = len(data)
            try:
                info["json_size"] = len(json.dumps(data, ensure_ascii=False))
            except (TypeError, ValueError):
                info["json_size"] = None
        
        return info
    
    def __init__(
        self,
        observer: Any,
        metrics: Any,
        policy: Any,
        log: logging.Logger,
        event_bus: Any,
    ):
        self.observer = observer
        self.metrics = metrics
        self.policy = policy
        self.log = log
        self.event_bus = event_bus
    
    async def analyze(
        self,
        result: ExecutionResult,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        session_context: Any,
        step_number: int,
    ) -> ObservationAnalysis:
        """
        Унифицированный анализ результата.
        
        Args:
            result: ExecutionResult от ExecutionPhase
            decision_action: Название действия
            decision_parameters: Параметры действия
            session_context: Контекст сессии для регистрации
            step_number: Номер шага
            
        Returns:
            ObservationAnalysis: типизированный результат анализа (Шаг 2.3)
        """
        session_id = session_context.session_id if session_context else "unknown"
        
        # Определяем нужно ли LLM
        should_call_llm = self._should_call_llm(result)
        
        # Выполняем анализ
        observation_dict = await self._run_analysis(
            result=result,
            action=decision_action,
            parameters=decision_parameters,
            force_llm=should_call_llm,
            session_id=session_id,
            step_number=step_number,
        )
        
        # Конвертируем в типизированный ObservationAnalysis (Шаг 2.3)
        # Определяем тип сохранения на основе размера данных
        save_type = self.decide_save_type(result.data)
        
        observation = ObservationAnalysis(
            status=observation_dict.get('status', 'unknown'),
            quality=observation_dict.get('quality', {}) or {},
            insight=observation_dict.get('insight', observation_dict.get('observation', '')),
            hint=observation_dict.get('hint', observation_dict.get('next_step_suggestion', '')),
            rule_based=observation_dict.get('_rule_based', False),
            timestamp=datetime.utcnow().isoformat(),
            action_name=decision_action,
            step_number=step_number,
            save_type=save_type,
        )
        
        # Логируем
        self.log.info(
            f"📊 Observation: status={observation.status}, "
            f"quality={observation.quality}, save_type={save_type}",
            extra={"event_type": EventType.INFO},
        )
        
        return observation
    
    def _should_call_llm(self, result: ExecutionResult) -> bool:
        """Определить нужно ли LLM."""
        # Observer настраиваемый trigger_mode
        trigger_mode = getattr(self.observer, 'trigger_mode', 'always')
        
        if trigger_mode == 'always':
            return True
        
        if result.status == ExecutionStatus.FAILED:
            return True
        
        if result.data in (None, {}, [], ""):
            return True
        
        if trigger_mode == 'on_error':
            return result.status in (ExecutionStatus.FAILED,)
        
        if trigger_mode == 'on_empty':
            return result.data in (None, {}, [], "")
        
        return False
    
    async def _run_analysis(
        self,
        result: ExecutionResult,
        action: str,
        parameters: Dict[str, Any],
        force_llm: bool,
        session_id: str,
        step_number: int,
    ) -> Dict[str, Any]:
        """Запустить Observer или rule-based."""
        error = result.error if result.status == ExecutionStatus.FAILED else None
        
        # Observer.analyze() самостоятельно решает LLM vs rule-based
        observation = await self.observer.analyze(
            action_name=action,
            parameters=parameters,
            result=result.data,
            error=error,
            session_id=session_id,
            agent_id="agent",
            step_number=step_number,
            force_llm=force_llm,
        )
        
        # Метрика использования LLM
        used_llm = not observation.get('_rule_based', False)
        self.metrics.record_observer_call(used_llm=used_llm)
        
        # Обогащаем observation для обратной совместимости
        observation.setdefault('insight', observation.get('observation', ''))
        observation.setdefault('hint', observation.get('next_step_suggestion', ''))
        
        return observation
    

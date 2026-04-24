"""
Фаза наблюдения: унифицированный анализ результата.

АРХИТЕКТУРА:
- observation_phase.analyze() — единая точка входа
- Внутри: _should_call_llm() → _run_analysis() → _register_result()
- Возвращает строго типизированный ObservationResult (Pydantic) - Шаг 2.3
"""

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
    """
    
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
        observation = ObservationAnalysis(
            status=observation_dict.get('status', 'unknown'),
            quality=observation_dict.get('quality', {}) or {},
            insight=observation_dict.get('insight', observation_dict.get('observation', '')),
            hint=observation_dict.get('hint', observation_dict.get('next_step_suggestion', '')),
            rule_based=observation_dict.get('_rule_based', False),
            timestamp=datetime.utcnow().isoformat(),
            action_name=decision_action,
            step_number=step_number,
        )
        
        # Регистрируем в agent_state и metrics
        self._register_result(
            observation=observation,
            action=decision_action,
            result=result,
            session_context=session_context,
        )
        
        # Логируем
        self.log.info(
            f"📊 Observation: status={observation.status}, "
            f"quality={observation.quality}",
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
    
    def _register_result(
        self,
        observation: ObservationAnalysis,
        action: str,
        result: ExecutionResult,
        session_context: Any,
    ) -> None:
        """Зарегистрировать в agent_state и metrics."""
        if not session_context or not hasattr(session_context, 'agent_state'):
            return
        
        agent_state = session_context.agent_state
        
        # Сохраняем в историю наблюдений (Шаг 2.2)
        agent_state.push_observation(observation)
        
        # agent_state.add_step() + register_observation()
        obs_status = str(observation.status).lower()
        agent_state.add_step(
            action_name=action,
            status=result.status.value,
            parameters={},
            observation=observation.model_dump(),
        )
        agent_state.register_observation(observation.model_dump())
        
        # Metrics
        self.metrics.add_step(
            action_name=action,
            status=obs_status,
            error=None,  # ObservationAnalysis не содержит errors напрямую
        )
        
        # Event
        self.event_bus.publish(
            EventType.DEBUG,
            {
                "event": "OBSERVATION",
                "status": obs_status,
                "quality": observation.quality,
                "rule_based": observation.rule_based,
                "observer_skip_rate": self.metrics.observer_skip_rate,
            },
            session_id=session_context.session_id,
            agent_id="agent",
        )
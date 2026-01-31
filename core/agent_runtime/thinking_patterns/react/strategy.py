"""
ReActThinkingPattern — компонуемый паттерн мышления на основе атомарных действий.
ОСОБЕННОСТИ:
- ИСПОЛЬЗУЕТ атомарные действия (THINK, ACT, OBSERVE) из новой архитектуры
- ЯВЛЯЕТСЯ компонуемым паттерном, собранным из базовых компонентов
- НЕТ жесткой привязки к конкретным навыкам - использует динамическую маршрутизацию
- ПОЛНОСТЬЮ адаптируется под домен задачи через DomainManager
"""
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface
from core.session_context.model import ContextItemMetadata
from models.execution import ExecutionStatus

# Импорты для новой архитектуры
from core.atomic_actions.actions import THINK, ACT, OBSERVE
from core.composable_patterns.base import ComposablePattern

logger = logging.getLogger(__name__)


class ReActThinkingPattern(AgentThinkingPatternInterface, ComposablePattern):
    """
    Компонуемый паттерн ReAct (Reasoning + Acting) на основе атомарных действий.
    
    АРХИТЕКТУРА:
    1. THINK: Анализ текущего состояния и формирование плана действий
    2. ACT: Выполнение действия через динамически определенную capability
    3. OBSERVE: Сбор результатов выполнения для последующего анализа
    4. ЦИКЛ: Повторение до достижения цели или предела шагов
    
    ПРЕИМУЩЕСТВА НОВОЙ РЕАЛИЗАЦИИ:
    - Полная заменяемость компонентов (можно подставить другие реализации THINK, ACT, OBSERVE)
    - Динамическая адаптация к домену задачи
    - Возможность компоновки с другими паттернами
    - Легкая модификация поведения через замену атомарных действий
    """
    name = "react_composable"
    
    def __init__(self):
        # Инициализация как компонуемого паттерна
        ComposablePattern.__init__(self, self.name, "Компонуемый ReAct паттерн на основе атомарных действий")
        # Добавление атомарных действий в паттерн
        self.add_action(THINK())
        self.add_action(ACT())
        self.add_action(OBSERVE())
        
        # Параметры стратегии
        self._max_steps = 15
        self._confidence_threshold = 0.9

    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполнить компонуемый паттерн ReAct с полным жизненным циклом атомарных действий.
        """
        from core.atomic_actions.executor import AtomicActionExecutor

        # Инициализация исполнителя атомарных действий
        executor = AtomicActionExecutor(runtime)
        
        # Выполняем действия в последовательности с полным жизненным циклом
        for action in self.actions:
            result = await executor.execute_atomic_action(action, context, parameters)
            # Если действие возвращает терминальное решение, возвращаем его
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]:
                return result
        # Если ни одно действие не вернуло терминальное решение, возвращаем ACT для продолжения
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            reason="pattern_executed",
            payload={"pattern_name": self.name, "actions_count": len(self.actions)}
        )
    
    async def next_step(self, runtime) -> StrategyDecision:
        """
        Основной метод стратегии — реализация компонуемого цикла ReAct.
        """
        # Определяем, какой тип контекста используется
        if hasattr(runtime, 'session'):
            # Это обычный интерфейс агента
            session = runtime.session
        else:
            # Это ExecutionContext
            session = runtime.session_context
        
        goal = session.get_goal() or ""
        current_step = session.step_context.get_current_step_number() if hasattr(session, 'step_context') and hasattr(session.step_context, 'get_current_step_number') else getattr(runtime, 'step', 0)
        
        # Проверка лимита шагов
        if current_step >= self._max_steps:
            logger.info(f"Достигнут лимит шагов ({self._max_steps}), завершение работы")
            return StrategyDecision(
                action=StrategyDecisionType.STOP,
                reason="step_limit_reached",
                payload={"final_reason": "max_steps_exceeded"}
            )
        
        # Используем атомарные действия для реализации цикла ReAct
        # ШАГ 1: THINK - анализ ситуации и планирование
        think_action = self.get_action_by_type("THINK")
        thought_obs_id = None
        target_action = {}
        if think_action:
            thought_process = await think_action.execute(runtime, session, {
                "goal": goal,
                "context": self._get_context_summary(session),
                "step_number": current_step + 1
            })
            
            # Запись мысли в контекст
            thought_obs_id = session.record_observation(
                {
                    "action": "reasoning",
                    "step_number": current_step + 1,
                    "thought_process": thought_process.payload.get("reasoning", "") if thought_process.payload else "",
                    "confidence": thought_process.payload.get("confidence", 0.5) if thought_process.payload else 0.5,
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=current_step + 1,
                metadata=ContextItemMetadata(
                    source="react_thinking",
                    confidence=thought_process.payload.get("confidence", 0.5) if thought_process.payload else 0.5,
                    step_number=current_step + 1
                )
            )
            
            # Получение целевого действия из результата мышления
            target_action = thought_process.payload.get("next_action", {}) if thought_process.payload else {}
        # ШАГ 2: ACT - выполнение действия
        act_action = self.get_action_by_type("ACT")
        action_obs_id = None
        if act_action:
            action_result = await act_action.execute(runtime, session, {
                "action_request": target_action,
                "step_number": current_step + 1
            })
            
            # Запись результата действия
            action_obs_id = session.record_observation(
                {
                    "action": "action_execution",
                    "step_number": current_step + 1,
                    "action_request": target_action,
                    "execution_result": action_result.payload if action_result.payload else {},
                    "status": "success" if action_result.action == StrategyDecisionType.ACT else "failed",
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=current_step + 1,
                metadata=ContextItemMetadata(
                    source="react_action",
                    confidence=1.0 if action_result.action == StrategyDecisionType.ACT else 0.0,
                    step_number=current_step + 1
                )
            )
        # ШАГ 3: OBSERVE - сбор результатов и анализ
        observe_action = self.get_action_by_type("OBSERVE")
        if observe_action:
            # Используем те ID, которые действительно существуют
            recent_observations = []
            if thought_obs_id:
                recent_observations.append(thought_obs_id)
            if action_obs_id:
                recent_observations.append(action_obs_id)
            
            observation_result = await observe_action.execute(runtime, session, {
                "step_number": current_step + 1,
                "recent_observations": recent_observations
            })
            
            # Анализ результатов и принятие решения о продолжении
            should_continue = self._should_continue(goal, observation_result, current_step)
            
            if not should_continue:
                logger.info(f"Цель достигнута на шаге {current_step + 1}")
                return StrategyDecision(
                    action=StrategyDecisionType.STOP,
                    reason="goal_achieved",
                    payload={"final_reason": "goal_accomplished", "thought_observation_id": thought_obs_id, "action_observation_id": action_obs_id}
                )
        # Продолжение выполнения
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            reason="continue_react_cycle",
            payload={
                "cycle_step": current_step + 1,
                "thought_observation_id": thought_obs_id,
                "action_observation_id": action_obs_id
            }
        )
    
    def get_action_by_type(self, action_type: str):
        """Получить действие по типу из компонуемого паттерна."""
        for action in self.actions:
            if action.name.upper() == action_type or action.__class__.__name__.upper().startswith(action_type):
                return action
        return None
    
    def _get_context_summary(self, session: Any) -> str:
        """Получить краткое резюме контекста сессии."""
        # Получаем последние элементы контекста
        if hasattr(session, 'data_context'):
            last_items = session.data_context.get_last_items(5)
            context_parts = []
            for item in last_items:
                if hasattr(item, 'content') and isinstance(item.content, dict):
                    if "result_summary" in item.content:
                        context_parts.append(f"Результат: {item.content['result_summary'][:100]}")
                    elif "thought_process" in item.content:
                        context_parts.append(f"Мысль: {item.content['thought_process'][:100]}")
            return " | ".join(context_parts[-3:])  # Берем последние 3 элемента
        
        return "Начало сессии - контекст ограничен"
    
    def _should_continue(self, goal: str, observation_result: StrategyDecision, current_step: int) -> bool:
        """Определить, следует ли продолжать выполнение."""
        # Проверяем, достигнута ли цель на основе наблюдений и уверенности
        if current_step >= self._max_steps:
            return False
            
        # В реальной реализации здесь будет более сложная логика анализа
        # на основе результатов наблюдения и уверенности в достижении цели
        confidence = observation_result.payload.get("confidence", 0.0) if observation_result.payload else 0.0
        return confidence < self._confidence_threshold and current_step < self._max_steps
"""
EvaluationComposableThinkingPattern — компонуемый паттерн мышления для оценки достижения цели на основе атомарных действий.
ОСОБЕННОСТИ:
- ИСПОЛЬЗУЕТ атомарные действия (THINK, OBSERVE, EVALUATE) из новой архитектуры
- ЯВЛЯЕТСЯ компонуемым паттерном, собранным из базовых компонентов
- ПОЛНОСТЬЮ адаптируется под домен задачи через использование атомарных действий
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
from core.atomic_actions.actions import THINK, OBSERVE, EVALUATE
from core.composable_patterns.base import ComposablePattern

logger = logging.getLogger(__name__)


class EvaluationComposableThinkingPattern(AgentThinkingPatternInterface, ComposablePattern):
    """
    Компонуемый паттерн оценки на основе атомарных действий.
    
    АРХИТЕКТУРА:
    1. OBSERVE: Сбор информации о текущем состоянии и результатах
    2. THINK: Анализ собранной информации и текущего прогресса
    3. EVALUATE: Формальная оценка достижения цели и принятие решения
    4. РЕШЕНИЕ: Продолжить работу или завершить выполнение задачи
    
    ПРЕИМУЩЕСТВА НОВОЙ РЕАЛИЗАЦИИ:
    - Полная заменяемость компонентов (можно подставить другие реализации)
    - Динамическая адаптация к домену задачи
    - Возможность компоновки с другими паттернами
    - Легкая модификация поведения через замену атомарных действий
    """
    name = "evaluation_composable"
    
    def __init__(self):
        # Инициализация как компонуемого паттерна
        ComposablePattern.__init__(self, self.name, "Компонуемый паттерн оценки на основе атомарных действий")
        # Добавление атомарных действий в паттерн
        self.add_action(OBSERVE())
        self.add_action(THINK())
        self.add_action(EVALUATE())
        
        # Параметры стратегии
        self._confidence_threshold = 0.9

    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполнить компонуемый паттерн оценки.
        """
        from core.atomic_actions.executor import AtomicActionExecutor

        # Инициализация исполнителя атомарных действий
        executor = AtomicActionExecutor(runtime)
        
        # Выполняем действия в последовательности
        for action in self.actions:
            result = await executor.execute_atomic_action(action, context, parameters)
            # Если действие возвращает терминальное решение, возвращаем его
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP]:
                return result
        # Если ни одно действие не вернуло терминальное решение, возвращаем ACT для продолжения
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            reason="pattern_executed",
            payload={"pattern_name": self.name, "actions_count": len(self.actions)}
        )
    
    async def next_step(self, runtime) -> StrategyDecision:
        """
        Основной метод стратегии — реализация компонуемого процесса оценки.
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
        
        # Используем атомарные действия для реализации процесса оценки
        # ШАГ 1: OBSERVE - сбор информации о текущем состоянии и результатах
        observe_action = self.get_action_by_type("OBSERVE")
        observation_id = None
        if observe_action:
            observation_result = await observe_action.execute(runtime, session, {
                "goal": goal,
                "context": self._get_context_summary(session),
                "step_number": current_step + 1
            })
            
            # Запись наблюдения в контекст
            observation_id = session.record_observation(
                {
                    "action": "evaluation_observation",
                    "step_number": current_step + 1,
                    "observation_data": observation_result.payload.get("observations", []) if observation_result.payload else [],
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=current_step + 1,
                metadata=ContextItemMetadata(
                    source="evaluation_observing",
                    confidence=1.0,
                    step_number=current_step + 1
                )
            )
        # ШАГ 2: THINK - анализ собранной информации и текущего прогресса
        think_action = self.get_action_by_type("THINK")
        thought_obs_id = None
        if think_action:
            thought_process = await think_action.execute(runtime, session, {
                "goal": goal,
                "observations": observation_result.payload.get("observations", []) if observation_result and observation_result.payload else [],
                "context": self._get_context_summary(session),
                "step_number": current_step + 1
            })
            
            # Запись мысли в контекст
            thought_obs_id = session.record_observation(
                {
                    "action": "evaluation_reasoning",
                    "step_number": current_step + 1,
                    "thought_process": thought_process.payload.get("reasoning", "") if thought_process.payload else "",
                    "confidence": thought_process.payload.get("confidence", 0.5) if thought_process.payload else 0.5,
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=current_step + 1,
                metadata=ContextItemMetadata(
                    source="evaluation_thinking",
                    confidence=thought_process.payload.get("confidence", 0.5) if thought_process.payload else 0.5,
                    step_number=current_step + 1
                )
            )
        # ШАГ 3: EVALUATE - формальная оценка достижения цели и принятие решения
        evaluate_action = self.get_action_by_type("EVALUATE")
        if evaluate_action:
            evaluation_result = await evaluate_action.execute(runtime, session, {
                "goal": goal,
                "observations": observation_result.payload.get("observations", []) if observation_result and observation_result.payload else [],
                "reasoning": thought_process.payload.get("reasoning", "") if thought_process and thought_process.payload else "",
                "step_number": current_step + 1
            })
            
            # Анализ результата оценки и принятие решения о завершении
            evaluation_payload = evaluation_result.payload if evaluation_result.payload else {}
            eval_result = evaluation_payload.get("evaluation", {})
            progress_score = eval_result.get("progress_score", 0.0)
            goal_achieved = eval_result.get("goal_achieved", False)
            recommendation = eval_result.get("recommendation", "continue")
            
            # Запись результата оценки
            evaluation_obs_id = session.record_observation(
                {
                    "action": "evaluation_result",
                    "step_number": current_step + 1,
                    "progress_score": progress_score,
                    "goal_achieved": goal_achieved,
                    "recommendation": recommendation,
                    "full_evaluation": eval_result,
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=current_step + 1,
                metadata=ContextItemMetadata(
                    source="evaluation_result",
                    confidence=progress_score,
                    step_number=current_step + 1
                )
            )
            
            # Принятие решения на основе оценки
            if goal_achieved or recommendation == "conclude":
                logger.info(f"Цель достигнута на шаге {current_step + 1}, завершение работы")
                return StrategyDecision(
                    action=StrategyDecisionType.STOP,
                    reason="goal_achieved_evaluation",
                    payload={
                        "final_reason": "goal_accomplished_by_evaluation",
                        "evaluation_observation_id": evaluation_obs_id,
                        "progress_score": progress_score
                    }
                )
            elif recommendation == "modify":
                logger.info(f"Требуется изменение подхода на шаге {current_step + 1}")
                return StrategyDecision(
                    action=StrategyDecisionType.SWITCH,
                    next_strategy="planning",  # Возврат к планированию для корректировки
                    reason="approach_modification_needed",
                    payload={
                        "evaluation_observation_id": evaluation_obs_id,
                        "progress_score": progress_score
                    }
                )
            else:
                logger.info(f"Продолжение работы на шаге {current_step + 1}, прогресс: {progress_score:.2f}")
                return StrategyDecision(
                    action=StrategyDecisionType.ACT,
                    reason="continue_after_evaluation",
                    payload={
                        "evaluation_observation_id": evaluation_obs_id,
                        "progress_score": progress_score
                    }
                )
        else:
            # Если действие EVALUATE недоступно, используем простую проверку
            logger.info(f"Действие EVALUATE недоступно, возврат к реактивной стратегии на шаге {current_step + 1}")
            return StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                next_strategy="react_composable",
                reason="evaluate_action_unavailable",
                payload={"current_step": current_step + 1}
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
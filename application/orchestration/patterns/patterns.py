# Реализация компонуемых паттернов
"""
ReActPattern, PlanAndExecutePattern, ReflectionPattern
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Tuple
from domain.models.composable_pattern_state import ComposablePatternState
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus
from domain.models.agent.agent_runtime_state import AgentRuntimeState, AgentRuntimeStatus
from domain.models.session.context_item import ContextItem, ContextItemType
from infrastructure.gateways.event_system import EventSystem, EventType
from application.services.prompt_renderer import PromptRenderer
from application.services.prompt_initializer import PromptInitializer
from application.services.system_initialization_service import SystemInitializationService
from domain.models.prompt.prompt_version import PromptVersion, PromptRole
import asyncio
import json


class IComposablePattern(ABC):
    """
    Интерфейс компонуемого паттерна
    """
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> ExecutionResult:
        """
        Выполнить паттерн с заданным контекстом
        
        Args:
            context: Контекст выполнения паттерна
            
        Returns:
            Результат выполнения
        """
        pass


class ReActPattern(IComposablePattern):
    """
    Паттерн ReAct (Reasoning and Acting) - чередование рассуждения и действия
    
    Реализует полноценный цикл ReAct с:
    - Мышлением (Thought) - анализ текущего состояния и выбор следующего действия
    - Действием (Action) - выполнение выбранного действия
    - Наблюдением (Observation) - анализ результата действия
    """
    
    def __init__(self, 
                 prompt_renderer: PromptRenderer,
                 system_initialization_service: SystemInitializationService):
        self.prompt_renderer = prompt_renderer
        self.system_initialization_service = system_initialization_service
        self.event_system = EventSystem()
        
        # Инициализация промптов для ReAct
        self._initialize_prompts()
    
    def _initialize_prompts(self):
        """
        Инициализация промптов, необходимых для ReAct паттерна
        """
        # Используем PromptInitializer для загрузки промптов
        # В реальной реализации нужно передать необходимые зависимости
        try:
            # Временно отключаем инициализацию до тех пор, пока не будет доступен prompt_repository
            pass
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            print(f"Warning: Could not initialize prompts: {e}")
            pass
    
    async def execute(self, context: Dict[str, Any]) -> ExecutionResult:
        """
        Выполнить паттерн ReAct с заданным контекстом
        
        Args:
            context: Контекст выполнения, содержащий:
                    - query: исходный запрос пользователя
                    - session_id: ID сессии
                    - agent_id: ID агента
                    - max_iterations: максимальное количество итераций
                    - task_description: описание задачи
                    
        Returns:
            Результат выполнения с историей ReAct циклов
        """
        # Инициализация состояния выполнения
        runtime_state = AgentRuntimeState()
        runtime_state.start_execution(
            agent_id=context.get("agent_id", "default_agent"),
            session_id=context.get("session_id", "default_session"),
            task_id=context.get("task_id", "default_task"),
            task_description=context.get("task_description", "")
        )
        
        # Устанавливаем максимальное количество итераций
        max_iterations = context.get("max_iterations", 10)
        runtime_state.max_iterations = max_iterations
        
        # Публикуем событие начала выполнения
        await self.event_system.publish_simple(
            event_type=EventType.INFO,
            source="ReActPattern",
            data={
                "message": f"Начало выполнения ReAct паттерна",
                "session_id": runtime_state.session_id,
                "task_id": runtime_state.task_id,
                "max_iterations": max_iterations
            }
        )
        
        # Основной цикл ReAct
        iteration = 0
        final_result = None
        
        while iteration < max_iterations and not runtime_state.is_max_iterations_reached():
            iteration += 1
            runtime_state.start_iteration()
            
            # Публикуем событие начала итерации
            await self.event_system.publish_simple(
                event_type=EventType.AGENT_THOUGHT,
                source="ReActPattern",
                data={
                    "message": f"Начало итерации {iteration}",
                    "session_id": runtime_state.session_id,
                    "task_id": runtime_state.task_id,
                    "iteration": iteration
                }
            )
            
            try:
                # Фаза мышления (Thought)
                thought_result = await self._think(context, runtime_state)
                
                # Обновляем состояние мышления
                runtime_state.start_thinking(thought_result.get("thought", ""))
                
                # Публикуем событие мышления
                await self.event_system.publish_simple(
                    event_type=EventType.AGENT_THOUGHT,
                    source="ReActPattern",
                    data={
                        "message": "Фаза мышления (Thought)",
                        "session_id": runtime_state.session_id,
                        "task_id": runtime_state.task_id,
                        "iteration": iteration,
                        "thought": thought_result.get("thought", ""),
                        "reasoning": thought_result.get("reasoning", "")
                    }
                )
                
                # Фаза действия (Action)
                action_result = await self._act(context, thought_result, runtime_state)
                
                # Обновляем состояние действия
                runtime_state.start_acting(action_result.get("action", {}))
                
                # Публикуем событие действия
                await self.event_system.publish_simple(
                    event_type=EventType.AGENT_ACTION,
                    source="ReActPattern",
                    data={
                        "message": "Фаза действия (Action)",
                        "session_id": runtime_state.session_id,
                        "task_id": runtime_state.task_id,
                        "iteration": iteration,
                        "action": action_result.get("action", {}),
                        "tool_name": action_result.get("tool_name", ""),
                        "tool_args": action_result.get("tool_args", {})
                    }
                )
                
                # Фаза наблюдения (Observation)
                observation_result = await self._observe(context, action_result, runtime_state)
                
                # Обновляем состояние наблюдения
                runtime_state.start_observing(observation_result.get("observation", ""))
                
                # Публикуем событие наблюдения
                await self.event_system.publish_simple(
                    event_type=EventType.AGENT_OBSERVATION,
                    source="ReActPattern",
                    data={
                        "message": "Фаза наблюдения (Observation)",
                        "session_id": runtime_state.session_id,
                        "task_id": runtime_state.task_id,
                        "iteration": iteration,
                        "observation": observation_result.get("observation", ""),
                        "action_result": observation_result.get("action_result", {})
                    }
                )
                
                # Проверяем, достигли ли мы цели
                if await self._is_goal_reached(context, observation_result, runtime_state):
                    await self.event_system.publish_simple(
                        event_type=EventType.SUCCESS,
                        source="ReActPattern",
                        data={
                            "message": "Цель достигнута",
                            "session_id": runtime_state.session_id,
                            "task_id": runtime_state.task_id,
                            "iteration": iteration
                        }
                    )
                    runtime_state.complete()
                    final_result = observation_result.get("action_result")
                    break
                
                # Регистрируем прогресс (в данном случае считаем, что каждая итерация - это прогресс)
                runtime_state.register_progress(True)
                
            except Exception as e:
                # Обработка ошибок
                runtime_state.register_error()
                error_msg = f"Ошибка в итерации {iteration}: {str(e)}"
                
                await self.event_system.publish_simple(
                    event_type=EventType.ERROR,
                    source="ReActPattern",
                    data={
                        "message": error_msg,
                        "session_id": runtime_state.session_id,
                        "task_id": runtime_state.task_id,
                        "iteration": iteration,
                        "error": str(e)
                    }
                )
                
                # Проверяем, достигнуто ли максимальное количество ошибок
                if runtime_state.error_count >= 3:  # Максимум 3 ошибки
                    runtime_state.fail({"error_count": runtime_state.error_count, "last_error": str(e)})
                    break
        
        # Проверяем, не было ли превышено максимальное количество итераций
        if runtime_state.is_max_iterations_reached() and not runtime_state.finished:
            await self.event_system.publish_simple(
                event_type=EventType.WARNING,
                source="ReActPattern",
                data={
                    "message": "Превышено максимальное количество итераций",
                    "session_id": runtime_state.session_id,
                    "task_id": runtime_state.task_id,
                    "max_iterations": max_iterations
                }
            )
            runtime_state.fail({"error": "Max iterations reached"})
        
        # Определяем статус выполнения
        execution_status = ExecutionStatus.SUCCESS if runtime_state.status.value == "completed" else ExecutionStatus.FAILED
        
        # Возвращаем результат выполнения
        return ExecutionResult(
            status=execution_status,
            result=final_result,
            observation_item_id=f"obs_react_{runtime_state.id}",
            summary=f"ReAct паттерн завершен за {iteration} итераций",
            error=runtime_state.error_details.get("error", None) if runtime_state.error_details else None,
            execution_time=0.0,  # В реальной реализации нужно замерять время
            progress_metadata={
                "iterations_completed": iteration,
                "errors_count": runtime_state.error_count,
                "progress_percentage": runtime_state.progress_percentage
            },
            action_metadata={
                "pattern_name": "ReAct",
                "session_id": runtime_state.session_id
            },
            iteration_number=iteration,
            timestamp=runtime_state.finished_at
        )
    
    async def _think(self, context: Dict[str, Any], runtime_state: AgentRuntimeState) -> Dict[str, Any]:
        """
        Фаза мышления (Thought) - анализ текущего состояния и выбор следующего действия
        
        Args:
            context: Контекст выполнения
            runtime_state: Текущее состояние выполнения
            
        Returns:
            Результат мышления с планом действий
        """
        # Подготовка контекста для мышления
        thinking_context = {
            "query": context.get("query", ""),
            "history": runtime_state.thought_history[-5:],  # Последние 5 мыслей
            "observations": runtime_state.observation_history[-5:],  # Последние 5 наблюдений
            "current_iteration": runtime_state.iteration_count,
            "max_iterations": runtime_state.max_iterations,
            "progress": runtime_state.progress_percentage
        }
        
        # Здесь должен быть вызов LLM для генерации мысли
        # Для упрощения возвращаем фиктивный результат
        # В реальной реализации нужно использовать prompt_renderer для генерации мысли
        
        thought = f"Анализирую задачу, итерация {runtime_state.iteration_count}. "
        thought += f"Цель: {context.get('query', 'неизвестна')}. "
        thought += f"Прогресс: {runtime_state.progress_percentage}%."
        
        reasoning = f"На основе текущего прогресса ({runtime_state.progress_percentage}%) "
        reasoning += f"и истории выполнения ({len(runtime_state.thought_history)} шагов), "
        reasoning += "планирую следующее действие."
        
        return {
            "thought": thought,
            "reasoning": reasoning,
            "next_action": "analyze_or_perform_task"
        }
    
    async def _act(self, context: Dict[str, Any], thought_result: Dict[str, Any], 
                   runtime_state: AgentRuntimeState) -> Dict[str, Any]:
        """
        Фаза действия (Action) - выполнение выбранного действия
        
        Args:
            context: Контекст выполнения
            thought_result: Результат фазы мышления
            runtime_state: Текущее состояние выполнения
            
        Returns:
            Результат выполнения действия
        """
        # В реальной реализации здесь будет вызов конкретного инструмента или навыка
        # В упрощенном варианте возвращаем фиктивный результат
        
        action = {
            "type": "example_action",
            "description": thought_result.get("next_action", "analyze_or_perform_task"),
            "parameters": {"context": context, "iteration": runtime_state.iteration_count}
        }
        
        # Здесь должна быть логика выполнения действия
        # Для упрощения просто возвращаем фиктивный результат
        return {
            "action": action,
            "tool_name": "example_tool",
            "tool_args": {"param": "value"},
            "execution_status": "success"
        }
    
    async def _observe(self, context: Dict[str, Any], action_result: Dict[str, Any], 
                       runtime_state: AgentRuntimeState) -> Dict[str, Any]:
        """
        Фаза наблюдения (Observation) - анализ результата действия
        
        Args:
            context: Контекст выполнения
            action_result: Результат выполнения действия
            runtime_state: Текущее состояние выполнения
            
        Returns:
            Результат наблюдения
        """
        # В реальной реализации здесь будет анализ результата действия
        # В упрощенном варианте возвращаем фиктивный результат
        
        observation = f"Результат действия: {action_result.get('execution_status', 'unknown')}. "
        observation += f"Итерация {runtime_state.iteration_count} завершена."
        
        return {
            "observation": observation,
            "action_result": action_result,
            "success": action_result.get("execution_status") == "success"
        }
    
    async def _is_goal_reached(self, context: Dict[str, Any], observation_result: Dict[str, Any], 
                              runtime_state: AgentRuntimeState) -> bool:
        """
        Проверить, достигнута ли цель
        
        Args:
            context: Контекст выполнения
            observation_result: Результат наблюдения
            runtime_state: Текущее состояние выполнения
            
        Returns:
            True если цель достигнута, иначе False
        """
        # Проверяем, достигнут ли прогресс 100%
        if runtime_state.progress_percentage >= 100.0:
            return True
            
        # Проверяем, есть ли в наблюдении указание на завершение
        obs = observation_result.get("observation", "")
        if "цель достигнута" in obs.lower() or "задача выполнена" in obs.lower():
            return True
            
        # В противном случае цель не достигнута
        return False


class PlanAndExecutePattern(IComposablePattern):
    """
    Паттерн PlanAndExecute - сначала планирование, затем выполнение
    """
    
    async def execute(self, context: Dict[str, Any]) -> ExecutionResult:
        """
        Выполнить паттерн PlanAndExecute
        """
        # Заглушка для реализации
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result="PlanAndExecute completed",
            observation_item_id="obs_plan_execute_default",
            summary="PlanAndExecute паттерн заглушка",
            execution_time=0.0
        )


class ReflectionPattern(IComposablePattern):
    """
    Паттерн Reflection - выполнение с рефлексией и самоанализом
    """
    
    async def execute(self, context: Dict[str, Any]) -> ExecutionResult:
        """
        Выполнить паттерн Reflection
        """
        # Заглушка для реализации
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result="Reflection completed",
            observation_item_id="obs_reflection_default",
            summary="Reflection паттерн заглушка",
            execution_time=0.0
        )

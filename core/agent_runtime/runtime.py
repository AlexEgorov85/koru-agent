from datetime import datetime
import logging
from typing import Any, Dict
from core.agent_runtime.strategies.base import AgentStrategyInterface
from core.agent_runtime.strategies.evaluation import EvaluationStrategy
from core.agent_runtime.strategies.fallback import FallbackStrategy
from core.agent_runtime.strategies.react.strategy import ReActStrategy
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemMetadata
from core.system_context.base_system_contex import BaseSystemContext
from .state import AgentState
from .progress import ProgressScorer
from .executor import ActionExecutor
from .policy import AgentPolicy
from .model import StrategyDecisionType
from .strategy_manager import StrategyManager, ProgressMetrics
from models.execution import ExecutionStatus

logger = logging.getLogger(__name__)

class AgentRuntime:
    """Тонкий оркестратор выполнения агента.

    НЕ содержит логики стратегий."""

    def __init__(
        self,
        system_context: BaseSystemContext,
        session_context: BaseSessionContext,
        policy: AgentPolicy = None,
        max_steps: int = 10,
        strategy_name: str = "react"  # Новое поле для выбора стратегии
    ):
        self.system = system_context
        self.session = session_context
        self.policy = policy or AgentPolicy()
        self.max_steps = max_steps
        self.state = AgentState()
        self.progress = ProgressScorer()
        self.executor = ActionExecutor(system_context)

        # Инициализация стратегического менеджера
        self.strategy_manager = StrategyManager()
        self.progress_metrics = ProgressMetrics()

        # Регистрация всех доступных стратегий
        self._strategy_registry = {
            "react": ReActStrategy(),
            "plan_and_execute": ReActStrategy(),  # Используем ReAct как базу для plan_and_execute
            "chain_of_thought": None,  # Заглушка для будущей реализации
            "evaluation": EvaluationStrategy(),
            "fallback": FallbackStrategy()
        }

        # Ленивая инициализация PlanningStrategy для избежания циклического импорта
        if "planning" not in self._strategy_registry:
            from core.agent_runtime.strategies.planning.strategy import PlanningStrategy
            self._strategy_registry["planning"] = PlanningStrategy()

        # Устанавливаем стратегию на основе переданного имени или по умолчанию
        self.strategy = self._strategy_registry.get(strategy_name, ReActStrategy())

    async def _select_initial_strategy(self, goal: str) -> str:
        """
        Выбор начальной стратегии на основе анализа цели пользователя.
        Использует простой анализ ключевых слов + эвристики сложности.
        """
        goal_lower = goal.lower().strip()

        # Ключевые слова, указывающие на необходимость планирования
        planning_indicators = [
            # Декомпозиция задач
            "запланируй", "план", "шаги", "этапы", "последовательность", "алгоритм",
            "расписание", "график", "маршрут", "по порядку", "сначала", "потом", "затем",
            # Множественные действия
            "и затем", "после этого", "в итоге", "в конце",
            # Временные рамки
            "на завтра", "на неделю", "ежедневно", "каждый день"
        ]

        # Эвристика сложности: длинные цели часто требуют планирования
        is_complex = len(goal.split()) > 15 or goal.count("?") > 1 or goal.count(".") > 2

        # Проверка ключевых слов
        requires_planning = any(indicator in goal_lower for indicator in planning_indicators)

        # Решение на основе анализа
        if requires_planning or is_complex:
            # Дополнительная проверка: есть ли доступные планировочные capability
            planning_caps = [
                cap for cap in self.system.list_capabilities()
                if "planning" in [s.lower() for s in cap.supported_strategies]
            ]
            if planning_caps:
                # Проверяем, что стратегия планирования доступна
                if "planning" in self._strategy_registry or self._is_strategy_available("planning"):
                    return "planning"

        # По умолчанию — реактивная стратегия
        return self.system.config.agent.get("default_strategy", "react") if hasattr(self.system, 'config') and hasattr(self.system.config, 'agent') else "react"

    def _is_strategy_available(self, strategy_name: str) -> bool:
        """Проверяет, доступна ли стратегия (возможна ленивая инициализация)."""
        if strategy_name == "planning":
            return True  # Предполагаем, что планирующая стратегия может быть инициализирована
        return strategy_name in self._strategy_registry

    def get_strategy(self, strategy_name: str) -> AgentStrategyInterface:
        """Получение стратегии по имени.

        ПАРАМЕТРЫ:
        - strategy_name: имя стратегии

        ВОЗВРАЩАЕТ:
        - экземпляр стратегии

        ИСКЛЮЧЕНИЯ:
        - ValueError если стратегия не найдена
        """
        strategy_name = strategy_name.lower()
        
        # Если запрашивается планирующая стратегия, но она еще не инициализирована
        if strategy_name == "planning" and strategy_name not in self._strategy_registry:
            from core.agent_runtime.strategies.planning.strategy import PlanningStrategy
            self._strategy_registry["planning"] = PlanningStrategy()
        
        if strategy_name not in self._strategy_registry:
            raise ValueError(f"Стратегия '{strategy_name}' не найдена. Доступные: {list(self._strategy_registry.keys())}")

        strategy = self._strategy_registry[strategy_name]
        if strategy is None:
            raise ValueError(f"Стратегия '{strategy_name}' зарегистрирована, но не реализована")

        logger.debug(f"Получена стратегия: {strategy_name} -> {strategy.__class__.__name__}")
        return strategy

    async def run(self, goal: str):
        """Главный execution loop агента."""
        self.session.goal = goal
        
        # Запись системного события
        self.session.record_system_event("session_start", f"Starting session with goal: {goal}")

        # Выбор начальной стратегии через стратегический менеджер
        initial_strategy_name = await self.strategy_manager.select_initial_strategy(goal)
        self.strategy = self.get_strategy(initial_strategy_name)
        logger.info(f"Выбрана начальная стратегия: {initial_strategy_name}")

        for _ in range(self.max_steps):
            if self.state.finished:
                break

            # Текущий номер шага (начинаем с 1)
            current_step = self.state.step + 1

            decision = await self.strategy.next_step(self)

            # Запись решения стратегии
            if decision:
                self.session.record_decision(decision.action.value, reasoning=decision.reason)

            if decision.action == StrategyDecisionType.STOP:
                self.state.finished = True
                # Регистрируем финальное решение
                self.session.record_decision(
                    decision_data="STOP",
                    reasoning="goal_achieved",
                    metadata=ContextItemMetadata(step_number=current_step)
                )
                break

            if decision.action == StrategyDecisionType.SWITCH:
                try:
                    # Используем новый метод для получения стратегии
                    self.strategy = self.get_strategy(decision.next_strategy)
                    
                    # Записываем переключение в историю
                    self.strategy_manager.record_strategy_switch(
                        decision=decision,
                        from_strategy=self.strategy.name if hasattr(self.strategy, 'name') else 'unknown'
                    )
                    
                    logger.info(f"Переключение стратегии на: {decision.next_strategy}")
                except Exception as e:
                    logger.error(f"Ошибка переключения стратегии: {str(e)}. Используется fallback стратегия.")
                    self.strategy = self.get_strategy("fallback")

                # Регистрируем смену стратегии
                self.session.record_decision(
                    decision_data="SWITCH",
                    reasoning={"action": "strategy_change", "to_strategy": decision.next_strategy},
                    metadata=ContextItemMetadata(step_number=current_step)
                )
                continue
            
            if decision.action == StrategyDecisionType.ACT:
                try:
                    # 1. Создаем элемент действия в контексте перед выполнением
                    action_content = {
                        "capability": decision.capability.name,
                        "parameters": decision.payload,
                        "reason": decision.reason,
                        "skill": decision.capability.skill_name,
                        "step_number": current_step
                    }

                    action_item_id = self.session.record_action(
                        action_data=action_content,
                        step_number=current_step,
                        metadata=ContextItemMetadata(
                            source="agent_runtime",
                            timestamp=datetime.now(),
                            confidence=0.9
                        )
                    )

                    # 2. Выполняем capability
                    execution_result = await self.executor.execute_capability(
                        capability=decision.capability,
                        parameters=decision.payload,
                        session_context=self.session
                    )

                    # 3. Запись результата выполнения
                    # execution_result.observation_item_id может быть как одиночным ID, так и списком
                    obs_ids = execution_result.observation_item_id
                    if not isinstance(obs_ids, list):
                        obs_ids = [obs_ids] if obs_ids else []
                    
                    self.session.register_step(
                        step_number=current_step,
                        capability_name=decision.capability.name,
                        skill_name = decision.capability.skill_name,
                        action_item_id = action_item_id,
                        observation_item_ids = obs_ids,
                        summary=execution_result.summary,
                        status=execution_result.status.value
                    )

                    # 3.5 Обновление статуса шага в плане, если он был выполнен
                    if hasattr(self.session, 'current_plan_step_id') and self.session.current_plan_step_id:
                        await self._update_step_status_via_capability(
                            session=self.session,
                            step_id=self.session.current_plan_step_id,
                            status="completed" if execution_result.status == ExecutionStatus.SUCCESS else "failed",
                            result=execution_result.result,
                            error=execution_result.error
                        )
                        # Очищаем ID текущего шага после обновления
                        self.session.current_plan_step_id = None

                    # 4. Оценка прогресса и обновление состояния
                    progressed = self.progress.evaluate(self.session)
                    self.state.register_progress(progressed)

                    # 5. ПОСЛЕ выполнения — оценка необходимости переключения стратегии
                    state_metrics = self.progress_metrics.get_state_metrics()
                    switch_decision = await self.strategy_manager.should_switch_strategy(
                        current_strategy=self.strategy.name if hasattr(self.strategy, 'name') else 'unknown',
                        state_metrics=state_metrics
                    )

                    if switch_decision:
                        logger.info(f"Принято решение о переключении стратегии: {switch_decision.to_strategy}, причина: {switch_decision.reason}")

                        # Получаем текущую стратегию для записи в историю
                        current_strategy_name = self.strategy.name if hasattr(self.strategy, 'name') else 'unknown'

                        # Выполняем переключение
                        self.strategy = self.get_strategy(switch_decision.to_strategy)

                        # Записываем переключение в историю
                        self.strategy_manager.record_strategy_switch(
                            decision=switch_decision,
                            from_strategy=current_strategy_name
                        )

                        # Обновляем метрики переключения стратегии
                        self.state.increment_strategy_switches()

                        # Регистрируем смену стратегии
                        self.session.record_decision(
                            decision_data="STRATEGY_SWITCH_BY_MANAGER",
                            reasoning={"action": "auto_strategy_change", "to_strategy": switch_decision.to_strategy, "reason": switch_decision.reason},
                            metadata=ContextItemMetadata(step_number=current_step)
                        )

                    # Обновление состояния сессии
                    self.session.last_activity = datetime.now()

                except Exception as e:
                    logger.error(f"Ошибка в работе агента на шаге {current_step}: {e}", exc_info=True)
                    self.state.register_error()

                    # Регистрация ошибки в контексте
                    error_item_id = self.session.record_error(
                        error_data=str(e),
                        error_type="execution_error",
                        step_number=current_step,
                        metadata=ContextItemMetadata(
                            source="agent_runtime",
                            timestamp=datetime.now()
                        )
                    )

                    # Обновление статуса шага в плане при ошибке
                    if hasattr(self.session, 'current_plan_step_id') and self.session.current_plan_step_id:
                        await self._update_step_status_via_capability(
                            session=self.session,
                            step_id=self.session.current_plan_step_id,
                            status="failed",
                            error=str(e)
                        )
                        # Очищаем ID текущего шага после обновления
                        self.session.current_plan_step_id = None

                    # Обновление состояния сессии
                    self.session.last_activity = datetime.now()

            # В любом случае увеличиваем номер текущего шага для следующей итерации
            self.state.step += 1
        
        # Регистрация завершения сессии
        self.session.record_system_event(
            event_type="session_complete",
            description=f"Result: {self.session.get_summary()}",
            metadata=ContextItemMetadata(
                timestamp=datetime.now(),
                step_number=self.state.step
            )
        )

        # Генерация финального ответа
        final_answer_result = await self._generate_final_answer()

        # Возвращаем сессию с добавленной информацией о финальном ответе
        self.session.final_answer = final_answer_result
        return self.session
    
    async def _update_step_status_via_capability(
        self, 
        session, 
        step_id: str, 
        status: str,
        result: Any = None,
        error: str = None
    ):
        """Обновление статуса шага ИСКЛЮЧИТЕЛЬНО через capability PlanningSkill.
        
        ПАРАМЕТРЫ:
        - session: контекст сессии
        - step_id: ID шага для обновления
        - status: новый статус (completed/failed)
        - result: результат выполнения (опционально)
        - error: описание ошибки (опционально)
        """
        try:
            # Получение текущего плана из контекста
            current_plan_item = session.get_current_plan()
            if not current_plan_item:
                logger.warning("Невозможно обновить статус шага: план не найден в контексте")
                return
            
            # Получение capability для обновления статуса шага
            capability = self.system.get_capability("planning.update_step_status")
            if not capability:
                logger.error("Capability 'planning.update_step_status' не найдена, невозможно обновить статус шага")
                return
            
            # Подготовка параметров для capability
            parameters = {
                "plan_id": current_plan_item.item_id,
                "step_id": step_id,
                "status": status,
                "context": f"Автоматическое обновление статуса после выполнения шага"
            }
            
            if result is not None:
                # Создаем краткое описание результата
                result_summary = str(result)
                if len(result_summary) > 500:
                    result_summary = result_summary[:500] + "..."
                parameters["result_summary"] = result_summary
            
            if error is not None:
                parameters["error"] = error
            
            # Выполнение capability для обновления статуса
            await self.executor.execute_capability(
                capability=capability,
                parameters=parameters,
                session_context=session,
                system_context = self.system

            )
        
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса шага через capability: {str(e)}", exc_info=True)

    async def _generate_final_answer(self):
        """Генерация финального ответа при завершении сессии."""
        try:
            logger.info("Генерация финального ответа...")
            
            # Получение capability для генерации финального ответа
            capability = self.system.get_capability("final_answer.generate")
            
            if not capability:
                logger.warning("Capability 'final_answer.generate' не найдена, создаем фиктивную")
                # Возвращаем резервный ответ
                return {
                    "final_answer": self.session.get_summary().get("last_steps", [])[-1]["summary"] if self.session.get_summary().get("last_steps") else "Ответ сгенерирован",
                    "source": "backup_solution"
                }
            
            # Подготовка параметров для генерации финального ответа
            parameters = {
                "include_steps": True,
                "include_evidence": True,
                "format_type": "detailed"
            }
            
            # Выполнение capability для генерации финального ответа
            execution_result = await self.executor.execute_capability(
                capability=capability,
                parameters=parameters,
                session_context=self.session
            )
            
            if execution_result.status == ExecutionStatus.SUCCESS and execution_result.result:
                logger.info("Финальный ответ успешно сгенерирован")
                return execution_result.result
            else:
                logger.warning(f"Capability для генерации финального ответа вернула статус: {execution_result.status}")
                # Возвращаем резервный ответ на основе последнего шага
                last_steps = self.session.get_summary().get("last_steps", [])
                backup_answer = last_steps[-1]["summary"] if last_steps else "Ответ сгенерирован"
                return {
                    "final_answer": backup_answer,
                    "source": "backup_from_last_step",
                    "execution_status": execution_result.status.value if execution_result.status else "unknown"
                }
                
        except Exception as e:
            logger.error(f"Ошибка при генерации финального ответа: {str(e)}", exc_info=True)
            # Возвращаем резервный ответ
            last_steps = self.session.get_summary().get("last_steps", [])
            backup_answer = last_steps[-1]["summary"] if last_steps else "Ответ сгенерирован"
            return {
                "final_answer": backup_answer,
                "source": "backup_exception_handling",
                "error": str(e)
            }
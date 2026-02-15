from datetime import datetime
import logging
import uuid
from typing import Any, Dict, Optional
from core.agent_runtime.strategies.base import AgentStrategyInterface
from core.agent_runtime.strategies.evaluation import EvaluationStrategy
from core.agent_runtime.strategies.fallback import FallbackStrategy
from core.agent_runtime.strategies.react.strategy import ReActStrategy
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemMetadata
from core.application.context.base_system_context import BaseSystemContext
from core.config.agent_config import AgentConfig
from .state import AgentState
from .progress import ProgressScorer
from .executor import ActionExecutor
from .policy import AgentPolicy
from .model import StrategyDecisionType
from .behavior_manager import BehaviorManager
from .strategy_manager import ProgressMetrics
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
        strategy_name: str = "react",  # Новое поле для выбора стратегии
        agent_config: Optional[AgentConfig] = None,  # ← Новая зависимость
        correlation_id: Optional[str] = None,
        user_context: Optional['UserContext'] = None  # Добавляем контекст пользователя
    ):
        self.system = system_context
        self.session = session_context
        self.policy = policy or AgentPolicy()
        self.max_steps = max_steps
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self._agent_config = agent_config  # ← Сохраняем конфигурацию
        self.user_context = user_context  # Сохраняем контекст пользователя

        self.state = AgentState()
        self.progress = ProgressScorer()
        self.executor = ActionExecutor(system_context)

        # Инициализация менеджера поведения
        self.behavior_manager = BehaviorManager(application_context=system_context.application_context)
        self.progress_metrics = ProgressMetrics()


    def _is_strategy_available(self, strategy_name: str) -> bool:
        """Проверяет, доступна ли стратегия (возможна ленивая инициализация)."""
        if strategy_name == "planning":
            return True  # Предполагаем, что планирующая стратегия может быть инициализирована
        return strategy_name in self._strategy_registry


    async def run(self, goal: str):
        """Главный execution loop агента."""
        # 1. Проверка готовности перед началом выполнения
        await self._verify_readiness()

        self.session.goal = goal

        # Запись системного события
        self.session.record_system_event("session_start", f"Starting session with goal: {goal}")

        # Инициализация менеджера поведения
        await self.behavior_manager.initialize()

    async def _verify_readiness(self):
        """Проверка готовности агента к выполнению задачи."""
        # Проверяем, что система полностью инициализирована
        if not self.system.is_fully_initialized():
            raise RuntimeError(
                "Агент не готов к выполнению: системные ресурсы не полностью инициализированы. "
                "Выполните предварительную инициализацию системного контекста."
            )
        
        # Проверяем, что конфигурация агента доступна
        if not self._agent_config:
            raise RuntimeError(
                "Агент не готов к выполнению: отсутствует конфигурация агента. "
                "Конфигурация должна быть предоставлена при создании агента."
            )
        
        # Проверяем, что все необходимые сервисы доступны
        required_services = ['prompt_service', 'contract_service']
        for service_name in required_services:
            service = self.system.get_resource(service_name)
            if not service:
                raise RuntimeError(f"Агент не готов к выполнению: отсутствует необходимый сервис '{service_name}'")
        

        # Получаем доступные capability для использования в паттернах поведения
        available_caps = self.system.list_capabilities()

        for _ in range(self.max_steps):
            if self.state.finished:
                break

            # Текущий номер шага (начинаем с 1)
            current_step = self.state.step + 1

            # Получаем решение от менеджера поведения
            decision = await self.behavior_manager.generate_next_decision(
                session_context=self.session,
                available_capabilities=available_caps
            )

            # Запись решения паттерна поведения
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

            if decision.action == StrategyDecisionType.ACT:
                try:
                    # Получаем capability по имени из решения
                    capability = self.system.get_capability(decision.capability_name)
                    
                    if not capability:
                        logger.error(f"Capability '{decision.capability_name}' не найдена")
                        continue

                    # 1. Создаем элемент действия в контексте перед выполнением
                    action_content = {
                        "capability": capability.name,
                        "parameters": decision.parameters,
                        "reason": decision.reason,
                        "skill": capability.skill_name,
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
                        capability=capability,
                        parameters=decision.parameters,
                        session_context=self.session,
                        user_context=self.user_context  # Передаем контекст пользователя
                    )

                    # 3. Запись результата выполнения
                    # execution_result.observation_item_id может быть как одиночным ID, так и списком
                    obs_ids = execution_result.observation_item_id
                    if not isinstance(obs_ids, list):
                        obs_ids = [obs_ids] if obs_ids else []

                    self.session.register_step(
                        step_number=current_step,
                        capability_name=capability.name,
                        skill_name = capability.skill_name,
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

    def get_agent_config_snapshot(self) -> Dict[str, Any]:
        """Получение снапшота конфигурации для сохранения в отчёт бенчмарка"""
        if not self._agent_config:
            return {}
        
        return {
            "config_id": self._agent_config.config_id,
            "source": self._agent_config.source,
            "prompt_versions": self._agent_config.prompt_versions,
            "contract_versions": self._agent_config.contract_versions,
            "max_steps": self._agent_config.max_steps,
            "temperature": self._agent_config.temperature,
            "created_at": self._agent_config.created_at.isoformat()
        }
    
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
                system_context = self.system,
                user_context=self.user_context  # Передаем контекст пользователя
            )
        
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса шага через capability: {str(e)}", exc_info=True)

    async def _generate_final_answer(self):
        """Генерация финального ответа при завершении сессии."""
        try:
            # Получение capability для генерации финального ответа
            capability = self.system.get_capability("final_answer.generate")

            if not capability:
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
                session_context=self.session,
                user_context=self.user_context  # Передаем контекст пользователя
            )

            if execution_result.status == ExecutionStatus.SUCCESS and execution_result.result:
                return execution_result.result
            else:
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
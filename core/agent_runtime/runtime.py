from datetime import datetime
import logging
from typing import Any, Dict, Optional

# Импорты для новой архитектуры
from core.composable_patterns.registry import PatternRegistry
from core.domain_management.domain_manager import DomainManager
from core.agent_runtime.strategy_loader import ThinkingPatternLoader
from core.composable_patterns.state_manager import ComposablePatternStateManager

from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemMetadata
from core.system_context.base_system_contex import BaseSystemContext

# Используем TYPE_CHECKING для предотвращения циклических импортов
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.session_context.session_context import SessionContext
    from core.atomic_actions.base import AtomicAction
    from core.composable_patterns.base import ComposablePattern

from models.agent_state import AgentState
from .progress import ProgressScorer
from .executor import ActionExecutor
from .policy import AgentPolicy
from .model import StrategyDecisionType
from .execution_context import ExecutionContext
from .states import ExecutionState
from models.execution import ExecutionStatus
from models.composable_pattern_state import ComposablePatternState, ComposablePatternStatus

# Импорт интерфейса для ComposableAgentRuntime
from .interfaces import ComposableAgentInterface

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
        strategy: str = None
    ):
        self.system = system_context
        self.session = session_context
        self.policy = policy or AgentPolicy()
        self.max_steps = max_steps
        self.state = AgentState()
        self.progress = ProgressScorer()
        self.executor = ActionExecutor(system_context)
        
        # Инициализация менеджера состояния композиционных паттернов
        self.pattern_state_manager = ComposablePatternStateManager()
        self.current_pattern_state_id = None
        
        # Инициализация новой архитектуры
        self.pattern_loader = ThinkingPatternLoader(use_new_architecture=True)
        self.domain_manager = self.pattern_loader.get_domain_manager()
        self.pattern_registry = self.pattern_loader.get_pattern_registry()
        
        # Инициализация реестра паттернов
        self._pattern_registry = PatternRegistry()
        
        # Регистрация компонуемых паттернов как основных
        composable_patterns = {
            "react_composable": self._pattern_registry.get_pattern("react_composable"),
            "plan_and_execute_composable": self._pattern_registry.get_pattern("plan_and_execute_composable"),
            "tool_use_composable": self._pattern_registry.get_pattern("tool_use_composable"),
            "reflection_composable": self._pattern_registry.get_pattern("reflection_composable"),
            # Регистрация доменных паттернов
            "code_analysis.default": self._pattern_registry.get_pattern("code_analysis.default"),
            "database_query.default": self._pattern_registry.get_pattern("database_query.default"),
            "research.default": self._pattern_registry.get_pattern("research.default"),
        }

        # Фильтрация None значений (если какие-то паттерны не были найдены)
        self._thinking_pattern_registry = {k: v for k, v in composable_patterns.items() if v is not None}
        
        # Определение стратегии на основе параметра или по умолчанию
        if strategy:
            if strategy not in self._thinking_pattern_registry:
                raise ValueError(f"Стратегия '{strategy}' не найдена в реестре паттернов")
            self.strategy = self._thinking_pattern_registry[strategy]
        else:
            # По умолчанию начинать с компонуемого реактивного паттерна мышления
            if "react_composable" in self._thinking_pattern_registry:
                self.strategy = self._thinking_pattern_registry["react_composable"]
            else:
                # Если компонуемый не доступен, использовать резервную стратегию
                # или выбросить исключение, если нет подходящей стратегии
                available_strategies = list(self._thinking_pattern_registry.keys())
                if available_strategies:
                    self.strategy = self._thinking_pattern_registry[available_strategies[0]]
                else:
                    raise ValueError("Нет доступных стратегий для использования")
        
    def get_strategy(self, strategy_name: str):
        """Получение стратегии по имени.
        
        ПАРАМЕТРЫ:
        - strategy_name: имя стратегии
        
        ВОЗВРАЩАЕТ:
        - экземпляр стратегии
        
        ИСКЛЮЧЕНИЯ:
        - ValueError если стратегия не найдена
        """
        strategy_name = strategy_name.lower()
        if strategy_name not in self._thinking_pattern_registry:
            raise ValueError(f"Паттерн мышления '{strategy_name}' не найден. Доступные: {list(self._thinking_pattern_registry.keys())}")
        
        pattern = self._thinking_pattern_registry[strategy_name]
        if pattern is None:
            raise ValueError(f"Паттерн мышления '{strategy_name}' зарегистрирован, но не реализован")
        
        logger.debug(f"Получен паттерн мышления: {strategy_name} -> {pattern.__class__.__name__}")
        return pattern

    def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """
        Адаптировать агента к задаче: определить домен и выбрать подходящий паттерн.
        """
        return self.pattern_loader.adapt_to_task(task_description)

    async def run(self, goal: str):
        """Главный execution loop агента."""
        self.session.goal = goal
        
        # Определяем домен задачи и потенциально подходящий паттерн
        task_adaptation = self.adapt_to_task(goal)
        detected_domain = task_adaptation["domain"]
        logger.info(f"Определен домен задачи: {detected_domain}")
        
        # Создаем состояние для текущего паттерна мышления
        self.current_pattern_state_id = self.pattern_state_manager.create_state(
            pattern_name=self.strategy.name if hasattr(self.strategy, 'name') else str(type(self.strategy).__name__),
            pattern_description=f"Выполнение паттерна мышления для задачи: {goal}"
        )
        
        # Запись системного события
        self.session.record_system_event("session_start", f"Starting session with goal: {goal} (domain: {detected_domain})")
        
        # Используем паттерн "Состояние" для управления выполнением
        execution_state = ExecutionState()
        
        for _ in range(self.max_steps):
            if self.state.finished:
                break
            
            # Текущий номер шага (начинаем с 1)
            current_step = self.state.step + 1
            
            # Обновляем состояние паттерна
            if self.current_pattern_state_id:
                self.pattern_state_manager.update_state(self.current_pattern_state_id, {
                    "step": current_step,
                    "status": ComposablePatternStatus.ACTIVE
                })
            
            # Создаем контекст выполнения для текущего шага
            execution_context = ExecutionContext(
                system=self.system,
                session=self.session,
                state=self.state,
                policy=self.policy,
                progress=self.progress,
                executor=self.executor,
                strategy=self.strategy
            )
            
            decision = await execution_state.execute(execution_context)
            
            # Запись решения стратегии
            if decision:
                self.session.record_decision(decision.action.value, reasoning=decision.reason)
            
            if decision.action == StrategyDecisionType.STOP:
                self.state.finished = True
                # Обновляем состояние паттерна как завершенное
                if self.current_pattern_state_id:
                    self.pattern_state_manager.complete(self.current_pattern_state_id)
                # Регистрируем финальное решение
                self.session.record_decision(
                    decision_data="STOP",
                    reasoning="goal_achieved",
                    metadata=ContextItemMetadata(step_number=current_step)
                )
                break
            
            if decision.action == StrategyDecisionType.SWITCH:
                try:
                    # Обновляем состояние паттерна перед переключением
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.update_state(self.current_pattern_state_id, {
                            "status": ComposablePatternStatus.TERMINATED
                        })
                    
                    # Используем новый метод для получения стратегии
                    old_strategy_name = self.strategy.name if hasattr(self.strategy, 'name') else str(type(self.strategy).__name__)
                    self.strategy = self.get_strategy(decision.next_strategy)
                    logger.info(f"Переключение стратегии на: {decision.next_strategy}")
                    
                    # Создаем новое состояние для нового паттерна
                    self.current_pattern_state_id = self.pattern_state_manager.create_state(
                        pattern_name=self.strategy.name if hasattr(self.strategy, 'name') else str(type(self.strategy).__name__),
                        pattern_description=f"Переключение на паттерн мышления: {decision.next_strategy}"
                    )
                    
                except Exception as e:
                    logger.error(f"Ошибка переключения стратегии: {str(e)}. Используется fallback стратегия.")
                    # Пытаемся использовать любую доступную стратегию в качестве fallback
                    available_strategies = list(self._thinking_pattern_registry.keys())
                    if available_strategies:
                        self.strategy = self.get_strategy(available_strategies[0])
                
                # Регистрируем смену стратегии
                self.session.record_decision(
                    decision_data="SWITCH",
                    reasoning={"action": "strategy_change", "to_strategy": decision.next_strategy},
                    metadata=ContextItemMetadata(step_number=current_step)
                )
                continue
            
            if decision.action == StrategyDecisionType.ACT:
                try:
                    # Начинаем выполнение действия в состоянии паттерна
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.start_action_execution(self.current_pattern_state_id, decision.reason)
                    
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
                    
                    # 3. Завершаем выполнение действия в состоянии паттерна
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.finish_action_execution(self.current_pattern_state_id, {
                            "action_name": decision.reason,
                            "result": execution_result.result,
                            "status": execution_result.status.value
                        })
                    
                    # 3. Запись результата выполнения
                    self.session.register_step(
                        step_number=current_step,
                        capability_name=decision.capability.name,
                        skill_name = decision.capability.skill_name,
                        action_item_id = action_item_id,
                        observation_item_ids = execution_result.observation_item_id,
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
                    
                    # Обновляем прогресс в состоянии паттерна
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.register_progress(self.current_pattern_state_id, progressed)
                        
                except Exception as e:
                    logger.error(f"Ошибка в работе агента на шаге {current_step}: {e}", exc_info=True)
                    self.state.register_error()
                    
                    # Регистрация ошибки в состоянии паттерна
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.register_error(self.current_pattern_state_id)
                    
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
            self.state.step += 1
            self.session.last_activity = datetime.now()
            # Сохраняем текущий домен в сессии для возможного динамического переключения
            self.session.current_domain = detected_domain
        
        # Регистрация завершения сессии
        self.session.record_system_event(
            event_type="session_complete",
            description=f"Result: {self.session.get_summary()} (domain: {detected_domain})",
            metadata=ContextItemMetadata(
                timestamp=datetime.now(),
                step_number=self.state.step
            )
        )
        
        # Завершаем состояние текущего паттерна
        if self.current_pattern_state_id:
            self.pattern_state_manager.update_state(self.current_pattern_state_id, {
                "status": ComposablePatternStatus.COMPLETED if self.state.finished else ComposablePatternStatus.STOPPED
            })
        
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


class ComposableAgentRuntime(ComposableAgentInterface):
    """
    Реализация интерфейса ComposableAgentInterface для работы с компонуемыми агентами.
    Этот класс предоставляет конкретную реализацию методов, необходимых для выполнения
    атомарных действий и компонуемых паттернов в контексте агента.
    """
    
    def __init__(
        self,
        system_context: BaseSystemContext,
        session_context: BaseSessionContext,
        policy: AgentPolicy = None,
        max_steps: int = 10, 
        strategy: str = None
    ):
        """
        Инициализирует ComposableAgentRuntime с заданными контекстами и параметрами.
        
        ПАРАМЕТРЫ:
        - system_context: Контекст системы, предоставляющий доступ к ресурсам и возможностям
        - session_context: Контекст сессии, хранящий состояние текущей сессии агента
        - policy: Политика агента, определяющая правила поведения (по умолчанию AgentPolicy())
        - max_steps: Максимальное количество шагов выполнения (по умолчанию 10)
        - strategy: Стратегия выполнения (по умолчанию используется реактивная стратегия)
        """
        # Инициализируем внутренний AgentRuntime для выполнения основной логики
        self._runtime = AgentRuntime(
            system_context=system_context,
            session_context=session_context,
            policy=policy,
            max_steps=max_steps,
            strategy=strategy
        )
        # Используем также компоненты из внутреннего runtime
        self.system = self._runtime.system
        self.session = self._runtime.session
        self.policy = self._runtime.policy
        self.max_steps = self._runtime.max_steps
        self.state = self._runtime.state
        self.progress = self._runtime.progress
        self.executor = self._runtime.executor
        self.pattern_loader = self._runtime.pattern_loader
        self.domain_manager = self._runtime.domain_manager
        self.pattern_registry = self._runtime.pattern_registry
        self._pattern_registry = self._runtime._pattern_registry
        self._thinking_pattern_registry = self._runtime._thinking_pattern_registry
        self.strategy = self._runtime.strategy
        # Передаем доступ к менеджеру состояний паттернов
        self.pattern_state_manager = self._runtime.pattern_state_manager
        self.current_pattern_state_id = self._runtime.current_pattern_state_id

    async def execute_atomic_action(
        self,
        action: 'AtomicAction',
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Выполняет атомарное действие в заданном контексте с указанными параметрами.
        
        ПАРАМЕТРЫ:
        - action: Атомарное действие для выполнения
        - context: Контекст выполнения действия
        - parameters: Дополнительные параметры для выполнения действия (необязательно)
        
        ВОЗВРАЩАЕТ:
        - Результат выполнения атомарного действия
        """
        # Логика выполнения атомарного действия
        # В данном случае делегируем выполнение внутреннему executor
        execution_result = await self.executor.execute_capability(
            capability=action.capability,  # Предполагаем, что у AtomicAction есть capability
            parameters=parameters or {},
            session_context=self.session,
            system_context=self.system
        )
        return execution_result

    async def execute_composable_pattern(
        self,
        pattern: 'ComposablePattern',
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Выполняет компонуемый паттерн в заданном контексте с указанными параметрами.
        
        ПАРАМЕТРЫ:
        - pattern: Компонуемый паттерн для выполнения
        - context: Контекст выполнения паттерна
        - parameters: Дополнительные параметры для выполнения паттерна (необязательно)
        
        ВОЗВРАЩАЕТ:
        - Результат выполнения компонуемого паттерна
        """
        # Выполняем паттерн, используя его метод execute с предоставленным контекстом
        execution_result = await pattern.execute(context, parameters or {})
        return execution_result

    def adapt_to_domain(self, domain: str):
        """
        Адаптирует агента к указанной области знаний (домену).
        
        ПАРАМЕТРЫ:
        - domain: Название домена, к которому нужно адаптироваться
        """
        # Используем domain_manager для адаптации к домену
        self.domain_manager.set_current_domain(domain)
        # Также можем обновить стратегии, если они зависят от домена
        # Например, получить подходящую стратегию для нового домена
        try:
            # Пробуем установить стратегию, соответствующую домену
            domain_strategy = f"{domain}.default" if f"{domain}.default" in self._thinking_pattern_registry else None
            if domain_strategy:
                self.strategy = self._thinking_pattern_registry[domain_strategy]
        except Exception as e:
            logger.warning(f"Не удалось установить стратегию для домена {domain}: {str(e)}")

    def get_available_domains(self) -> list[str]:
        """
        Возвращает список доступных доменов, к которым может адаптироваться агент.
        
        ВОЗВРАЩАЕТ:
        - Список строк, представляющих доступные домены
        """
        # Возвращаем список доступных доменов из domain_manager
        return self.domain_manager.get_available_domains()



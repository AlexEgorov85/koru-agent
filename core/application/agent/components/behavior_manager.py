"""
Менеджер поведения агента для новой архитектуры

АРХИТЕКТУРА:
- НЕ содержит захардкоженных версий паттернов
- component_name используется вместо pattern_id
- Версии управляются через registry.yaml → AppConfig → ComponentConfig
- Интеграция с FailureMemory для принятия решений о переключении паттернов
- Интеграция с StrategySelector для интеллектуального выбора паттерна
"""
import asyncio
from typing import Optional, List
from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.models.errors import InvalidDecisionError
from core.models.enums.common_enums import ComponentType
from core.application.storage.behavior.behavior_storage import BehaviorStorage
from core.infrastructure.logging import EventBusLogger
from core.application.agent.components.failure_memory import FailureMemory
from core.application.agent.components.strategy_selector import StrategySelector


class BehaviorManager:
    """Управление паттернами поведения с изоляцией через ApplicationContext"""

    def __init__(
        self,
        application_context: 'ApplicationContext',
        initial_component_name: str = None,
        executor: Optional['ActionExecutor'] = None,
        failure_memory: Optional[FailureMemory] = None  # ← НОВОЕ: FailureMemory
    ):
        """
        Инициализация менеджера поведения.

        ПАРАМЕТРЫ:
        - application_context: Прикладной контекст
        - initial_component_name: Имя начального компонента (из AppConfig, например "react_pattern")
        - executor: ActionExecutor для передачи в паттерны
        - failure_memory: FailureMemory для принятия решений о переключении паттернов
        """
        self._app_ctx = application_context
        self._initial_component_name = initial_component_name or "react_pattern"  # Fallback для совместимости
        self._executor = executor  # ← Сохраняем executor
        self._failure_memory = failure_memory  # ← НОВОЕ: Сохраняем FailureMemory
        self._strategy_selector = StrategySelector()  # ← НОВОЕ: StrategySelector
        self._current_pattern: Optional[BehaviorPatternInterface] = None
        self._pattern_history: List[dict] = []
        self._behavior_storage: Optional[BehaviorStorage] = None
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        if hasattr(self, '_app_ctx') and self._app_ctx:
            event_bus = getattr(self._app_ctx.infrastructure_context, 'event_bus', None)
            if event_bus:
                self.event_bus_logger = EventBusLogger(
                    event_bus=event_bus,
                    session_id="system",
                    agent_id="system",
                    component=self.__class__.__name__
                )

    async def initialize(self, component_name: str = None):
        """
        Инициализация хранилища паттернов и загрузка начального паттерна.
        
        ПАРАМЕТРЫ:
        - component_name: Имя компонента для инициализации (переопределяет initial_component_name)
        """
        # Инициализация хранилища паттернов
        prompt_service = self._app_ctx.components.get(ComponentType.SERVICE, "prompt_service")
        self._behavior_storage = BehaviorStorage(
            data_dir="data",
            prompt_service=prompt_service,
            application_context=self._app_ctx,  # ← Передаём ApplicationContext
            executor=self._executor  # ← Передаём executor
        )

        # Загрузка начального паттерна (через component_name)
        target_component_name = component_name or self._initial_component_name
        self._current_pattern = await self._behavior_storage.load_pattern_by_component(target_component_name)
        
        # Инициализация паттерна (загрузка промптов/контрактов если кэши пустые)
        if hasattr(self._current_pattern, 'initialize'):
            await self._current_pattern.initialize()

    async def generate_next_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability]
    ) -> BehaviorDecision:
        # ПРОВЕРКА: инициализирован ли BehaviorManager
        if not self._current_pattern:
            raise RuntimeError(
                "BehaviorManager not initialized. "
                "Call await initialize(component_name) first."
            )

        # Единая точка анализа контекста
        context_analysis = await self._current_pattern.analyze_context(
            session_context,
            available_capabilities,
            {}  # Доп. анализ можно расширить
        )

        # Генерация решения
        decision = await self._current_pattern.generate_decision(
            session_context,
            available_capabilities,
            context_analysis
        )

        # 🔵 ОТЛАДКА: Получен decision от паттерна
        print(f"🔵 [BehaviorManager] Получен decision: action={decision.action.value}, capability_name={decision.capability_name}", flush=True)

        # КРИТИЧЕСКАЯ ПРОВЕРКА: decision должен иметь capability_name для ACT
        if decision.action == BehaviorDecisionType.ACT:
            if not decision.capability_name:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(
                        f"ACT decision без capability_name! "
                        f"Decision: {decision.action.value}, reason: {decision.reason[:100] if decision.reason else 'N/A'}"
                    )
                # Валидация не прошла — переключение на react_pattern
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="react_pattern",
                    reason="invalid_act_decision_no_capability"
                )

            # Проверка что capability существует в доступных
            # ИСПОЛЬЗУЕМ ту же логику что и _find_capability (с поиском по префиксу)
            # 🔵 ОТЛАДКА: Перед проверкой capability_exists
            print(f"🔵 [BehaviorManager] Проверка capability: {decision.capability_name}", flush=True)
            capability_exists = any(
                cap.name == decision.capability_name
                for cap in available_capabilities
            )
            
            # Если точное совпадение не найдено, проверяем по префиксу
            if not capability_exists and '.' in decision.capability_name:
                prefix = decision.capability_name.split('.')[0]
                capability_exists = any(
                    cap.name == prefix
                    for cap in available_capabilities
                )
                if capability_exists and self.event_bus_logger:
                    await self.event_bus_logger.debug(
                        f"Capability '{decision.capability_name}' найдена по префиксу '{prefix}'"
                    )
            
            if not capability_exists:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(
                        f"Capability '{decision.capability_name}' не найдена в доступных! "
                        f"Available: {[c.name for c in available_capabilities]}"
                    )
                # ← НОВОЕ: Используем StrategySelector для выбора паттерна
                next_pattern = self._strategy_selector.select_best_pattern(
                    available_patterns=["react_pattern", "planning_pattern", "evaluation_pattern"],
                    context={"complexity": "medium"},
                    failure_memory=self._failure_memory,
                    current_pattern=self._current_pattern.pattern_id if self._current_pattern else None
                )
                # Валидация не прошла — переключение на выбранный паттерн
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern=next_pattern,
                    reason="capability_not_found"
                )

            # ← НОВОЕ: Проверка FailureMemory на необходимость переключения паттерна
            if self._failure_memory and self._failure_memory.should_switch_pattern(decision.capability_name):
                if self.event_bus_logger:
                    await self.event_bus_logger.warning(
                        f"FailureMemory рекомендует переключить паттерн для {decision.capability_name}. "
                        f"Recommendation: {self._failure_memory.get_recommendation(decision.capability_name)}"
                    )
                # ← НОВОЕ: Используем StrategySelector для выбора паттерна
                next_pattern = self._strategy_selector.select_best_pattern(
                    available_patterns=["react_pattern", "planning_pattern", "evaluation_pattern"],
                    context={"complexity": "medium"},
                    failure_memory=self._failure_memory,
                    current_pattern=self._current_pattern.pattern_id if self._current_pattern else None
                )
                # Возвращаем SWITCH decision
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern=next_pattern,
                    reason=f"failure_memory_recommendation: {self._failure_memory.get_recommendation(decision.capability_name)}"
                )

        # Логирование decision для аудита
        if self.event_bus_logger:
            await self.event_bus_logger.info(
                f"Decision: action={decision.action.value}, "
                f"capability={decision.capability_name or 'N/A'}, "
                f"reason={decision.reason[:100] if decision.reason else 'N/A'}"
            )

        # Автоматическое переключение паттернов
        if decision.action == BehaviorDecisionType.SWITCH and decision.next_pattern:
            await self._switch_pattern(decision.next_pattern, decision.reason)

        # 🔵 ОТЛАДКА: Перед возвратом decision
        print(f"🔵 [BehaviorManager] Возвращаем decision: action={decision.action.value}, capability_name={decision.capability_name}", flush=True)

        return decision

    async def _switch_pattern(self, new_component_name: str, reason: str):
        """Переключение на новый паттерн
        
        ПАРАМЕТРЫ:
        - new_component_name: Имя компонента (например "fallback_pattern", "react_pattern")
        - reason: Причина переключения
        """
        if not self._behavior_storage:
            raise ValueError("BehaviorStorage не инициализирован")

        # Загрузка нового паттерна по component_name
        new_pattern = await self._behavior_storage.load_pattern_by_component(new_component_name)

        # Сохранение истории переключений
        switch_record = {
            "timestamp": "TODO",  # В реальной реализации будет время
            "from_pattern": self._current_pattern.pattern_id if self._current_pattern else None,
            "to_pattern": new_component_name,
            "reason": reason
        }
        self._pattern_history.append(switch_record)

        # Установка нового паттерна
        self._current_pattern = new_pattern

    def get_current_pattern_id(self) -> Optional[str]:
        """Получить ID текущего паттерна"""
        if self._current_pattern:
            return self._current_pattern.pattern_id
        return None

    def get_pattern_history(self) -> List[dict]:
        """Получить историю переключений паттернов"""
        return self._pattern_history.copy()
"""
Менеджер поведения агента для новой архитектуры

АРХИТЕКТУРА:
- НЕ содержит захардкоженных версий паттернов
- component_name используется вместо pattern_id
- Версии управляются через registry.yaml → AppConfig → ComponentConfig
"""
import asyncio
from typing import Optional, List
from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.models.errors import InvalidDecisionError
from core.application.storage.behavior.behavior_storage import BehaviorStorage
from core.infrastructure.logging import EventBusLogger


class BehaviorManager:
    """Управление паттернами поведения с изоляцией через ApplicationContext"""

    def __init__(self, application_context: 'ApplicationContext', initial_component_name: str = None):
        """
        Инициализация менеджера поведения.

        ПАРАМЕТРЫ:
        - application_context: Прикладной контекст
        - initial_component_name: Имя начального компонента (из AppConfig, например "react_pattern")
        """
        self._app_ctx = application_context
        self._initial_component_name = initial_component_name or "react_pattern"  # Fallback для совместимости
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
                    source=self.__class__.__name__,
                    correlation_id='behavior_manager'
                )

    async def initialize(self, component_name: str = None):
        """
        Инициализация хранилища паттернов и загрузка начального паттерна.
        
        ПАРАМЕТРЫ:
        - component_name: Имя компонента для инициализации (переопределяет initial_component_name)
        """
        # Инициализация хранилища паттернов
        prompt_service = self._app_ctx.get_service("prompt_service")
        self._behavior_storage = BehaviorStorage(
            data_dir="data",
            prompt_service=prompt_service,
            application_context=self._app_ctx  # ← Передаём ApplicationContext
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
        print(f"[DEBUG] generate_next_decision: _current_pattern={self._current_pattern is not None}")
        if not self._current_pattern:
            raise ValueError("BehaviorManager не инициализирован")

        # Единая точка анализа контекста
        print(f"[DEBUG] generate_next_decision: вызываем analyze_context")
        context_analysis = await self._current_pattern.analyze_context(
            session_context,
            available_capabilities,
            {}  # Доп. анализ можно расширить
        )

        # Генерация решения
        print(f"[DEBUG] generate_next_decision: вызываем generate_decision")
        decision = await self._current_pattern.generate_decision(
            session_context,
            available_capabilities,
            context_analysis
        )
        print(f"[DEBUG] generate_next_decision: decision.action={decision.action}")

        # КРИТИЧЕСКАЯ ПРОВЕРКА: decision должен иметь capability_name для ACT
        if decision.action == BehaviorDecisionType.ACT:
            if not decision.capability_name:
                if self.event_bus_logger:
                    asyncio.create_task(self.event_bus_logger.error(
                        f"ACT decision без capability_name! "
                        f"Decision: {decision.action.value}, reason: {decision.reason[:100] if decision.reason else 'N/A'}"
                    ))
                # Валидация не прошла — возвращаем SWITCH на fallback
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="fallback_pattern",
                    reason="invalid_act_decision_no_capability"
                )

            # Проверка что capability существует в доступных
            capability_exists = any(
                cap.name == decision.capability_name
                for cap in available_capabilities
            )
            if not capability_exists:
                if self.event_bus_logger:
                    asyncio.create_task(self.event_bus_logger.error(
                        f"Capability '{decision.capability_name}' не найдена в доступных! "
                        f"Available: {[c.name for c in available_capabilities]}"
                    ))
                # Валидация не прошла — возвращаем SWITCH на fallback
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="fallback_pattern",
                    reason="capability_not_found"
                )

        # Логирование decision для аудита
        if self.event_bus_logger:
            asyncio.create_task(self.event_bus_logger.info(
                f"Decision: action={decision.action.value}, "
                f"capability={decision.capability_name or 'N/A'}, "
                f"reason={decision.reason[:100] if decision.reason else 'N/A'}"
            ))

        # Автоматическое переключение паттернов
        if decision.action == BehaviorDecisionType.SWITCH and decision.next_pattern:
            await self._switch_pattern(decision.next_pattern, decision.reason)

        return decision

    async def _switch_pattern(self, new_pattern_id: str, reason: str):
        """Переключение на новый паттерн"""
        if not self._behavior_storage:
            raise ValueError("BehaviorStorage не инициализирован")

        # Загрузка нового паттерна
        new_pattern = await self._behavior_storage.load_pattern(new_pattern_id)

        # Сохранение истории переключений
        switch_record = {
            "timestamp": "TODO",  # В реальной реализации будет время
            "from_pattern": self._current_pattern.pattern_id if self._current_pattern else None,
            "to_pattern": new_pattern_id,
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
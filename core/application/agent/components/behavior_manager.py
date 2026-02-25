"""
Менеджер поведения агента для новой архитектуры

АРХИТЕКТУРА:
- НЕ содержит захардкоженных версий паттернов
- component_name используется вместо pattern_id
- Версии управляются через registry.yaml → AppConfig → ComponentConfig
"""
from typing import Optional, List
from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.application.storage.behavior.behavior_storage import BehaviorStorage


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
        if not self._current_pattern:
            raise ValueError("BehaviorManager не инициализирован")

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
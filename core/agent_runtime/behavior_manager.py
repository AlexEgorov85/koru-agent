from typing import Optional, List
from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from models.capability import Capability
from core.application.storage.behavior.behavior_storage import BehaviorStorage


class BehaviorManager:
    """Управление паттернами поведения с изоляцией через ApplicationContext"""
    
    def __init__(self, application_context: 'ApplicationContext'):
        self._app_ctx = application_context
        self._current_pattern: Optional[BehaviorPatternInterface] = None
        self._pattern_history: List[dict] = []
        self._behavior_storage: Optional[BehaviorStorage] = None

    async def initialize(self, initial_pattern_id: str = "react.v1.0.0"):
        # Инициализация хранилища паттернов
        prompt_service = self._app_ctx.get_service("prompt")
        self._behavior_storage = BehaviorStorage(
            data_dir="data",
            prompt_service=prompt_service
        )
        
        # Загрузка начального паттерна
        self._current_pattern = await self._behavior_storage.load_pattern(initial_pattern_id)

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
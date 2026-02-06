"""
Менеджер состояния паттернов мышления.
"""
from typing import Dict, Optional
from domain.models.composable_pattern_state import ComposablePatternState
from datetime import datetime


class PatternStateManager:
    """Менеджер состояния паттернов мышления."""
    
    def __init__(self):
        self.pattern_states: Dict[str, ComposablePatternState] = {}
    
    def create_state(
        self, 
        pattern_name: str, 
        pattern_description: str = "", 
        state_id: Optional[str] = None
    ) -> ComposablePatternState:
        """Создает новое состояние для паттерна мышления."""
        if state_id is None:
            state_id = f"state_{pattern_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        state = ComposablePatternState()
        state.start_execution(pattern_name, pattern_description)
        self.pattern_states[state_id] = state
        return state
    
    def get_state(self, state_id: str) -> Optional[ComposablePatternState]:
        """Получает состояние паттерна по идентификатору."""
        return self.pattern_states.get(state_id)
    
    def complete(self, state_id: str) -> bool:
        """Отмечает паттерн как завершенный."""
        if state_id not in self.pattern_states:
            return False

        state = self.pattern_states[state_id]
        state.complete()
        return True
    
    def remove_state(self, state_id: str) -> bool:
        """Удаляет состояние паттерна."""
        if state_id in self.pattern_states:
            del self.pattern_states[state_id]
            return True
        return False
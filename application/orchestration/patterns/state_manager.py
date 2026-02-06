"""
Менеджер состояния для композиционных паттернов.
Обеспечивает отслеживание и управление состоянием выполнения композиционных паттернов.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from domain.models.composable_pattern_state import ComposablePatternState, ComposablePatternStatus
from domain.models.execution.execution_result import ExecutionResult
from domain.interfaces.event_system import EventSystem
from domain.models.events import EventType


class ComposablePatternStateManager:
    """
    Менеджер состояния для композиционных паттернов.
    
    НАЗНАЧЕНИЕ:
    - Отслеживает состояние выполнения композиционных паттернов
    - Управляет жизненным циклом состояния паттернов
    - Обеспечивает возможность восстановления состояния после сбоев
    - Поддерживает историю выполнения действий внутри паттернов
    
    ВОЗМОЖНОСТИ:
    - Инициализация состояния нового паттерна
    - Обновление состояния во время выполнения
    - Регистрация ошибок и прогресса
    - Приостановка и возобновление выполнения
    - Завершение выполнения паттерна
    - Получение истории выполнения
    """
    
    def __init__(self):
        self.pattern_states: Dict[str, ComposablePatternState] = {}
    
    def create_state(
        self, 
        pattern_name: str, 
        pattern_description: str = "", 
        state_id: Optional[str] = None
    ) -> ComposablePatternState:
        """
        Создает новое состояние для композиционного паттерна.
        
        Args:
            pattern_name: Имя паттерна
            pattern_description: Описание паттерна
            state_id: Идентификатор состояния (если не указан, генерируется автоматически)
            
        Returns:
            Новое состояние паттерна
        """
        if state_id is None:
            state_id = f"state_{pattern_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        state = ComposablePatternState()
        state.start_execution(pattern_name, pattern_description)
        self.pattern_states[state_id] = state

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.INFO,
            source="ComposablePatternStateManager",
            data={
                "message": f"Создано состояние для паттерна '{pattern_name}' с ID: {state_id}",
                "pattern_name": pattern_name,
                "state_id": state_id,
                "context": "pattern_state_created"
            }
        ))
        return state
    
    def get_state(self, state_id: str) -> Optional[ComposablePatternState]:
        """
        Получает состояние паттерна по идентификатору.
        
        Args:
            state_id: Идентификатор состояния
            
        Returns:
            Состояние паттерна или None если не найдено
        """
        return self.pattern_states.get(state_id)
    
    def update_state(self, state_id: str, updates: Dict[str, Any]) -> bool:
        """
        Обновляет состояние паттерна.

        Args:
            state_id: Идентификатор состояния
            updates: Обновления для применения к состоянию

        Returns:
            True если обновление прошло успешно, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено для обновления",
                    "state_id": state_id,
                    "context": "state_not_found_for_update"
                }
            ))
            return False

        state = self.pattern_states[state_id]

        # Обновляем поля состояния
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.DEBUG,
            source="ComposablePatternStateManager",
            data={
                "message": f"Обновлено состояние с ID '{state_id}'",
                "state_id": state_id,
                "context": "state_updated"
            }
        ))
        return True
    
    def start_action_execution(self, state_id: str, action_name: str) -> bool:
        """
        Инициирует выполнение действия внутри паттерна.

        Args:
            state_id: Идентификатор состояния
            action_name: Имя выполняемого действия

        Returns:
            True если операция успешна, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return False

        state = self.pattern_states[state_id]
        # Обновляем текущее действие в состоянии
        state.record_action({"action_name": action_name})
        state.start_iteration()

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.INFO,
            source="ComposablePatternStateManager",
            data={
                "message": f"Начало выполнения действия '{action_name}' в паттерне '{state.pattern_name}' (ID: {state_id})",
                "action_name": action_name,
                "pattern_name": state.pattern_name,
                "state_id": state_id,
                "context": "action_execution_started"
            }
        ))
        return True
    
    def finish_action_execution(self, state_id: str, action_result: Dict[str, Any]) -> bool:
        """
        Завершает выполнение действия внутри паттерна.

        Args:
            state_id: Идентификатор состояния
            action_result: Результат выполнения действия

        Returns:
            True если операция успешна, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return False

        state = self.pattern_states[state_id]
        # Обновляем результат действия в состоянии
        if "observation" in action_result:
            state.record_observation(action_result["observation"])
        if "error" in action_result and action_result["error"]:
            state.register_error()

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.INFO,
            source="ComposablePatternStateManager",
            data={
                "message": f"Завершено действие в паттерне '{state.pattern_name}', всего выполнено действий: {state.step_count}",
                "pattern_name": state.pattern_name,
                "action_count": state.step_count,
                "context": "action_execution_finished"
            }
        ))
        return True
    
    def register_error(self, state_id: str) -> bool:
        """
        Регистрирует ошибку в состоянии паттерна.

        Args:
            state_id: Идентификатор состояния

        Returns:
            True если операция успешна, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return False

        state = self.pattern_states[state_id]
        state.register_error()

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.ERROR,
            source="ComposablePatternStateManager",
            data={
                "message": f"Зарегистрирована ошибка в паттерне '{state.pattern_name}' (ID: {state_id})",
                "pattern_name": state.pattern_name,
                "state_id": state_id,
                "context": "error_registered"
            }
        ))
        return True
    
    def register_progress(self, state_id: str, progressed: bool) -> bool:
        """
        Регистрирует прогресс выполнения паттерна.

        Args:
            state_id: Идентификатор состояния
            progressed: Флаг прогресса (True если был прогресс, False если нет)

        Returns:
            True если операция успешна, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return False

        state = self.pattern_states[state_id]
        state.register_progress(progressed)

        progress_status = "прогресс" if progressed else "без прогресса"
        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.INFO,
            source="ComposablePatternStateManager",
            data={
                "message": f"Зарегистрирован {progress_status} в паттерне '{state.pattern_name}' (ID: {state_id})",
                "progress_status": progress_status,
                "pattern_name": state.pattern_name,
                "state_id": state_id,
                "context": "progress_registered"
            }
        ))
        return True
    
    def complete(self, state_id: str) -> bool:
        """
        Отмечает паттерн как завершенный.

        Args:
            state_id: Идентификатор состояния

        Returns:
            True если операция успешна, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return False

        state = self.pattern_states[state_id]
        state.complete()

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.INFO,
            source="ComposablePatternStateManager",
            data={
                "message": f"Паттерн '{state.pattern_name}' помечен как завершенный (ID: {state_id})",
                "pattern_name": state.pattern_name,
                "state_id": state_id,
                "context": "pattern_completed"
            }
        ))
        return True
    
    def pause(self, state_id: str) -> bool:
        """
        Приостанавливает выполнение паттерна.

        Args:
            state_id: Идентификатор состояния

        Returns:
            True если операция успешна, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return False

        state = self.pattern_states[state_id]
        state.pause()

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.INFO,
            source="ComposablePatternStateManager",
            data={
                "message": f"Паттерн '{state.pattern_name}' приостановлен (ID: {state_id})",
                "pattern_name": state.pattern_name,
                "state_id": state_id,
                "context": "pattern_paused"
            }
        ))
        return True
    
    def resume(self, state_id: str) -> bool:
        """
        Возобновляет выполнение паттерна.

        Args:
            state_id: Идентификатор состояния

        Returns:
            True если операция успешна, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return False

        state = self.pattern_states[state_id]
        state.resume()

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.INFO,
            source="ComposablePatternStateManager",
            data={
                "message": f"Паттерн '{state.pattern_name}' возобновлен (ID: {state_id})",
                "pattern_name": state.pattern_name,
                "state_id": state_id,
                "context": "pattern_resumed"
            }
        ))
        return True
    
    def waiting_for_input(self, state_id: str) -> bool:
        """
        Отмечает паттерн как ожидающий ввода.

        Args:
            state_id: Идентификатор состояния

        Returns:
            True если операция успешна, иначе False
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return False

        state = self.pattern_states[state_id]
        state.waiting_for_input()

        # Используем шину событий вместо логгера
        import asyncio
        event_bus = EventSystem()
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.INFO,
            source="ComposablePatternStateManager",
            data={
                "message": f"Паттерн '{state.pattern_name}' ожидает ввода (ID: {state_id})",
                "pattern_name": state.pattern_name,
                "state_id": state_id,
                "context": "pattern_waiting_for_input"
            }
        ))
        return True
    
    def get_pattern_history(self, state_id: str) -> List[Dict[str, Any]]:
        """
        Получает историю выполнения действий в паттерне.

        Args:
            state_id: Идентификатор состояния

        Returns:
            Список записей истории выполнения
        """
        if state_id not in self.pattern_states:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено",
                    "state_id": state_id,
                    "context": "state_not_found"
                }
            ))
            return []

        state = self.pattern_states[state_id]
        return state.action_history
    
    def get_all_states(self) -> Dict[str, ComposablePatternState]:
        """
        Получает все состояния паттернов.
        
        Returns:
            Словарь всех состояний с их идентификаторами
        """
        return self.pattern_states.copy()
    
    def remove_state(self, state_id: str) -> bool:
        """
        Удаляет состояние паттерна.

        Args:
            state_id: Идентификатор состояния

        Returns:
            True если операция успешна, иначе False
        """
        if state_id in self.pattern_states:
            del self.pattern_states[state_id]
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.INFO,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Удалено состояние с ID '{state_id}'",
                    "state_id": state_id,
                    "context": "state_removed"
                }
            ))
            return True
        else:
            # Используем шину событий вместо логгера
            import asyncio
            event_bus = EventSystem()
            asyncio.create_task(event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="ComposablePatternStateManager",
                data={
                    "message": f"Состояние с ID '{state_id}' не найдено для удаления",
                    "state_id": state_id,
                    "context": "state_not_found_for_removal"
                }
            ))
            return False
"""
Модуль управления жизненным циклом компонентов.

СОДЕРЖИТ:
- ComponentState: enum состояний компонента
- ComponentLifecycle: базовый класс для управления состоянием компонента
"""
from enum import Enum
from typing import Optional
import asyncio


class ComponentState(Enum):
    """
    Состояния жизненного цикла компонента/ресурса.

    DIAGRAM:
    CREATED → INITIALIZING → READY → SHUTDOWN
                ↓
              FAILED (при ошибке)

    PENDING — используется только в ResourceRecord (LifecycleManager).
    """
    CREATED = "created"           # Экземпляр создан, не инициализирован
    PENDING = "pending"           # Зарегистрирован, ждёт инициализации (LifecycleManager)
    INITIALIZING = "initializing" # В процессе инициализации
    READY = "ready"               # Готов к работе
    FAILED = "failed"             # Ошибка инициализации
    SHUTDOWN = "shutdown"         # Завершён

    @property
    def is_ready_state(self) -> bool:
        """Готов к работе."""
        return self == ComponentState.READY

    @property
    def is_initialized_state(self) -> bool:
        """Был инициализирован (READY или SHUTDOWN)."""
        return self in (ComponentState.READY, ComponentState.SHUTDOWN)

    @property
    def is_failed_state(self) -> bool:
        """Завершился ошибкой."""
        return self == ComponentState.FAILED


class ComponentLifecycle:
    """
    Базовый класс для управления жизненным циклом компонента.

    USAGE:
    ```python
    class MyComponent(ComponentLifecycle):
        def __init__(self, name: str):
            super().__init__(name)

        async def initialize(self):
            await self._transition_to(ComponentState.INITIALIZING)
            try:
                # Инициализация
                await self._do_init()
                await self._transition_to(ComponentState.READY)
            except Exception as e:
                await self._transition_to(ComponentState.FAILED)
                raise

        async def shutdown(self):
            await self._transition_to(ComponentState.SHUTDOWN)

        def some_method(self):
            self.ensure_ready()  # Проверка готовности
            # Бизнес-логика
    ```
    """
    
    def __init__(self, name: str):
        """
        Инициализация миксина.
        
        ARGS:
        - name: имя компонента для логирования
        """
        self._state = ComponentState.CREATED
        self._name = name
        self._state_lock = asyncio.Lock()
    
    def ensure_ready(self):
        """
        Проверка готовности компонента.
        
        RAISES:
        - RuntimeError: если компонент не в состоянии READY
        """
        if self._state != ComponentState.READY:
            raise RuntimeError(
                f"Component '{self._name}' not ready (state={self._state.value}). "
                f"Call initialize() first."
            )
    
    async def _transition_to(self, state: ComponentState):
        """
        Безопасный переход в новое состояние.
        
        ARGS:
        - state: целевое состояние
        """
        async with self._state_lock:
            old_state = self._state
            self._state = state
    
    @property
    def state(self) -> ComponentState:
        """Текущее состояние компонента."""
        return self._state
    
    @property
    def is_ready(self) -> bool:
        """Проверка готовности компонента."""
        return self._state == ComponentState.READY
    
    @property
    def is_initialized(self) -> bool:
        """Проверка, был ли компонент инициализирован (READY или SHUTDOWN)."""
        return self._state in (ComponentState.READY, ComponentState.SHUTDOWN)
    
    @property
    def is_failed(self) -> bool:
        """Проверка, завершилась ли инициализация ошибкой."""
        return self._state == ComponentState.FAILED
    
    @property
    def name(self) -> str:
        """Имя компонента."""
        return self._name
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self._name}', state={self._state.value})"


# Алиас для обратной совместимости
LifecycleMixin = ComponentLifecycle


__all__ = ['ComponentState', 'ComponentLifecycle', 'LifecycleMixin']

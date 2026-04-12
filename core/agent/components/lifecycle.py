"""
Модуль управления жизненным циклом компонентов.

СОДЕРЖИТ:
- ComponentLifecycle: базовый класс для управления состоянием компонента

ComponentStatus импортируется из core.models.enums.component_status для предотвращения циклических импортов.
"""
from typing import Optional
import asyncio

from core.models.enums.component_status import ComponentStatus


class ComponentLifecycle:
    """
    Базовый класс для управления жизненным циклом компонента.

    USAGE:
    ```python
    class MyComponent(ComponentLifecycle):
        def __init__(self, name: str):
            super().__init__(name)

        async def initialize(self):
            await self._transition_to(ComponentStatus.INITIALIZING)
            try:
                # Инициализация
                await self._do_init()
                await self._transition_to(ComponentStatus.READY)
            except Exception as e:
                await self._transition_to(ComponentStatus.FAILED)
                raise

        async def shutdown(self):
            await self._transition_to(ComponentStatus.SHUTDOWN)

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
        self._state = ComponentStatus.CREATED
        self._name = name
        self._state_lock = asyncio.Lock()

    def ensure_ready(self):
        """
        Проверка готовности компонента.

        RAISES:
        - RuntimeError: если компонент не в состоянии READY
        """
        if self._state != ComponentStatus.READY:
            raise RuntimeError(
                f"Component '{self._name}' not ready (state={self._state.value}). "
                f"Call initialize() first."
            )

    async def _transition_to(self, state: ComponentStatus):
        """
        Безопасный переход в новое состояние.

        ARGS:
        - state: целевое состояние
        """
        async with self._state_lock:
            old_state = self._state
            self._state = state

    @property
    def state(self) -> ComponentStatus:
        """Текущее состояние компонента."""
        return self._state

    @property
    def is_ready(self) -> bool:
        """Проверка готовности компонента."""
        return self._state == ComponentStatus.READY

    @property
    def is_initialized(self) -> bool:
        """Проверка, был ли компонент инициализирован (READY или SHUTDOWN)."""
        return self._state in (ComponentStatus.READY, ComponentStatus.SHUTDOWN)

    @property
    def is_failed(self) -> bool:
        """Проверка, завершилась ли инициализация ошибкой."""
        return self._state == ComponentStatus.FAILED

    @property
    def name(self) -> str:
        """Имя компонента."""
        return self._name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self._name}', state={self._state.value})"


# Алиас для обратной совместимости
LifecycleMixin = ComponentLifecycle


__all__ = ['ComponentLifecycle', 'LifecycleMixin']

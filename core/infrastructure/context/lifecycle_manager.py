"""
Менеджер жизненного цикла инфраструктурных ресурсов.
"""
import logging
from typing import List, Callable, Awaitable, Any, Optional
from contextlib import asynccontextmanager

from core.infrastructure.event_bus.unified_logger import EventBusLogger
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus


class LifecycleManager:
    """
    Менеджер жизненного цикла инфраструктурных ресурсов.
    Управляет инициализацией и завершением работы ресурсов.
    """

    def __init__(self, event_bus: Optional[UnifiedEventBus] = None):
        self._initializers: List[Callable[[], Awaitable[Any]]] = []
        self._cleanup_funcs: List[Callable[[], Awaitable[Any]]] = []
        self._initialized = False
        self.logger = logging.getLogger(__name__)
        self.event_bus: Optional[UnifiedEventBus] = event_bus
        self.event_bus_logger: Optional[EventBusLogger] = None
        if event_bus:
            self.event_bus_logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="LifecycleManager")

    def register_initializer(self, func: Callable[[], Awaitable[Any]]):
        """Регистрация функции инициализации."""
        self._initializers.append(func)

    def register_cleanup(self, func: Callable[[], Awaitable[Any]]):
        """Регистрация функции очистки."""
        self._cleanup_funcs.insert(0, func)  # Вставляем в начало для обратного порядка

    async def initialize_all(self) -> bool:
        """Инициализация всех зарегистрированных ресурсов."""
        if self._initialized:
            if self.event_bus_logger:
                await self.event_bus_logger.warning("LifecycleManager уже инициализирован")
            return True

        # Инициализируем event_bus_logger если ещё не создан
        if self.event_bus_logger is None and self.event_bus:
            self.event_bus_logger = EventBusLogger(self.event_bus, session_id="system", agent_id="system", component="LifecycleManager")

        if self.event_bus_logger:
            await self.event_bus_logger.info("Начало инициализации всех инфраструктурных ресурсов")

        failed_initializers = []
        for i, initializer in enumerate(self._initializers):
            try:
                if self.event_bus_logger:
                    await self.event_bus_logger.debug(f"Инициализация ресурса {i+1}/{len(self._initializers)}")
                await initializer()
            except Exception as e:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"Ошибка инициализации ресурса: {str(e)}")
                failed_initializers.append((initializer, str(e)))

        if failed_initializers:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Не удалось инициализировать {len(failed_initializers)} ресурсов")
            return False

        self._initialized = True
        if self.event_bus_logger:
            await self.event_bus_logger.info("Все инфраструктурные ресурсы инициализированы")
        return True

    async def shutdown_all(self):
        """Завершение работы всех ресурсов."""
        if not self._initialized:
            return

        if self.event_bus_logger:
            await self.event_bus_logger.info("Завершение работы инфраструктурных ресурсов")

        for cleanup_func in self._cleanup_funcs:
            try:
                await cleanup_func()
            except Exception as e:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"Ошибка при завершении ресурса: {str(e)}")

        self._initialized = False
        if self.event_bus_logger:
            await self.event_bus_logger.info("Все инфраструктурные ресурсы завершены")

    async def cleanup_all(self):
        """Алиас для shutdown_all (для обратной совместимости)."""
        await self.shutdown_all()

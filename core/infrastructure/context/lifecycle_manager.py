"""
Менеджер жизненного цикла инфраструктурных ресурсов.
"""
import logging
from typing import List, Callable, Awaitable, Any
from contextlib import asynccontextmanager


class LifecycleManager:
    """
    Менеджер жизненного цикла инфраструктурных ресурсов.
    Управляет инициализацией и завершением работы ресурсов.
    """
    
    def __init__(self):
        self._initializers: List[Callable[[], Awaitable[Any]]] = []
        self._cleanup_funcs: List[Callable[[], Awaitable[Any]]] = []
        self._initialized = False
        self.logger = logging.getLogger(__name__)
        
    def register_initializer(self, func: Callable[[], Awaitable[Any]]):
        """Регистрация функции инициализации."""
        self._initializers.append(func)
        
    def register_cleanup(self, func: Callable[[], Awaitable[Any]]):
        """Регистрация функции очистки."""
        self._cleanup_funcs.insert(0, func)  # Вставляем в начало для обратного порядка
        
    async def initialize_all(self) -> bool:
        """Инициализация всех зарегистрированных ресурсов."""
        if self._initialized:
            self.logger.warning("LifecycleManager уже инициализирован")
            return True
            
        self.logger.info("Начало инициализации всех инфраструктурных ресурсов")
        
        failed_initializers = []
        for i, initializer in enumerate(self._initializers):
            try:
                self.logger.debug(f"Инициализация ресурса {i+1}/{len(self._initializers)}")
                await initializer()
            except Exception as e:
                self.logger.error(f"Ошибка инициализации ресурса: {str(e)}")
                failed_initializers.append((initializer, str(e)))
                
        if failed_initializers:
            self.logger.error(f"Не удалось инициализировать {len(failed_initializers)} ресурсов")
            # В реальной системе можно было бы реализовать стратегию восстановления
            return False
            
        self._initialized = True
        self.logger.info("Все инфраструктурные ресурсы успешно инициализированы")
        return True
        
    async def cleanup_all(self):
        """Завершение работы всех зарегистрированных ресурсов."""
        if not self._initialized:
            return
            
        self.logger.info("Начало завершения работы всех инфраструктурных ресурсов")
        
        for i, cleanup_func in enumerate(self._cleanup_funcs):
            try:
                self.logger.debug(f"Завершение ресурса {i+1}/{len(self._cleanup_funcs)}")
                await cleanup_func()
            except Exception as e:
                self.logger.error(f"Ошибка при завершении ресурса: {str(e)}")
                
        self._initialized = False
        self.logger.info("Все инфраструктурные ресурсы завершены")
        
    @asynccontextmanager
    async def managed_context(self):
        """Контекстный менеджер для управления жизненным циклом."""
        if await self.initialize_all():
            try:
                yield self
            finally:
                await self.cleanup_all()
        else:
            raise RuntimeError("Не удалось инициализировать ресурсы")
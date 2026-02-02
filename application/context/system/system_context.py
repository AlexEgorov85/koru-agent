# Реализация системного контекста
"""
SystemContext — реализация системного контекста
"""
from typing import Any, Dict, List, Optional, Callable
import os
import logging
from domain.abstractions.system.base_system_context import IBaseSystemContext
from domain.abstractions.event_system import IEventPublisher, EventType, Event
from domain.models.capability import Capability
from config.models import SystemConfig
from application.services.system_initialization_service import SystemInitializationService


class SystemContext(IBaseSystemContext):
    """
    Реализация системного контекста для управления системными ресурсами
    """
    
    def __init__(self, config: SystemConfig, event_publisher: IEventPublisher):
        """Инициализация системного контекста."""
        self._config = config
        self._event_publisher = event_publisher
        self._resource_factories: Dict[str, Callable] = {}
        self._resources: Dict[str, Any] = {}
        self._capabilities: Dict[str, Capability] = {}
        self._initialized = False
        
        # Инициализация сервиса инициализации
        self._initialization_service = SystemInitializationService(
            system_context=self,
            config=config,
            event_publisher=event_publisher
        )

    async def _register_system_handlers(self) -> None:
        """Регистрация системных обработчиков событий"""
        # Обработчик ошибок — запись в лог-файл + вывод в консоль
        async def error_handler(event: Event):
            # Запись в файл
            log_dir = self._config.log_dir or "logs"
            os.makedirs(log_dir, exist_ok=True)
            log_file_path = os.path.join(log_dir, "system_errors.log")
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(f"[ERROR] {event.timestamp} {event.source}: {event.data}\n")
            # Вывод в консоль
            print(f"❌ [{event.source}] {event.data.get('message', event.data)}")
        
        # Обработчик прогресса — вывод в консоль
        async def progress_handler(event: Event):
            progress = event.data.get('progress', 0)
            total = event.data.get('total_steps', 100)
            message = event.data.get('message', 'Processing')
            print(f"⏳ {message} [{progress}/{total}]")
        
        # Обработчик отладки — только в режиме разработки
        if self._config.debug:
            async def debug_handler(event: Event):
                print(f"🐞 [DEBUG] {event.source}: {event.data}")
            self._event_publisher.subscribe(EventType.DEBUG, debug_handler)
        
        # Регистрация глобальных обработчиков
        self._event_publisher.subscribe(EventType.ERROR, error_handler)
        self._event_publisher.subscribe(EventType.INFO, progress_handler)

    async def _initialize_resources(self) -> None:
        """Инициализация ресурсов через фабрики"""
        # Регистрация фабрик инструментов
        from infrastructure.tools.file_reader_tool import FileReaderTool
        from infrastructure.tools.file_lister_tool import FileListerTool
        
        self._register_resource_factory("file_reader", lambda: FileReaderTool(
            name="file_reader",
            event_publisher=self._event_publisher,
            config={"root_dir": self._config.data_dir}
        ))
        self._register_resource_factory("file_lister", lambda: FileListerTool(
            name="file_lister",
            event_publisher=self._event_publisher,
            config={"root_dir": self._config.data_dir}
        ))

    def _register_resource_factory(self, name: str, factory: Callable) -> None:
        """Регистрация фабрики ресурса"""
        self._resource_factories[name] = factory

    def get_resource(self, resource_name: str) -> Any:
        """Получить ресурс по имени"""
        if resource_name in self._resources:
            return self._resources[resource_name]
        
        factory = self._resource_factories.get(resource_name)
        if not factory:
            raise ValueError(f"Resource '{resource_name}' not registered in system context")
        
        resource = factory()
        self._resources[resource_name] = resource
        return resource

    def get_event_bus(self) -> IEventPublisher:
        """Получить шину событий"""
        return self._event_publisher

    def get_capability(self, name: str) -> Optional[Capability]:
        """Получить capability по имени"""
        return self._capabilities.get(name)

    def list_capabilities(self) -> List[Capability]:
        """Получить список всех capability"""
        return list(self._capabilities.values())

    async def initialize(self) -> bool:
        """Инициализировать контекст"""
        if self._initialized:
            return True
        
        try:
            # 1. Настройка логирования
            await self._initialization_service.setup_logging()
            
            # 2. Регистрация обработчиков ДО инициализации ресурсов
            await self._register_system_handlers()
            
            # 3. Инициализация ресурсов через фабрики
            await self._initialize_resources()
            
            # 4. Инициализация провайдеров из конфигурации
            await self._initialization_service.initialize_providers_from_config()
            
            # 5. Регистрация capability из ресурсов
            await self._register_capabilities()
            
            self._initialized = True
            await self._event_publisher.publish(
                EventType.INFO, "SystemContext", {"message": "System initialized successfully"}
            )
            return True
        except Exception as e:
            await self._event_publisher.publish(
                EventType.ERROR, "SystemContext", {"message": "Initialization failed", "error": str(e)}
            )
            return False

    async def _register_capabilities(self) -> None:
        """Регистрация capability из ресурсов"""
        # Получение всех ресурсов и регистрация их capability
        for name, resource in self._resources.items():
            if hasattr(resource, 'get_capabilities'):
                capabilities = resource.get_capabilities()
                for cap in capabilities:
                    self._capabilities[cap.name] = cap

    async def shutdown(self) -> None:
        """Корректно завершить работу"""
        if not self._initialized:
            return
        
        try:
            # Обратный порядок: сначала ресурсы, потом шина
            for name in reversed(list(self._resources.keys())):
                resource = self._resources[name]
                if hasattr(resource, 'shutdown'):
                    if callable(getattr(resource, 'shutdown')):
                        await resource.shutdown()
            
            self._resources.clear()
            self._initialized = False
            await self._event_publisher.publish(
                EventType.INFO, "SystemContext", {"message": "System shutdown completed"}
            )
        except Exception as e:
            await self._event_publisher.publish(
                EventType.ERROR, "SystemContext", {"message": "Shutdown error", "error": str(e)}
            )

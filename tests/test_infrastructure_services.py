"""
Тесты для проверки регистрации и работы инфраструктурных сервисов через SystemContext.
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig
from core.infrastructure.service.base_service import BaseService
from core.infrastructure.service.table_description_service import TableDescriptionService
from core.events.event_bus import EventType


class MockService(BaseService):
    """Мок-класс для тестирования базового сервиса."""
    
    def __init__(self, system_context, name=None):
        super().__init__(system_context, name or "MockService")
        self.initialized_flag = False
        self.shutdown_flag = False
        self.operation_result = None
    
    async def initialize(self) -> bool:
        """Имитация инициализации сервиса."""
        self.initialized_flag = True
        return True
    
    async def shutdown(self) -> None:
        """Имитация завершения работы сервиса."""
        self.shutdown_flag = True


@pytest.mark.asyncio
async def test_register_service():
    """Тест регистрации инфраструктурного сервиса."""
    # Создаем временный каталог для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_register_service_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        
        # Создаем системный контекст
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Создаем мок-сервис
        mock_service = MockService(system_context)
        
        # Регистрируем сервис
        registration_success = await system_context.register_service("test_service", mock_service)
        assert registration_success is True
        
        # Проверяем, что сервис зарегистрирован
        assert "test_service" in system_context.service_registry
        assert system_context.service_registry["test_service"] is mock_service
        
        # Проверяем, что событие регистрации сервиса было опубликовано
        # (проверим через метрики обработчика событий)
        assert EventType.SERVICE_REGISTERED.value in system_context.metrics_handler.metrics
        assert system_context.metrics_handler.metrics[EventType.SERVICE_REGISTERED.value] >= 1
        
        # Завершаем работу системы
        await system_context.shutdown()
        
    finally:
        # Удаляем временный каталог
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_get_service():
    """Тест получения инфраструктурного сервиса по имени."""
    # Создаем временный каталог для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_get_service_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        
        # Создаем системный контекст
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Создаем мок-сервис
        mock_service = MockService(system_context, "GetTestService")
        
        # Регистрируем сервис
        registration_success = await system_context.register_service("get_test_service", mock_service)
        assert registration_success is True
        
        # Получаем сервис
        retrieved_service = await system_context.get_service("get_test_service")
        assert retrieved_service is mock_service
        assert retrieved_service.name == "GetTestService"
        
        # Проверяем получение несуществующего сервиса
        nonexistent_service = await system_context.get_service("nonexistent_service")
        assert nonexistent_service is None
        
        # Завершаем работу системы
        await system_context.shutdown()
        
    finally:
        # Удаляем временный каталог
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_initialize_infrastructure_services():
    """Тест инициализации инфраструктурных сервисов."""
    # Создаем временный каталог для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_init_services_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        
        # Создаем системный контекст
        system_context = SystemContext(config)
        
        # Создаем мок-сервисы
        service1 = MockService(system_context, "Service1")
        service2 = MockService(system_context, "Service2")
        
        # Регистрируем сервисы
        await system_context.register_service("service1", service1)
        await system_context.register_service("service2", service2)
        
        # Проверяем, что сервисы не инициализированы до вызова метода
        assert service1.initialized_flag is False
        assert service2.initialized_flag is False
        
        # Инициализируем инфраструктурные сервисы
        await system_context._initialize_infrastructure_services()
        
        # Проверяем, что сервисы были инициализированы
        assert service1.initialized_flag is True
        assert service2.initialized_flag is True
        
        # Проверяем, что события инициализации сервисов были опубликованы
        assert EventType.SERVICE_INITIALIZED.value in system_context.metrics_handler.metrics
        assert system_context.metrics_handler.metrics[EventType.SERVICE_INITIALIZED.value] >= 2  # по одному для каждого сервиса
        
        # Завершаем работу системы
        await system_context.shutdown()
        
    finally:
        # Удаляем временный каталог
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_shutdown_infrastructure_services():
    """Тест завершения работы инфраструктурных сервисов."""
    # Создаем временный каталог для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_shutdown_services_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        
        # Создаем системный контекст
        system_context = SystemContext(config)
        
        # Создаем мок-сервисы
        service1 = MockService(system_context, "ShutdownService1")
        service2 = MockService(system_context, "ShutdownService2")
        
        # Регистрируем сервисы
        await system_context.register_service("shutdown_service1", service1)
        await system_context.register_service("shutdown_service2", service2)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Проверяем, что сервисы не завершены до вызова метода
        assert service1.shutdown_flag is False
        assert service2.shutdown_flag is False
        
        # Завершаем работу инфраструктурных сервисов
        await system_context._shutdown_infrastructure_services()
        
        # Проверяем, что сервисы были завершены
        assert service1.shutdown_flag is True
        assert service2.shutdown_flag is True
        
        # Проверяем, что события завершения работы сервисов были опубликованы
        assert EventType.SERVICE_SHUTDOWN.value in system_context.metrics_handler.metrics
        assert system_context.metrics_handler.metrics[EventType.SERVICE_SHUTDOWN.value] >= 2  # по одному для каждого сервиса
        
        # Завершаем работу системы
        await system_context.shutdown()
        
    finally:
        # Удаляем временный каталог
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_table_description_service_registration():
    """Тест регистрации реального сервиса описания таблиц."""
    # Создаем временный каталог для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_table_desc_service_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        
        # Создаем системный контекст
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Создаем реальный сервис описания таблиц
        table_desc_service = TableDescriptionService(system_context)
        
        # Регистрируем сервис
        registration_success = await system_context.register_service("table_description", table_desc_service)
        assert registration_success is True
        
        # Проверяем, что сервис зарегистрирован
        assert "table_description" in system_context.service_registry
        assert system_context.service_registry["table_description"] is table_desc_service
        
        # Проверяем, что можно получить сервис
        retrieved_service = await system_context.get_service("table_description")
        assert retrieved_service is table_desc_service
        
        # Завершаем работу системы
        await system_context.shutdown()
        
    finally:
        # Удаляем временный каталог
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
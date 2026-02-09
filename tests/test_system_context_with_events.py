"""
Тесты для проверки интеграции SystemContext с шиной событий.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import tempfile
import os
import time

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig
from core.events.event_bus import EventType, get_event_bus
from core.events.event_handlers import LoggingEventHandler, MetricsEventHandler


@pytest.mark.asyncio
async def test_system_context_initialization_with_events():
    """Тест инициализации SystemContext с использованием шины событий."""
    # Создаем временную директорию для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_logs_" + str(int(time.time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию с временной директорией для логов
        config = SystemConfig()
        config.log_dir = temp_dir
        
        # Создаем SystemContext
        system_context = SystemContext(config)
        
        # Проверяем, что шина событий была инициализирована
        assert system_context.event_bus is not None
        
        # Проверяем, что обработчики событий были созданы
        assert hasattr(system_context, 'logging_handler')
        assert hasattr(system_context, 'metrics_handler')
        assert hasattr(system_context, 'audit_handler')
        
        # Инициализируем систему
        success = await system_context.initialize()
        
        # Проверяем, что инициализация прошла успешно
        assert success is True
        assert system_context.initialized is True
        
        # Проверяем, что были опубликованы соответствующие события
        # (проверим через метрики)
        assert EventType.SYSTEM_INITIALIZED.value in system_context.metrics_handler.metrics
        assert system_context.metrics_handler.metrics[EventType.SYSTEM_INITIALIZED.value] >= 1
    finally:
        # Удаляем временную директорию вручную
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass  # Игнорируем ошибки при удалении


@pytest.mark.asyncio
async def test_system_context_shutdown_with_events():
    """Тест завершения работы SystemContext с использованием шины событий."""
    # Создаем временную директорию для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_logs_" + str(int(time.time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию с временной директорией для логов
        config = SystemConfig()
        config.log_dir = temp_dir
        
        # Создаем SystemContext
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Завершаем работу системы
        await system_context.shutdown()
        
        # Проверяем, что были опубликованы соответствующие события
        assert EventType.SYSTEM_SHUTDOWN.value in system_context.metrics_handler.metrics
        assert system_context.metrics_handler.metrics[EventType.SYSTEM_SHUTDOWN.value] >= 1
    finally:
        # Удаляем временную директорию вручную
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass  # Игнорируем ошибки при удалении


@pytest.mark.asyncio
async def test_system_context_call_llm_with_events():
    """Тест вызова LLM через SystemContext с использованием шины событий."""
    # Создаем временную директорию для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_logs_" + str(int(time.time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию с временной директорией для логов
        config = SystemConfig()
        config.log_dir = temp_dir
        
        # Создаем SystemContext
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Проверяем, что вызов LLM (даже если завершится ошибкой из-за отсутствия провайдеров)
        # все равно генерирует события
        try:
            await system_context.call_llm("test prompt")
        except ValueError:
            # Ожидаем ошибку, потому что нет доступных LLM провайдеров
            pass
        
        # Проверяем, что были опубликованы соответствующие события
        assert EventType.LLM_CALL_STARTED.value in system_context.metrics_handler.metrics
        assert EventType.LLM_CALL_FAILED.value in system_context.metrics_handler.metrics
    finally:
        # Удаляем временную директорию вручную
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass  # Игнорируем ошибки при удалении


@pytest.mark.asyncio
async def test_system_context_create_agent_with_events():
    """Тест создания агента через SystemContext с использованием шины событий."""
    # Создаем временную директорию для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "test_logs_" + str(int(time.time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию с временной директорией для логов
        config = SystemConfig()
        config.log_dir = temp_dir
        
        # Создаем SystemContext
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Создаем агента
        agent = await system_context.create_agent()
        
        # Проверяем, что были опубликованы соответствующие события
        assert EventType.AGENT_CREATED.value in system_context.metrics_handler.metrics
        assert system_context.metrics_handler.metrics[EventType.AGENT_CREATED.value] >= 1
    finally:
        # Удаляем временную директорию вручную
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass  # Игнорируем ошибки при удалении


if __name__ == "__main__":
    pytest.main([__file__])
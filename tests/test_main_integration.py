"""
Тесты для проверки взаимодействия Application (из main.py) с остальными компонентами системы.
"""
import pytest
import asyncio
import tempfile
import os
import argparse
from unittest.mock import Mock, patch

from main import Application, parse_arguments
from core.config.models import SystemConfig
from core.system_context.system_context import SystemContext


def test_argument_parsing():
    """Тест парсинга аргументов командной строки."""
    # Тестируем аргументы по умолчанию
    args = parse_arguments()
    assert args.goal == "Какие книги написал Пушкин?"
    assert args.profile == "dev"
    
    # Тестируем с переданными аргументами
    import sys
    original_argv = sys.argv.copy()
    
    try:
        sys.argv = ["main.py", "Тестовый вопрос", "--profile", "dev", "--debug"]
        args = parse_arguments()
        assert args.goal == "Тестовый вопрос"
        assert args.profile == "dev"
        assert args.debug is True
    finally:
        sys.argv = original_argv


@pytest.mark.asyncio
async def test_application_initialization_with_mock_config():
    """Тест инициализации приложения с минимальной конфигурацией."""
    temp_dir = os.path.join(tempfile.gettempdir(), "app_init_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем аргументы для приложения
        args = argparse.Namespace()
        args.profile = "dev"
        args.debug = False
        args.max_steps = None
        args.temperature = None
        args.max_tokens = None
        args.strategy = None
        args.output = None
        args.goal = "Тестовая цель"
        
        app = Application(args)
        
        # Создаем минимальную конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        # Подменяем функцию получения конфигурации
        with patch('main.get_config', return_value=config):
            # Инициализируем приложение
            await app.initialize()
            
            # Проверяем, что системный контекст создан
            assert app.system_context is not None
            assert app.config is not None
            
            # Проверяем, что система инициализирована
            assert app.system_context.initialized is True
            
            # Завершаем работу
            await app.shutdown()
            
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_application_with_minimal_real_components():
    """Тест приложения с минимальными реальными компонентами."""
    temp_dir = os.path.join(tempfile.gettempdir(), "app_real_comp_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем аргументы для приложения
        args = argparse.Namespace()
        args.profile = "dev"
        args.debug = False
        args.max_steps = None
        args.temperature = None
        args.max_tokens = None
        args.strategy = None
        args.output = None
        args.goal = "Тестовая цель"
        
        app = Application(args)
        
        # Создаем реальный SystemContext с минимальной конфигурацией
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        # Присваиваем конфигурацию напрямую
        app.config = config
        app.system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await app.system_context.initialize()
        assert success is True
        
        # Проверяем, что все компоненты созданы
        assert app.system_context is not None
        assert app.system_context.registry is not None
        assert app.system_context.capabilities is not None
        assert app.system_context.event_bus is not None
        
        # Применяем переопределения конфигурации
        app._apply_config_overrides()
        
        # Проверяем, что приложение может выполнить базовую операцию
        # Создаем сессию для тестирования
        from core.session_context.session_context import SessionContext
        app.session = SessionContext()
        
        # Завершаем работу
        await app.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_application_run_method_with_mocked_agent():
    """Тест метода run приложения с замоканным агентом."""
    temp_dir = os.path.join(tempfile.gettempdir(), "app_run_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем аргументы для приложения
        args = argparse.Namespace()
        args.profile = "dev"
        args.debug = False
        args.max_steps = None
        args.temperature = None
        args.max_tokens = None
        args.strategy = None
        args.output = None
        args.goal = "Тестовая цель"
        
        app = Application(args)
        
        # Создаем конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        # Создаем системный контекст
        app.config = config
        app.system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await app.system_context.initialize()
        assert success is True
        
        # Создаем сессию для тестирования
        from core.session_context.session_context import SessionContext
        app.session = SessionContext()
        
        # Замокаем метод create_agent, чтобы избежать ошибок из-за отсутствия провайдеров
        async def mock_create_agent(**kwargs):
            # Создаем mock агента
            mock_agent = Mock()
            mock_agent.execute = Mock()
            mock_agent.execute.return_value = "Тестовый результат"
            mock_agent.session = SessionContext()
            return mock_agent
        
        # Заменяем метод create_agent
        app.system_context.create_agent = mock_create_agent
        
        # Выполняем тест
        result = await app.run()
        
        # Проверяем результат
        assert result["success"] is True
        assert result["goal"] == "Тестовая цель"
        
        # Завершаем работу
        await app.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_application_lifecycle():
    """Тест полного жизненного цикла приложения."""
    temp_dir = os.path.join(tempfile.gettempdir(), "app_lifecycle_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем аргументы для приложения
        args = argparse.Namespace()
        args.profile = "dev"
        args.debug = False
        args.max_steps = None
        args.temperature = None
        args.max_tokens = None
        args.strategy = None
        args.output = None
        args.goal = "Тестовая цель"
        
        app = Application(args)
        
        # Создаем конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        # Инициализируем приложение
        app.config = config
        app.system_context = SystemContext(config)
        
        success = await app.system_context.initialize()
        assert success is True
        
        # Проверяем, что все компоненты инициализированы
        assert app.system_context.initialized is True
        
        # Создаем сессию
        from core.session_context.session_context import SessionContext
        app.session = SessionContext()
        
        # Завершаем работу
        await app.shutdown()
        
        # Проверяем, что система завершена
        assert app.system_context.initialized is False
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
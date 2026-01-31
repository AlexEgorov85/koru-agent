"""
Тесты для базового класса сервиса (BaseService).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.infrastructure.services.base_service import BaseService
from core.system_context.base_system_contex import BaseSystemContext


class ConcreteService(BaseService):
    """Конкретная реализация BaseService для тестов."""
    
    async def initialize(self) -> bool:
        return True
    
    async def shutdown(self) -> None:
        pass


class TestBaseService:
    """Тесты для BaseService."""
    
    def test_initialization(self):
        """Тест инициализации сервиса."""
        service = ConcreteService("test_service", config_param="test_value")
        
        assert service.name == "test_service"
        assert service.config == {"config_param": "test_value"}
        assert service.is_initialized is False
    
    def test_initialization_with_system_context(self):
        """Тест инициализации сервиса с системным контекстом."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        service = ConcreteService("test_service", mock_system_context, config_param="test_value")
        
        assert service.name == "test_service"
        assert service.system_context == mock_system_context
        assert service.config == {"config_param": "test_value"}
        assert service.is_initialized is False
    
    def test_get_config(self):
        """Тест метода get_config."""
        service = ConcreteService("test_service", config_param="test_value", another_param=123)
        config = service.get_config()
        
        assert config == {"config_param": "test_value", "another_param": 123}
    
    def test_set_config(self):
        """Тест метода set_config."""
        service = ConcreteService("test_service")
        new_config = {"new_param": "new_value", "another_param": 456}
        
        service.set_config(new_config)
        
        assert service.config == {"new_param": "new_value", "another_param": 456}
    
    def test_get_system_context(self):
        """Тест метода get_system_context."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        service = ConcreteService("test_service", mock_system_context)
        
        context = service.get_system_context()
        
        assert context == mock_system_context
    
    def test_set_system_context(self):
        """Тест метода set_system_context."""
        service = ConcreteService("test_service")
        mock_system_context = MagicMock(spec=BaseSystemContext)
        
        service.set_system_context(mock_system_context)
        
        assert service.system_context == mock_system_context
    
    @pytest.mark.asyncio
    async def test_initialize_method(self):
        """Тест метода initialize."""
        service = ConcreteService("test_service")
        
        result = await service.initialize()
        
        assert result is True
        assert service.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_shutdown_method(self):
        """Тест метода shutdown."""
        service = ConcreteService("test_service")
        
        # Просто проверяем, что метод не вызывает исключений
        await service.shutdown()


def test_base_service_abstract_methods():
    """Тест, что BaseService нельзя инстанцировать без реализации абстрактных методов."""
    
    with pytest.raises(TypeError):
        BaseService("test")
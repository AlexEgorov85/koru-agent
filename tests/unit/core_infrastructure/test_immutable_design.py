"""
Юнит-тесты для проверки иммутабельности InfrastructureContext.

Тестирует:
- Запрет на изменение атрибутов после инициализации
- Возможность изменения до инициализации
"""
import pytest
from unittest.mock import AsyncMock, patch

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext


def test_can_modify_attributes_before_initialization():
    """Проверка: можно изменять атрибуты до инициализации"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # До инициализации можно изменять атрибуты
    infra.test_attribute = "test_value"
    assert infra.test_attribute == "test_value"


@pytest.mark.asyncio
async def test_cannot_modify_attributes_after_initialization():
    """Проверка: нельзя изменять атрибуты после инициализации"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Инициализация
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # После инициализации нельзя изменять атрибуты
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.test_attribute = "test_value"


@pytest.mark.asyncio
async def test_cannot_modify_existing_attributes_after_initialization():
    """Проверка: нельзя изменять существующие атрибуты после инициализации"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Инициализация
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # После инициализации нельзя изменять существующие атрибуты
    original_config = infra.config
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.config = SystemConfig()
    
    # Убедимся, что атрибут не изменился
    assert infra.config is original_config


@pytest.mark.asyncio
async def test_internal_initialized_flag_can_be_modified():
    """Проверка: внутренний флаг _initialized можно изменять даже после инициализации"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Инициализация
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # Внутренний флаг _initialized можно изменять
    infra._initialized = False  # Это допустимо, так как это внутренний атрибут
    assert infra._initialized is False


@pytest.mark.asyncio
async def test_attribute_modification_error_message():
    """Проверка: сообщение об ошибке при попытке модификации содержит нужный текст"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Инициализация
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # Проверка сообщения об ошибке
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.some_attribute = "some_value"


@pytest.mark.asyncio
async def test_multiple_attribute_modifications_blocked():
    """Проверка: блокировка модификации работает для всех атрибутов после инициализации"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Инициализация
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # Попытка изменить разные атрибуты
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.new_attr1 = "value1"
    
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.new_attr2 = "value2"
    
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.config = SystemConfig()
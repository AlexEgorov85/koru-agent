"""
Юнит-тесты для InfrastructureContext.

Тестирует:
- Логику инициализации/завершения
- Регистрацию только включённых провайдеров
- Иммутабельность после инициализации
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext


@pytest.mark.asyncio
async def test_infrastructure_registers_only_enabled_providers():
    """Проверка: только включённые провайдеры регистрируются"""
    # Подготовка конфигурации с включённым и отключённым провайдерами
    config = SystemConfig(
        llm_providers={
            "prod_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="qwen-4b",
                enabled=True,
                parameters={"model_name": "qwen-4b", "temperature": 0.7}
            ),
            "backup_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="qwen-4b",
                enabled=False,  # ← Отключён
                parameters={"model_name": "qwen-4b", "temperature": 0.7}
            ),
        },
        db_providers={
            "primary_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={"database": "test_primary.db", "host": "localhost"}
            ),
            "secondary_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=False,  # ← Отключён
                parameters={"database": "test_secondary.db", "host": "localhost"}
            ),
        }
    )
    
    # Создание и инициализация инфраструктурного контекста
    infra = InfrastructureContext(config)
    
    # Вызов метода инициализации, который сам регистрирует провайдеров
    await infra.initialize()
    
    # Проверка: только включённые провайдеры в реестре
    resource_names = infra.resource_registry.get_all_names()
    
    # prod_llm должен быть зарегистрирован
    assert "prod_llm" in resource_names
    # backup_llm не должен быть зарегистрирован
    assert "backup_llm" not in resource_names
    
    # primary_db должен быть зарегистрирован
    assert "primary_db" in resource_names
    # secondary_db не должен быть зарегистрирован
    assert "secondary_db" not in resource_names


@pytest.mark.asyncio
async def test_infrastructure_immutable_after_init():
    """Проверка: контекст становится неизменяемым после инициализации"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Инициализация
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # Попытка изменения после инициализации → исключение
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.new_attribute = "value"


@pytest.mark.asyncio
async def test_infrastructure_cannot_be_modified_after_init():
    """Проверка: нельзя изменять атрибуты после инициализации"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Инициализация
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # Попытка изменить существующий атрибут
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.config = SystemConfig()


def test_infrastructure_context_initialization_state():
    """Проверка начального состояния контекста до инициализации"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Проверка начальных значений
    assert infra._initialized is False
    assert infra.id is not None
    assert infra.config == config
    assert infra.lifecycle_manager is None
    assert infra.event_bus is None
    assert infra.resource_registry is None


@pytest.mark.asyncio
async def test_infrastructure_initialize_twice():
    """Проверка: повторная инициализация не вызывает ошибок"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # Мокируем внутренние методы
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        
        # Первая инициализация
        result1 = await infra.initialize()
        assert result1 is True
        assert infra._initialized is True
        
        # Вторая инициализация (должна вернуть True без ошибок)
        result2 = await infra.initialize()
        assert result2 is True


@pytest.mark.asyncio
async def test_get_provider_returns_correct_instance():
    """Проверка: получение провайдера по имени работает корректно"""
    config = SystemConfig()
    infra = InfrastructureContext(config)

    # Инициализируем инфраструктуру
    await infra.initialize()

    # Регистрируем мок-провайдер через реестр ресурсов
    from core.models.resource import ResourceInfo, ResourceType
    mock_provider = MagicMock()
    resource_info = ResourceInfo(
        name="test_provider",
        resource_type=ResourceType.LLM_PROVIDER,
        instance=mock_provider
    )
    infra.resource_registry.register_resource(resource_info)

    # Получаем провайдер
    retrieved = infra.get_provider("test_provider")

    assert retrieved is mock_provider


@pytest.mark.asyncio
async def test_get_nonexistent_provider_returns_none():
    """Проверка: получение несуществующего провайдера возвращает None"""
    config = SystemConfig()
    infra = InfrastructureContext(config)

    # Инициализируем инфраструктуру
    await infra.initialize()

    # Получаем несуществующий провайдер
    retrieved = infra.get_provider("nonexistent_provider")

    assert retrieved is None


@pytest.mark.asyncio
async def test_get_resource_returns_correct_instance():
    """Проверка: получение ресурса по имени работает корректно"""
    config = SystemConfig()
    infra = InfrastructureContext(config)

    # Инициализируем контекст
    await infra.initialize()

    # Регистрируем тестовый ресурс
    from core.models.resource import ResourceInfo, ResourceType
    test_resource = MagicMock()
    resource_info = ResourceInfo(
        name="test_resource",
        resource_type=ResourceType.OTHER,
        instance=test_resource
    )
    infra.resource_registry.register_resource(resource_info)

    # Получаем ресурс
    retrieved = infra.get_resource("test_resource")
    assert retrieved is test_resource


@pytest.mark.asyncio
async def test_shutdown_sets_initialized_to_false():
    """Проверка: shutdown устанавливает _initialized в False"""
    config = SystemConfig()
    infra = InfrastructureContext(config)

    # Инициализация
    await infra.initialize()

    assert infra._initialized is True

    # Завершение работы
    await infra.shutdown()

    assert infra._initialized is False
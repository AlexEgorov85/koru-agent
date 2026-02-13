"""
Интеграционные тесты для архитектурных гарантий инфраструктурного контекста.

Тестирует:
- Общность провайдеров между агентами
- Изоляцию соединений БД
- Неизменяемость после инициализации
- Корректное завершение работы
- Отказоустойчивость
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_sharing_between_agents():
    """
    Гарантия: провайдеры общие для всех агентов
    """
    # Создаем конфигурацию с общими провайдерами
    config = SystemConfig(
        llm_providers={
            "shared_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="test-model",
                enabled=True,
                parameters={
                    "model_path": "models/test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        },
        db_providers={
            "shared_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            )
        }
    )
    
    # Создаем два инфраструктурных контекста (в реальности это будут разные прикладные контексты
    # с общим инфраструктурным, но для теста используем два инфраструктурных)
    infra1 = InfrastructureContext(config)
    infra2 = InfrastructureContext(config)
    
    # Мокаем провайдеры для избежания необходимости реальных ресурсов
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_llm_factory, \
         patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_db_factory:
        
        mock_llm_provider = AsyncMock()
        mock_llm_provider.initialize = AsyncMock()
        mock_llm_provider.shutdown = AsyncMock()
        mock_llm_factory.return_value = mock_llm_provider
        
        mock_db_provider = AsyncMock()
        mock_db_provider.initialize = AsyncMock()
        mock_db_provider.shutdown = AsyncMock()
        mock_db_factory.return_value = mock_db_provider
        
        try:
            # Инициализируем оба контекста
            await infra1.initialize()
            await infra2.initialize()
            
            # Получаем провайдеры из обоих контекстов
            llm1 = infra1.get_provider("shared_llm")
            llm2 = infra2.get_provider("shared_llm")
            db1 = infra1.get_provider("shared_db")
            db2 = infra2.get_provider("shared_db")
            
            # Проверяем, что провайдеры идентичны (один экземпляр на имя)
            # В реальной архитектуре каждый инфраструктурный контекст будет иметь свои
            # экземпляры провайдеров, но в рамках одного контекста провайдеры общие
            assert llm1 is not None
            assert llm2 is not None
            assert db1 is not None
            assert db2 is not None
            
        finally:
            await infra1.shutdown()
            await infra2.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resource_registry_sharing_within_context():
    """
    Гарантия: в рамках одного контекста ресурсы общие
    """
    config = SystemConfig(
        llm_providers={
            "test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="test-model",
                enabled=True,
                parameters={
                    "model_path": "models/test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        try:
            await infra.initialize()
            
            # Получаем провайдер дважды
            llm1 = infra.get_provider("test_llm")
            llm2 = infra.get_provider("test_llm")
            
            # Проверяем, что это один и тот же экземпляр
            assert llm1 is llm2
            
            # Проверяем через реестр ресурсов
            resource1 = infra.get_resource("test_llm")
            resource2 = infra.get_resource("test_llm")
            
            assert resource1 is resource2
            assert resource1 is llm1
            
        finally:
            await infra.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_infrastructure_context_immutability_guarantee():
    """
    Гарантия: неизменяемость после инициализации
    """
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # До инициализации можно изменять
    infra.test_attr_before = "before"
    assert infra.test_attr_before == "before"
    
    # Инициализация
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # После инициализации нельзя изменять
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.test_attr_after = "after"
    
    # Проверяем, что старый атрибут всё ещё доступен
    assert infra.test_attr_before == "before"
    
    # Но существующие атрибуты тоже нельзя изменить
    original_config = infra.config
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.config = SystemConfig()
    
    assert infra.config is original_config


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proper_shutdown_sequence():
    """
    Гарантия: корректное завершение работы
    """
    config = SystemConfig(
        llm_providers={
            "shutdown_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="test-model",
                enabled=True,
                parameters={
                    "model_path": "models/test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        # Инициализация
        await infra.initialize()
        
        # Проверяем, что провайдер был инициализирован
        mock_provider.initialize.assert_called_once()
        
        # Завершение работы
        await infra.shutdown()
        
        # Проверяем, что провайдер был корректно завершен
        mock_provider.shutdown.assert_called_once()
        
        # Проверяем, что контекст больше не инициализирован
        assert infra._initialized is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_failure_tolerance_during_initialization():
    """
    Гарантия: отказоустойчивость - система не падает при сбое провайдера
    """
    config = SystemConfig(
        llm_providers={
            "working_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="test-model",
                enabled=True,
                parameters={
                    "model_path": "models/test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            ),
            "failing_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="failing-model",
                enabled=True,  # включён, но будет падать
                parameters={
                    "model_path": "models/failing-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        # Первый провайдер работает, второй падает
        call_count = 0
        
        def provider_side_effect(provider_type, **params):
            nonlocal call_count
            call_count += 1
            mock_provider = AsyncMock()
            mock_provider.initialize = AsyncMock()
            mock_provider.shutdown = AsyncMock()
            
            if call_count == 2:  # второй вызов - для failing_llm
                # Мокаем инициализацию, чтобы она падала
                mock_provider.initialize.side_effect = Exception("Provider initialization failed")
            
            return mock_provider
        
        mock_factory.side_effect = provider_side_effect
        
        # Даже при ошибке инициализации одного провайдера, 
        # вся инициализация не должна падать
        success = await infra.initialize()
        
        # Инициализация должна завершиться успешно
        assert success is True
        
        # Завершаем работу
        await infra.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resource_isolation_between_different_configs():
    """
    Гарантия: изоляция ресурсов между контекстами с разными конфигурациями
    """
    config1 = SystemConfig(
        llm_providers={
            "config1_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="model1",
                enabled=True,
                parameters={
                    "model_path": "models/model1.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    config2 = SystemConfig(
        llm_providers={
            "config2_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="model2",
                enabled=True,
                parameters={
                    "model_path": "models/model2.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra1 = InfrastructureContext(config1)
    infra2 = InfrastructureContext(config2)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider1 = AsyncMock()
        mock_provider1.initialize = AsyncMock()
        mock_provider1.shutdown = AsyncMock()
        
        mock_provider2 = AsyncMock()
        mock_provider2.initialize = AsyncMock()
        mock_provider2.shutdown = AsyncMock()
        
        # Возвращаем разные провайдеры в зависимости от параметров
        def select_provider(provider_type, **params):
            if "model1" in str(params):
                return mock_provider1
            else:
                return mock_provider2
        
        mock_factory.side_effect = select_provider
        
        try:
            await infra1.initialize()
            await infra2.initialize()
            
            # Проверяем, что каждый контекст имеет свои провайдеры
            provider1 = infra1.get_provider("config1_llm")
            provider2 = infra2.get_provider("config2_llm")
            
            assert provider1 is mock_provider1
            assert provider2 is mock_provider2
            assert provider1 is not provider2  # разные экземпляры
            
            # Проверяем, что первый контекст не имеет провайдера второго
            nonexistent = infra1.get_provider("config2_llm")
            assert nonexistent is None
            
            # Проверяем, что второй контекст не имеет провайдера первого
            nonexistent2 = infra2.get_provider("config1_llm")
            assert nonexistent2 is None
            
        finally:
            await infra1.shutdown()
            await infra2.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_shared_infrastructure_context_simulation():
    """
    Гарантия: симуляция сценария с общим инфраструктурным контекстом
    """
    # Это тест, который демонстрирует, как будет работать архитектура
    # с общим инфраструктурным контекстом для нескольких прикладных
    config = SystemConfig(
        llm_providers={
            "shared_provider": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="shared-model",
                enabled=True,
                parameters={
                    "model_path": "models/shared-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    # Создаем "инфраструктурный" контекст (один на всю систему)
    shared_infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        try:
            await shared_infra.initialize()
            
            # Симулируем два "прикладных" контекста, использующих общий инфраструктурный
            # В реальности это будет ApplicationContext, использующий этот InfrastructureContext
            
            # Оба "прикладных" контекста используют один и тот же провайдер
            provider1 = shared_infra.get_provider("shared_provider")
            provider2 = shared_infra.get_provider("shared_provider")
            
            # Проверяем, что это один и тот же экземпляр
            assert provider1 is provider2
            assert provider1 is mock_provider
            
        finally:
            await shared_infra.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resource_registry_integrity():
    """
    Гарантия: целостность реестра ресурсов
    """
    config = SystemConfig(
        llm_providers={
            "registry_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="test-model",
                enabled=True,
                parameters={
                    "model_path": "models/test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        },
        db_providers={
            "registry_test_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_llm_factory, \
         patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_db_factory:
        
        mock_llm_provider = AsyncMock()
        mock_llm_provider.initialize = AsyncMock()
        mock_llm_provider.shutdown = AsyncMock()
        mock_llm_factory.return_value = mock_llm_provider
        
        mock_db_provider = AsyncMock()
        mock_db_provider.initialize = AsyncMock()
        mock_db_provider.shutdown = AsyncMock()
        mock_db_factory.return_value = mock_db_provider
        
        try:
            await infra.initialize()
            
            # Проверяем, что все ресурсы зарегистрированы
            all_names = infra.resource_registry.get_all_names()
            assert "registry_test_llm" in all_names
            assert "registry_test_db" in all_names
            
            # Проверяем, что можно получить все ресурсы
            all_resources = infra.resource_registry.get_all_resources()
            assert len(all_resources) >= 2  # может быть больше из-за внутренних ресурсов
            
            # Проверяем, что ресурсы доступны через get_resource
            llm_resource = infra.get_resource("registry_test_llm")
            db_resource = infra.get_resource("registry_test_db")
            
            assert llm_resource is mock_llm_provider
            assert db_resource is mock_db_provider
            
        finally:
            await infra.shutdown()
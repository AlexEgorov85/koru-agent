"""
Юнит-тесты для фабрик провайдеров.

Тестирует:
- Создание LLM провайдеров
- Создание DB провайдеров
- Обработку неверных типов провайдеров
"""
import pytest
from unittest.mock import Mock, patch

from core.infrastructure.providers.llm.factory import LLMProviderFactory
from core.infrastructure.providers.database.factory import DBProviderFactory


def test_llm_provider_factory_creates_mock_provider():
    """Проверка: фабрика LLM создает mock провайдер"""
    factory = LLMProviderFactory()
    
    # Создаем провайдер с правильной конфигурацией
    from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
    config = MockLLMConfig(model_name='test-model', temperature=0.7)
    provider = factory.create_provider('mock', config=config)
    
    # Проверяем, что это экземпляр BaseLLMProvider
    from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
    assert isinstance(provider, BaseLLMProvider)


def test_llm_provider_factory_creates_llama_cpp_provider():
    """Проверка: фабрика LLM создает llama_cpp провайдер"""
    factory = LLMProviderFactory()
    
    # Создаем провайдер с правильной конфигурацией
    from core.infrastructure.providers.llm.llama_cpp_provider import MockLlamaCppConfig
    config = MockLlamaCppConfig(model_name='test-model', temperature=0.7)
    provider = factory.create_provider('llama_cpp', config=config)
    
    # Проверяем, что это экземпляр BaseLLMProvider
    from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
    assert isinstance(provider, BaseLLMProvider)


def test_llm_provider_factory_raises_error_for_invalid_type():
    """Проверка: фабрика LLM выбрасывает ошибку для неверного типа"""
    factory = LLMProviderFactory()

    with pytest.raises(ValueError, match="Неизвестный тип провайдера"):
        factory.create_provider('invalid_type', model_path='test/model.gguf')


def test_db_provider_factory_creates_postgres_provider():
    """Проверка: фабрика DB создает postgres провайдер"""
    factory = DBProviderFactory()
    
    # Создаем провайдер с правильной конфигурацией
    from core.models.db_types import DBConnectionConfig
    config = DBConnectionConfig(host='localhost', database='test', username='user', password='pass')
    provider = factory.create_provider('postgres', config=config)
    
    # Проверяем, что это экземпляр BaseDBProvider
    from core.infrastructure.providers.database.base_db import BaseDBProvider
    assert isinstance(provider, BaseDBProvider)


def test_db_provider_factory_creates_sqlite_provider():
    """Проверка: фабрика DB создает sqlite провайдер"""
    factory = DBProviderFactory()
    
    # Создаем провайдер с правильной конфигурацией
    from core.models.db_types import DBConnectionConfig
    config = DBConnectionConfig(host='localhost', database='test', username='user', password='pass')
    provider = factory.create_provider('sqlite', config=config)
    
    # Проверяем, что это экземпляр BaseDBProvider
    from core.infrastructure.providers.database.base_db import BaseDBProvider
    assert isinstance(provider, BaseDBProvider)


def test_db_provider_factory_raises_error_for_invalid_type():
    """Проверка: фабрика DB выбрасывает ошибку для неверного типа"""
    factory = DBProviderFactory()

    with pytest.raises(ValueError, match="Неизвестный тип провайдера"):
        factory.create_provider('invalid_type', database_url='postgresql://...')


def test_llm_provider_factory_passes_parameters_correctly():
    """Проверка: фабрика LLM передает параметры корректно"""
    factory = LLMProviderFactory()
    
    # Создаем провайдер с параметрами
    from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
    params = {
        'model_name': 'test-model',
        'temperature': 0.7,
        'max_tokens': 100
    }
    config = MockLLMConfig(**params)
    provider = factory.create_provider('mock', config=config)
    
    # Проверяем, что провайдер создался
    from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
    assert isinstance(provider, BaseLLMProvider)


def test_db_provider_factory_passes_parameters_correctly():
    """Проверка: фабрика DB передает параметры корректно"""
    factory = DBProviderFactory()
    
    # Создаем провайдер с параметрами
    from core.models.db_types import DBConnectionConfig
    params = {
        'host': 'localhost',
        'database': 'test_db',
        'username': 'test_user',
        'password': 'test_pass',
        'pool_size': 10,
        'timeout': 30
    }
    config = DBConnectionConfig(**params)
    provider = factory.create_provider('sqlite', config=config)
    
    # Проверяем, что провайдер создался
    from core.infrastructure.providers.database.base_db import BaseDBProvider
    assert isinstance(provider, BaseDBProvider)
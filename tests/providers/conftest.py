"""
Конфигурация для тестов провайдеров.
Содержит фикстуры и настройки для всех тестов в пакете.
"""
import pytest
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from providers.base_llm import BaseLLMProvider, LLMRequest, LLMResponse
from providers.base_db import BaseDBProvider, DBConnectionConfig
from providers.vllm_provider import VLLMProvider
from providers.llama_cpp_provider import LlamaCppProvider
from providers.postgres_provider import PostgreSQLProvider
from providers.factory import ProviderFactory

# ==========================================================
# Глобальные настройки
# ==========================================================

def pytest_configure(config):
    """Настройка переменных окружения для тестов."""
    # Отключаем логирование для тестов (кроме ошибок)
    import logging
    for logger_name in ['root', 'providers', 'asyncpg', 'vllm', 'llama_cpp']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)

@pytest.fixture(scope="session")
def event_loop():
    """Фикстура для асинхронных тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# ==========================================================
# Фикстуры конфигураций
# ==========================================================

@pytest.fixture
def mock_llm_config():
    """Фикстура с конфигурацией для LLM провайдера."""
    return {
        "temperature": 0.7,
        "max_tokens": 500,
        "top_p": 0.95
    }

@pytest.fixture
def mock_db_config():
    """Фикстура с конфигурацией для PostgreSQL провайдера."""
    return {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "username": "test_user",
        "password": "test_password",
        "timeout": 10.0,
        "pool_size": 5
    }

@pytest.fixture
def db_connection_config(mock_db_config):
    """Фикстура с конфигурацией подключения к БД как объектом."""
    return DBConnectionConfig(**mock_db_config)

# ==========================================================
# Фикстуры моков
# ==========================================================

@pytest.fixture
def mock_vllm_engine():
    """Фикстура с моком vLLM движка."""
    with patch('providers.vllm_provider.AsyncLLMEngine') as mock_engine:
        mock_instance = AsyncMock()
        mock_engine.from_engine_args.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_llama_cpp_engine():
    """Фикстура с моком Llama.cpp движка."""
    with patch('providers.llama_cpp_provider.Llama') as mock_engine:
        mock_instance = MagicMock()
        mock_engine.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_asyncpg_pool():
    """Фикстура с моком asyncpg пула соединений."""
    with patch('providers.postgres_provider.asyncpg.create_pool') as mock_create_pool:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Настройка контекстного менеджера для соединения
        mock_conn_ctx = AsyncMock()
        mock_conn_ctx.__aenter__.return_value = mock_conn
        mock_conn_ctx.__aexit__.return_value = None
        
        mock_pool.acquire.return_value = mock_conn_ctx
        mock_create_pool.return_value = mock_pool
        yield mock_pool, mock_conn

# ==========================================================
# Фикстуры провайдеров
# ==========================================================

@pytest.fixture
async def vllm_provider(mock_llm_config, mock_vllm_engine):
    """Фикстура с инициализированным VLLMProvider."""
    provider = VLLMProvider("test-model", mock_llm_config)
    # Мокаем инициализацию
    with patch.object(provider, '_load_vllm_engine', return_value=mock_vllm_engine):
        success = await provider.initialize()
        assert success, "Failed to initialize VLLMProvider"
    return provider

@pytest.fixture
async def llama_cpp_provider(mock_llm_config, mock_llama_cpp_engine):
    """Фикстура с инициализированным LlamaCppProvider."""
    provider = LlamaCppProvider("test-model", mock_llm_config)
    # Мокаем инициализацию
    with patch.object(provider, '_load_llama_cpp_engine', return_value=mock_llama_cpp_engine):
        success = await provider.initialize()
        assert success, "Failed to initialize LlamaCppProvider"
    return provider

@pytest.fixture
async def postgres_provider(db_connection_config, mock_asyncpg_pool):
    """Фикстура с инициализированным PostgreSQLProvider."""
    provider = PostgreSQLProvider(db_connection_config)
    # Мокаем инициализацию
    success = await provider.initialize()
    assert success, "Failed to initialize PostgreSQLProvider"
    return provider
"""
Интеграционные тесты для DB провайдеров.

Тестирует:
- Работоспособность DB провайдера через простой запрос
- Правильное управление соединениями
- Изоляцию соединений при параллельных запросах
"""
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from core.config.models import SystemConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext


@pytest.mark.integration
@pytest.mark.asyncio
async def test_db_provider_basic_functionality():
    """
    Интеграционный тест: проверка базовой функциональности DB провайдера
    """
    # Пропускаем, если нет флага
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Пропущено: нет флага RUN_INTEGRATION_TESTS")
    
    # Создаем конфигурацию с тестовой БД
    config = SystemConfig(
        db_providers={
            "test_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    # Мокаем создание реального провайдера
    with patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.execute_query = AsyncMock(return_value=type('Result', (), {
            'rowcount': 1,
            'rows': [{'test': 1}],
            'columns': ['test']
        })())
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        try:
            await infra.initialize()
            
            # Получаем провайдер из инфраструктурного контекста
            db = infra.get_provider("test_db")
            
            # Выполняем простой запрос
            result = await db.execute_query("SELECT 1 AS test")
            
            assert result.rowcount == 1
            assert len(result.rows) == 1
            assert result.rows[0]["test"] == 1
            
            # Проверяем, что метод был вызван с правильными параметрами
            mock_provider.execute_query.assert_called_once_with("SELECT 1 AS test")
            
        finally:
            await infra.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_db_provider_connection_isolation():
    """
    Интеграционный тест: проверка изоляции соединений БД
    """
    # Пропускаем, если нет флага
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Пропущено: нет флага RUN_INTEGRATION_TESTS")
    
    # Создаем конфигурацию с двумя БД для проверки изоляции
    config = SystemConfig(
        db_providers={
            "db1": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            ),
            "db2": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_factory:
        mock_provider1 = AsyncMock()
        mock_provider1.initialize = AsyncMock()
        mock_provider1.execute_query = AsyncMock(return_value=type('Result', (), {
            'rowcount': 1,
            'rows': [{'db_id': 1}]
        })())
        mock_provider1.shutdown = AsyncMock()
        
        mock_provider2 = AsyncMock()
        mock_provider2.initialize = AsyncMock()
        mock_provider2.execute_query = AsyncMock(return_value=type('Result', (), {
            'rowcount': 1,
            'rows': [{'db_id': 2}]
        })())
        mock_provider2.shutdown = AsyncMock()
        
        # Возвращаем разные провайдеры в зависимости от параметров
        def provider_selector(provider_type, **params):
            if 'db1' in str(params):
                return mock_provider1
            else:
                return mock_provider2
        
        mock_factory.side_effect = provider_selector
        
        try:
            await infra.initialize()
            
            # Получаем оба провайдера
            db1 = infra.get_provider("db1")
            db2 = infra.get_provider("db2")
            
            # Выполняем запросы к разным БД
            result1 = await db1.execute_query("SELECT 1 AS db_id")
            result2 = await db2.execute_query("SELECT 2 AS db_id")
            
            # Проверяем, что результаты соответствуют разным БД
            assert result1.rows[0]["db_id"] == 1
            assert result2.rows[0]["db_id"] == 2
            
            # Проверяем, что вызовы были направлены разным провайдерам
            mock_provider1.execute_query.assert_called_once_with("SELECT 1 AS db_id")
            mock_provider2.execute_query.assert_called_once_with("SELECT 2 AS db_id")
            
        finally:
            await infra.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_db_provider_concurrent_access():
    """
    Интеграционный тест: проверка возможности параллельного доступа к БД
    """
    # Пропускаем, если нет флага
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Пропущено: нет флага RUN_INTEGRATION_TESTS")
    
    config = SystemConfig(
        db_providers={
            "concurrent_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:",
                    "pool_size": 5  # Пул из 5 соединений
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        
        # Мокаем выполнение запроса с небольшой задержкой
        async def delayed_query(query):
            await asyncio.sleep(0.01)  # небольшая задержка
            return type('Result', (), {
                'rowcount': 1,
                'rows': [{'query': query, 'result': 'ok'}]
            })()
        
        mock_provider.execute_query = delayed_query
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        try:
            await infra.initialize()
            
            db = infra.get_provider("concurrent_db")
            
            # Выполняем несколько параллельных запросов
            queries = [f"SELECT {i}" for i in range(5)]
            tasks = [db.execute_query(q) for q in queries]
            results = await asyncio.gather(*tasks)
            
            # Проверяем, что все запросы выполнились успешно
            assert len(results) == 5
            for i, result in enumerate(results):
                assert result.rows[0]['query'] == f"SELECT {i}"
                assert result.rows[0]['result'] == 'ok'
                
        finally:
            await infra.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_db_provider_transaction_handling():
    """
    Интеграционный тест: проверка обработки транзакций
    """
    # Пропускаем, если нет флага
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Пропущено: нет флага RUN_INTEGRATION_TESTS")
    
    config = SystemConfig(
        db_providers={
            "transaction_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.begin_transaction = AsyncMock(return_value=AsyncMock())
        mock_provider.execute_query = AsyncMock(return_value=type('Result', (), {
            'rowcount': 1,
            'rows': [{'status': 'success'}]
        })())
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        try:
            await infra.initialize()
            
            db = infra.get_provider("transaction_db")
            
            # Проверяем, что транзакции могут быть начаты
            transaction = await db.begin_transaction()
            assert transaction is not None
            
            # Выполняем запрос в транзакции
            result = await db.execute_query("SELECT 1")
            assert result.rows[0]['status'] == 'success'
            
        finally:
            await infra.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_db_provider_with_timeout():
    """
    Тест с таймаутом: защита от зависания при сбоях ресурсов
    """
    # Пропускаем, если нет флага
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Пропущено: нет флага RUN_INTEGRATION_TESTS")
    
    config = SystemConfig(
        db_providers={
            "timeout_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        
        # Мокаем выполнение запроса с задержкой
        async def slow_query(query):
            await asyncio.sleep(0.1)  # короткая задержка
            return type('Result', (), {
                'rowcount': 1,
                'rows': [{'result': 'slow_ok'}]
            })()
        
        mock_provider.execute_query = slow_query
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        try:
            await infra.initialize()
            
            db = infra.get_provider("timeout_db")
            
            # Тестируем с таймаутом
            result = await asyncio.wait_for(
                db.execute_query("SELECT 1"),
                timeout=2.0  # 2 секунды таймаут
            )
            
            assert result.rows[0]['result'] == 'slow_ok'
            
        except asyncio.TimeoutError:
            pytest.fail("Запрос к БД превысил таймаут")
        finally:
            await infra.shutdown()
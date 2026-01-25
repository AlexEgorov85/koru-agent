"""
Тесты для базового класса DB-провайдеров.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from providers.base_db import BaseDBProvider, DBConnectionConfig, DBQueryResult, DBHealthStatus
from contextlib import asynccontextmanager


class MockDBProvider(BaseDBProvider):
    """Мок-реализация BaseDBProvider для тестов."""
    
    async def initialize(self) -> bool:
        self.is_initialized = True
        return True
    
    async def shutdown(self) -> None:
        self.is_initialized = False
    
    async def health_check(self) -> dict:
        return {"status": self.health_status.value}
    
    async def execute(self, query: str, params: dict = None) -> DBQueryResult:
        return DBQueryResult(
            success=True,
            rows=[{"id": 1, "name": "test"}],
            rowcount=1,
            columns=["id", "name"],
            execution_time=0.01
        )
    
    @asynccontextmanager
    async def transaction(self):
        yield MagicMock()


@pytest.fixture
def base_provider(mock_db_config):
    """Фикстура с базовым DB провайдером."""
    return MockDBProvider(mock_db_config)


@pytest.mark.asyncio
async def test_base_provider_initialization(base_provider):
    """Тест инициализации базового DB провайдера."""
    assert base_provider.config.host == "localhost"
    assert base_provider.config.port == 5432
    assert base_provider.config.database == "test_db"
    assert base_provider.is_initialized is False
    assert base_provider.health_status == DBHealthStatus.UNKNOWN
    
    # Тестируем инициализацию
    await base_provider.initialize()
    assert base_provider.is_initialized is True
    assert base_provider.health_status == DBHealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_base_provider_shutdown(base_provider):
    """Тест завершения работы DB провайдера."""
    await base_provider.initialize()
    assert base_provider.is_initialized is True
    
    await base_provider.shutdown()
    assert base_provider.is_initialized is False


@pytest.mark.asyncio
async def test_base_provider_health_check(base_provider):
    """Тест проверки здоровья DB провайдера."""
    await base_provider.initialize()
    result = await base_provider.health_check()
    
    assert result["status"] == DBHealthStatus.HEALTHY.value


@pytest.mark.asyncio
async def test_base_provider_execute(base_provider):
    """Тест выполнения запроса."""
    await base_provider.initialize()
    
    result = await base_provider.execute("SELECT * FROM test", {"param": "value"})
    
    assert result.success is True
    assert len(result.rows) == 1
    assert result.rowcount == 1
    assert result.columns == ["id", "name"]
    assert result.execution_time > 0
    assert isinstance(result.execution_time, float)


@pytest.mark.asyncio
async def test_base_provider_transaction(base_provider):
    """Тест транзакции."""
    await base_provider.initialize()
    
    # Тестируем контекстный менеджер транзакции
    async with base_provider.transaction() as conn:
        assert conn is not None
        # Имитируем выполнение запросов в транзакции
        result = await base_provider.execute("INSERT INTO test VALUES (1)")
        assert result.success is True
    
    # После выхода из контекста транзакция должна быть завершена


def test_db_query_result_methods():
    """Тест методов DBQueryResult."""
    result = DBQueryResult(
        success=True,
        rows=[{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}],
        rowcount=2,
        columns=["id", "name"],
        execution_time=0.01
    )
    
    # Тестируем метод first()
    first_row = result.first()
    assert first_row == {"id": 1, "name": "test"}
    
    # Тестируем метод __len__()
    assert len(result) == 2
    
    # Тестируем для пустого результата
    empty_result = DBQueryResult(success=True, rows=[], rowcount=0, columns=[], execution_time=0.0)
    assert empty_result.first() is None
    assert len(empty_result) == 0


def test_base_provider_update_metrics(base_provider):
    """Тест обновления метрик."""
    # Первоначальные метрики
    assert base_provider.query_count == 0
    assert base_provider.error_count == 0
    assert base_provider.avg_query_time == 0.0
    
    # Обновляем метрики для успешного запроса
    base_provider._update_metrics(0.5, success=True)
    assert base_provider.query_count == 1
    assert base_provider.error_count == 0
    assert base_provider.avg_query_time > 0
    
    # Обновляем метрики для неуспешного запроса
    base_provider._update_metrics(0.3, success=False)
    assert base_provider.query_count == 2
    assert base_provider.error_count == 1
    assert base_provider.avg_query_time > 0
    
    # Проверяем обновление состояния здоровья
    for _ in range(10):
        base_provider._update_metrics(0.1, success=False)
    
    assert base_provider.health_status == DBHealthStatus.DEGRADED


def test_base_provider_get_connection_info(base_provider):
    """Тест получения информации о подключении."""
    info = base_provider.get_connection_info()
    
    assert info["database"] == "test_db"
    assert info["host"] == "localhost"
    assert info["port"] == 5432
    assert info["username"] == "test_user"
    assert info["provider_type"] == "MockDBProvider"
    assert info["is_initialized"] is False
    assert info["health_status"] == DBHealthStatus.UNKNOWN.value
    assert info["uptime_seconds"] > 0
    assert info["query_count"] == 0
    assert info["error_count"] == 0
    assert info["avg_query_time"] == 0.0
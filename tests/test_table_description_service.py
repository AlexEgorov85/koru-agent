"""
Тесты для проверки инфраструктурного сервиса описания таблицы.
"""
import pytest
import tempfile
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.infrastructure.service.table_description_service import TableDescriptionService
from core.system_context.base_system_contex import BaseSystemContext


@pytest.mark.asyncio
async def test_table_description_service_initialization():
    """Тест инициализации сервиса описания таблицы."""
    # Создаем mock системного контекста
    mock_system_context = AsyncMock(spec=BaseSystemContext)
    
    # Создаем сервис
    service = TableDescriptionService(mock_system_context)
    
    # Проверяем, что сервис создан
    assert service is not None
    assert service.system_context == mock_system_context
    
    # Инициализируем сервис
    success = await service.initialize()
    
    # Проверяем, что инициализация прошла успешно
    assert success is True


@pytest.mark.asyncio
async def test_table_description_service_get_table_metadata():
    """Тест получения метаданных таблицы через сервис."""
    # Создаем mock системного контекста
    mock_system_context = AsyncMock(spec=BaseSystemContext)
    
    # Создаем mock результата SQL-запроса
    mock_columns_result = MagicMock()
    mock_columns_result.rows = []
    
    mock_table_desc_result = MagicMock()
    mock_table_desc_result.rows = []
    
    # Мокаем метод execute_sql_query
    mock_system_context.execute_sql_query = AsyncMock(side_effect=[
        mock_columns_result,  # Результат для запроса столбцов
        mock_table_desc_result  # Результат для запроса описания таблицы
    ])
    
    # Создаем сервис
    service = TableDescriptionService(mock_system_context)
    
    # Инициализируем сервис
    await service.initialize()
    
    # Вызываем метод получения метаданных
    result = await service.get_table_metadata(
        schema_name="public",
        table_name="users",
        context=MagicMock(),  # Mock контекста сессии
        step_number=1
    )
    
    # Проверяем результат
    assert result is not None
    assert result["schema_name"] == "public"
    assert result["table_name"] == "users"
    
    # Проверяем, что были вызваны SQL-запросы
    assert mock_system_context.execute_sql_query.call_count == 2


@pytest.mark.asyncio
async def test_table_description_service_invalid_identifiers():
    """Тест проверки недопустимых идентификаторов."""
    # Создаем mock системного контекста
    mock_system_context = AsyncMock(spec=BaseSystemContext)
    
    # Создаем сервис
    service = TableDescriptionService(mock_system_context)
    
    # Инициализируем сервис
    await service.initialize()
    
    # Проверяем, что сервис правильно проверяет идентификаторы
    assert service._is_valid_identifier("valid_name") is True
    assert service._is_valid_identifier("ValidName123") is True
    assert service._is_valid_identifier("_valid_name_") is True
    
    assert service._is_valid_identifier("") is False
    assert service._is_valid_identifier(None) is False
    assert service._is_valid_identifier("1invalid_start") is False
    assert service._is_valid_identifier("invalid-name") is False
    assert service._is_valid_identifier("invalid name") is False
    assert service._is_valid_identifier(";" * 200) is False


@pytest.mark.asyncio
async def test_table_description_service_shutdown():
    """Тест завершения работы сервиса описания таблицы."""
    # Создаем mock системного контекста
    mock_system_context = AsyncMock(spec=BaseSystemContext)
    
    # Создаем сервис
    service = TableDescriptionService(mock_system_context)
    
    # Завершаем работу сервиса
    await service.shutdown()
    
    # Проверяем, что метод завершения работы завершился без ошибок
    # (если бы была ошибка, тест бы упал)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
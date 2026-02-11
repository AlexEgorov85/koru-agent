#!/usr/bin/env python3
"""
Тест для проверки SQLQueryService
"""

import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.infrastructure.service.sql_query.service import SQLQueryService


async def test_sql_query_service():
    """Тестируем SQLQueryService"""
    
    print("=== Тестирование SQLQueryService ===")
    
    # Создаем mock для system_context
    mock_system_context = MagicMock()
    mock_system_context.get_resource = MagicMock()
    
    # Мокируем SQLValidatorService
    mock_validator_service = AsyncMock()
    from core.infrastructure.service.sql_validator.service import ValidatedSQL
    mock_validated_sql = ValidatedSQL(
        sql="SELECT * FROM users WHERE id = $id",
        parameters={"id": 123},
        is_valid=True,
        validation_errors=[],
        safety_score=0.9
    )
    mock_validator_service.validate_query.return_value = mock_validated_sql
    
    # Мокируем системный контекст для выполнения SQL
    mock_system_context.execute_sql_query = AsyncMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.rows = [{"id": 123, "name": "John"}]
    mock_result.columns = ["id", "name"]
    mock_result.rowcount = 1
    mock_result.error = None
    mock_system_context.execute_sql_query.return_value = mock_result
    
    mock_system_context.get_resource.return_value = mock_validator_service
    
    # Создаем экземпляр SQLQueryService
    service = SQLQueryService(system_context=mock_system_context)
    
    # Инициализируем сервис
    init_result = await service.initialize()
    assert init_result, "Сервис должен инициализироваться успешно"
    print("+ Инициализация прошла успешно")
    
    # Тестируем execute_direct_query
    result = await service.execute_direct_query(
        sql_query="SELECT * FROM users WHERE id = $id",
        parameters={"id": 123},
        max_rows=10
    )
    
    assert result.success, "Запрос должен выполниться успешно"
    assert result.rowcount == 1, "Должна быть возвращена 1 строка"
    print("+ Выполнение прямого запроса прошло успешно")
    
    # Проверяем, что валидатор был вызван
    mock_validator_service.validate_query.assert_called_once()
    print("+ Валидация SQL-запроса выполнена")
    
    # Проверяем, что системный контекст был вызван для выполнения запроса
    mock_system_context.execute_sql_query.assert_called_once()
    print("+ Выполнение SQL-запроса через системный контекст выполнено")
    
    print("\n=== Все тесты SQLQueryService пройдены успешно! ===")
    return True


async def main():
    try:
        success = await test_sql_query_service()
        if success:
            print("\n[SUCCESS] Все тесты SQLQueryService прошли успешно!")
            return True
        else:
            print("\n[ERROR] Один или несколько тестов не прошли")
            return False
    except Exception as e:
        print(f"\n[ERROR] Непредвиденная ошибка в тесте: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
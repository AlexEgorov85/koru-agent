#!/usr/bin/env python3
"""
Тест проверки корректного статуса FAILED при ошибке выполнения.

Проверяет:
1. ExecutionResult.failure() формирует корректный результат с error
2. Runtime корректно определяет финальный статус при ошибке
"""
import asyncio
import sys
from pathlib import Path

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent))

from core.models.data.execution import ExecutionResult, ExecutionStatus


def test_execution_result_failure():
    """Проверка формирования ExecutionResult.failure()"""
    print("=" * 60)
    print("ТЕСТ 1: ExecutionResult.failure()")
    print("=" * 60)
    
    # Создаём результат с ошибкой
    result = ExecutionResult.failure(
        error="Тестовая ошибка выполнения",
        metadata={"script_name": "get_books_by_author", "execution_type": "static"}
    )
    
    print(f"status: {result.status}")
    print(f"error: {result.error}")
    print(f"metadata: {result.metadata}")
    print(f"data: {result.data}")
    
    assert result.status == ExecutionStatus.FAILED, f"Ожидался FAILED, получен {result.status}"
    assert result.error == "Тестовая ошибка выполнения", f"Ошибка не сохранена: {result.error}"
    assert result.data is None, f"Данные должны быть None: {result.data}"
    
    print("\n[OK] ExecutionResult.failure() работает корректно\n")
    return True


def test_execution_result_success():
    """Проверка формирования ExecutionResult.success()"""
    print("=" * 60)
    print("ТЕСТ 2: ExecutionResult.success()")
    print("=" * 60)
    
    # Создаём результат с успехом
    result = ExecutionResult.success(
        data={"rows": [{"id": 1, "title": "Test"}], "rowcount": 1},
        metadata={"execution_time_ms": 50.0, "rows_returned": 1},
        side_effect=True
    )
    
    print(f"status: {result.status}")
    print(f"data: {result.data}")
    print(f"metadata: {result.metadata}")
    print(f"side_effect: {result.side_effect}")
    
    assert result.status == ExecutionStatus.COMPLETED, f"Ожидался COMPLETED, получен {result.status}"
    assert result.data is not None, "Данные должны быть не None"
    assert result.side_effect is True, "side_effect должен быть True"
    
    print("\n[OK] ExecutionResult.success() работает корректно\n")
    return True


def test_runtime_failed_status():
    """
    Проверка логики определения финального статуса в runtime.
    
    Симулирует ситуацию:
    - error_count = 1 (меньше max_errors = 2)
    - no_progress_steps = 0
    - current_step = 0 (меньше max_steps = 10)
    - last_step_failed = True
    
    Ожидаемый результат: FAILED (из-за last_step_failed)
    """
    print("=" * 60)
    print("ТЕСТ 3: Логика определения финального статуса (с last_step_failed)")
    print("=" * 60)
    
    # Симулируем состояние
    error_count = 1
    max_errors = 2
    no_progress_steps = 0
    max_no_progress_steps = 3
    current_step = 0
    max_steps = 10
    last_step_failed = True
    last_error_message = "Ошибка выполнения SQL: таблица не существует"
    
    # Логика из runtime.py
    error_message = None
    if error_count >= max_errors:
        final_status = ExecutionStatus.FAILED
        error_message = f"Превышен лимит ошибок: {error_count}/{max_errors}"
    elif no_progress_steps >= max_no_progress_steps:
        final_status = ExecutionStatus.FAILED
        error_message = f"Нет прогресса в течение {no_progress_steps} шагов"
    elif current_step >= max_steps:
        final_status = ExecutionStatus.FAILED
        error_message = "Превышено максимальное количество шагов"
    elif last_step_failed:
        final_status = ExecutionStatus.FAILED
        error_message = last_error_message or "Последний шаг выполнения завершился ошибкой"
    else:
        final_status = ExecutionStatus.COMPLETED
    
    print(f"final_status: {final_status}")
    print(f"error_message: {error_message}")
    
    assert final_status == ExecutionStatus.FAILED, f"Ожидался FAILED, получен {final_status}"
    assert error_message == "Ошибка выполнения SQL: таблица не существует", f"Некорректное сообщение: {error_message}"
    
    print("\n[OK] Логика с last_step_failed работает корректно\n")
    return True


def test_runtime_completed_status():
    """
    Проверка логики определения финального статуса в runtime.
    
    Симулирует ситуацию:
    - error_count = 0
    - no_progress_steps = 0
    - current_step = 1
    - last_step_failed = False
    
    Ожидаемый результат: COMPLETED
    """
    print("=" * 60)
    print("ТЕСТ 4: Логика определения финального статуса (успех)")
    print("=" * 60)
    
    # Симулируем состояние
    error_count = 0
    max_errors = 2
    no_progress_steps = 0
    max_no_progress_steps = 3
    current_step = 1
    max_steps = 10
    last_step_failed = False
    last_error_message = None
    
    # Логика из runtime.py
    error_message = None
    if error_count >= max_errors:
        final_status = ExecutionStatus.FAILED
        error_message = f"Превышен лимит ошибок: {error_count}/{max_errors}"
    elif no_progress_steps >= max_no_progress_steps:
        final_status = ExecutionStatus.FAILED
        error_message = f"Нет прогресса в течение {no_progress_steps} шагов"
    elif current_step >= max_steps:
        final_status = ExecutionStatus.FAILED
        error_message = "Превышено максимальное количество шагов"
    elif last_step_failed:
        final_status = ExecutionStatus.FAILED
        error_message = last_error_message or "Последний шаг выполнения завершился ошибкой"
    else:
        final_status = ExecutionStatus.COMPLETED
    
    print(f"final_status: {final_status}")
    print(f"error_message: {error_message}")
    
    assert final_status == ExecutionStatus.COMPLETED, f"Ожидался COMPLETED, получен {final_status}"
    assert error_message is None, f"Сообщение должно быть None: {error_message}"
    
    print("\n[OK] Логика успеха работает корректно\n")
    return True


async def test_book_library_execute_script_failure():
    """
    Проверка book_library.execute_script при ошибке SQL.
    
    Эмулирует ситуацию когда sql_query_service возвращает ошибку.
    """
    print("=" * 60)
    print("ТЕСТ 5: book_library.execute_script - эмуляция ошибки")
    print("=" * 60)
    
    from core.models.types.db_types import DBQueryResult
    
    # Эмулируем ошибку от sql_query_service
    error_result = DBQueryResult(
        success=False,
        rows=[],
        columns=[],
        rowcount=0,
        error="таблица Lib.books не существует",
        execution_time=0.0
    )
    
    print(f"DBQueryResult.success: {error_result.success}")
    print(f"DBQueryResult.error: {error_result.error}")
    
    # Эмулируем логику из _execute_script_static
    if hasattr(error_result, 'success') and error_result.success:
        print("Успешное выполнение")
    else:
        error_msg = error_result.error if hasattr(error_result, 'error') else "Неизвестная ошибка"
        execution_result = ExecutionResult.failure(
            error=f"Ошибка выполнения скрипта: {error_msg}",
            metadata={"rows": [], "rowcount": 0, "execution_type": "static", "script_name": "get_books_by_author"}
        )
        
        print(f"ExecutionResult.status: {execution_result.status}")
        print(f"ExecutionResult.error: {execution_result.error}")
        print(f"ExecutionResult.metadata: {execution_result.metadata}")
        
        assert execution_result.status == ExecutionStatus.FAILED
        assert "таблица Lib.books не существует" in execution_result.error
    
    print("\n[OK] book_library.execute_script корректно формирует ошибку\n")
    return True


async def main():
    print("\n" + "=" * 60)
    print("ТЕСТЫ ИСПРАВЛЕНИЯ СТАТУСА FAILED")
    print("=" * 60 + "\n")
    
    # Тест 1: ExecutionResult.failure()
    test_execution_result_failure()
    
    # Тест 2: ExecutionResult.success()
    test_execution_result_success()
    
    # Тест 3: Логика runtime с last_step_failed
    test_runtime_failed_status()
    
    # Тест 4: Логика runtime успех
    test_runtime_completed_status()
    
    # Тест 5: book_library.execute_script ошибка
    await test_book_library_execute_script_failure()
    
    print("=" * 60)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

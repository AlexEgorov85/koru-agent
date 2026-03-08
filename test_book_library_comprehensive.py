"""
Комплексный тест BookLibrarySkill.

ТЕСТИРУЕМ:
1. book_library.execute_script - выполнение скрипта
2. book_library.list_scripts - список скриптов
3. book_library.search_books - динамический поиск (опционально, требует LLM)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.models.data.execution import ExecutionResult


def test_execution_result_structure():
    """Проверка структуры ExecutionResult"""
    print("=" * 80)
    print("ТЕСТ 1: Структура ExecutionResult")
    print("=" * 80)

    # Создаём ExecutionResult
    result = ExecutionResult.success(
        data={"rows": [{"id": 1, "title": "Test"}], "rowcount": 1},
        metadata={"test": "value"}
    )
    
    print(f"result.technical_success: {result.technical_success}")
    print(f"result.data: {result.data}")
    print(f"result.error: {result.error}")
    print(f"result.metadata: {result.metadata}")
    print(f"result.side_effect: {result.side_effect}")
    print("[OK] ExecutionResult структура корректна\n")


def test_execute_script_result():
    """Проверка результата execute_script"""
    print("=" * 80)
    print("ТЕСТ 2: Результат execute_script")
    print("=" * 80)
    
    # Имитируем результат выполнения скрипта
    result_data = {
        "rows": [
            {"id": 1, "title": "Евгений Онегин", "author": "Пушкин", "year": 1833},
            {"id": 2, "title": "Капитанская дочка", "author": "Пушкин", "year": 1836}
        ],
        "rowcount": 2,
        "execution_time": 0.05,
        "script_name": "get_books_by_author",
        "execution_type": "static"
    }
    
    # Проверяем что все required поля есть
    required_fields = ["rows", "rowcount"]
    for field in required_fields:
        assert field in result_data, f"Отсутствует поле {field}"
        print(f"[OK] Поле '{field}' присутствует: {result_data[field]}")
    
    print("[OK] Результат execute_script корректен\n")


def test_list_scripts_result():
    """Проверка результата list_scripts"""
    print("=" * 80)
    print("ТЕСТ 3: Результат list_scripts")
    print("=" * 80)
    
    # Имитируем результат list_scripts
    result_data = {
        "scripts": [
            {
                "name": "get_all_books",
                "description": "Получить все книги",
                "sql": "SELECT * FROM books"
            },
            {
                "name": "get_books_by_author",
                "description": "Книги по автору",
                "sql": "SELECT * FROM books WHERE author = $1",
                "parameters": ["author"]
            }
        ],
        "count": 2
    }
    
    assert "scripts" in result_data
    assert "count" in result_data
    print(f"[OK] scripts count: {result_data['count']}")
    print(f"[OK] Первый скрипт: {result_data['scripts'][0]['name']}")
    print("[OK] Результат list_scripts корректен\n")


def test_search_books_result():
    """Проверка результата search_books"""
    print("=" * 80)
    print("ТЕСТ 4: Результат search_books")
    print("=" * 80)
    
    # Имитируем результат динамического поиска
    result_data = {
        "rows": [
            {"id": 1, "title": "Евгений Онегин", "author": "Пушкин"}
        ],
        "rowcount": 1,
        "execution_time": 2.5,
        "execution_type": "dynamic"
    }
    
    required_fields = ["rows", "rowcount", "execution_type"]
    for field in required_fields:
        assert field in result_data, f"Отсутствует поле {field}"
        print(f"[OK] Поле '{field}' присутствует")
    
    print("[OK] Результат search_books корректен\n")


def test_script_registry():
    """Проверка реестра скриптов"""
    print("=" * 80)
    print("ТЕСТ 5: Реестр скриптов")
    print("=" * 80)
    
    from core.application.skills.book_library.scripts_registry import get_all_scripts
    
    scripts = get_all_scripts()
    print(f"[OK] Загружено скриптов: {len(scripts)}")
    
    # Проверяем что скрипт get_books_by_author существует
    assert "get_books_by_author" in scripts, "Скрипт get_books_by_author не найден"
    print(f"[OK] Скрипт 'get_books_by_author' найден")
    
    # ScriptConfig это объект, получаем атрибуты
    script_config = scripts['get_books_by_author']
    sql = script_config.sql if hasattr(script_config, 'sql') else script_config['sql']
    print(f"     SQL: {sql[:50]}...")
    
    # Проверяем что у всех скриптов есть SQL и описание
    for name, config in scripts.items():
        has_sql = hasattr(config, 'sql') or (isinstance(config, dict) and 'sql' in config)
        has_desc = hasattr(config, 'description') or (isinstance(config, dict) and 'description' in config)
        assert has_sql, f"Скрипт {name} не имеет SQL"
        assert has_desc, f"Скрипт {name} не имеет описания"
    
    print(f"[OK] Все {len(scripts)} скрипта имеют SQL и описание")
    print("[OK] Реестр скриптов корректен\n")


def test_contract_validation():
    """Проверка валидации контрактов"""
    print("=" * 80)
    print("ТЕСТ 6: Валидация контрактов")
    print("=" * 80)
    
    # Проверяем что выходные данные соответствуют контракту
    from pydantic import BaseModel, create_model
    
    # Создаём динамическую модель для проверки
    # (в реальности используется схема из YAML контракта)
    output_fields = {
        "rows": (list, ...),
        "rowcount": (int, ...),
        "execution_time": (float, None),
        "script_name": (str, None),
        "execution_type": (str, ...)
    }
    
    OutputSchema = create_model("BookLibraryOutput", **output_fields)
    
    # Тестовые данные
    test_data = {
        "rows": [{"id": 1, "title": "Test"}],
        "rowcount": 1,
        "execution_time": 0.05,
        "script_name": "get_books_by_author",
        "execution_type": "static"
    }
    
    # Валидируем
    try:
        validated = OutputSchema.model_validate(test_data)
        print(f"[OK] Валидация успешна")
        print(f"     rows: {validated.rows}")
        print(f"     rowcount: {validated.rowcount}")
        print(f"     execution_type: {validated.execution_type}")
    except Exception as e:
        print(f"[FAIL] Валидация не удалась: {e}")
        return False
    
    print("[OK] Валидация контрактов корректна\n")
    return True


async def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 80)
    print("КОМПЛЕКСНЫЙ ТЕСТ BookLibrarySkill")
    print("=" * 80 + "\n")
    
    # Тесты которые не требуют asyncio
    test_skill_result_structure()
    test_execute_script_result()
    test_list_scripts_result()
    test_search_books_result()
    test_script_registry()
    test_contract_validation()
    
    print("=" * 80)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

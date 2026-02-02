"""
Пример использования навыка генерации SQL запросов.
"""
import asyncio
from unittest.mock import Mock
from core.skills.sql_generator.skill import SQLGeneratorSkill
from core.skills.sql_generator.schema import SQLGenerationParams, TableInfo


async def demonstrate_sql_generator():
    """
    Демонстрация работы навыка генерации SQL.
    """
    print("=== Демонстрация навыка генерации SQL ===\n")
    
    # Создаем фиктивный системный контекст для демонстрации
    # В реальной системе это будет полноценный SystemContext
    class DummySystemContext:
        async def call_llm_with_params(self, **kwargs):
            # Фиктивный ответ от LLM
            class DummyResponse:
                def __init__(self):
                    # Для демонстрации возвращаем простой SQL запрос
                    self.content = "SELECT u.id, u.name, u.email FROM users u WHERE u.active = true AND u.created_date >= '2023-01-01';"
            
            return DummyResponse()
        
        async def execute_sql_query(self, query):
            # Фиктивный результат выполнения SQL запроса
            class DummySQLResult:
                def __init__(self):
                    self.rows = [{"operation": "Seq Scan", "relation": "users"}]
            
            return DummySQLResult()
    
    # Создаем экземпляр навыка
    system_context = DummySystemContext()
    sql_generator = SQLGeneratorSkill("sql_generator", system_context)
    
    # Определяем параметры генерации
    params = SQLGenerationParams(
        description="Выбрать ID, имя и email всех активных пользователей, зарегистрированных после 2023 года",
        tables=[
            TableInfo(
                name="users",
                schema_name="public",
                description="Таблица пользователей",
                columns=[
                    {"name": "id", "type": "integer", "description": "Уникальный идентификатор пользователя"},
                    {"name": "name", "type": "varchar(100)", "description": "Имя пользователя"},
                    {"name": "email", "type": "varchar(255)", "description": "Email пользователя"},
                    {"name": "active", "type": "boolean", "description": "Статус активности пользователя"},
                    {"name": "created_date", "type": "date", "description": "Дата создания учетной записи"}
                ]
            )
        ],
        sql_type="SELECT",
        format="standard",
        validate_syntax=True,
        optimize_query=True,
        explain_plan=True,
        auto_correct=True
    )
    
    print("Параметры генерации:")
    print(f"- Описание запроса: {params.description}")
    print(f"- Тип SQL: {params.sql_type}")
    print(f"- Количество таблиц: {len(params.tables)}")
    print()
    
    # Выполняем генерацию SQL
    print("Генерация SQL запроса...")
    
    # Получаем capability для выполнения
    capability = sql_generator.get_capabilities()[0]
    
    # Создаем фиктивный контекст сессии
    # Используем простой mock для демонстрации
    session_context = Mock()
    
    try:
        result = await sql_generator.execute(capability, params, session_context)
        
        print("\nРезультат генерации:")
        print(f"Статус: {result.status}")
        print(f"Сводка: {result.summary}")
        
        if result.result:
            sql_result = result.result
            print(f"\nСгенерированный SQL:")
            print(f">>> {sql_result['generated_sql']}")
            
            print(f"\nРезультат валидации:")
            validation = sql_result['validation_result']
            print(f"- Валиден: {validation['is_valid']}")
            print(f"- Ошибки: {len(validation['errors'])}")
            print(f"- Предупреждения: {len(validation['warnings'])}")
            
            if validation['errors']:
                print("Ошибки:")
                for error in validation['errors']:
                    print(f"  - {error}")
            
            if validation['warnings']:
                print("Предупреждения:")
                for warning in validation['warnings']:
                    print(f"  - {warning}")
            
            if sql_result['corrected']:
                print(f"\nЗапрос был скорректирован: {sql_result['correction_reason']}")
            
            if sql_result['execution_plan']:
                print(f"\nПлан выполнения:")
                for key, value in sql_result['execution_plan'].items():
                    print(f"  {key}: {value}")
    
    except Exception as e:
        print(f"Ошибка при генерации SQL: {e}")
        import traceback
        traceback.print_exc()


async def demonstrate_error_correction():
    """
    Демонстрация автоматической коррекции ошибок в SQL.
    """
    print("\n\n=== Демонстрация автоматической коррекции ошибок ===\n")
    
    class DummySystemContextWithErrors:
        async def call_llm_with_params(self, **kwargs):
            # Имитируем ответ LLM с ошибкой в SQL
            class DummyResponse:
                def __init__(self):
                    # Намеренно вводим ошибку в SQL запросе (опечатка в SELECT)
                    self.content = "SELCT id, name FROM users WHERE active = true;"  # Опечатка: SELCT вместо SELECT
            
            return DummyResponse()
        
        async def execute_sql_query(self, query):
            class DummySQLResult:
                def __init__(self):
                    self.rows = [{"operation": "Seq Scan", "relation": "users"}]
            
            return DummySQLResult()
    
    system_context = DummySystemContextWithErrors()
    sql_generator = SQLGeneratorSkill("sql_generator", system_context)
    
    params = SQLGenerationParams(
        description="Выбрать ID и имя всех активных пользователей (с ошибкой в генерации)",
        tables=[
            TableInfo(
                name="users",
                schema_name="public",
                description="Таблица пользователей",
                columns=[
                    {"name": "id", "type": "integer", "description": "Уникальный идентификатор пользователя"},
                    {"name": "name", "type": "varchar(100)", "description": "Имя пользователя"},
                    {"name": "active", "type": "boolean", "description": "Статус активности пользователя"}
                ]
            )
        ],
        sql_type="SELECT",
        format="standard",
        validate_syntax=True,
        optimize_query=False,
        explain_plan=False,
        auto_correct=True  # Включаем автокоррекцию
    )
    
    print("Параметры генерации (с намеренной ошибкой в генерации):")
    print(f"- Описание запроса: {params.description}")
    print("- Автокоррекция включена: True")
    print()
    
    capability = sql_generator.get_capabilities()[0]
    session_context = Mock()
    
    try:
        result = await sql_generator.execute(capability, params, session_context)
        
        print("Результат генерации:")
        print(f"Статус: {result.status}")
        print(f"Сводка: {result.summary}")
        
        if result.result:
            sql_result = result.result
            print(f"\nОригинальный (ошибочный) SQL от LLM: SELCT id, name FROM users WHERE active = true;")
            print(f"Исправленный SQL: {sql_result['generated_sql']}")
            print(f"Запрос был скорректирован: {sql_result['corrected']}")
            
            if sql_result['correction_reason']:
                print(f"Причина коррекции: {sql_result['correction_reason']}")
            
            validation = sql_result['validation_result']
            print(f"Валидация после коррекции: {validation['is_valid']}")
    
    except Exception as e:
        print(f"Ошибка при генерации SQL: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(demonstrate_sql_generator())
    asyncio.run(demonstrate_error_correction())
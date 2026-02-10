#!/usr/bin/env python3
"""
Скрипт для проверки структуры таблицы книг
"""
import asyncio
import sys
import os

# Добавляем корневую директорию в путь Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import get_config
from core.system_context.system_context import SystemContext

async def check_table_structure():
    print("Загружаем конфигурацию...")
    config = get_config(profile='dev')
    
    print("Создаем системный контекст...")
    system_context = SystemContext(config)
    
    print("Инициализируем системный контекст...")
    success = await system_context.initialize()
    if not success:
        print("Ошибка инициализации")
        return
    
    print("Получаем SQL сервис...")
    sql_service = system_context.get_resource("sql_query_service")
    if not sql_service:
        print("SQL сервис не найден")
        return
    
    print("Проверяем структуру таблицы Lib.books...")
    try:
        # Запрос структуры таблицы
        query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_schema = 'Lib' AND table_name = 'books'
        ORDER BY ordinal_position;
        """
        
        result = await sql_service.execute_direct_query(query, {}, max_rows=100)
        
        print("Структура таблицы Lib.books:")
        if result.success and result.rows:
            print(f"{'Колонка':<20} {'Тип':<20} {'Может быть NULL':<15} {'Значение по умолчанию'}")
            print("-" * 80)
            for row in result.rows:
                print(f"{row['column_name']:<20} {row['data_type']:<20} {str(row['is_nullable']):<15} {str(row['column_default'])}")
        else:
            print("Не удалось получить структуру таблицы")
            
    except Exception as e:
        print(f"Ошибка при получении структуры таблицы: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_table_structure())
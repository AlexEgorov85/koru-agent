import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig


async def test_sql_generation_with_prompts():
    """Тестирование SQLGenerationService с новыми промптами"""
    print("=== Тестирование SQLGenerationService с новыми промптами ===")
    
    # Создаем конфигурацию
    config = SystemConfig()
    
    # Создаем и инициализируем системный контекст
    system_context = SystemContext(config)
    success = await system_context.initialize()
    
    if not success:
        print("Ошибка инициализации системного контекста")
        return
    
    # Получаем SQLGenerationService
    sql_service = system_context.get_resource("sql_generation_service")
    if not sql_service:
        print("SQLGenerationService не найден")
        await system_context.shutdown()
        return
    
    print(f"SQLGenerationService загружен: {type(sql_service).__name__}")
    
    # Получаем PromptService
    prompt_service = system_context.get_resource("prompt_service")
    if not prompt_service:
        print("PromptService не найден")
        await system_context.shutdown()
        return
    
    print(f"PromptService загружен: {type(prompt_service).__name__}")
    
    # Проверяем, что промпты для sql_generation загружены
    try:
        # Получаем список всех промптов
        all_prompts = await prompt_service.list_prompts()
        print(f"Всего промптов загружено: {len(all_prompts)}")
        
        # Ищем промпты, связанные с sql_generation
        sql_prompts = [p for p in all_prompts if 'sql_generation' in p['capability']]
        print(f"Промптов для sql_generation: {len(sql_prompts)}")
        
        for prompt in sql_prompts:
            print(f"  - {prompt['capability']} (v{prompt['version']})")
        
        # Проверим, можем ли мы получить и отрендерить конкретный промпт
        if sql_prompts:
            for prompt_info in sql_prompts:
                capability_name = prompt_info['capability']
                print(f"\nПроверка промпта: {capability_name}")
                
                try:
                    # Получаем сырой промпт
                    raw_prompt = await prompt_service.get_prompt(capability_name)
                    print(f"+ Промпт успешно получен, длина: {len(raw_prompt)} символов")
                    
                    # Пытаемся отрендерить с тестовыми переменными
                    if 'generate_safe_query' in capability_name:
                        rendered = await prompt_service.render(
                            capability_name=capability_name,
                            variables={
                                "user_question": "Покажи все книги автора Толстой",
                                "table_descriptions": "Таблица Lib.books: id, title, author_id\nТаблица Lib.authors: id, first_name, last_name",
                                "allowed_operations": "SELECT, WITH",
                                "max_rows": 100
                            }
                        )
                    elif 'correct_query' in capability_name:
                        rendered = await prompt_service.render(
                            capability_name=capability_name,
                            variables={
                                "original_query": "SELECT * FROM books WHERE author = 'Tolstoy'",
                                "error_message": "column 'author' does not exist",
                                "error_type": "schema_error",
                                "suggested_fix": "Use author_id instead of author",
                                "allowed_operations": "SELECT, WITH"
                            }
                        )
                    
                    print(f"+ Промпт успешно отрендерен, длина: {len(rendered)} символов")
                    
                except Exception as e:
                    print(f"- Ошибка при работе с промптом {capability_name}: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print("Не найдено промптов для sql_generation")
            
    except Exception as e:
        print(f"Ошибка при получении списка промптов: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Тестирование SQLGenerationService с промптами завершено ===")
    
    # Завершаем работу
    await system_context.shutdown()


if __name__ == "__main__":
    asyncio.run(test_sql_generation_with_prompts())
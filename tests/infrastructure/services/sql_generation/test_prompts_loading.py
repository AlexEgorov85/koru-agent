import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig


async def test_prompts_loading():
    """Тестирование загрузки промптов SQLGenerationService"""
    print("=== Тестирование загрузки промптов SQLGenerationService ===")
    
    # Создаем конфигурацию
    config = SystemConfig()
    
    # Создаем и инициализируем системный контекст
    system_context = SystemContext(config)
    success = await system_context.initialize()
    
    if not success:
        print("Ошибка инициализации системного контекста")
        return
    
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
        
        # Проверим, можем ли мы получить конкретный промпт
        if sql_prompts:
            sample_capability = sql_prompts[0]['capability']
            print(f"\nПроверка получения промпта: {sample_capability}")
            
            try:
                raw_prompt = await prompt_service.get_prompt(sample_capability)
                print(f"✓ Промпт успешно получен, длина: {len(raw_prompt)} символов")
                
                # Попробуем отрендерить с тестовыми переменными
                rendered = await prompt_service.render(
                    capability_name=sample_capability,
                    variables={
                        "user_question": "Покажи все книги автора Толстой",
                        "table_descriptions": "Таблица Lib.books: id, title, author_id",
                        "allowed_operations": "SELECT, WITH",
                        "max_rows": 100
                    }
                )
                print(f"✓ Промпт успешно отрендерен, длина: {len(rendered)} символов")
                
            except Exception as e:
                print(f"✗ Ошибка при работе с промптом: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("Не найдено промптов для sql_generation")
            
    except Exception as e:
        print(f"Ошибка при получении списка промптов: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Тестирование загрузки промптов завершено ===")
    
    # Завершаем работу
    await system_context.shutdown()


if __name__ == "__main__":
    asyncio.run(test_prompts_loading())
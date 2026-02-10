"""Простой тест для проверки регистрации навыка финального ответа."""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.config import get_config
from core.system_context.system_context import SystemContext


async def test_final_answer_registration():
    """Тестирование регистрации навыка финального ответа."""
    print("=== Тест регистрации навыка финального ответа ===")
    
    # Загружаем конфигурацию
    config = get_config(profile="dev")
    
    # Создаем системный контекст
    system_context = SystemContext(config)
    await system_context.initialize()
    
    # Проверяем, что навык зарегистрирован
    final_answer_capability = system_context.get_capability("final_answer.generate")
    if final_answer_capability:
        print("SUCCESS: Навык финального ответа успешно зарегистрирован")
        print(f"  - Название: {final_answer_capability.name}")
        print(f"  - Описание: {final_answer_capability.description}")
        print(f"  - Навык: {final_answer_capability.skill_name}")
    else:
        print("ERROR: Навык финального ответа не найден")
    
    # Проверяем список всех capability
    all_capabilities = system_context.list_capabilities()
    final_answer_caps = [cap for cap in all_capabilities if "final_answer" in cap]
    print(f"Найдено capability с 'final_answer': {len(final_answer_caps)}")
    for cap in final_answer_caps:
        print(f"  - {cap}")
    
    await system_context.shutdown()
    print("=== Тест завершен ===")


if __name__ == "__main__":
    asyncio.run(test_final_answer_registration())
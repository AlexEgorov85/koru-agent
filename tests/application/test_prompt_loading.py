#!/usr/bin/env python3
"""
Тестовый скрипт для проверки загрузки промпта planning.create_plan
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.agent_config import AgentConfig
from core.application.context.application_context import ApplicationContext


async def test_prompt_loading():
    print("=== Тест загрузки промпта planning.create_plan ===")
    
    # Создаём минимальную системную конфигурацию
    from core.config.models import SystemConfig
    
    system_config = SystemConfig()
    
    # Создаём инфраструктурный контекст
    infra = InfrastructureContext(config=system_config)
    await infra.initialize()
    print("+ Инфраструктурный контекст инициализирован")
    
    # Создаём прикладной контекст с промптом
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AgentConfig(
            prompt_versions={"planning.create_plan": "v1.0.0"},
            component_name="ctx1"
        )
    )
    
    try:
        await ctx1.initialize()
        print("+ Прикладной контекст успешно инициализирован")
        
        # Попробуем получить промпт
        prompt = ctx1.get_prompt("planning.create_plan", "v1.0.0")
        print(f"+ Промпт успешно получен, длина: {len(prompt)} символов")
        print("--- Пример содержимого промпта ---")
        print(prompt[:200] + "..." if len(prompt) > 200 else prompt)
        print("--- Конец примера ---")
        
        return True
        
    except Exception as e:
        print(f"- Ошибка при инициализации: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await infra.cleanup()


if __name__ == "__main__":
    success = asyncio.run(test_prompt_loading())
    if success:
        print("\n✓ Тест пройден успешно!")
    else:
        print("\n✗ Тест завершился с ошибками!")
        sys.exit(1)
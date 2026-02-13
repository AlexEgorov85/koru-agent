#!/usr/bin/env python3
"""
Тест для проверки оригинального кода после исправлений
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.agent_config import AgentConfig
from core.application.context.application_context import ApplicationContext


async def test_original_code_fixed():
    print("=== Тест оригинального кода после исправлений ===")
    
    # Создаём минимальную системную конфигурацию
    from core.config.models import SystemConfig
    
    system_config = SystemConfig()
    
    # Создаём инфраструктурный контекст
    infra = InfrastructureContext(config=system_config)
    await infra.initialize()
    print("+ Инфраструктурный контекст инициализирован")
    
    # Создаём прикладной контекст с промптом (оригинальный код)
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AgentConfig(
            prompt_versions={"planning.create_plan": "v1.0.0"},
            component_name="ctx1"
        )
    )
    
    try:
        await ctx1.initialize()
        print("+ Прикладной контекст успешно инициализирован!")
        
        # Попробуем получить промпт
        prompt = ctx1.get_prompt("planning.create_plan", "v1.0.0")
        print(f"+ Промпт успешно получен, длина: {len(prompt)} символов")
        
        return True
        
    except Exception as e:
        print(f"- Ошибка при инициализации: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Попробуем вызвать правильный метод очистки, если он существует
        if hasattr(infra, 'shutdown'):
            await infra.shutdown()
        elif hasattr(infra, 'cleanup'):
            await infra.cleanup()


if __name__ == "__main__":
    success = asyncio.run(test_original_code_fixed())
    if success:
        print("\n+ Оригинальный код работает без ошибок!")
        print("  - Нет ошибки 'maximum recursion depth exceeded'")
        print("  - Нет ошибки 'missing capability'")
        print("  - Нет ошибки 'TableDescriptionService can't be used in await'")
    else:
        print("\n- Оригинальный код всё ещё вызывает ошибки!")
        sys.exit(1)
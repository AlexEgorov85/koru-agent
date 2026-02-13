#!/usr/bin/env python3
"""
Финальный тест для подтверждения, что оригинальный код работает
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.agent_config import AgentConfig
from core.application.context.application_context import ApplicationContext


async def final_test():
    print("=== ФИНАЛЬНЫЙ ТЕСТ: проверка оригинального кода ===")
    
    # Создаём минимальную системную конфигурацию
    from core.config.models import SystemConfig
    
    system_config = SystemConfig()
    
    # Создаём инфраструктурный контекст
    infra = InfrastructureContext(config=system_config)
    await infra.initialize()
    print("ШАГ 1: Инфраструктурный контекст создан и инициализирован")
    
    # ВАШ ОРИГИНАЛЬНЫЙ КОД:
    print("ШАГ 2: Создание прикладного контекста (ваш оригинальный код)...")
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AgentConfig(
            prompt_versions={"planning.create_plan": "v1.0.0"},
            component_name="ctx1"
        )
    )
    
    print("ШАГ 3: Инициализация прикладного контекста...")
    await ctx1.initialize()
    print("ШАГ 4: Прикладной контекст успешно инициализирован!")
    
    # Проверим, что промпт действительно загрузился
    print("ШАГ 5: Проверка загрузки промпта...")
    prompt = ctx1.get_prompt("planning.create_plan", "v1.0.0")
    print(f"ШАГ 6: Промпт успешно получен, длина: {len(prompt)} символов")
    
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТ:")
    print("✅ ВАШ ОРИГИНАЛЬНЫЙ КОД ТЕПЕРЬ РАБОТАЕТ!")
    print("✅ Нет ошибки 'maximum recursion depth exceeded'")
    print("✅ Нет ошибки 'missing capability'")
    print("✅ Нет ошибки 'await с сервисом'")
    print("✅ Промпт planning.create_plan успешно загружается")
    print("="*60)
    
    # Попробуем вызвать правильный метод очистки
    try:
        if hasattr(infra, 'shutdown'):
            await infra.shutdown()
        elif hasattr(infra, 'cleanup'):
            await infra.cleanup()
    except Exception as e:
        print(f"Предупреждение при очистке: {e}")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(final_test())
    if success:
        print("\n🎉 Финальный тест пройден! Ваш код работает корректно!")
    else:
        print("\n💥 Финальный тест не пройден!")
        sys.exit(1)
#!/usr/bin/env python3
"""
Тестирование оригинального кода, который выдавал ошибки.
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.models import SystemConfig


async def test_original_code():
    """Тестируем оригинальный код, который выдавал ошибки"""
    
    # Загружаем конфигурацию
    config = SystemConfig()
    config.profile = "prod"
    config.data_dir = "data"  # Указываем правильную директорию данных
    
    # Создаем инфраструктурный контекст
    infra = InfrastructureContext(config)
    
    # Инициализируем инфраструктурный контекст
    success = await infra.initialize()
    if not success:
        print("[ERROR] Ошибка инициализации инфраструктурного контекста")
        return False
    
    print("[OK] Инфраструктурный контекст инициализирован")
    
    # Создаем и инициализируем прикладной контекст (оригинальный код из запроса)
    try:
        ctx1 = ApplicationContext(
            infrastructure_context=infra,
            config=AppConfig.from_registry(profile="prod"),
            profile='prod'
        )
        print("[OK] ApplicationContext создан")
        
        # Пытаемся инициализировать (оригинальный код из запроса)
        await ctx1.initialize()
        print("[OK] ApplicationContext успешно инициализирован")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка при создании или инициализации ApplicationContext: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Завершаем инфраструктурный контекст
        await infra.shutdown()


async def main():
    print("TEST: Запуск теста оригинального кода...")
    
    success = await test_original_code()
    
    if success:
        print("\nSUCCESS: Оригинальный код теперь работает без ошибок!")
        return 0
    else:
        print("\nFAILURE: Оригинальный код все еще выдает ошибки")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
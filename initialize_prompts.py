#!/usr/bin/env python3
"""
Скрипт инициализации промтов в репозитории
"""
import asyncio
from application.services.prompt_initializer import PromptInitializer
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository


async def main():
    """Основная функция инициализации промтов"""
    print("Начинаем инициализацию промтов в репозитории...")
    
    # Создаем репозиторий
    repository = InMemoryPromptRepository()
    
    # Создаем инициализатор
    initializer = PromptInitializer(repository)
    
    # Инициализируем промты
    await initializer.initialize_prompts()
    
    print("\nИнициализация промтов завершена!")


if __name__ == "__main__":
    asyncio.run(main())
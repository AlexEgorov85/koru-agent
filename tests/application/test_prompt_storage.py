#!/usr/bin/env python3
"""
Тест для проверки работы PromptStorage
"""
import asyncio
from pathlib import Path
from core.infrastructure.storage.prompt_storage import PromptStorage
from core.errors.version_not_found import VersionNotFoundError


async def test_prompt_storage():
    """
    Тестируем работу PromptStorage напрямую
    """
    print("=== Тестирование PromptStorage ===\n")
    
    # Создаем PromptStorage
    # Теперь PromptStorage ищет файлы в подкаталогах prompts/ (skills/, strategies/, и т.д.)
    prompts_dir = Path("prompts")  # корневая директория для поиска
    storage = PromptStorage(prompts_dir)
    
    # Проверяем, существует ли промпт
    capability_name = "planning.create_plan"
    version = "v1.0.0"
    
    print(f"Проверяем существование промпта: {capability_name}@{version}")
    
    # Проверяем напрямую файл
    import os
    print(f"Текущая рабочая директория: {os.getcwd()}")
    print(f"Проверяем файл: prompts/skills/planning/create_plan_v1.0.0.yaml")
    file_exists = Path("prompts/skills/planning/create_plan_v1.0.0.yaml").exists()
    print(f"Файл существует: {file_exists}")
    
    # Проверяем через storage.exists()
    exists = await storage.exists(capability_name, version)
    print(f"PromptStorage.exists() возвращает: {exists}")
    
    # Попробуем загрузить
    try:
        prompt = await storage.load(capability_name, version)
        print(f"Загрузка успешна: {prompt.metadata.capability} версии {prompt.metadata.version}")
        print(f"Длина контента: {len(prompt.content)} символов")
    except VersionNotFoundError as e:
        print(f"Ошибка VersionNotFoundError: {e}")
    except Exception as e:
        print(f"Другая ошибка при загрузке: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_prompt_storage())
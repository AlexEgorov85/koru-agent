#!/usr/bin/env python3
"""
Тестирование автоматической генерации AgentConfig для продакшена
"""
import asyncio
import tempfile
import os
from pathlib import Path
import yaml

from core.config.models import SystemConfig, AgentConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext


async def test_auto_config_generation():
    """Тест автоматической генерации конфигурации для продакшена"""

    # Создаем временную директорию для данных
    with tempfile.TemporaryDirectory() as temp_dir:
        # Копируем registry.yaml из корня проекта
        import shutil
        registry_src = Path(__file__).parent.parent.parent.parent / "registry.yaml"
        registry_dst = Path(temp_dir) / "registry.yaml"
        if registry_src.exists():
            shutil.copy(registry_src, registry_dst)
        
        # Подготовка тестовых данных
        prompts_dir = Path(temp_dir) / "prompts"
        prompts_dir.mkdir(exist_ok=True)
        
        # Создаем тестовые подкаталоги и файлы
        planning_dir = prompts_dir / "planning"
        planning_dir.mkdir(exist_ok=True)
        
        book_library_dir = prompts_dir / "book_library"
        book_library_dir.mkdir(exist_ok=True)
        
        # Создаем тестовые YAML файлы с разными статусами
        test_prompts = {
            "v1.0.0": {
                "content": "Active prompt content",
                "version": "v1.0.0",
                "skill": "planning",
                "capability": "planning",
                "status": "active",
                "author": "test",
                "language": "ru",
                "tags": ["test"],
                "variables": [],
                "role": "system"
            },
            "v1.1.0": {
                "content": "Draft prompt content",
                "version": "v1.1.0",
                "skill": "planning",
                "capability": "planning",
                "status": "draft",
                "author": "test",
                "language": "ru",
                "tags": ["test"],
                "variables": [],
                "role": "system"
            },
            "v2.0.0": {
                "content": "Another active prompt",
                "version": "v2.0.0",
                "skill": "book_library",
                "capability": "book_library",
                "status": "active",
                "author": "test",
                "language": "ru",
                "tags": ["test"],
                "variables": [],
                "role": "system"
            }
        }

        for version, data in test_prompts.items():
            # Определяем директорию по capability
            capability = data["capability"]
            cap_dir = prompts_dir / capability
            cap_dir.mkdir(exist_ok=True)
            
            file_path = cap_dir / f"{version}.yaml"
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f)
        
        # Создаем конфигурацию
        system_config = SystemConfig(data_dir=str(temp_dir))
        
        # Создаем инфраструктурный контекст
        infra = InfrastructureContext(system_config)
        await infra.initialize()
        
        
        # Тестируем автоматическую генерацию конфигурации для продакшена
        prod_context = await ApplicationContext.create_prod_auto(infra, profile="prod")
        
        
        # Проверяем, что в продакшене есть только активные версии
        for capability, version in prod_context.config.prompt_versions.items():
        
        success = await prod_context.initialize()
        
        if success:
            # Проверяем, что можно получить промпты
            for capability in prod_context.config.prompt_versions.keys():
                try:
                    prompt = prod_context.get_prompt(capability)
                except Exception as e:
        
        # Тестируем песочницу с ручной конфигурацией
        from core.config.app_config import AppConfig
        sandbox_config = AppConfig(
            prompt_versions={"planning": "v1.0.0"},  # активная версия
            input_contract_versions={"planning": "v1.0.0"},
            output_contract_versions={"planning": "v1.0.0"},
            side_effects_enabled=True,
            detailed_metrics=False
        )

        sandbox_context = ApplicationContext(
            infrastructure_context=infra,
            config=sandbox_config,
            profile="sandbox"
        )

        # Устанавливаем оверрайд на черновую версию
        sandbox_context.set_prompt_override("planning", "v1.1.0")
        
        success = await sandbox_context.initialize()
        
        if success:
            # В новой архитектуре получение промптов работает через PromptService
            # который должен быть правильно инициализирован
            prompt_service = sandbox_context.get_service("prompt_service")
            if prompt_service:
                try:
                    prompt = await prompt_service.render("planning", {})
                except Exception as e:
            else:
        
        # Завершаем инфраструктурный контекст
        await infra.shutdown()
        


if __name__ == "__main__":
    asyncio.run(test_auto_config_generation())
#!/usr/bin/env python3
"""
Полный тест автоматической генерации AgentConfig для продакшена
"""
import asyncio
import tempfile
import os
from pathlib import Path
import yaml

from core.config.models import SystemConfig, AgentConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext


async def test_full_auto_config():
    """Полный тест автоматической генерации конфигурации"""
    print("=== Полный тест автоматической генерации конфигурации ===")

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
        
        contracts_dir = Path(temp_dir) / "contracts"
        contracts_dir.mkdir(exist_ok=True)
        
        # Создаем поддиректории для контрактов
        skills_dir = contracts_dir / "skills"
        skills_dir.mkdir(exist_ok=True)
        
        planning_dir = skills_dir / "planning"
        planning_dir.mkdir(exist_ok=True)
        
        book_library_dir = skills_dir / "book_library"
        book_library_dir.mkdir(exist_ok=True)
        
        # Создаем тестовые подкаталоги и файлы для промптов
        planning_prompts_dir = prompts_dir / "planning"
        planning_prompts_dir.mkdir(exist_ok=True)
        
        book_library_prompts_dir = prompts_dir / "book_library"
        book_library_prompts_dir.mkdir(exist_ok=True)
        
        # Создаем тестовые YAML файлы с разными статусами
        test_prompts = {
            "planning": {
                "v1.0.0": {
                    "content": "Active planning prompt content",
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
                    "content": "Draft planning prompt content",
                    "version": "v1.1.0",
                    "skill": "planning",
                    "capability": "planning",
                    "status": "draft",
                    "author": "test",
                    "language": "ru",
                    "tags": ["test"],
                    "variables": [],
                    "role": "system"
                }
            },
            "book_library": {
                "v2.0.0": {
                    "content": "Active book library prompt",
                    "version": "v2.0.0",
                    "skill": "book_library",
                    "capability": "book_library",
                    "status": "active",
                    "author": "test",
                    "language": "ru",
                    "tags": ["test"],
                    "variables": [],
                    "role": "system"
                },
                "v2.1.0": {
                    "content": "Draft book library prompt",
                    "version": "v2.1.0",
                    "skill": "book_library",
                    "capability": "book_library",
                    "status": "draft",
                    "author": "test",
                    "language": "ru",
                    "tags": ["test"],
                    "variables": [],
                    "role": "system"
                }
            }
        }

        for capability, versions in test_prompts.items():
            cap_dir = prompts_dir / capability
            cap_dir.mkdir(exist_ok=True)
            
            for version, data in versions.items():
                file_path = cap_dir / f"{version}.yaml"
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f)
        
        # Создаем тестовые контракты
        test_contracts = {
            "planning": {
                "v1.0.0_input": {
                    "title": "Planning Input Schema",
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"}
                    },
                    "required": ["task"]
                },
                "v1.0.0_output": {
                    "title": "Planning Output Schema",
                    "type": "object",
                    "properties": {
                        "plan": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["plan"]
                }
            },
            "book_library": {
                "v2.0.0_input": {
                    "title": "Book Library Input Schema",
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                },
                "v2.0.0_output": {
                    "title": "Book Library Output Schema",
                    "type": "object",
                    "properties": {
                        "books": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["books"]
                }
            }
        }

        for capability, versions in test_contracts.items():
            cap_dir = skills_dir / capability
            cap_dir.mkdir(exist_ok=True)
            
            for version_suffix, schema in versions.items():
                # Извлекаем версию из суффикса
                parts = version_suffix.split('_')
                if len(parts) >= 2:
                    version = parts[0]  # v1.0.0
                    direction = parts[1]  # input или output
                    
                    file_path = cap_dir / f"{capability}_{version_suffix}.yaml"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        yaml.dump(schema, f)
        
        # Создаем конфигурацию
        system_config = SystemConfig(data_dir=str(temp_dir))
        
        # Создаем инфраструктурный контекст
        infra = InfrastructureContext(system_config)
        await infra.initialize()
        
        print("Инфраструктурный контекст инициализирован")
        
        # Тестируем автоматическую генерацию конфигурации для продакшена
        print("\n1. Тестирование автоматической генерации конфигурации для продакшена...")
        prod_context = await ApplicationContext.create_prod_auto(infra, profile="prod")
        
        print(f"   Prompt versions в автосгенерированной конфигурации: {prod_context.config.prompt_versions}")
        print(f"   Contract versions: {prod_context.config.contract_versions}")
        
        # Проверяем, что в продакшене есть только активные версии
        expected_active_prompts = {"planning": "v1.0.0", "book_library": "v2.0.0"}
        for capability, expected_version in expected_active_prompts.items():
            if capability in prod_context.config.prompt_versions:
                actual_version = prod_context.config.prompt_versions[capability]
                print(f"   - {capability}: {actual_version} (ожидалось {expected_version}) - {'V' if actual_version == expected_version else 'X'}")
            else:
                print(f"   - {capability}: отсутствует (✗)")
        
        success = await prod_context.initialize()
        print(f"   Продакшен контекст с автосгенерированной конфигурацией: {success}")
        
        if success:
            # Проверяем, что можно получить промпты
            for capability in prod_context.config.prompt_versions.keys():
                try:
                    prompt = prod_context.get_prompt(capability)
                    print(f"   - Промпт {capability}: {prompt[:30]}...")
                except Exception as e:
                    print(f"   - Ошибка получения промпта {capability}: {e}")
        
        # Тестируем песочницу с ручной конфигурацией
        print("\n2. Тестирование песочницы с ручной конфигурацией...")
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
        print(f"   Песочница с ручной конфигурацией и оверрайдом: {success}")
        
        if success:
            # В новой архитектуре получение промптов работает через PromptService
            # который должен быть правильно инициализирован
            prompt_service = sandbox_context.get_service("prompt_service")
            if prompt_service:
                try:
                    prompt = await prompt_service.render("planning", {})
                    print(f"   - Промпт в песочнице (должен быть v1.1.0): {prompt[:30]}...")
                except Exception as e:
                    print(f"   - Ошибка получения промпта в песочнице: {e}")
            else:
                print("   - PromptService недоступен в песочнице")
        
        # Тестируем продакшен с попыткой использовать черновик (должно отклонить)
        print("\n3. Тестирование продакшена с черновиком (должно отклонить)...")
        try:
            bad_config = AgentConfig(
                prompt_versions={"planning": "v1.1.0"},  # черновик
                side_effects_enabled=True
            )
            
            bad_prod_context = ApplicationContext(
                infrastructure_context=infra,
                config=bad_config,
                profile="prod"
            )
            
            success = await bad_prod_context.initialize()
            print(f"   Продакшен с черновиком: {success} (должно быть False)")
        except Exception as e:
            print(f"   Продакшен с черновиком отклонен: {e}")
        
        # Завершаем инфраструктурный контекст
        await infra.shutdown()
        
        print("\n=== Полный тест автоматической генерации завершен ===")


if __name__ == "__main__":
    asyncio.run(test_full_auto_config())
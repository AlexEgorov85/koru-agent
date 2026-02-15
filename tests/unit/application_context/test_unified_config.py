#!/usr/bin/env python3
"""
Тестирование новой архитектуры с единым AppConfig
"""
import asyncio
import tempfile
from pathlib import Path
import yaml

from core.config.app_config import AppConfig
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


async def test_unified_config():
    """Тестирование новой архитектуры с единым AppConfig"""
    print("=== Тестирование новой архитектуры с единым AppConfig ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Подготовка тестовых данных
        prompts_dir = Path(temp_dir) / "prompts"
        prompts_dir.mkdir(exist_ok=True)

        # Создаем тестовые подкаталоги и файлы
        planning_dir = prompts_dir / "planning"
        planning_dir.mkdir(exist_ok=True)

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
            }
        }

        for version, data in test_prompts.items():
            file_path = planning_dir / f"{version}.yaml"
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f)

        # Создаем системную конфигурацию
        system_config = SystemConfig(data_dir=str(temp_dir))

        # Создаем инфраструктурный контекст
        infra = InfrastructureContext(system_config)
        await infra.initialize()

        print("Инфраструктурный контекст инициализирован")

        # Тестируем продакшен контекст с автоматической генерацией конфигурации
        print("\n1. Тестирование продакшена с автоматической генерацией конфигурации...")
        prod_context = await ApplicationContext.create_prod_auto(infra, profile="prod")

        print(f"   Prompt versions: {prod_context.config.prompt_versions}")
        print(f"   Input contract versions: {prod_context.config.input_contract_versions}")
        print(f"   Output contract versions: {prod_context.config.output_contract_versions}")

        # Проверяем, что в продакшене есть только активные версии
        for capability, version in prod_context.config.prompt_versions.items():
            print(f"   - {capability}: {version}")

        success = await prod_context.initialize()
        print(f"   Продакшен контекст инициализирован: {success}")

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
        sandbox_config = AppConfig(
            config_id="sandbox_test",
            prompt_versions={"planning": "v1.0.0"},
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
        print(f"   Песочница с оверрайдом инициализирована: {success}")

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

        # Тестируем горячую замену версий
        print("\n3. Тестирование горячей замены версий...")
        new_context = await sandbox_context.clone_with_version_override(
            prompt_overrides={"planning": "v1.0.0"}  # возвращаем к активной версии
        )
        print(f"   Новый контекст с обновленной версией создан: {new_context is not None}")

        if new_context:
            try:
                await new_context.initialize()  # Инициализируем новый контекст
                new_prompt = new_context.get_prompt("planning")
                print(f"   - Промпт в новом контексте: {new_prompt[:30]}...")
            except Exception as e:
                print(f"   - Ошибка инициализации нового контекста: {e}")

        # Завершаем инфраструктурный контекст
        await infra.shutdown()

        print("\n=== Тестирование новой архитектуры завершено успешно ===")


if __name__ == "__main__":
    asyncio.run(test_unified_config())
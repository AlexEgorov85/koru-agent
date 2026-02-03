#!/usr/bin/env python3
"""
Демонстрация работы системы версионности промтов
"""
import asyncio
from application.services.prompt_initializer import PromptInitializer
from application.services.prompt_renderer import PromptRenderer
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository
from domain.models.capability import Capability
from domain.value_objects.provider_type import LLMProviderType


async def demo_prompt_versioning():
    """Демонстрация работы системы версионности промтов"""
    print("=== Демонстрация системы версионности промтов ===\n")
    
    # 1. Создаем репозиторий и инициализируем промты
    print("1. Создание репозитория и инициализация промтов...")
    repository = InMemoryPromptRepository()
    initializer = PromptInitializer(repository)
    await initializer.initialize_prompts()
    print("   OK Промты инициализированы\n")
    
    # 2. Создаем capability с привязкой к версиям промтов
    print("2. Создание capability с привязкой к версиям промтов...")
    capability = Capability(
        name="planning_task",
        description="Навык планирования задач",
        skill_name="planning_skill",
        prompt_versions={
            "openai:system": "prompt_123",  # Это будет заменено на реальный ID
            "openai:user": "prompt_456"    # Это будет заменено на реальный ID
        }
    )
    print(f"   OK Capability создан: {capability.name}\n")
    
    # 3. Демонстрация рендеринга промтов
    print("3. Демонстрация рендеринга промтов...")
    renderer = PromptRenderer(repository)
    
    # Получим все версии из репозитория и выберем подходящие для демонстрации
    all_versions = list(repository._versions.values())
    print(f"   Найдено версий промтов: {len(all_versions)}")
    
    for version in all_versions[:2]:  # Показываем первые 2 версии
        print(f"   - ID: {version.id}")
        print(f"     Capability: {version.capability_name}")
        print(f"     Роль: {version.role}")
        print(f"     Домен: {version.domain}")
        print(f"     Статус: {version.status}")
        print(f"     Переменные: {version.template_variables}")
        content_preview = version.content[:50]  # Возьмем только 50 символов
        safe_content = ''.join(c if ord(c) < 128 else '?' for c in content_preview)
        print(f"     Content (first 50 chars, safe): {safe_content}...")
        print()
    
    # 4. Демонстрация работы рендеринга
    print("4. Демонстрация рендеринга с подстановкой переменных...")
    
    # Найдем подходящий capability для демонстрации
    sample_capability = None
    for cap_name, version_obj in repository._versions.items():
        if "llm_decision" in version_obj.capability_name:
            sample_capability = Capability(
                name=version_obj.capability_name,
                description="Sample capability for demo",
                skill_name="demo_skill",
                prompt_versions={
                    f"{version_obj.provider_type.value}:{version_obj.role.value}": version_obj.id
                }
            )
            break
    
    if sample_capability:
        template_context = {
            "goal": "Анализировать структуру проекта",
            "tools": ["file_reader", "file_lister"],
            "last_steps_summary": "Шаг 1: Инициализация контекста"
        }
        
        rendered = await renderer.render_for_request(
            capability=sample_capability,
            provider_type=LLMProviderType.OPENAI,
            template_context=template_context
        )
        
        print("   Подставленные переменные:")
        for var, value in template_context.items():
            print(f"     {var}: {value}")
        
        print("\n   Результат рендеринга:")
        for role, content in rendered.items():
            safe_content = ''.join(c if ord(c) < 128 else '?' for c in content[:100])
            print(f"     {role.value}: {safe_content}...")
    else:
        print("   Не найдено подходящих capability для демонстрации")
    
    print("\n5. Демонстрация метрик использования...")
    # Показываем, как обновляются метрики
    for version_id, version in list(repository._versions.items())[:1]:
        print(f"   - Версия {version.id}:")
        print(f"     - Использований: {version.usage_metrics.usage_count}")
        print(f"     - Успешных: {version.usage_metrics.success_count}")
        print(f"     - Среднее время: {version.usage_metrics.avg_generation_time}")
        print(f"     - Ошибок: {version.usage_metrics.error_rate}")
    
    print("\nOK Демонстрация системы версионности промтов завершена!")


if __name__ == "__main__":
    asyncio.run(demo_prompt_versioning())

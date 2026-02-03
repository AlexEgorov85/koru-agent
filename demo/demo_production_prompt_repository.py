#!/usr/bin/env python3
"""
Демонстрация работы production-ready PromptRepository
"""
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from domain.models.prompt.prompt_version import (
    PromptVersion, PromptStatus, PromptRole, VariableSchema
)
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from application.services.prompt_renderer import PromptRenderer
from application.services.cached_prompt_repository import CachedPromptRepository
from domain.models.capability import Capability


async def demo_production_prompt_repository():
    """Демонстрация работы production-ready PromptRepository"""
    print("=== Демонстрация Production-Ready PromptRepository ===\n")
    
    # 1. Создаем mock-репозиторий (в реальной системе это будет DatabasePromptRepository)
    mock_repository = Mock()
    
    # 2. Создаем кэширующий репозиторий
    cached_repo = CachedPromptRepository(mock_repository)
    
    # 3. Создаем mock-менеджер снапшотов
    mock_snapshot_manager = Mock()
    mock_snapshot_manager.save_snapshot = AsyncMock()
    
    # 4. Создаем рендерер
    renderer = PromptRenderer(cached_repo, mock_snapshot_manager)
    
    print("1. Создание тестовой версии промта с полным жизненным циклом...")
    
    # Создаем тестовую версию промта
    test_version = PromptVersion(
        id="prod_test_version_001",
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="code_analysis",
        role=PromptRole.SYSTEM,
        content="Ты — эксперт по анализу кода. Проанализируй: {code_snippet}",
        variables_schema=[
            VariableSchema(
                name="code_snippet",
                type="string",
                required=True,
                description="Сниппет кода для анализа"
            ),
            VariableSchema(
                name="analysis_goal",
                type="string",
                required=False,
                description="Цель анализа"
            )
        ],
        status=PromptStatus.ACTIVE,
        version_notes="Инициализация production-версии промта для анализа кода"
    )
    
    print(f"   - ID: {test_version.id}")
    print(f"   - Версия: {test_version.semantic_version}")
    print(f"   - Домен: {test_version.domain}")
    print(f"   - Провайдер: {test_version.provider_type}")
    print(f"   - Капабилити: {test_version.capability_name}")
    print(f"   - Роль: {test_version.role}")
    print(f"   - Статус: {test_version.status}")
    print(f"   - Адрес: {test_version.get_address_key()}")
    print(f"   - Переменные: {[v.name for v in test_version.variables_schema]}")
    
    # Настройка mock-репозитория
    mock_repository.get_version_by_id = AsyncMock(return_value=test_version)
    mock_repository.get_active_version = AsyncMock(return_value=test_version)
    
    print("\n2. Демонстрация валидации переменных...")
    
    # Проверяем валидацию с корректными переменными
    validation_result = test_version.validate_variables({
        "code_snippet": "print('Hello World')"
    })
    print(f"   - Валидация с корректными переменными: {validation_result}")
    
    # Проверяем валидацию без обязательных переменных
    validation_result = test_version.validate_variables({
        "analysis_goal": "Найти баги"
    })
    print(f"   - Валидация без обязательной переменной: {validation_result}")
    
    print("\n3. Демонстрация рендеринга с валидацией...")
    
    # Создаем capability
    capability = Capability(
        name="code_analysis",
        description="Анализ кода",
        skill_name="code_analysis_skill",
        prompt_versions={
            "openai:system": "prod_test_version_001"
        }
    )
    
    # Рендерим с корректными переменными
    print("   - Рендеринг с корректными переменными:")
    rendered, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "code_snippet": "def hello():\n    return 'Hello World'",
            "analysis_goal": "Найти возможные проблемы"
        },
        session_id="demo_session_001"
    )
    
    print(f"     Ошибки: {errors}")
    if rendered:
        for role, content in rendered.items():
            print(f"     {role.value}: {content[:100]}...")
    
    # Рендерим без обязательной переменной
    print("   - Рендеринг без обязательной переменной:")
    rendered, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "analysis_goal": "Найти возможные проблемы"
        },  # code_snippet отсутствует
        session_id="demo_session_002"
    )
    
    print(f"     Ошибки: {errors}")
    print(f"     Результат: {rendered}")
    
    print("\n4. Демонстрация снапшотов выполнения...")
    
    # Рендерим и создаем снапшот
    rendered, snapshot, errors = await renderer.render_and_create_snapshot(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "code_snippet": "x = 1\ny = 2\nprint(x + y)"
        },
        session_id="demo_session_003"
    )
    
    print(f"   - Создан снапшот: {snapshot.id if snapshot else 'None'}")
    print(f"   - ID промта в снапшоте: {snapshot.prompt_id if snapshot else 'None'}")
    print(f"   - ID сессии в снапшоте: {snapshot.session_id if snapshot else 'None'}")
    print(f"   - Ошибки: {errors}")
    
    # Проверяем, что snapshot был передан в менеджер
    if mock_snapshot_manager.save_snapshot.called:
        print("   - Снапшот успешно передан в менеджер")
    
    print("\n5. Демонстрация полного жизненного цикла...")
    
    # Показываем возможные переходы статусов
    statuses = [PromptStatus.DRAFT, PromptStatus.ACTIVE, PromptStatus.SHADOW, 
                PromptStatus.DEPRECATED, PromptStatus.ARCHIVED]
    
    print("   - Возможные статусы:")
    for status in statuses:
        print(f"     * {status.value}: {status.description if hasattr(status, 'description') else 'Статус в системе промтов'}")
    
    print("\n6. Демонстрация контрактов переменных...")
    
    print("   - Схема переменных:")
    for var_schema in test_version.variables_schema:
        print(f"     * {var_schema.name}: {var_schema.type} ({'обязательная' if var_schema.required else 'опциональная'})")
        print(f"       Описание: {var_schema.description}")
    
    print("\nOK Демонстрация Production-Ready PromptRepository завершена успешно!")
    print("\nКлючевые особенности системы:")
    print("  - Полный жизненный цикл промтов (draft -> active -> shadow -> deprecated -> archived)")
    print("  - Строгая валидация переменных по схеме")
    print("  - Защита от инъекций через проверку переменных")
    print("  - Снапшоты выполнения для отладки и мониторинга")
    print("  - Кэширование в памяти для высокой производительности")
    print("  - Интеграция с файловой системой и базой данных")
    print("  - Совместимость с GreenPlum/PostgreSQL")


async def main():
    await demo_production_prompt_repository()


if __name__ == "__main__":
    asyncio.run(main())
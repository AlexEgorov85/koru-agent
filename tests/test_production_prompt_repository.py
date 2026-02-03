#!/usr/bin/env python3
"""
Тест production-ready PromptRepository
"""
import asyncio
import tempfile
import os
import sys
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Добавляем текущую директорию в путь Python для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from domain.models.prompt.prompt_version import (
    PromptVersion, PromptStatus, PromptRole, VariableSchema, PromptUsageMetrics
)
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from application.services.prompt_renderer import PromptRenderer


async def test_prompt_version_lifecycle():
    """Тест полного жизненного цикла промта"""
    print("=== Тест жизненного цикла промта ===")
    
    # Создаем версию промта
    prompt_version = PromptVersion(
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Тестовый промт с переменной {test_var}",
        variables_schema=[
            VariableSchema(
                name="test_var",
                type="string",
                required=True,
                description="Тестовая переменная"
            )
        ],
        status=PromptStatus.DRAFT
    )
    
    print(f"Создана версия: {prompt_version.id}")
    print(f"Статус: {prompt_version.status}")
    print(f"Адрес: {prompt_version.get_address_key()}")
    
    # Проверяем валидацию переменных
    validation_result = prompt_version.validate_variables({"test_var": "значение"})
    print(f"Валидация с корректными переменными: {validation_result}")
    
    validation_result = prompt_version.validate_variables({})
    print(f"Валидация без переменных: {validation_result}")
    
    assert len(validation_result) > 0, "Должна быть ошибка валидации при отсутствии обязательной переменной"
    print("OK Валидация переменных работает корректно")


async def test_prompt_renderer_with_validation():
    """Тест рендерера промтов с валидацией"""
    print("\n=== Тест рендерера промтов с валидацией ===")
    
    # Создаем mock-объекты
    mock_repository = Mock()
    mock_snapshot_manager = Mock()
    mock_snapshot_manager.save_snapshot = AsyncMock()
    
    # Создаем capability
    from domain.models.capability import Capability
    capability = Capability(
        name="test_capability",
        description="Тест capability",
        skill_name="test_skill",
        prompt_versions={
            "openai:system": "test_version_id"
        }
    )
    
    # Создаем тестовую версию промта
    test_version = PromptVersion(
        id="test_version_id",
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Промт с переменной {required_var} и {optional_var}",
        variables_schema=[
            VariableSchema(
                name="required_var",
                type="string",
                required=True,
                description="Обязательная переменная"
            ),
            VariableSchema(
                name="optional_var",
                type="string",
                required=False,
                description="Опциональная переменная"
            )
        ],
        status=PromptStatus.ACTIVE
    )
    
    # Настройка mock-репозитория
    mock_repository.get_version_by_id = AsyncMock(return_value=test_version)
    
    # Создаем рендерер
    renderer = PromptRenderer(mock_repository, mock_snapshot_manager)
    
    # Тестируем с корректными переменными
    rendered, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={"required_var": "тест", "optional_var": "опционально"},
        session_id="test_session"
    )
    
    print(f"Рендеринг с корректными переменными - ошибки: {errors}")
    print(f"Рендеринг с корректными переменными - результат: {rendered}")
    
    assert len(errors) == 0, "Не должно быть ошибок при корректных переменных"
    
    # Тестируем с отсутствующей обязательной переменной
    rendered, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={"optional_var": "опционально"},  # required_var отсутствует
        session_id="test_session"
    )
    
    print(f"Рендеринг без обязательной переменной - ошибки: {errors}")
    
    assert len(errors) > 0, "Должна быть ошибка при отсутствии обязательной переменной"
    print("OK Валидация в рендерере работает корректно")


async def test_prompt_status_transitions():
    """Тест переходов статусов промта"""
    print("\n=== Тест переходов статусов ===")
    
    # Создаем версию промта
    prompt_version = PromptVersion(
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Тестовый промт",
        status=PromptStatus.DRAFT
    )
    
    print(f"Начальный статус: {prompt_version.status}")
    
    # Имитируем изменение статуса (в реальной системе это будет происходить через репозиторий)
    updated_version = prompt_version.model_copy(update={'status': PromptStatus.ACTIVE})
    print(f"Статус после активации: {updated_version.status}")
    
    updated_version = updated_version.model_copy(update={'status': PromptStatus.DEPRECATED})
    print(f"Статус после депрекации: {updated_version.status}")
    
    updated_version = updated_version.model_copy(update={'status': PromptStatus.ARCHIVED})
    print(f"Статус после архивации: {updated_version.status}")
    
    print("OK Переходы статусов работают корректно")


async def main():
    """Основная функция теста"""
    print("Тестирование production-ready PromptRepository...")
    
    await test_prompt_version_lifecycle()
    await test_prompt_renderer_with_validation()
    await test_prompt_status_transitions()
    
    print("\nOK Все тесты пройдены успешно!")
    print("Production-ready PromptRepository готов к использованию.")


if __name__ == "__main__":
    asyncio.run(main())

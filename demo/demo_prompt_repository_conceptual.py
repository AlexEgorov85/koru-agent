#!/usr/bin/env python3
"""
Концептуальная демонстрация архитектуры production-ready PromptRepository
"""
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Добавляем текущую директорию в путь Python для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from domain.models.prompt.prompt_version import (
    PromptVersion, PromptStatus, PromptRole, VariableSchema, PromptUsageMetrics
)
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from domain.models.capability import Capability
from application.services.prompt_renderer import PromptRenderer
from application.services.cached_prompt_repository import CachedPromptRepository
from infrastructure.repositories.prompt_repository import DatabasePromptRepository, DatabaseSnapshotManager


async def demo_prompt_repository_architecture():
    """Демонстрация архитектуры PromptRepository"""
    print("=== Концептуальная демонстрация Production-Ready PromptRepository ===\n")
    
    print("1. Архитектурные компоненты системы:")
    print("   - PromptVersion: Модель данных версии промта")
    print("   - PromptRepository: Абстракция репозитория промтов")
    print("   - DatabasePromptRepository: Реализация с использованием DBProvider")
    print("   - CachedPromptRepository: Кэширующая обертка")
    print("   - PromptRenderer: Рендерер с валидацией переменных")
    print("   - PromptExecutionSnapshot: Снапшоты выполнения")
    
    print("\n2. Демонстрация модели PromptVersion с полным жизненным циклом:")
    
    # Создаем пример версии промта
    example_version = PromptVersion(
        id="prod_example_version_001",
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="code_analysis",
        role=PromptRole.SYSTEM,
        content="Ты — эксперт по анализу кода. Проанализируй: {{code_snippet}} с целью {{analysis_goal}}",
        variables_schema=[
            VariableSchema(name="code_snippet", type="string", required=True, description="Сниппет кода для анализа"),
            VariableSchema(name="analysis_goal", type="string", required=True, description="Цель анализа"),
            VariableSchema(name="context", type="string", required=False, description="Дополнительный контекст")
        ],
        status=PromptStatus.ACTIVE,
        version_notes="Инициализация production-версии промта для анализа кода"
    )
    
    print(f"   - ID: {example_version.id}")
    print(f"   - Семантическая версия: {example_version.semantic_version}")
    print(f"   - Домен: {example_version.domain}")
    print(f"   - Провайдер: {example_version.provider_type}")
    print(f"   - Капабилити: {example_version.capability_name}")
    print(f"   - Роль: {example_version.role}")
    print(f"   - Статус: {example_version.status}")
    print(f"   - Адрес: {example_version.get_address_key()}")
    print(f"   - Содержимое: {example_version.content}")
    print(f"   - Переменные: {[(v.name, v.type, v.required) for v in example_version.variables_schema]}")
    print(f"   - Заметки: {example_version.version_notes}")
    
    print("\n3. Демонстрация валидации переменных:")
    
    # Проверяем валидацию с корректными переменными
    validation_result = example_version.validate_variables({
        "code_snippet": "def hello(): pass",
        "analysis_goal": "нахождение багов"
    })
    print(f"   - Валидация корректных переменных: {len(validation_result)} ошибок")
    
    # Проверяем валидацию без обязательной переменной
    validation_result = example_version.validate_variables({
        "code_snippet": "def hello(): pass"
        # analysis_goal отсутствует
    })
    print(f"   - Валидация без обязательной переменной: {len(validation_result)} ошибок")
    if validation_result:
        for var_name, errors in validation_result.items():
            print(f"     - Ошибка переменной '{var_name}': {errors[0]}")
    
    print("\n4. Демонстрация схемы переменных:")
    for var_schema in example_version.variables_schema:
        required_status = "обязательная" if var_schema.required else "опциональная"
        print(f"   - {var_schema.name}: {var_schema.type} ({required_status}) - {var_schema.description}")
    
    print("\n5. Демонстрация статусов жизненного цикла:")
    status_descriptions = {
        PromptStatus.DRAFT: "Черновик, не готов к использованию",
        PromptStatus.ACTIVE: "Активная версия, используется в системе",
        PromptStatus.SHADOW: "Теневая версия для A/B тестирования",
        PromptStatus.DEPRECATED: "Устаревшая, но еще работает",
        PromptStatus.ARCHIVED: "Архивированная, больше не используется"
    }
    
    for status, description in status_descriptions.items():
        print(f"   - {status.value}: {description}")
    
    print("\n6. Демонстрация структуры Capability:")
    
    # Создаем пример capability
    example_capability = Capability(
        name="code_analysis",
        description="Анализ кода",
        skill_name="code_analysis_skill",
        prompt_versions={
            "openai:system": "prod_example_version_001",
            "openai:user": "user_version_002"
        }
    )
    
    print(f"   - Название: {example_capability.name}")
    print(f"   - Описание: {example_capability.description}")
    print(f"   - Навык: {example_capability.skill_name}")
    print(f"   - Привязки версий: {example_capability.prompt_versions}")
    
    print("\n7. Демонстрация снапшота выполнения:")
    
    # Создаем пример снапшота
    from domain.models.prompt.prompt_execution_snapshot import PromptExecutionSnapshot
    example_snapshot = PromptExecutionSnapshot(
        id="snapshot_001",
        prompt_id="prod_example_version_001",
        session_id="session_001",
        rendered_prompt="Ты — эксперт по анализу кода. Проанализируй: def hello(): pass с целью нахождение багов",
        variables={
            "code_snippet": "def hello(): pass",
            "analysis_goal": "нахождение багов"
        },
        response="Код выглядит корректным...",
        execution_time=1.25,
        timestamp=datetime.utcnow(),
        success=True,
        error_message=None,
        rejection_reason=None,
        provider_response_time=1.2
    )
    
    print(f"   - ID промта: {example_snapshot.prompt_id}")
    print(f"   - ID сессии: {example_snapshot.session_id}")
    print(f"   - Отрендеренный промт: {example_snapshot.rendered_prompt[:100]}...")
    print(f"   - Переменные: {list(example_snapshot.variables.keys())}")
    print(f"   - Время выполнения: {example_snapshot.execution_time}s")
    print(f"   - Успех: {example_snapshot.success}")
    print(f"   - Время ответа провайдера: {example_snapshot.provider_response_time}s")
    
    print("\n8. Демонстрация метрик использования:")
    
    example_metrics = PromptUsageMetrics(
        usage_count=150,
        success_count=142,
        avg_generation_time=1.35,
        last_used_at=datetime.utcnow(),
        error_rate=0.05,
        rejection_count=3
    )
    
    print(f"   - Количество использований: {example_metrics.usage_count}")
    print(f"   - Количество успехов: {example_metrics.success_count}")
    print(f"   - Среднее время генерации: {example_metrics.avg_generation_time}s")
    print(f"   - Время последнего использования: {example_metrics.last_used_at}")
    print(f"   - Процент ошибок: {example_metrics.error_rate * 100}%")
    print(f"   - Количество отклонений: {example_metrics.rejection_count}")
    
    print("\n9. Иерархия репозитория:")
    print("   - IPromptRepository (абстракция)")
    print("     + DatabasePromptRepository (реализация с DBProvider)")
    print("       + CachedPromptRepository (кэширующая обертка)")
    
    print("\n10. Поток выполнения запроса:")
    print("   1. Agent → Capability")
    print("   2. PromptRenderer ← Capability (получает промт по ID)")
    print("   3. CachedPromptRepository ← ID версии")
    print("   4. DatabasePromptRepository ← ID версии (если нет в кэше)")
    print("   5. PromptVersion.validate_variables(контекст)")
    print("   6. Подстановка переменных в шаблон")
    print("   7. Создание PromptExecutionSnapshot")
    print("   8. Результат → Agent → LLM")
    
    print("\n=== Архитектурная демонстрация завершена ===")
    print("\nКлючевые особенности production-ready PromptRepository:")
    print("  ✓ Полный жизненный цикл промтов (draft → active → shadow → deprecated → archived)")
    print("  ✓ Строгая валидация переменных по схеме")
    print("  ✓ Защита от инъекций через проверку переменных")
    print("  ✓ Снапшоты выполнения для отладки и мониторинга")
    print("  ✓ Кэширование в памяти для высокой производительности")
    print("  ✓ Интеграция с файловой системой и базой данных")
    print("  ✓ Совместимость с GreenPlum/PostgreSQL")
    print("  ✓ Обработка ошибок и fallback-механизмы")
    print("  ✓ Метрики использования и производительности")


async def main():
    await demo_prompt_repository_architecture()


if __name__ == "__main__":
    asyncio.run(main())

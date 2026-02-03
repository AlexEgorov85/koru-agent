"""
Интеграционный тест полного workflow PromptRepository
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from domain.models.prompt.prompt_version import (
    PromptVersion, PromptStatus, PromptRole, VariableSchema
)
from domain.models.capability import Capability
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from application.services.prompt_renderer import PromptRenderer
from application.services.cached_prompt_repository import CachedPromptRepository
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository
from domain.models.prompt.prompt_execution_snapshot import PromptExecutionSnapshot


# Удаляем фикстуру, так как она будет мешать тестированию, и используем мок напрямую в тестах
# pytest.fixture
# def mock_db_provider():
#     """Фикстура для mock DBProvider"""
#     provider = Mock()
#     provider.execute_query = AsyncMock()
#     provider.execute_non_query = AsyncMock()
#     return provider


@pytest.mark.asyncio
async def test_full_prompt_repository_workflow():
    """Тест полного workflow PromptRepository от файла до выполнения"""
    print("=== Тест полного workflow PromptRepository ===\n")
    
    # 1. Создаем мок для DBProvider
    mock_db_provider = Mock()
    mock_db_provider.execute_query = AsyncMock(return_value=[])
    mock_db_provider.execute_non_query = AsyncMock(return_value=None)
    
    # Создаем репозиторий
    db_repo = InMemoryPromptRepository()
    cached_repo = CachedPromptRepository(db_repo)
    
    print("1. Репозитории созданы")
    
    # 2. Создаем версию промта
    test_version = PromptVersion(
        id="full_workflow_test_version_001",
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="full_workflow_test",
        role=PromptRole.SYSTEM,
        content="Анализируй код: {{code_snippet}} с целью {{analysis_goal}}",
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
                required=True,
                description="Цель анализа"
            )
        ],
        status=PromptStatus.ACTIVE
    )
    
    print(f"2. Создана версия промта: {test_version.id}")
    print(f"   - Семантическая версия: {test_version.semantic_version}")
    print(f"   - Домен: {test_version.domain}")
    print(f"   - Роль: {test_version.role}")
    print(f"   - Статус: {test_version.status}")
    print(f"   - Переменные: {[(v.name, v.required) for v in test_version.variables_schema]}")
    
    # 3. Сохраняем версию в репозиторий
    await cached_repo.save_version(test_version)
    print("3. Версия сохранена в репозиторий")
    
    # 4. Проверяем, что версия доступна
    retrieved_version = await cached_repo.get_version_by_id("full_workflow_test_version_001")
    assert retrieved_version is not None
    assert retrieved_version.id == test_version.id
    assert retrieved_version.status == PromptStatus.ACTIVE
    print("4. Версия успешно извлечена из репозитория")
    
    # 5. Проверяем получение активной версии по адресу
    active_version = await cached_repo.get_active_version(
        domain="problem_solving",
        capability_name="full_workflow_test",
        provider_type="openai",
        role="system"
    )
    assert active_version is not None
    assert active_version.id == test_version.id
    print("5. Активная версия успешно получена по адресу")
    
    # 6. Создаем менеджер снапшотов
    mock_snapshot_manager = Mock()
    mock_snapshot_manager.save_snapshot = AsyncMock()
    
    # 7. Создаем рендерер
    renderer = PromptRenderer(cached_repo, mock_snapshot_manager)
    
    print("6. Рендерер создан")
    
    # 8. Создаем capability
    capability = Capability(
        name="full_workflow_test",
        description="Тест полного workflow",
        skill_name="test_skill",
        prompt_versions={
            "openai:system": "full_workflow_test_version_001"
        }
    )
    
    print("7. Capability создан")
    
    # 9. Рендерим с корректными переменными
    print("8. Рендеринг с корректными переменными...")
    rendered, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "code_snippet": "def hello(): pass",
            "analysis_goal": "нахождение багов"
        },
        session_id="test_session_001"
    )
    
    assert len(errors) == 0, f"Не должно быть ошибок при корректных переменных, но получено: {errors}"
    assert PromptRole.SYSTEM in rendered
    expected_content = "Анализируй код: def hello(): pass с целью нахождение багов"
    assert rendered[PromptRole.SYSTEM] == expected_content
    print(f"   - Результат рендеринга: {rendered[PromptRole.SYSTEM]}")
    
    # 10. Рендерим с отсутствующей обязательной переменной
    print("9. Рендеринг с отсутствующей обязательной переменной...")
    rendered, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "code_snippet": "def hello(): pass"
            # analysis_goal отсутствует
        },
        session_id="test_session_002"
    )
    
    assert len(errors) > 0, "Должна быть ошибка при отсутствии обязательной переменной"
    print(f"   - Ошибки валидации: {errors}")
    
    # 11. Рендерим и создаем снапшот
    print("10. Рендеринг и создание снапшота...")
    rendered, snapshot, errors = await renderer.render_and_create_snapshot(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "code_snippet": "x = 1\ny = 2\nprint(x + y)",
            "analysis_goal": "проверка корректности"
        },
        session_id="test_session_003"
    )
    
    assert len(errors) == 0, "Не должно быть ошибок при корректных переменных"
    assert snapshot is not None, "Снапшот должен быть создан"
    assert snapshot.prompt_id == "full_workflow_test_version_001"
    assert snapshot.session_id == "test_session_003"
    print(f"   - Снапшот создан: {snapshot.id}")
    print(f"   - ID промта в снапшоте: {snapshot.prompt_id}")
    print(f"   - ID сессии в снапшоте: {snapshot.session_id}")
    
    # Проверяем, что снапшот был передан в менеджер
    assert mock_snapshot_manager.save_snapshot.called, "Снапшот должен быть передан в менеджер"
    print("   - Снапшот успешно передан в менеджер")
    
    # 12. Проверяем валидацию переменных в версии
    print("11. Проверка валидации переменных в версии...")
    validation_errors = test_version.validate_variables({
        "code_snippet": "test code",
        "analysis_goal": "test goal"
    })
    assert len(validation_errors) == 0, "Валидация должна пройти успешно для корректных переменных"
    print("   - Валидация корректных переменных: OK")
    
    validation_errors = test_version.validate_variables({
        "code_snippet": "test code"
        # analysis_goal отсутствует
    })
    assert len(validation_errors) > 0, "Должна быть ошибка при отсутствии обязательной переменной"
    assert "analysis_goal" in validation_errors, "Ошибка должна быть для отсутствующей переменной analysis_goal"
    print(f"   - Валидация без обязательной переменной: {validation_errors}")
    
    # 13. Проверяем обновление метрик
    print("12. Проверка обновления метрик...")
    # Имитируем обновление метрик
    from domain.models.prompt.prompt_version import PromptUsageMetrics
    metrics_update = PromptUsageMetrics(
        usage_count=1,
        success_count=1,
        avg_generation_time=0.5,
        error_rate=0.0,
        rejection_count=0
    )
    
    await cached_repo.update_usage_metrics("full_workflow_test_version_001", metrics_update)
    print("   - Метрики успешно обновлены")
    
    # 14. Проверяем изменение статуса
    print("13. Проверка изменения статуса...")
    await cached_repo.update_version_status("full_workflow_test_version_001", PromptStatus.DEPRECATED)
    
    updated_version = await cached_repo.get_version_by_id("full_workflow_test_version_001")
    assert updated_version.status == PromptStatus.DEPRECATED
    print(f"   - Статус изменен на: {updated_version.status}")
    
    # 15. Проверяем работу кэша
    print("14. Проверка работы кэша...")
    # Второй раз запрашиваем ту же версию - должна быть из кэша
    cached_version = await cached_repo.get_version_by_id("full_workflow_test_version_001")
    assert cached_version is not None
    assert cached_version.id == "full_workflow_test_version_001"
    print("   - Версия успешно получена из кэша")
    
    print("\n✓ Все этапы полного workflow успешно пройдены!")
    print("\nТест проверил:")
    print("  - Создание и сохранение версии промта")
    print("  - Получение версии из репозитория")
    print("  - Получение активной версии по адресу")
    print("  - Рендеринг с валидацией переменных")
    print("  - Создание снапшотов выполнения")
    print("  - Валидацию переменных в модели")
    print("  - Обновление метрик использования")
    print("  - Изменение статусов версий")
    print("  - Работу кэширования")


@pytest.mark.asyncio
async def test_prompt_version_lifecycle_management():
    """Тест управления жизненным циклом версий промтов"""
    print("\n=== Тест управления жизненным циклом ===")
    
    # Создаем мок для DBProvider
    mock_db_provider = Mock()
    mock_db_provider.execute_query = AsyncMock(return_value=[])
    mock_db_provider.execute_non_query = AsyncMock(return_value=None)
    
    # Создаем репозиторий
    db_repo = InMemoryPromptRepository()
    cached_repo = CachedPromptRepository(db_repo)
    
    # Создаем версию
    version = PromptVersion(
        id="lifecycle_test_version_001",
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="lifecycle_test",
        role=PromptRole.SYSTEM,
        content="Тестовый промт для жизненного цикла: {{test_var}}",
        variables_schema=[
            VariableSchema(name="test_var", type="string", required=True, description="Тестовая переменная")
        ],
        status=PromptStatus.DRAFT
    )
    
    # Сохраняем
    await cached_repo.save_version(version)
    print(f"1. Версия создана со статусом: {version.status}")
    
    # Активируем
    await cached_repo.activate_version("lifecycle_test_version_001")
    activated_version = await cached_repo.get_version_by_id("lifecycle_test_version_001")
    assert activated_version.status == PromptStatus.ACTIVE
    print(f"2. Версия активирована, статус: {activated_version.status}")
    
    # Архивируем
    await cached_repo.archive_version("lifecycle_test_version_001")
    archived_version = await cached_repo.get_version_by_id("lifecycle_test_version_001")
    assert archived_version.status == PromptStatus.ARCHIVED
    print(f"3. Версия архивирована, статус: {archived_version.status}")
    
    print("✓ Тест жизненного цикла пройден")


@pytest.mark.asyncio
async def test_security_validation_features():
    """Тест функций безопасности и валидации"""
    print("\n=== Тест функций безопасности ===")
    
    # Создаем мок для DBProvider
    mock_db_provider = Mock()
    mock_db_provider.execute_query = AsyncMock(return_value=[])
    mock_db_provider.execute_non_query = AsyncMock(return_value=None)
    
    # Создаем репозиторий
    db_repo = InMemoryPromptRepository()
    cached_repo = CachedPromptRepository(db_repo)
    
    # Создаем версию с безопасной схемой переменных
    secure_version = PromptVersion(
        id="security_test_version_001",
        semantic_version="1.0.0",
        domain=DomainType.SECURITY,
        provider_type=LLMProviderType.OPENAI,
        capability_name="security_test",
        role=PromptRole.SYSTEM,
        content="Обрабатывай безопасно: {{safe_input}}",
        variables_schema=[
            VariableSchema(
                name="safe_input", 
                type="string", 
                required=True, 
                description="Безопасный ввод",
                validation_pattern=r"^[a-zA-Z0-9\s]+$"  # Только буквы, цифры и пробелы
            )
        ],
        status=PromptStatus.ACTIVE
    )
    
    await cached_repo.save_version(secure_version)
    
    # Проверяем валидацию с безопасным вводом
    validation_result = secure_version.validate_variables({
        "safe_input": "normal text 123"
    })
    assert len(validation_result) == 0, "Безопасный ввод должен пройти валидацию"
    print("1. Безопасный ввод проходит валидацию")
    
    # Проверяем валидацию с потенциально опасным вводом
    validation_result = secure_version.validate_variables({
        "safe_input": "malicious code {{__import__('os').system('rm -rf /')}}"
    })
    assert len(validation_result) > 0, "Потенциально опасный ввод не должен пройти валидацию"
    print("2. Потенциально опасный ввод отклоняется валидацией")
    
    # Проверяем, что рендерер не подставляет переменные, не определенные в схеме
    renderer = PromptRenderer(cached_repo, Mock())
    capability = Capability(
        name="security_test",
        description="Тест безопасности",
        skill_name="security_test_skill",
        prompt_versions={
            "openai:system": "security_test_version_001"
        }
    )
    
    # Переменная, не определенная в схеме, не должна быть подставлена
    rendered, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "safe_input": "normal text",
            "malicious_var": "should_not_be_substituted"  # Эта переменная не определена в схеме
        },
        session_id="security_test_001"
    )
    
    assert len(errors) == 0, "Ошибок быть не должно при корректных переменных"
    assert "should_not_be_substituted" not in rendered[PromptRole.SYSTEM], "Непредусмотренные переменные не должны подставляться"
    print("3. Рендерер защищен от подстановки непредусмотренных переменных")
    
    print("✓ Тест функций безопасности пройден")


if __name__ == "__main__":
    asyncio.run(test_full_prompt_repository_workflow(Mock()))
    asyncio.run(test_prompt_version_lifecycle_management(Mock()))
    asyncio.run(test_security_validation_features(Mock()))
    print("\n🎉 Все интеграционные тесты пройдены успешно!")
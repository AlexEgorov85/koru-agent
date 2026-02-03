import pytest
from unittest.mock import Mock, AsyncMock
from domain.models.capability import Capability
from application.gateways.execution.execution_gateway import ExecutionGateway
from infrastructure.repositories.prompt_repository import DatabasePromptRepository


@pytest.fixture
def mock_system_context():
    """Фикстура для mock системного контекста"""
    context = Mock()
    # Создаем mock навыка
    mock_skill = Mock()
    mock_skill.execute = AsyncMock(return_value="Test result")
    context.get_resource.return_value = mock_skill
    return context


@pytest.mark.asyncio
async def test_execution_gateway_works_without_prompt_versions(mock_system_context):
    """Тест, что ExecutionGateway работает без привязки к версиям промтов (обратная совместимость)"""
    # Создаем capability БЕЗ привязки к версиям промтов
    capability = Capability(
        name="test_capability",
        description="Test capability without prompt versions",
        skill_name="test_skill"
        # НЕТ поля prompt_versions
    )
    
    # Создаем сессию
    mock_session = Mock()
    
    # Создаем ExecutionGateway без репозитория промтов
    gateway = ExecutionGateway(mock_system_context, prompt_repository=None)
    
    # Выполняем capability
    result = await gateway.execute_capability(
        capability=capability,
        parameters={"test_param": "test_value"},
        session=mock_session
    )
    
    # Проверяем, что выполнение прошло успешно (обратная совместимость)
    assert result.status.name == "SUCCESS"
    assert result.summary == "Capability 'test_capability' executed successfully"


@pytest.mark.asyncio
async def test_execution_gateway_works_with_empty_prompt_versions(mock_system_context):
    """Тест, что ExecutionGateway работает с пустыми версиями промтов"""
    # Создаем capability с пустым словарем версий промтов
    capability = Capability(
        name="test_capability",
        description="Test capability with empty prompt versions",
        skill_name="test_skill",
        prompt_versions={}  # Пустой словарь
    )
    
    # Создаем сессию
    mock_session = Mock()
    
    # Создаем ExecutionGateway без репозитория промтов
    gateway = ExecutionGateway(mock_system_context, prompt_repository=None)
    
    # Выполняем capability
    result = await gateway.execute_capability(
        capability=capability,
        parameters={"test_param": "test_value"},
        session=mock_session
    )
    
    # Проверяем, что выполнение прошло успешно (обратная совместимость)
    assert result.status.name == "SUCCESS"
    assert result.summary == "Capability 'test_capability' executed successfully"


@pytest.mark.asyncio
async def test_execution_gateway_works_with_partial_prompt_versions(mock_system_context):
    """Тест, что ExecutionGateway работает с частичными версиями промтов"""
    # Создаем capability с частичными версиями (только одна роль)
    capability = Capability(
        name="test_capability",
        description="Test capability with partial prompt versions",
        skill_name="test_skill",
        prompt_versions={
            "openai:system": "existing_version_id"  # Только системный промт, нет пользовательского
        }
    )
    
    # Создаем сессию
    mock_session = Mock()
    
    # Создаем ExecutionGateway с репозиторием, который НЕ содержит указанную версию
    repo = Mock()
    repo.get_version_by_id = AsyncMock(return_value=None)  # Возвращаем None, так как версия не существует
    gateway = ExecutionGateway(mock_system_context, prompt_repository=repo)
    
    # Выполняем capability
    result = await gateway.execute_capability(
        capability=capability,
        parameters={"test_param": "test_value"},
        session=mock_session
    )
    
    # Проверяем, что выполнение прошло успешно (обратная совместимость)
    assert result.status.name == "SUCCESS"
    assert result.summary == "Capability 'test_capability' executed successfully"


@pytest.mark.asyncio
async def test_execution_gateway_error_handling(mock_system_context):
    """Тест обработки ошибок в ExecutionGateway для обратной совместимости"""
    # Создаем capability
    capability = Capability(
        name="test_capability",
        description="Test capability for error handling",
        skill_name="test_skill"
    )
    
    # Создаем сессию
    mock_session = Mock()
    
    # Создаем ExecutionGateway
    gateway = ExecutionGateway(mock_system_context, prompt_repository=None)
    
    # Вызываем ошибку в навыке
    mock_skill = Mock()
    mock_skill.execute = AsyncMock(side_effect=Exception("Test error"))
    mock_system_context.get_resource.return_value = mock_skill
    
    # Выполняем capability (ожидаем ошибку)
    result = await gateway.execute_capability(
        capability=capability,
        parameters={"test_param": "test_value"},
        session=mock_session
    )
    
    # Проверяем, что ошибка обработана корректно
    assert result.status.name == "FAILED"
    assert "Test error" in result.error


@pytest.mark.asyncio
async def test_existing_functionality_preserved(mock_system_context):
    """Тест, что существующая функциональность сохранена"""
    # Создаем capability без версий промтов (как в оригинальной системе)
    capability = Capability(
        name="original_capability",
        description="Original capability without prompt versioning",
        skill_name="original_skill"
    )
    
    # Создаем сессию
    mock_session = Mock()
    
    # Выполняем через ExecutionGateway без репозитория (оригинальное поведение)
    gateway = ExecutionGateway(mock_system_context, prompt_repository=None)
    
    # Выполняем capability
    result = await gateway.execute_capability(
        capability=capability,
        parameters={},
        session=mock_session
    )
    
    # Проверяем, что результат такой же, как и до добавления системы версионности
    assert result.status.name == "SUCCESS"
    assert result.result == "Test result"  # Значение из mock
    assert result.summary == "Capability 'original_capability' executed successfully"


@pytest.mark.asyncio
async def test_new_fields_optional_in_capability():
    """Тест, что новые поля в Capability являются опциональными"""
    # Создаем capability старым способом (без новых полей)
    capability_dict = {
        "name": "legacy_capability",
        "description": "Legacy capability without new fields",
        "skill_name": "legacy_skill"
    }
    
    # Создаем объект Capability (новое поле prompt_versions должно быть опциональным)
    capability = Capability(**capability_dict)
    
    # Проверяем, что новое поле по умолчанию имеет допустимое значение
    assert hasattr(capability, 'prompt_versions')
    assert capability.prompt_versions is not None  # Должно быть инициализировано
    assert isinstance(capability.prompt_versions, dict)  # Должно быть словарем
    
    # Проверяем, что остальные поля также работают
    assert capability.name == "legacy_capability"
    assert capability.description == "Legacy capability without new fields"
    assert capability.skill_name == "legacy_skill"
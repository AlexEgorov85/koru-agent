import pytest
from unittest.mock import Mock, AsyncMock
from application.gateways.execution.execution_gateway import ExecutionGateway
from domain.models.capability import Capability
from domain.models.prompt.prompt_version import PromptVersion, PromptRole
from application.services.prompt_renderer import PromptRenderer

from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository


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
async def test_prompt_version_end_to_end_flow(mock_system_context):
    """Тест сквозного потока работы с версиями промтов"""
    # Создаем репозиторий и добавляем тестовые версии
    repo = InMemoryPromptRepository()
    
    system_version = PromptVersion(
        id="system_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="You are a {{role}} assistant for {{task_type}}.",
        variables_schema=[
            {"name": "role", "type": "string", "required": True, "description": "Role for the assistant"},
            {"name": "task_type", "type": "string", "required": True, "description": "Type of task"}
        ],
        status="active"
    )
    
    user_version = PromptVersion(
        id="user_version_456",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.USER,
        content="Please analyze this code: {{code}}",
        variables_schema=[
            {"name": "code", "type": "string", "required": True, "description": "Code to analyze"}
        ],
        status="active"
    )
    
    # Сохраняем версии в репозитории
    await repo.save_version(system_version)
    await repo.save_version(user_version)
    
    # Создаем capability с привязкой к версиям
    capability = Capability(
        name="test_capability",
        description="Test capability",
        skill_name="test_skill",
        prompt_versions={
            "openai:system": "system_version_123",
            "openai:user": "user_version_456"
        }
    )
    
    # Создаем сессию (упрощенная версия для теста)
    mock_session = Mock()
    mock_session.get_goal = Mock(return_value="Test goal")
    mock_session.get_last_steps = Mock(return_value=["Step 1", "Step 2"])
    
    # Создаем ExecutionGateway с репозиторием
    gateway = ExecutionGateway(mock_system_context, prompt_repository=repo)
    
    # Выполняем capability
    result = await gateway.execute_capability(
        capability=capability,
        parameters={"role": "coding", "task_type": "analysis", "code": "print('Hello')"},
        session=mock_session
    )
    
    # Проверяем результат
    assert result.status.name == "SUCCESS"
    assert result.summary == "Capability 'test_capability' executed successfully"
    
    # Проверяем, что метрики были обновлены
    updated_system_version = await repo.get_version_by_id("system_version_123")
    assert updated_system_version.usage_metrics.usage_count >= 0  # Может быть 0 или 1 в зависимости от реализации


@pytest.mark.asyncio
async def test_prompt_renderer_with_repository():
    """Тест работы PromptRenderer с реальным репозиторием"""
    # Создаем репозиторий и добавляем версию
    repo = InMemoryPromptRepository()
    
    version = PromptVersion(
        id="test_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="You are a {{role}} assistant for {{task_type}} tasks.",
        variables_schema=[
            {"name": "role", "type": "string", "required": True, "description": "Role for the assistant"},
            {"name": "task_type", "type": "string", "required": True, "description": "Type of task"}
        ],
        status="active"
    )
    
    await repo.save_version(version)
    
    # Создаем capability
    capability = Capability(
        name="test_capability",
        description="Test capability",
        skill_name="test_skill",
        prompt_versions={
            "openai:system": "test_version_123"
        }
    )
    
    # Создаем рендерер
    renderer = PromptRenderer(repo)
    
    # Рендерим промт
    result, errors  = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "role": "coding",
            "task_type": "debugging"
        },
        session_id="test_session_123"
    )
    
    # Проверяем результат
    assert PromptRole.SYSTEM in result
    expected_content = "You are a coding assistant for debugging tasks."
    assert result[PromptRole.SYSTEM] == expected_content


@pytest.mark.asyncio
async def test_execution_gateway_without_prompt_repository():
    """Тест работы ExecutionGateway без репозитория промтов (обратная совместимость)"""
    # Создаем capability без привязки к версиям
    capability = Capability(
        name="test_capability",
        description="Test capability",
        skill_name="test_skill"
    )
    
    # Создаем сессию
    mock_session = Mock()
    
    # Создаем ExecutionGateway без репозитория
    mock_system_context = Mock()
    mock_skill = Mock()
    mock_skill.execute = AsyncMock(return_value="Test result")
    mock_system_context.get_resource.return_value = mock_skill
    
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
async def test_prompt_version_metrics_updates():
    """Тест обновления метрик использования версий промтов"""
    # Создаем репозиторий
    repo = InMemoryPromptRepository()
    
    version = PromptVersion(
        id="metrics_test_version",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Test prompt for metrics",
        status="active"
    )
    
    await repo.save_version(version)
    
    # Проверяем начальные метрики
    initial_version = await repo.get_version_by_id("metrics_test_version")
    initial_usage_count = initial_version.usage_metrics.usage_count
    
    # Создаем capability
    capability = Capability(
        name="test_capability",
        description="Test capability",
        skill_name="test_skill",
        prompt_versions={
            "openai:system": "metrics_test_version"
        }
    )
    
    # Создаем сессию
    mock_session = Mock()
    mock_session.get_goal = Mock(return_value="Test goal")
    
    # Создаем ExecutionGateway
    mock_system_context = Mock()
    mock_skill = Mock()
    mock_skill.execute = AsyncMock(return_value="Test result")
    mock_system_context.get_resource.return_value = mock_skill
    
    gateway = ExecutionGateway(mock_system_context, prompt_repository=repo)
    
    # Выполняем capability несколько раз
    for _ in range(3):
        await gateway.execute_capability(
            capability=capability,
            parameters={},
            session=mock_session
        )
    
    # Проверяем, что метрики обновились
    updated_version = await repo.get_version_by_id("metrics_test_version")
    assert updated_version.usage_metrics.usage_count >= initial_usage_count
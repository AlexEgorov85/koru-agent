import pytest
from unittest.mock import Mock, AsyncMock
from domain.models.capability import Capability
from domain.models.prompt.prompt_version import PromptVersion, PromptRole, PromptUsageMetrics, VariableSchema
from application.services.prompt_renderer import PromptRenderer
from application.gateways.execution.execution_gateway import ExecutionGateway
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository
from datetime import datetime


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
async def test_complete_prompt_versioning_workflow(mock_system_context):
    """Тест полного рабочего процесса системы версионности промтов"""
    # 1. Создаем репозиторий и добавляем версии промтов
    repo = InMemoryPromptRepository()
    
    # Создаем системный промт
    system_version = PromptVersion(
        id="sys_v1_0_0",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="code_analyzer",
        role=PromptRole.SYSTEM,
        content="You are an expert {{expertise}} assistant for {{task_type}} tasks.",
        variables_schema=[
            VariableSchema(name="expertise", type="string", required=True, description="Expertise area"),
            VariableSchema(name="task_type", type="string", required=True, description="Type of task")
        ],
        status="draft"  # Сначала статус draft
    )
    
    # Создаем пользовательский промт
    user_version = PromptVersion(
        id="usr_v1_0_0",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="code_analyzer",
        role=PromptRole.USER,
        content="Analyze this code: {{code}} and identify {{concerns}}.",
        variables_schema=[
            VariableSchema(name="code", type="string", required=True, description="Code to analyze"),
            VariableSchema(name="concerns", type="string", required=True, description="Concerns to identify")
        ],
        status="draft"
    )
    
    # Сохраняем версии
    await repo.save_version(system_version)
    await repo.save_version(user_version)
    
    # 2. Активируем версии
    await repo.activate_version("sys_v1_0_0")
    await repo.activate_version("usr_v1_0_0")
    
    # 3. Проверяем, что версии активированы
    active_sys = await repo.get_active_version(
        domain="code_generation",
        capability_name="code_analyzer",
        provider_type="openai",
        role="system"
    )
    active_usr = await repo.get_active_version(
        domain="code_generation",
        capability_name="code_analyzer",
        provider_type="openai",
        role="user"
    )
    
    assert active_sys is not None
    assert active_usr is not None
    assert active_sys.status == "active"
    assert active_usr.status == "active"
    
    # 4. Создаем capability с привязкой к версиям
    capability = Capability(
        name="code_analyzer",
        description="Code analysis capability",
        skill_name="code_analysis_skill",
        prompt_versions={
            "openai:system": "sys_v1_0_0",
            "openai:user": "usr_v1_0_0"
        }
    )
    
    # 5. Тестируем рендеринг через PromptRenderer
    renderer = PromptRenderer(repo)
    
    template_context = {
        "expertise": "Python coding",
        "task_type": "code review",
        "code": "def hello():\n    print('Hello, World!')",
        "concerns": "potential bugs and performance issues"
    }
    
    rendered_prompts = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверяем результаты рендеринга
    assert PromptRole.SYSTEM in rendered_prompts
    assert PromptRole.USER in rendered_prompts
    
    expected_system = "You are an expert Python coding assistant for code review tasks."
    expected_user = "Analyze this code: def hello():\n    print('Hello, World!') and identify potential bugs and performance issues."
    
    assert rendered_prompts[PromptRole.SYSTEM] == expected_system
    assert rendered_prompts[PromptRole.USER] == expected_user
    
    # 6. Тестируем выполнение через ExecutionGateway
    mock_session = Mock()
    mock_session.get_goal = Mock(return_value="Perform code analysis")
    mock_session.get_last_steps = Mock(return_value=["Step 1: Identify code", "Step 2: Analyze structure"])
    
    gateway = ExecutionGateway(mock_system_context, prompt_repository=repo)
    
    result = await gateway.execute_capability(
        capability=capability,
        parameters=template_context,
        session=mock_session
    )
    
    # Проверяем результат выполнения
    assert result.status.name == "SUCCESS"
    assert result.summary == "Capability 'code_analyzer' executed successfully"
    
    # 7. Проверяем, что метрики использования обновились
    updated_sys_version = await repo.get_version_by_id("sys_v1_0_0")
    updated_usr_version = await repo.get_version_by_id("usr_v1_0_0")
    
    # Проверяем, что метрики были обновлены (по крайней мере, last_used_at должен быть установлен)
    assert updated_sys_version.usage_metrics is not None
    assert updated_usr_version.usage_metrics is not None


@pytest.mark.asyncio
async def test_prompt_version_creation_and_storage():
    """Тест создания и хранения версий промтов"""
    repo = InMemoryPromptRepository()
    
    # Создаем несколько версий для одного capability
    version_1 = PromptVersion(
        id="ver_1_0_0",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Initial prompt version",
        variables_schema=[],
        status="active"
    )
    
    version_2 = PromptVersion(
        id="ver_1_1_0",
        semantic_version="1.1.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Improved prompt version with {{variable}}",
        variables_schema=[
            {"name": "variable", "type": "string", "required": True, "description": "A test variable"}
        ],
        status="draft"
    )
    
    # Сохраняем обе версии
    await repo.save_version(version_1)
    await repo.save_version(version_2)
    
    # Проверяем, что обе версии сохранены
    retrieved_1 = await repo.get_version_by_id("ver_1_0_0")
    retrieved_2 = await repo.get_version_by_id("ver_1_1_0")
    
    assert retrieved_1 is not None
    assert retrieved_2 is not None
    assert retrieved_1.content == "Initial prompt version"
    assert retrieved_2.content == "Improved prompt version with {{variable}}"
    
    # Проверяем, что активна только первая версия
    active_version = await repo.get_active_version(
        domain="code_generation",
        capability_name="test_capability",
        provider_type="openai",
        role="system"
    )
    
    assert active_version.id == "ver_1_0_0"


@pytest.mark.asyncio
async def test_prompt_version_metric_aggregation():
    """Тест агрегации метрик использования версий промтов"""
    repo = InMemoryPromptRepository()
    
    # Создаем версию
    version = PromptVersion(
        id="metric_test_version",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="metric_test",
        role=PromptRole.USER,
        content="Test prompt for metrics",
        status="active"
    )
    
    await repo.save_version(version)
    
    # Обновляем метрики несколько раз
    for i in range(3):
        metrics_update = PromptUsageMetrics(
            usage_count=1,
            success_count=1 if i < 2 else 0,  # Последний вызов будет неуспешным
            avg_generation_time=0.5 + i * 0.1,
            last_used_at=datetime.utcnow(),
            error_rate=0.0 if i < 2 else 1.0
        )
        await repo.update_usage_metrics("metric_test_version", metrics_update)
    
    # Проверяем итоговые метрики
    updated_version = await repo.get_version_by_id("metric_test_version")
    metrics = updated_version.usage_metrics
    
    assert metrics.usage_count == 3
    assert metrics.success_count == 2  # 2 успешных из 3
    assert metrics.error_rate == 1.0/3.0  # 1 ошибка из 3


@pytest.mark.asyncio
async def test_prompt_version_role_separation():
    """Тест разделения версий по ролям"""
    repo = InMemoryPromptRepository()
    
    # Создаем версии для разных ролей
    system_version = PromptVersion(
        id="sys_role_test",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="role_test",
        role=PromptRole.SYSTEM,
        content="System prompt",
        status="active"
    )
    
    user_version = PromptVersion(
        id="usr_role_test",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="role_test",
        role=PromptRole.USER,
        content="User prompt",
        status="active"
    )
    
    await repo.save_version(system_version)
    await repo.save_version(user_version)
    
    # Проверяем, что можно получить активные версии для каждой роли отдельно
    active_system = await repo.get_active_version(
        domain="code_generation",
        capability_name="role_test",
        provider_type="openai",
        role="system"
    )
    
    active_user = await repo.get_active_version(
        domain="code_generation",
        capability_name="role_test",
        provider_type="openai",
        role="user"
    )
    
    assert active_system.id == "sys_role_test"
    assert active_user.id == "usr_role_test"
    assert active_system.role == PromptRole.SYSTEM
    assert active_user.role == PromptRole.USER


@pytest.mark.asyncio
async def test_prompt_version_provider_separation():
    """Тест разделения версий по провайдерам"""
    repo = InMemoryPromptRepository()
    
    # Создаем версии для разных провайдеров
    openai_version = PromptVersion(
        id="openai_provider_test",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="provider_test",
        role=PromptRole.SYSTEM,
        content="OpenAI specific prompt",
        status="active"
    )
    
    anthropic_version = PromptVersion(
        id="anthropic_provider_test",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.ANTHROPIC,
        capability_name="provider_test",
        role=PromptRole.SYSTEM,
        content="Anthropic specific prompt",
        status="active"
    )
    
    await repo.save_version(openai_version)
    await repo.save_version(anthropic_version)
    
    # Проверяем, что можно получить активные версии для каждого провайдера
    active_openai = await repo.get_active_version(
        domain="code_generation",
        capability_name="provider_test",
        provider_type="openai",
        role="system"
    )
    
    active_anthropic = await repo.get_active_version(
        domain="code_generation",
        capability_name="provider_test",
        provider_type="anthropic",
        role="system"
    )
    
    assert active_openai.id == "openai_provider_test"
    assert active_anthropic.id == "anthropic_provider_test"
    assert active_openai.provider_type == LLMProviderType.OPENAI
    assert active_anthropic.provider_type == LLMProviderType.ANTHROPIC
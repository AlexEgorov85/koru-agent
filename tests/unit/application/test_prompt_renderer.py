import pytest
from unittest.mock import Mock, AsyncMock
from domain.models.capability import Capability
from domain.models.prompt.prompt_version import PromptVersion, PromptRole, VariableSchema
from application.services.prompt_renderer import PromptRenderer
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType


@pytest.fixture
def mock_prompt_repository():
    """Фикстура для mock репозитория промтов"""
    repo = Mock()
    repo.get_version_by_id = AsyncMock()
    return repo


@pytest.fixture
def sample_capability():
    """Фикстура для тестового capability"""
    return Capability(
        name="test_capability",
        description="Test capability",
        skill_name="test_skill",
        prompt_versions={
            "openai:system": "system_version_123",
            "openai:user": "user_version_456"
        }
    )


@pytest.mark.asyncio
async def test_prompt_renderer_render_for_request(mock_prompt_repository, sample_capability):
    """Тест рендеринга промтов для запроса"""
    # Подготовка mock версий промтов
    system_version = PromptVersion(
        id="system_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="You are a {{role}} assistant for {{task_type}}.",
        variables_schema=[
            VariableSchema(name="role", type="string", required=True, description="Role for the assistant"),
            VariableSchema(name="task_type", type="string", required=True, description="Type of task")
        ]
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
            VariableSchema(name="code", type="string", required=True, description="Code to analyze")
        ]
    )
    
    # Настройка mock
    async def mock_get_version_by_id(version_id):
        if version_id == "system_version_123":
            return system_version
        elif version_id == "user_version_456":
            return user_version
        return None
    
    mock_prompt_repository.get_version_by_id.side_effect = mock_get_version_by_id
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст для подстановки переменных
    template_context = {
        "role": "coding",
        "task_type": "code analysis",
        "code": "print('Hello, world!')"
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=sample_capability,
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результатов
    assert PromptRole.SYSTEM in result
    assert PromptRole.USER in result
    
    expected_system_content = "You are a coding assistant for code analysis."
    expected_user_content = "Please analyze this code: print('Hello, world!')"
    
    assert result[PromptRole.SYSTEM] == expected_system_content
    assert result[PromptRole.USER] == expected_user_content


@pytest.mark.asyncio
async def test_prompt_renderer_missing_version(mock_prompt_repository, sample_capability):
    """Тест обработки отсутствующих версий промтов"""
    # Настройка mock - возвращаем None для одной из версий
    async def mock_get_version_by_id(version_id):
        if version_id == "system_version_123":
            return None  # Нет системного промта
        return None
    
    mock_prompt_repository.get_version_by_id.side_effect = mock_get_version_by_id
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Вызов метода
    result, errors  = await renderer.render_for_request(
        capability=sample_capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={},
        session_id="test_session_123"
    )
    
    # Проверка результатов - должно быть пустым
    assert len(result) == 0


@pytest.mark.asyncio
async def test_prompt_renderer_no_matching_versions(mock_prompt_repository, sample_capability):
    """Тест обработки случая, когда нет соответствующих версий для провайдера"""
    # У capability другие версии промтов
    different_capability = Capability(
        name="test_capability",
        description="Test capability",
        skill_name="test_skill",
        prompt_versions={
            "anthropic:system": "system_version_789"
        }
    )
    
    # Настройка mock
    version = PromptVersion(
        id="system_version_789",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.ANTHROPIC,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="You are an assistant.",
        template_variables=[]
    )
    
    async def mock_get_version_by_id(version_id):
        if version_id == "system_version_789":
            return version
        return None
    
    mock_prompt_repository.get_version_by_id.side_effect = mock_get_version_by_id
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Вызов метода - ищем версии для OPENAI, но у capability только для ANTHROPIC
    result, errors  = await renderer.render_for_request(
        capability=different_capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={},
        session_id="test_session_456"
    )
    
    # Проверка результатов - должно быть пустым
    assert len(result) == 0


@pytest.mark.asyncio
async def test_prompt_renderer_variable_substitution(mock_prompt_repository, sample_capability):
    """Тест подстановки переменных в шаблон"""
    # Подготовка версии с несколькими переменными
    version = PromptVersion(
        id="system_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="{{greeting}}, you are a {{role}} assistant. Handle {{task_type}} tasks.",
        variables_schema=[
            VariableSchema(name="greeting", type="string", required=True, description="Greeting for the assistant"),
            VariableSchema(name="role", type="string", required=True, description="Role for the assistant"),
            VariableSchema(name="task_type", type="string", required=True, description="Type of task")
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст с переменными для подстановки
    template_context = {
        "greeting": "Hello",
        "role": "coding",
        "task_type": "debugging",
        "extra_var": "should_not_be_used"  # Эта переменная не используется
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=sample_capability,
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результата
    expected_content = "Hello, you are a coding assistant. Handle debugging tasks."
    assert result[PromptRole.SYSTEM] == expected_content
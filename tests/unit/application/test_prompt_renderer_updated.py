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
async def test_prompt_renderer_render_for_request_with_validation(mock_prompt_repository, sample_capability):
    """Тест рендеринга промтов для запроса с валидацией переменных"""
    # Подготовка mock версий промтов с новой схемой переменных
    system_version = PromptVersion(
        id="system_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="You are a {{role}} assistant for {{task_type}}.",
        variables_schema=[
            VariableSchema(name="role", type="string", required=True),
            VariableSchema(name="task_type", type="string", required=True)
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
            VariableSchema(name="code", type="string", required=True)
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
    assert len(errors) == 0  # Нет ошибок валидации
    
    expected_system_content = "You are a coding assistant for code analysis."
    expected_user_content = "Please analyze this code: print('Hello, world!')"
    
    assert result[PromptRole.SYSTEM] == expected_system_content
    assert result[PromptRole.USER] == expected_user_content


@pytest.mark.asyncio
async def test_prompt_renderer_render_with_validation_errors(mock_prompt_repository, sample_capability):
    """Тест рендеринга промтов с ошибками валидации"""
    # Подготовка mock версии промта с обязательной переменной
    system_version = PromptVersion(
        id="system_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="You are a {{role}} assistant for {{task_type}}.",
        variables_schema=[
            VariableSchema(name="role", type="string", required=True),
            VariableSchema(name="task_type", type="string", required=True)
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = system_version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст без обязательной переменной
    template_context = {
        "role": "coding"
        # task_type отсутствует
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=sample_capability,
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результатов - должны быть ошибки валидации
    assert len(errors) > 0
    assert "task_type" in str(errors[0])  # Ошибка должна содержать имя отсутствующей переменной
    assert len(result) == 0  # Нет отрендеренного содержимого из-за ошибок


@pytest.mark.asyncio
async def test_prompt_renderer_render_with_type_validation(mock_prompt_repository, sample_capability):
    """Тест рендеринга промтов с валидацией типов переменных"""
    # Подготовка mock версии промта с переменной типа integer
    system_version = PromptVersion(
        id="system_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Process {{count}} items.",
        variables_schema=[
            VariableSchema(name="count", type="integer", required=True)
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = system_version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст с переменной неправильного типа
    template_context = {
        "count": "not_an_integer"  # Должно быть целое число, а не строка
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=sample_capability,
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результатов - должны быть ошибки валидации типа
    assert len(errors) > 0
    assert "целое число" in str(errors[0])  # Ошибка должна указывать на тип
    assert "str" in str(errors[0])   # Ошибка должна указывать на фактический тип
    assert len(result) == 0  # Нет отрендеренного содержимого из-за ошибок


@pytest.mark.asyncio
async def test_prompt_renderer_render_with_correct_types(mock_prompt_repository, sample_capability):
    """Тест рендеринга промтов с правильными типами переменных"""
    # Подготовка mock версии промта с переменной типа integer
    system_version = PromptVersion(
        id="system_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Process {{count}} items.",
        variables_schema=[
            VariableSchema(name="count", type="integer", required=True)
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = system_version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст с переменной правильного типа
    template_context = {
        "count": 42  # Целое число, как и ожидалось
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=sample_capability,
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результатов - не должно быть ошибок
    assert len(errors) == 0
    assert len(result) == 2
    assert result[PromptRole.SYSTEM] == "Process 42 items."


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
    result, errors = await renderer.render_for_request(
        capability=sample_capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={},
        session_id="test_session_123"
    )
    
    # Проверка результатов - должны быть ошибки
    assert len(errors) > 0
    assert "не найдена" in str(errors[0]).lower()
    assert len(result) == 0


@pytest.mark.asyncio
async def test_prompt_renderer_variable_substitution(mock_prompt_repository, sample_capability):
    """Тест подстановки переменных в шаблон с новой системой"""
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
            VariableSchema(name="greeting", type="string", required=True),
            VariableSchema(name="role", type="string", required=True),
            VariableSchema(name="task_type", type="string", required=True)
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
    
    # Проверка результатов
    assert len(errors) == 0
    expected_content = "Hello, you are a coding assistant. Handle debugging tasks."
    assert result[PromptRole.SYSTEM] == expected_content
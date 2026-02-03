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
    repo.get_version_by_id = AsyncMock(return_value=None)  # Явно указываем возвращаемое значение по умолчанию
    return repo


@pytest.mark.asyncio
async def test_prompt_renderer_safe_variable_substitution(mock_prompt_repository):
    """Тест безопасной подстановки переменных (защита от инъекций)"""
    # Подготовка версии с переменными
    version = PromptVersion(
        id="security_test_version",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Process this: {{user_input}} and {{safe_var}}",
        variables_schema=[
            VariableSchema(name="user_input", type="string", required=True),
            VariableSchema(name="safe_var", type="string", required=True)
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст с потенциально опасными данными
    template_context = {
        "user_input": "{{__import__('os').system('rm -rf /')}}",  # Попытка инъекции
        "safe_var": "normal_value",
        "__import__": "blocked",  # Попытка обхода безопасности
        "exec": "also_blocked"
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=Capability(
            name="test_capability",
            description="Test capability",
            skill_name="test_skill",
            prompt_versions={
                "openai:system": "security_test_version"
            }
        ),
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результата - инъекции не должны выполниться
    expected_content = "Process this: {{__import__('os').system('rm -rf /')}} and normal_value"
    assert result[PromptRole.SYSTEM] == expected_content


@pytest.mark.asyncio
async def test_prompt_renderer_only_exact_variable_matches(mock_prompt_repository):
    """Тест, что подстановка происходит только для точных совпадений переменных"""
    # Подготовка версии с переменной
    version = PromptVersion(
        id="exact_match_test_version",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Variable: {{target_var}}, Similar: {{target_var_extra}}, Prefix: pre_target_var}}",
        variables_schema=[
            VariableSchema(name="target_var", type="string", required=True)
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст с переменными
    template_context = {
        "target_var": "REPLACED_VALUE",
        "target_var_extra": "SHOULD_NOT_REPLACE"  # Эта не должна замениться
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=Capability(
            name="test_capability",
            description="Test capability",
            skill_name="test_skill",
            prompt_versions={
                "openai:system": "exact_match_test_version"
            }
        ),
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результата - заменится только точное совпадение
    expected_content = "Variable: REPLACED_VALUE, Similar: {{target_var_extra}}, Prefix: pre_target_var}}"
    assert result[PromptRole.SYSTEM] == expected_content


@pytest.mark.asyncio
async def test_prompt_renderer_handles_special_characters(mock_prompt_repository):
    """Тест обработки специальных символов в переменных"""
    # Подготовка версии с переменной
    version = PromptVersion(
        id="special_chars_test_version",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.USER,
        content="Code: {{code_snippet}}",
        variables_schema=[
            VariableSchema(name="code_snippet", type="string", required=True)
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст со специальными символами
    template_context = {
        "code_snippet": 'console.log("Hello\nWorld\t!"); // Comment with "quotes"'
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=Capability(
            name="test_capability",
            description="Test capability",
            skill_name="test_skill",
            prompt_versions={
                "openai:user": "special_chars_test_version"
            }
        ),
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результата
    expected_content = 'Code: console.log("Hello\nWorld\t!"); // Comment with "quotes"'
    assert result[PromptRole.USER] == expected_content


@pytest.mark.asyncio
async def test_prompt_renderer_missing_variables_unchanged(mock_prompt_repository):
    """Тест, что отсутствующие переменные остаются без изменений"""
    # Подготовка версии с переменными
    version = PromptVersion(
        id="missing_vars_test_version",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Present: {{present_var}}, Missing: {{missing_var}}, Also missing: {{another_missing}}",
        variables_schema=[
            VariableSchema(name="present_var", type="string", required=True),
            VariableSchema(name="missing_var", type="string", required=False)
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст с частичными переменными
    template_context = {
        "present_var": "REPLACED_VALUE"
        # missing_var и another_missing отсутствуют
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=Capability(
            name="test_capability",
            description="Test capability",
            skill_name="test_skill",
            prompt_versions={
                "openai:system": "missing_vars_test_version"
            }
        ),
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результата - должны замениться только существующие переменные
    expected_content = "Present: REPLACED_VALUE, Missing: {{missing_var}}, Also missing: {{another_missing}}"
    assert result[PromptRole.SYSTEM] == expected_content


@pytest.mark.asyncio
async def test_prompt_renderer_multiple_occurrences_same_variable(mock_prompt_repository):
    """Тест, что все вхождения одной переменной заменяются"""
    # Подготовка версии с повторяющейся переменной
    version = PromptVersion(
        id="multiple_occurrences_test_version",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.USER,
        content="First: {{repeated_var}}, Second: {{repeated_var}}, Third: {{repeated_var}}",
        variables_schema=[
            VariableSchema(name="repeated_var", type="string", required=True)
        ]
    )
    
    # Настройка mock
    mock_prompt_repository.get_version_by_id.return_value = version
    
    # Создание рендерера
    renderer = PromptRenderer(mock_prompt_repository)
    
    # Контекст с переменной
    template_context = {
        "repeated_var": "REPEATED_VALUE"
    }
    
    # Вызов метода
    result, errors = await renderer.render_for_request(
        capability=Capability(
            name="test_capability",
            description="Test capability",
            skill_name="test_skill",
            prompt_versions={
                "openai:user": "multiple_occurrences_test_version"
            }
        ),
        provider_type=LLMProviderType.OPENAI,
        template_context=template_context,
        session_id="test_session_123"
    )
    
    # Проверка результата - все вхождения должны быть заменены
    expected_content = "First: REPEATED_VALUE, Second: REPEATED_VALUE, Third: REPEATED_VALUE"
    assert result[PromptRole.USER] == expected_content
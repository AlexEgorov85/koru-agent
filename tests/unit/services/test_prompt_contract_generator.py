"""
Юнит-тесты для PromptContractGenerator.

ТЕСТЫ:
- test_generate_prompt_variant: генерация варианта промпта
- test_save_prompt_to_filesystem: сохранение промпта
- test_generate_contract: генерация контракта
"""
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.data.prompt import Prompt
from core.models.data.contract import Contract
from core.models.data.benchmark import FailureAnalysis, EvaluationType, EvaluationCriterion
from core.application.services.prompt_contract_generator import (
    PromptContractGenerator,
    GenerationConfig,
)
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource


@pytest.fixture
def mock_llm_provider():
    """Моковый LLM провайдер"""
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value="Generated content")
    return provider


@pytest.fixture
def mock_data_source():
    """Моковый FileSystemDataSource"""
    source = AsyncMock(spec=FileSystemDataSource)
    source.save_prompt = AsyncMock(return_value=True)
    source.save_contract = AsyncMock(return_value=True)
    source.load_prompt = AsyncMock()
    return source


@pytest.fixture
def temp_data_dir(tmp_path):
    """Временная директория для данных"""
    return tmp_path / "data"


@pytest.fixture
def generator(mock_llm_provider, mock_data_source, temp_data_dir):
    """PromptContractGenerator для тестов"""
    return PromptContractGenerator(
        llm_provider=mock_llm_provider,
        data_source=mock_data_source,
        data_dir=temp_data_dir,
        config=GenerationConfig(temperature=0.7)
    )


@pytest.fixture
def sample_prompt():
    """Тестовый промпт"""
    from core.models.enums.common_enums import ComponentType
    
    return Prompt(
        capability='test.capability',
        version='v1.0.0',
        content='Original prompt content with at least 20 characters',
        variables=[],
        status='active',
        component_type=ComponentType.SKILL,
        metadata={'test': 'value'}
    )


@pytest.fixture
def sample_failure_analysis():
    """Тестовый анализ неудач"""
    analysis = FailureAnalysis(
        capability='test.capability',
        version='v1.0.0',
        total_failures=10
    )
    analysis.add_failure_category('syntax_error', 5)
    analysis.add_failure_category('logic_error', 3)
    analysis.add_failure_category('timeout', 2)
    analysis.add_recommendation('Improve input validation')
    analysis.add_recommendation('Add error handling')
    return analysis


class TestGeneratePromptVariant:
    """Тесты generate_prompt_variant"""

    @pytest.mark.asyncio
    async def test_generate_prompt_variant(self, generator, sample_prompt, sample_failure_analysis):
        """Тест генерации варианта промпта"""
        # Мокаем LLM ответ
        generator.llm_provider.generate = AsyncMock(return_value="New improved prompt content")

        new_prompt = await generator.generate_prompt_variant(
            sample_prompt,
            sample_failure_analysis,
            target_improvement='Better error handling'
        )

        assert new_prompt is not None
        assert new_prompt.capability == sample_prompt.capability
        assert new_prompt.version != sample_prompt.version  # Версия должна измениться
        assert new_prompt.metadata['generated_from'] == sample_prompt.version
        assert new_prompt.metadata['target_improvement'] == 'Better error handling'

    @pytest.mark.asyncio
    async def test_generate_prompt_variant_without_target(self, generator, sample_prompt, sample_failure_analysis):
        """Тест генерации без целевого улучшения"""
        generator.llm_provider.generate = AsyncMock(return_value="New content")

        new_prompt = await generator.generate_prompt_variant(
            sample_prompt,
            sample_failure_analysis
        )

        assert new_prompt is not None
        assert 'target_improvement' in new_prompt.metadata

    @pytest.mark.asyncio
    async def test_generate_prompt_variant_llm_error(self, generator, sample_prompt, sample_failure_analysis):
        """Тест ошибки LLM"""
        generator.llm_provider.generate = AsyncMock(side_effect=Exception("LLM error"))

        with pytest.raises(Exception):
            await generator.generate_prompt_variant(sample_prompt, sample_failure_analysis)


class TestGenerateFromScratch:
    """Тесты generate_from_scratch"""

    @pytest.mark.asyncio
    async def test_generate_from_scratch(self, generator):
        """Тест генерации с нуля"""
        generator.llm_provider.generate = AsyncMock(return_value="New prompt from scratch")

        new_prompt = await generator.generate_from_scratch(
            capability='new.capability',
            description='This is a new capability'
        )

        assert new_prompt is not None
        assert new_prompt.capability == 'new.capability'
        assert new_prompt.version == 'v1.0.0'
        assert new_prompt.metadata['generated_from_scratch'] == 'true'

    @pytest.mark.asyncio
    async def test_generate_from_scratch_with_examples(self, generator):
        """Тест генерации с примерами"""
        generator.llm_provider.generate = AsyncMock(return_value="Prompt with examples")

        new_prompt = await generator.generate_from_scratch(
            capability='example.capability',
            description='Test',
            examples=['Example 1', 'Example 2']
        )

        assert new_prompt is not None
        assert new_prompt.capability == 'example.capability'


class TestGenerateMatchingContract:
    """Тесты generate_matching_contract"""

    @pytest.mark.asyncio
    async def test_generate_contract(self, generator, sample_prompt):
        """Тест генерации контракта"""
        # Мокаем валидный JSON ответ
        schema_json = {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }
        generator.llm_provider.generate = AsyncMock(return_value=json.dumps(schema_json))

        contract = await generator.generate_matching_contract(sample_prompt)

        assert contract is not None
        assert contract.capability == sample_prompt.capability
        assert contract.version == sample_prompt.version
        assert contract.input_schema == schema_json

    @pytest.mark.asyncio
    async def test_generate_contract_invalid_json(self, generator, sample_prompt):
        """Тест генерации контракта с невалидным JSON"""
        # Возвращаем невалидный JSON
        generator.llm_provider.generate = AsyncMock(return_value="This is not JSON")

        contract = await generator.generate_matching_contract(sample_prompt)

        # Должна вернуться дефолтная схема
        assert contract is not None
        assert contract.input_schema is not None

    @pytest.mark.asyncio
    async def test_generate_contract_partial_json(self, generator, sample_prompt):
        """Тест генерации контракта с частичным JSON"""
        # JSON с лишним текстом
        schema_json = {"type": "object", "properties": {"test": {"type": "string"}}}
        generator.llm_provider.generate = AsyncMock(
            return_value=f"Here is the schema:\n{json.dumps(schema_json)}\nHope it helps!"
        )

        contract = await generator.generate_matching_contract(sample_prompt)

        assert contract is not None
        assert contract.input_schema == schema_json


class TestSavePrompt:
    """Тесты save_prompt"""

    @pytest.mark.asyncio
    async def test_save_prompt_to_filesystem(self, generator, sample_prompt):
        """Тест сохранения промпта"""
        result = await generator.save_prompt(sample_prompt)

        assert result is True
        generator.data_source.save_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_prompt_error(self, generator, sample_prompt):
        """Тест ошибки сохранения"""
        generator.data_source.save_prompt = AsyncMock(side_effect=Exception("Save error"))

        result = await generator.save_prompt(sample_prompt)

        assert result is False


class TestSaveContract:
    """Тесты save_contract"""

    @pytest.mark.asyncio
    async def test_save_contract(self, generator, sample_prompt):
        """Тест сохранения контракта"""
        contract = Contract(
            capability=sample_prompt.capability,
            version=sample_prompt.version,
            input_schema={"type": "object"}
        )

        result = await generator.save_contract(contract)

        assert result is True
        generator.data_source.save_contract.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_contract_error(self, generator, sample_prompt):
        """Тест ошибки сохранения контракта"""
        generator.data_source.save_contract = AsyncMock(side_effect=Exception("Save error"))

        contract = Contract(
            capability=sample_prompt.capability,
            version=sample_prompt.version,
            input_schema={"type": "object"}
        )

        result = await generator.save_contract(contract)

        assert result is False


class TestGenerateAndSave:
    """Тесты generate_and_save"""

    @pytest.mark.asyncio
    async def test_generate_and_save_success(self, generator, sample_prompt, sample_failure_analysis):
        """Тест успешной генерации и сохранения"""
        generator.llm_provider.generate = AsyncMock(side_effect=[
            "New prompt content",  # Для промпта
            json.dumps({"type": "object"})  # Для контракта
        ])

        new_prompt, contract = await generator.generate_and_save(
            sample_prompt,
            sample_failure_analysis
        )

        assert new_prompt is not None
        assert contract is not None

    @pytest.mark.asyncio
    async def test_generate_and_save_prompt_error(self, generator, sample_prompt, sample_failure_analysis):
        """Тест ошибки сохранения промпта"""
        generator.llm_provider.generate = AsyncMock(return_value="New prompt")
        generator.data_source.save_prompt = AsyncMock(return_value=False)

        new_prompt, contract = await generator.generate_and_save(
            sample_prompt,
            sample_failure_analysis
        )

        assert new_prompt is None
        assert contract is None

    @pytest.mark.asyncio
    async def test_generate_and_save_contract_error(self, generator, sample_prompt, sample_failure_analysis):
        """Тест ошибки сохранения контракта"""
        generator.llm_provider.generate = AsyncMock(side_effect=[
            "New prompt content",
            json.dumps({"type": "object"})
        ])
        generator.data_source.save_prompt = AsyncMock(return_value=True)
        generator.data_source.save_contract = AsyncMock(return_value=False)

        new_prompt, contract = await generator.generate_and_save(
            sample_prompt,
            sample_failure_analysis
        )

        assert new_prompt is not None
        assert contract is None


class TestVersionIncrement:
    """Тесты инкремента версии"""

    def test_increment_version_patch(self, generator):
        """Тест инкремента patch версии"""
        new_version = generator._increment_version('v1.0.0')
        assert new_version == 'v1.0.1'

    def test_increment_version_minor(self, generator):
        """Тест инкремента minor версии"""
        new_version = generator._increment_version('v1.0.9')
        assert new_version == 'v1.0.10'

    def test_increment_version_invalid(self, generator):
        """Тест невалидной версии"""
        new_version = generator._increment_version('invalid')
        assert new_version == 'v1.0.0'

    def test_increment_version_no_v_prefix(self, generator):
        """Тест версии без префикса v"""
        new_version = generator._increment_version('1.0.0')
        assert new_version == 'v1.0.1'


class TestGenerationHistory:
    """Тесты истории генераций"""

    @pytest.mark.asyncio
    async def test_generation_history_recorded(self, generator, sample_prompt, sample_failure_analysis):
        """Тест записи в историю"""
        generator.llm_provider.generate = AsyncMock(return_value="New content")

        await generator.generate_prompt_variant(sample_prompt, sample_failure_analysis)

        history = generator.get_generation_history()
        assert len(history) >= 1
        assert history[-1]['type'] == 'prompt'
        assert history[-1]['from_version'] == sample_prompt.version

    def test_generation_history_copy(self, generator):
        """Тест что история возвращается копией"""
        history1 = generator.get_generation_history()
        history2 = generator.get_generation_history()

        # Это должны быть разные объекты
        assert history1 is not history2


class TestRollback:
    """Тесты отката версии"""

    @pytest.mark.asyncio
    async def test_rollback_to_version(self, generator):
        """Тест отката к версии"""
        from core.models.enums.common_enums import ComponentType
        
        generator.data_source.load_prompt = AsyncMock(
            return_value=Prompt(
                capability='test',
                version='v1.0.0',
                content='Test content with enough characters',
                status='active',
                component_type=ComponentType.SKILL
            )
        )

        result = await generator.rollback_to_version('test.capability', 'v1.0.0')

        assert result is True
        generator.data_source.load_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_to_version_error(self, generator):
        """Тест ошибки отката"""
        generator.data_source.load_prompt = AsyncMock(side_effect=Exception("Not found"))

        result = await generator.rollback_to_version('test.capability', 'v1.0.0')

        assert result is False


class TestGenerationConfig:
    """Тесты конфигурации генерации"""

    def test_default_config(self):
        """Тест конфигурации по умолчанию"""
        config = GenerationConfig()

        assert config.temperature == 0.7
        assert config.max_tokens == 4000
        assert config.top_p == 0.9
        assert config.include_examples is True
        assert config.preserve_structure is True

    def test_custom_config(self):
        """Тест custom конфигурации"""
        config = GenerationConfig(
            temperature=0.5,
            max_tokens=2000,
            include_examples=False
        )

        assert config.temperature == 0.5
        assert config.max_tokens == 2000
        assert config.include_examples is False


class TestBuildPrompts:
    """Тесты формирования промптов"""

    def test_build_generation_prompt(self, generator, sample_prompt, sample_failure_analysis):
        """Тест формирования промпта для генерации"""
        prompt = generator._build_generation_prompt(
            sample_prompt,
            sample_failure_analysis,
            'Better performance'
        )

        assert 'ОРИГИНАЛЬНЫЙ ПРОМПТ' in prompt
        assert 'АНАЛИЗ НЕУДАЧ' in prompt
        assert 'syntax_error' in prompt
        assert 'Better performance' in prompt

    def test_build_schema_prompt(self, generator, sample_prompt):
        """Тест формирования промпта для схемы"""
        prompt = generator._build_schema_prompt(sample_prompt)

        assert 'JSON Schema' in prompt
        assert sample_prompt.content[:100] in prompt

    def test_build_scratch_prompt(self, generator):
        """Тест формирования промпта с нуля"""
        prompt = generator._build_scratch_prompt(
            'test.capability',
            'Test description',
            ['Example 1']
        )

        assert 'test.capability' in prompt
        assert 'Test description' in prompt
        assert 'Example 1' in prompt


class TestDefaultSchemas:
    """Тесты дефолтных схем"""

    def test_create_default_schema(self, generator, sample_prompt):
        """Тест создания дефолтной схемы"""
        schema = generator._create_default_schema(sample_prompt)

        assert schema['type'] == 'object'
        assert 'input' in schema['properties']
        assert 'input' in schema['required']

    def test_create_output_schema(self, generator):
        """Тест создания схемы вывода"""
        schema = generator._create_output_schema()

        assert schema['type'] == 'object'
        assert 'output' in schema['properties']
        assert 'output' in schema['required']

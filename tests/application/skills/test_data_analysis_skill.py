"""
Unit-тесты для DataAnalysisSkill.

Тестирует:
- Загрузку данных из различных источников
- Чанкинг больших данных
- Парсинг LLM-ответов
- Валидацию входных/выходных данных
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Dict, Any

from core.application.skills.data_analysis.skill import DataAnalysisSkill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.common_enums import ErrorCategory


@pytest.fixture
def mock_application_context():
    """Фикстура мокированного ApplicationContext."""
    mock_ctx = MagicMock()
    
    # Мокируем LLM провайдер
    mock_llm_provider = AsyncMock()
    mock_ctx.get_llm_provider = MagicMock(return_value=mock_llm_provider)
    
    # Мокируем реестр компонентов
    mock_components = MagicMock()
    mock_components.get = MagicMock(return_value=None)
    mock_ctx.components = mock_components
    
    # Мокируем инфраструктурный контекст
    mock_infra = MagicMock()
    mock_ctx.infrastructure_context = mock_infra
    
    return mock_ctx


@pytest.fixture
def mock_component_config():
    """Фикстура мокированной ComponentConfig."""
    mock_config = MagicMock()
    mock_config.prompt_versions = {"data_analysis.analyze_step_data": "v1.0.0"}
    mock_config.input_contract_versions = {"data_analysis.analyze_step_data": "v1.0.0"}
    mock_config.output_contract_versions = {"data_analysis.analyze_step_data": "v1.0.0"}
    mock_config.side_effects_enabled = True
    mock_config.detailed_metrics = False
    mock_config.parameters = {}
    return mock_config


@pytest.fixture
def mock_executor():
    """Фикстура мокированного ActionExecutor."""
    return MagicMock()


@pytest.fixture
def data_analysis_skill(mock_application_context, mock_component_config, mock_executor):
    """Фикстура для создания навыка."""
    skill = DataAnalysisSkill(
        name="data_analysis",
        application_context=mock_application_context,
        component_config=mock_component_config,
        executor=mock_executor
    )
    
    # Инициализация кэшей (в реальности через initialize())
    skill.prompts = {"data_analysis.analyze_step_data": MagicMock(content="mock prompt")}
    skill.input_schemas = {"data_analysis.analyze_step_data": MagicMock()}
    skill.output_schemas = {"data_analysis.analyze_step_data": MagicMock()}
    skill._initialized = True
    
    return skill


@pytest.mark.asyncio
async def test_get_capabilities(data_analysis_skill):
    """Тест получения списка capability."""
    capabilities = data_analysis_skill.get_capabilities()
    
    assert len(capabilities) == 1
    assert capabilities[0].name == "data_analysis.analyze_step_data"
    assert capabilities[0].skill_name == "data_analysis"
    assert capabilities[0].meta["supports_chunking"] is True
    assert "summary" in capabilities[0].meta["aggregation_methods"]


@pytest.mark.asyncio
async def test_execute_small_data(data_analysis_skill):
    """Тест анализа небольших данных."""
    # Мокируем LLM провайдер
    mock_llm_response = MagicMock()
    mock_llm_response.content = '{"answer": "2 записи", "confidence": 0.95, "evidence": []}'
    mock_llm_response.tokens_used = 150
    
    mock_llm_provider = AsyncMock()
    mock_llm_provider.generate = AsyncMock(return_value=mock_llm_response)
    data_analysis_skill.application_context.get_llm_provider = MagicMock(return_value=mock_llm_provider)
    
    capability = Capability(
        name="data_analysis.analyze_step_data",
        description="Test",
        skill_name="data_analysis"
    )
    
    parameters = {
        "step_id": "step_123",
        "question": "Сколько записей в данных?",
        "data_source": {
            "type": "memory",
            "content": "id,name,value\n1,test,100\n2,demo,200"
        }
    }
    
    execution_context = MagicMock()
    
    result = await data_analysis_skill.execute(capability, parameters, execution_context)
    
    assert result.status == ExecutionStatus.COMPLETED
    assert result.result["answer"] == "2 записи"
    assert result.result["confidence"] == 0.95
    assert result.metadata["chunks_processed"] == 1


@pytest.mark.asyncio
async def test_execute_large_data_chunking(data_analysis_skill):
    """Тест анализа больших данных с чанкингом."""
    # Генерируем большие данные
    large_data = "\n".join([f"row_{i},value_{i}" for i in range(10000)])
    
    # Мокируем LLM провайдер
    mock_llm_response = MagicMock()
    mock_llm_response.content = '{"answer": "Среднее: 5000", "confidence": 0.88}'
    mock_llm_response.tokens_used = 800
    
    mock_llm_provider = AsyncMock()
    mock_llm_provider.generate = AsyncMock(return_value=mock_llm_response)
    data_analysis_skill.application_context.get_llm_provider = MagicMock(return_value=mock_llm_provider)
    
    capability = Capability(
        name="data_analysis.analyze_step_data",
        description="Test",
        skill_name="data_analysis"
    )
    
    parameters = {
        "step_id": "step_456",
        "question": "Каково среднее значение?",
        "data_source": {"type": "memory", "content": large_data},
        "analysis_config": {
            "chunk_size": 500,
            "aggregation_method": "statistical"
        }
    }
    
    execution_context = MagicMock()
    
    result = await data_analysis_skill.execute(capability, parameters, execution_context)
    
    assert result.status == ExecutionStatus.COMPLETED
    assert result.metadata["chunks_processed"] > 1


@pytest.mark.asyncio
async def test_parse_llm_response_json_block(data_analysis_skill):
    """Тест парсинга JSON из markdown-блока."""
    content = """
    Вот мой анализ:
    ```json
    {
        "answer": "Найдено 5 записей",
        "confidence": 0.9,
        "evidence": []
    }
    ```
    """
    
    result = data_analysis_skill._parse_llm_response(content)
    
    assert result["answer"] == "Найдено 5 записей"
    assert result["confidence"] == 0.9


@pytest.mark.asyncio
async def test_parse_llm_response_plain_json(data_analysis_skill):
    """Тест парсинга простого JSON."""
    content = '{"answer": "Тест", "confidence": 0.7}'
    
    result = data_analysis_skill._parse_llm_response(content)
    
    assert result["answer"] == "Тест"
    assert result["confidence"] == 0.7


@pytest.mark.asyncio
async def test_parse_llm_response_invalid_json(data_analysis_skill):
    """Тест парсинга невалидного JSON."""
    content = "Некорректный ответ без JSON"
    
    result = data_analysis_skill._parse_llm_response(content)
    
    assert result["answer"] == "Некорректный ответ без JSON"
    assert result["confidence"] == 0.5
    assert "parse_error" in result.get("metadata", {})


@pytest.mark.asyncio
async def test_validate_output_valid(data_analysis_skill):
    """Тест валидации корректных выходных данных."""
    data = {
        "answer": "Тестовый ответ",
        "confidence": 0.85,
        "evidence": []
    }
    
    result = data_analysis_skill._validate_output(data, "data_analysis.analyze_step_data")
    
    assert result["answer"] == "Тестовый ответ"
    assert result["confidence"] == 0.85


@pytest.mark.asyncio
async def test_validate_output_confidence_bounds(data_analysis_skill):
    """Тест ограничения confidence в пределах [0, 1]."""
    # Слишком высокое значение
    data_high = {"answer": "Тест", "confidence": 1.5}
    result_high = data_analysis_skill._validate_output(data_high, "data_analysis.analyze_step_data")
    assert result_high["confidence"] == 1.0
    
    # Отрицательное значение
    data_low = {"answer": "Тест", "confidence": -0.5}
    result_low = data_analysis_skill._validate_output(data_low, "data_analysis.analyze_step_data")
    assert result_low["confidence"] == 0.0


@pytest.mark.asyncio
async def test_validate_output_missing_fields(data_analysis_skill):
    """Тест валидации с отсутствующими полями."""
    data = {"answer": "Тест"}  # Отсутствует confidence
    
    with pytest.raises(ValueError) as exc_info:
        data_analysis_skill._validate_output(data, "data_analysis.analyze_step_data")
    
    assert "confidence" in str(exc_info.value)


@pytest.mark.asyncio
async def test_chunk_data_small_data(data_analysis_skill):
    """Тест чанкинга для небольших данных."""
    data = "small data"
    config = {"chunk_size": 2000}
    metadata = {}
    
    result = await data_analysis_skill._chunk_data_if_needed(data, config, metadata)
    
    assert result is None
    assert metadata["chunking_applied"] is False


@pytest.mark.asyncio
async def test_chunk_data_large_data(data_analysis_skill):
    """Тест чанкинга для больших данных."""
    # Генерируем данные > 2000 токенов (~8000 символов)
    data = "\n".join([f"line_{i}" for i in range(3000)])
    config = {"chunk_size": 500, "max_chunks": 50}  # Увеличили max_chunks для соответствия дефолту
    metadata = {}
    
    result = await data_analysis_skill._chunk_data_if_needed(data, config, metadata)
    
    assert result is not None
    assert len(result) > 0
    assert len(result) <= config["max_chunks"]
    assert metadata["chunking_applied"] is True
    assert metadata["chunks_created"] == len(result)


@pytest.mark.asyncio
async def test_render_prompt_simple(data_analysis_skill):
    """Тест простого рендеринга промпта."""
    prompt = "Вопрос: {{ question }}, ID: {{ step_id }}"
    variables = {
        "question": "Тестовый вопрос",
        "step_id": "step_123"
    }
    
    result = data_analysis_skill._render_prompt(prompt, variables)
    
    assert "Тестовый вопрос" in result
    assert "step_123" in result


@pytest.mark.asyncio
async def test_render_prompt_with_chunks(data_analysis_skill):
    """Тест рендеринга промпта с чанками."""
    prompt = "Данные: {{ chunks }}"
    variables = {
        "chunks": [
            {"content": "Чанк 1"},
            {"content": "Чанк 2"}
        ]
    }
    
    result = data_analysis_skill._render_prompt(prompt, variables)
    
    assert "Чанк 1" in result
    assert "Чанк 2" in result
    assert "### Чанк 1" in result
    assert "### Чанк 2" in result


@pytest.mark.asyncio
async def test_load_from_memory(data_analysis_skill):
    """Тест загрузки данных из памяти."""
    data_source = {
        "type": "memory",
        "content": "test,data\n1,2"
    }
    metadata = {}
    
    content, meta = await data_analysis_skill._load_from_memory(data_source, metadata)
    
    assert content == "test,data\n1,2"
    assert meta["size_mb"] > 0


@pytest.mark.asyncio
async def test_load_from_file_invalid_path(data_analysis_skill):
    """Тест загрузки из файла с отсутствующим путём."""
    data_source = {
        "type": "file",
        "path": ""  # Пустой путь
    }
    
    with pytest.raises(ValueError) as exc_info:
        await data_analysis_skill._load_from_file(data_source, {}, {})
    
    assert "Путь к файлу не указан" in str(exc_info.value)


@pytest.mark.asyncio
async def test_load_from_database_no_params(data_analysis_skill):
    """Тест загрузки из БД без параметров."""
    data_source = {
        "type": "database"
        # Отсутствует path и query
    }
    
    with pytest.raises(ValueError) as exc_info:
        await data_analysis_skill._load_from_database(data_source, {}, {})
    
    assert "table_name или query" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_error_handling(data_analysis_skill):
    """Тест обработки ошибок при выполнении."""
    # Мокируем ошибку при загрузке данных
    data_analysis_skill._load_data = AsyncMock(side_effect=Exception("Test error"))
    
    capability = Capability(
        name="data_analysis.analyze_step_data",
        description="Test",
        skill_name="data_analysis"
    )
    
    parameters = {
        "step_id": "step_123",
        "question": "Test?",
        "data_source": {"type": "memory", "content": "data"}
    }
    
    execution_context = MagicMock()
    
    result = await data_analysis_skill.execute(capability, parameters, execution_context)
    
    assert result.status == ExecutionStatus.FAILED
    assert result.error is not None
    assert "Test error" in result.error


@pytest.mark.asyncio
async def test_execute_missing_prompt(data_analysis_skill):
    """Тест выполнения с отсутствующим промптом."""
    # Удаляем промпт из кэша
    data_analysis_skill.prompts = {}
    
    capability = Capability(
        name="data_analysis.analyze_step_data",
        description="Test",
        skill_name="data_analysis"
    )
    
    parameters = {
        "step_id": "step_123",
        "question": "Test?",
        "data_source": {"type": "memory", "content": "data"}
    }
    
    execution_context = MagicMock()

    result = await data_analysis_skill.execute(capability, parameters, execution_context)

    assert result.status == ExecutionStatus.FAILED
    assert result.error is not None
    assert "не загружен" in result.error
    assert result.metadata.get("summary") == "Промпт не найден"


class TestDataAnalysisSkillIntegration:
    """Интеграционные тесты для DataAnalysisSkill."""
    
    @pytest.mark.asyncio
    async def test_full_analysis_workflow(self, data_analysis_skill):
        """Тест полного рабочего процесса анализа."""
        # Мокируем LLM ответ
        mock_llm_response = MagicMock()
        mock_llm_response.content = '''
        {
            "answer": "В данных представлено 3 категории продуктов",
            "confidence": 0.92,
            "evidence": [
                {
                    "source": "чанк_1, строки 1-10",
                    "excerpt": "Категория A: 10 товаров",
                    "relevance_score": 0.95
                }
            ],
            "metadata": {
                "chunks_processed": 2,
                "total_tokens": 500
            }
        }
        '''
        mock_llm_response.tokens_used = 500
        
        mock_llm_provider = AsyncMock()
        mock_llm_provider.generate = AsyncMock(return_value=mock_llm_response)
        data_analysis_skill.application_context.get_llm_provider = MagicMock(return_value=mock_llm_provider)
        
        capability = data_analysis_skill.get_capabilities()[0]
        
        parameters = {
            "step_id": "step_integration_test",
            "question": "Сколько категорий продуктов в данных?",
            "data_source": {
                "type": "memory",
                "content": "category,product,count\nA,Product1,10\nB,Product2,20\nC,Product3,15"
            },
            "analysis_config": {
                "aggregation_method": "summary"
            }
        }
        
        execution_context = MagicMock()

        result = await data_analysis_skill.execute(capability, parameters, execution_context)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.result is not None
        assert "answer" in result.result
        assert result.result["confidence"] > 0.9
        assert len(result.result.get("evidence", [])) > 0

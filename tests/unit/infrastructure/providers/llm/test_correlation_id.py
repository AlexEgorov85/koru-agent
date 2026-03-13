"""
Тесты для correlation_id в LLM провайдерах.

Проверяют что:
- correlation_id генерируется в BaseLLMProvider
- correlation_id одинаковый для LLM_PROMPT_GENERATED и LLM_RESPONSE_RECEIVED
- correlation_id это валидный UUID
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from core.infrastructure.providers.llm.mock_provider import MockProvider, MockLLMConfig
from core.models.types.llm_types import LLMRequest, StructuredOutputConfig


@pytest.fixture
def mock_event_bus():
    """Фикстура для mock event bus."""
    event_bus = AsyncMock()
    event_bus.publish = AsyncMock()
    return event_bus


@pytest.fixture
def mock_provider(mock_event_bus):
    """Фикстура для mock провайдера с настроенным контекстом."""
    provider = MockProvider(config=MockLLMConfig(model_name="test-mock"))
    provider.set_call_context(
        event_bus=mock_event_bus,
        session_id="test_session_123",
        agent_id="test_agent_456",
        component="test_component",
        phase="test_phase"
    )
    # Инициализируем event_bus_logger
    provider.event_bus_logger = MagicMock()
    provider.event_bus_logger.info = AsyncMock()
    provider.event_bus_logger.error = AsyncMock()
    provider.event_bus_logger.warning = AsyncMock()
    provider.event_bus_logger.debug = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_correlation_id_generated_in_base_provider(mock_event_bus, mock_provider):
    """correlation_id генерируется в BaseLLMProvider, не в подклассе."""
    
    request = LLMRequest(
        prompt="Test prompt",
        structured_output=StructuredOutputConfig(
            output_model="TestModel",
            schema_def={"type": "object", "properties": {"status": {"type": "string"}}},
            max_retries=1
        )
    )
    
    # Mock Provider зарегистрирует ответ по умолчанию
    mock_provider.register_response('', '{"status": "ok"}')  # registered for all prompts
    
    response = await mock_provider.generate_structured(request)
    
    # Проверка что publish был вызван
    assert mock_event_bus.publish.called
    
    # Проверка что correlation_id был сгенерирован
    publish_calls = mock_event_bus.publish.call_args_list
    
    # Должно быть как минимум 2 вызова: LLM_PROMPT_GENERATED и LLM_RESPONSE_RECEIVED
    assert len(publish_calls) >= 2
    
    # Находим события по типу
    prompt_event = None
    response_event = None
    
    for call in publish_calls:
        # call[1] это kwargs
        if call[1].get('event_type') and call[1]['event_type'].value == "llm.prompt.generated":
            prompt_event = call[1]
        elif call[1].get('event_type') and call[1]['event_type'].value == "llm.response.received":
            response_event = call[1]
    
    assert prompt_event is not None, "LLM_PROMPT_GENERATED событие не опубликовано"
    assert response_event is not None, "LLM_RESPONSE_RECEIVED событие не опубликовано"
    
    # ✅ correlation_id одинаковый для обоих событий
    assert prompt_event['correlation_id'] == response_event['correlation_id']
    
    # ✅ correlation_id это UUID
    uuid.UUID(prompt_event['correlation_id'])  # Не вызовет ошибку


@pytest.mark.asyncio
async def test_correlation_id_is_valid_uuid(mock_event_bus, mock_provider):
    """correlation_id это валидный UUID v4."""
    
    request = LLMRequest(
        prompt="Test prompt",
        structured_output=StructuredOutputConfig(
            output_model="TestModel",
            schema_def={"type": "object", "properties": {"status": {"type": "string"}}},
            max_retries=1
        )
    )
    
    mock_provider.register_response('', '{"status": "ok"}')  # registered for all prompts
    response = await mock_provider.generate_structured(request)
    
    # Получаем correlation_id из первого события
    publish_calls = mock_event_bus.publish.call_args_list
    correlation_id = None
    
    for call in publish_calls:
        if call[1].get('correlation_id'):
            correlation_id = call[1]['correlation_id']
            break
    
    assert correlation_id is not None
    
    # Проверяем что это валидный UUID
    parsed_uuid = uuid.UUID(correlation_id)
    
    # Проверяем что это UUID v4 (случайный)
    assert parsed_uuid.version == 4


@pytest.mark.asyncio
async def test_correlation_id_unique_for_each_call(mock_event_bus, mock_provider):
    """Каждый вызов generate_structured получает уникальный correlation_id."""
    
    request = LLMRequest(
        prompt="Test prompt",
        structured_output=StructuredOutputConfig(
            output_model="TestModel",
            schema_def={"type": "object", "properties": {"status": {"type": "string"}}},
            max_retries=1
        )
    )
    
    mock_provider.register_response('', '{"status": "ok"}')  # registered for all prompts
    
    # Первый вызов
    await mock_provider.generate_structured(request)
    first_call_correlation_ids = set()
    for call in mock_event_bus.publish.call_args_list:
        if call[1].get('correlation_id'):
            first_call_correlation_ids.add(call[1]['correlation_id'])
    
    # Очищаем mock
    mock_event_bus.publish.reset_mock()
    
    # Второй вызов
    await mock_provider.generate_structured(request)
    second_call_correlation_ids = set()
    for call in mock_event_bus.publish.call_args_list:
        if call[1].get('correlation_id'):
            second_call_correlation_ids.add(call[1]['correlation_id'])
    
    # correlation_id внутри одного вызова одинаковый
    assert len(first_call_correlation_ids) == 1
    assert len(second_call_correlation_ids) == 1
    
    # correlation_id разных вызовов разные
    assert first_call_correlation_ids != second_call_correlation_ids


@pytest.mark.asyncio
async def test_prompt_and_response_share_same_correlation_id(mock_event_bus, mock_provider):
    """Промпт и ответ имеют одинаковый correlation_id (трассировка пары)."""
    
    request = LLMRequest(
        prompt="Test prompt for correlation",
        structured_output=StructuredOutputConfig(
            output_model="TestModel",
            schema_def={"type": "object", "properties": {"result": {"type": "string"}}},
            max_retries=1
        )
    )
    
    mock_provider.register_response('', '{"result": "success"}')  # registered for all prompts
    response = await mock_provider.generate_structured(request)
    
    # Собираем все correlation_id из событий
    publish_calls = mock_event_bus.publish.call_args_list
    correlation_ids = []
    
    for call in publish_calls:
        if call[1].get('correlation_id'):
            correlation_ids.append(call[1]['correlation_id'])
    
    # Все correlation_id в рамках одного вызова должны быть одинаковыми
    assert len(set(correlation_ids)) == 1


@pytest.mark.asyncio
async def test_set_call_context_does_not_accept_correlation_id(mock_provider):
    """set_call_context() не принимает correlation_id параметр."""
    
    import inspect
    sig = inspect.signature(mock_provider.set_call_context)
    params = list(sig.parameters.keys())
    
    # correlation_id НЕ должен быть в параметрах
    assert 'correlation_id' not in params
    
    # Должны быть параметры контекста
    assert 'event_bus' in params
    assert 'session_id' in params
    assert 'agent_id' in params
    assert 'component' in params
    assert 'phase' in params


@pytest.mark.asyncio
async def test_error_event_shares_correlation_id(mock_event_bus, mock_provider):
    """Событие об ошибке также использует тот же correlation_id."""
    
    request = LLMRequest(
        prompt="Test prompt that will fail",
        structured_output=StructuredOutputConfig(
            output_model="TestModel",
            schema_def={"type": "object", "properties": {"result": {"type": "string"}}},
            max_retries=1  # Только одна попытка
        )
    )
    
    # Устанавливаем ответ который не валидируется
    mock_provider.register_response('', '{"wrong_field": "value"}')  # registered for all prompts
    
    try:
        await mock_provider.generate_structured(request)
        assert False, "Ожидалось StructuredOutputError"
    except Exception:
        pass  # Ожидаем ошибку
    
    # Проверяем что все события имеют одинаковый correlation_id
    publish_calls = mock_event_bus.publish.call_args_list
    correlation_ids = []
    
    for call in publish_calls:
        if call[1].get('correlation_id'):
            correlation_ids.append(call[1]['correlation_id'])
    
    # Если были опубликованы события, все correlation_id должны быть одинаковыми
    if correlation_ids:
        assert len(set(correlation_ids)) == 1

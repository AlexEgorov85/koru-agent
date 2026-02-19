"""
Интеграционные тесты workflow с Mock LLM.

Тестирует:
- Полный цикл работы агента с mock LLM
- Взаимодействие между компонентами через mock LLM
- Историю вызовов LLM
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch


# ============================================================================
# Тесты базового workflow
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_llm_basic_workflow(infrastructure_with_mock_llm):
    """
    Тест полного workflow агента с mock LLM.
    
    Проверяет:
    - Инициализацию инфраструктуры с mock LLM
    - Регистрацию ответов для паттернов
    - Историю вызовов LLM
    """
    infra = infrastructure_with_mock_llm
    mock_llm = infra.get_provider('mock_llm')
    
    # Проверяем что mock LLM был создан
    assert mock_llm is not None
    assert mock_llm.model_name == "test-mock"
    
    # Проверяем историю вызовов (пока пустая)
    history = mock_llm.get_call_history()
    assert len(history) == 0
    
    # Выполняем тестовый запрос
    from core.models.types.llm_types import LLMRequest
    request = LLMRequest(
        prompt="planning.create_plan: Test goal",
        max_tokens=100,
        temperature=0.0
    )
    
    response = await mock_llm.generate(request)
    
    # Проверяем ответ
    assert response.content is not None
    assert response.model == "test-mock"
    assert response.generation_time >= 0
    
    # Проверяем историю вызовов
    history = mock_llm.get_call_history()
    assert len(history) == 1
    assert 'planning.create_plan' in history[0]['prompt']
    assert history[0]['matched_pattern'] == 'planning.create_plan'


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_llm_pattern_matching(infrastructure_with_mock_llm):
    """
    Тест сопоставления паттернов в mock LLM.
    
    Проверяет что правильные ответы возвращаются для разных паттернов.
    """
    infra = infrastructure_with_mock_llm
    mock_llm = infra.get_provider('mock_llm')
    mock_llm.clear_history()
    
    from core.models.types.llm_types import LLMRequest
    
    # Тест 1: planning паттерн
    request1 = LLMRequest(
        prompt="planning.create_plan: Create a plan for searching books",
        max_tokens=100
    )
    response1 = await mock_llm.generate(request1)
    assert 'steps' in response1.content
    
    # Тест 2: book_library паттерн
    request2 = LLMRequest(
        prompt="book_library.search_books: Find books by Pushkin",
        max_tokens=100
    )
    response2 = await mock_llm.generate(request2)
    assert 'rows' in response2.content
    
    # Тест 3: final_answer паттерн
    request3 = LLMRequest(
        prompt="final_answer.generate: Generate final answer",
        max_tokens=100
    )
    response3 = await mock_llm.generate(request3)
    assert 'final_answer' in response3.content
    
    # Тест 4: default ответ
    request4 = LLMRequest(
        prompt="unknown_pattern: Some unknown request",
        max_tokens=100
    )
    response4 = await mock_llm.generate(request4)
    assert response4.content == '{"status": "ok"}'
    
    # Проверяем историю вызовов
    history = mock_llm.get_call_history()
    assert len(history) == 4


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_llm_deterministic(infrastructure_with_mock_llm):
    """
    Тест детерминированности ответов mock LLM.
    
    Проверяет что одинаковые запросы возвращают одинаковые ответы.
    """
    infra = infrastructure_with_mock_llm
    mock_llm = infra.get_provider('mock_llm')
    mock_llm.clear_history()
    
    from core.models.types.llm_types import LLMRequest
    
    request = LLMRequest(
        prompt="planning.create_plan: Test",
        max_tokens=100
    )
    
    # Выполняем несколько одинаковых запросов
    responses = []
    for _ in range(5):
        response = await mock_llm.generate(request)
        responses.append(response.content)
    
    # Все ответы должны быть одинаковыми
    assert len(set(responses)) == 1, "Mock LLM не детерминирован"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_llm_assertions(infrastructure_with_mock_llm):
    """
    Тест assertion методов mock LLM.
    
    Проверяет работу assert_called_with и assert_call_count.
    """
    infra = infrastructure_with_mock_llm
    mock_llm = infra.get_provider('mock_llm')
    mock_llm.clear_history()
    
    from core.models.types.llm_types import LLMRequest
    
    # Выполняем запрос
    request = LLMRequest(
        prompt="planning.create_plan: Test planning",
        max_tokens=100
    )
    await mock_llm.generate(request)
    
    # Проверяем assert_called_with
    mock_llm.assert_called_with("planning.create_plan")
    
    # Проверяем assert_call_count
    mock_llm.assert_call_count(1)
    
    # Выполняем еще один запрос
    await mock_llm.generate(request)
    
    # Проверяем что count обновился
    mock_llm.assert_call_count(2)
    
    # Проверяем что неправильный assert вызывает ошибку
    with pytest.raises(AssertionError):
        mock_llm.assert_called_with("nonexistent_pattern")


# ============================================================================
# Тесты с кастомными ответами
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_llm_custom_responses():
    """
    Тест регистрации кастомных ответов.
    
    Проверяет что можно динамически регистрировать новые ответы.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="custom-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    
    # Регистрируем кастомный ответ
    provider.register_response(
        "custom.test",
        '{"custom": "response", "value": 42}'
    )
    
    # Выполняем запрос
    request = LLMRequest(
        prompt="custom.test: Testing custom response",
        max_tokens=100
    )
    response = await provider.generate(request)
    
    # Проверяем ответ
    assert response.content == '{"custom": "response", "value": 42}'
    
    # Проверяем что паттерн был найден
    assert response.metadata['matched_pattern'] == 'custom.test'


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_llm_regex_patterns():
    """
    Тест regex паттернов в mock LLM.
    
    Проверяет что regex паттерны работают корректно.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="regex-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    
    # Регистрируем regex паттерн
    provider.register_regex_response(
        r"search.*books.*author.*(\w+)",
        '{"action": "search", "author": "\\1"}'
    )
    
    # Тест 1: совпадение с паттерном
    request1 = LLMRequest(
        prompt="search books by author Pushkin",
        max_tokens=100
    )
    response1 = await provider.generate(request1)
    assert response1.content == '{"action": "search", "author": "\\1"}'
    
    # Тест 2: еще одно совпадение
    request2 = LLMRequest(
        prompt="I want to search books from author Tolstoy",
        max_tokens=100
    )
    response2 = await provider.generate(request2)
    assert response2.content == '{"action": "search", "author": "\\1"}'
    
    # Тест 3: нет совпадения (default ответ)
    request3 = LLMRequest(
        prompt="delete database",
        max_tokens=100
    )
    response3 = await provider.generate(request3)
    assert response3.content == '{"status": "ok"}'


# ============================================================================
# Тесты производительности
# ============================================================================

@pytest.mark.asyncio
async def test_mock_llm_response_time():
    """
    Тест скорости ответа mock LLM.
    
    Mock LLM должен отвечать быстрее 10ms.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    import time
    
    config = MockLLMConfig(model_name="perf-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    
    request = LLMRequest(
        prompt="Test prompt",
        max_tokens=100
    )
    
    # Замеряем время ответа
    start = time.perf_counter()
    response = await provider.generate(request)
    elapsed = time.perf_counter() - start
    
    # Mock LLM должен отвечать < 10ms
    assert elapsed < 0.01, f"Mock LLM слишком медленный: {elapsed}s"
    assert response.generation_time < 0.01


@pytest.mark.asyncio
async def test_mock_llm_concurrent_requests():
    """
    Тест параллельных запросов к mock LLM.
    
    Проверяет что mock LLM корректно обрабатывает параллельные запросы.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="concurrent-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    
    async def make_request(prompt: str):
        request = LLMRequest(prompt=prompt, max_tokens=100)
        return await provider.generate(request)
    
    # Создаем 10 параллельных запросов
    tasks = [
        make_request(f"Test prompt {i}")
        for i in range(10)
    ]
    
    responses = await asyncio.gather(*tasks)
    
    # Проверяем что все запросы выполнены
    assert len(responses) == 10
    
    # Проверяем что история вызовов корректна
    history = provider.get_call_history()
    assert len(history) == 10

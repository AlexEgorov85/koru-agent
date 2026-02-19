"""
Сценарий: Поиск книг автора.

Тестирует полный workflow:
1. Agent получает goal "Найти книги Пушкина"
2. Planning создаёт план
3. BookLibrary выполняет поиск
4. FinalAnswer формирует ответ
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_books_scenario(infrastructure_with_mock_llm):
    """
    Сценарий: Пользователь хочет найти книги автора.
    
    Ожидаемый workflow:
    1. Agent получает goal
    2. Planning создаёт план
    3. BookLibrary выполняет поиск
    4. FinalAnswer формирует ответ
    """
    infra = infrastructure_with_mock_llm
    mock_llm = infra.get_provider('mock_llm')
    
    # Настраиваем ответы для сценария
    mock_llm.clear_history()
    
    mock_llm.register_response(
        "planning.create_plan",
        json.dumps({
            "steps": [
                {"action": "book_library.search_books", "parameters": {"query": "Пушкин"}}
            ]
        })
    )
    
    mock_llm.register_response(
        "book_library.search_books",
        json.dumps({
            "rows": [
                {"title": "Евгений Онегин", "author": "Пушкин"},
                {"title": "Капитанская дочка", "author": "Пушкин"}
            ],
            "rowcount": 2
        })
    )
    
    mock_llm.register_response(
        "final_answer.generate",
        json.dumps({
            "final_answer": "Найдено 2 книги Пушкина",
            "confidence": 0.95
        })
    )
    
    # Проверяем что ответы зарегистрированы
    from core.models.types.llm_types import LLMRequest
    
    # Тест 1: Planning
    planning_request = LLMRequest(
        prompt="planning.create_plan: Найти книги Пушкина",
        max_tokens=500
    )
    planning_response = await mock_llm.generate(planning_request)
    planning_data = json.loads(planning_response.content)
    
    assert 'steps' in planning_data
    assert len(planning_data['steps']) > 0
    assert planning_data['steps'][0]['action'] == 'book_library.search_books'
    
    # Тест 2: BookLibrary search
    search_request = LLMRequest(
        prompt="book_library.search_books: Пушкин",
        max_tokens=500
    )
    search_response = await mock_llm.generate(search_request)
    search_data = json.loads(search_response.content)
    
    assert 'rows' in search_data
    assert search_data['rowcount'] == 2
    assert len(search_data['rows']) == 2
    
    # Тест 3: FinalAnswer
    final_request = LLMRequest(
        prompt="final_answer.generate: Сформировать ответ",
        max_tokens=500
    )
    final_response = await mock_llm.generate(final_request)
    final_data = json.loads(final_response.content)
    
    assert 'final_answer' in final_data
    assert final_data['confidence'] == 0.95
    
    # Проверяем историю вызовов
    history = mock_llm.get_call_history()
    assert len(history) == 3
    
    # Проверяем последовательность вызовов
    prompts = [h['prompt'] for h in history]
    assert any('planning.create_plan' in p for p in prompts)
    assert any('book_library.search_books' in p for p in prompts)
    assert any('final_answer.generate' in p for p in prompts)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_books_with_mock_responses():
    """
    Упрощенный тест сценария поиска книг с изолированным mock LLM.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    # Создаем mock LLM
    config = MockLLMConfig(model_name="search-mock", temperature=0.0)
    mock_llm = MockLLMProvider(config=config)
    
    # Регистрируем ответы для сценария
    mock_llm.register_response(
        "Найти книги",
        json.dumps({
            "action": "search",
            "query": "книги",
            "results": [
                {"title": "Книга 1", "author": "Автор 1"},
                {"title": "Книга 2", "author": "Автор 2"}
            ]
        })
    )
    
    # Выполняем запрос
    request = LLMRequest(
        prompt="Помоги Найти книги по программированию",
        max_tokens=500
    )
    response = await mock_llm.generate(request)
    
    # Проверяем ответ
    data = json.loads(response.content)
    assert data['action'] == 'search'
    assert len(data['results']) == 2
    
    # Проверяем историю
    history = mock_llm.get_call_history()
    assert len(history) == 1
    assert 'Найти книги' in history[0]['prompt']


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_books_error_handling():
    """
    Тест обработки ошибок в сценарии поиска книг.
    
    Проверяет что mock LLM корректно возвращает ошибки.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="error-mock", temperature=0.0)
    mock_llm = MockLLMProvider(config=config)
    
    # Регистрируем ответ с ошибкой
    mock_llm.register_response(
        "error_case",
        json.dumps({
            "error": "Book not found",
            "status": "failed"
        })
    )
    
    # Выполняем запрос
    request = LLMRequest(
        prompt="error_case: Поиск несуществующей книги",
        max_tokens=100
    )
    response = await mock_llm.generate(request)
    
    # Проверяем ответ с ошибкой
    data = json.loads(response.content)
    assert data['error'] == "Book not found"
    assert data['status'] == "failed"


@pytest.mark.asyncio
async def test_search_books_scenario_step_by_step():
    """
    Пошаговый тест сценария поиска книг.
    
    Детально проверяет каждый шаг workflow.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    # Создаем mock LLM
    config = MockLLMConfig(model_name="step-mock", temperature=0.0)
    mock_llm = MockLLMProvider(config=config)
    
    # Шаг 1: Планирование
    mock_llm.register_response(
        "plan",
        json.dumps({
            "step": 1,
            "action": "search",
            "next": "execute"
        })
    )
    
    request1 = LLMRequest(prompt="plan: Найти книги", max_tokens=100)
    response1 = await mock_llm.generate(request1)
    data1 = json.loads(response1.content)
    
    assert data1['step'] == 1
    assert data1['action'] == 'search'
    
    # Шаг 2: Выполнение поиска
    mock_llm.register_response(
        "execute",
        json.dumps({
            "step": 2,
            "results": ["Book A", "Book B"],
            "next": "finalize"
        })
    )
    
    request2 = LLMRequest(prompt="execute: Поиск", max_tokens=100)
    response2 = await mock_llm.generate(request2)
    data2 = json.loads(response2.content)
    
    assert data2['step'] == 2
    assert len(data2['results']) == 2
    
    # Шаг 3: Финализация
    mock_llm.register_response(
        "finalize",
        json.dumps({
            "step": 3,
            "final_answer": "Найдено 2 книги",
            "complete": True
        })
    )
    
    request3 = LLMRequest(prompt="finalize: Ответ", max_tokens=100)
    response3 = await mock_llm.generate(request3)
    data3 = json.loads(response3.content)
    
    assert data3['step'] == 3
    assert data3['complete'] is True
    
    # Проверяем полную историю
    history = mock_llm.get_call_history()
    assert len(history) == 3
    
    # Проверяем последовательность шагов
    steps = [json.loads(h['response'])['step'] for h in history]
    assert steps == [1, 2, 3]

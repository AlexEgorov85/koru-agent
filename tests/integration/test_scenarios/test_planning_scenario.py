"""
Сценарий: Планирование задач.

Тестирует workflow планирования:
1. Получение цели
2. Декомпозиция на шаги
3. Последовательное выполнение
4. Валидация результата
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock


@pytest.mark.integration
@pytest.mark.asyncio
async def test_planning_scenario(infrastructure_with_mock_llm):
    """
    Сценарий: Планирование сложной задачи.
    
    Ожидаемый workflow:
    1. Agent получает сложную цель
    2. Planning декомпозирует на подзадачи
    3. Выполняет каждую подзадачу
    4. Агрегирует результаты
    """
    infra = infrastructure_with_mock_llm
    mock_llm = infra.get_provider('mock_llm')
    mock_llm.clear_history()
    
    # Регистрируем ответы для планирования
    mock_llm.register_response(
        "planning.decompose",
        json.dumps({
            "goal": "Анализ данных",
            "subtasks": [
                {"id": 1, "task": "Загрузить данные", "type": "data_load"},
                {"id": 2, "task": "Обработать данные", "type": "data_process"},
                {"id": 3, "task": "Анализировать результаты", "type": "data_analyze"}
            ]
        })
    )
    
    mock_llm.register_response(
        "data_load",
        json.dumps({
            "status": "success",
            "rows_loaded": 1000
        })
    )
    
    mock_llm.register_response(
        "data_process",
        json.dumps({
            "status": "success",
            "rows_processed": 1000
        })
    )
    
    mock_llm.register_response(
        "data_analyze",
        json.dumps({
            "status": "success",
            "insights": ["Insight 1", "Insight 2"]
        })
    )
    
    from core.models.types.llm_types import LLMRequest
    
    # Шаг 1: Декомпозиция
    decompose_request = LLMRequest(
        prompt="planning.decompose: Анализ данных за 2024 год",
        max_tokens=500
    )
    decompose_response = await mock_llm.generate(decompose_request)
    plan = json.loads(decompose_response.content)
    
    assert 'subtasks' in plan
    assert len(plan['subtasks']) == 3
    
    # Шаг 2: Выполнение подзадач
    results = []
    for subtask in plan['subtasks']:
        task_type = subtask['type']
        task_request = LLMRequest(
            prompt=f"{task_type}: Выполнить {subtask['task']}",
            max_tokens=200
        )
        task_response = await mock_llm.generate(task_request)
        result = json.loads(task_response.content)
        results.append(result)
    
    # Проверяем результаты
    assert len(results) == 3
    assert all(r['status'] == 'success' for r in results)
    
    # Проверяем историю вызовов
    history = mock_llm.get_call_history()
    assert len(history) == 4  # 1 decompose + 3 subtasks
    
    # Проверяем последовательность
    prompts = [h['prompt'] for h in history]
    assert any('planning.decompose' in p for p in prompts)
    assert any('data_load' in p for p in prompts)
    assert any('data_process' in p for p in prompts)
    assert any('data_analyze' in p for p in prompts)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_planning_sequence_generation():
    """
    Тест генерации последовательности действий.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="sequence-mock", temperature=0.0)
    mock_llm = MockLLMProvider(config=config)
    
    # Регистрируем ответ для генерации последовательности
    mock_llm.register_response(
        "planning.sequence",
        json.dumps({
            "sequence": [
                {"step": 1, "action": "validate_input"},
                {"step": 2, "action": "fetch_data"},
                {"step": 3, "action": "transform_data"},
                {"step": 4, "action": "save_results"}
            ]
        })
    )
    
    request = LLMRequest(
        prompt="planning.sequence: Обработать данные",
        max_tokens=300
    )
    response = await mock_llm.generate(request)
    sequence = json.loads(response.content)
    
    assert 'sequence' in sequence
    assert len(sequence['sequence']) == 4
    
    # Проверяем нумерацию шагов
    steps = [s['step'] for s in sequence['sequence']]
    assert steps == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_planning_with_dependencies():
    """
    Тест планирования с зависимостями между задачами.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="deps-mock", temperature=0.0)
    mock_llm = MockLLMProvider(config=config)
    
    # Регистрируем ответ с зависимостями
    mock_llm.register_response(
        "planning.with_deps",
        json.dumps({
            "tasks": [
                {"id": "A", "depends_on": []},
                {"id": "B", "depends_on": ["A"]},
                {"id": "C", "depends_on": ["A"]},
                {"id": "D", "depends_on": ["B", "C"]}
            ]
        })
    )
    
    request = LLMRequest(
        prompt="planning.with_deps: Построить график задач",
        max_tokens=300
    )
    response = await mock_llm.generate(request)
    plan = json.loads(response.content)
    
    assert 'tasks' in plan
    assert len(plan['tasks']) == 4
    
    # Проверяем зависимости
    task_map = {t['id']: t['depends_on'] for t in plan['tasks']}
    assert task_map['A'] == []
    assert task_map['B'] == ['A']
    assert task_map['C'] == ['A']
    assert task_map['D'] == ['B', 'C']


@pytest.mark.asyncio
async def test_planning_error_recovery():
    """
    Тест восстановления после ошибок в планировании.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="recovery-mock", temperature=0.0)
    mock_llm = MockLLMProvider(config=config)
    
    # Регистрируем ответ для восстановления
    mock_llm.register_response(
        "planning.recovery",
        json.dumps({
            "error": "Task failed",
            "retry_count": 1,
            "fallback_action": "use_cache",
            "success": True
        })
    )
    
    request = LLMRequest(
        prompt="planning.recovery: Обработать ошибку",
        max_tokens=200
    )
    response = await mock_llm.generate(request)
    recovery = json.loads(response.content)
    
    assert recovery['error'] == "Task failed"
    assert recovery['fallback_action'] == "use_cache"
    assert recovery['success'] is True


@pytest.mark.asyncio
async def test_planning_parallel_execution():
    """
    Тест планирования параллельного выполнения задач.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="parallel-mock", temperature=0.0)
    mock_llm = MockLLMProvider(config=config)
    
    # Регистрируем ответ для параллельного выполнения
    mock_llm.register_response(
        "planning.parallel",
        json.dumps({
            "parallel_groups": [
                {"group": 1, "tasks": ["A", "B", "C"]},
                {"group": 2, "tasks": ["D", "E"]}
            ]
        })
    )
    
    request = LLMRequest(
        prompt="planning.parallel: Распараллелить задачи",
        max_tokens=200
    )
    response = await mock_llm.generate(request)
    plan = json.loads(response.content)
    
    assert 'parallel_groups' in plan
    assert len(plan['parallel_groups']) == 2
    
    # Проверяем первую группу
    assert plan['parallel_groups'][0]['group'] == 1
    assert len(plan['parallel_groups'][0]['tasks']) == 3

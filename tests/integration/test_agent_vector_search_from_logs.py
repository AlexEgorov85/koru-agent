"""
Интеграционный тест на основе логов logs/2026-04-28_15-14-33.

ВОСПРОИЗВЕДЕНИЕ СЦЕНАРИЯ:
  Цель: "В каких проверках были описания с нарушениями сроков предоставления отчетности?"
  Шаг 1: check_result.vector_search (query="нарушения сроков предоставления отчетности")
  Шаг 2: data_analysis.analyze_step_data (анализ результатов шага 1)
  Шаг 3: check_result.vector_search (уточнённый запрос)

ЗАПУСК:
    pytest tests/integration/test_agent_vector_search_from_logs.py -v -s

ПРИНЦИПЫ:
- Реальный InfrastructureContext и ApplicationContext
- Реальный LLM (не мок)
- Реальные вызовы check_result.vector_search и data_analysis
- Проверка структуры и содержания ответов
"""

import pytest
import pytest_asyncio
from typing import List, Dict, Any

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.session_context.session_context import SessionContext
from core.components.action_executor import ActionExecutor, ExecutionContext
from core.models.enums.common_enums import ExecutionStatus


# ============================================================================
# ФИКСТУРЫ (scope="module" — один подъём на ВСЕ тесты)
# ============================================================================

@pytest.fixture(scope="module")
def config():
    return get_config(profile='prod', data_dir='data')


@pytest_asyncio.fixture(scope="module")
async def infrastructure(config):
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest_asyncio.fixture(scope="module")
async def app_context(infrastructure):
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=infrastructure.config.data_dir
    )
    ctx = ApplicationContext(
        infrastructure_context=infrastructure,
        config=app_config,
        profile="prod"
    )
    await ctx.initialize()
    yield ctx
    await ctx.shutdown()


@pytest_asyncio.fixture(scope="module")
def executor(app_context):
    return ActionExecutor(application_context=app_context)


@pytest.fixture
def session_context():
    return SessionContext(
        session_id="test_vector_search_from_logs",
        agent_id="agent_test_vector"
    )


def _extract_results(result):
    """
    Извлечь список результатов из ответа vector_search.

    vector_search может возвращать:
    - result.data как список
    - result.data как dict со ключом 'results' или 'rows'
    """
    data = result.data

    # Если data — это list, возвращаем как есть
    if isinstance(data, list):
        return data

    # Если data — это dict
    if isinstance(data, dict):
        return data.get("results") or data.get("rows") or []

    # Если это Pydantic модель
    if hasattr(data, 'model_dump'):
        d = data.model_dump()
        return d.get("results") or d.get("rows") or []

    return []


def _extract_audit_ids(results: List[Dict]) -> set:
    """Извлечь audit_id из результатов vector_search."""
    audit_ids = set()
    for r in results:
        audit_id = None
        if "audit_id" in r:
            audit_id = r["audit_id"]
        elif "row" in r and isinstance(r["row"], dict):
            audit_id = r["row"].get("id")
        elif "id" in r:
            audit_id = r["id"]

        if audit_id is not None:
            audit_ids.add(int(audit_id))
    return audit_ids


# ============================================================================
# ТЕСТ 1: ПЕРВЫЙ ШАГ — vector_search с исходным запросом
# ============================================================================

@pytest.mark.asyncio
async def test_step1_vector_search_original_query(executor, session_context):
    """
    Шаг 1 из логов: vector_search с query='нарушения сроков предоставления отчетности'.

    ОЖИДАНИЕ:
    - status == COMPLETED
    - result.data содержит список с результатами (audit id 4, 9 из логов)
    - score >= 0.5 для релевантных результатов
    """
    exec_ctx = ExecutionContext(session_context=session_context)

    result = await executor.execute_action(
        action_name="check_result.vector_search",
        parameters={
            "query": "нарушения сроков предоставления отчетности",
            "source": "audits",
            "top_k": 10,
            "min_score": 0.5
        },
        context=exec_ctx
    )

    assert result.status == ExecutionStatus.COMPLETED, \
        f"Ожидался COMPLETED, но получил {result.status}: {result.error}"

    results = _extract_results(result)
    assert isinstance(results, list), f"results должен быть списком: {type(results)}"
    assert len(results) > 0, "Результаты поиска пусты"

    # Проверка структуры первого результата (как в логах строка 123)
    first = results[0]
    assert isinstance(first, dict), f"Элемент результата должен быть dict: {type(first)}"

    # Проверяем наличие ключевых полей
    has_score = "score" in first
    has_audit_id = "audit_id" in first or ("row" in first and "id" in first.get("row", {}))
    assert has_score, f"В результате нет 'score': {first.keys()}"

    print(f"✅ Шаг 1: vector_search нашёл {len(results)} результатов")
    score = first.get("score", 0)
    audit_id = first.get("audit_id") or first.get("row", {}).get("id", "N/A")
    print(f"   Первый результат: score={score:.3f}, audit_id={audit_id}")


# ============================================================================
# ТЕСТ 2: ВТОРОЙ ШАГ — data_analysis.analyze_step_data
# ============================================================================

@pytest.mark.asyncio
async def test_step2_data_analysis(executor, session_context):
    """
    Шаг 2 из логов: анализ данных шага 1 через data_analysis.

    ОЖИДАНИЕ:
    - status == COMPLETED (даже если данные не извлечены)
    - В ответе есть execution_status или answer
    """
    exec_ctx = ExecutionContext(session_context=session_context)

    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Провести детальный анализ задержек в аудите по трудовому законодательству "
                       "и уточнить сроки выполнения для аудита управления рисками",
            "step_id": 1
        },
        context=exec_ctx
    )

    # data_analysis может вернуть COMPLETED даже при частичном результате
    assert result.status == ExecutionStatus.COMPLETED, \
        f"Ожидался COMPLETED, но получил {result.status}: {result.error}"

    data = result.data if isinstance(result.data, dict) else \
        (result.data.model_dump() if hasattr(result.data, 'model_dump') else {})

    # Проверка структуры ответа (как в логах строка 286)
    has_answer = "answer" in data
    has_status = "execution_status" in data or "status" in data
    assert has_answer or has_status, \
        f"Неожиданная структура ответа: {data.keys() if isinstance(data, dict) else type(data)}"

    print(f"✅ Шаг 2: data_analysis выполнен")
    answer = data.get("answer", data.get("execution_status", "N/A"))
    print(f"   Ответ: {str(answer)[:100]}")


# ============================================================================
# ТЕСТ 3: ТРЕТИЙ ШАГ — vector_search с уточнённым запросом
# ============================================================================

@pytest.mark.asyncio
async def test_step3_vector_search_refined_query(executor, session_context):
    """
    Шаг 3 из логов: vector_search с уточнённым запросом.

    ОЖИДАНИЕ:
    - status == COMPLETED
    - Находятся те же аудиты (id 4, 9)
    """
    exec_ctx = ExecutionContext(session_context=session_context)

    result = await executor.execute_action(
        action_name="check_result.vector_search",
        parameters={
            "query": "нарушения сроков предоставления отчетности в аудите по трудовому законодательству и аудите управления рисками",
            "source": "audits",
            "top_k": 10,
            "min_score": 0.5
        },
        context=exec_ctx
    )

    assert result.status == ExecutionStatus.COMPLETED, \
        f"Ожидался COMPLETED, но получил {result.status}: {result.error}"

    results = _extract_results(result)
    assert isinstance(results, list), f"results должен быть списком: {type(results)}"
    assert len(results) > 0, "Результаты поиска пусты"

    # Проверяем, что нашлись аудиты с id 4 и 9 (как в логах)
    audit_ids = _extract_audit_ids(results)
    assert 4 in audit_ids, f"Аудит id=4 не найден в результатах: {audit_ids}"
    assert 9 in audit_ids, f"Аудит id=9 не найден в результатах: {audit_ids}"

    print(f"✅ Шаг 3: уточнённый vector_search нашёл аудиты: {sorted(audit_ids)}")


# ============================================================================
# ТЕСТ 4: ПОЛНЫЙ СЦЕНАРИЙ — последовательные шаги как в логах
# ============================================================================

@pytest.mark.asyncio
async def test_full_scenario_from_logs(executor):
    """
    Полный сценарий из логов: последовательно шаги 1 → 2 → 3.

    ОЖИДАНИЕ:
    - Каждый шаг завершается успешно
    - Результаты векторного поиска согласованы
    - Данные аудитов корректны
    """
    session = SessionContext(
        session_id="test_full_scenario_logs",
        agent_id="agent_full_scenario"
    )

    # ШАГ 1: Исходный vector_search
    exec_ctx1 = ExecutionContext(session_context=session)

    result1 = await executor.execute_action(
        action_name="check_result.vector_search",
        parameters={
            "query": "нарушения сроков предоставления отчетности",
            "source": "audits",
            "top_k": 10,
            "min_score": 0.5
        },
        context=exec_ctx1
    )

    assert result1.status == ExecutionStatus.COMPLETED, f"Шаг 1 FAILED: {result1.error}"

    results1 = _extract_results(result1)
    assert len(results1) > 0, "Шаг 1: пустые результаты"

    # Сохраняем observation для следующего шага (имитация того, что делает агент)
    session.record_observation(
        result1.data,
        source="check_result.vector_search",
        step_number=1
    )

    # ШАГ 2: data_analysis
    exec_ctx2 = ExecutionContext(session_context=session)

    result2 = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Провести детальный анализ задержек в аудите по трудовому законодательству "
                       "и уточнить сроки выполнения для аудита управления рисками",
            "step_id": 1
        },
        context=exec_ctx2
    )

    assert result2.status == ExecutionStatus.COMPLETED, f"Шаг 2 FAILED: {result2.error}"

    # ШАГ 3: Уточнённый vector_search
    exec_ctx3 = ExecutionContext(session_context=session)

    result3 = await executor.execute_action(
        action_name="check_result.vector_search",
        parameters={
            "query": "нарушения сроков предоставления отчетности в аудите по трудовому законодательству и аудите управления рисками",
            "source": "audits",
            "top_k": 10,
            "min_score": 0.5
        },
        context=exec_ctx3
    )

    assert result3.status == ExecutionStatus.COMPLETED, f"Шаг 3 FAILED: {result3.error}"

    results3 = _extract_results(result3)

    # Проверяем согласованность результатов
    audit_ids_1 = _extract_audit_ids(results1)
    audit_ids_3 = _extract_audit_ids(results3)

    # Ожидаем пересечение результатов
    assert len(audit_ids_1 & audit_ids_3) > 0, \
        f"Результаты шагов 1 и 3 не пересекаются: {audit_ids_1} vs {audit_ids_3}"

    print(f"✅ Полный сценарий выполнен успешно!")
    print(f"   Шаг 1: {sorted(audit_ids_1)}")
    print(f"   Шаг 3: {sorted(audit_ids_3)}")
    print(f"   Пересечение: {sorted(audit_ids_1 & audit_ids_3)}")


# ============================================================================
# ТЕСТ 5: ПРОВЕРКА СТРУКТУРЫ РЕЗУЛЬТАТА VECTOR_SEARCH
# ============================================================================

@pytest.mark.asyncio
async def test_vector_search_result_structure(executor, session_context):
    """
    Проверка структуры результата vector_search.

    ОЖИДАНИЕ (как в логах строка 123):
    - type: 'audits'
    - score: float
    - source: 'audits'
    - row: dict с полями id, title, audit_type, status, planned_date, actual_date
    - matched_text: str
    - audit_id: int
    """
    exec_ctx = ExecutionContext(session_context=session_context)

    result = await executor.execute_action(
        action_name="check_result.vector_search",
        parameters={
            "query": "нарушения сроков предоставления отчетности",
            "source": "audits",
            "top_k": 5,
            "min_score": 0.5
        },
        context=exec_ctx
    )

    assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"

    results = _extract_results(result)
    assert len(results) > 0, "Нет результатов"

    # Проверяем структуру первого результата
    first = results[0]

    # Вариант 1: структура как в логах (строка 123)
    if "type" in first and "row" in first:
        assert first["type"] == "audits", f"type != 'audits': {first['type']}"
        assert "score" in first, "Нет 'score'"
        assert isinstance(first["score"], (int, float)), "score не число"
        assert "row" in first and isinstance(first["row"], dict), "row не dict"
        row = first["row"]
        assert "id" in row, "В row нет 'id'"
        assert "title" in row, "В row нет 'title'"
        assert "audit_type" in row, "В row нет 'audit_type'"
        assert "status" in row, "В row нет 'status'"
    # Вариант 2: упрощённая структура
    elif "audit_id" in first:
        assert isinstance(first["audit_id"], int), "audit_id не int"
        assert "score" in first, "Нет 'score'"
    else:
        # Проверяем хотя бы наличие score
        assert "score" in first, f"Нет 'score' в результате: {first.keys()}"

    print(f"✅ Структура результата vector_search корректна")


# ============================================================================
# ТЕСТ 6: ПРОВЕРКА ФИЛЬТРАЦИИ ПО SOURCE
# ============================================================================

@pytest.mark.asyncio
async def test_vector_search_source_filtering(executor, session_context):
    """
    Проверка фильтрации по source.

    ОЖИДАНИЕ:
    - source='audits' возвращает только аудиты
    """
    exec_ctx = ExecutionContext(session_context=session_context)

    # Тест с source='audits'
    result_audits = await executor.execute_action(
        action_name="check_result.vector_search",
        parameters={
            "query": "нарушения",
            "source": "audits",
            "top_k": 5,
            "min_score": 0.5
        },
        context=exec_ctx
    )

    assert result_audits.status == ExecutionStatus.COMPLETED, \
        f"FAILED (audits): {result_audits.error}"

    results_audits = _extract_results(result_audits)

    # Проверяем, что все результаты - аудиты
    for r in results_audits:
        if "type" in r:
            assert r["type"] == "audits", f"Ожидался type='audits', получил {r['type']}"

    print(f"✅ Фильтрация по source='audits' работает: {len(results_audits)} результатов")


# ============================================================================
# ТЕСТ 7: ПРОВЕРКА MIN_SCORE ПОРОГА
# ============================================================================

@pytest.mark.asyncio
async def test_vector_search_min_score(executor, session_context):
    """
    Проверка работы min_score порога.

    ОЖИДАНИЕ:
    - Все результаты имеют score >= min_score
    """
    min_score = 0.9
    exec_ctx = ExecutionContext(session_context=session_context)

    result = await executor.execute_action(
        action_name="check_result.vector_search",
        parameters={
            "query": "нарушения сроков предоставления отчетности",
            "source": "audits",
            "top_k": 10,
            "min_score": min_score
        },
        context=exec_ctx
    )

    assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"

    results = _extract_results(result)

    # Проверяем порог
    for r in results:
        score = r.get("score", 0)
        assert score >= min_score, \
            f"Результат с score={score} ниже порога min_score={min_score}"

    print(f"✅ min_score={min_score} работает: {len(results)} результатов, все score >= {min_score}")

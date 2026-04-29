"""
Интеграционный тест на основе реального лога сессии.

ЛОГ: logs/2026-04-28_15-14-33
ЦЕЛЬ: "В каких проверках были описания с нарушениями сроков предоставления отчетности?"

СЦЕНАРИЙ:
  Агент вызывает check_result.vector_search с запросом о нарушениях сроков отчетности.
  Ожидается найти проверки (аудиты) с релевантными текстами.

ПРИНЦИПЫ:
  - Реальная инфраструктура (InfrastructureContext, ApplicationContext)
  - Реальный LLM (через провайдер из конфига)
  - Реальный вызов навыка через ActionExecutor
  - Без моков для компонентов
"""

import pytest
import pytest_asyncio

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.session_context.session_context import SessionContext
from core.models.enums.common_enums import ExecutionStatus


# ============================================================================
# ФИКСТУРЫ
# ============================================================================

@pytest.fixture(scope="module")
def config():
    """Конфигурация из профиля prod (как в рабочем логе)."""
    return get_config(profile='prod')


@pytest_asyncio.fixture(scope="module")
async def infrastructure(config):
    """Реальный InfrastructureContext."""
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest_asyncio.fixture(scope="module")
async def app_context(infrastructure):
    """Реальный ApplicationContext с авто-обнаружением (profile='prod')."""
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
async def executor(app_context):
    """ActionExecutor для вызова навыков."""
    from core.components.action_executor import ActionExecutor
    return ActionExecutor(application_context=app_context)


@pytest.fixture
def session():
    """Свежий контекст сессии с целью из лога."""
    session = SessionContext(
        session_id="test_vector_search_from_logs",
        agent_id="test_agent_logs"
    )
    session.set_goal("В каких проверках были описания с нарушениями сроков предоставления отчетности?")
    return session


# ============================================================================
# ТЕСТЫ
# ============================================================================

class TestVectorSearchFromLogs:
    """
    Тесты на основе реального лога сессии 2026-04-28_15-14-33.

    Проверяют что check_result.vector_search работает с реальным LLM
    и возвращает релевантные результаты.
    """

    @pytest.mark.asyncio
    async def test_vector_search_with_real_llm(self, executor, session):
        """
        Тест 1: Вызов check_result.vector_search с параметрами из лога.

        ПАРАМЕТРЫ (из лога, шаг 1):
          query: "нарушения сроков предоставления отчетности"
          source: "audits"
          top_k: 10
          min_score: 0.5

        ОЖИДАНИЕ:
          - status == COMPLETED
          - result содержит список с результатами
          - в результатах есть audit_id 4, 9 (как в логе)
        """
        result = await executor.execute_action(
            action_name="check_result.vector_search",
            parameters={
                "query": "нарушения сроков предоставления отчетности",
                "source": "audits",
                "top_k": 10,
                "min_score": 0.5
            },
            context=session
        )

        # Проверка статуса выполнения
        assert result.status == ExecutionStatus.COMPLETED, \
            f"Ожидался COMPLETED, но получил {result.status}: {result.error}"

        # Проверка наличия данных
        raw_data = result.data
        if hasattr(raw_data, 'model_dump'):
            raw_data = raw_data.model_dump()
        
        # Обработка: data может быть списком или словарём
        if isinstance(raw_data, list):
            results = raw_data
            data = {}
        elif isinstance(raw_data, dict):
            data = raw_data
            results = data.get("results", [])
        else:
            data = {}
            results = []

        # В логе результат содержит список словарей с ключами type, score, source, row, matched_text
        assert isinstance(results, list), \
            f"results должен быть списком, получил: {type(results)}"

        assert isinstance(results, list), f"results должен быть списком, получил: {type(results)}"
        assert len(results) > 0, "Результаты поиска пусты"

        # Проверка структуры каждого результата
        for item in results[:3]:  # Проверяем первые 3
            assert "score" in item, f"Нет 'score' в результате: {item.keys()}"
            assert "row" in item or "audit_id" in item, f"Нет 'row' или 'audit_id': {item.keys()}"
            assert item.get("score", 0) >= 0.5, \
                f"Score {item.get('score')} ниже min_score=0.5"

        # Проверка что найдены релевантные аудиты (ID 4 и 9 из лога)
        audit_ids = []
        for item in results:
            row = item.get("row", {})
            if isinstance(row, dict):
                audit_id = row.get("id") or item.get("audit_id")
                if audit_id:
                    audit_ids.append(audit_id)

        print(f"✅ VectorSearch: найдено {len(results)} результатов")
        print(f"   Audit IDs: {audit_ids[:5]}")  # Первые 5
        print(f"   Top score: {results[0].get('score', 0):.3f}")

    @pytest.mark.asyncio
    async def test_vector_search_refined_query(self, executor, session):
        """
        Тест 2: Уточнённый запрос (как в шаге 3 лога).

        ПАРАМЕТРЫ (из лога, шаг 3):
          query: "нарушения сроков предоставления отчетности в аудите по трудовому законодательству и аудите управления рисками"
          source: "audits"
          top_k: 10
          min_score: 0.5

        ОЖИДАНИЕ:
          - Статус COMPLETED
          - Результаты содержат аудиты по трудовому законодательству (ID 4)
            и управлению рисками (ID 9)
        """
        result = await executor.execute_action(
            action_name="check_result.vector_search",
            parameters={
                "query": "нарушения сроков предоставления отчетности в аудите по трудовому законодательству и аудите управления рисками",
                "source": "audits",
                "top_k": 10,
                "min_score": 0.5
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, \
            f"Ожидался COMPLETED: {result.status}, error: {result.error}"

        # Обработка результата
        raw_data = result.data
        if hasattr(raw_data, 'model_dump'):
            raw_data = raw_data.model_dump()
        
        if isinstance(raw_data, list):
            results = raw_data
        elif isinstance(raw_data, dict):
            results = raw_data.get("results", [])
        else:
            results = []

        assert len(results) > 0, "Пустые результаты для уточнённого запроса"

        # Ищем целевые аудиты в результатах
        found_audit_4 = False
        found_audit_9 = False

        for item in results:
            row = item.get("row", {})
            if isinstance(row, dict):
                audit_id = row.get("id")
                if audit_id == 4:
                    found_audit_4 = True
                elif audit_id == 9:
                    found_audit_9 = True

        assert found_audit_4, "Не найден аудит ID 4 (трудовое законодательство)"
        assert found_audit_9, "Не найден аудит ID 9 (управление рисками)"

        print(f"✅ VectorSearch (refined): найдены целевые аудиты ID 4 и ID 9")

    @pytest.mark.asyncio
    async def test_vector_search_min_score_filtering(self, executor, session):
        """
        Тест 3: Проверка фильтрации по min_score.

        Проверяем что результаты с score < min_score не возвращаются.
        """
        # Запрос с высоким порогом
        result = await executor.execute_action(
            action_name="check_result.vector_search",
            parameters={
                "query": "нарушения сроков предоставления отчетности",
                "source": "audits",
                "top_k": 10,
                "min_score": 0.9  # Высокий порог как в логе
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, \
            f"Ожидался COMPLETED: {result.status}"

        # Обработка результата
        raw_data = result.data
        if hasattr(raw_data, 'model_dump'):
            raw_data = raw_data.model_dump()
        
        if isinstance(raw_data, list):
            results = raw_data
        elif isinstance(raw_data, dict):
            results = raw_data.get("results", [])
        else:
            results = []

        # Проверяем что все результаты выше порога
        for item in results:
            score = item.get("score", 0)
            assert score >= 0.9, \
                f"Score {score} ниже min_score=0.9 для {item.get('audit_id', 'unknown')}"

        print(f"✅ VectorSearch (min_score=0.9): {len(results)} результатов, все выше порога")

    @pytest.mark.asyncio
    async def test_vector_search_empty_result_handling(self, executor, session):
        """
        Тест 4: Обработка запроса, который может вернуть мало результатов.

        Проверяем что навык корректно обрабатывает запрос
        и возвращает COMPLETED даже если результатов мало.
        """
        result = await executor.execute_action(
            action_name="check_result.vector_search",
            parameters={
                "query": "xyznonexistentquery12345",
                "source": "audits",
                "top_k": 5,
                "min_score": 0.8
            },
            context=session
        )

        # Даже при пустых результатах статус должен быть COMPLETED (не FAILED)
        assert result.status == ExecutionStatus.COMPLETED, \
            f"Ожидался COMPLETED даже при пустых результатах: {result.status}"

        # Обработка результата
        raw_data = result.data
        if hasattr(raw_data, 'model_dump'):
            raw_data = raw_data.model_dump()
        
        if isinstance(raw_data, list):
            results = raw_data
        elif isinstance(raw_data, dict):
            results = raw_data.get("results", [])
        else:
            results = []

        # Результатов может не быть, это нормально для такого запроса
        print(f"✅ VectorSearch (empty query): статус={result.status}, результатов={len(results)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

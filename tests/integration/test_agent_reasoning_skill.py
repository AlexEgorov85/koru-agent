"""
Интеграционный тест: агент + реальный LLM + выполнение навыка vector_search.

СЦЕНАРИЙ (из логов 2026-04-28_15-14-33):
  ЦЕЛЬ: В каких проверках были описания с нарушениями сроков предоставления отчетности?
  ШАГ 1: LLM решает вызвать check_result.vector_search
  ШАГ 2: Навык возвращает найденные аудиты (id=4, 9, 8)
  ШАГ 3: LLM анализирует результат и принимает решение о следующем шаге

ЗАПУСК:
    pytest tests/integration/test_agent_reasoning_skill.py -v -s

ТРЕБОВАНИЯ:
  - Реальный LLM (не мок), провайдер из infra
  - Реальный навык check_result.vector_search
  - Реальная инфраструктура и ApplicationContext
"""
import json
import pytest
import pytest_asyncio
import logging

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.session_context.session_context import SessionContext
from core.agent.behaviors.react.pattern import ReActPattern
from core.components.action_executor import ActionExecutor
from core.models.enums.common_enums import ExecutionStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_agent_reasoning_skill")


# ============================================================================
# ФИКСТУРЫ (реальная инфраструктура, реальный LLM)
# ============================================================================

@pytest.fixture(scope="module")
def config():
    return get_config(profile='dev', data_dir='data')


@pytest_asyncio.fixture(scope="module")
async def infrastructure(config):
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest_asyncio.fixture(scope="module")
async def app_context(infrastructure):
    app_config = AppConfig.from_discovery(
        profile="dev",
        data_dir=infrastructure.config.data_dir
    )
    ctx = ApplicationContext(
        infrastructure_context=infrastructure,
        config=app_config,
        profile="dev"
    )
    await ctx.initialize()
    yield ctx
    await ctx.shutdown()


@pytest_asyncio.fixture(scope="module")
async def executor(app_context):
    return ActionExecutor(application_context=app_context)


@pytest_asyncio.fixture(scope="module")
async def react_pattern(app_context):
    """Создаём ReActPattern как в реальном агенте."""
    pattern = ReActPattern(application_context=app_context)
    await pattern.initialize()
    return pattern


# ============================================================================
# ТЕСТЫ
# ============================================================================

class TestAgentReasoningWithRealLLM:
    """
    Тесты размышления агента с реальным LLM.

    Имитируем сценарий из логов:
    1) Создаём сессию с целью
    2) Паттерн решает следующее действие (LLM вызывается реально)
    3) Выполняем навык через executor
    4) Проверяем результаты
    """

    @pytest.mark.asyncio
    async def test_reasoning_calls_vector_search(
        self, react_pattern, executor, app_context
    ):
        """
        LLM должен принять решение вызвать check_result.vector_search
        с параметрами, похожими на логи.
        """
        session = SessionContext(
            session_id="test_reasoning_001",
            agent_id="test_agent_reasoning"
        )
        session.set_goal(
            "В каких проверках были описания с нарушениями сроков предоставления отчетности?"
        )

        # ReActPattern.decide() вызывает реальный LLM
        decision = await react_pattern.decide(session)

        logger.info(f"LLM decision: {json.dumps(decision, ensure_ascii=False, indent=2)}")

        # Проверяем структуру решения
        assert "next_action" in decision, "В решении нет next_action"
        assert "parameters" in decision, "В решении нет parameters"

        next_action = decision["next_action"]
        params = decision["parameters"]

        # Ожидаем, что LLM выберет vector_search (как в логах)
        assert "vector_search" in next_action, \
            f"Ожидался vector_search, получен: {next_action}"

        assert "query" in params, "В параметрах нет query"
        assert "source" in params, "В параметрах нет source"

        # source должен быть audits (как в логах)
        assert params["source"] == "audits", \
            f"Ожидался source=audits, получен: {params['source']}"

        print(f"✅ LLM решил вызвать: {next_action}")
        print(f"   Параметры: query='{params.get('query')}', source={params.get('source')}")

    @pytest.mark.asyncio
    async def test_execute_vector_search_skill(self, executor, app_context):
        """
        Выполняем check_result.vector_search с параметрами,
        аналогичными тем, что были в логах.
        """
        session = SessionContext(
            session_id="test_vector_001",
            agent_id="test_agent_vector"
        )
        session.set_goal(
            "В каких проверках были описания с нарушениями сроков предоставления отчетности?"
        )

        # Параметры из логов (шаг 1)
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

        logger.info(f"Skill result status: {result.status}")
        logger.info(f"Skill result data keys: {result.data.keys() if isinstance(result.data, dict) else 'N/A'}")

        # Проверяем что навык выполнился
        assert result.status == ExecutionStatus.COMPLETED, \
            f"Ожидался COMPLETED, но получен {result.status}: {result.error}"

        data = result.data if isinstance(result.data, dict) else result.data.model_dump()

        # Проверяем что есть результаты поиска
        assert "results" in data or "rows" in data, \
            f"Нет результатов в ответе: {data.keys()}"

        results = data.get("results") or data.get("rows") or []
        assert isinstance(results, list), "Результаты должны быть списком"
        assert len(results) > 0, "Результаты поиска пусты"

        # Проверяем структуру найденных документов
        first_result = results[0]
        assert "score" in first_result, "В результате нет score"
        assert "row" in first_result or "audit_id" in first_result, \
            "В результате нет данных об аудите"

        print(f"✅ vector_search вернул {len(results)} результатов")
        for i, r in enumerate(results[:3]):
            audit_id = r.get("audit_id") or r.get("row", {}).get("id")
            title = r.get("title") or r.get("row", {}).get("title")
            print(f"   [{i}] id={audit_id}, title={title}, score={r.get('score', 0):.3f}")

    @pytest.mark.asyncio
    async def test_full_reasoning_and_skill_loop(
        self, react_pattern, executor, app_context
    ):
        """
        Полный цикл: размышление → выполнение навыка → наблюдение → следующее решение.

        Имитируем один шаг агента как в логах.
        """
        session = SessionContext(
            session_id="test_full_loop_001",
            agent_id="test_agent_full_loop"
        )
        session.set_goal(
            "В каких проверках были описания с нарушениями сроков предоставления отчетности?"
        )

        # ШАГ 1: Размышление (LLM решает что делать)
        decision = await react_pattern.decide(session)

        assert "next_action" in decision
        next_action = decision["next_action"]
        params = decision["parameters"]

        logger.info(f"Step 1 - LLM decision: {next_action}")

        # ШАГ 2: Выполняем навык
        result = await executor.execute_action(
            action_name=next_action,
            parameters=params,
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, \
            f"Skill execution failed: {result.error}"

        # Сохраняем наблюдение в сессии (как делает агент)
        session.record_observation(
            result.data if isinstance(result.data, dict) else result.data.model_dump(),
            source=next_action,
            step_number=1
        )

        # Регистрируем шаг
        from core.models.enums.common_enums import ExecutionStatus as ES
        session.register_step(
            step_number=1,
            capability_name=next_action,
            skill_name=next_action.split(".")[0],
            action_item_id="auto_1",
            observation_item_ids=[],
            summary=f"Step 1: {next_action}",
            status=ES.COMPLETED
        )

        # ШАГ 3: Следующее размышление (LLM анализирует результат)
        decision2 = await react_pattern.decide(session)

        logger.info(f"Step 2 - LLM decision after observation: {json.dumps(decision2, ensure_ascii=False)}")

        assert "next_action" in decision2, "Второе решение должно содержать next_action"
        assert "stop_condition" in decision2, "Второе решение должно содержать stop_condition"

        print(f"✅ Полный цикл: размышление → навык → наблюдение → следующее решение")
        print(f"   Шаг 1: {next_action} → {result.status}")
        print(f"   Шаг 2 decision: next_action={decision2.get('next_action')}, stop={decision2.get('stop_condition')}")


class TestVectorSearchSkillIntegration:
    """
    Интеграционные тесты vector_search навыка с реальными данными.
    """

    @pytest.mark.asyncio
    async def test_vector_search_returns_audit_ids_from_logs(self, executor):
        """
        Проверяем что vector_search возвращает аудиты,
        упоминавшиеся в логах (id=4, 9, 8).
        """
        session = SessionContext(
            session_id="test_audit_ids_001",
            agent_id="test_agent_audit_ids"
        )

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

        assert result.status == ExecutionStatus.COMPLETED

        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        results = data.get("results") or data.get("rows") or []

        # Собираем ID найденных аудитов
        audit_ids = []
        for r in results:
            aid = r.get("audit_id") or r.get("row", {}).get("id")
            if aid and aid not in audit_ids:
                audit_ids.append(aid)

        logger.info(f"Found audit IDs: {audit_ids}")

        # В логах были id=4, 9, 8 - они должны быть найдены
        assert 4 in audit_ids, f"Аудит 4 (трудовое законодательство) не найден в {audit_ids}"
        assert 9 in audit_ids, f"Аудит 9 (управление рисками) не найден в {audit_ids}"

        print(f"✅ Найдены ожидаемые аудиты: {audit_ids}")

    @pytest.mark.asyncio
    async def test_vector_search_with_different_queries(self, executor):
        """
        Проверяем что vector_search работает с разными запросами.
        """
        session = SessionContext(
            session_id="test_queries_001",
            agent_id="test_agent_queries"
        )

        queries = [
            "нарушения сроков",
            "трудовое законодательство",
            "аудит управления рисками"
        ]

        for query in queries:
            result = await executor.execute_action(
                action_name="check_result.vector_search",
                parameters={
                    "query": query,
                    "source": "audits",
                    "top_k": 5,
                    "min_score": 0.3
                },
                context=session
            )

            assert result.status == ExecutionStatus.COMPLETED, \
                f"Query '{query}' failed: {result.error}"

            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            results = data.get("results") or data.get("rows") or []

            assert len(results) > 0, f"Query '{query}' вернул пустой результат"

            print(f"✅ Query '{query}': {len(results)} результатов")

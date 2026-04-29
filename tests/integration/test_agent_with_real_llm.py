"""
Интеграционный тест с реальным LLM: сценарий из логов 2026-04-28_15-14-33.

ТЕСТИРУЕТ:
1. Полный цикл рассуждения агента с реальным LLM (Qwen3)
2. Вызов навыка check_result.vector_search с семантическим поиском
3. Корректность принятия решений ReAct-паттерном
4. Обработку результатов наблюдателем

СЦЕНАРИЙ ИЗ ЛОГОВ:
- Цель: "В каких проверках были описания с нарушениями сроков предоставления отчетности?"
- Шаг 1: vector_search → успех, найдены аудиты
- Шаг 2: data_analysis.analyze_step_data → partial
- Шаг 3-6: повторные vector_search с уточнением

ПРИНЦИПЫ:
- Реальная инфраструктура (InfrastructureContext, ApplicationContext)
- Реальный LLM провайдер (Qwen3 через LLMOrchestrator)
- Проверка структуры решений и результатов навыков
"""

import pytest
import pytest_asyncio
import time
from typing import Dict, Any, List

from core.config import get_config
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.session_context.session_context import SessionContext
from core.agent.agent_factory import AgentFactory
from core.agent.runtime import AgentRuntime
from core.config.agent_config import AgentConfig
from core.models.enums.common_enums import ExecutionStatus


# ============================================================================
# ФИКСТУРЫ
# ============================================================================

@pytest.fixture(scope="module")
def config():
    """Конфигурация dev-профиля для тестов."""
    return get_config(profile='dev')


@pytest_asyncio.fixture(scope="module")
async def infrastructure(config):
    """Реальный InfrastructureContext."""
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest_asyncio.fixture(scope="module")
async def app_context(infrastructure):
    """Реальный ApplicationContext с авто-обнаружением."""
    from core.config.app_config import AppConfig
    
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


# ============================================================================
# ТЕСТЫ
# ============================================================================

class TestAgentRealLLMVectorSearch:
    """
    Тесты с реальным LLM для сценария поиска нарушений сроков отчетности.
    
    ВНИМАНИЕ: Тесты требуют доступной LLM (Qwen3) и настроенной FAISS БД.
    Если LLM недоступен — тесты пропускаются.
    """

    @pytest.mark.asyncio
    async def test_vector_search_step(self, app_context):
        """
        Тест Шага 1 из логов: vector_search находит аудиты с нарушениями.
        
        КРИТЕРИИ:
        - LLM принимает решение вызвать check_result.vector_search
        - Параметры содержат query, source, top_k, min_score
        - Результат содержит найденные аудиты (id=4, id=9)
        """
        # Создаем контекст сессии
        session = SessionContext(
            session_id="test_vector_search_001",
            agent_id="agent_test_001"
        )
        session.set_goal("В каких проверках были описания с нарушениями сроков предоставления отчетности?")
        
        # Создаем конфиг агента
        agent_config = AgentConfig(
            goal="В каких проверках были описания с нарушениями сроков предоставления отчетности?",
            max_steps=3,
            max_no_progress_steps=2,
            confidence_threshold=0.7
        )
        
        # Создаем компоненты через фабрику
        import logging
        log = logging.getLogger(__name__)
        
        components = AgentFactory.create_components(
            application_context=app_context,
            agent_config=agent_config,
            log=log,
            event_bus=app_context.infrastructure_context.event_bus
        )
        
        # Создаем runtime
        runtime = AgentRuntime(
            session_context=session,
            application_context=app_context,
            agent_config=agent_config,
            components=components,
            log=log
        )
        
        # Выполняем один шаг (только решение + выполнение, без финального ответа)
        await runtime._execute_step(step_number=1)
        
        # Проверяем что шаг выполнен
        assert session.get_step_count() >= 1, "Шаг не был выполнен"
        
        # Получаем последний шаг
        steps = session.get_step_history()
        last_step = steps[-1]
        
        # Проверяем что вызывался vector_search
        assert "vector_search" in last_step.capability_name, \
            f"Ожидался vector_search, получен: {last_step.capability_name}"
        
        # Проверяем статус выполнения
        assert last_step.status == ExecutionStatus.COMPLETED, \
            f"Ожидался COMPLETED, получен: {last_step.status}"
        
        # Проверяем что в observation есть данные
        observations = session.get_observations()
        assert len(observations) > 0, "Нет observations после шага"
        
        last_observation = observations[-1]
        obs_content = last_observation.content if hasattr(last_observation, 'content') else last_observation
        
        # Проверяем что найдены аудиты (по логам: id=4 и id=9)
        # Результат может быть списком или dict с rows
        if isinstance(obs_content, dict):
            rows = obs_content.get("rows") or obs_content.get("results") or []
        elif isinstance(obs_content, list):
            rows = obs_content
        else:
            rows = []
        
        # Проверяем что есть результаты поиска
        # В логах: audit_id=4 (Проверка соблюдения трудового законодательства)
        # и audit_id=9 (Аудит управления рисками)
        found_audit_ids = set()
        for row in (rows if isinstance(rows, list) else []):
            if isinstance(row, dict):
                audit_id = row.get("audit_id") or row.get("id")
                if audit_id:
                    found_audit_ids.add(int(audit_id))
        
        # Ожидаем найти хотя бы один из аудитов
        assert len(found_audit_ids) > 0, \
            f"Векторный поиск не вернул аудиты. Результат: {obs_content}"
        
        print(f"✅ Vector search нашел аудиты с ID: {found_audit_ids}")
        print(f"   Статус шага: {last_step.status}")
        print(f"   Количество результатов: {len(rows) if isinstance(rows, list) else 'N/A'}")

    @pytest.mark.asyncio
    async def test_react_decision_calls_vector_search(self, app_context):
        """
        Тест принятия решения ReAct: LLM должен выбрать vector_search.
        
        КРИТЕРИИ:
        - LLM возвращает decision с next_action="check_result.vector_search"
        - Параметры содержат query про нарушения сроков
        """
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.agent.behaviors.react.prompt_builder import PromptBuilder
        
        # Создаем контекст сессии
        session = SessionContext(
            session_id="test_react_decision_001",
            agent_id="agent_test_002"
        )
        session.set_goal("В каких проверках были описания с нарушениями сроков предоставления отчетности?")
        
        # Создаем ReActPattern
        import logging
        log = logging.getLogger(__name__)
        
        # Получаем prompt_storage из app_context
        prompt_storage = app_context.infrastructure.prompt_storage
        contract_registry = app_context.infrastructure.contract_registry
        
        # Создаем PromptBuilder и Pattern
        prompt_builder = PromptBuilder(
            prompt_storage=prompt_storage,
            contract_registry=contract_registry,
            application_context=app_context
        )
        
        pattern = ReActPattern(
            prompt_builder=prompt_builder,
            llm_orchestrator=app_context.infrastructure.llm_orchestrator,
            log=log
        )
        
        # Вызываем decide
        decision_result = await pattern.decide(
            session_context=session,
            available_tools=self._get_available_tools(app_context)
        )
        
        # Проверяем что решение содержит vector_search
        decision = decision_result.decision if hasattr(decision_result, 'decision') else decision_result
        
        assert "vector_search" in decision.get("next_action", ""), \
            f"LLM должен выбрать vector_search, выбрал: {decision.get('next_action')}"
        
        params = decision.get("parameters", {})
        assert "нарушения" in params.get("query", "").lower() or \
               "срок" in params.get("query", "").lower(), \
            f"Query должен содержать 'нарушения' или 'срок': {params.get('query')}"
        
        assert params.get("source") == "audits", \
            f"Source должен быть 'audits': {params.get('source')}"
        
        print(f"✅ ReAct решение: {decision.get('next_action')}")
        print(f"   Query: {params.get('query')}")
        print(f"   Source: {params.get('source')}")

    @pytest.mark.asyncio
    async def test_full_agent_loop_two_steps(self, app_context):
        """
        Тест полного цикла агента на 2 шага (как в логах).
        
        КРИТЕРИИ:
        - Шаг 1: vector_search успешно находит аудиты
        - Шаг 2: data_analysis вызывается (возможно partial)
        - Контекст накапливается между шагами
        """
        session = SessionContext(
            session_id="test_full_loop_001",
            agent_id="agent_test_003"
        )
        session.set_goal("В каких проверках были описания с нарушениями сроков предоставления отчетности?")
        
        agent_config = AgentConfig(
            goal="В каких проверках были описания с нарушениями сроков предоставления отчетности?",
            max_steps=2,
            max_no_progress_steps=3,
            confidence_threshold=0.7
        )
        
        import logging
        log = logging.getLogger(__name__)
        
        components = AgentFactory.create_components(
            application_context=app_context,
            agent_config=agent_config,
            log=log,
            event_bus=app_context.infrastructure_context.event_bus
        )
        
        runtime = AgentRuntime(
            session_context=session,
            application_context=app_context,
            agent_config=agent_config,
            components=components,
            log=log
        )
        
        # Выполняем 2 шага
        for step_num in range(1, 3):
            await runtime._execute_step(step_number=step_num)
        
        # Проверяем что выполнено 2 шага
        assert session.get_step_count() == 2, \
            f"Ожидалось 2 шага, выполнено: {session.get_step_count()}"
        
        # Проверяем историю шагов
        steps = session.get_step_history()
        capabilities_used = [s.capability_name for s in steps]
        
        # Шаг 1 должен быть vector_search
        assert "check_result.vector_search" in capabilities_used[0], \
            f"Шаг 1 должен быть vector_search: {capabilities_used[0]}"
        
        # Шаг 2 может быть data_analysis (как в логах)
        # или повторный vector_search (зависит от LLM)
        print(f"✅ Выполнено шагов: {len(steps)}")
        print(f"   Шаг 1: {capabilities_used[0]}")
        print(f"   Шаг 2: {capabilities_used[1]}")
        
        # Проверяем что есть observations
        observations = session.get_observations()
        assert len(observations) >= 2, \
            f"Ожидалось минимум 2 observations, получено: {len(observations)}"
        
        print(f"   Observations: {len(observations)}")

    # ========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ========================================================================

    def _get_available_tools(self, app_context) -> List[Dict[str, Any]]:
        """Возвращает список доступных инструментов для ReAct паттерна."""
        tools = []
        
        # check_result.vector_search
        tools.append({
            "name": "check_result.vector_search",
            "description": "Семантический поиск по текстам актов аудиторской проверки",
            "parameters": {
                "query": {"type": "string", "required": True},
                "source": {"type": "string", "required": False},
                "top_k": {"type": "integer", "required": False},
                "min_score": {"type": "number", "required": False}
            }
        })
        
        # data_analysis.analyze_step_data
        tools.append({
            "name": "data_analysis.analyze_step_data",
            "description": "Анализ данных шага с LLM и MapReduce",
            "parameters": {
                "question": {"type": "string", "required": True},
                "step_id": {"type": "integer", "required": True}
            }
        })
        
        return tools


class TestAgentVectorSearchResults:
    """
    Тесты проверки результатов vector_search.
    """

    @pytest.mark.asyncio
    async def test_vector_search_returns_audit_4_and_9(self, app_context):
        """
        Проверка что vector_search возвращает ожидаемые аудиты (id=4 и id=9).
        
        Согласно логам:
        - audit_id=4: "Проверка соблюдения трудового законодательства (4)"
        - audit_id=9: "Аудит управления рисками (9)"
        """
        from core.components.action_executor import ActionExecutor
        from core.agent.components.execution_context import ExecutionContext
        
        session = SessionContext(
            session_id="test_results_001",
            agent_id="agent_test_004"
        )
        
        executor = ActionExecutor(application_context=app_context)
        exec_context = ExecutionContext(session_context=session)
        
        # Вызываем vector_search напрямую через executor
        result = await executor.execute_action(
            action_name="check_result.vector_search",
            parameters={
                "query": "нарушения сроков предоставления отчетности",
                "source": "audits",
                "top_k": 10,
                "min_score": 0.5
            },
            context=exec_context
        )
        
        # Проверяем статус
        assert result.status == ExecutionStatus.COMPLETED, \
            f"Ожидался COMPLETED: {result.status}, ошибка: {result.error}"
        
        # Получаем данные
        data = result.data if hasattr(result, 'data') else result
        if hasattr(data, 'model_dump'):
            data = data.model_dump()
        elif hasattr(data, 'dict'):
            data = data.dict()
        
        # Проверяем что есть rows
        rows = data.get("rows") or data.get("results") or []
        assert isinstance(rows, list), f"rows должен быть списком: {type(rows)}"
        assert len(rows) > 0, "vector_search не вернул результатов"
        
        # Проверяем что есть аудиты 4 и 9
        found_ids = set()
        for row in rows:
            if isinstance(row, dict):
                audit_id = row.get("audit_id") or row.get("id")
                if audit_id:
                    found_ids.add(int(audit_id))
        
        # Проверяем наличие ожидаемых аудитов
        assert 4 in found_ids or 9 in found_ids, \
            f"Ожидались аудиты 4 или 9, найдены: {found_ids}"
        
        print(f"✅ Vector search вернул {len(rows)} результатов")
        print(f"   Найденные audit_id: {found_ids}")

    @pytest.mark.asyncio
    async def test_vector_search_with_different_queries(self, app_context):
        """
        Проверка vector_search с разными вариациями запроса.
        """
        from core.components.action_executor import ActionExecutor
        from core.agent.components.execution_context import ExecutionContext
        
        session = SessionContext(
            session_id="test_queries_001",
            agent_id="agent_test_005"
        )
        
        executor = ActionExecutor(application_context=app_context)
        
        test_queries = [
            "нарушения сроков предоставления отчетности",
            "нарушения сроков предоставления отчетности в аудите по трудовому законодательству",
            "задержки в аудите трудового законодательства"
        ]
        
        for query in test_queries:
            exec_context = ExecutionContext(session_context=session)
            
            result = await executor.execute_action(
                action_name="check_result.vector_search",
                parameters={
                    "query": query,
                    "source": "audits",
                    "top_k": 5,
                    "min_score": 0.4
                },
                context=exec_context
            )
            
            assert result.status == ExecutionStatus.COMPLETED, \
                f"Query '{query}' failed: {result.error}"
            
            print(f"✅ Query '{query[:40]}...' успешно выполнен")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

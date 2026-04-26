"""
Интеграционные тесты для FinalAnswerSkill.

ЗАПУСК:
  Все тесты:           pytest tests/integration/test_final_answer.py -v -s
  Конкретный тест:     pytest tests/integration/test_final_answer.py::TestFinalAnswerSkillIntegration::test_final_answer_simple -v -s

ПРИНЦИПЫ:
- Реальные контексты (InfrastructureContext, ApplicationContext)
- Использует executor для вызова навыка
- Реальный LLM (5-7 минут на тест)
"""
import pytest
import pytest_asyncio

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.components.action_executor import ActionExecutor
from core.session_context.session_context import SessionContext
from core.models.enums.common_enums import ExecutionStatus


# ============================================================================
# ФИКСТУРЫ
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
async def executor(app_context):
    return ActionExecutor(application_context=app_context)


@pytest.fixture
def session():
    return SessionContext()


# ============================================================================
# FINAL ANSWER SKILL TESTS
# ============================================================================

class TestFinalAnswerSkillIntegration:
    """Final Answer Skill — интеграционные тесты."""

    @pytest.mark.asyncio
    async def test_final_answer_simple(self, executor, session):
        """Простой тест генерации финального ответа."""
        session.set_goal("Узнать количество глав в книге")
        
        # Наполняем контекст наблюдениями и шагами
        session.record_observation(
            "В библиотеке найдена книга с book_id=5. Количество глав: 15",
            source="sql_query"
        )
        session.record_action(
            "SELECT COUNT(*) as chapter_count FROM Lib.chapters WHERE book_id = 5",
            step_number=1
        )
        
        result = await executor.execute_action(
            action_name="final_answer.generate",
            parameters={
                "goal": "Узнать количество глав в книге",
                "decision_reasoning": "Пользователь хочет получить общее количество глав",
                "is_fallback": False,
                "executed_steps": 1,
                "format_type": "detailed"
            },
            context=session
        )
        
        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        assert "final_answer" in data or "answer" in data
        answer_text = data.get("final_answer") or data.get("answer", "")
        assert len(answer_text) > 0

    @pytest.mark.asyncio
    async def test_final_answer_with_history(self, executor, session):
        """Тест с историей диалога и наблюдениями."""
        session.set_goal("Проанализировать данные о книгах")
        
        # Наполняем контекст
        session.record_observation("Найдено 50 книг в библиотеке", source="sql_query")
        session.record_observation("Самая популярная книга имеет 100 загрузок", source="sql_query")
        session.record_observation("Всего 10 авторов", source="sql_query")
        session.record_action("SELECT COUNT(*) FROM Lib.books", step_number=1)
        session.record_action("SELECT book_id, download_count FROM Lib.books ORDER BY download_count DESC LIMIT 1", step_number=2)
        session.record_action("SELECT COUNT(DISTINCT author_id) FROM Lib.books", step_number=3)
        
        result = await executor.execute_action(
            action_name="final_answer.generate",
            parameters={
                "goal": "Проанализировать данные о книгах",
                "decision_reasoning": "Требуется完整的 анализ",
                "is_fallback": False,
                "executed_steps": 3,
                "format_type": "detailed",
                "include_steps": True,
                "include_evidence": True
            },
            context=session
        )
        
        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_final_answer_fallback_mode(self, executor, session):
        """Тест fallback режима."""
        session.set_goal("Найти информацию")
        
        # Fallback - данные не найдены
        session.record_observation("Данные не найдены - таблица пуста", source="sql_query")
        
        result = await executor.execute_action(
            action_name="final_answer.generate",
            parameters={
                "goal": "Найти информацию",
                "decision_reasoning": "Не удалось найти точные данные",
                "is_fallback": True,
                "executed_steps": 0,
                "format_type": "concise"
            },
            context=session
        )
        
        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_final_answer_minimal_params(self, executor, session):
        """Тест с минимальными параметрами."""
        session.set_goal("Тестовый вопрос")
        
        result = await executor.execute_action(
            action_name="final_answer.generate",
            parameters={
                "goal": "Тестовый вопрос",
                "decision_reasoning": "",
                "is_fallback": False,
                "executed_steps": 1,
                "format_type": "concise"
            },
            context=session
        )
        
        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
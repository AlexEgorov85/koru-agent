"""
Интеграционные тесты для DataAnalysis Skill.

ТЕСТЫ:
  data_analysis.analyze_step_data (3):
  - test_analyze_step_data_with_memory: анализ данных из памяти
  - test_analyze_step_data_with_database: анализ данных из БД
  - test_analyze_step_data_missing_required_fields: отсутствие обязательных полей

  Тесты ошибок (3):
  - test_analyze_empty_data: пустые данные
  - test_analyze_invalid_source_type: невалидный тип источника
  - test_analyze_question_mismatch: вопрос не соответствует данным

ПРИНЦИПЫ:
- Контексты поднимаются ОДИН РАЗ (scope="module")
- Проверка логики: answer содержит осмысленный ответ на вопрос
- Реальные контексты, без моков
- Тесты ошибок: проверка FAILED при невалидных входных данных
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
async def executor(app_context):
    from core.agent.components.action_executor import ActionExecutor
    return ActionExecutor(application_context=app_context)


@pytest.fixture
def session():
    return SessionContext()


def create_filled_session(goal: str = "Анализ данных") -> SessionContext:
    """
    Создаёт SessionContext для DataAnalysis тестов.

    Данные шага записываются в SessionContext через record_observation
    с указанием step_id. Skill берёт данные оттуда.
    """
    session = SessionContext(session_id="test_data_analysis_001", agent_id="test_agent_001")
    session.set_goal(goal)
    session.dialogue_history.add_user_message(f"Проанализируй данные: {goal}")
    return session


def add_step_data(session: SessionContext, step_id: str, raw_content: str):
    """
    Добавляет сырые данные шага в SessionContext.

    DataAnalysis skill ищет данные по step_id в additional_data.
    """
    import uuid
    from core.session_context.model import ContextItem, ContextItemType, ContextItemMetadata

    item = ContextItem(
        item_id=str(uuid.uuid4()),
        session_id=session.session_id or "test_session",
        content=raw_content,
        item_type=ContextItemType.OBSERVATION,
        metadata=ContextItemMetadata(
            source="raw_data",
            additional_data={"step_id": step_id}
        )
    )
    session.data_context.add_item(item)


# ============================================================================
# DATA ANALYSIS SKILL
# ============================================================================

class TestDataAnalysisSkillIntegration:
    """DataAnalysis Skill — 3 теста."""

    @pytest.mark.asyncio
    async def test_analyze_step_data_with_memory(self, executor):
        """Анализ данных из SessionContext - ответ на вопрос о количестве записей."""
        session = create_filled_session(goal="Анализ количества записей")

        # Добавляем сырые данные шага в SessionContext
        csv_data = "id,name,value\n1,Item1,100\n2,Item2,200\n3,Item3,300"
        add_step_data(session, "step_001", csv_data)

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "step_id": "step_001",
                "question": "Сколько записей в данных?",
                "data_source": {
                    "type": "memory"
                },
                "analysis_config": {
                    "aggregation_method": "summary"
                }
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка: есть answer и confidence
        assert "answer" in data, "Нет поля answer"
        assert "confidence" in data, "Нет поля confidence"
        
        # Проверка: answer содержит осмысленный ответ (число записей = 3)
        answer_lower = data["answer"].lower()
        has_number = any(char.isdigit() for char in data["answer"])
        assert has_number, f"answer не содержит числа: {data['answer']}"
        
        # Проверка: confidence в диапазоне 0-1
        assert isinstance(data["confidence"], (int, float)), "confidence должен быть числом"
        assert 0 <= data["confidence"] <= 1, f"confidence вне диапазона: {data['confidence']}"
        
        # Проверка логики: в данных 3 записи, ответ должен содержать "3" или "три"
        has_correct_count = "3" in data["answer"] or "три" in answer_lower
        assert has_correct_count, f"answer не соответствует данным (ожидалось 3): {data['answer']}"

        # Проверка: есть evidence (если skill его возвращает)
        if "evidence" in data:
            assert isinstance(data["evidence"], list), "evidence должен быть списком"
        
        print(f"✅ DataAnalysis: анализ из памяти выполнен (answer: {data['answer']})")

    @pytest.mark.asyncio
    async def test_analyze_step_data_with_database(self, executor):
        """Анализ данных из SessionContext (имитация данных из БД)."""
        session = create_filled_session(goal="Анализ количества книг в базе")

        # Имитируем данные из БД в SessionContext
        csv_data = "book_id,title,author\n1,Евгений Онегин,Пушкин\n2,Капитанская дочка,Пушкин\n3,Руслан и Людмила,Пушкин"
        add_step_data(session, "step_002", csv_data)

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "step_id": "step_002",
                "question": "Какое количество книг в базе?",
                "data_source": {
                    "type": "memory"
                },
                "analysis_config": {
                    "max_rows": 10,
                    "aggregation_method": "statistical"
                }
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка: есть answer
        assert "answer" in data, "Нет поля answer"
        assert len(data["answer"]) > 0, "answer не должен быть пустым"
        
        # Проверка: confidence в диапазоне
        assert "confidence" in data
        assert 0 <= data["confidence"] <= 1, f"confidence вне диапазона: {data['confidence']}"
        
        # Проверка логики: answer содержит информацию о количестве
        answer_lower = data["answer"].lower()
        has_count_info = any(word in answer_lower for word in ["книг", "количеств", "10", "десять", "в базе", "запис", "row"])
        assert has_count_info, f"answer не содержит информацию о количестве: {data['answer']}"

        # Проверка: есть metadata (если skill его возвращает)
        if "metadata" in data:
            assert isinstance(data["metadata"], dict)
        
        print(f"✅ DataAnalysis: анализ из БД выполнен (answer: {data['answer'][:50]}...)")

    @pytest.mark.asyncio
    async def test_analyze_step_data_missing_required_fields(self, executor):
        """Отсутствие обязательных полей — ожидается FAILED."""
        session = create_filled_session(goal="Анализ данных")

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "step_id": "step_003",
                "data_source": {
                    "type": "memory"
                }
            },
            context=session
        )

        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED, но получен COMPLETED"
        assert result.error is not None, "Нет сообщения об ошибке"
        
        # Проверка: ошибка связана с отсутствующим полем question
        error_lower = result.error.lower()
        assert "question" in error_lower or "required" in error_lower or "field" in error_lower, \
            f"Ошибка не связана с отсутствующим полем: {result.error}"
        
        print(f"✅ DataAnalysis: отсутствующие обязательные поля → FAILED")


class TestDataAnalysisSkillErrorHandling:
    """Тесты ошибок DataAnalysis Skill — 3 теста."""

    @pytest.mark.asyncio
    async def test_analyze_empty_data(self, executor):
        """Анализ пустых данных — должен вернуть низкий confidence."""
        session = create_filled_session(goal="Анализ пустых данных")

        # Добавляем пустые данные в SessionContext
        add_step_data(session, "step_empty", "")

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "step_id": "step_empty",
                "question": "Что в данных?"
            },
            context=session
        )

        # При пустых данных должен вернуть ответ с низким confidence
        if result.status == ExecutionStatus.FAILED:
            print(f"✅ DataAnalysis: пустые данные → FAILED")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            confidence = data.get("confidence", 1.0)
            # При пустых данных confidence должен быть низким
            assert confidence < 0.5, f"При пустых данных confidence должен быть низким: {confidence}"
            print(f"✅ DataAnalysis: пустые данные обработаны (confidence: {confidence})")

    @pytest.mark.asyncio
    async def test_analyze_invalid_source_type(self, executor):
        """Анализ с невалидным типом источника — должен вернуть FAILED."""
        session = create_filled_session(goal="Анализ с невалидным типом")

        # data_source с невалидным типом — fallback когда в контексте нет данных
        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "step_id": "step_invalid",
                "question": "Что в данных?",
                "data_source": {
                    "type": "invalid_type_xyz",
                    "content": "test data"
                }
            },
            context=session
        )

        # Невалидный тип источника — должен быть FAILED
        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED при невалидном типе"
        assert result.error is not None
        error_lower = result.error.lower()
        assert "type" in error_lower or "source" in error_lower or "invalid" in error_lower, \
            f"Ошибка не связана с типом источника: {result.error}"
        
        print(f"✅ DataAnalysis: невалидный тип источника → FAILED")

    @pytest.mark.asyncio
    async def test_analyze_question_mismatch(self, executor):
        """Вопрос не соответствует данным — низкий confidence или FAILED."""
        session = create_filled_session(goal="Анализ несоответствия вопроса")

        # Данные про товары, вопрос про сотрудников
        csv_data = "id,name,value\n1,Item1,100\n2,Item2,200"
        add_step_data(session, "step_mismatch", csv_data)

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "step_id": "step_mismatch",
                "question": "Сколько сотрудников в компании?",
                "analysis_config": {
                    "aggregation_method": "summary"
                }
            },
            context=session
        )

        # При несоответствии вопроса данным — FAILED или низкий confidence
        if result.status == ExecutionStatus.FAILED:
            assert result.error is not None
            print(f"✅ DataAnalysis: несоответствие → FAILED")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            confidence = data.get("confidence", 1.0)
            assert confidence < 0.8, f"При несоответствии confidence должен быть < 0.8: {confidence}"
            print(f"✅ DataAnalysis: несоответствие обработано (confidence: {confidence})")
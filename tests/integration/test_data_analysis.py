"""
Интеграционные тесты для DataAnalysis Skill.

ТЕСТЫ:
  data_analysis.analyze_step_data:
  - test_analyze_step_data_with_csv_rows: анализ CSV-данных (строк)
  - test_analyze_step_data_with_text: анализ текстовых данных
  - test_analyze_step_data_missing_required_fields: отсутствие обязательных полей
  - test_analyze_step_data_not_found: шаг не найден в контексте

ПРИНЦИПЫ:
- Правильное создание контекста (как в реальном агенте)
- Проверка логики: answer содержит осмысленный ответ на вопрос
- Реальные контексты, без моков
- Тесты ошибок: проверка FAILED при невалидных входных данных
"""
import uuid
import pytest
import pytest_asyncio

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.session_context.session_context import SessionContext
from core.session_context.model import ContextItemMetadata
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
async def executor(app_context):
    from core.components.action_executor import ActionExecutor
    return ActionExecutor(application_context=app_context)


@pytest.fixture
def session():
    return SessionContext()


def create_filled_session(
    goal: str = "Анализ данных",
    session_id: str = "test_data_analysis_001",
    agent_id: str = "test_agent_001"
) -> SessionContext:
    """
    Создаёт SessionContext для DataAnalysis тестов.
    
    Имитирует работу агента: создаёт сессию с целью и историей диалога.
    """
    session = SessionContext(session_id=session_id, agent_id=agent_id)
    session.set_goal(goal)
    session.dialogue_history.add_user_message(f"Проанализируй данные: {goal}")
    return session


def add_step_with_data(
    session: SessionContext,
    step_number: int,
    raw_content: Any,
    capability_name: str = "sql_tool.execute",
    skill_name: str = "sql_tool"
) -> str:
    """
    Имитирует работу агента: создаёт шаг и добавляет данные в контекст.
    
    Как это работает в реальном агенте:
    1. Инструмент/навык выполняется и записывает результат через record_observation
    2. Агент регистрирует шаг через register_step с ссылкой на observation_item_ids
    
    ВОЗВРАЩАЕТ:
    - step_number (для передачи в data_analysis.analyze_step_data)
    """
    # 1. Записываем результат в контекст (как это делает инструмент)
    obs_id = session.record_observation(
        observation_data=raw_content,
        source=skill_name,
        step_number=step_number,
        metadata=ContextItemMetadata(
            source=skill_name,
            step_number=step_number,
            confidence=0.9
        )
    )
    
    # 2. Регистрируем шаг (как это делает AgentRuntime)
    session.register_step(
        step_number=step_number,
        capability_name=capability_name,
        skill_name=skill_name,
        action_item_id=str(uuid.uuid4()),
        observation_item_ids=[obs_id],
        obs_text=f"Получены данные на шаге {step_number}",
        status=ExecutionStatus.COMPLETED
    )
    
    return step_number


# ============================================================================
# DATA ANALYSIS SKILL
# ============================================================================

class TestDataAnalysisSkillIntegration:
    """DataAnalysis Skill — интеграционные тесты с реальным контекстом."""

    @pytest.mark.asyncio
    async def test_analyze_step_data_with_csv_rows(self, executor):
        """Анализ CSV-данных (строк) из SessionContext.
        
        Сценарий:
        1. Агент выполнил SQL-запрос (шаг 1) и получил данные
        2. Данные сохранены в контекст через record_observation
        3. Шаг зарегистрирован через register_step
        4. DataAnalysis анализирует данные через MapReduce
        """
        session = create_filled_session(goal="Анализ количества записей")

        # Имитируем данные от SQL-инструмента (список словарей)
        rows = [
            {"id": 1, "name": "Item1", "value": 100},
            {"id": 2, "name": "Item2", "value": 200},
            {"id": 3, "name": "Item3", "value": 300},
        ]
        
        # Создаём шаг с данными (как это делает агент)
        step_num = add_step_with_data(
            session=session,
            step_number=1,
            raw_content=rows,
            capability_name="sql_tool.execute",
            skill_name="sql_tool"
        )

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "question": "Какие ключевые темы и тренды в данных?",
                "step_id": step_num,
                "mode": "mapreduce",
            },
            context=ExecutionContext(session_context=session)
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка структуры ответа
        assert "answer" in data, "Нет поля answer"
        assert "confidence" in data, "Нет поля confidence"
        assert "metadata" in data, "Нет поля metadata"
        
        # Проверка: answer содержит осмысленный ответ
        answer = data["answer"]
        assert len(answer) > 20, f"answer слишком короткий: {answer}"
        
        # Проверка: confidence в диапазоне 0-1
        assert isinstance(data["confidence"], (int, float)), "confidence должен быть числом"
        assert 0 <= data["confidence"] <= 1, f"confidence вне диапазона: {data['confidence']}"
        
        # Проверка метаданных
        metadata = data["metadata"]
        assert metadata.get("mode_used") == "mapreduce", f"Ожидался режим mapreduce, получен {metadata.get('mode_used')}"
        assert "chunks_created" in metadata, "Нет информации о созданных чанках"
        assert "processing_time_ms" in metadata, "Нет времени обработки"
        
        print(f"✅ DataAnalysis: анализ CSV-данных выполнен (answer: {answer[:100]}...)")

    @pytest.mark.asyncio
    async def test_analyze_step_data_with_text(self, executor):
        """Анализ текстовых данных из SessionContext."""
        session = create_filled_session(goal="Анализ текстового отчёта")

        # Имитируем текстовые данные
        text_data = """
        Отчёт по продажам за март 2026.
        
        Регион МСК: Закрыто 3 сделки на сумму 58701.25 рублей.
        Регион СПБ: Закрыто 2 сделки на сумму 30400 рублей.
        Регион ЕКБ: 1 сделка в статусе failed.
        """
        
        step_num = add_step_with_data(
            session=session,
            step_number=2,
            raw_content=text_data,
            capability_name="document_tool.process",
            skill_name="document_tool"
        )

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "question": "Какие проблемы и тренды по регионам?",
                "step_id": step_num,
                "mode": "mapreduce",
            },
            context=ExecutionContext(session_context=session)
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        answer = data["answer"]
        assert len(answer) > 20, f"answer слишком короткий: {answer}"
        
        print(f"✅ DataAnalysis: анализ текста выполнен (answer: {answer[:100]}...)")

    @pytest.mark.asyncio
    async def test_analyze_step_data_missing_required_fields(self, executor):
        """Отсутствие обязательных полей — ожидается FAILED."""
        session = create_filled_session(goal="Анализ данных")

        # Без question
        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "step_id": 999,  # Несуществующий шаг
            },
            context=ExecutionContext(session_context=session)
        )

        # Если нет question - ошибка валидации
        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED при отсутствии question"
        assert "question" in (result.error or "").lower(), f"Ошибка должна быть про question: {result.error}"
        
        print(f"✅ DataAnalysis: отсутствующее поле question → FAILED")

    @pytest.mark.asyncio
    async def test_analyze_step_data_not_found(self, executor):
        """Шаг не найден в контексте — ожидается FAILED."""
        session = create_filled_session(goal="Анализ данных")

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "question": "Что в данных?",
                "step_id": 999,
            },
            context=ExecutionContext(session_context=session)
        )

        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED при отсутствии шага"
        assert "не найдены" in (result.error or "").lower() or "not found" in (result.error or "").lower(), \
            f"Ошибка должна быть про отсутствие данных: {result.error}"
        
        print(f"✅ DataAnalysis: несуществующий step_id → FAILED")


class TestDataAnalysisSkillErrorHandling:
    """Тесты обработки ошибок и краевых случаев."""

    @pytest.mark.asyncio
    async def test_analyze_empty_data(self, executor):
        """Анализ пустых данных — навык должен вернуть ответ о отсутствии данных."""
        session = create_filled_session(goal="Анализ пустых данных")

        # Создаём шаг с пустым списком (имитирует SQL без результатов)
        step_num = add_step_with_data(
            session=session,
            step_number=3,
            raw_content=[],  # Пустой список
            capability_name="sql_tool.execute",
            skill_name="sql_tool"
        )

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "question": "Что в данных?",
                "step_id": step_num,
                "mode": "mapreduce",
            },
            context=ExecutionContext(session_context=session)
        )

        # С пустыми данными навык вернёт ответ, но с низким confidence или спец. сообщением
        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        answer = data.get("answer", "").lower()
        # Ответ должен содержать указание на отсутствие данных
        has_no_data = any(phrase in answer for phrase in [
            "нет данных", "пусто", "не удалось", "отсутствуют", "empty"
        ])
        assert has_no_data, f"Ожидалось указание на пустые данные: {answer}"
        
        print(f"✅ DataAnalysis: пустые данные обработаны (answer: {answer[:60]}...)")

    @pytest.mark.asyncio
    async def test_analyze_none_data(self, executor):
        """Анализ None данных — ожидается FAILED."""
        session = create_filled_session(goal="Анализ None данных")

        # Создаём шаг с None данными
        step_num = add_step_with_data(
            session=session,
            step_number=4,
            raw_content=None,
            capability_name="sql_tool.execute",
            skill_name="sql_tool"
        )

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "question": "Что в данных?",
                "step_id": step_num,
            },
            context=ExecutionContext(session_context=session)
        )

        # None данные должны приводить к ошибке
        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED при None данных"
        print(f"✅ DataAnalysis: None данные → FAILED")

    @pytest.mark.asyncio
    async def test_analyze_question_mismatch(self, executor):
        """Вопрос не соответствует данным — LLM сообщает об отсутствии relevant данных."""
        session = create_filled_session(goal="Анализ несоответствия вопроса")

        # Данные про товары
        rows = [
            {"id": 1, "product": "Laptop", "price": 1000},
            {"id": 2, "product": "Mouse", "price": 50},
        ]
        
        step_num = add_step_with_data(
            session=session,
            step_number=5,
            raw_content=rows,
            capability_name="sql_tool.execute",
            skill_name="sql_tool"
        )

        result = await executor.execute_action(
            action_name="data_analysis.analyze_step_data",
            parameters={
                "question": "Сколько сотрудников в компании?",
                "step_id": step_num,
                "mode": "mapreduce",
            },
            context=ExecutionContext(session_context=session)
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()

        assert "answer" in data, "Нет поля answer"
        answer_lower = data["answer"].lower()
        
        # LLM должен указать что данных о сотрудниках нет в предоставленных данных
        has_no_data_indication = any(word in answer_lower for word in [
            "нет данных", "не содержит", "отсутствует", "не предоставлены",
            "не найдено", "нет информации", "сотрудник", "товар",
            "не удалось извлечь"
        ])
        assert has_no_data_indication, f"answer не указывает на несоответствие вопроса данным: {data['answer']}"

        print(f"✅ DataAnalysis: несоответствие вопроса данным обработано (answer: {data['answer'][:80]}...)")
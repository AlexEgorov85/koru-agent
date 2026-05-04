"""
Реалистичные интеграционные тесты для DataAnalysis Skill.

ТЕСТЫ:
- test_data_analysis_mapreduce_mode: реальный MapReduce через LLM
- test_data_analysis_large_dataset: обработка большого набора данных
- test_data_analysis_text_data: анализ текстовых данных
- test_data_analysis_empty_result: обработка пустого результата
- test_data_analysis_real_pipeline: полный пайплайн SQL → Context → Analysis

ПРИНЦИПЫ:
1. Реальный ApplicationContext с настоящей БД/файлами
2. Правильное создание контекста (как в реальном агенте)
3. Валидация ответа от LLM
4. Без моков LLM (если LLM недоступен — тест пропускается)
"""
import pytest
import pytest_asyncio
import time
import uuid
from typing import Any

from core.config import get_config
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
    from core.config.app_config import AppConfig
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=infrastructure.config.data_dir
    )
    app_ctx = ApplicationContext(
        infrastructure_context=infrastructure,
        config=app_config,
        profile="prod"
    )
    await app_ctx.initialize()
    yield app_ctx
    await app_ctx.shutdown()


@pytest.fixture(scope="module")
def executor(app_context):
    return ActionExecutor(application_context=app_context)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def add_step_with_data(
    session: SessionContext,
    step_number: int,
    raw_content: Any,
    capability_name: str = "sql_tool.execute",
    skill_name: str = "sql_tool"
) -> int:
    """
    Имитирует работу агента: создаёт шаг и добавляет данные в контекст.
    
    ВОЗВРАЩАЕТ:
    - step_number (для передачи в data_analysis.analyze_step_data)
    """
    import uuid
    
    # 1. Записываем результат в контекст
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
    
    # 2. Регистрируем шаг
    session.register_step(
        step_number=step_number,
        capability_name=capability_name,
        skill_name=skill_name,
        action_item_id=str(uuid.uuid4()),
        observation_item_ids=[obs_id],
        summary=f"Получены данные на шаге {step_number}",
        status=ExecutionStatus.COMPLETED
    )
    
    return step_number


# ============================================================================
# ТЕСТ 1: MAPREDUCE MODE — реальный анализ через LLM
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_mapreduce_mode(executor, app_context):
    """
    MapReduce mode: проверка анализа данных через LLM.
    
    КРИТЕРИИ:
    - Ответ содержит анализ данных
    - metadata.mode_used = "mapreduce"
    - confidence > 0
    - Время обработки записано
    """
    session = SessionContext(
        session_id="test_mapreduce_session",
        agent_id="agent_test"
    )
    session.set_goal("Анализ продаж по регионам")
    
    # Реальные данные
    rows = [
        {"id": 1, "region": "МСК", "amount": 12500.50, "status": "closed"},
        {"id": 2, "region": "СПБ", "amount": 8400.00, "status": "pending"},
        {"id": 3, "region": "МСК", "amount": 31200.75, "status": "closed"},
        {"id": 4, "region": "ЕКБ", "amount": None, "status": "failed"},
        {"id": 5, "region": "МСК", "amount": 15000.00, "status": "closed"},
        {"id": 6, "region": "СПБ", "amount": 22000.00, "status": "closed"},
    ]
    
    step_num = add_step_with_data(
        session=session,
        step_number=1,
        raw_content=rows,
        capability_name="sql_tool.execute",
        skill_name="sql_tool"
    )
    
    # Выполняем анализ
    start = time.time()
    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Какие регионы принесли больше всего выручки? Посчитай сумму и среднее по amount.",
            "step_id": step_num,
            "mode": "mapreduce",
        },
        context=ExecutionContext(session_context=session)
    )
    elapsed = time.time() - start
    
    # Проверки
    assert result.status == ExecutionStatus.COMPLETED, f"MapReduce failed: {result.error}"
    
    # Конвертируем data в dict
    if hasattr(result.data, 'model_dump'):
        data = result.data.model_dump()
    elif hasattr(result.data, 'dict'):
        data = result.data.dict()
    else:
        data = result.data
    
    # Проверка структуры
    assert "answer" in data, "Нет поля answer"
    assert "confidence" in data, "Нет поля confidence"
    assert "metadata" in data, "Нет поля metadata"
    
    answer = data["answer"]
    assert len(answer) > 30, f"Ответ слишком короткий: {answer}"
    
    # Проверка метаданных
    metadata = data["metadata"]
    assert metadata.get("mode_used") == "mapreduce", \
        f"Ожидался режим mapreduce, получен {metadata.get('mode_used')}"
    assert "chunks_created" in metadata, "Нет информации о чанках"
    assert "processing_time_ms" in metadata, "Нет времени обработки"
    assert metadata.get("input_type") == "rows", \
        f"Ожидался input_type=rows, получен {metadata.get('input_type')}"
    
    # Проверка confidence
    assert 0 <= data["confidence"] <= 1, f"confidence вне диапазона: {data['confidence']}"
    
    print(f"✅ MapReduce: анализ выполнен за {elapsed:.2f}s (answer: {answer[:100]}...)")


# ============================================================================
# ТЕСТ 2: БОЛЬШОЙ НАБОР ДАННЫХ
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_large_dataset(executor, app_context):
    """
    Проверка обработки большого набора данных (много чанков).
    """
    session = SessionContext(
        session_id="test_large_dataset_session",
        agent_id="agent_test"
    )
    session.set_goal("Анализ большого набора данных")
    
    # Создаём много данных (будет разбито на несколько чанков)
    rows = [
        {"id": i, "region": "МСК" if i % 3 == 0 else ("СПБ" if i % 3 == 1 else "ЕКБ"),
         "amount": float(1000 * i), "status": "closed" if i % 2 == 0 else "pending"}
        for i in range(1, 51)  # 50 записей
    ]
    
    step_num = add_step_with_data(
        session=session,
        step_number=2,
        raw_content=rows,
        capability_name="sql_tool.execute",
        skill_name="sql_tool"
    )
    
    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Посчитай общую сумму amount и среднее значение. Какой регион лидирует?",
            "step_id": step_num,
            "mode": "mapreduce",
        },
        context=ExecutionContext(session_context=session)
    )
    
    assert result.status == ExecutionStatus.COMPLETED, f"Failed: {result.error}"
    
    # Конвертируем data
    if hasattr(result.data, 'model_dump'):
        data = result.data.model_dump()
    elif hasattr(result.data, 'dict'):
        data = result.data.dict()
    else:
        data = result.data
    
    answer = data["answer"]
    assert len(answer) > 50, f"Ответ слишком короткий для большого набора данных: {answer}"
    
    # Проверка что данные были обработаны (чанков может быть 1 если данные помещаются)
    metadata = data["metadata"]
    assert metadata.get("chunks_created", 0) >= 1, \
        f"Ожидался хотя бы 1 чанк, получено {metadata.get('chunks_created')}"
    
    print(f"✅ Large dataset: {metadata.get('chunks_created')} чанков, answer: {answer[:100]}...")


# ============================================================================
# ТЕСТ 3: ТЕКСТОВЫЕ ДАННЫЕ
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_text_data(executor, app_context):
    """
    Проверка анализа текстовых данных.
    """
    session = SessionContext(
        session_id="test_text_data_session",
        agent_id="agent_test"
    )
    session.set_goal("Анализ текстового отчёта")
    
    text_data = """
    Отчёт по продажам за март 2026.
    
    Регион МСК: Закрыто 3 сделки на сумму 58701.25 рублей.
    Ключевые клиенты: поставка оборудования, разработка ПО.
    Проблемы: задержка согласования договоров на 2 недели.
    
    Регион СПБ: Закрыто 2 сделки на сумму 30400 рублей.
    Основные направления: консалтинг, аутсорсинг.
    Тренды: рост спроса на IT-услуги на 15%.
    
    Регион ЕКБ: 1 сделка в статусе failed.
    Причина: ошибка валидации данных контрагента.
    Требуется: повторная проверка документов.
    """
    
    step_num = add_step_with_data(
        session=session,
        step_number=3,
        raw_content=text_data,
        capability_name="document_tool.process",
        skill_name="document_tool"
    )
    
    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Выдели ключевые проблемы и тренды по регионам",
            "step_id": step_num,
            "mode": "mapreduce",
        },
        context=ExecutionContext(session_context=session)
    )
    
    assert result.status == ExecutionStatus.COMPLETED, f"Failed: {result.error}"
    
    # Конвертируем data
    if hasattr(result.data, 'model_dump'):
        data = result.data.model_dump()
    elif hasattr(result.data, 'dict'):
        data = result.data.dict()
    else:
        data = result.data
    
    answer = data["answer"]
    assert len(answer) > 20, f"Ответ слишком короткий: {answer}"
    
    # Проверка метаданных
    metadata = data["metadata"]
    assert metadata.get("input_type") == "text", \
        f"Ожидался input_type=text, получен {metadata.get('input_type')}"
    
    print(f"✅ Text data: анализ выполнен (answer: {answer[:100]}...)")


# ============================================================================
# ТЕСТ 4: ПУСТОЙ РЕЗУЛЬТАТ
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_empty_result(executor, app_context):
    """
    Проверка обработки пустых данных.
    """
    session = SessionContext(
        session_id="test_empty_result_session",
        agent_id="agent_test"
    )
    session.set_goal("Анализ пустых данных")
    
    step_num = add_step_with_data(
        session=session,
        step_number=4,
        raw_content=[],  # Пустой список
        capability_name="sql_tool.execute",
        skill_name="sql_tool"
    )
    
    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Какие данные в результате?",
            "step_id": step_num,
            "mode": "mapreduce",
        },
        context=ExecutionContext(session_context=session)
    )
    
    # С пустыми данными навык должен вернуть ответ о отсутствии данных
    assert result.status == ExecutionStatus.COMPLETED, f"Failed: {result.error}"
    
    # Конвертируем data
    if hasattr(result.data, 'model_dump'):
        data = result.data.model_dump()
    elif hasattr(result.data, 'dict'):
        data = result.data.dict()
    else:
        data = result.data
    
    answer = data.get("answer", "").lower()
    has_no_data = any(phrase in answer for phrase in 
                      ["нет данных", "пусто", "не удалось", "отсутствуют", "empty"])
    assert has_no_data, f"Ожидалось указание на пустые данные: {answer}"
    
    print(f"✅ Empty result: обработан (answer: {answer[:60]}...)")


# ============================================================================
# ТЕСТ 5: ПОЛНЫЙ ПАЙПЛАЙН
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_real_pipeline(executor, app_context):
    """
    Полный пайплайн: данные → Context → Analysis.
    
    Сценарий:
    1. Создаём данные и сохраняем в контекст (как после выполнения SQL)
    2. Выполняем анализ через data_analysis
    3. Проверяем что результат сохранён в контекст
    """
    session = SessionContext(
        session_id="test_pipeline_session",
        agent_id="agent_test"
    )
    session.set_goal("Полный пайплайн анализа данных")
    
    rows = [
        {"id": 1, "region": "МСК", "amount": 12500.50, "status": "closed"},
        {"id": 2, "region": "СПБ", "amount": 8400.00, "status": "pending"},
        {"id": 3, "region": "МСК", "amount": 31200.75, "status": "closed"},
        {"id": 4, "region": "ЕКБ", "amount": None, "status": "failed"},
        {"id": 5, "region": "МСК", "amount": 15000.00, "status": "closed"},
        {"id": 6, "region": "СПБ", "amount": 22000.00, "status": "closed"},
    ]
    
    # Шаг 1: Имитируем выполнение SQL (сохранение данных)
    step_num = add_step_with_data(
        session=session,
        step_number=1,
        raw_content=rows,
        capability_name="sql_tool.execute",
        skill_name="sql_tool"
    )
    
    # Шаг 2: Анализ данных
    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Сколько записей и чему равна общая сумма amount?",
            "step_id": step_num,
            "mode": "mapreduce",
        },
        context=ExecutionContext(session_context=session)
    )
    
    assert result.status == ExecutionStatus.COMPLETED, f"Failed: {result.error}"
    
    # Конвертируем data
    if hasattr(result.data, 'model_dump'):
        data = result.data.model_dump()
    elif hasattr(result.data, 'dict'):
        data = result.data.dict()
    else:
        data = result.data
    
    # Проверка что результат анализа сохранён в контекст
    # Навык вызывает session_context.record_observation в любом случае
    assert len(session.data_context.items) >= 2, f"Ожидалось минимум 2 записи (данные + анализ), получено {len(session.data_context.items)}"
    
    print(f"✅ Pipeline: данные → анализ → сохранение в контекст выполнено")


# ============================================================================
# ТЕСТ 6: ОТСУТСТВИЕ ДАННЫХ (НЕСУЩЕСТВУЮЩИЙ STEP_ID)
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_nonexistent_step(executor, app_context):
    """
    Тест на отсутствие данных (step_id не существует).
    """
    session = SessionContext(
        session_id="test_nonexistent_step_session",
        agent_id="agent_test"
    )
    session.set_goal("Тест с несуществующим step_id")
    
    # НЕ добавляем никаких данных - step_id не существует
    
    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Посчитай сумму",
            "step_id": 999,  # Несуществующий шаг
        },
        context=ExecutionContext(session_context=session)
    )
    
    # Ожидаем ошибку - нет данных
    assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED при несуществующем step_id"
    assert "не найдены" in (result.error or "").lower() or "not found" in (result.error or "").lower(), \
        f"Ошибка должна быть про отсутствие данных: {result.error}"
    
    print(f"✅ Nonexistent step: {result.error}")

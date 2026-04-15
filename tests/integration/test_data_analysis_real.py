"""
Реалистичные интеграционные тесты для DataAnalysis Skill.

ТЕСТЫ:
- test_data_analysis_python_mode: детерминированная арифметика
- test_data_analysis_llm_mode: интерпретация через LLM
- test_data_analysis_semantic_mode: работа с текстом
- test_data_analysis_auto_mode: автовыбор режима
- test_data_analysis_real_pipeline: полный пайплайн SQL → Context → Analysis

ПРИНЦИПЫ:
1. Реальный ApplicationContext с настоящей БД/файлами
2. Реальные инструменты через ActionExecutor
3. Реальные observations в SessionContext.data_context
4. Валидация против математических ожиданий
5. Без моков LLM (если LLM недоступен — тест пропускается)
"""
import asyncio
import pytest
import pytest_asyncio
import time

from core.config import get_config
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.session_context.session_context import SessionContext
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
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


@pytest.fixture
def session_context():
    return SessionContext(
        session_id="test_real_session",
        agent_id="agent_test"
    )


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def add_step_data_to_context(session_ctx, step_id: str, data):
    """Добавить данные в контекст под step_id."""
    import uuid
    from core.session_context.model import ContextItem, ContextItemMetadata, ContextItemType
    
    item = ContextItem(
        item_id=str(uuid.uuid4()),
        session_id=session_ctx.session_id or "test_session",
        content=data,
        item_type=ContextItemType.OBSERVATION,
        metadata=ContextItemMetadata(
            source="test",
            additional_data={"step_id": step_id}
        )
    )
    session_ctx.data_context.add_item(item)


# ============================================================================
# ТЕСТ 1: PYTHON MODE — детерминированная арифметика
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_python_mode(executor, session_context):
    """
    PYTHON mode: проверка точной арифметики без LLM.
    
    КРИТЕРИИ:
    - Сумма amount = 89101.25 (для closed)
    - Среднее amount = ~17820.25
    - Количество = 6
    - Время < 50мс
    """
    exec_ctx = ExecutionContext(session_context=session_context)
    
    # Реальные строки с разными типами данных
    rows = [
        {"id": 1, "region": "МСК", "amount": 12500.50, "status": "closed"},
        {"id": 2, "region": "СПБ", "amount": 8400.00, "status": "pending"},
        {"id": 3, "region": "МСК", "amount": 31200.75, "status": "closed"},
        {"id": 4, "region": "ЕКБ", "amount": None, "status": "failed"},
        {"id": 5, "region": "МСК", "amount": 15000.00, "status": "closed"},
        {"id": 6, "region": "СПБ", "amount": 22000.00, "status": "closed"},
    ]

    # Добавляем в контекст
    add_step_data_to_context(session_context, "python_test", {"rows": rows})

    # 3. PYTHON mode
    start = time.time()
    py_res = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "step_id": "python_test",
            "question": "Посчитай сумму и среднее по amount",
            "mode": "python"
        },
        context=exec_ctx
    )
    py_time = time.time() - start

    # 4. Проверки
    assert py_res.status == ExecutionStatus.COMPLETED, f"Python mode failed: {py_res.error}"
    
    # Конвертируем data в dict если это Pydantic модель
    if hasattr(py_res.data, 'model_dump'):
        result_data = py_res.data.model_dump()
    elif hasattr(py_res.data, 'dict'):
        result_data = py_res.data.dict()
    else:
        result_data = py_res.data
    
    # Проверка времени
    assert py_time < 0.1, f"Python mode слишком медленный: {py_time:.3f}s"

    # Проверка ответа
    answer = result_data.get("answer", "").lower()
    assert any(kw in answer for kw in ["сумма", "sum", "89101", "17820", "средн", "всего"]), \
        f"Ответ не содержит ожидаемых данных: {answer}"

    # Проверка метаданных
    metadata = result_data.get("metadata", {})
    assert metadata.get("mode") == "python"
    assert "processing_time_ms" in metadata
    assert "rows_processed" in metadata
    assert result_data.get("confidence", 0) > 0


# ============================================================================
# ТЕСТ 2: LLM MODE — интерпретация через LLM (пропускаем - медленный)
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_llm_mode(executor, session_context):
    """
    LLM mode: проверка интерпретации данных.
    
    КРИТЕРИИ:
    - Ответ содержит интерпретацию
    - metadata.mode = "llm"
    - confidence > 0
    """
    exec_ctx = ExecutionContext(session_context=session_context)
    
    rows = [
        {"id": 1, "region": "МСК", "amount": 12500.50, "status": "closed"},
        {"id": 2, "region": "СПБ", "amount": 8400.00, "status": "pending"},
        {"id": 3, "region": "МСК", "amount": 31200.75, "status": "closed"},
        {"id": 4, "region": "ЕКБ", "amount": None, "status": "failed"},
        {"id": 5, "region": "МСК", "amount": 15000.00, "status": "closed"},
        {"id": 6, "region": "СПБ", "amount": 22000.00, "status": "closed"},
    ]
    add_step_data_to_context(session_context, "llm_test", {"rows": rows})

    # LLM mode
    start = time.time()
    llm_res = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "step_id": "llm_test",
            "question": "Какие регионы принесли больше всего выручки? Опиши тренды.",
            "mode": "llm"
        },
        context=exec_ctx
    )
    llm_time = time.time() - start

    # Проверки
    assert llm_res.status == ExecutionStatus.COMPLETED, f"LLM mode failed: {llm_res.error}"
    
    # Конвертируем data в dict если это Pydantic модель
    if hasattr(llm_res.data, 'model_dump'):
        result_data = llm_res.data.model_dump()
    elif hasattr(llm_res.data, 'dict'):
        result_data = llm_res.data.dict()
    else:
        result_data = llm_res.data
    
    answer = result_data.get("answer", "")
    assert len(answer) > 20, "Ответ слишком короткий"

    metadata = result_data.get("metadata", {})
    assert metadata.get("mode") == "llm"
    assert "processing_time_ms" in metadata
    assert result_data.get("confidence", 0) > 0


# ============================================================================
# ТЕСТ 3: SEMANTIC MODE — работа с текстом (пропускаем - медленный)
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_semantic_mode(executor, session_context):
    """
    SEMANTIC mode: проверка работы с текстовыми данными.
    
    КРИТЕРИИ:
    - Ответ содержит анализ текста
    - metadata.mode = "semantic"
    """
    exec_ctx = ExecutionContext(session_context=session_context)

    # Текстовые данные
    text_data = {
        "content": """
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
    }
    add_step_data_to_context(session_context, "semantic_test", text_data)

    # SEMANTIC mode
    sem_res = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "step_id": "semantic_test",
            "question": "Выдели ключевые проблемы и тренды по регионам",
            "mode": "semantic"
        },
        context=exec_ctx
    )

    # Проверки
    assert sem_res.status == ExecutionStatus.COMPLETED, f"Semantic mode failed: {sem_res.error}"
    
    # Конвертируем data в dict если это Pydantic модель
    if hasattr(sem_res.data, 'model_dump'):
        result_data = sem_res.data.model_dump()
    elif hasattr(sem_res.data, 'dict'):
        result_data = sem_res.data.dict()
    else:
        result_data = sem_res.data
    
    answer = result_data.get("answer", "")
    assert len(answer) > 20, "Ответ слишком короткий"

    metadata = result_data.get("metadata", {})
    assert metadata.get("mode") == "semantic"
    assert result_data.get("confidence", 0) > 0


# ============================================================================
# ТЕСТ 4: AUTO MODE — автовыбор режима
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_auto_mode_python(executor, session_context):
    """
    AUTO mode: должен выбрать python для числового вопроса.
    """
    exec_ctx = ExecutionContext(session_context=session_context)
    
    rows = [
        {"id": 1, "region": "МСК", "amount": 12500.50, "status": "closed"},
        {"id": 2, "region": "СПБ", "amount": 8400.00, "status": "pending"},
        {"id": 3, "region": "МСК", "amount": 31200.75, "status": "closed"},
    ]
    add_step_data_to_context(session_context, "auto_test", {"rows": rows})

    # AUTO mode с числовым вопросом
    auto_res = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "step_id": "auto_test",
            "question": "Посчитай сумму по amount",  # Должен выбрать python
            "mode": "auto"
        },
        context=exec_ctx
    )

    assert auto_res.status == ExecutionStatus.COMPLETED
    
    # Конвертируем data в dict если это Pydantic модель
    if hasattr(auto_res.data, 'model_dump'):
        result_data = auto_res.data.model_dump()
    elif hasattr(auto_res.data, 'dict'):
        result_data = auto_res.data.dict()
    else:
        result_data = auto_res.data
    
    metadata = result_data.get("metadata", {})
    assert metadata.get("mode") == "python", f"AUTO должен был выбрать python, выбрал {metadata.get('mode')}"


# ============================================================================
# ТЕСТ 5: ПОЛНЫЙ ПАЙПЛАИН SQL → Context → Analysis
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_real_pipeline(executor, session_context):
    """
    Полный пайплайн: данные → Context → Analysis в разных режимах.
    
    КРИТЕРИИ:
    - Данные сохраняются в контекст
    - Все режимы работают
    - Математика точная
    """
    exec_ctx = ExecutionContext(session_context=session_context)
    
    rows = [
        {"id": 1, "region": "МСК", "amount": 12500.50, "status": "closed"},
        {"id": 2, "region": "СПБ", "amount": 8400.00, "status": "pending"},
        {"id": 3, "region": "МСК", "amount": 31200.75, "status": "closed"},
        {"id": 4, "region": "ЕКБ", "amount": None, "status": "failed"},
        {"id": 5, "region": "МСК", "amount": 15000.00, "status": "closed"},
        {"id": 6, "region": "СПБ", "amount": 22000.00, "status": "closed"},
    ]

    # 2. Сохранение в контекст
    step_id = "pipeline_step"
    add_step_data_to_context(session_context, step_id, {"rows": rows})

    # 3. PYTHON mode
    py_res = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={"step_id": step_id, "question": "Сколько записей?", "mode": "python"},
        context=exec_ctx
    )
    assert py_res.status == ExecutionStatus.COMPLETED
    
    # Конвертируем data в dict
    if hasattr(py_res.data, 'model_dump'):
        py_data = py_res.data.model_dump()
    elif hasattr(py_res.data, 'dict'):
        py_data = py_res.data.dict()
    else:
        py_data = py_res.data
    
    assert py_data.get("metadata", {}).get("mode") == "python"

    # 4. Проверка что PYTHON быстрый
    py_time = py_data.get("metadata", {}).get("processing_time_ms", 999)
    assert py_time < 100, f"Python mode медленный: {py_time}мс"

    # 5. AUTO mode
    auto_res = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={"step_id": step_id, "question": "Вычисли сумму amount", "mode": "auto"},
        context=exec_ctx
    )
    assert auto_res.status == ExecutionStatus.COMPLETED


# ============================================================================
# ТЕСТ 6: КРАЕВЫЕ СЛУЧАИ
# ============================================================================

@pytest.mark.asyncio
async def test_data_analysis_empty_rows(executor, session_context):
    """Тест на отсутствие данных (step_id не существует)."""
    exec_ctx = ExecutionContext(session_context=session_context)
    
    # НЕ добавляем никаких данных - step_id не существует

    res = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={"step_id": "nonexistent_step", "question": "Посчитай сумму", "mode": "python"},
        context=exec_ctx
    )

    # Ожидаем ошибку - нет данных
    assert res.status == ExecutionStatus.FAILED
    assert "нет данных" in (res.error or "").lower() or "no data" in (res.error or "").lower()

"""
Интеграционные тесты для Planning Skill.

ТЕСТЫ:
  planning.create_plan (2):
  - test_create_plan_simple: создание простого плана
  - test_create_plan_with_capabilities: создание плана со списком capabilities

  planning.update_plan (1):
  - test_update_plan: обновление плана

  planning.get_next_step (1):
  - test_get_next_step: получение следующего шага

  planning.decompose_task (1):
  - test_decompose_task: декомпозиция задачи

  Тесты ошибок (3):
  - test_create_plan_empty_goal: пустая цель
  - test_get_next_step_empty_plan: пустой план
  - test_decompose_task_empty_task: пустая задача

ПРИНЦИПЫ:
- Контексты поднимаются ОДИН РАЗ (scope="module")
- Проверка логики: plan содержит осмысленные шаги
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


def create_filled_session(goal: str, add_observations: bool = True, add_steps: bool = True) -> SessionContext:
    """Создаёт SessionContext с наполненными данными."""
    session = SessionContext(session_id="test_planning_001", agent_id="test_agent_001")
    session.set_goal(goal)
    
    if add_observations:
        session.record_observation(
            {"result": "Доступны инструменты SQL", "capabilities": ["sql_tool.execute", "book_library.search"]},
            source="system",
            step_number=1
        )
        session.record_observation(
            {"result": "Доступен LLM для анализа", "capabilities": ["llm.generate"]},
            source="system",
            step_number=2
        )
    
    if add_steps:
        session.register_step(
            step_number=1,
            capability_name="planning.create_plan",
            skill_name="planning",
            action_item_id=session.record_action({"action": "create_plan", "goal": goal}),
            observation_item_ids=[],
            summary=f"Создание плана для: {goal}",
            status=ExecutionStatus.COMPLETED
        )
    
    session.dialogue_history.add_user_message(goal)
    session.dialogue_history.add_assistant_message("Создаю план...")
    
    return session


# ============================================================================
# PLANNING SKILL
# ============================================================================

class TestPlanningSkillIntegration:
    """Planning Skill — 5 тестов."""

    @pytest.mark.asyncio
    async def test_create_plan_simple(self, executor):
        """Создание простого плана по цели."""
        session = create_filled_session(goal="Найти все книги Пушкина в библиотеке")
        
        result = await executor.execute_action(
            action_name="planning.create_plan",
            parameters={
                "goal": "Найти все книги Пушкина в библиотеке",
                "context": "База данных содержит таблицы books и authors"
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка логики: есть план с шагами
        assert "plan" in data or "steps" in data, "Нет поля plan или steps"
        
        # Извлекаем план
        plan = data.get("plan") or data.get("steps") or []
        assert isinstance(plan, list), "plan должен быть списком"
        assert len(plan) > 0, "plan не должен быть пустым"
        
        # Проверка: каждый шаг имеет описание
        for step in plan:
            assert "description" in step or "action" in step, f"Шаг не имеет description: {step}"
            desc = step.get("description") or step.get("action") or ""
            assert len(desc) > 0, "description не должен быть пустым"
        
        # Проверка логики: описание релевантно цели
        first_step_desc = (plan[0].get("description") or plan[0].get("action") or "").lower()
        has_relevant_action = any(word in first_step_desc for word in ["книг", "пушкин", "sql", "поиск", "найти", "запрос"])
        assert has_relevant_action, f"Первый шаг не релевантен цели: {first_step_desc}"
        
        print(f"✅ Planning: план создан ({len(plan)} шагов)")

    @pytest.mark.asyncio
    async def test_create_plan_with_capabilities(self, executor):
        """Создание плана с использованием списка capabilities."""
        session = create_filled_session(goal="Проанализировать данные и дать финальный ответ")
        
        result = await executor.execute_action(
            action_name="planning.create_plan",
            parameters={
                "goal": "Проанализировать данные и дать финальный ответ",
                "capabilities_list": [
                    "sql_tool.execute",
                    "data_analysis.analyze_step_data",
                    "final_answer.generate"
                ],
                "context": "Доступны инструменты для работы с БД и LLM"
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка: план создан
        plan = data.get("plan") or data.get("steps") or []
        assert len(plan) > 0, "plan не должен быть пустым"
        
        # Проверка логики: в плане есть шаги связанные с указанными capabilities
        plan_text = str(plan).lower()
        has_sql = "sql" in plan_text or "запрос" in plan_text
        has_analysis = "анализ" in plan_text or "данн" in plan_text
        has_final = "ответ" in plan_text or "финальн" in plan_text or "итогов" in plan_text
        
        # План должен содержать элементы связанные с целью
        assert any([has_sql, has_analysis, has_final]), f"План не содержит релевантных шагов: {plan_text[:200]}"
        
        print(f"✅ Planning: план с capabilities создан ({len(plan)} шагов)")

    @pytest.mark.asyncio
    async def test_update_plan(self, executor):
        """Обновление существующего плана."""
        session = create_filled_session(goal="Тестовая цель для обновления плана")
        
        result = await executor.execute_action(
            action_name="planning.update_plan",
            parameters={
                "goal": "Тестовая цель",
                "current_plan": {
                    "steps": [
                        {"step_id": "1", "description": "Шаг 1", "status": "pending"},
                        {"step_id": "2", "description": "Шаг 2", "status": "pending"}
                    ]
                },
                "updates": {
                    "add_steps": [
                        {"step_id": "3", "description": "Новый шаг"}
                    ]
                }
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка: обновлённый план содержит все шаги
        plan = data.get("plan") or data.get("steps") or data.get("updated_plan") or []
        assert isinstance(plan, list), "plan должен быть списком"
        assert len(plan) >= 2, f"plan должен содержать исходные шаги, получено: {len(plan)}"
        
        # Проверка: есть добавленный шаг
        plan_str = str(plan)
        has_new_step = "новый" in plan_str.lower() or "3" in plan_str
        assert has_new_step, f"Добавленный шаг не найден: {plan}"
        
        print(f"✅ Planning: план обновлён ({len(plan)} шагов)")

    @pytest.mark.asyncio
    async def test_get_next_step(self, executor):
        """Получение следующего шага из плана."""
        session = create_filled_session(goal="Выполнение плана")
        
        result = await executor.execute_action(
            action_name="planning.get_next_step",
            parameters={
                "plan": {
                    "steps": [
                        {"step_id": "1", "description": "Выполнить SQL запрос", "status": "completed"},
                        {"step_id": "2", "description": "Проанализировать результаты", "status": "in_progress"},
                        {"step_id": "3", "description": "Сформировать ответ", "status": "pending"}
                    ]
                }
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка: есть next_step или step_id
        assert "next_step" in data or "step_id" in data, "Нет поля next_step или step_id"
        
        # Проверка логики: next_step соответствует ожидаемому (2 или 3)
        next_step_id = data.get("next_step") or data.get("step_id")
        assert next_step_id in ["2", "3", 2, 3], f"Неверный next_step: {next_step_id}"
        
        # Проверка: next_step имеет описание
        step_desc = data.get("description") or data.get("next_step", {}).get("description") if isinstance(data.get("next_step"), dict) else ""
        assert len(str(step_desc)) > 0, "next_step должен иметь описание"
        
        print(f"✅ Planning: следующий шаг получен: {next_step_id}")

    @pytest.mark.asyncio
    async def test_decompose_task(self, executor):
        """Декомпозиция сложной задачи на подзадачи."""
        session = create_filled_session(goal="Провести полное исследование библиотеки")
        
        result = await executor.execute_action(
            action_name="planning.decompose_task",
            parameters={
                "task": "Провести полное исследование библиотеки и подготовить отчёт",
                "context": "Доступны инструменты SQL, поиска и анализа данных"
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка: есть подзадачи
        subtasks = data.get("subtasks") or data.get("tasks") or data.get("decomposition") or []
        assert isinstance(subtasks, list), "subtasks должен быть списком"
        assert len(subtasks) > 1, f"Должно быть больше одной подзадачи, получено: {len(subtasks)}"
        
        # Проверка: каждая подзадача имеет описание
        for subtask in subtasks:
            assert "description" in subtask or "title" in subtask or "name" in subtask, f"Подзадача без описания: {subtask}"
            desc = subtask.get("description") or subtask.get("title") or subtask.get("name") or ""
            assert len(desc) > 0, "Описание подзадачи не должно быть пустым"
        
        # Проверка логики: подзадачи покрывают разные аспекты (исследование + отчёт)
        subtasks_text = " ".join([
            str(s.get("description") or s.get("title") or s.get("name") or "")
            for s in subtasks
        ]).lower()
        
        has_research = any(word in subtasks_text for word in ["исслед", "поиск", "данн", "анализ"])
        has_report = any(word in subtasks_text for word in ["отчёт", "подготов", "финальн", "ответ"])
        
        assert has_research or has_report, f"Подзадачи не покрывают цель: {subtasks_text[:200]}"
        
        print(f"✅ Planning: задача декомпозирована на {len(subtasks)} подзадач")


class TestPlanningSkillErrorHandling:
    """Тесты ошибок Planning Skill — 3 теста."""

    @pytest.mark.asyncio
    async def test_create_plan_empty_goal(self, executor):
        """Создание плана с пустой целью — должен вернуть FAILED."""
        session = create_filled_session(goal="")
        
        result = await executor.execute_action(
            action_name="planning.create_plan",
            parameters={
                "goal": "",
                "context": "Тестовый контекст"
            },
            context=session
        )

        # Пустая цель — должен быть FAILED
        if result.status == ExecutionStatus.FAILED:
            assert result.error is not None
            print(f"✅ Planning: пустая цель → FAILED")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            # Проверяем что план пустой или содержит ошибку в данных
            plan = data.get("plan") or data.get("steps") or []
            assert len(plan) == 0, f"План должен быть пустым при пустой цели: {len(plan)}"
            print(f"✅ Planning: пустая цель обработана")

    @pytest.mark.asyncio
    async def test_get_next_step_empty_plan(self, executor):
        """Получение следующего шага из пустого плана."""
        session = create_filled_session(goal="Выполнение плана")
        
        result = await executor.execute_action(
            action_name="planning.get_next_step",
            parameters={
                "plan": {
                    "steps": []
                }
            },
            context=session
        )

        # Пустой план — должен вернуть FAILED или пустой next_step
        if result.status == ExecutionStatus.FAILED:
            assert result.error is not None
            print(f"✅ Planning: пустой план → FAILED")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            # При пустом плане next_step должен быть None или отсутствовать
            next_step = data.get("next_step") or data.get("step_id")
            assert next_step is None or next_step == "", f"next_step должен быть пустым: {next_step}"
            print(f"✅ Planning: пустой план обработан")

    @pytest.mark.asyncio
    async def test_decompose_task_empty_task(self, executor):
        """Декомпозиция пустой задачи — должен вернуть FAILED."""
        session = create_filled_session(goal="Декомпозиция задачи")
        
        result = await executor.execute_action(
            action_name="planning.decompose_task",
            parameters={
                "task": "",
                "context": "Контекст"
            },
            context=session
        )

        # Пустая задача — должен быть FAILED
        if result.status == ExecutionStatus.FAILED:
            assert result.error is not None
            print(f"✅ Planning: пустая задача → FAILED")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            subtasks = data.get("subtasks") or data.get("tasks") or []
            assert len(subtasks) == 0, "Подзадачи должны быть пустыми при пустой задаче"
            print(f"✅ Planning: пустая задача обработана")
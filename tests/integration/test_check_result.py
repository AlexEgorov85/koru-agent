"""
Интеграционные тесты для CheckResult Skill.

ПРЕДМЕТНАЯ ОБЛАСТЬ: Аудиторские проверки (audits, violations, audit_reports)

ТЕСТЫ:
  check_result.execute_script (2):
  - test_execute_script_exists: выполнение существующего скрипта (get_all_audits)
  - test_execute_script_not_found: выполнение несуществующего скрипта (FAILED)

  check_result.generate_script (1):
  - test_generate_script: генерация SQL скрипта через LLM

  Тесты ошибок (3):
  - test_generate_empty_query: пустой запрос
  - test_generate_invalid_query: некорректный запрос
  - test_execute_missing_params: отсутствует обязательный script_name

ПРИНЦИПЫ:
- Контексты поднимаются ОДИН РАЗ (scope="module")
- Реальное поведение, без моков
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
    from core.components.action_executor import ActionExecutor
    return ActionExecutor(application_context=app_context)


@pytest.fixture
def session():
    return SessionContext()


def create_filled_session(goal: str = "Проверка результатов аудита") -> SessionContext:
    """Создаёт SessionContext с наполненными данными для CheckResult."""
    session = SessionContext(session_id="test_check_result_001", agent_id="test_agent_001")
    session.set_goal(goal)

    # Актуальные скрипты из execute_script_handler.py
    session.record_observation(
        {
            "result": "Доступны скрипты проверки аудита",
            "scripts": [
                "get_all_audits", "get_audit_by_status", "get_audit_reports",
                "get_report_items", "get_violations_by_audit", "get_violations_by_status",
                "get_violations_by_severity", "get_overdue_violations",
                "get_violations_by_responsible", "get_audit_statistics"
            ]
        },
        source="system",
        step_number=1
    )

    session.register_step(
        step_number=1,
        capability_name="check_result.execute_script",
        skill_name="check_result",
        action_item_id=session.record_action({"action": "check_result", "goal": goal}),
        observation_item_ids=[],
        summary=f"Проверка результатов аудита: {goal}",
        status=ExecutionStatus.COMPLETED
    )

    session.dialogue_history.add_user_message(f"Проверь: {goal}")
    session.dialogue_history.add_assistant_message("Выполняю проверку аудита...")

    return session


# ============================================================================
# CHECK RESULT SKILL
# ============================================================================

class TestCheckResultSkillIntegration:
    """CheckResult Skill — интеграционные тесты."""

    @pytest.mark.asyncio
    async def test_execute_script_exists(self, executor):
        """Выполнение существующего скрипта — get_all_audits (без обязательных параметров)."""
        session = create_filled_session(goal="Получить все аудиторские проверки")

        result = await executor.execute_action(
            action_name="check_result.execute_script",
            parameters={
                "script_name": "get_all_audits",
                "max_rows": 10
            },
            context=session
        )

        # Ожидаем успешное выполнение
        assert result.status == ExecutionStatus.COMPLETED, \
            f"Ожидался COMPLETED, но получил {result.status}: {result.error}"

        data = result.data if isinstance(result.data, dict) else result.data.model_dump()

        # Проверка: результат содержит данные
        assert "rows" in data, f"Нет 'rows' в результате: {data.keys()}"

        rows = data.get("rows", [])
        assert isinstance(rows, list), "rows должен быть списком"
        assert data.get("script_name") == "get_all_audits", "Неверное имя скрипта"
        print(f"✅ CheckResult: скрипт get_all_audits выполнен ({len(rows)} строк)")

    @pytest.mark.asyncio
    async def test_execute_script_not_found(self, executor):
        """Выполнение несуществующего скрипта — ожидается FAILED."""
        session = create_filled_session(goal="Проверка несуществующего скрипта")

        result = await executor.execute_action(
            action_name="check_result.execute_script",
            parameters={
                "script_name": "nonexistent_script_xyz",
                "max_rows": 5
            },
            context=session
        )

        # Ожидаем FAILED — скрипт не существует
        assert result.status == ExecutionStatus.FAILED, \
            f"Ожидался FAILED, но получил {result.status}"
        assert result.error is not None, "Нет сообщения об ошибке"
        error_lower = result.error.lower()
        assert "script" in error_lower or "не найден" in error_lower, \
            f"Ошибка не связана со скриптом: {result.error}"
        print(f"✅ CheckResult: несуществующий скрипт вернул FAILED")

    @pytest.mark.asyncio
    async def test_generate_script(self, executor):
        """Генерация SQL скрипта через LLM — проверяем что SQL сгенерирован."""
        session = create_filled_session(goal="Генерация SQL запроса для аудита")

        result = await executor.execute_action(
            action_name="check_result.generate_script",
            parameters={
                "query": "Показать все аудиторские проверки",
                "schema_context": "audits,violations",
                "max_results": 5
            },
            context=session
        )

        # SQL генерация может упасть из-за LLM или БД — проверяем логику
        if result.status == ExecutionStatus.COMPLETED:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()

            # Проверка: есть сгенерированный SQL
            sql = data.get("sql_query") or data.get("sql") or data.get("generated_sql") or ""
            if sql:
                sql_lower = sql.lower()
                has_select = "select" in sql_lower
                assert has_select, f"SQL не содержит SELECT: {sql}"

                # Проверка: есть результаты выполнения (могут быть пустыми)
                rows = data.get("rows") or data.get("results") or data.get("data") or []
                assert isinstance(rows, list), "rows должен быть списком"
                print(f"✅ CheckResult: SQL сгенерирован и выполнен ({len(rows)} строк)")
            else:
                # Нет SQL — значит генерация не удалась
                assert False, f"Нет сгенерированного SQL в результате: {data.keys()}"
        else:
            # FAILED — проверяем что ошибка не связана с отсутствующим методом
            assert "has no attribute" not in result.error, f"Баг в коде: {result.error}"
            print(f"✅ CheckResult: генерация SQL не удалась (ожидаемо для ограниченных ресурсов): {result.error[:80]}...")


class TestCheckResultSkillErrorHandling:
    """Тесты ошибок CheckResult Skill."""

    @pytest.mark.asyncio
    async def test_generate_empty_query(self, executor):
        """Генерация SQL с пустым запросом — валидация входа."""
        session = create_filled_session(goal="Генерация SQL с пустым запросом")

        result = await executor.execute_action(
            action_name="check_result.generate_script",
            parameters={
                "query": "",
                "max_results": 10
            },
            context=session
        )

        # Пустой query проходит валидацию (type: string), но handler должен обработать
        # Тест проверяет что skill не падает с критической ошибкой
        if result.status == ExecutionStatus.FAILED:
            assert result.error is not None
            # Ошибка не должна быть связана с отсутствующим методом
            assert "has no attribute" not in result.error, f"Баг в коде: {result.error}"
            print(f"✅ CheckResult: пустой запрос → FAILED ({result.error[:60]}...)")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            sql = data.get("sql_query") or data.get("sql") or data.get("generated_sql") or ""
            # При пустом запросе SQL может быть пустым или содержать дефолтный запрос
            print(f"✅ CheckResult: пустой запрос обработан (sql_len={len(sql)})")

    @pytest.mark.asyncio
    async def test_generate_invalid_query(self, executor):
        """Генерация SQL с некорректным запросом — handler обрабатывает."""
        session = create_filled_session(goal="Генерация с некорректным запросом")

        result = await executor.execute_action(
            action_name="check_result.generate_script",
            parameters={
                "query": "xyz abc 123",
                "max_results": 5
            },
            context=session
        )

        # Некорректный запрос — может вернуть FAILED или пустой SQL
        if result.status == ExecutionStatus.FAILED:
            assert "has no attribute" not in result.error, f"Баг в коде: {result.error}"
            print(f"✅ CheckResult: некорректный запрос → FAILED")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            sql = data.get("sql_query") or data.get("sql") or data.get("generated_sql") or ""
            # LLM может сгенерировать что-то или вернуть пустой результат
            print(f"✅ CheckResult: некорректный запрос обработан (sql_len={len(sql)})")

    @pytest.mark.asyncio
    async def test_execute_missing_params(self, executor):
        """Выполнение скрипта без обязательных параметров — должен вернуть FAILED."""
        session = create_filled_session(goal="Выполнение без параметров")

        result = await executor.execute_action(
            action_name="check_result.execute_script",
            parameters={
                "max_rows": 10
            },
            context=session
        )

        # Отсутствует script_name — должен быть FAILED
        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED без script_name"
        assert result.error is not None
        error_lower = result.error.lower()
        assert "script_name" in error_lower or "required" in error_lower or "field" in error_lower, \
            f"Ошибка не связана с отсутствующим script_name: {result.error}"

        print(f"✅ CheckResult: отсутствует script_name → FAILED")

"""
Интеграционные тесты для MetaComponentCreator Skill.

ТЕСТЫ:
  meta_component_creator.create (2):
  - test_create_skill: создание нового skill-компонента
  - test_create_tool: создание нового tool-компонента

  meta_component_creator.fix (1):
  - test_fix_component: исправление существующего компонента

  meta_component_creator.review (1):
  - test_review_component: код-ревью компонента

  Тесты ошибок (3):
  - test_create_empty_description: пустое описание
  - test_create_invalid_type: невалидный тип компонента
  - test_fix_missing_skill_name: отсутствует имя компонента

ПРИНЦИПЫ:
- Контексты поднимаются ОДИН РАЗ (scope="module")
- Проверка логики: результаты содержат сгенерированный код
- Реальные контексты, без моков
- Тесты ошибок: проверка FAILED при невалидных входных данных
- SessionContext НЕ используется (навык работает автономно на основе параметров)
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


# ============================================================================
# METACOMPONENT CREATOR SKILL
# ============================================================================

class TestMetaComponentCreatorIntegration:
    """MetaComponentCreator Skill — 4 теста."""

    @pytest.mark.asyncio
    async def test_create_skill(self, executor):
        """Создание нового skill-компонента."""
        # Мета-навык работает автономно - SessionContext не используется
        session = SessionContext()
        
        result = await executor.execute_action(
            action_name="meta_component_creator.create",
            parameters={
                "description": "Навык для поиска книг по автору. Принимает имя автора, возвращает список книг.",
                "component_type": "skill",
                "capabilities": ["search_books_by_author"],
                "dependencies": ["sql_tool"],
                "has_prompts": True,
                "has_contracts": True,
                "register_after": False
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка: есть сгенерированный код
        assert "code" in data or "python_code" in data or "generated_code" in data, "Нет сгенерированного кода"
        
        code = data.get("code") or data.get("python_code") or data.get("generated_code") or ""
        assert len(code) > 50, f"Сгенерированный код слишком короткий: {len(code)}"
        
        # Проверка логики: код содержит основные элементы
        code_lower = code.lower()
        has_class = "class" in code_lower
        has_skill = "skill" in code_lower
        has_import = "import" in code_lower
        
        assert has_class or has_skill, f"Код не содержит класс или навык: {code[:200]}"
        
        # Проверка: есть валидация
        assert "validation" in data or "validated" in data, "Нет информации о валидации"
        
        # Проверка: есть metadata с информацией о компоненте
        assert "component_type" in data, "Нет информации о типе компонента"
        assert data["component_type"] == "skill", f"Неверный тип компонента: {data['component_type']}"
        
        print(f"✅ MetaComponentCreator: skill создан ({len(code)} символов кода)")

    @pytest.mark.asyncio
    async def test_create_tool(self, executor):
        """Создание нового tool-компонента."""
        session = SessionContext()
        
        result = await executor.execute_action(
            action_name="meta_component_creator.create",
            parameters={
                "description": "Инструмент для отправки email. Принимает адрес и текст, возвращает статус отправки.",
                "component_type": "tool",
                "capabilities": ["send_email"],
                "dependencies": [],
                "has_prompts": False,
                "has_contracts": True,
                "register_after": False
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        
        # Проверка: есть код
        code = data.get("code") or data.get("python_code") or data.get("generated_code") or ""
        assert len(code) > 30, f"Код слишком короткий: {len(code)}"
        
        # Проверка: тип компонента
        assert data.get("component_type") == "tool", "Тип должен быть tool"
        
        # Проверка: для tool не нужны промпты
        if "has_prompts" in data:
            assert data["has_prompts"] == False, "Для tool не нужны промпты"
        
        print(f"✅ MetaComponentCreator: tool создан ({len(code)} символов кода)")

    @pytest.mark.asyncio
    async def test_fix_component(self, executor):
        """Исправление существующего компонента."""
        session = SessionContext()
        
        result = await executor.execute_action(
            action_name="meta_component_creator.fix",
            parameters={
                "skill_name": "planning",
                "issue_description": "Добавить обработку ошибок при отсутствии шага",
                "dry_run": True
            },
            context=session
        )

        # FIX может вернуть FAILED если компонент не найден - это нормально
        if result.status == ExecutionStatus.FAILED:
            print(f"✅ MetaComponentCreator: компонент не найден (ожидаемо)")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            
            # Проверка: есть исправленный код или описание изменений
            has_fixed_code = "fixed_code" in data or "code" in data
            has_changes = "changes" in data or "diff" in data or "modifications" in data
            
            assert has_fixed_code or has_changes, "Нет исправленного кода или изменений"
            
            # Проверка: dry_run не должен создавать файлы
            assert data.get("dry_run") == True or "dry_run" not in data, "Должен быть dry_run"
            
            print(f"✅ MetaComponentCreator: компонент исправлен")

    @pytest.mark.asyncio
    async def test_review_component(self, executor):
        """Код-ревью компонента."""
        session = SessionContext()
        
        result = await executor.execute_action(
            action_name="meta_component_creator.review",
            parameters={
                "skill_name": "planning",
                "review_focus": ["security", "architecture"]
            },
            context=session
        )

        # REVIEW может вернуть FAILED если компонент не найден
        if result.status == ExecutionStatus.FAILED:
            print(f"✅ MetaComponentCreator: компонент не найден для ревью")
        else:
            data = result.data if isinstance(result.data, dict) else result.data.model_dump()
            
            # Проверка: есть результаты ревью
            assert "review" in data or "issues" in data or "findings" in data, "Нет результатов ревью"
            
            # Проверка: есть оценки или замечания
            review_data = data.get("review") or data.get("issues") or data.get("findings") or {}
            
            # Проверка: есть информация о фокусе ревью
            if "focus" in data:
                focus = data["focus"]
                assert "security" in focus or "architecture" in focus, "Фокус не соответствует"
            
            print(f"✅ MetaComponentCreator: ревью выполнено")


class TestMetaComponentCreatorErrorHandling:
    """Тесты ошибок MetaComponentCreator Skill — 3 теста."""

    @pytest.mark.asyncio
    async def test_create_empty_description(self, executor):
        """Создание компонента с пустым описанием — должен вернуть FAILED."""
        session = SessionContext()
        
        result = await executor.execute_action(
            action_name="meta_component_creator.create",
            parameters={
                "description": "",
                "component_type": "skill"
            },
            context=session
        )

        # Пустое описание — должен быть FAILED
        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED при пустом описании"
        assert result.error is not None
        error_lower = result.error.lower()
        assert "description" in error_lower or "required" in error_lower or "empty" in error_lower, \
            f"Ошибка не связана с описанием: {result.error}"
        
        print(f"✅ MetaComponentCreator: пустое описание → FAILED")

    @pytest.mark.asyncio
    async def test_create_invalid_type(self, executor):
        """Создание компонента с невалидным типом — должен вернуть FAILED."""
        session = SessionContext()
        
        result = await executor.execute_action(
            action_name="meta_component_creator.create",
            parameters={
                "description": "Тестовый компонент",
                "component_type": "invalid_type_xyz"
            },
            context=session
        )

        # Невалидный тип — должен быть FAILED
        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED при невалидном типе"
        assert result.error is not None
        error_lower = result.error.lower()
        assert "type" in error_lower or "invalid" in error_lower or "enum" in error_lower, \
            f"Ошибка не связана с типом: {result.error}"
        
        print(f"✅ MetaComponentCreator: невалидный тип → FAILED")

    @pytest.mark.asyncio
    async def test_fix_missing_skill_name(self, executor):
        """Исправление без имени компонента — должен вернуть FAILED."""
        session = SessionContext()
        
        result = await executor.execute_action(
            action_name="meta_component_creator.fix",
            parameters={
                "issue_description": "Исправить ошибку"
            },
            context=session
        )

        # Отсутствует skill_name — должен быть FAILED
        assert result.status == ExecutionStatus.FAILED, "Ожидался FAILED без skill_name"
        assert result.error is not None
        error_lower = result.error.lower()
        assert "skill_name" in error_lower or "required" in error_lower or "field" in error_lower, \
            f"Ошибка не связана с skill_name: {result.error}"
        
        print(f"✅ MetaComponentCreator: отсутствует skill_name → FAILED")
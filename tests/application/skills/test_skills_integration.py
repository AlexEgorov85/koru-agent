"""
Интеграционные тесты для всех Skills.

Запускают навыки напрямую с реальным контекстом и executor,
проверяют результаты выполнения.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from core.models.data.execution import SkillResult, ExecutionResult
from core.models.data.capability import Capability
from core.session_context.session_context import SessionContext
from core.application.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.infrastructure.event_bus.event_bus import EventBus
from core.infrastructure.logging import EventBusLogger


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def event_bus():
    """Создаёт EventBus для тестов"""
    return EventBus()


@pytest.fixture
def session_context(event_bus):
    """Создаёт SessionContext с EventBus"""
    ctx = SessionContext(session_id="test_session_001")
    # Устанавливаем goal через метод контекста
    if hasattr(ctx, 'set_goal'):
        ctx.set_goal("Тестовая цель для интеграционных тестов Skills")
    return ctx


@pytest.fixture
def action_executor(session_context, event_bus):
    """Создаёт ActionExecutor с моками"""
    # Создаём полный mock application_context
    mock_infrastructure = MagicMock()
    mock_infrastructure.event_bus = event_bus
    
    mock_app_context = MagicMock()
    mock_app_context.infrastructure_context = mock_infrastructure
    mock_app_context.session_context = session_context
    
    # Создаём executor
    from core.application.agent.components.action_executor import ActionExecutor
    executor = ActionExecutor(application_context=mock_app_context)
    
    return executor, mock_app_context


@pytest.fixture
def component_config():
    """Создаёт ComponentConfig для skills"""
    config = MagicMock()
    config.variant_key = "default"
    config.constraints = {}
    return config


# ============================================================================
# ТЕСТЫ BOOK_LIBRARY_SKILL
# ============================================================================

class TestBookLibrarySkillIntegration:
    """Интеграционные тесты BookLibrarySkill"""

    @pytest.mark.asyncio
    async def test_list_scripts(self, action_executor, component_config):
        """Тест: получение списка скриптов"""
        from core.application.skills.book_library.skill import BookLibrarySkill

        executor, app_context = action_executor

        skill = BookLibrarySkill(
            name="book_library",
            application_context=app_context,
            component_config=component_config,
            executor=executor
        )

        await skill.initialize()

        capabilities = skill.get_capabilities()
        list_scripts_cap = next(c for c in capabilities if c.name == "book_library.list_scripts")

        from core.application.agent.components.action_executor import ExecutionContext
        result = await skill.execute(
            capability=list_scripts_cap,
            parameters={},
            execution_context=ExecutionContext(
                session_context=app_context.session_context,
                available_capabilities=[cap.name for cap in skill.get_capabilities()]
            )
        )

        # Проверяем что результат SkillResult
        assert isinstance(result, SkillResult)
        assert result.technical_success is True
        assert result.data is not None
        assert "scripts" in result.data
        assert isinstance(result.data["scripts"], list)
        assert result.side_effect is False  # Только чтение

    @pytest.mark.asyncio
    async def test_execute_script_get_all_books(self, action_executor, component_config):
        """Тест: выполнение скрипта get_all_books"""
        from core.application.skills.book_library.skill import BookLibrarySkill

        executor, app_context = action_executor

        skill = BookLibrarySkill(
            name="book_library",
            application_context=app_context,
            component_config=component_config,
            executor=executor
        )

        await skill.initialize()

        capabilities = skill.get_capabilities()
        execute_script_cap = next(c for c in capabilities if c.name == "book_library.execute_script")

        # Мокаем executor для SQL выполнения
        async def mock_execute_action(action_name, parameters, context):
            if action_name == "sql_query.execute":
                return ExecutionResult(
                    status="success",
                    result={
                        "rows": [
                            {"id": 1, "title": "Book 1", "author": "Author 1"},
                            {"id": 2, "title": "Book 2", "author": "Author 2"}
                        ],
                        "execution_time": 0.05
                    },
                    metadata={}
                )
            return ExecutionResult(status="success", result={})

        executor.execute_action = mock_execute_action

        from core.application.agent.components.action_executor import ExecutionContext
        result = await skill.execute(
            capability=execute_script_cap,
            parameters={"script_name": "get_all_books", "max_rows": 10},
            execution_context=ExecutionContext(
                session_context=app_context.session_context,
                available_capabilities=[cap.name for cap in skill.get_capabilities()]
            )
        )

        # Проверяем результат
        assert isinstance(result, SkillResult)
        assert result.technical_success is True
        assert result.data is not None
        assert result.side_effect is True  # SQL query выполнен


# ============================================================================
# ТЕСТЫ PLANNING_SKILL
# ============================================================================

class TestPlanningSkillIntegration:
    """Интеграционные тесты PlanningSkill"""

    @pytest.mark.asyncio
    async def test_create_plan(self, action_executor, component_config):
        """Тест: создание плана"""
        from core.application.skills.planning.skill import PlanningSkill

        executor, app_context = action_executor

        skill = PlanningSkill(
            name="planning",
            application_context=app_context,
            component_config=component_config,
            executor=executor
        )

        await skill.initialize()

        capabilities = skill.get_capabilities()
        create_plan_cap = next(c for c in capabilities if c.name == "planning.create_plan")

        # Мокаем executor для LLM вызова
        async def mock_execute_action(action_name, parameters, context):
            if action_name == "llm.generate_structured":
                return ExecutionResult(
                    status="success",
                    result={
                        "parsed_content": {
                            "plan_id": "test_plan_001",
                            "steps": [
                                {"step_id": "step_1", "action": "Шаг 1", "status": "pending"},
                                {"step_id": "step_2", "action": "Шаг 2", "status": "pending"}
                            ]
                        }
                    },
                    metadata={"parsing_attempts": 1}
                )
            elif action_name == "context.record_plan":
                return ExecutionResult(
                    status="success",
                    result={"item_id": "plan_001"},
                    metadata={"plan_type": "initial"}
                )
            return ExecutionResult(status="success", result={})

        executor.execute_action = mock_execute_action

        from core.application.agent.components.action_executor import ExecutionContext
        result = await skill.execute(
            capability=create_plan_cap,
            parameters={
                "goal": "Тестовая цель для планирования",
                "max_steps": 5
            },
            execution_context=ExecutionContext(
                session_context=app_context.session_context,
                available_capabilities=[cap.name for cap in skill.get_capabilities()]
            )
        )

        # Проверяем результат
        assert isinstance(result, SkillResult)
        assert result.technical_success is True
        assert result.data is not None
        assert "plan_id" in result.data or "steps" in result.data
        assert result.side_effect is True  # Запись в контекст

    @pytest.mark.asyncio
    async def test_get_next_step(self, action_executor, component_config):
        """Тест: получение следующего шага"""
        from core.application.skills.planning.skill import PlanningSkill

        executor, app_context = action_executor

        skill = PlanningSkill(
            name="planning",
            application_context=app_context,
            component_config=component_config,
            executor=executor
        )

        await skill.initialize()

        capabilities = skill.get_capabilities()
        get_next_step_cap = next(c for c in capabilities if c.name == "planning.get_next_step")

        # Мокаем executor для получения плана
        async def mock_execute_action(action_name, parameters, context):
            if action_name == "context.get_current_plan":
                return ExecutionResult(
                    status="success",
                    result={
                        "plan_id": "test_plan_001",
                        "steps": [
                            {"step_id": "step_1", "action": "Шаг 1", "status": "pending"},
                            {"step_id": "step_2", "action": "Шаг 2", "status": "pending"}
                        ]
                    },
                    metadata={"exists": True}
                )
            return ExecutionResult(status="success", result={})

        executor.execute_action = mock_execute_action

        from core.application.agent.components.action_executor import ExecutionContext
        result = await skill.execute(
            capability=get_next_step_cap,
            parameters={},
            execution_context=ExecutionContext(
                session_context=app_context.session_context,
                available_capabilities=[cap.name for cap in skill.get_capabilities()]
            )
        )

        # Проверяем результат
        assert isinstance(result, SkillResult)
        assert result.technical_success is True


# ============================================================================
# ТЕСТЫ FINAL_ANSWER_SKILL
# ============================================================================

class TestFinalAnswerSkillIntegration:
    """Интеграционные тесты FinalAnswerSkill"""

    @pytest.mark.asyncio
    async def test_generate_final_answer(self, action_executor, component_config):
        """Тест: генерация финального ответа"""
        from core.application.skills.final_answer.skill import FinalAnswerSkill

        executor, app_context = action_executor

        skill = FinalAnswerSkill(
            name="final_answer",
            application_context=app_context,
            component_config=component_config,
            executor=executor
        )

        await skill.initialize()

        capabilities = skill.get_capabilities()
        generate_cap = next(c for c in capabilities if c.name == "final_answer.generate")

        # Мокаем executor для LLM вызова и получения контекста
        async def mock_execute_action(action_name, parameters, context):
            if action_name == "context.get_all_items":
                return ExecutionResult(
                    status="success",
                    result={"items": {}},
                    metadata={"count": 0}
                )
            elif action_name == "context.get_step_history":
                return ExecutionResult(
                    status="success",
                    result={"steps": []},
                    metadata={"count": 0}
                )
            elif action_name == "llm.generate_structured":
                return ExecutionResult(
                    status="success",
                    result={
                        "parsed_content": {
                            "answer": "Финальный ответ на основе анализа",
                            "confidence": 0.85,
                            "remaining_questions": []
                        }
                    },
                    metadata={"parsing_attempts": 1}
                )
            return ExecutionResult(status="success", result={})

        executor.execute_action = mock_execute_action

        from core.application.agent.components.action_executor import ExecutionContext
        result = await skill.execute(
            capability=generate_cap,
            parameters={
                "format_type": "detailed",
                "include_steps": True,
                "include_evidence": True
            },
            execution_context=ExecutionContext(
                session_context=app_context.session_context,
                available_capabilities=[cap.name for cap in skill.get_capabilities()]
            )
        )

        # Проверяем результат
        assert isinstance(result, SkillResult)
        assert result.technical_success is True
        assert result.data is not None
        assert "final_answer" in result.data
        assert result.side_effect is False  # Только генерация, нет side effects


# ============================================================================
# ТЕСТЫ DATA_ANALYSIS_SKILL
# ============================================================================

class TestDataAnalysisSkillIntegration:
    """Интеграционные тесты DataAnalysisSkill"""

    @pytest.mark.asyncio
    async def test_analyze_step_data(self, action_executor, component_config):
        """Тест: анализ данных шага"""
        from core.application.skills.data_analysis.skill import DataAnalysisSkill

        executor, app_context = action_executor

        skill = DataAnalysisSkill(
            name="data_analysis",
            application_context=app_context,
            component_config=component_config,
            executor=executor
        )

        await skill.initialize()

        capabilities = skill.get_capabilities()
        analyze_cap = next(c for c in capabilities if c.name == "data_analysis.analyze_step_data")

        # Мокаем executor для LLM вызова
        async def mock_execute_action(action_name, parameters, context):
            if action_name == "llm.generate_structured":
                return ExecutionResult(
                    status="success",
                    result={
                        "parsed_content": {
                            "answer": "Анализ показывает положительные результаты",
                            "confidence": 0.75,
                            "evidence": ["Данные обработаны"]
                        }
                    },
                    metadata={"parsing_attempts": 1, "tokens_used": 150}
                )
            return ExecutionResult(status="success", result={})

        executor.execute_action = mock_execute_action

        from core.application.agent.components.action_executor import ExecutionContext
        result = await skill.execute(
            capability=analyze_cap,
            parameters={
                "step_id": "step_001",
                "question": "Что показывают данные?",
                "data_source": {
                    "type": "memory",
                    "content": "Тестовые данные для анализа"
                },
                "analysis_config": {
                    "aggregation_method": "summary",
                    "max_response_tokens": 500
                }
            },
            execution_context=ExecutionContext(
                session_context=app_context.session_context,
                available_capabilities=[cap.name for cap in skill.get_capabilities()]
            )
        )

        # Проверяем результат
        assert isinstance(result, SkillResult)
        assert result.technical_success is True
        assert result.data is not None
        assert "answer" in result.data
        assert result.side_effect is True  # Чтение данных (file/DB)


# ============================================================================
# СКВОЗНЫЕ ТЕСТЫ
# ============================================================================

class TestSkillsEndToEnd:
    """Сквозные тесты workflow с несколькими skills"""

    @pytest.mark.asyncio
    async def test_planning_then_final_answer(self, action_executor, component_config):
        """Тест: планирование → выполнение → финальный ответ"""
        from core.application.skills.planning.skill import PlanningSkill
        from core.application.skills.final_answer.skill import FinalAnswerSkill

        executor, app_context = action_executor

        # 1. Создаём план
        planning_skill = PlanningSkill(
            name="planning",
            application_context=app_context,
            component_config=component_config,
            executor=executor
        )
        await planning_skill.initialize()

        # 2. Генерируем финальный ответ
        final_answer_skill = FinalAnswerSkill(
            name="final_answer",
            application_context=app_context,
            component_config=component_config,
            executor=executor
        )
        await final_answer_skill.initialize()

        # Мокаем executor
        async def mock_execute_action(action_name, parameters, context):
            if action_name == "llm.generate_structured":
                prompt = parameters.get("prompt", "")
                if "planning" in prompt.lower() or "plan" in prompt.lower():
                    return ExecutionResult(
                        status="success",
                        result={
                            "parsed_content": {
                                "plan_id": "test_plan_001",
                                "steps": [{"step_id": "step_1", "action": "Шаг 1", "status": "pending"}]
                            }
                        },
                        metadata={"parsing_attempts": 1}
                    )
                else:
                    return ExecutionResult(
                        status="success",
                        result={
                            "parsed_content": {
                                "answer": "Финальный ответ",
                                "confidence": 0.8
                            }
                        },
                        metadata={"parsing_attempts": 1}
                    )
            elif action_name == "context.record_plan":
                return ExecutionResult(status="success", result={"item_id": "plan_001"})
            elif action_name == "context.get_all_items":
                return ExecutionResult(status="success", result={"items": {}})
            elif action_name == "context.get_step_history":
                return ExecutionResult(status="success", result={"steps": []})
            elif action_name == "context.get_current_plan":
                return ExecutionResult(
                    status="success",
                    result={"plan_id": "test_plan_001", "steps": []},
                    metadata={"exists": True}
                )
            return ExecutionResult(status="success", result={})

        executor.execute_action = mock_execute_action

        from core.application.agent.components.action_executor import ExecutionContext

        # Выполняем planning
        planning_caps = planning_skill.get_capabilities()
        create_plan_cap = next(c for c in planning_caps if c.name == "planning.create_plan")

        planning_result = await planning_skill.execute(
            capability=create_plan_cap,
            parameters={"goal": "Тестовая цель", "max_steps": 3},
            execution_context=ExecutionContext(
                session_context=app_context.session_context,
                available_capabilities=[cap.name for cap in planning_skill.get_capabilities()]
            )
        )

        assert isinstance(planning_result, SkillResult)
        assert planning_result.technical_success is True
        assert planning_result.side_effect is True

        # Выполняем final_answer
        final_answer_caps = final_answer_skill.get_capabilities()
        generate_cap = next(c for c in final_answer_caps if c.name == "final_answer.generate")

        final_result = await final_answer_skill.execute(
            capability=generate_cap,
            parameters={"format_type": "concise"},
            execution_context=ExecutionContext(
                session_context=app_context.session_context,
                available_capabilities=[cap.name for cap in final_answer_skill.get_capabilities()]
            )
        )

        assert isinstance(final_result, SkillResult)
        assert final_result.technical_success is True
        assert final_result.side_effect is False


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

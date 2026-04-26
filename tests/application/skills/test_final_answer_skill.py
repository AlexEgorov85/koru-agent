"""
Интеграционные тесты для FinalAnswerSkill.

Проверяют:
1. Валидацию входных параметров (goal, decision_reasoning, etc.)
2. Генерацию финального ответа через executor
3. Работу с session_context
4. Обработку fallback-режима

ЗАПУСК:
    pytest tests/application/skills/test_final_answer_skill.py -v -s
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any
import yaml
from pathlib import Path

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.data.capability import Capability


def load_contract_schema(capability: str, direction: str):
    """Загружает схему контракта из YAML файла и возвращает Contract объект."""
    from core.models.data.contract import Contract
    from core.models.enums.common_enums import ComponentType, ContractDirection, PromptStatus
    
    contract_path = Path("data") / "contracts" / "skill" / "final_answer" / f"final_answer.generate_{direction}_v1.0.0.yaml"
    with open(contract_path, 'r', encoding='utf-8') as f:
        contract_data = yaml.safe_load(f)
    
    # Создаём Contract объект который скомпилирует JSON Schema в Pydantic модель
    contract = Contract(
        capability=contract_data['capability'],
        version=contract_data['version'],
        status=PromptStatus(contract_data['status']),
        component_type=ComponentType(contract_data['component_type']),
        direction=ContractDirection(contract_data['direction']),
        schema_data=contract_data['schema_data'],
        description=contract_data.get('description', '')
    )
    return contract


class TestFinalAnswerInputValidation:
    """Тесты валидации входных параметров final_answer.generate"""

    def test_valid_input_with_all_fields(self):
        """Валидный input со всеми полями"""
        # Загружаем схему из YAML через Contract
        contract = load_contract_schema("final_answer.generate", "input")
        
        # Валидные данные
        valid_data = {
            "goal": "Сколько проверок было проведено в 2024?",
            "decision_reasoning": "Цель достигнута, все данные собраны",
            "is_fallback": False,
            "executed_steps": 3,
            "include_steps": True,
            "include_evidence": True,
            "format_type": "detailed",
            "confidence_threshold": 0.7,
            "max_sources": 10
        }
        
        # Валидация должна пройти без ошибок (используем pydantic_schema из Contract)
        result = contract.pydantic_schema.model_validate(valid_data)
        assert result is not None
        assert result.goal == valid_data["goal"]
        assert result.decision_reasoning == valid_data["decision_reasoning"]

    def test_valid_input_minimal(self):
        """Минимальный валидный input (пустой required)"""
        contract = load_contract_schema("final_answer.generate", "input")
        
        # Минимальные данные (все поля опциональны)
        minimal_data = {}
        result = contract.pydantic_schema.model_validate(minimal_data)
        assert result is not None

    def test_invalid_extra_field_rejected(self):
        """Extra поля должны отклоняться (additionalProperties: false)"""
        from pydantic import ValidationError
        
        contract = load_contract_schema("final_answer.generate", "input")
        
        # Данные с extra полем
        invalid_data = {
            "goal": "Test goal",
            "unknown_field": "should be rejected"
        }
        
        # Должна быть ошибка валидации
        with pytest.raises(ValidationError) as exc_info:
            contract.pydantic_schema.model_validate(invalid_data)
        
        assert "extra_forbidden" in str(exc_info.value) or "Extra inputs are not permitted" in str(exc_info.value)

    def test_goal_and_decision_reasoning_are_strings(self):
        """goal и decision_reasoning должны быть строками"""
        contract = load_contract_schema("final_answer.generate", "input")
        
        # Данные с правильными типами
        valid_data = {
            "goal": "Test goal string",
            "decision_reasoning": "Test reasoning string"
        }
        
        result = contract.pydantic_schema.model_validate(valid_data)
        assert isinstance(result.goal, str)
        assert isinstance(result.decision_reasoning, str)


class TestFinalAnswerSkillExecution:
    """Тесты выполнения FinalAnswerSkill"""

    @pytest_asyncio.fixture
    async def mock_executor(self):
        """Mock executor для тестов"""
        executor = AsyncMock()
        
        # Mock для context.get_all_items
        executor.execute_action = AsyncMock()
        
        async def mock_execute_action(action_name, parameters, context):
            if action_name == "context.get_all_items":
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"items": {}}
                )
            elif action_name == "llm.generate":
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"text": "Финальный ответ на тестовый запрос"}
                )
            return ExecutionResult(status=ExecutionStatus.COMPLETED, data={})
        
        executor.execute_action.side_effect = mock_execute_action
        return executor

    @pytest_asyncio.fixture
    async def mock_session_context(self):
        """Mock session_context для тестов"""
        session_context = MagicMock()
        session_context.get_goal = MagicMock(return_value="Тестовая цель")
        session_context.dialogue_history = MagicMock()
        session_context.dialogue_history.format_for_prompt = MagicMock(return_value="")
        session_context.data_context = MagicMock()
        session_context.data_context.count = MagicMock(return_value=0)
        session_context.session_id = "test-session-001"
        return session_context

    @pytest_asyncio.fixture
    async def final_answer_skill(self, mock_executor, real_component_config):
        """FinalAnswerSkill для тестов"""
        from core.components.skills.final_answer.skill import FinalAnswerSkill
        
        skill = FinalAnswerSkill(
            name="final_answer",
            component_config=real_component_config,
            executor=mock_executor
        )
        
        # Мокаем промпты и контракты
        skill.prompts = {
            "final_answer.generate": MagicMock(
                content="Создай финальный ответ на основе данных.\n\n{goal}\n{dialogue_history}\n{observations}\n{thoughts}\n{actions}"
            )
        }
        skill.input_contracts = {"final_answer.generate": MagicMock()}
        skill.output_contracts = {"final_answer.generate": MagicMock()}
        
        await skill.initialize()
        return skill

    @pytest.mark.asyncio
    async def test_skill_executes_with_valid_parameters(
        self, final_answer_skill, mock_session_context
    ):
        """Skill выполняется с валидными параметрами"""
        from core.components.action_executor import ExecutionContext
        
        exec_context = ExecutionContext(
            session_context=mock_session_context,
            session_id="test-session-001"
        )
        
        parameters = {
            "goal": "Тестовая цель",
            "decision_reasoning": "Данные собраны, цель достигнута",
            "is_fallback": False,
            "executed_steps": 2,
            "format_type": "detailed"
        }
        
        capability = Capability(
            name="final_answer.generate",
            description="Генерация финального ответа",
            skill_name="final_answer"
        )
        
        # Выполняем skill
        result = await final_answer_skill.execute(
            capability=capability,
            parameters=parameters,
            execution_context=exec_context
        )
        
        # Проверяем результат
        assert result.status == ExecutionStatus.COMPLETED
        assert result.data is not None
        assert "final_answer" in result.data

    @pytest.mark.asyncio
    async def test_skill_uses_goal_from_parameters(
        self, final_answer_skill, mock_session_context
    ):
        """Skill использует goal из parameters (приоритет над session_context)"""
        from core.components.action_executor import ExecutionContext
        
        exec_context = ExecutionContext(
            session_context=mock_session_context,
            session_id="test-session-001"
        )
        
        parameters = {
            "goal": "Goal from parameters",  # Этот goal должен использоваться
            "decision_reasoning": "Test reasoning"
        }
        
        capability = Capability(
            name="final_answer.generate",
            description="Генерация финального ответа",
            skill_name="final_answer"
        )
        
        result = await final_answer_skill.execute(
            capability=capability,
            parameters=parameters,
            execution_context=exec_context
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        
        # Проверяем что executor был вызван (для сбора контекста)
        assert final_answer_skill.executor.execute_action.called

    @pytest.mark.asyncio
    async def test_skill_handles_fallback_mode(
        self, final_answer_skill, mock_session_context
    ):
        """Skill корректно обрабатывает fallback-режим"""
        from core.components.action_executor import ExecutionContext
        
        exec_context = ExecutionContext(
            session_context=mock_session_context,
            session_id="test-session-001"
        )
        
        parameters = {
            "goal": "Тестовая цель",
            "decision_reasoning": "Достигнут лимит шагов",
            "is_fallback": True,  # Fallback режим
            "executed_steps": 10,  # Лимит достигнут
            "format_type": "concise"
        }
        
        capability = Capability(
            name="final_answer.generate",
            description="Генерация финального ответа",
            skill_name="final_answer"
        )
        
        result = await final_answer_skill.execute(
            capability=capability,
            parameters=parameters,
            execution_context=exec_context
        )
        
        # Skill должен выполниться даже в fallback режиме
        assert result.status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_skill_collects_context_via_executor(
        self, final_answer_skill, mock_session_context, mock_executor
    ):
        """Skill собирает контекст через executor.execute_action"""
        from core.components.action_executor import ExecutionContext
        
        exec_context = ExecutionContext(
            session_context=mock_session_context,
            session_id="test-session-001"
        )
        
        parameters = {
            "goal": "Тестовая цель",
            "decision_reasoning": "Test"
        }
        
        capability = Capability(
            name="final_answer.generate",
            description="Генерация финального ответа",
            skill_name="final_answer"
        )
        
        await final_answer_skill.execute(
            capability=capability,
            parameters=parameters,
            execution_context=exec_context
        )
        
        # Проверяем что context.get_all_items был вызван
        calls = [call[0][0] for call in mock_executor.execute_action.call_args_list]
        assert "context.get_all_items" in calls


class TestFinalAnswerWithMockLLM:
    """Интеграционные тесты final_answer с MockLLM"""

    @pytest_asyncio.fixture
    async def infrastructure_with_mock_llm(self):
        """InfrastructureContext с MockLLM"""
        from core.config.models import SystemConfig
        from core.infrastructure_context.infrastructure_context import InfrastructureContext
        from core.models.data.resource import ResourceInfo
        from core.models.enums.common_enums import ResourceType
        from core.infrastructure_context.resource_registry import ResourceRegistry
        from tests.mocks.interfaces import MockLLM
        
        config = SystemConfig(
            llm_providers={},
            db_providers={},
            data_dir='data'
        )
        
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        # Создаём новый registry с MockLLM
        old_registry = infra.resource_registry
        infra.resource_registry = ResourceRegistry()
        infra._initialized = True
        
        # Регистрируем MockLLM
        mock_llm = MockLLM(default_response="Финальный ответ от MockLLM")
        mock_llm.register_response("final_answer.generate", "Финальный ответ на основе контекста")
        
        infra.resource_registry.register_resource(
            ResourceInfo(
                name='mock_llm',
                resource_type=ResourceType.LLM,
                instance=mock_llm
            )
        )
        
        # Копируем DB провайдеры
        for res in old_registry.get_resources_by_type(ResourceType.DATABASE):
            infra.resource_registry.register_resource(res)
        
        yield infra
        await infra.shutdown()

    @pytest_asyncio.fixture
    async def app_context(self, infrastructure_with_mock_llm):
        """ApplicationContext с discovery"""
        from core.config.app_config import AppConfig
        from core.application_context.application_context import ApplicationContext
        
        app_config = AppConfig.from_discovery(
            profile="dev",
            data_dir=infrastructure_with_mock_llm.config.data_dir
        )
        
        ctx = ApplicationContext(
            infrastructure_context=infrastructure_with_mock_llm,
            config=app_config,
            profile="dev"
        )
        await ctx.initialize()
        
        yield ctx
        await ctx.shutdown()

    @pytest.mark.asyncio
    async def test_final_answer_integration_with_mock_llm(
        self, app_context
    ):
        """Интеграционный тест final_answer.generate с MockLLM"""
        from core.components.action_executor import ActionExecutor
        from core.components.action_executor import ExecutionContext
        from core.session_context.session_context import SessionContext
        from core.application_context.application_context import ComponentType
        
        # Получаем skill из app_context (с правильно загруженными ресурсами)
        skill = app_context.components.get(ComponentType.SKILL, "final_answer")
        assert skill is not None, "final_answer skill not found in app_context"
        
        executor = ActionExecutor(application_context=app_context)
        
        # Создаём session_context с данными
        session_context = SessionContext(
            session_id="test-session-final-answer"
        )
        session_context.set_goal("Тестовая цель для интеграционного теста")
        session_context.record_observation("Тестовое наблюдение", source="test")
        
        exec_context = ExecutionContext(
            session_context=session_context,
            session_id="test-session-final-answer"
        )
        
        parameters = {
            "goal": "Тестовая цель для интеграционного теста",
            "decision_reasoning": "Интеграционный тест с MockLLM",
            "is_fallback": False,
            "executed_steps": 1,
            "format_type": "detailed"
        }
        
        capability = Capability(
            name="final_answer.generate",
            description="Генерация финального ответа",
            skill_name="final_answer"
        )
        
        # Выполняем skill
        result = await skill.execute(
            capability=capability,
            parameters=parameters,
            execution_context=exec_context
        )
        
        # Проверяем результат
        assert result.status == ExecutionStatus.COMPLETED
        assert result.data is not None
        assert "final_answer" in result.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

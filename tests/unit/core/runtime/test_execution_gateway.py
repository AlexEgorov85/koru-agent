"""
Тесты для ExecutionGateway.
Проверяют работу шлюза в различных реальных сценариях:
- Успешное выполнение capability
- Ошибки поиска навыков
- Валидация параметров
- Обработка ошибок с политиками повторных попыток
- Различные типы ошибок (TRANSIENT, INVALID_INPUT, TOOL_FAILURE, FATAL)
- Работа с контекстом сессии
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, List

from core.retry_policy.retry_and_error_policy import RetryPolicy
from core.session_context.session_context import SessionContext
from core.skills.base_skill import BaseSkill
from core.system_context.execution_gateway import ExecutionGateway
from models.capability import Capability
from models.execution import ExecutionStatus
from models.retry_policy import ErrorCategory, RetryDecision, RetryResult
from models.structured_actions import ActionSchema, ActionSchemaRegistry, ActionValidator, StructuredActionError



# ===================================================================
# Фикстуры для тестов
# ===================================================================

@pytest.fixture
def mock_retry_policy():
    """Фикстура с моком RetryPolicy."""
    policy = MagicMock(spec=RetryPolicy)
    policy.evaluate.return_value = RetryResult(
        decision=RetryDecision.RETRY,
        delay_seconds=0.1,
        reason="test_retry"
    )
    return policy

@pytest.fixture
def mock_system_context():
    """Фикстура с моком SystemContext."""
    system = MagicMock()
    system.get_skill_for_capability = AsyncMock()
    system.get_resource = MagicMock()
    return system

@pytest.fixture
def session_context():
    """Фикстура с реальным SessionContext для тестов."""
    return SessionContext()

@pytest.fixture
def sample_capability():
    """Фикстура с примером capability."""
    return Capability(
        name="test.capability",
        description="Тестовая capability",
        parameters_schema={"type": "object", "properties": {"param": {"type": "string"}}},
        skill_name="test_skill"
    )

@pytest.fixture
def mock_skill():
    """Фикстура с моком навыка."""
    skill = MagicMock(spec=BaseSkill)
    skill.name = "test_skill"
    skill.get_metadata.return_value = MagicMock(input_schema={"type": "object"})
    skill.run = AsyncMock(return_value={"result": "success"})
    return skill

@pytest.fixture
def mock_action_validator():
    """Фикстура с моком ActionValidator."""
    validator = MagicMock(spec=ActionValidator)
    validator.validate.return_value = {"param": "validated_value"}
    return validator

# ===================================================================
# Тестовые классы и схемы
# ===================================================================

class TestActionSchema(ActionSchema):
    """Тестовая схема для валидации действий."""
    @classmethod
    def validate(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if "invalid" in payload.get("param", ""):
            raise ValueError("Invalid parameter value")
        return payload

# ===================================================================
# Тесты ExecutionGateway
# ===================================================================

class TestExecutionGateway:
    """Тесты для ExecutionGateway."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, mock_system_context, mock_retry_policy, mock_action_validator):
        """Настройка перед каждым тестом."""
        self.gateway = ExecutionGateway(
            system_context=mock_system_context,
            retry_policy=mock_retry_policy,
            action_validator=mock_action_validator
        )
        self.mock_system_context = mock_system_context
        self.mock_retry_policy = mock_retry_policy
        self.mock_action_validator = mock_action_validator
    
    @pytest.mark.asyncio
    async def test_successful_capability_execution(self, sample_capability, session_context, mock_skill):
        """Тест успешного выполнения capability."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        self.mock_action_validator.validate.return_value = {"param": "test_value"}
        
        # Действие
        result = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"param": "test_value"},
            session=session_context,
            step_number=1
        )
        
        # Проверки
        assert result.status == ExecutionStatus.SUCCESS
        assert result.observation_item_id is not None
        assert result.summary == "Capability test.capability executed successfully"
        assert result.error is None
        
        # Проверка вызовов
        self.mock_system_context.get_skill_for_capability.assert_called_once_with("test.capability")
        mock_skill.run.assert_called_once_with(
            capability="test.capability",
            parameters={"param": "test_value"},
            session=session_context
        )
        
        # Проверка контекста
        assert session_context.data_context.count() == 2  # action + observation
        assert len(session_context.step_context.steps) == 1
        
        # Проверка шага
        step = session_context.step_context.steps[0]
        assert step.step_number == 1
        assert step.capability_name == "test.capability"
        assert step.skill_name == "test_skill"
    
    @pytest.mark.asyncio
    async def test_skill_not_found(self, sample_capability, session_context):
        """Тест обработки ситуации, когда навык не найден."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = None
        
        # Действие
        result = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"param": "test_value"},
            session=session_context,
            step_number=1
        )
        
        # Проверки
        assert result.status == ExecutionStatus.FAILED
        assert result.observation_item_id is None
        assert "Skill not found for capability test.capability" in result.summary
        assert result.error == "SKILL_NOT_FOUND"
        
        # Проверка, что другие методы не вызывались
        self.mock_action_validator.validate.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_validation_failure(self, sample_capability, session_context, mock_skill):
        """Тест обработки ошибок валидации параметров."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        self.mock_action_validator.validate.side_effect = StructuredActionError("Invalid parameter format")
        
        # Действие
        result = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"invalid_param": "value"},
            session=session_context,
            step_number=1
        )
        
        # Проверки
        assert result.status == ExecutionStatus.FAILED
        assert result.observation_item_id is None
        assert "Invalid action payload" in result.summary
        assert result.error == "INVALID_INPUT"
        
        # Проверка вызова политики
        self.mock_retry_policy.evaluate.assert_called_once()
        error_info = self.mock_retry_policy.evaluate.call_args[1]["error"]
        assert error_info.category == ErrorCategory.INVALID_INPUT
    
    @pytest.mark.asyncio
    async def test_skill_execution_failure_with_retry(self, sample_capability, session_context, mock_skill):
        """Тест обработки ошибок выполнения навыка с повторными попытками."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        mock_skill.run.side_effect = [
            Exception("Temporary failure"),
            {"result": "success after retry"}
        ]
        
        # Настройка политики повторов
        self.mock_retry_policy.evaluate.side_effect = [
            RetryResult(decision=RetryDecision.RETRY, delay_seconds=0.1, reason="retry_reason"),
            RetryResult(decision=RetryDecision.RETRY, delay_seconds=0.2, reason="retry_reason"),
            RetryResult(decision=RetryDecision.FAIL, reason="final_fail")
        ]
        
        # Патчим asyncio.sleep для ускорения тестов
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Действие
            result = await self.gateway.execute_capability(
                capability=sample_capability,
                action_payload={"param": "test_value"},
                session=session_context,
                step_number=1
            )
            
            # Проверки
            assert result.status == ExecutionStatus.SUCCESS
            assert result.observation_item_id is not None
            assert "Capability test.capability executed successfully" in result.summary
            
            # Проверка количества вызовов
            assert mock_skill.run.call_count == 2
            assert mock_sleep.call_count == 1  # Один раз был сделан retry
            
            # Проверка контекста
            assert session_context.data_context.count() == 2  # action + observation
            assert len(session_context.step_context.steps) == 1
    
    @pytest.mark.asyncio
    async def test_max_retry_limit_exceeded(self, sample_capability, session_context, mock_skill):
        """Тест превышения лимита повторных попыток."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        mock_skill.run.side_effect = Exception("Persistent failure")
        
        # Настройка политики повторов
        self.mock_retry_policy.evaluate.return_value = RetryResult(
            decision=RetryDecision.FAIL,
            reason="Retry limit exceeded"
        )
        
        # Действие
        result = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"param": "test_value"},
            session=session_context,
            step_number=1
        )
        
        # Проверки
        assert result.status == ExecutionStatus.FAILED
        assert result.observation_item_id is None
        assert "Retry limit exceeded" in result.summary
        assert result.error == "FAILED"
        
        # Проверка количества попыток
        assert mock_skill.run.call_count == 1  # Должна быть только одна попытка, так как политика сразу вернула FAIL
    
    @pytest.mark.asyncio
    async def test_transient_error_handling(self, sample_capability, session_context, mock_skill):
        """Тест обработки временных ошибок (TRANSIENT)."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        mock_skill.run.side_effect = [
            Exception("Network timeout"),
            {"result": "success"}
        ]
        
        # Настройка политики для TRANSIENT ошибок
        self.mock_retry_policy.evaluate.side_effect = [
            RetryResult(decision=RetryDecision.RETRY, delay_seconds=0.1, reason="transient_error"),
            RetryResult(decision=RetryDecision.RETRY, delay_seconds=0.1, reason="transient_error")
        ]
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Действие
            result = await self.gateway.execute_capability(
                capability=sample_capability,
                action_payload={"param": "test_value"},
                session=session_context,
                step_number=1
            )
            
            # Проверки
            assert result.status == ExecutionStatus.SUCCESS
            assert result.observation_item_id is not None
            
            # Проверка вызова политики с правильной категорией ошибки
            error_info = self.mock_retry_policy.evaluate.call_args_list[0][1]["error"]
            assert error_info.category == ErrorCategory.TRANSIENT
    
    @pytest.mark.asyncio
    async def test_tool_failure_error_handling(self, sample_capability, session_context, mock_skill):
        """Тест обработки ошибок внешних инструментов (TOOL_FAILURE)."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        mock_skill.run.side_effect = Exception("External tool error")
        
        # Настройка политики для TOOL_FAILURE ошибок
        self.mock_retry_policy.evaluate.return_value = RetryResult(
            decision=RetryDecision.RETRY,
            delay_seconds=0.1,
            reason="tool_failure"
        )
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            # Действие
            result = await self.gateway.execute_capability(
                capability=sample_capability,
                action_payload={"param": "test_value"},
                session=session_context,
                step_number=1
            )
            
            # Проверки (первый вызов должен быть неудачным, но retry_policy позволит повторить)
            # В реальном коде нужно добавить логику для повторных попыток
            assert result.status == ExecutionStatus.FAILED  # Пока не реализованы повторные попытки в коде
    
    @pytest.mark.asyncio
    async def test_invalid_input_error_handling(self, sample_capability, session_context, mock_skill):
        """Тест обработки ошибок валидации входных данных (INVALID_INPUT)."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        self.mock_action_validator.validate.side_effect = StructuredActionError("Invalid input format")
        
        # Настройка политики для INVALID_INPUT ошибок
        self.mock_retry_policy.evaluate.return_value = RetryResult(
            decision=RetryDecision.ABORT,
            reason="invalid_input"
        )
        
        # Действие
        result = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"invalid": "data"},
            session=session_context,
            step_number=1
        )
        
        # Проверки
        assert result.status == ExecutionStatus.FAILED
        assert result.error == "INVALID_INPUT"
        assert "Invalid action payload" in result.summary
        
        # Проверка, что навык не был вызван
        mock_skill.run.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_fatal_error_handling(self, sample_capability, session_context, mock_skill):
        """Тест обработки критических ошибок (FATAL)."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        mock_skill.run.side_effect = Exception("Fatal system error")
        
        # Настройка политики для FATAL ошибок
        self.mock_retry_policy.evaluate.return_value = RetryResult(
            decision=RetryDecision.FAIL,
            reason="fatal_error"
        )
        
        # Действие
        result = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"param": "test_value"},
            session=session_context,
            step_number=1
        )
        
        # Проверки
        assert result.status == ExecutionStatus.FAILED
        assert result.error == "FAILED"
        assert "fatal_error" in result.summary
    
    @pytest.mark.asyncio
    async def test_context_registration(self, sample_capability, session_context, mock_skill):
        """Тест корректной регистрации действий и результатов в контексте."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        self.mock_action_validator.validate.return_value = {"param": "test_value"}
        
        # Действие
        result = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"param": "test_value"},
            session=session_context,
            step_number=1
        )
        
        # Проверки контекста
        assert session_context.data_context.count() == 2
        
        # Получение элементов контекста
        action_item = None
        observation_item = None
        
        for item_id, item in session_context.data_context.items.items():
            if item.item_type == "ACTION":
                action_item = item
            elif item.item_type == "OBSERVATION":
                observation_item = item
        
        # Проверки action item
        assert action_item is not None
        assert action_item.content == {"param": "test_value"}
        
        # Проверки observation item
        assert observation_item is not None
        assert observation_item.content == {"result": "success"}
        
        # Проверка шага
        assert len(session_context.step_context.steps) == 1
        step = session_context.step_context.steps[0]
        assert step.step_number == 1
        assert step.capability_name == "test.capability"
        assert step.skill_name == "test_skill"
        assert step.action_item_id == action_item.item_id
        assert step.observation_item_ids == [observation_item.item_id]
        assert step.summary == sample_capability.description
    
    @pytest.mark.asyncio
    async def test_multiple_step_execution(self, sample_capability, session_context, mock_skill):
        """Тест выполнения нескольких шагов подряд."""
        # Настройка моков
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        self.mock_action_validator.validate.return_value = {"param": "test_value"}
        
        # Выполнение первого шага
        result1 = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"param": "step1"},
            session=session_context,
            step_number=1
        )
        
        # Выполнение второго шага
        result2 = await self.gateway.execute_capability(
            capability=sample_capability,
            action_payload={"param": "step2"},
            session=session_context,
            step_number=2
        )
        
        # Проверки
        assert result1.status == ExecutionStatus.SUCCESS
        assert result2.status == ExecutionStatus.SUCCESS
        
        # Проверка контекста
        assert session_context.data_context.count() == 4  # 2 actions + 2 observations
        assert len(session_context.step_context.steps) == 2
        
        # Проверка шагов
        step1 = session_context.step_context.steps[0]
        step2 = session_context.step_context.steps[1]
        
        assert step1.step_number == 1
        assert step2.step_number == 2
        assert step1.capability_name == step2.capability_name == "test.capability"
        
        # Проверка элементов контекста для второго шага
        second_action_item = session_context.data_context.get_item(step2.action_item_id)
        second_observation_item = session_context.data_context.get_item(step2.observation_item_ids[0])
        
        assert second_action_item.content == {"param": "step2"}
        assert second_observation_item.content == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_execution_with_real_action_schema(self, session_context):
        """Тест выполнения с реальной схемой валидации действий."""
        # Создание реальной схемы валидации
        registry = ActionSchemaRegistry()
        registry.register("test.capability", TestActionSchema)
        validator = ActionValidator(registry)
        
        # Создание gateway с реальным валидатором
        gateway = ExecutionGateway(
            system_context=self.mock_system_context,
            action_validator=validator
        )
        
        mock_skill = MagicMock(spec=BaseSkill)
        mock_skill.name = "test_skill"
        mock_skill.get_metadata.return_value = MagicMock(input_schema={"type": "object"})
        mock_skill.run = AsyncMock(return_value={"result": "success"})
        
        capability = Capability(
            name="test.capability",
            description="Тестовая capability с реальной схемой",
            parameters_schema={"type": "object", "properties": {"param": {"type": "string"}}},
            skill_name="test_skill"
        )
        
        self.mock_system_context.get_skill_for_capability.return_value = mock_skill
        
        # Успешный вызов
        result1 = await gateway.execute_capability(
            capability=capability,
            action_payload={"param": "valid_value"},
            session=session_context,
            step_number=1
        )
        
        assert result1.status == ExecutionStatus.SUCCESS
        
        # Вызов с невалидными параметрами
        result2 = await gateway.execute_capability(
            capability=capability,
            action_payload={"param": "invalid_value"},
            session=session_context,
            step_number=2
        )
        
        assert result2.status == ExecutionStatus.FAILED
        assert result2.error == "INVALID_INPUT"
        assert "Invalid parameter value" in result2.summary

# ===================================================================
# Интеграционные тесты
# ===================================================================

@pytest.mark.asyncio
async def test_end_to_end_execution_flow(session_context):
    """
    Интеграционный тест полного цикла выполнения.
    Тестирует реальный сценарий работы с несколькими шагами и различными типами ошибок.
    """
    # Создание реальных компонентов
    retry_policy = RetryPolicy(max_retries=2)
    
    # Мок SystemContext
    system_context = MagicMock()
    
    # Создание gateway
    gateway = ExecutionGateway(
        system_context=system_context,
        retry_policy=retry_policy
    )
    
    # Создание тестового навыка
    class TestSkill(BaseSkill):
        name = "integration_test_skill"
        
        async def run(self, action_payload: Dict[str, Any], session: SessionContext) -> Dict[str, Any]:
            param = action_payload.get("param", "")
            
            if "error" in param:
                raise Exception(f"Test error for param: {param}")
            if "invalid" in param:
                raise StructuredActionError("Invalid parameter format")
            
            return {"result": f"success_{param}"}
        
        def get_capabilities(self) -> List[Capability]:
            return [
                Capability(
                    name="integration.test",
                    description="Интеграционная тестовая capability",
                    parameters_schema={"type": "object", "properties": {"param": {"type": "string"}}},
                    skill_name=self.name
                )
            ]
        
        def get_capability_by_name(self, capability_name: str) -> Capability:
            return self.get_capabilities()[0]
    
    test_skill = TestSkill()
    
    # Моки для SystemContext
    system_context.get_skill_for_capability.return_value = test_skill
    
    # Тестовый capability
    test_capability = test_skill.get_capability_by_name("integration.test")
    
    # Шаг 1: Успешное выполнение
    result1 = await gateway.execute_capability(
        capability=test_capability,
        action_payload={"param": "valid1"},
        session=session_context,
        step_number=1
    )
    
    assert result1.status == ExecutionStatus.SUCCESS
    assert session_context.data_context.count() == 2
    assert len(session_context.step_context.steps) == 1
    
    # Шаг 2: Временная ошибка с успешным повтором
    system_context.get_skill_for_capability.return_value = test_skill
    test_skill.run.side_effect = [
        Exception("Network timeout"),
        {"result": "success_after_retry"}
    ]
    
    result2 = await gateway.execute_capability(
        capability=test_capability,
        action_payload={"param": "valid2_with_retry"},
        session=session_context,
        step_number=2
    )
    
    assert result2.status == ExecutionStatus.SUCCESS
    assert session_context.data_context.count() == 4
    assert len(session_context.step_context.steps) == 2
    
    # Шаг 3: Ошибка валидации (должна вызвать ABORT)
    with patch.object(gateway.retry_policy, 'evaluate') as mock_evaluate:
        mock_evaluate.return_value = RetryResult(
            decision=RetryDecision.ABORT,
            reason="validation_failed"
        )
        
        result3 = await gateway.execute_capability(
            capability=test_capability,
            action_payload={"param": "invalid_value"},
            session=session_context,
            step_number=3
        )
        
        assert result3.status == ExecutionStatus.FAILED
        assert result3.error == "INVALID_INPUT"
    
    # Шаг 4: Критическая ошибка (должна вызвать FAIL)
    with patch.object(gateway.retry_policy, 'evaluate') as mock_evaluate:
        mock_evaluate.return_value = RetryResult(
            decision=RetryDecision.FAIL,
            reason="fatal_system_error"
        )
        
        result4 = await gateway.execute_capability(
            capability=test_capability,
            action_payload={"param": "error_fatal"},
            session=session_context,
            step_number=4
        )
        
        assert result4.status == ExecutionStatus.FAILED
        assert result4.error == "FAILED"
    
    # Финальная проверка состояния контекста
    assert session_context.data_context.count() == 8  # 2 actions + 2 observations для каждого из 4 шагов
    assert len(session_context.step_context.steps) == 4
    
    # Проверка последнего шага
    last_step = session_context.step_context.steps[-1]
    assert last_step.step_number == 4
    assert last_step.capability_name == "integration.test"
    assert last_step.summary == "Интеграционная тестовая capability"
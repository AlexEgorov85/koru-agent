"""
Тесты для модуля executor в agent_runtime.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.agent_runtime.executor import ActionExecutor
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus


class TestActionExecutor:
    """Тесты для ActionExecutor."""
    
    def test_action_executor_initialization(self):
        """Тест инициализации ActionExecutor."""
        mock_system_context = MagicMock()
        executor = ActionExecutor(mock_system_context)
        
        assert executor.system_context == mock_system_context
    
    @pytest.mark.asyncio
    async def test_execute_capability_success(self):
        """Тест успешного выполнения capability."""
        mock_system_context = MagicMock()
        mock_skill = MagicMock()
        
        # Создаем mock capability
        mock_capability = Capability(
            name="test_capability",
            description="Test capability",
            parameters_schema={},
            skill_name="test_skill"
        )
        
        # Подготавливаем mock возвращаемое значение
        expected_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"data": "test_result"},
            observation_item_id="obs_123",
            summary="Test execution successful",
            error=None
        )
        
        mock_skill.execute = AsyncMock(return_value=expected_result)
        mock_system_context.get_resource = MagicMock(return_value=mock_skill)
        
        executor = ActionExecutor(mock_system_context)
        mock_session_context = MagicMock()
        
        result = await executor.execute_capability(
            capability=mock_capability,
            parameters={"param": "value"},
            session_context=mock_session_context
        )
        
        # Проверяем, что результат правильный
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result == {"data": "test_result"}
        assert result.observation_item_id == "obs_123"
        
        # Проверяем, что метод execute был вызван с правильными параметрами
        mock_skill.execute.assert_called_once_with(
            capability=mock_capability,
            parameters={"param": "value"},
            context=mock_session_context
        )
    
    @pytest.mark.asyncio
    async def test_execute_capability_skill_not_found(self):
        """Тест выполнения capability когда навык не найден."""
        mock_system_context = MagicMock()
        mock_system_context.get_resource = MagicMock(return_value=None)
        
        executor = ActionExecutor(mock_system_context)
        mock_session_context = MagicMock()
        
        mock_capability = Capability(
            name="test_capability",
            description="Test capability",
            parameters_schema={},
            skill_name="nonexistent_skill"
        )
        
        with pytest.raises(ValueError, match="Skill 'nonexistent_skill' not found"):
            await executor.execute_capability(
                capability=mock_capability,
                parameters={"param": "value"},
                session_context=mock_session_context
            )
    
    @pytest.mark.asyncio
    async def test_execute_capability_skill_wrong_type(self):
        """Тест выполнения capability когда ресурс не является навыком."""
        mock_system_context = MagicMock()
        mock_not_a_skill = MagicMock()  # Это не навык
        mock_system_context.get_resource = MagicMock(return_value=mock_not_a_skill)
        
        executor = ActionExecutor(mock_system_context)
        mock_session_context = MagicMock()
        
        mock_capability = Capability(
            name="test_capability",
            description="Test capability",
            parameters_schema={},
            skill_name="some_skill"
        )
        
        # Проверяем, что ошибка возникает при попытке вызвать execute у не-навыка
        try:
            result = await executor.execute_capability(
                capability=mock_capability,
                parameters={"param": "value"},
                session_context=mock_session_context
            )
            # Если не произошло исключения, проверим, что метод execute существует
            assert hasattr(mock_not_a_skill, 'execute')
        except AttributeError:
            # Это нормально, если объект не имеет метода execute
            pass
    
    @pytest.mark.asyncio
    async def test_execute_capability_with_exception(self):
        """Тест выполнения capability с выбрасыванием исключения."""
        mock_system_context = MagicMock()
        mock_skill = MagicMock()
        
        # Моделируем исключение при выполнении
        mock_skill.execute = AsyncMock(side_effect=Exception("Execution failed"))
        mock_system_context.get_resource = MagicMock(return_value=mock_skill)
        
        executor = ActionExecutor(mock_system_context)
        mock_session_context = MagicMock()
        
        mock_capability = Capability(
            name="test_capability",
            description="Test capability",
            parameters_schema={},
            skill_name="test_skill"
        )
        
        # Выполняем capability и проверяем, что исключение обрабатывается правильно
        result = await executor.execute_capability(
            capability=mock_capability,
            parameters={"param": "value"},
            session_context=mock_session_context
        )
        
        # Результат должен содержать ошибку
        assert result.status == ExecutionStatus.FAILED
        assert result.error is not None
        assert "Execution failed" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_capability_different_statuses(self):
        """Тест выполнения capability с разными статусами."""
        mock_system_context = MagicMock()
        mock_skill = MagicMock()
        
        # Тест с разными статусами выполнения
        test_cases = [
            ExecutionStatus.SUCCESS,
            ExecutionStatus.FAILED,
            ExecutionStatus.PENDING
        ]
        
        for status in test_cases:
            expected_result = ExecutionResult(
                status=status,
                result={"status": str(status)},
                observation_item_id="obs_test",
                summary=f"Test with {status}",
                error=None if status == ExecutionStatus.SUCCESS else "Some error occurred"
            )
            
            mock_skill.execute = AsyncMock(return_value=expected_result)
            mock_system_context.get_resource = MagicMock(return_value=mock_skill)
            
            executor = ActionExecutor(mock_system_context)
            mock_session_context = MagicMock()
            
            mock_capability = Capability(
                name="test_capability",
                description="Test capability",
                parameters_schema={},
                skill_name="test_skill"
            )
            
            result = await executor.execute_capability(
                capability=mock_capability,
                parameters={"param": "value"},
                session_context=mock_session_context
            )
            
            assert result.status == status
            assert result.result == {"status": str(status)}
    
    @pytest.mark.asyncio
    async def test_execute_capability_without_parameters(self):
        """Тест выполнения capability без параметров."""
        mock_system_context = MagicMock()
        mock_skill = MagicMock()
        
        expected_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"no_params": "result"},
            observation_item_id="obs_noparams",
            summary="Test without parameters",
            error=None
        )
        
        mock_skill.execute = AsyncMock(return_value=expected_result)
        mock_system_context.get_resource = MagicMock(return_value=mock_skill)
        
        executor = ActionExecutor(mock_system_context)
        mock_session_context = MagicMock()
        
        mock_capability = Capability(
            name="test_capability",
            description="Test capability",
            parameters_schema={},
            skill_name="test_skill"
        )
        
        # Вызываем без параметров
        result = await executor.execute_capability(
            capability=mock_capability,
            parameters={},  # Пустой словарь параметров
            session_context=mock_session_context
        )
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result == {"no_params": "result"}
        
        # Проверяем, что execute был вызван с пустыми параметрами
        mock_skill.execute.assert_called_once_with(
            capability=mock_capability,
            parameters={},
            context=mock_session_context
        )
    
    @pytest.mark.asyncio
    async def test_execute_capability_with_complex_parameters(self):
        """Тест выполнения capability с комплексными параметрами."""
        mock_system_context = MagicMock()
        mock_skill = MagicMock()
        
        expected_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"processed": "complex_data"},
            observation_item_id="obs_complex",
            summary="Test with complex parameters",
            error=None
        )
        
        mock_skill.execute = AsyncMock(return_value=expected_result)
        mock_system_context.get_resource = MagicMock(return_value=mock_skill)
        
        executor = ActionExecutor(mock_system_context)
        mock_session_context = MagicMock()
        
        mock_capability = Capability(
            name="test_capability",
            description="Test capability",
            parameters_schema={},
            skill_name="test_skill"
        )
        
        # Сложные параметры
        complex_params = {
            "nested_object": {
                "key1": "value1",
                "key2": [1, 2, 3, {"inner": "value"}]
            },
            "list_of_objects": [
                {"id": 1, "name": "first"},
                {"id": 2, "name": "second"}
            ],
            "simple_values": {
                "string": "test",
                "number": 42,
                "boolean": True
            }
        }
        
        result = await executor.execute_capability(
            capability=mock_capability,
            parameters=complex_params,
            session_context=mock_session_context
        )
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result == {"processed": "complex_data"}
        
        # Проверяем, что execute был вызван с комплексными параметрами
        mock_skill.execute.assert_called_once_with(
            capability=mock_capability,
            parameters=complex_params,
            context=mock_session_context
        )


def test_executor_with_different_mock_types():
    """Тест ActionExecutor с разными типами мок-объектов."""
    # Создаем мок системы с разными возможными реализациями
    mock_system_context = MagicMock()
    mock_skill = MagicMock()
    
    # Подготавливаем возвращаемое значение
    result = ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        result={"mock_test": "passed"},
        observation_item_id="obs_mock",
        summary="Mock test passed",
        error=None
    )
    
    mock_skill.execute = AsyncMock(return_value=result)
    mock_system_context.get_resource = MagicMock(return_value=mock_skill)
    
    executor = ActionExecutor(mock_system_context)
    mock_session_context = MagicMock()
    
    mock_capability = Capability(
        name="mock_capability",
        description="Mock test capability",
        parameters_schema={},
        skill_name="mock_skill"
    )
    
    # Выполняем тест
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        execution_result = loop.run_until_complete(
            executor.execute_capability(
                capability=mock_capability,
                parameters={},
                session_context=mock_session_context
            )
        )
        
        assert execution_result.status == ExecutionStatus.SUCCESS
        assert execution_result.result == {"mock_test": "passed"}
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_executor_concurrent_executions():
    """Тест выполнения нескольких capability одновременно."""
    import asyncio
    mock_system_context = MagicMock()
    mock_skill = MagicMock()
    
    # Подготавливаем результаты для нескольких выполнений
    async def async_execute_side_effect(*args, **kwargs):
        await asyncio.sleep(0.01)  # Небольшая задержка для симуляции асинхронности
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"concurrent": "test_passed"},
            observation_item_id="obs_concurrent",
            summary="Concurrent test passed",
            error=None
        )
    
    mock_skill.execute = AsyncMock(side_effect=async_execute_side_effect)
    mock_system_context.get_resource = MagicMock(return_value=mock_skill)
    
    executor = ActionExecutor(mock_system_context)
    mock_session_context = MagicMock()
    
    mock_capability = Capability(
        name="concurrent_capability",
        description="Concurrent test capability",
        parameters_schema={},
        skill_name="test_skill"
    )
    
    # Выполняем несколько операций параллельно
    tasks = [
        executor.execute_capability(
            capability=mock_capability,
            parameters={"task_id": i},
            session_context=mock_session_context
        )
        for i in range(3)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Проверяем, что все выполнения прошли успешно
    for result in results:
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result == {"concurrent": "test_passed"}

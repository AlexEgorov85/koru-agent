"""Тесты для агента выполнения."""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from core.agent_runtime.runtime import AgentRuntime
from core.agent_runtime.execution_context import ExecutionContext
from core.agent_runtime.states import ExecutionState
from core.agent_runtime.task_scheduler import SimpleTaskScheduler, Task, TaskStatus
from core.agent_runtime.checkpoint import CheckpointManager
from core.agent_runtime.strategy_loader import ThinkingPatternLoader
from core.agent_runtime.state import AgentState
from core.agent_runtime.progress import ProgressScorer
from core.agent_runtime.executor import ActionExecutor
from core.agent_runtime.policy import AgentPolicy
from core.system_context.base_system_contex import BaseSystemContext
from core.session_context.base_session_context import BaseSessionContext
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from models.execution import ExecutionStatus


@pytest.fixture
def mock_system_context():
    """Фикстура для мок-объекта системного контекста."""
    return Mock(spec=BaseSystemContext)


@pytest.fixture
def mock_session_context():
    """Фикстура для мок-объекта сессионного контекста."""
    return Mock(spec=BaseSessionContext)


@pytest.fixture
def mock_capability():
    """Фикстура для мок-объекта capability."""
    capability = Mock()
    capability.name = "test_capability"
    capability.skill_name = "test_skill"
    return capability


class TestExecutionContext:
    """Тесты для ExecutionContext."""
    
    def test_execution_context_creation(self, mock_system_context, mock_session_context):
        """Тест создания ExecutionContext."""
        state = AgentState()
        policy = AgentPolicy()
        progress = ProgressScorer()
        executor = ActionExecutor(mock_system_context)
        
        context = ExecutionContext(
            system=mock_system_context,
            session=mock_session_context,
            state=state,
            policy=policy,
            progress=progress,
            executor=executor
        )
        
        assert context.system == mock_system_context
        assert context.session == mock_session_context
        assert context.state == state
        assert context.policy == policy
        assert context.progress == progress
        assert context.executor == executor


class TestExecutionState:
    """Тесты для ExecutionState."""
    
    @pytest.mark.asyncio
    async def test_execution_state_execute(self, mock_system_context, mock_session_context):
        """Тест выполнения состояния."""
        # Создаем контекст
        state = AgentState()
        policy = AgentPolicy()
        progress = ProgressScorer()
        executor = ActionExecutor(mock_system_context)
        
        context = ExecutionContext(
            system=mock_system_context,
            session=mock_session_context,
            state=state,
            policy=policy,
            progress=progress,
            executor=executor
        )
        
        # Создаем мок-стратегию
        mock_strategy = AsyncMock()
        mock_decision = Mock()
        mock_decision.action = StrategyDecisionType.ACT
        mock_strategy.next_step.return_value = mock_decision
        
        # Устанавливаем стратегию в контекст
        context.strategy = mock_strategy
        
        # Создаем состояние выполнения
        execution_state = ExecutionState()
        
        # Выполняем состояние
        decision = await execution_state.execute(context)
        
        # Проверяем, что стратегия была вызвана
        mock_strategy.next_step.assert_called_once_with(context)
        assert decision == mock_decision
        assert not context.state.finished  # Так как действие не терминальное
    
    @pytest.mark.asyncio
    async def test_execution_state_execute_terminal(self, mock_system_context, mock_session_context):
        """Тест выполнения состояния с терминальным действием."""
        # Создаем контекст
        state = AgentState()
        policy = AgentPolicy()
        progress = ProgressScorer()
        executor = ActionExecutor(mock_system_context)
        
        context = ExecutionContext(
            system=mock_system_context,
            session=mock_session_context,
            state=state,
            policy=policy,
            progress=progress,
            executor=executor
        )
        
        # Создаем мок-стратегию с терминальным решением
        mock_strategy = AsyncMock()
        mock_decision = Mock()
        mock_decision.action = StrategyDecisionType.STOP
        mock_strategy.next_step.return_value = mock_decision
        
        # Устанавливаем стратегию в контекст
        context.strategy = mock_strategy
        
        # Создаем состояние выполнения
        execution_state = ExecutionState()
        
        # Выполняем состояние
        decision = await execution_state.execute(context)
        
        # Проверяем, что состояние завершено
        assert decision == mock_decision
        assert context.state.finished


class TestAgentRuntime:
    """Тесты для AgentRuntime."""
    
    @pytest.mark.asyncio
    async def test_agent_runtime_initialization(self, mock_system_context, mock_session_context):
        """Тест инициализации AgentRuntime."""
        runtime = AgentRuntime(
            system_context=mock_system_context,
            session_context=mock_session_context
        )
        
        assert runtime.system == mock_system_context
        assert runtime.session == mock_session_context
        assert isinstance(runtime.state, AgentState)
        assert isinstance(runtime.policy, AgentPolicy)
        assert isinstance(runtime.progress, ProgressScorer)
        assert isinstance(runtime.executor, ActionExecutor)
        assert isinstance(runtime.context, ExecutionContext)
        assert runtime.max_steps == 10
    
    @pytest.mark.asyncio
    async def test_agent_runtime_run_method(self, mock_system_context, mock_session_context):
        """Тест метода run AgentRuntime."""
        # Настройка мок-объектов
        mock_session_context.goal = None
        mock_session_context.step_context = Mock()
        mock_session_context.step_context.get_current_step_number.return_value = 0
        mock_session_context.data_context = Mock()
        mock_session_context.data_context.get_last_items.return_value = []
        mock_session_context.get_goal.return_value = "Test goal"
        mock_session_context.record_system_event = Mock()
        mock_session_context.record_decision = Mock()
        mock_session_context.record_action = Mock(return_value="action_id")
        mock_session_context.register_step = Mock()
        mock_session_context.record_error = Mock()
        mock_session_context.get_current_plan = Mock(return_value=None)
        mock_session_context.get_summary = Mock(return_value="Test summary")
        mock_session_context.last_activity = None
        mock_session_context.record_observation = Mock(return_value="obs_id")
        mock_session_context.step_context.record_step = Mock()
        mock_session_context.record_decision = Mock()

        runtime = AgentRuntime(
            system_context=mock_system_context,
            session_context=mock_session_context
        )

        # Создаем мок-стратегию, которая возвращает STOP сразу
        mock_strategy = AsyncMock()
        mock_decision = Mock()
        mock_decision.action = StrategyDecisionType.STOP
        mock_decision.reason = "Goal achieved"
        mock_strategy.next_step.return_value = mock_decision

        # Заменяем стратегию в runtime и в контексте
        runtime.strategy = mock_strategy
        runtime.context.strategy = mock_strategy

        # Запускаем выполнение
        result = await runtime.run("Test goal")

        # Проверяем, что цель установлена
        assert mock_session_context.goal == "Test goal"

        # Проверяем, что стратегия была вызвана
        mock_strategy.next_step.assert_called()

        # Проверяем, что сессия возвращается
        assert result == mock_session_context


class TestTaskScheduler:
    """Тесты для TaskScheduler."""
    
    @pytest.mark.asyncio
    async def test_simple_task_scheduler_schedule_and_complete(self):
        """Тест планировщика задач - расписание и выполнение."""
        scheduler = SimpleTaskScheduler()
        
        # Создаем задачу
        task = Task(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[]
        )
        
        # Запланировываем задачу
        task_id = await scheduler.schedule_task(task)
        assert task_id == "task1"
        
        # Проверяем, что задача в планировщике
        assert "task1" in scheduler._tasks
        
        # Отмечаем задачу как выполненную
        await scheduler.mark_task_completed("task1", result="Success")
        
        # Проверяем статус задачи
        assert scheduler._tasks["task1"].status == TaskStatus.COMPLETED
        assert scheduler._tasks["task1"].result == "Success"
    
    @pytest.mark.asyncio
    async def test_simple_task_scheduler_failure(self):
        """Тест планировщика задач - ошибка."""
        scheduler = SimpleTaskScheduler()
        
        # Создаем задачу
        task = Task(
            id="task2",
            name="Test Task 2",
            description="Another test task",
            dependencies=[]
        )
        
        # Запланировываем задачу
        await scheduler.schedule_task(task)
        
        # Отмечаем задачу как неудачную
        await scheduler.mark_task_failed("task2", error="Something went wrong")
        
        # Проверяем статус задачи
        assert scheduler._tasks["task2"].status == TaskStatus.FAILED
        assert scheduler._tasks["task2"].error == "Something went wrong"
    
    @pytest.mark.asyncio
    async def test_simple_task_scheduler_get_current_task(self):
        """Тест получения текущей задачи."""
        scheduler = SimpleTaskScheduler()
        
        # Создаем задачу
        task = Task(
            id="task3",
            name="Current Task",
            description="Task to be current",
            dependencies=[]
        )
        
        # Запланировываем задачу
        await scheduler.schedule_task(task)
        
        # Получаем текущую задачу
        current_task_id = await scheduler.get_current_task_id()
        
        assert current_task_id == "task3"


class TestCheckpointManager:
    """Тесты для CheckpointManager."""
    
    def test_checkpoint_save_and_load(self, tmp_path):
        """Тест сохранения и загрузки чекпоинта."""
        # Создаем временный каталог для чекпоинтов
        checkpoint_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(str(checkpoint_dir))
        
        # Объект для сохранения
        test_obj = {"key": "value", "number": 42}
        
        # Сохраняем чекпоинт
        checkpoint_name = manager.save_checkpoint(test_obj, "test_checkpoint")
        
        # Проверяем, что чекпоинт создан
        assert checkpoint_name == "test_checkpoint"
        
        # Загружаем чекпоинт
        loaded_obj = manager.load_checkpoint("test_checkpoint")
        
        # Проверяем, что данные совпадают
        assert loaded_obj == test_obj
    
    def test_checkpoint_list_and_delete(self, tmp_path):
        """Тест списка и удаления чекпоинтов."""
        # Создаем временный каталог для чекпоинтов
        checkpoint_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(str(checkpoint_dir))
        
        # Сохраняем несколько чекпоинтов
        manager.save_checkpoint({"data": 1}, "checkpoint1")
        manager.save_checkpoint({"data": 2}, "checkpoint2")
        
        # Получаем список чекпоинтов
        checkpoints = manager.list_checkpoints()
        
        # Проверяем, что есть два чекпоинта
        assert len(checkpoints) == 2
        assert "checkpoint1" in checkpoints
        assert "checkpoint2" in checkpoints
        
        # Удаляем один чекпоинт
        manager.delete_checkpoint("checkpoint1")
        
        # Проверяем, что остался только один
        checkpoints_after_delete = manager.list_checkpoints()
        assert len(checkpoints_after_delete) == 1
        assert "checkpoint2" in checkpoints_after_delete


# Удаляем тест для SerializableMixin, так как этот класс больше не используется
# class TestSerializableMixin:
#     """Тесты для SerializableMixin."""
#     
#     def test_serializable_mixin(self):
#         """Тест примеси сериализации."""
#         
#         # Определяем класс вне метода для возможности сериализации
#         class TestClass(SerializableMixin):
#             def __init__(self, value):
#                 self.value = value
#
#         # Создаем объект
#         obj = TestClass("test_value")
#         
#         # Сериализуем
#         serialized = obj.serialize()
#         
#         # Десериализуем
#         deserialized = TestClass.deserialize(serialized)
#         
#         # Проверяем, что значения совпадают
#         assert deserialized.value == "test_value"
#         assert isinstance(deserialized, TestClass)


class TestThinkingPatternLoader:
    """Тесты для ThinkingPatternLoader."""
    
    def test_pattern_loader_default_patterns(self):
        """Тест загрузчика паттернов мышления с паттернами по умолчанию."""
        loader = ThinkingPatternLoader()
        
        # Проверяем, что все паттерны мышления зарегистрированы
        assert "react" in loader._patterns
        assert "planning" in loader._patterns
        assert "plan_execution" in loader._patterns
        assert "code_analysis" in loader._patterns
        assert "evaluation" in loader._patterns
        assert "fallback" in loader._patterns
        
        # Проверяем, что можно получить класс паттерна мышления
        react_pattern_class = loader.get_pattern_class("react")
        assert react_pattern_class.__name__ == "ReActThinkingPattern"
    
    def test_pattern_loader_create_pattern(self):
        """Тест создания паттерна мышления."""
        loader = ThinkingPatternLoader()
        
        # Создаем паттерн мышления
        pattern = loader.create_pattern("react")
        
        # Проверяем тип паттерна мышления
        from core.agent_runtime.thinking_patterns.react.strategy import ReActThinkingPattern
        assert isinstance(pattern, ReActThinkingPattern)
    
    def test_pattern_loader_register_custom_pattern(self):
        """Тест регистрации пользовательского паттерна мышления."""
        loader = ThinkingPatternLoader()
        
        # Создаем тестовый паттерн мышления
        from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface
        
        class CustomThinkingPattern(AgentThinkingPatternInterface):
            async def next_step(self, context):
                pass
        
        # Регистрируем паттерн мышления
        loader.register_pattern("custom", CustomThinkingPattern)
        
        # Проверяем, что паттерн мышления зарегистрирован
        assert "custom" in loader._patterns
        assert loader._patterns["custom"] == CustomThinkingPattern
        
        # Проверяем, что можно создать экземпляр
        custom_pattern = loader.create_pattern("custom")
        assert isinstance(custom_pattern, CustomThinkingPattern)

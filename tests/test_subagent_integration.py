"""
Тесты для проверки интеграции субагентов с SessionContext.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from core.session_context.session_context import SessionContext
from core.session_context.model import ContextItemType, ContextItemMetadata


class TestAgent:
    """Заглушка агента для тестирования"""
    def __init__(self, name):
        self.name = name


def test_session_context_creation():
    """Тест создания SessionContext"""
    session = SessionContext()
    
    assert session.session_id is not None
    assert session.created_at is not None
    assert session.last_activity is not None
    assert session.running_subagents == {}


def test_record_subagent_start():
    """Тест записи начала работы субагента"""
    session = SessionContext()
    
    agent_id = "test_agent_1"
    agent_name = "TestAgent"
    task_description = "Test task for subagent"
    
    item_id = session.record_subagent_start(agent_id, agent_name, task_description)
    
    assert item_id is not None
    
    # Проверяем, что элемент добавлен в контекст
    item = session.get_context_item(item_id)
    assert item is not None
    assert item.item_type == ContextItemType.THOUGHT
    assert item.content["event"] == "subagent_started"
    assert item.content["agent_id"] == agent_id
    assert item.content["task"] == task_description


def test_record_subagent_result():
    """Тест записи результата работы субагента"""
    session = SessionContext()
    
    agent_id = "test_agent_2"
    agent_name = "TestAgent"
    result = {"status": "success", "data": "test result"}
    
    item_id = session.record_subagent_result(agent_id, agent_name, result)
    
    assert item_id is not None
    
    # Проверяем, что элемент добавлен в контекст
    item = session.get_context_item(item_id)
    assert item is not None
    assert item.item_type == ContextItemType.SKILL_RESULT
    assert item.content["event"] == "subagent_completed"
    assert item.content["agent_id"] == agent_id
    assert item.content["result"] == result


def test_record_subagent_error():
    """Тест записи ошибки субагента"""
    session = SessionContext()
    
    agent_id = "test_agent_3"
    agent_name = "TestAgent"
    error_info = {
        "error": "Test error occurred",
        "timestamp": datetime.now().isoformat(),
        "phase": "execution"
    }
    
    item_id = session.record_subagent_error(agent_id, agent_name, error_info)
    
    assert item_id is not None
    
    # Проверяем, что элемент добавлен в контекст
    item = session.get_context_item(item_id)
    assert item is not None
    assert item.item_type == ContextItemType.ERROR_LOG
    assert item.content["event"] == "subagent_error"
    assert item.content["agent_id"] == agent_id
    assert item.content["error"] == error_info["error"]


def test_track_subagent():
    """Тест отслеживания субагента"""
    session = SessionContext()
    
    agent_id = "test_agent_4"
    agent_instance = TestAgent("test_agent")
    task_description = "Test tracking task"
    
    session.track_subagent(agent_id, agent_instance, task_description)
    
    # Проверяем, что субагент добавлен в отслеживаемые
    tracked = session.get_subagent_status(agent_id)
    assert tracked is not None
    assert tracked['instance'] == agent_instance
    assert tracked['task'] == task_description
    assert tracked['status'] == 'running'


def test_update_subagent_status():
    """Тест обновления статуса субагента"""
    session = SessionContext()
    
    agent_id = "test_agent_5"
    agent_instance = TestAgent("test_agent")
    task_description = "Test update task"
    
    session.track_subagent(agent_id, agent_instance, task_description)
    
    # Обновляем статус
    session.update_subagent_status(agent_id, 'completed')
    
    # Проверяем, что статус обновился
    tracked = session.get_subagent_status(agent_id)
    assert tracked is not None
    assert tracked['status'] == 'completed'


def test_remove_subagent():
    """Тест удаления субагента из отслеживаемых"""
    session = SessionContext()
    
    agent_id = "test_agent_6"
    agent_instance = TestAgent("test_agent")
    task_description = "Test removal task"
    
    session.track_subagent(agent_id, agent_instance, task_description)
    
    # Удаляем субагента
    session.remove_subagent(agent_id)
    
    # Проверяем, что субагента больше нет в отслеживаемых
    tracked = session.get_subagent_status(agent_id)
    assert tracked is None


def test_get_running_subagents():
    """Тест получения всех запущенных субагентов"""
    session = SessionContext()
    
    # Добавляем несколько субагентов
    session.track_subagent("agent_1", TestAgent("agent1"), "task1")
    session.track_subagent("agent_2", TestAgent("agent2"), "task2")
    
    running_agents = session.get_running_subagents()
    
    assert len(running_agents) == 2
    assert "agent_1" in running_agents
    assert "agent_2" in running_agents
    assert running_agents["agent_1"]["task"] == "task1"
    assert running_agents["agent_2"]["task"] == "task2"


def test_should_spawn_subagents_positive():
    """Тест положительного сценария запуска субагентов"""
    session = SessionContext()
    
    # Создаем задачи, которые можно выполнить параллельно
    task_breakdown = [
        {"id": "task1", "description": "Task 1", "depends_on": []},
        {"id": "task2", "description": "Task 2", "depends_on": []},
        {"id": "task3", "description": "Task 3", "depends_on": []}
    ]
    
    should_spawn = session.should_spawn_subagents(task_breakdown)
    
    assert should_spawn is True


def test_should_spawn_subagents_negative_single_task():
    """Тест отрицательного сценария - одна задача"""
    session = SessionContext()
    
    task_breakdown = [
        {"id": "task1", "description": "Single task", "depends_on": []}
    ]
    
    should_spawn = session.should_spawn_subagents(task_breakdown)
    
    assert should_spawn is False


def test_should_spawn_subagents_negative_dependent_tasks():
    """Тест отрицательного сценария - зависимые задачи"""
    session = SessionContext()
    
    # Задачи зависят друг от друга, поэтому не подходят для параллельного выполнения
    task_breakdown = [
        {"id": "task1", "description": "Task 1", "depends_on": []},
        {"id": "task2", "description": "Task 2", "depends_on": ["task1"]},
        {"id": "task3", "description": "Task 3", "depends_on": ["task2"]}
    ]
    
    should_spawn = session.should_spawn_subagents(task_breakdown)
    
    # В текущей реализации мы проверяем только наличие depends_on, 
    # но если задачи зависимые, они не считаются независимыми
    # В данном случае только task1 независима, поэтому меньше 2 независимых задач
    assert should_spawn is False


def test_should_spawn_subagents_mixed_dependencies():
    """Тест смешанных зависимостей"""
    session = SessionContext()
    
    # Одна независимая задача и одна зависимая - недостаточно для запуска субагентов
    task_breakdown = [
        {"id": "task1", "description": "Independent task", "depends_on": []},
        {"id": "task2", "description": "Dependent task", "depends_on": ["task1"]},
        {"id": "task3", "description": "Another independent task", "depends_on": []}
    ]
    
    should_spawn = session.should_spawn_subagents(task_breakdown)
    
    # У нас есть 2 независимые задачи (task1 и task3), что >= 2, значит True
    assert should_spawn is True


if __name__ == "__main__":
    # Запуск всех тестов
    pytest.main([__file__, "-v"])
"""
Пример запуска агента.

Этот пример демонстрирует:
- Создание всех необходимых зависимостей для агента
- Настройку системного контекста
- Регистрацию навыков и инструментов
- Запуск агента с простой задачей
"""
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock

# Добавляем корневую директорию проекта в путь Python для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from domain.models.system.config import SystemConfig
from infrastructure.contexts.system.system_context import SystemContext
from application.agent.runtime import AgentRuntime
from application.agent.pattern_selector import SimplePatternSelector
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository
from infrastructure.gateways.llm.llm_execution_gateway import ExecutionGateway
from domain.abstractions.event_types import EventType, IEventPublisher
from application.context.session.base_session_context import BaseSessionContext
from domain.abstractions.base_skill import BaseSkill
from infrastructure.tools.file_tools.file_reader_tool import FileReaderTool


class MockSessionContext(BaseSessionContext):
    """Мок-класс для сессионного контекста."""
    
    def __init__(self):
        self.session_id = "test_session_123"
        self.state = {}
        
    def initialize(self):
        """Инициализировать контекст сессии."""
        self.state = {"initialized": True}
        
    def update_state(self, state_data):
        """Обновить состояние сессии."""
        self.state.update(state_data)
        
    def get_state(self):
        """Получить текущее состояние сессии."""
        return self.state


class MockEventPublisher(IEventPublisher):
    """Мок-класс для издателя событий."""
    
    def __init__(self):
        self.published_events = []
        
    async def publish(self, event_type: EventType, source: str, data: dict):
        """Публиковать событие."""
        event = {
            "type": event_type,
            "source": source,
            "data": data,
            "timestamp": None
        }
        self.published_events.append(event)
        print(f"Published event: {event_type.value} from {source} with data: {data}")
        
    def subscribe(self, event_type: EventType, handler):
        """Подписаться на событие."""
        pass


class SimpleTestSkill(BaseSkill):
    """Простой тестовый навык для демонстрации работы агента."""
    
    def __init__(self, name: str = "simple_test_skill", description: str = "Simple test skill"):
        super().__init__()
        self._name = name
        self._description = description
        self.dependencies = []  # Нет зависимостей
        
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    async def execute(self, parameters: dict, session_context=None) -> dict:
        """Выполнение навыка."""
        return {
            "success": True,
            "result": f"Skill {self.name} executed with parameters: {parameters}",
            "metadata": {"skill_type": "simple_test"}
        }


async def demonstrate_agent_runtime():
    """Демонстрация работы агента."""
    print("=== Демонстрация работы агента ===\n")
    
    # Создаем системный контекст
    config = SystemConfig()
    system_context = SystemContext(config=config)
    print("✓ Системный контекст создан")
    
    # Создаем и регистрируем инструмент
    file_reader = FileReaderTool()
    await file_reader.initialize()
    system_context.register_tool(file_reader)
    print(f"✓ Инструмент '{file_reader.name}' зарегистрирован")
    
    # Создаем и регистрируем навык
    test_skill = SimpleTestSkill()
    system_context.register_skill(test_skill)
    print(f"✓ Навык '{test_skill.name}' зарегистрирован")
    
    # Создаем сессионный контекст
    session_context = MockSessionContext()
    session_context.initialize()
    print("✓ Сессионный контекст создан и инициализирован")
    
    # Создаем издателя событий
    event_publisher = MockEventPublisher()
    print("✓ Издатель событий создан")
    
    # Создаем репозиторий промтов
    prompt_repository = InMemoryPromptRepository()
    print("✓ Репозиторий промтов создан")
    
    # Создаем селектор паттернов
    from application.thinking_patterns.composable.composable_pattern import ReActPattern
    react_pattern = ReActPattern()
    patterns = {"react": react_pattern}
    pattern_selector = SimplePatternSelector(patterns)
    print("✓ Селектор паттернов создан")
    
    # Создаем шлюз выполнения
    execution_gateway = ExecutionGateway(
        skill_registry=system_context.get_skill_registry(),
        event_publisher=event_publisher
    )
    print("✓ Шлюз выполнения создан")
    
    # Создаем агента
    agent = AgentRuntime(
        session_context=session_context,
        pattern_selector=pattern_selector,
        prompt_repository=prompt_repository,
        execution_gateway=execution_gateway,
        skill_registry=system_context.get_skill_registry(),
        event_publisher=event_publisher,
        max_steps=10
    )
    print("✓ Агент создан")
    
    # Инициализируем агента
    initialized = await agent.initialize()
    print(f"✓ Агент инициализирован: {'Да' if initialized else 'Нет'}")
    
    # Выполняем простую задачу
    print("\n--- Выполнение задачи ---")
    task_result = await agent.execute_task("Расскажи о себе и своих возможностях")
    print(f"Результат выполнения задачи: {task_result}")
    
    # Выводим опубликованные события
    print(f"\n--- Опубликованные события ({len(event_publisher.published_events)}) ---")
    for i, event in enumerate(event_publisher.published_events):
        print(f"{i+1}. {event['type'].value} - {event['source']}: {event['data']}")
    
    print("\n=== Демонстрация завершена ===")


if __name__ == "__main__":
    asyncio.run(demonstrate_agent_runtime())
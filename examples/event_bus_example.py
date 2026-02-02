"""
Пример использования шины событий (Event Bus) в системе.

Этот пример демонстрирует:
- Создание системного контекста с шиной событий
- Публикацию различных типов событий
- Подписку на события
- Вывод событий в консоль и запись в логи
"""
import asyncio
import sys
import os

# Добавляем корневую директорию в путь Python для импорта модулей
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.system_context import SystemContext, EventType
from config.models import SystemConfig
from core.system_context.event_bus import Event


async def demonstrate_event_bus():
    """
    Демонстрация работы шины событий.
    """
    print("=== Демонстрация шины событий ===\n")
    
    # Создаем конфигурацию системы
    config = SystemConfig()
    config.log_dir = "logs"
    
    # Создаем системный контекст (он автоматически инициализирует шину событий)
    system_context = SystemContext(config=config)
    
    print("Системный контекст создан с шиной событий\n")
    
    # Публикуем различные типы событий
    print("Публикация событий...\n")
    
    # Событие выполнения задачи
    await system_context.event_system.publish_simple(
        event_type=EventType.TASK_EXECUTION,
        source="TaskExecutor",
        data={
            "task_id": "task_001",
            "action": "start_processing",
            "description": "Начало обработки задачи"
        }
    )
    
    # Событие прогресса
    await system_context.event_system.publish_simple(
        event_type=EventType.PROGRESS,
        source="ProgressTracker",
        data={
            "task_id": "task_001",
            "progress": 50,
            "total_steps": 10,
            "completed_steps": 5,
            "message": "Задача выполнена наполовину"
        }
    )
    
    # Событие ошибки
    await system_context.event_system.publish_simple(
        event_type=EventType.ERROR,
        source="ErrorHandler",
        data={
            "error_code": "E001",
            "message": "Произошла ошибка при обработке данных",
            "traceback": "Traceback details..."
        }
    )
    
    # Событие взаимодействия с пользователем
    await system_context.event_system.publish_simple(
        event_type=EventType.USER_INTERACTION,
        source="UserInterface",
        data={
            "user_input": "Запрос пользователя",
            "response": "Ответ системы",
            "interaction_type": "query"
        }
    )
    
    # Системное событие
    await system_context.event_system.publish_simple(
        event_type=EventType.SYSTEM,
        source="SystemMonitor",
        data={
            "status": "healthy",
            "memory_usage": "45%",
            "cpu_usage": "23%"
        }
    )
    
    # Отладочное событие
    await system_context.event_system.publish_simple(
        event_type=EventType.DEBUG,
        source="Debugger",
        data={
            "variable_name": "x",
            "value": 42,
            "context": "calculation_step_3"
        }
    )
    
    print("\nСобытия опубликованы!")
    print("Проверьте файлы логов в директории 'logs' и консольный вывод.")


if __name__ == "__main__":
    asyncio.run(demonstrate_event_bus())
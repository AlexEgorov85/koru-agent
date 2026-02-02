"""
Пример использования обработчика красивого отображения шагов агента.

Этот пример демонстрирует:
- Создание системного контекста с шиной событий
- Добавление обработчика AgentStepDisplayHandler
- Публикацию различных типов событий
- Красивое отображение промежуточных шагов агента
"""
import asyncio
import sys
import os

# Добавляем корневую директорию в путь Python для импорта модулей
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.system_context import SystemContext, EventType, AgentStepDisplayHandler
from config.models import SystemConfig
from core.system_context.event_bus import Event


async def demonstrate_agent_step_display():
    """
    Демонстрация работы обработчика красивого отображения шагов агента.
    """
    print("=== Демонстрация обработчика красивого отображения шагов агента ===\n")
    
    # Создаем конфигурацию системы
    config = SystemConfig()
    config.log_dir = "logs"
    
    # Создаем системный контекст (он автоматически инициализирует шину событий)
    system_context = SystemContext(config=config)
    
    print("Системный контекст создан с шиной событий\n")
    
    # Создаем и регистрируем обработчик красивого отображения шагов агента
    agent_step_handler = AgentStepDisplayHandler(
        show_task_execution=True,
        show_progress=True,
        show_user_interaction=True,
        use_colors=False  # Отключаем цвета для избежания проблем с кодировкой в Windows
    )
    system_context.event_system.subscribe_global(agent_step_handler)
    
    print("Обработчик красивого отображения шагов агента зарегистрирован\n")
    
    # Публикуем различные типы событий
    print("Публикация событий...\n")
    
    # Событие выполнения задачи
    await system_context.event_system.publish_simple(
        event_type=EventType.TASK_EXECUTION,
        source="TaskExecutor",
        data={
            "task_id": "TASK_001",
            "action": "analyze_code",
            "description": "Анализ исходного кода для поиска потенциальных проблем"
        }
    )
    
    # Событие прогресса
    await system_context.event_system.publish_simple(
        event_type=EventType.PROGRESS,
        source="ProgressTracker",
        data={
            "task_id": "TASK_001",
            "progress": 25,
            "total_steps": 10,
            "completed_steps": 3,
            "message": "Обработка файлов завершена"
        }
    )
    
    # Еще одно событие прогресса
    await system_context.event_system.publish_simple(
        event_type=EventType.PROGRESS,
        source="ProgressTracker",
        data={
            "task_id": "TASK_001",
            "progress": 50,
            "total_steps": 10,
            "completed_steps": 5,
            "message": "Анализ логики завершен"
        }
    )
    
    # Событие взаимодействия с пользователем
    await system_context.event_system.publish_simple(
        event_type=EventType.USER_INTERACTION,
        source="UserInterface",
        data={
            "user_input": "Пожалуйста, объясни, что делает эта функция?",
            "response": "Функция process_data обрабатывает входные данные и возвращает результат после применения набора преобразований.",
            "interaction_type": "question_answer"
        }
    )
    
    # Еще одно событие выполнения задачи
    await system_context.event_system.publish_simple(
        event_type=EventType.TASK_EXECUTION,
        source="TaskExecutor",
        data={
            "task_id": "TASK_002",
            "action": "generate_report",
            "description": "Генерация отчета на основе анализа кода"
        }
    )
    
    # Финальное событие прогресса
    await system_context.event_system.publish_simple(
        event_type=EventType.PROGRESS,
        source="ProgressTracker",
        data={
            "task_id": "TASK_001",
            "progress": 100,
            "total_steps": 10,
            "completed_steps": 10,
            "message": "Задача выполнена успешно!"
        }
    )
    
    print("\nСобытия опубликованы!")
    print("Проверьте красивое отображение шагов агента выше.")


if __name__ == "__main__":
    asyncio.run(demonstrate_agent_step_display())
"""
Комплексный тест сценария использования субагентов.
"""
import asyncio
import sys
import os
from datetime import datetime

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.session_context.session_context import SessionContext


def test_subagent_scenario():
    """
    Тест комплексного сценария использования субагентов:
    1. Основной агент получает задачу, которую можно разбить на подзадачи
    2. Определяется, что нужно запустить субагентов
    3. Создаются субагенты для выполнения независимых подзадач
    4. Состояние субагентов отслеживается
    5. Результаты интегрируются обратно в основной контекст
    """
    print("=== Тест комплексного сценария использования субагентов ===")
    
    # 1. Создаем основной контекст
    session = SessionContext()
    session.set_goal("Анализировать проект и подготовить отчет")
    
    print(f"Создана сессия: {session.session_id}")
    print(f"Цель: {session.get_goal()}")
    
    # 2. Имитируем разбиение задачи на подзадачи
    task_breakdown = [
        {"id": "code_analysis", "description": "Анализ исходного кода", "depends_on": [], "type": "code_analysis"},
        {"id": "doc_review", "description": "Проверка документации", "depends_on": [], "type": "research"},
        {"id": "test_check", "description": "Проверка тестов", "depends_on": [], "type": "code_analysis"},
        {"id": "dependency_check", "description": "Проверка зависимостей", "depends_on": [], "type": "research"}
    ]
    
    print(f"\nРазбиение задачи на подзадачи: {len(task_breakdown)} подзадач")
    
    # 3. Проверяем, нужно ли запускать субагентов
    should_spawn = session.should_spawn_subagents(task_breakdown)
    print(f"Необходимость запуска субагентов: {should_spawn}")
    
    assert should_spawn is True, "Должны запустить субагентов, так как есть 4 независимые подзадачи"
    
    # 4. Запускаем субагентов для выполнения подзадач
    subagent_tasks = []
    for i, task in enumerate(task_breakdown):
        agent_id = f"subagent_{i+1}"
        agent_name = f"SubAgent_{task['type']}"
        
        # Отслеживаем субагента
        session.track_subagent(agent_id, f"MockAgent_{task['type']}", task['description'])
        print(f"Запущен субагент {agent_id} для задачи: {task['description']}")
        
        # Регистрируем начало работы субагента
        session.record_subagent_start(agent_id, agent_name, task['description'])
        
        subagent_tasks.append({
            'id': agent_id,
            'name': agent_name,
            'task': task
        })
    
    # 5. Проверяем статусы субагентов
    running_agents = session.get_running_subagents()
    print(f"\nКоличество запущенных субагентов: {len(running_agents)}")
    
    for agent_id, info in running_agents.items():
        print(f"  - {agent_id}: {info['task']} (статус: {info['status']})")
    
    # 6. Имитируем выполнение задач субагентами
    results = []
    for task_info in subagent_tasks:
        agent_id = task_info['id']
        agent_name = task_info['name']
        task = task_info['task']
        
        # Имитируем результат выполнения задачи
        result = {
            "task_completed": task['description'],
            "result_data": f"Результат выполнения задачи {task['id']}",
            "metrics": {"time_spent": 2.5, "elements_processed": 10}
        }
        
        # Обновляем статус субагента
        session.update_subagent_status(agent_id, 'completed')
        
        # Регистрируем результат в основном контексте
        session.record_subagent_result(agent_id, agent_name, result)
        print(f"Субагент {agent_id} завершил задачу: {task['description']}")
        
        results.append(result)
    
    # 7. Проверяем, что результаты записаны в контекст
    print(f"\nКоличество результатов, записанных в контекст: {len(results)}")
    
    # Подсчитываем элементы контекста, связанные с субагентами
    all_items = session.data_context.get_all_items()
    subagent_related_items = [item for item in all_items 
                              if 'subagent' in (item.content.get('event', '') if isinstance(item.content, dict) else str(item.content))]
    
    print(f"Количество элементов контекста, связанных с субагентами: {len(subagent_related_items)}")
    
    # 8. Проверяем, что все субагенты завершены
    for agent_id in [t['id'] for t in subagent_tasks]:
        status = session.get_subagent_status(agent_id)
        if status:
            print(f"Статус субагента {agent_id}: {status['status']}")
            assert status['status'] == 'completed', f"Субагент {agent_id} должен быть завершен"
    
    # 9. Удаляем завершенных субагентов из отслеживания
    for agent_id in [t['id'] for t in subagent_tasks]:
        session.remove_subagent(agent_id)
        print(f"Субагент {agent_id} удален из отслеживания")
    
    # Проверяем, что больше нет активных субагентов
    final_running = session.get_running_subagents()
    print(f"Количество активных субагентов после очистки: {len(final_running)}")
    
    assert len(final_running) == 0, "Не должно остаться активных субагентов"
    
    print("\nOK Комплексный тест сценария использования субагентов пройден успешно!")


def test_error_handling_scenario():
    """
    Тест сценария обработки ошибок субагентов.
    """
    print("\n=== Тест сценария обработки ошибок субагентов ===")
    
    session = SessionContext()
    session.set_goal("Тест обработки ошибок")
    
    # Создаем субагента
    agent_id = "error_subagent"
    agent_name = "ErrorSubAgent"
    task_desc = "Задача, которая завершится ошибкой"
    
    session.track_subagent(agent_id, "MockAgent_Error", task_desc)
    session.record_subagent_start(agent_id, agent_name, task_desc)
    
    print(f"Запущен субагент {agent_id} для задачи: {task_desc}")
    
    # Имитируем ошибку
    error_info = {
        "error": "Connection timeout occurred",
        "timestamp": datetime.now().isoformat(),
        "phase": "execution",
        "details": "Failed to connect to external service"
    }
    
    # Обновляем статус на ошибочный
    session.update_subagent_status(agent_id, 'failed')
    
    # Регистрируем ошибку в основном контексте
    session.record_subagent_error(agent_id, agent_name, error_info)
    
    print(f"Субагент {agent_id} завершился с ошибкой: {error_info['error']}")
    
    # Проверяем, что ошибка записана в контекст
    all_items = session.data_context.get_all_items()
    error_items = [item for item in all_items 
                   if isinstance(item.content, dict) and item.content.get('event') == 'subagent_error']
    
    assert len(error_items) == 1, "Должна быть зарегистрирована одна ошибка субагента"
    assert error_items[0].content['error'] == error_info['error'], "Ошибка должна совпадать с зарегистрированной"
    
    print("✓ Тест сценария обработки ошибок пройден успешно!")


if __name__ == "__main__":
    test_subagent_scenario()
    test_error_handling_scenario()
    print("\n✓ Все тесты сценариев использования субагентов пройдены!")
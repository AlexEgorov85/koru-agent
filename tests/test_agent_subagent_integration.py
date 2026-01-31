"""
Тесты для проверки интеграции субагентов с агентом.
"""
import asyncio
from unittest.mock import Mock
from core.session_context.session_context import SessionContext


def test_agent_subagent_workflow():
    """
    Тест полного рабочего процесса взаимодействия агента и субагентов:
    1. Агент анализирует задачу
    2. Принимает решение о запуске субагентов
    3. Создает и управляет субагентами
    4. Интегрирует результаты
    """
    print("=== Тест рабочего процесса агента и субагентов ===")
    
    # 1. Создаем основной контекст
    session = SessionContext()
    session.set_goal("Выполнить комплексный анализ проекта")
    
    # 2. Имитируем анализ задачи агентом
    print("Агент анализирует задачу...")
    
    # Задача, которую можно разбить на подзадачи
    main_task = {
        "id": "full_analysis",
        "description": "Комплексный анализ проекта",
        "subtasks": [
            {"id": "code_review", "description": "Анализ исходного кода", "type": "code_analysis", "depends_on": []},
            {"id": "doc_check", "description": "Проверка документации", "type": "research", "depends_on": []},
            {"id": "security_audit", "description": "Аудит безопасности", "type": "code_analysis", "depends_on": []},
            {"id": "performance_test", "description": "Тестирование производительности", "type": "research", "depends_on": []}
        ]
    }
    
    print(f"Задача '{main_task['description']}' может быть разбита на {len(main_task['subtasks'])} подзадач")
    
    # 3. Проверяем, стоит ли запускать субагентов
    should_spawn = session.should_spawn_subagents(main_task['subtasks'])
    print(f"Агент решает запустить субагентов: {should_spawn}")
    
    assert should_spawn is True, "Агент должен запустить субагентов для независимых подзадач"
    
    # 4. Агент создает субагентов для выполнения подзадач
    print("Агент создает субагентов для выполнения подзадач...")
    
    subagent_results = []
    for i, subtask in enumerate(main_task['subtasks']):
        subagent_id = f"subagent_{i+1}"
        subagent_name = f"Specialist_{subtask['type']}"
        
        print(f"  - Создан субагент {subagent_id} для задачи '{subtask['description']}'")
        
        # Отслеживаем субагента в контексте
        session.track_subagent(subagent_id, f"AgentInstance_{subtask['type']}", subtask['description'])
        
        # Регистрируем начало работы субагента
        session.record_subagent_start(subagent_id, subagent_name, subtask['description'])
        
        # Имитируем выполнение задачи субагентом
        print(f"    Субагент {subagent_id} выполняет задачу...")
        
        # Имитируем результат выполнения
        result = {
            "task_id": subtask['id'],
            "task_description": subtask['description'],
            "result": f"Результат анализа от субагента {subagent_id}",
            "findings": [f"Находка {j+1} от субагента {subagent_id}" for j in range(2)],
            "recommendations": [f"Рекомендация {j+1}" for j in range(2)],
            "confidence": 0.85 + (i * 0.05)  # Разная уверенность для разных субагентов
        }
        
        # Обновляем статус субагента
        session.update_subagent_status(subagent_id, 'completed')
        
        # Регистрируем результат в основном контексте
        session.record_subagent_result(subagent_id, subagent_name, result)
        
        subagent_results.append(result)
        
        print(f"    Субагент {subagent_id} завершил задачу с результатом")
    
    # 5. Проверяем, что все результаты записаны в контекст
    print(f"Агент получил {len(subagent_results)} результатов от субагентов")
    
    # Подсчитываем элементы контекста, связанные с субагентами
    all_items = session.data_context.get_all_items()
    subagent_start_items = [item for item in all_items if 'subagent_started' in str(item.content)]
    subagent_result_items = [item for item in all_items if 'subagent_completed' in str(item.content)]
    
    print(f"  - Записей начала работы субагентов: {len(subagent_start_items)}")
    print(f"  - Записей результатов субагентов: {len(subagent_result_items)}")
    
    assert len(subagent_start_items) == len(main_task['subtasks']), "Должны быть записи начала для всех субагентов"
    assert len(subagent_result_items) == len(main_task['subtasks']), "Должны быть записи результатов для всех субагентов"
    
    # 6. Агент анализирует результаты от субагентов и формирует итоговый вывод
    print("Агент анализирует результаты от субагентов...")
    
    aggregated_findings = []
    aggregated_recommendations = []
    
    for result in subagent_results:
        aggregated_findings.extend(result['findings'])
        aggregated_recommendations.extend(result['recommendations'])
    
    print(f"  - Обобщено находок: {len(aggregated_findings)}")
    print(f"  - Обобщено рекомендаций: {len(aggregated_recommendations)}")
    
    # 7. Агент завершает работу субагентов
    print("Агент завершает работу субагентов...")
    
    for i, subtask in enumerate(main_task['subtasks']):
        subagent_id = f"subagent_{i+1}"
        session.remove_subagent(subagent_id)
        print(f"  - Субагент {subagent_id} удален из отслеживания")
    
    # Проверяем, что больше нет активных субагентов
    active_subagents = session.get_running_subagents()
    print(f"Активных субагентов после завершения: {len(active_subagents)}")
    
    assert len(active_subagents) == 0, "Не должно быть активных субагентов после завершения"
    
    # 8. Формируем итоговый результат
    final_report = {
        "main_task": main_task['description'],
        "subtasks_completed": len(subagent_results),
        "total_findings": len(aggregated_findings),
        "total_recommendations": len(aggregated_recommendations),
        "subagent_results_summary": [r['task_description'] for r in subagent_results],
        "overall_confidence": sum(r['confidence'] for r in subagent_results) / len(subagent_results)
    }
    
    print(f"\nИтоговый отчет агента:")
    print(f"  - Основная задача: {final_report['main_task']}")
    print(f"  - Выполнено подзадач: {final_report['subtasks_completed']}")
    print(f"  - Всего находок: {final_report['total_findings']}")
    print(f"  - Всего рекомендаций: {final_report['total_recommendations']}")
    print(f"  - Уровень уверенности: {final_report['overall_confidence']:.2f}")
    
    print("\n✓ Тест рабочего процесса агента и субагентов пройден успешно!")


def test_agent_decision_making():
    """
    Тест принятия решения агентом о запуске субагентов.
    """
    print("\n=== Тест принятия решения агентом ===")
    
    session = SessionContext()
    
    # Сценарий 1: Много независимых задач - должны запускать субагентов
    print("Сценарий 1: Много независимых задач")
    tasks_independent = [
        {"id": "task1", "description": "Task 1", "depends_on": []},
        {"id": "task2", "description": "Task 2", "depends_on": []},
        {"id": "task3", "description": "Task 3", "depends_on": []},
        {"id": "task4", "description": "Task 4", "depends_on": []}
    ]
    
    should_spawn = session.should_spawn_subagents(tasks_independent)
    print(f"  Нужно запустить субагентов: {should_spawn} (ожидаем: True)")
    assert should_spawn is True, "Должны запустить субагентов для независимых задач"
    
    # Сценарий 2: Одна задача - не нужно запускать субагентов
    print("Сценарий 2: Одна задача")
    tasks_single = [
        {"id": "task1", "description": "Single task", "depends_on": []}
    ]
    
    should_spawn = session.should_spawn_subagents(tasks_single)
    print(f"  Нужно запустить субагентов: {should_spawn} (ожидаем: False)")
    assert should_spawn is False, "Не должны запускать субагентов для одной задачи"
    
    # Сценарий 3: Зависимые задачи - не нужно запускать субагентов (в текущей реализации)
    print("Сценарий 3: Зависимые задачи")
    tasks_dependent = [
        {"id": "task1", "description": "Task 1", "depends_on": []},
        {"id": "task2", "description": "Task 2", "depends_on": ["task1"]},
        {"id": "task3", "description": "Task 3", "depends_on": ["task2"]}
    ]
    
    should_spawn = session.should_spawn_subagents(tasks_dependent)
    print(f"  Нужно запустить субагентов: {should_spawn} (ожидаем: False)")
    # В текущей реализации мы проверяем только количество независимых задач
    # Если задачи зависимые, только первая считается независимой
    assert should_spawn is False, "Не должны запустить субагентов для зависимых задач"
    
    # Сценарий 4: Смешанные задачи - часть зависима, часть нет
    print("Сценарий 4: Смешанные задачи")
    tasks_mixed = [
        {"id": "task1", "description": "Independent task 1", "depends_on": []},
        {"id": "task2", "description": "Independent task 2", "depends_on": []},
        {"id": "task3", "description": "Dependent task", "depends_on": ["task1"]},
        {"id": "task4", "description": "Independent task 3", "depends_on": []}
    ]
    
    should_spawn = session.should_spawn_subagents(tasks_mixed)
    print(f"  Нужно запустить субагентов: {should_spawn} (ожидаем: True)")
    # У нас 3 независимых задачи (task1, task2, task4), что >= 2, значит True
    assert should_spawn is True, "Должны запустить субагентов для смешанных задач с >=2 независимыми"
    
    print("✓ Тест принятия решения агентом пройден успешно!")


if __name__ == "__main__":
    test_agent_subagent_workflow()
    test_agent_decision_making()
    print("\n✓ Все тесты интеграции агента и субагентов пройдены!")
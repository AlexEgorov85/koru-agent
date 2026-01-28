import asyncio
from core.config import get_config
from core.system_context.system_context import SystemContext
from core.session_context.session_context import SessionContext
from core.skills.project_map.schema import AnalyzeProjectInput
from models.execution import ExecutionStatus

async def analyze_project_example():
    """Пример полного анализа проекта."""
    
    # 1. Загрузка конфигурации
    config = get_config(profile='dev')
    
    # 2. Создание системного контекста
    system_context = SystemContext(config)
    
    # 3. Инициализация системного контекста
    success = await system_context.initialize()
    if not success:
        print("Ошибка инициализации системы")
        return
    
    # 4. Создание сессии
    session = SessionContext()
    session.set_goal("Проанализировать структуру проекта")
    
    # 5. Получение навыка и capability
    project_map_skill = system_context.get_resource("project_map")
    if not project_map_skill:
        print("Навык ProjectMapSkill не найден")
        return
    
    analyze_capability = system_context.get_capability("project_map.analyze_project")
    if not analyze_capability:
        print("Capability project_map.analyze_project не найдена")
        return
    
    # 6. Подготовка параметров
    parameters = AnalyzeProjectInput(
        root_dir = ".",
        max_items = 10000,
        include_tests = False,
        file_extensions = ["py"],
        include_code_units = True
    )
    
    # 7. Выполнение анализа
    print("Начало анализа проекта...")
    result = await project_map_skill.execute(analyze_capability, parameters, session)
    
    # 8. Обработка результата
    if result.status == ExecutionStatus.SUCCESS:
        project_data = result.result
        structure = project_data["project_structure"]
        
        print(f"\n===== Результаты анализа проекта =====")
        print(f"Всего файлов: {project_data['file_count']}")
        print(f"Всего единиц кода: {project_data['code_unit_count']}")
        print(f"Типы файлов: {structure.get('file_types', {})}")
        print(f"Точек входа: {structure.get('entry_points_count', 0)}")
        print(f"Зависимостей: {structure.get('dependencies_count', 0)}")
        
        # Вывод топ-10 точек входа
        print(f"\n===== Точки входа =====")
        for i, ep in enumerate(structure.get('top_entry_points', [])[:10], 1):
            print(f"{i}. {ep['name']} ({ep['entry_type']}) в {ep['file_path']}:{ep['line']}")
        
        # Сохранение результата в файл
        import json
        with open("project_structure.json", "w", encoding="utf-8") as f:
            json.dump(structure, f, indent=2, ensure_ascii=False)
        print(f"\nСтруктура проекта сохранена в project_structure.json")
        
    else:
        print(f"Ошибка анализа проекта: {result.error}")
        print(f"Детали: {result.summary}")

# Запуск примера
if __name__ == "__main__":
    asyncio.run(analyze_project_example())
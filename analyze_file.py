import asyncio
from core.config import get_config
from core.system_context.system_context import SystemContext
from core.session_context.session_context import SessionContext
from models.execution import ExecutionStatus

async def analyze_file_example():
    """Пример анализа конкретного файла."""
    
    # 1. Загрузка конфигурации и инициализация
    config = get_config(profile='dev')
    system_context = SystemContext(config)
    await system_context.initialize()
    
    # 2. Создание сессии
    session = SessionContext()
    
    # 3. Получение навыка
    project_map_skill = system_context.get_resource("ProjectMapSkill")
    if not project_map_skill:
        print("Навык ProjectMapSkill не найден")
        return
    
    # 4. Анализ файла с кодом навыка
    file_path = "core/skills/project_map/skill.py"
    
    capability = system_context.get_capability("project_map.get_file_code_units")
    parameters = {
        "file_path": file_path,
        "include_source_code": False  # Не включать исходный код для краткости
    }
    
    print(f"Анализ файла: {file_path}")
    result = await project_map_skill.execute(capability, parameters, session)
    
    if result.status == ExecutionStatus.SUCCESS:
        data = result.result
        print(f"\n===== Анализ файла {data['file_path']} =====")
        print(f"Найдено единиц кода: {data['unit_count']}")
        
        # Группировка по типам
        type_counts = {}
        for unit in data["code_units"]:
            unit_type = unit["type"]
            type_counts[unit_type] = type_counts.get(unit_type, 0) + 1
        
        print(f"\n===== Распределение по типам =====")
        for unit_type, count in type_counts.items():
            print(f"{unit_type}: {count}")
        
        # Вывод информации о классах и функциях
        print(f"\n===== Классы и функции =====")
        for unit in data["code_units"]:
            if unit["type"] in ["class", "function", "method"]:
                print(f"- {unit['type']} '{unit['name']}' at line {unit['location']['start_line']}")
                if unit.get("documentation"):
                    doc = unit["documentation"].split('\n')[0][:60] + "..."
                    print(f"  Doc: {doc}")
                if unit.get("signature"):
                    print(f"  Signature: {unit['signature']}")
        
        # Сохранение в файл
        import json
        output_file = f"{file_path.replace('/', '_').replace('.py', '')}_analysis.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data["code_units"], f, indent=2, ensure_ascii=False)
        print(f"\nРезультат анализа сохранен в {output_file}")
        
    else:
        print(f"Ошибка анализа файла: {result.error}")

if __name__ == "__main__":
    asyncio.run(analyze_file_example())
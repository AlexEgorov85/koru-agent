# Импорт из core
import asyncio

from core.config import get_config
from core.system_context.system_context import SystemContext
from core.session_context.session_context import SessionContext

async def main():
    """Основная асинхронная функция приложения"""
    # 1. Загрузка конфигурации
    config = get_config(profile='dev')

    # 2. Создание системного контекста
    system_context = SystemContext(config)

    # 3. Инициализация системного контекста
    success = await system_context.initialize()



    from core.infrastructure.tools.file_lister_tool import FileListerInput
    tool = system_context.get_resource("FileListerTool")
    result = await tool.execute(FileListerInput(
            path= ".",  # текущая директория
            recursive= True,
            max_items= 200,
            include_files= True,
            include_directories= True
    ))

    # 2. Создание и запуск агента
    # goal = "Какие книги написал Пушкин?"
    # agent = await system_context.create_agent()
            
    # 3. Выполнение агента
    # result = await agent.run(goal)
    # print("Результат:", result)


    #session = SessionContext()
    #session.set_goal("Какие книги написал Пушкин?")

    # Запуск конкретного навыка
    #skill_result = await system_context.run_skill(
    #    skill_name="PlanningSkill",
    #    capability_name="planning.create_plan",
    #    parameters={},
    #    session_context=session)
    #print(skill_result)

if __name__ == "__main__":
    # Запуск асинхронной функции
    asyncio.run(main())


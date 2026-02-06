"""
Пример использования компонуемых паттернов мышления в агенте.
"""
import asyncio
from application.orchestration.system_orchestrator import SystemOrchestrator


async def main():
    """Пример использования компонуемых паттернов мышления."""
    # Создаем оркестратор системы
    orchestrator = SystemOrchestrator()
    await orchestrator.initialize()
    
    # Создаем агента с компонуемым паттерном мышления
    agent = await orchestrator.create_agent(
        session_id="example_session",
        thinking_pattern_name="react",  # Используем компонуемый ReAct паттерн
        max_steps=5
    )
    
    # Запускаем выполнение задачи
    result = await agent.run("Расскажи о себе и своих возможностях")
    
    print(f"Результат выполнения: {result}")
    
    # Завершаем работу агента
    await agent.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

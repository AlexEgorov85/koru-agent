"""
Пример использования системного контекста.

Этот пример демонстрирует:
- Создание системного контекста
- Регистрацию инструментов и навыков
- Работу с конфигурацией
- Валидацию системы
"""
import asyncio
from domain.models.system.config import SystemConfig
from infrastructure.contexts.system.system_context import SystemContext
from infrastructure.tools.file_tools.file_reader_tool import FileReaderTool
from domain.abstractions.base_skill import BaseSkill


class SimpleSkill(BaseSkill):
    """Простой пример навыка для демонстрации регистрации."""
    
    def __init__(self, name: str = "simple_skill", description: str = "Simple skill for demonstration"):
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
    
    async def execute(self, parameters: dict) -> dict:
        """Выполнение навыка."""
        return {
            "success": True,
            "result": f"Skill {self.name} executed with parameters: {parameters}",
            "metadata": {"skill_type": "simple_demo"}
        }


async def demonstrate_system_context():
    """Демонстрация работы системного контекста."""
    print("=== Демонстрация системного контекста ===\n")
    
    # Создаем конфигурацию системы
    config = SystemConfig()
    config.log_level = "INFO"
    config.log_dir = "logs"
    
    # Создаем системный контекст
    system_context = SystemContext(config=config)
    print("✓ Системный контекст создан")
    
    # Регистрируем инструмент
    file_reader = FileReaderTool()
    await file_reader.initialize()
    system_context.register_tool(file_reader)
    print(f"✓ Инструмент '{file_reader.name}' зарегистрирован")
    
    # Регистрируем навык
    simple_skill = SimpleSkill()
    system_context.register_skill(simple_skill)
    print(f"✓ Навык '{simple_skill.name}' зарегистрирован")
    
    # Работа с конфигурацией
    system_context.set_config("max_workers", 4)
    system_context.set_config("timeout", 30)
    max_workers = system_context.get_config("max_workers", 1)
    print(f"✓ Конфигурация: max_workers = {max_workers}")
    
    # Получаем все инструменты
    all_tools = system_context.get_all_tools()
    print(f"✓ Зарегистрировано инструментов: {len(all_tools)}")
    
    # Получаем все навыки
    all_skills = system_context.get_all_skills()
    print(f"✓ Зарегистрировано навыков: {len(all_skills)}")
    
    # Валидация системы
    is_valid = system_context.validate()
    print(f"✓ Валидация системы: {'Успешна' if is_valid else 'Неудачна'}")
    
    # Демонстрация получения ресурсов
    retrieved_tool = system_context.get_resource(file_reader.name)
    if retrieved_tool:
        print(f"✓ Инструмент получен по имени: {retrieved_tool.name}")
    
    retrieved_skill = system_context.get_resource(simple_skill.name)
    if retrieved_skill:
        print(f"✓ Навык получен по имени: {retrieved_skill.name}")
    
    # Экспорт конфигурации
    exported_config = system_context.export_config()
    print(f"✓ Экспортированная конфигурация: {exported_config}")
    
    print("\n=== Демонстрация завершена ===")


if __name__ == "__main__":
    asyncio.run(demonstrate_system_context())
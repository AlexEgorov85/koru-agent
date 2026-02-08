"""
Скрипт для реального запуска системного контекста.

Этот скрипт демонстрирует:
- Загрузку конфигурации системы
- Создание системного контекста с реальными компонентами
- Регистрацию инструментов и навыков
- Инициализацию и проверку работоспособности
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.config_loader import ConfigLoader
from infrastructure.contexts.system.system_context import SystemContext
from infrastructure.tools.file_tools.file_reader_tool import FileReaderTool
from infrastructure.tools.file_tools.file_writer_tool import FileWriterTool
from domain.abstractions.base_skill import BaseSkill


class DemoSkill(BaseSkill):
    """Демонстрационный навык для тестирования системного контекста."""
    
    def __init__(self, name: str = "demo_skill", description: str = "Demo skill for system context testing"):
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
            "result": f"Demo skill executed with parameters: {parameters}",
            "metadata": {"skill_type": "demo", "execution_time": "immediate"}
        }


async def setup_and_test_system_context():
    """Настройка и тестирование системного контекста."""
    print("=== Настройка и тестирование системного контекста ===\n")
    
    # Загружаем конфигурацию
    print("1. Загрузка конфигурации системы...")
    config_loader = ConfigLoader(profile="dev")
    config = config_loader.load()
    print(f"   + Загружена конфигурация профиля: {config.profile}")
    print(f"   + Уровень логирования: {config.log_level}")
    print(f"   + Директория логов: {config.log_dir}")
    
    # Создаем системный контекст
    print("\n2. Создание системного контекста...")
    system_context = SystemContext(config=config)
    print("   + Системный контекст создан")
    
    # Работа с конфигурацией (до инициализации, чтобы не нарушить валидацию)
    print("\n3. Работа с конфигурацией...")
    system_context.set_config("demo_param", "demo_value")
    system_context.set_config("startup_time", "2023-01-01T00:00:00Z")
    demo_value = system_context.get_config("demo_param", "default")
    print(f"   + Установлен параметр: demo_param = {demo_value}")
    
    # Инициализируем и проверяем контекст
    print("\n4. Инициализация системного контекста...")
    is_initialized = system_context.initialize()
    print(f"   + Инициализация: {'Успешна' if is_initialized else 'Неудачна'}")
    
    # Создаем и регистрируем инструменты
    print("\n5. Регистрация инструментов...")
    file_reader = FileReaderTool()
    await file_reader.initialize()
    system_context.register_tool(file_reader)
    print(f"   + Инструмент '{file_reader.name}' зарегистрирован")
    
    file_writer = FileWriterTool()
    await file_writer.initialize()
    system_context.register_tool(file_writer)
    print(f"   + Инструмент '{file_writer.name}' зарегистрирован")
    
    # Создаем и регистрируем навык
    print("\n6. Регистрация навыков...")
    demo_skill = DemoSkill()
    system_context.register_skill(demo_skill)
    print(f"   + Навык '{demo_skill.name}' зарегистрирован")
    
    # Получаем все инструменты
    print("\n7. Проверка зарегистрированных компонентов...")
    all_tools = system_context.get_all_tools()
    print(f"   + Зарегистрировано инструментов: {len(all_tools)}")
    for name, tool in all_tools.items():
        print(f"     - {name}: {type(tool).__name__}")
    
    # Получаем все навыки
    all_skills = system_context.get_all_skills()
    print(f"   + Зарегистрировано навыков: {len(all_skills)}")
    for name, skill in all_skills.items():
        print(f"     - {name}: {type(skill).__name__}")
    
    # Валидация системы
    print("\n8. Валидация системного контекста...")
    is_valid = system_context.validate()
    print(f"   + Валидация: {'Успешна' if is_valid else 'Неудачна'}")
    
    # Демонстрация получения ресурсов
    print("\n9. Демонстрация получения ресурсов...")
    retrieved_tool = system_context.get_resource(file_reader.name)
    if retrieved_tool:
        print(f"   + Инструмент получен по имени: {retrieved_tool.name}")
    
    retrieved_skill = system_context.get_resource(demo_skill.name)
    if retrieved_skill:
        print(f"   + Навык получен по имени: {retrieved_skill.name}")
    
    # Экспорт конфигурации
    exported_config = system_context.export_config()
    print(f"   + Экспортировано параметров конфигурации: {len(exported_config)}")
    
    # Демонстрация работы навыка
    print("\n10. Тестирование работы навыка...")
    skill_result = await demo_skill.execute({"test_param": "test_value"})
    print(f"   + Навык выполнен: {skill_result['success']}")
    print(f"   + Результат: {skill_result['result']}")
    
    # Демонстрация работы инструмента (создадим временный файл для теста)
    print("\n11. Тестирование работы инструмента...")
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
        temp_file.write("Тестовое содержимое для проверки инструмента чтения файлов.")
        temp_file_path = temp_file.name
    
    try:
        # Тестируем инструмент чтения
        read_result = await file_reader.execute({
            "path": temp_file_path,
            "encoding": "utf-8"
        })
        print(f"   + Инструмент чтения выполнен: {read_result['success']}")
        if read_result['success']:
            print(f"   + Прочитано символов: {read_result['size']}")
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    
    print("\n=== Системный контекст успешно настроен и протестирован ===")
    
    return system_context


if __name__ == "__main__":
    asyncio.run(setup_and_test_system_context())
"""
Пример запуска инструмента и навыка без агента.

Этот пример демонстрирует:
- Создание и использование инструментов напрямую
- Создание и использование навыков напрямую
- Регистрацию в системном контексте
- Выполнение операций без участия агента
"""
import asyncio
import tempfile
import os
from domain.models.system.config import SystemConfig
from infrastructure.contexts.system.system_context import SystemContext
from infrastructure.tools.file_tools.file_reader_tool import FileReaderTool
from infrastructure.tools.file_tools.file_writer_tool import FileWriterTool
from domain.abstractions.base_skill import BaseSkill


class FileOperationSkill(BaseSkill):
    """Навык для выполнения операций с файлами."""
    
    def __init__(self, name: str = "file_operation_skill", description: str = "Skill for file operations"):
        super().__init__()
        self._name = name
        self._description = description
        self.dependencies = ["file_reader", "file_writer"]  # Зависимости от инструментов
        
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    async def execute(self, parameters: dict, session_context=None) -> dict:
        """Выполнение навыка - чтение и запись файлов."""
        operation = parameters.get("operation", "read")
        
        if operation == "read":
            file_path = parameters.get("path")
            if not file_path:
                return {"success": False, "error": "Path parameter is required for read operation"}
            
            # Используем инструмент для чтения файла
            reader = FileReaderTool()
            await reader.initialize()
            result = await reader.execute({"path": file_path})
            return {"success": True, "result": result, "operation": "read"}
        
        elif operation == "write":
            file_path = parameters.get("path")
            content = parameters.get("content", "")
            
            if not file_path:
                return {"success": False, "error": "Path parameter is required for write operation"}
            
            # Используем инструмент для записи файла
            writer = FileWriterTool()
            await writer.initialize()
            result = await writer.execute({"path": file_path, "content": content})
            return {"success": True, "result": result, "operation": "write"}
        
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}


async def demonstrate_direct_tool_usage():
    """Демонстрация прямого использования инструментов и навыков."""
    print("=== Демонстрация прямого использования инструментов и навыков ===\n")
    
    # Создаем временный файл для тестирования
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
        temp_file.write("Это тестовый файл для демонстрации работы инструментов.")
        temp_file_path = temp_file.name
    
    try:
        # Создаем системный контекст
        config = SystemConfig()
        system_context = SystemContext(config=config)
        print("✓ Системный контекст создан")
        
        # Создаем и инициализируем инструменты
        file_reader = FileReaderTool()
        await file_reader.initialize()
        print("✓ Инструмент чтения файлов инициализирован")
        
        file_writer = FileWriterTool()
        await file_writer.initialize()
        print("✓ Инструмент записи файлов инициализирован")
        
        # Регистрируем инструменты в системном контексте
        system_context.register_tool(file_reader)
        system_context.register_tool(file_writer)
        print("✓ Инструменты зарегистрированы в системном контексте")
        
        # Создаем и регистрируем навык
        file_skill = FileOperationSkill()
        system_context.register_skill(file_skill)
        print("✓ Навык файловых операций зарегистрирован")
        
        # Демонстрация прямого использования инструмента чтения
        print(f"\n--- Чтение файла: {temp_file_path} ---")
        read_result = await file_reader.execute({
            "path": temp_file_path,
            "encoding": "utf-8"
        })
        print(f"Результат чтения: {read_result}")
        
        # Демонстрация прямого использования инструмента записи
        print(f"\n--- Запись в файл: {temp_file_path}_new ---")
        new_file_path = temp_file_path + "_new"
        write_result = await file_writer.execute({
            "path": new_file_path,
            "content": "Новый контент, записанный через инструмент записи файлов.",
            "encoding": "utf-8"
        })
        print(f"Результат записи: {write_result}")
        
        # Демонстрация использования навыка для чтения
        print(f"\n--- Использование навыка для чтения: {temp_file_path} ---")
        skill_read_result = await file_skill.execute({
            "operation": "read",
            "path": temp_file_path
        })
        print(f"Результат чтения через навык: {skill_read_result}")
        
        # Демонстрация использования навыка для записи
        print(f"\n--- Использование навыка для записи: {temp_file_path}_skill ---")
        skill_write_result = await file_skill.execute({
            "operation": "write",
            "path": temp_file_path + "_skill",
            "content": "Контент, записанный через навык файловых операций."
        })
        print(f"Результат записи через навык: {skill_write_result}")
        
        # Проверяем, что файлы были созданы
        print(f"\n--- Проверка существования файлов ---")
        files_to_check = [temp_file_path, new_file_path, temp_file_path + "_skill"]
        for file_path in files_to_check:
            exists = os.path.exists(file_path)
            print(f"Файл {file_path} {'существует' if exists else 'не существует'}")
        
        # Демонстрация получения инструментов из системного контекста
        print(f"\n--- Получение инструментов из системного контекста ---")
        all_tools = system_context.get_all_tools()
        print(f"Зарегистрировано инструментов: {len(all_tools)}")
        for name, tool in all_tools.items():
            print(f"  - {name}: {type(tool).__name__}")
        
        # Демонстрация получения навыков из системного контекста
        print(f"\n--- Получение навыков из системного контекста ---")
        all_skills = system_context.get_all_skills()
        print(f"Зарегистрировано навыков: {len(all_skills)}")
        for name, skill in all_skills.items():
            print(f"  - {name}: {type(skill).__name__}")
        
    finally:
        # Очищаем временные файлы
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if os.path.exists(new_file_path):
            os.remove(new_file_path)
        if os.path.exists(temp_file_path + "_skill"):
            os.remove(temp_file_path + "_skill")
    
    print("\n=== Демонстрация завершена ===")


if __name__ == "__main__":
    asyncio.run(demonstrate_direct_tool_usage())
from dataclasses import dataclass
from typing import Optional, Any, Dict
import os

from domain.abstractions.event_types import EventType, IEventPublisher
from domain.abstractions.tools.base_tool import BaseTool
from domain.abstractions.tools.base_tool import ToolInput, ToolOutput


@dataclass
class FileWriteInput(ToolInput):
    path: str
    content: str
    encoding: str = "utf-8"
    append: bool = False
    backup: bool = True

@dataclass
class FileWriteOutput(ToolOutput):
    success: bool
    bytes_written: int = 0
    error: Optional[str] = None

class FileWriterTool(BaseTool):
    """Инструмент для записи содержимого в файлы."""

    name = "file_writer"
    
    @property
    def description(self) -> str:
        return "Запись содержимого в файлы с защитой от перезаписи важных файлов"
    
    def __init__(self, name: str = "file_writer", event_publisher: 'IEventPublisher' = None, system_context: Any = None, **kwargs):
        # Изменим инициализацию, чтобы она соответствовала базовому классу
        super().__init__()
        self.name = name
        self.event_publisher = event_publisher
        self.system_context = system_context
        self.config = kwargs.get("config", {})
        self.root_dir = self.config.get("root_dir", os.getcwd())
        self.allowed_extensions = self.config.get("allowed_extensions", ["py", "json", "md", "yaml", "txt"])
        self.protected_files = set(self.config.get("protected_files", [
            ".git", "package.json", "requirements.txt", "setup.py", 
            "pyproject.toml", "Dockerfile", ".env", "config.json"
        ]))
        
    async def initialize(self) -> bool:
        """Инициализация инструмента."""
        try:
            if not os.path.exists(self.root_dir):
                os.makedirs(self.root_dir, exist_ok=True)
            return os.access(self.root_dir, os.W_OK)
        except Exception as e:
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {"message": f"Ошибка инициализации FileWriterTool: {str(e)}"}
                )
            return False

    async def _validate_and_sanitize_path(self, path: str) -> Optional[str]:
        """Валидация и санитизация пути."""
        try:
            normalized_path = os.path.normpath(path)
            abs_path = os.path.abspath(os.path.join(self.root_dir, normalized_path))
            
            # Защита от выхода за пределы рабочей директории
            if not abs_path.startswith(os.path.abspath(self.root_dir)):
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.WARNING,
                        self.name,
                        {"message": f"Попытка доступа вне разрешенной директории: {abs_path}"}
                    )
                return None
                
            # Проверка на защищенные файлы
            filename = os.path.basename(abs_path)
            if filename in self.protected_files:
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.WARNING,
                        self.name,
                        {"message": f"Попытка записи в защищенный файл: {filename}"}
                    )
                return None
                
            # Проверка расширения файла
            ext = os.path.splitext(abs_path)[1][1:].lower()
            if ext and self.allowed_extensions and ext not in self.allowed_extensions:
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.WARNING,
                        self.name,
                        {"message": f"Недопустимое расширение файла: {ext}"}
                    )
                return None
                    
            return abs_path
        except Exception as e:
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {"message": f"Ошибка валидации пути {path}: {str(e)}"}
                )
            return None
    
    async def _execute_internal(self, input_data: FileWriteInput) -> FileWriteOutput:
        """Внутренняя реализация выполнения инструмента для записи файла."""
        try:
            safe_path = await self._validate_and_sanitize_path(input_data.path)
            if not safe_path:
                return FileWriteOutput(success=False, error="Недопустимый путь к файлу")
                
            # Проверка существования директории
            dir_path = os.path.dirname(safe_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                
            # Проверка прав на запись
            if os.path.exists(safe_path) and not os.access(safe_path, os.W_OK):
                return FileWriteOutput(success=False, error=f"Нет прав на запись в файл: {safe_path}")
                
            if not os.access(dir_path, os.W_OK):
                return FileWriteOutput(success=False, error=f"Нет прав на запись в директорию: {dir_path}")
                
            # Создание резервной копии если нужно
            if input_data.backup and os.path.exists(safe_path):
                backup_path = safe_path + ".backup"
                try:
                    with open(safe_path, 'rb') as src:
                        with open(backup_path, 'wb') as dst:
                            dst.write(src.read())
                except Exception as e:
                    if self.event_publisher:
                        await self.event_publisher.publish(
                            EventType.WARNING,
                            self.name,
                            {"message": f"Ошибка создания резервной копии: {str(e)}"}
                        )
                    # Продолжаем выполнение, т.к. резервное копирование не критично
                    
            # Запись файла
            try:
                mode = 'a' if input_data.append else 'w'
                with open(safe_path, mode, encoding=input_data.encoding, errors='ignore') as f:
                    f.write(input_data.content)
                    
                bytes_written = len(input_data.content.encode(input_data.encoding))
                return FileWriteOutput(success=True, bytes_written=bytes_written)
                
            except Exception as e:
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.ERROR,
                        self.name,
                        {"message": f"Ошибка записи файла {safe_path}: {str(e)}"}
                    )
                return FileWriteOutput(success=False, error=f"Ошибка записи файла: {str(e)}")
                
        except Exception as e:
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {"message": f"Ошибка выполнения FileWriterTool: {str(e)}"}
                )
            return FileWriteOutput(success=False, error=str(e))

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение инструмента согласно новому контракту."""
        # Создаем объект входных данных из параметров
        input_data = FileWriteInput(**parameters)
        # Выполняем внутреннюю логику
        result = await self._execute_internal(input_data)
        # Возвращаем результат виде словаря
        return {
            "success": result.success,
            "bytes_written": result.bytes_written,
            "error": result.error
        }
    
    async def shutdown(self) -> None:
        """Корректное завершение работы инструмента."""
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.INFO,
                self.name,
                {"message": "FileWriterTool завершил работу"}
            )

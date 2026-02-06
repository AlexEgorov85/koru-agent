from dataclasses import dataclass
from typing import Optional, Any, Dict
import os

from domain.abstractions.event_types import EventType, IEventPublisher
from domain.abstractions.tools.base_tool import BaseTool, ToolAdapter
from domain.abstractions.tools.base_tool import ToolInput, ToolOutput


@dataclass
class FileReadInput(ToolInput):
    path: str
    encoding: str = "utf-8"
    max_size: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

@dataclass
class FileReadOutput(ToolOutput):
    success: bool
    content: str = ""
    size: int = 0
    lines_count: int = 0
    encoding: str = ""
    error: Optional[str] = None

class FileReaderTool(BaseTool):
    """Инструмент для чтения содержимого файлов."""

    name = "file_reader"
    
    @property
    def description(self) -> str:
        return "Чтение содержимого файлов с защитой от чтения больших файлов"
    
    def __init__(self, name: str = "file_reader", event_publisher: IEventPublisher = None, system_context: Any = None, **kwargs):
        # Изменим инициализацию, чтобы она соответствовала базовому классу
        super().__init__()
        self.name = name
        self.event_publisher = event_publisher
        self.system_context = system_context
        self.config = kwargs.get("config", {})
        self.root_dir = self.config.get("root_dir", os.getcwd())
        self.allowed_extensions = self.config.get("allowed_extensions", ["py", "json", "md", "yaml"])
        self.max_file_size = self.config.get("max_file_size", 10 * 1024 * 1024)  # 10MB
        
    async def initialize(self) -> bool:
        """Инициализация инструмента."""
        try:
            if not os.path.exists(self.root_dir):
                os.makedirs(self.root_dir, exist_ok=True)
            return os.access(self.root_dir, os.R_OK)
        except Exception as e:
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {"message": f"Ошибка инициализации FileReaderTool: {str(e)}"}
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
                
            # Проверка расширения файла
            if os.path.isfile(abs_path):
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
    
    async def _execute_internal(self, input_data: FileReadInput) -> FileReadOutput:
        """Внутренняя реализация выполнения инструмента для чтения файла."""
        try:
            safe_path = await self._validate_and_sanitize_path(input_data.path)
            if not safe_path:
                return FileReadOutput(success=False, error="Недопустимый путь к файлу")
                
            if not os.path.exists(safe_path):
                return FileReadOutput(success=False, error=f"Файл не существует: {safe_path}")
                
            if not os.path.isfile(safe_path):
                return FileReadOutput(success=False, error=f"Путь не является файлом: {safe_path}")
                
            # Проверка размера файла
            file_size = os.path.getsize(safe_path)
            max_size = input_data.max_size or self.max_file_size
            
            if file_size > max_size:
                return FileReadOutput(
                    success=False,
                    error=f"Файл слишком большой: {file_size} байт. Максимум: {max_size} байт"
                )
                
            if not os.access(safe_path, os.R_OK):
                return FileReadOutput(success=False, error=f"Нет прав на чтение файла: {safe_path}")
                
            content = ""
            lines_count = 0
            
            try:
                if input_data.start_line is not None or input_data.end_line is not None:
                    # Чтение по строкам для больших файлов
                    with open(safe_path, 'r', encoding=input_data.encoding, errors='ignore') as f:
                        lines = f.readlines()
                        lines_count = len(lines)
                        
                        start_idx = max(0, (input_data.start_line or 1) - 1)
                        end_idx = input_data.end_line or len(lines)
                        
                        selected_lines = lines[start_idx:end_idx]
                        content = "".join(selected_lines)
                else:
                    # Чтение всего файла
                    with open(safe_path, 'r', encoding=input_data.encoding, errors='ignore') as f:
                        content = f.read()
                        lines_count = content.count('\n') + 1
                
                return FileReadOutput(
                    success=True,
                    content=content,
                    size=len(content),
                    lines_count=lines_count,
                    encoding=input_data.encoding
                )
            except UnicodeDecodeError as e:
                # Попытка чтения с другой кодировкой
                try:
                    with open(safe_path, 'r', encoding='latin-1', errors='ignore') as f:
                        content = f.read()
                        lines_count = content.count('\n') + 1
                        
                    return FileReadOutput(
                        success=True,
                        content=content,
                        size=len(content),
                        lines_count=lines_count,
                        encoding='latin-1'
                    )
                except Exception as inner_e:
                    if self.event_publisher:
                        await self.event_publisher.publish(
                            EventType.ERROR,
                            self.name,
                            {"message": f"Ошибка чтения файла {safe_path} с разными кодировками: {str(e)}, {str(inner_e)}"}
                        )
                    return FileReadOutput(success=False, error=f"Ошибка чтения файла с разными кодировками: {str(e)}")
            except Exception as e:
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.ERROR,
                        self.name,
                        {"message": f"Ошибка чтения файла {safe_path}: {str(e)}"}
                    )
                return FileReadOutput(success=False, error=str(e))
                
        except Exception as e:
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {"message": f"Ошибка выполнения FileReaderTool: {str(e)}"}
                )
            return FileReadOutput(success=False, error=str(e))
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение инструмента согласно новому контракту."""
        # Создаем объект входных данных из параметров
        input_data = FileReadInput(**parameters)
        # Выполняем внутреннюю логику
        result = await self._execute_internal(input_data)
        # Возвращаем результат виде словаря
        return {
            "success": result.success,
            "content": result.content,
            "size": result.size,
            "lines_count": result.lines_count,
            "encoding": result.encoding,
            "error": result.error
        }
    
    async def shutdown(self) -> None:
        """Корректное завершение работы инструмента."""
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.INFO,
                self.name,
                {"message": "FileReaderTool завершил работу"}
            )


# Применение адаптера к инструменту (на случай, если потребуется)
# FileReaderTool = ToolAdapter.wrap_tool(
#     FileReaderTool,
#     input_class=FileReadInput,
#     output_class=FileReadOutput
# )

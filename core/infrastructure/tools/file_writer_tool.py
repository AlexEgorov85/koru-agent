from dataclasses import dataclass
from typing import Optional
import os
import logging

from core.infrastructure.tools.base_tool import BaseTool, ToolInput, ToolOutput
from core.system_context.base_system_contex import BaseSystemContext

logger = logging.getLogger(__name__)

@dataclass
class FileWriteInput(ToolInput):
    path: str
    content: str
    encoding: str = "utf-8"
    mode: str = "w"  # "w" для записи, "a" для добавления
    create_directories: bool = True

@dataclass
class FileWriteOutput(ToolOutput):
    success: bool
    written_bytes: int = 0
    path: str = ""
    error: Optional[str] = None

class FileWriterTool(BaseTool):
    """Инструмент для записи содержимого в файлы."""
    
    @property
    def description(self) -> str:
        return "Запись содержимого в файлы с контролем перезаписи и созданием директорий"
    
    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        self.config = kwargs.get("config", {})
        self.root_dir = self.config.get("root_dir", os.getcwd())
        self.allowed_extensions = self.config.get("allowed_extensions", ["py", "json", "md", "yaml"])
        self.max_file_size = self.config.get("max_file_size", 5 * 1024 * 1024)  # 5MB
        self.backup_on_overwrite = self.config.get("backup_on_overwrite", True)
        
    async def initialize(self) -> bool:
        """Инициализация инструмента."""
        try:
            if not os.path.exists(self.root_dir):
                os.makedirs(self.root_dir, exist_ok=True)
            return os.access(self.root_dir, os.W_OK)
        except Exception as e:
            logger.error(f"Ошибка инициализации FileWriterTool: {str(e)}")
            return False
            
    async def _validate_and_sanitize_path(self, path: str) -> Optional[str]:
        """Валидация и санитизация пути."""
        try:
            normalized_path = os.path.normpath(path)
            abs_path = os.path.abspath(os.path.join(self.root_dir, normalized_path))
            
            # Защита от выхода за пределы рабочей директории
            if not abs_path.startswith(os.path.abspath(self.root_dir)):
                logger.warning(f"Попытка доступа вне разрешенной директории: {abs_path}")
                return None
                
            # Создание директорий при необходимости
            directory = os.path.dirname(abs_path)
            if not os.path.exists(directory) and self.config.get("create_directories", True):
                os.makedirs(directory, exist_ok=True)
                
            # Проверка расширения файла
            if '.' in os.path.basename(abs_path):
                ext = os.path.splitext(abs_path)[1][1:].lower()
                if ext and self.allowed_extensions and ext not in self.allowed_extensions:
                    logger.warning(f"Недопустимое расширение файла для записи: {ext}")
                    return None
                    
            return abs_path
        except Exception as e:
            logger.error(f"Ошибка валидации пути {path}: {str(e)}")
            return None
    
    async def _create_backup(self, file_path: str) -> bool:
        """Создание бэкапа файла перед перезаписью."""
        try:
            if not os.path.exists(file_path):
                return True
                
            backup_path = f"{file_path}.bak"
            with open(file_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            return True
        except Exception as e:
            logger.warning(f"Не удалось создать бэкап для {file_path}: {str(e)}")
            return False
    
    async def execute(self, input_data: FileWriteInput) -> FileWriteOutput:
        """Выполнение инструмента для записи файла."""
        try:
            safe_path = await self._validate_and_sanitize_path(input_data.path)
            if not safe_path:
                return FileWriteOutput(success=False, error="Недопустимый путь к файлу")
                
            # Проверка размера содержимого
            content_size = len(input_data.content.encode(input_data.encoding))
            if content_size > self.max_file_size:
                return FileWriteOutput(
                    success=False,
                    error=f"Содержимое слишком большое: {content_size} байт. Максимум: {self.max_file_size} байт"
                )
                
            directory = os.path.dirname(safe_path)
            if not os.access(directory, os.W_OK):
                return FileWriteOutput(success=False, error=f"Нет прав на запись в директорию: {directory}")
                
            # Создание бэкапа при перезаписи
            file_exists = os.path.exists(safe_path)
            if file_exists and self.backup_on_overwrite and input_data.mode == "w":
                await self._create_backup(safe_path)
                
            # Запись файла
            try:
                written_bytes = 0
                with open(safe_path, input_data.mode, encoding=input_data.encoding) as f:
                    written_bytes = f.write(input_data.content)
                    
                # Установка прав доступа
                if not file_exists:
                    os.chmod(safe_path, 0o644)
                    
                return FileWriteOutput(
                    success=True,
                    written_bytes=written_bytes,
                    path=os.path.relpath(safe_path, self.root_dir)
                )
            except Exception as e:
                logger.error(f"Ошибка записи файла {safe_path}: {str(e)}")
                return FileWriteOutput(success=False, error=str(e))
                
        except Exception as e:
            logger.error(f"Ошибка выполнения FileWriterTool: {str(e)}", exc_info=True)
            return FileWriteOutput(success=False, error=str(e))
    
    async def shutdown(self) -> None:
        """Корректное завершение работы инструмента."""
        logger.info("FileWriterTool завершил работу")

from dataclasses import dataclass
from typing import List, Optional
import os
import logging

from core.system_context.base_system_contex import BaseSystemContext
from core.infrastructure.tools.base_tool import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)

@dataclass
class FileListerInput(ToolInput):
    path: str = "."
    recursive: bool = False
    max_items: int = 100
    include_files: bool = True
    include_directories: bool = True
    extensions: Optional[List[str]] = None

@dataclass
class FileListItem:
    name: str
    path: str
    type: str  # "file" или "directory"
    size: int = 0
    last_modified: float = 0.0

@dataclass
class FileListerOutput(ToolOutput):
    success: bool
    items: List[FileListItem] = None
    error: Optional[str] = None
    total_items: int = 0
    truncated: bool = False

class FileListerTool(BaseTool):
    """Инструмент для получения списка файлов и директорий."""
    
    @property
    def description(self) -> str:
        return "Получение списка файлов и директорий с возможностью фильтрации"
    
    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        self.config = kwargs.get("config", {})
        self.root_dir = self.config.get("root_dir", os.getcwd())
        self.allowed_extensions = self.config.get("allowed_extensions", ["py", "json", "md", "yaml"])
        self.max_file_size = self.config.get("max_file_size", 100 * 1024 * 1024)  # 100MB
        
    async def initialize(self) -> bool:
        """Инициализация инструмента."""
        try:
            if not os.path.exists(self.root_dir):
                os.makedirs(self.root_dir, exist_ok=True)
            return os.access(self.root_dir, os.R_OK)
        except Exception as e:
            logger.error(f"Ошибка инициализации FileListerTool: {str(e)}")
            return False
            
    async def _validate_and_sanitize_path(self, path: str) -> Optional[str]:
        """Валидация и санитизация пути для защиты от path traversal."""
        try:
            normalized_path = os.path.normpath(path)
            abs_path = os.path.abspath(os.path.join(self.root_dir, normalized_path))
            
            # Защита от выхода за пределы рабочей директории
            if not abs_path.startswith(os.path.abspath(self.root_dir)):
                logger.warning(f"Попытка доступа вне разрешенной директории: {abs_path}")
                return None
                
            return abs_path
        except Exception as e:
            logger.error(f"Ошибка валидации пути {path}: {str(e)}")
            return None
    
    async def execute(self, input_data: FileListerInput) -> FileListerOutput:
        """Выполнение инструмента для получения списка файлов."""
        try:
            safe_path = await self._validate_and_sanitize_path(input_data.path)
            if not safe_path:
                return FileListerOutput(success=False, error="Недопустимый путь к файлу или директории")
                
            if not os.path.exists(safe_path):
                return FileListerOutput(success=False, error=f"Путь не существует: {safe_path}")
                
            if not os.access(safe_path, os.R_OK):
                return FileListerOutput(success=False, error=f"Нет прав на чтение: {safe_path}")
                
            items = []
            count = 0
            
            if os.path.isdir(safe_path):
                for item in os.listdir(safe_path):
                    if count >= input_data.max_items:
                        break
                        
                    item_path = os.path.join(safe_path, item)
                    is_dir = os.path.isdir(item_path)
                    
                    # Фильтр по типу
                    if (is_dir and not input_data.include_directories) or \
                       (not is_dir and not input_data.include_files):
                        continue
                        
                    # Фильтр по расширению
                    if not is_dir and input_data.extensions:
                        ext = os.path.splitext(item)[1][1:].lower()
                        if ext not in [e.lower() for e in input_data.extensions]:
                            continue
                    
                    # Защита от недопустимых расширений
                    if not is_dir and self.allowed_extensions:
                        ext = os.path.splitext(item)[1][1:].lower()
                        if ext not in self.allowed_extensions:
                            continue
                    
                    # Получение метаданных
                    size = 0
                    last_modified = 0.0
                    
                    try:
                        if not is_dir:
                            size = os.path.getsize(item_path)
                            if size > self.max_file_size:
                                continue
                        last_modified = os.path.getmtime(item_path)
                    except Exception as e:
                        logger.debug(f"Ошибка получения метаданных для {item_path}: {str(e)}")
                        continue
                    
                    items.append(FileListItem(
                        name=item,
                        path=os.path.relpath(item_path, self.root_dir),
                        type="directory" if is_dir else "file",
                        size=size,
                        last_modified=last_modified
                    ))
                    count += 1
                
                # Рекурсивный обход при необходимости
                if input_data.recursive and input_data.include_directories and count < input_data.max_items:
                    for root, dirs, files in os.walk(safe_path):
                        if root == safe_path:  # Пропускаем корневую директорию
                            continue
                            
                        if count >= input_data.max_items:
                            break
                            
                        # Обработка поддиректорий
                        for dir_name in dirs:
                            if count >= input_data.max_items:
                                break
                                
                            dir_path = os.path.join(root, dir_name)
                            last_modified = os.path.getmtime(dir_path)
                            
                            items.append(FileListItem(
                                name=dir_name,
                                path=os.path.relpath(dir_path, self.root_dir),
                                type="directory",
                                last_modified=last_modified
                            ))
                            count += 1
                        
                        # Обработка файлов
                        for file_name in files:
                            if count >= input_data.max_items:
                                break
                                
                            file_path = os.path.join(root, file_name)
                            
                            # Применение фильтров
                            if input_data.extensions:
                                ext = os.path.splitext(file_name)[1][1:].lower()
                                if ext not in [e.lower() for e in input_data.extensions]:
                                    continue
                            
                            if self.allowed_extensions:
                                ext = os.path.splitext(file_name)[1][1:].lower()
                                if ext not in self.allowed_extensions:
                                    continue
                            
                            try:
                                size = os.path.getsize(file_path)
                                if size > self.max_file_size:
                                    continue
                                last_modified = os.path.getmtime(file_path)
                                
                                items.append(FileListItem(
                                    name=file_name,
                                    path=os.path.relpath(file_path, self.root_dir),
                                    type="file",
                                    size=size,
                                    last_modified=last_modified
                                ))
                                count += 1
                            except Exception as e:
                                logger.debug(f"Ошибка получения метаданных для {file_path}: {str(e)}")
                                continue
                
                return FileListerOutput(
                    success=True,
                    items=items,
                    total_items=count,
                    truncated=count >= input_data.max_items
                )
            else:
                # Если путь указывает на файл
                size = os.path.getsize(safe_path)
                last_modified = os.path.getmtime(safe_path)
                
                items.append(FileListItem(
                    name=os.path.basename(safe_path),
                    path=os.path.relpath(safe_path, self.root_dir),
                    type="file",
                    size=size,
                    last_modified=last_modified
                ))
                
                return FileListerOutput(
                    success=True,
                    items=items,
                    total_items=1,
                    truncated=False
                )
                
        except Exception as e:
            logger.error(f"Ошибка выполнения FileListerTool: {str(e)}", exc_info=True)
            return FileListerOutput(success=False, error=str(e))
    
    async def shutdown(self) -> None:
        """Корректное завершение работы инструмента."""
        logger.info("FileListerTool завершил работу")
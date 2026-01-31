
from dataclasses import dataclass
import fnmatch
import re
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
    """Инструмент для получения списка файлов и директорий с защитой от опасных директорий."""

    name = "file_lister"
    
    @property
    def description(self) -> str:
        return "Получение списка файлов и директорий с возможностью фильтрации и игнорированием системных директорий"
    
    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        self.config = kwargs.get("config", {})
        self.root_dir = self.config.get("root_dir", os.getcwd())
        self.allowed_extensions = self.config.get("allowed_extensions", ["py", "json", "md", "yaml"])
        self.max_file_size = self.config.get("max_file_size", 100 * 1024 * 1024)  # 100MB
        
        # Стандартные антипаттерны для игнорирования
        self.ignored_dirs = set([
            # Системные директории
            ".git", 
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            # Директории сборки
            "build",
            "dist",
            "*.egg-info",
            ".tox",
            # Кэши и временные файлы
            ".mypy_cache",
            ".pytest_cache",
            ".coverage", 
            ".ipynb_checkpoints",
            # IDE
            ".vscode",
            ".idea",
            ".settings",
            # Логи и данные
            "logs",
            "__pycache__"
        ])
        
        # Добавляем кастомные паттерны из конфига
        custom_ignored_dirs = self.config.get("ignored_dirs", [])
        self.ignored_dirs.update(custom_ignored_dirs)
        
        # Компилируем паттерны для быстрой проверки
        self.ignore_patterns = [re.compile(fnmatch.translate(pattern), re.IGNORECASE) 
                               for pattern in self.ignored_dirs]

    async def initialize(self) -> bool:
        """Инициализация инструмента."""
        try:
            if not os.path.exists(self.root_dir):
                os.makedirs(self.root_dir, exist_ok=True)
            return os.access(self.root_dir, os.R_OK)
        except Exception as e:
            logger.error(f"Ошибка инициализации FileListerTool: {str(e)}")
            return False

    def _is_ignored_directory(self, dir_name: str, dir_path: str = None) -> bool:
        """Проверка, является ли директория игнорируемой по антипаттернам."""
        # Проверка по имени директории
        for pattern in self.ignore_patterns:
            if pattern.match(dir_name.lower()):
                # logger.debug(f"Игнорируем директорию по паттерну: {dir_name}")
                return True
                
        # Дополнительная проверка по полному пути (для вложенных директорий)
        if dir_path:
            normalized_path = os.path.normpath(dir_path)
            path_lower = normalized_path.lower()
            
            # Проверка на .git подмодули (обычно в поддиректориях .git/modules/)
            if ".git" in path_lower and "modules" in path_lower:
                return True
            
            # Проверка на другие специфичные паттерны
            dangerous_paths = [
                "/.git/",
                "/__pycache__/",
                "/node_modules/"
            ]
            for dangerous in dangerous_paths:
                if dangerous in path_lower:
                    logger.debug(f"Игнорируем директорию по пути: {dir_path}")
                    return True
                    
        return False

    async def _validate_and_sanitize_path(self, path: str) -> Optional[str]:
        """Валидация и санитизация пути для защиты от path traversal."""
        try:
            normalized_path = os.path.normpath(path)
            abs_path = os.path.abspath(os.path.join(self.root_dir, normalized_path))
            rel_path = os.path.relpath(abs_path, self.root_dir)
            
            # Защита от выхода за пределы рабочей директории
            if not abs_path.startswith(os.path.abspath(self.root_dir)):
                logger.warning(f"Попытка доступа вне разрешенной директории: {abs_path}")
                return None
                
            # Проверка на игнорируемые директории
            if os.path.isdir(abs_path):
                parent_dir = os.path.dirname(rel_path)
                current_dir = os.path.basename(rel_path)
                
                # Если это корень проекта, не проверяем на игнор
                if parent_dir != "." and self._is_ignored_directory(current_dir, rel_path):
                    logger.debug(f"Попытка доступа к игнорируемой директории: {rel_path}")
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
            
            # Если путь указывает на файл, возвращаем его напрямую
            if os.path.isfile(safe_path):
                return self._process_single_file(safe_path)
            
            # Обработка директории
            try:
                # Одноуровневый список файлов и директорий
                for item in os.listdir(safe_path):
                    if count >= input_data.max_items:
                        break
                        
                    item_path = os.path.join(safe_path, item)
                    rel_path = os.path.relpath(item_path, self.root_dir)
                    
                    # Проверка на игнорируемые директории
                    if os.path.isdir(item_path) and self._is_ignored_directory(item, rel_path):
                        logger.debug(f"Пропускаем игнорируемую директорию: {rel_path}")
                        continue
                        
                    item_info = self._process_item(item, item_path, rel_path, input_data)
                    if item_info:
                        items.append(item_info)
                        count += 1
                
                # Рекурсивный обход при необходимости
                if input_data.recursive and input_data.include_directories:
                    for root, dirs, files in os.walk(safe_path):
                        # Фильтрация директорий на лету
                        dirs[:] = [d for d in dirs if not self._is_ignored_directory(d, os.path.join(root, d))]
                        
                        if count >= input_data.max_items:
                            break
                        
                        # Пропускаем корневую директорию, так как она уже обработана
                        if root == safe_path:
                            continue
                            
                        # Обработка поддиректорий
                        for dir_name in dirs:
                            if count >= input_data.max_items:
                                break
                                
                            dir_path = os.path.join(root, dir_name)
                            rel_path = os.path.relpath(dir_path, self.root_dir)
                            
                            if input_data.include_directories:
                                items.append(FileListItem(
                                    name=dir_name,
                                    path=rel_path,
                                    type="directory",
                                    last_modified=os.path.getmtime(dir_path)
                                ))
                                count += 1
                        
                        # Обработка файлов
                        for file_name in files:
                            if count >= input_data.max_items:
                                break
                                
                            file_path = os.path.join(root, file_name)
                            rel_path = os.path.relpath(file_path, self.root_dir)
                            
                            # Применение фильтров
                            if not self._should_include_file(file_name, file_path, input_data):
                                continue
                                
                            file_info = self._process_file(file_name, file_path, rel_path)
                            if file_info:
                                items.append(file_info)
                                count += 1
            except PermissionError as e:
                logger.warning(f"Нет прав доступа к директории {safe_path}: {str(e)}")
                return FileListerOutput(success=False, error=f"Нет прав доступа к директории: {safe_path}")
            
            return FileListerOutput(
                success=True,
                items=items,
                total_items=count,
                truncated=count >= input_data.max_items
            )
            
        except Exception as e:
            logger.error(f"Ошибка выполнения FileListerTool: {str(e)}", exc_info=True)
            return FileListerOutput(success=False, error=str(e))
    
    def _should_include_file(self, file_name: str, file_path: str, input_data: FileListerInput) -> bool:
        """Проверка, должен ли файл быть включен в результат."""
        # Фильтр по расширению
        if input_data.extensions:
            ext = os.path.splitext(file_name)[1][1:].lower()
            if ext not in [e.lower() for e in input_data.extensions]:
                return False
        
        # Защита от недопустимых расширений
        if self.allowed_extensions:
            ext = os.path.splitext(file_name)[1][1:].lower()
            if ext and ext not in self.allowed_extensions:
                return False
        
        # Проверка максимального размера файла
        try:
            size = os.path.getsize(file_path)
            if size > self.max_file_size:
                logger.debug(f"Пропускаем файл {file_name} - превышает максимальный размер {self.max_file_size} байт")
                return False
        except OSError:
            return False
            
        return True
    
    def _process_item(self, item_name: str, item_path: str, rel_path: str, input_data: FileListerInput) -> Optional[FileListItem]:
        """Обработка отдельного элемента (файла или директории)."""
        is_dir = os.path.isdir(item_path)
        
        # Фильтр по типу
        if (is_dir and not input_data.include_directories) or (not is_dir and not input_data.include_files):
            return None
        
        # Защита от опасных директорий
        if is_dir and self._is_ignored_directory(item_name, rel_path):
            return None
        
        try:
            last_modified = os.path.getmtime(item_path)
            return FileListItem(
                name=item_name,
                path=rel_path,
                type="directory" if is_dir else "file",
                size=0 if is_dir else os.path.getsize(item_path),
                last_modified=last_modified
            )
        except (OSError, PermissionError) as e:
            logger.debug(f"Ошибка получения метаданных для {item_path}: {str(e)}")
            return None
    
    def _process_file(self, file_name: str, file_path: str, rel_path: str) -> Optional[FileListItem]:
        """Обработка отдельного файла."""
        try:
            size = os.path.getsize(file_path)
            last_modified = os.path.getmtime(file_path)
            return FileListItem(
                name=file_name,
                path=rel_path,
                type="file",
                size=size,
                last_modified=last_modified
            )
        except (OSError, PermissionError) as e:
            logger.debug(f"Ошибка получения метаданных для файла {file_path}: {str(e)}")
            return None
    
    def _process_single_file(self, file_path: str) -> FileListerOutput:
        """Обработка одного файла."""
        try:
            size = os.path.getsize(file_path)
            last_modified = os.path.getmtime(file_path)
            rel_path = os.path.relpath(file_path, self.root_dir)
            items = [FileListItem(
                name=os.path.basename(file_path),
                path=rel_path,
                type="file",
                size=size,
                last_modified=last_modified
            )]
            return FileListerOutput(
                success=True,
                items=items,
                total_items=1,
                truncated=False
            )
        except Exception as e:
            logger.error(f"Ошибка обработки файла {file_path}: {str(e)}")
            return FileListerOutput(success=False, error=str(e))
        
    async def shutdown(self) -> None:
        """Корректное завершение работы инструмента."""
        logger.info("FileListerTool завершил работу")
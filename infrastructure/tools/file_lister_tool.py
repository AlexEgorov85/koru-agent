
"""
File Lister Tool — инструмент для получения списка файлов и директорий с защитой от опасных директорий.

АРХИТЕКТУРА:
- Расположение: инфраструктурный слой (инструмент)
- Зависимости: только от абстракций (BaseTool, BaseSystemContext, EventSystem)
- Ответственность: безопасное получение списка файлов и директорий с фильтрацией
- Принципы: соблюдение инверсии зависимостей (D в SOLID)

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
```python
from infrastructure.tools.file_lister_tool import FileListerTool
tool = FileListerTool(name="file_lister", system_context=system_context)
result = await tool.execute(input_data=FileListerInput(path=".", recursive=True))
print(result.items)
```
"""

from dataclasses import dataclass
import fnmatch
import re
from typing import Any, List, Optional, Dict
import os

from domain.abstractions.tools.base_tool import BaseTool
from domain.abstractions.tools.base_tool import ToolInput, ToolOutput
from domain.abstractions.event_system import IEventPublisher, EventType


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
    
    def __init__(self, name: str = "file_lister", event_publisher: 'IEventPublisher' = None, system_context: Any = None, **kwargs):
        # Изменим инициализацию, чтобы она соответствовала базовому классу
        super().__init__()
        self.name = name
        self.event_publisher = event_publisher
        self.system_context = system_context
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
            # Используем шину событий вместо логгера
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {
                        "message": f"Ошибка инициализации FileListerTool: {str(e)}",
                        "error": str(e),
                        "context": "initialization_error"
                    }
                )
            return False

    def _is_ignored_directory(self, dir_name: str, dir_path: str = None) -> bool:
        """Проверка, является ли директория игнорируемой по антипаттернам."""
        # Проверка по имени директории
        for pattern in self.ignore_patterns:
            if pattern.match(dir_name.lower()):
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
                    # Используем шину событий вместо логгера
                    # Так как это синхронная функция, не можем использовать await
                    # Но можем вызвать асинхронную функцию через event loop
                    import asyncio
                    if self.event_publisher:
                        try:
                            loop = asyncio.get_running_loop()
                            # Создаем задачу для асинхронного вызова
                            asyncio.create_task(self.event_publisher.publish(
                                EventType.DEBUG,
                                self.name,
                                {
                                    "message": f"Игнорируем директорию по пути: {dir_path}",
                                    "directory_path": dir_path,
                                    "context": "ignored_directory_path"
                                }
                            ))
                        except RuntimeError as e:
                            # Если не удалось получить event loop, логируем ошибку
                            if self.event_publisher:
                                try:
                                    asyncio.create_task(self.event_publisher.publish(
                                        EventType.WARNING,
                                        self.name,
                                        {
                                            "message": "Не удалось получить event loop для публикации события",
                                            "error": str(e),
                                            "context": "event_loop_error"
                                        }
                                    ))
                                except Exception:
                                    # Если даже публикация ошибки не удалась, ничего не делаем
                                    pass
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
                # Используем шину событий вместо логгера
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.WARNING,
                        self.name,
                        {
                            "message": f"Попытка доступа вне разрешенной директории: {abs_path}",
                            "path": abs_path,
                            "context": "access_outside_allowed_directory"
                        }
                    )
                return None
                
            # Проверка на игнорируемые директории
            if os.path.isdir(abs_path):
                parent_dir = os.path.dirname(rel_path)
                current_dir = os.path.basename(rel_path)
                
                # Если это корень проекта, не проверяем на игнор
                if parent_dir != "." and self._is_ignored_directory(current_dir, rel_path):
                    # Используем шину событий вместо логгера
                    if self.event_publisher:
                        await self.event_publisher.publish(
                            EventType.DEBUG,
                            self.name,
                            {
                                "message": f"Попытка доступа к игнорируемой директории: {rel_path}",
                                "path": rel_path,
                                "context": "ignored_directory_access_attempt"
                            }
                        )
                    return None
                    
            return abs_path
        except Exception as e:
            # Используем шину событий вместо логгера
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {
                        "message": f"Ошибка валидации пути {path}: {str(e)}",
                        "path": path,
                        "error": str(e),
                        "context": "path_validation_error"
                    }
                )
            return None

    async def _execute_internal(self, input_data: FileListerInput) -> FileListerOutput:
        """Внутренняя реализация выполнения инструмента для получения списка файлов."""
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
                        # Используем шину событий вместо логгера
                        if self.event_publisher:
                            await self.event_publisher.publish(
                                EventType.DEBUG,
                                self.name,
                                {
                                    "message": f"Пропускаем игнорируемую директорию: {rel_path}",
                                    "directory_path": rel_path,
                                    "context": "skipping_ignored_directory"
                                }
                            )
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
                # Используем шину событий вместо логгера
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.WARNING,
                        self.name,
                        {
                            "message": f"Нет прав доступа к директории {safe_path}: {str(e)}",
                            "path": safe_path,
                            "error": str(e),
                            "context": "permission_error"
                        }
                    )
                return FileListerOutput(success=False, error=f"Нет прав доступа к директории: {safe_path}")
            
            return FileListerOutput(
                success=True,
                items=items,
                total_items=count,
                truncated=count >= input_data.max_items
            )
            
        except Exception as e:
            # Используем шину событий вместо логгера
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {
                        "message": f"Ошибка выполнения FileListerTool: {str(e)}",
                        "error": str(e),
                        "context": "execution_error"
                    }
                )
            return FileListerOutput(success=False, error=str(e))

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение инструмента согласно новому контракту."""
        # Создаем объект входных данных из параметров
        input_data = FileListerInput(**parameters)
        # Выполняем внутреннюю логику
        result = await self._execute_internal(input_data)
        # Возвращаем результат виде словаря
        return {
            "success": result.success,
            "items": [item.__dict__ for item in result.items] if result.items else [],
            "error": result.error,
            "total_items": result.total_items,
            "truncated": result.truncated
        }
    
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
                # Используем шину событий вместо логгера
                if self.event_publisher:
                    import asyncio
                    try:
                        loop = asyncio.get_running_loop()
                        # Создаем задачу для асинхронного вызова
                        asyncio.create_task(self.event_publisher.publish(
                            EventType.DEBUG,
                            self.name,
                            {
                                "message": f"Пропускаем файл {file_name} - превышает максимальный размер {self.max_file_size} байт",
                                "file_name": file_name,
                                "max_size": self.max_file_size,
                                "context": "file_size_exceeded"
                            }
                        ))
                    except RuntimeError as e:
                        # Если не удалось получить event loop, логируем ошибку
                        if self.event_publisher:
                            try:
                                asyncio.create_task(self.event_publisher.publish(
                                    EventType.WARNING,
                                    self.name,
                                    {
                                        "message": "Не удалось получить event loop для публикации события",
                                        "error": str(e),
                                        "context": "event_loop_error"
                                    }
                                ))
                            except Exception:
                                # Если даже публикация ошибки не удалась, ничего не делаем
                                pass
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
            # Используем шину событий вместо логгера
            if self.event_publisher:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # Создаем задачу для асинхронного вызова
                    asyncio.create_task(self.event_publisher.publish(
                        EventType.DEBUG,
                        self.name,
                        {
                            "message": f"Ошибка получения метаданных для {item_path}: {str(e)}",
                            "item_path": item_path,
                            "error": str(e),
                            "context": "metadata_retrieval_error"
                        }
                    ))
                except RuntimeError as e:
                    # Если не удалось получить event loop, логируем ошибку
                    if self.event_publisher:
                        try:
                            asyncio.create_task(self.event_publisher.publish(
                                EventType.WARNING,
                                self.name,
                                {
                                    "message": "Не удалось получить event loop для публикации события",
                                    "error": str(e),
                                    "context": "event_loop_error"
                                }
                            ))
                        except Exception:
                            # Если даже публикация ошибки не удалась, ничего не делаем
                            pass
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
            # Используем шину событий вместо логгера
            if self.event_publisher:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # Создаем задачу для асинхронного вызова
                    asyncio.create_task(self.event_publisher.publish(
                        EventType.DEBUG,
                        self.name,
                        {
                            "message": f"Ошибка получения метаданных для файла {file_path}: {str(e)}",
                            "file_path": file_path,
                            "error": str(e),
                            "context": "file_metadata_retrieval_error"
                        }
                    ))
                except RuntimeError as e:
                    # Если не удалось получить event loop, логируем ошибку
                    if self.event_publisher:
                        try:
                            asyncio.create_task(self.event_publisher.publish(
                                EventType.WARNING,
                                self.name,
                                {
                                    "message": "Не удалось получить event loop для публикации события",
                                    "error": str(e),
                                    "context": "event_loop_error"
                                }
                            ))
                        except Exception:
                            # Если даже публикация ошибки не удалась, ничего не делаем
                            pass
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
            # Используем шину событий вместо логгера
            if self.event_publisher:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # Создаем задачу для асинхронного вызова
                    asyncio.create_task(self.event_publisher.publish(
                        EventType.ERROR,
                        self.name,
                        {
                            "message": f"Ошибка обработки файла {file_path}: {str(e)}",
                            "file_path": file_path,
                            "error": str(e),
                            "context": "file_processing_error"
                        }
                    ))
                except RuntimeError as e:
                    # Если не удалось получить event loop, логируем ошибку
                    if self.event_publisher:
                        try:
                            asyncio.create_task(self.event_publisher.publish(
                                EventType.WARNING,
                                self.name,
                                {
                                    "message": "Не удалось получить event loop для публикации события",
                                    "error": str(e),
                                    "context": "event_loop_error"
                                }
                            ))
                        except Exception:
                            # Если даже публикация ошибки не удалась, ничего не делаем
                            pass
            return FileListerOutput(success=False, error=str(e))
        
    async def shutdown(self) -> None:
        """Корректное завершение работы инструмента."""
        # Используем шину событий вместо логгера
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.INFO,
                self.name,
                {
                    "message": "FileListerTool завершил работу",
                    "context": "tool_shutdown"
                }
            )

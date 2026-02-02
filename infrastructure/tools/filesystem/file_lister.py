"""
FileListerTool - инструмент для получения списка файлов и директорий.
"""
from typing import Dict, Any
from domain.abstractions.tools.base_tool import BaseTool
from domain.abstractions.tools.base_tool import ToolInput, ToolOutput
import os


class FileListInput(ToolInput):
    path: str = "."
    recursive: bool = False
    include_files: bool = True
    include_directories: bool = True
    max_items: int = 1000


class FileItem:
    def __init__(self, name: str, path: str, type: str, size: int = 0):
        self.name = name
        self.path = path
        self.type = type  # "file" или "directory"
        self.size = size


class FileListOutput(ToolOutput):
    success: bool
    items: list = None
    error: str = None

    def __post_init__(self):
        if self.items is None:
            self.items = []


class FileListerTool(BaseTool):
    """
    Инструмент для получения списка файлов и директорий.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (инструмент)
    - Зависимости: от абстракций (BaseTool)
    - Ответственность: безопасное получение списка файлов и директорий
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    name = "file_lister"
    
    @property
    def description(self) -> str:
        return "Получение списка файлов и директорий по указанному пути"
    
    async def execute(self, input_data: FileListInput) -> FileListOutput:
        """
        Выполнение операции получения списка файлов и директорий.
        
        Args:
            input_data: Параметры операции, содержащие 'path' - путь к директории
        
        Returns:
            FileListOutput: Результат операции получения списка файлов и директорий
        """
        try:
            scan_path = input_data.path
            if not scan_path:
                scan_path = "."
            
            if not os.path.exists(scan_path):
                return FileListOutput(success=False, error=f"Путь не существует: {scan_path}")
            
            if not os.access(scan_path, os.R_OK):
                return FileListOutput(success=False, error=f"Нет прав на чтение директории: {scan_path}")
            
            items = []
            count = 0
            
            if os.path.isfile(scan_path):
                # Если передан путь к файлу, возвращаем его как один элемент
                stat = os.stat(scan_path)
                items.append(FileItem(
                    name=os.path.basename(scan_path),
                    path=scan_path,
                    type="file",
                    size=stat.st_size
                ))
            else:
                # Если рекурсивный поиск включен
                if input_data.recursive:
                    for root, dirs, files in os.walk(scan_path):
                        # Фильтруем директории
                        if not input_data.include_directories:
                            dirs.clear()
                            
                        for d in dirs:
                            if count >= input_data.max_items:
                                break
                                
                            dir_path = os.path.join(root, d)
                            items.append(FileItem(
                                name=d,
                                path=dir_path,
                                type="directory"
                            ))
                            count += 1
                            
                        if not input_data.include_files:
                            continue
                            
                        for f in files:
                            if count >= input_data.max_items:
                                break
                                
                            file_path = os.path.join(root, f)
                            stat = os.stat(file_path)
                            items.append(FileItem(
                                name=f,
                                path=file_path,
                                type="file",
                                size=stat.st_size
                            ))
                            count += 1
                            
                        if count >= input_data.max_items:
                            break
                else:
                    # Простой список файлов и директорий в указанной директории
                    entries = os.listdir(scan_path)
                    
                    for entry in entries:
                        if count >= input_data.max_items:
                            break
                            
                        full_path = os.path.join(scan_path, entry)
                        
                        if os.path.isdir(full_path):
                            if input_data.include_directories:
                                items.append(FileItem(
                                    name=entry,
                                    path=full_path,
                                    type="directory"
                                ))
                                count += 1
                        elif os.path.isfile(full_path):
                            if input_data.include_files:
                                stat = os.stat(full_path)
                                items.append(FileItem(
                                    name=entry,
                                    path=full_path,
                                    type="file",
                                    size=stat.st_size
                                ))
                                count += 1
            
            return FileListOutput(success=True, items=items)
            
        except PermissionError:
            return FileListOutput(success=False, error=f"Нет прав на чтение директории: {input_data.path}")
            
        except Exception as e:
            return FileListOutput(success=False, error=str(e))
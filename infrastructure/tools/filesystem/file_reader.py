"""
FileReaderTool - инструмент для чтения содержимого файлов.
"""
from typing import Dict, Any
from domain.abstractions.tools.base_tool import BaseTool
from domain.abstractions.tools.base_tool import ToolInput, ToolOutput
import os


class FileReadInput(ToolInput):
    path: str
    encoding: str = "utf-8"


class FileReadOutput(ToolOutput):
    success: bool
    content: str = ""
    size: int = 0
    error: str = None


class FileReaderTool(BaseTool):
    """
    Инструмент для чтения содержимого файлов.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (инструмент)
    - Зависимости: от абстракций (BaseTool)
    - Ответственность: безопасное чтение содержимого файлов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    name = "file_reader"
    
    @property
    def description(self) -> str:
        return "Чтение содержимого файлов по указанному пути"
    
    async def execute(self, input_data: FileReadInput) -> FileReadOutput:
        """
        Выполнение операции чтения файла.
        
        Args:
            input_data: Параметры операции, содержащие 'path' - путь к файлу
        
        Returns:
            FileReadOutput: Результат операции чтения файла
        """
        try:
            file_path = input_data.path
            if not file_path:
                return FileReadOutput(success=False, error="Параметр 'path' обязателен для чтения файла")
            
            # Проверяем, что файл существует
            if not os.path.exists(file_path):
                return FileReadOutput(success=False, error=f"Файл не найден: {file_path}")
            
            # Проверяем права доступа
            if not os.access(file_path, os.R_OK):
                return FileReadOutput(success=False, error=f"Нет прав на чтение файла: {file_path}")
            
            # Открываем и читаем файл
            with open(file_path, 'r', encoding=input_data.encoding, errors='ignore') as file:
                content = file.read()
            
            return FileReadOutput(
                success=True,
                content=content,
                size=len(content)
            )
            
        except FileNotFoundError:
            return FileReadOutput(success=False, error=f"Файл не найден: {input_data.path}")
            
        except PermissionError:
            return FileReadOutput(success=False, error=f"Нет прав на чтение файла: {input_data.path}")
            
        except Exception as e:
            return FileReadOutput(success=False, error=str(e))
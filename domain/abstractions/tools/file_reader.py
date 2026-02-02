from abc import ABC, abstractmethod
from typing import List, Optional


class BaseFileReader(ABC):
    """
    Базовый абстрактный класс для инструментов чтения файлов.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от доменных моделей
    - Ответственность: определение контракта для чтения файлов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    class FileReaderTool(BaseFileReader):
        async def read_file(self, filepath: str) -> str:
            # Реализация чтения файла
            pass
    ```
    """
    
    @abstractmethod
    async def read_file(self, filepath: str) -> str:
        """
        Асинхронное чтение содержимого файла.
        
        Args:
            filepath: Путь к файлу для чтения
            
        Returns:
            str: Содержимое файла в виде строки
        """
        pass
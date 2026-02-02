from abc import ABC, abstractmethod
from typing import List, Optional


class BaseFileLister(ABC):
    """
    Базовый абстрактный класс для инструментов получения списка файлов.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от доменных моделей
    - Ответственность: определение контракта для получения списка файлов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    class FileListerTool(BaseFileLister):
        async def list_files(self, directory: str, extensions: Optional[List[str]] = None) -> List[str]:
            # Реализация получения списка файлов
            pass
    ```
    """
    
    @abstractmethod
    async def list_files(self, directory: str, extensions: Optional[List[str]] = None) -> List[str]:
        """
        Асинхронное получение списка файлов в директории.
        
        Args:
            directory: Директория для сканирования
            extensions: Необязательный список расширений файлов для фильтрации
            
        Returns:
            List[str]: Список путей к файлам
        """
        pass
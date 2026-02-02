"""
LanguageRegistry - сервис для регистрации и управления поддерживаемыми языками программирования.
"""
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod


class LanguageAdapter(ABC):
    """
    Абстрактный базовый класс для адаптера языка программирования.
    """
    
    @abstractmethod
    def get_name(self) -> str:
        """Возвращает имя языка."""
        pass
    
    @abstractmethod
    def get_file_extensions(self) -> List[str]:
        """Возвращает список поддерживаемых расширений файлов."""
        pass
    
    @abstractmethod
    def parse(self, source_code: str, source_bytes: bytes) -> Any:
        """Парсит исходный код в AST."""
        pass
    
    @abstractmethod
    def get_outline(self, ast: Any, file_path: str) -> List[Any]:
        """Получает структуру файла (классы, функции и т.д.)."""
        pass
    
    @abstractmethod
    def resolve_import(self, import_name: str, current_file: str, project_files: List[str]) -> Optional[str]:
        """Разрешает импорт в путь к файлу."""
        pass


class LanguageRegistry:
    """
    Сервис для регистрации и управления поддерживаемыми языками программирования.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (сервис)
    - Ответственность: регистрация и предоставление адаптеров для разных языков
    - Принципы: соблюдение открытости/закрытости (O в SOLID)
    """
    
    def __init__(self):
        """Инициализация реестра языков."""
        self._adapters: Dict[str, LanguageAdapter] = {}
        self._extension_map: Dict[str, LanguageAdapter] = {}
    
    def register_language(self, adapter: LanguageAdapter):
        """
        Регистрация адаптера языка.
        
        Args:
            adapter: Адаптер языка, реализующий LanguageAdapter
        """
        name = adapter.get_name()
        self._adapters[name] = adapter
        
        # Обновляем карту расширений
        for ext in adapter.get_file_extensions():
            self._extension_map[ext.lstrip('.')] = adapter
    
    def get_adapter_by_name(self, language_name: str) -> Optional[LanguageAdapter]:
        """
        Получение адаптера по имени языка.
        
        Args:
            language_name: Имя языка
            
        Returns:
            LanguageAdapter: Адаптер языка или None, если не найден
        """
        return self._adapters.get(language_name)
    
    def get_adapter_for_file(self, file_path: str) -> Optional[LanguageAdapter]:
        """
        Получение адаптера для файла по его расширению.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            LanguageAdapter: Адаптер языка или None, если не найден
        """
        import os
        _, ext = os.path.splitext(file_path)
        ext = ext.lstrip('.')
        return self._extension_map.get(ext)
    
    def get_supported_languages(self) -> List[str]:
        """
        Получение списка поддерживаемых языков.
        
        Returns:
            List[str]: Список имен поддерживаемых языков
        """
        return list(self._adapters.keys())
    
    def get_supported_extensions(self) -> List[str]:
        """
        Получение списка поддерживаемых расширений файлов.
        
        Returns:
            List[str]: Список поддерживаемых расширений
        """
        return list(self._extension_map.keys())
    
    def is_language_supported(self, language_name: str) -> bool:
        """
        Проверка, поддерживается ли язык.
        
        Args:
            language_name: Имя языка для проверки
            
        Returns:
            bool: True, если язык поддерживается
        """
        return language_name in self._adapters
    
    def is_file_type_supported(self, file_path: str) -> bool:
        """
        Проверка, поддерживается ли тип файла.
        
        Args:
            file_path: Путь к файлу для проверки
            
        Returns:
            bool: True, если тип файла поддерживается
        """
        return self.get_adapter_for_file(file_path) is not None


# Глобальный экземпляр реестра языков
language_registry = LanguageRegistry()


def get_language_registry() -> LanguageRegistry:
    """
    Функция для получения экземпляра реестра языков.
    
    Returns:
        LanguageRegistry: Экземпляр реестра языков
    """
    return language_registry
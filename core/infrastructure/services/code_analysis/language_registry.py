"""
Реестр языковых адаптеров для мультиязычной поддержки.
ОСОБЕННОСТИ:
- Единая точка доступа ко всем поддерживаемым языкам
- Автоматическое определение языка по расширению файла
- Ленивая инициализация адаптеров
"""
import logging
from typing import Dict, List, Optional, Type
from core.infrastructure.services.code_analysis.base import LanguageSupport

logger = logging.getLogger(__name__)

class LanguageRegistry:
    """
    Реестр адаптеров для поддержки разных языков программирования.
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        registry = LanguageRegistry()
        registry.register_adapter(PythonLanguageAdapter())
        
        adapter = registry.get_adapter_for_file("core/main.py")
        ast = await adapter.parse(source_code, source_bytes)
    """
    
    def __init__(self):
        self._adapters: Dict[str, LanguageSupport] = {}
        self._extension_map: Dict[str, str] = {}  # .py -> "python"

    def register_adapter(self, adapter: LanguageSupport) -> None:
        """Регистрирует адаптер для языка с автоматической инициализацией."""
        # Автоматическая инициализация адаптера
        if hasattr(adapter, 'initialize') and callable(adapter.initialize):
            import asyncio
            if asyncio.iscoroutinefunction(adapter.initialize):
                # Для асинхронной инициализации запускаем в фоне (будет завершена при первом использовании)
                asyncio.create_task(adapter.initialize())
            else:
                adapter.initialize()
        
        self._adapters[adapter.language_name] = adapter
        for ext in adapter.file_extensions:
            self._extension_map[ext.lower()] = adapter.language_name
        logger.info(f"Зарегистрирован адаптер языка: {adapter.language_name} ({', '.join(adapter.file_extensions)})")

    def get_adapter_for_file(self, file_path: str) -> Optional[LanguageSupport]:
        """
        Возвращает адаптер для файла по расширению.
        ПАРАМЕТРЫ:
            file_path: Путь к файлу
        ВОЗВРАЩАЕТ:
            Экземпляр адаптера или None если язык не поддерживается
        """
        # Извлекаем расширение файла
        if '.' not in file_path:
            return None
        
        ext = file_path.rsplit('.', 1)[-1].lower()
        lang_name = self._extension_map.get(ext)
        
        if not lang_name:
            return None
            
        return self._adapters.get(lang_name)

    def get_supported_languages(self) -> List[str]:
        """Возвращает список поддерживаемых языков."""
        return list(self._adapters.keys())

    def is_language_supported(self, language_name: str) -> bool:
        """Проверяет, поддерживается ли язык."""
        return language_name.lower() in [lang.lower() for lang in self._adapters.keys()]

    def get_adapter_by_name(self, language_name: str) -> Optional[LanguageSupport]:
        """Возвращает адаптер по имени языка."""
        return self._adapters.get(language_name.lower())
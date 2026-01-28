"""
Базовый класс для языковых адаптеров.
ОСОБЕННОСТИ:
- Единый интерфейс для всех языков
- Минимальные требования к реализации
- Поддержка расширения специфичной функциональностью
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from core.infrastructure.services.code_analysis.base import ASTNode, LanguageSupport


class BaseLanguageAdapter(LanguageSupport, ABC):
    """
    Базовый класс для адаптеров языков программирования.
    
    ТРЕБУЕТ РЕАЛИЗАЦИИ:
    - parse(): парсинг кода в AST
    - get_outline(): построение структуры файла
    - resolve_import(): разрешение импортов
    
    ПРИНЦИПЫ:
    - Адаптер НЕ должен выполнять семантический анализ
    - Адаптер НЕ должен вызывать внешние системы (включая LLM)
    - Все операции должны быть детерминированными
    """
    
    def __init__(self):
        super().__init__()
        self.initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Инициализация адаптера (загрузка парсера, грамматик)."""
        pass
    
    async def shutdown(self) -> None:
        """Корректное завершение работы адаптера."""
        self.initialized = False
    
    def _validate_source(self, source_code: str, source_bytes: bytes) -> bool:
        """Базовая валидация исходного кода."""
        if not source_code or not source_bytes:
            return False
        if len(source_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise ValueError("Файл слишком большой для анализа")
        return True
"""
Базовые абстракции для мультиязычного анализа кода.
ОСОБЕННОСТИ:
- Языко-независимые интерфейсы (не привязаны к конкретному парсеру)
- Поддержка расширения новыми языками через адаптеры
- Чёткое разделение уровней абстракции
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from models.code_unit import Location


class ASTNode(ABC):
    """
    Абстрактный узел AST для мультиязычной поддержки.
    ПРИНЦИПЫ:
    - Все операции с узлами должны быть языко-независимыми
    - НЕТ семантического анализа (определение типов, разрешение имён)
    - НЕТ вызовов к внешним системам (включая LLM)
    """
    @property
    @abstractmethod
    def type(self) -> str:
        """Тип узла в терминах конкретного языка (например, 'class_definition')."""
        pass

    @property
    @abstractmethod
    def children(self) -> List['ASTNode']:
        """Дочерние узлы."""
        pass

    @property
    @abstractmethod
    def parent(self) -> Optional['ASTNode']:
        """Родительский узел."""
        pass

    @abstractmethod
    def get_text(self, source_bytes: bytes) -> str:
        """
        Извлекает текст узла из байтового представления исходного кода.
        ВАЖНО: Работает с байтами для корректной обработки кодировок.
        """
        pass

    @abstractmethod
    def find_children_by_type(self, node_type: str) -> List['ASTNode']:
        """Находит все дочерние узлы заданного типа."""
        pass

    @abstractmethod
    def find_first_child_by_type(self, node_type: str) -> Optional['ASTNode']:
        """Находит первый дочерний узел заданного типа."""
        pass

    @property
    @abstractmethod
    def location(self) -> Location:
        """Местоположение узла в исходном коде."""
        pass


class LanguageSupport(ABC):
    """
    Адаптер для поддержки конкретного языка программирования.
    РЕАЛИЗАЦИЯ: Каждый язык имеет свой адаптер (PythonLanguageAdapter, JavaScriptAdapter, etc.)
    
    ВАЖНО: Адаптер НЕ должен выполнять семантический анализ или вызывать внешние системы.
    """
    language_name: str
    file_extensions: List[str]

    @abstractmethod
    async def parse(self, source_code: str, source_bytes: bytes) -> ASTNode:
        """
        Парсит исходный код в абстрактное дерево.
        ВОЗВРАЩАЕТ: Корневой узел AST дерева.
        """
        pass

    @abstractmethod
    async def get_outline(self, ast: ASTNode, file_path: str) -> List[Dict[str, Any]]:
        """
        Строит структуру файла (классы, функции, методы) из AST.
        ВОЗВРАЩАЕТ: Список элементов с метаданными для навигации.
        """
        pass

    @abstractmethod
    async def resolve_import(
        self,
        import_name: str,
        current_file: str,
        project_files: List[str]
    ) -> Optional[str]:
        """
        Разрешает имя импорта в путь к файлу проекта.
        ВОЗВРАЩАЕТ: Путь к файлу или None если не найден.
        """
        pass
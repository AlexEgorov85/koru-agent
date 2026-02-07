"""
PythonLanguageAdapter - адаптер для анализа Python-кода через AST.
"""
from typing import List, Optional, Any
from domain.core.project.value_objects.code_unit import CodeUnit, CodeUnitType
from infrastructure.services.code_analysis.analysis_functions import (
    parse,
    parse_file,
    get_outline,
    extract_dependencies,
    build_code_units,
    navigate_symbols,
    resolve_import,
    SymbolType,
    Dependency
)


class PythonLanguageAdapter:
    """
    Адаптер для анализа Python-кода через AST.
    
    Реализует универсальный интерфейс для анализа Python-кода с использованием:
    - встроенного модуля ast
    - pydantic-моделей для представления данных
    - функционального подхода (чистые функции для анализа)
    """
    
    def __init__(self):
        """Инициализация PythonLanguageAdapter."""
        self.language_name = "python"
        self.supported_extensions = [".py", ".pyi"]
    
    def get_name(self) -> str:
        """
        Возвращает имя языка.
        
        Returns:
            str: Имя языка
        """
        return self.language_name
    
    def get_file_extensions(self) -> List[str]:
        """
        Возвращает список поддерживаемых расширений файлов.
        
        Returns:
            List[str]: Список расширений файлов
        """
        return self.supported_extensions
    
    def parse(self, source_code: str, source_bytes: bytes) -> Any:
        """
        Парсит исходный код в AST.
        
        Args:
            source_code: Исходный код в виде строки
            source_bytes: Исходный код в виде байтов
            
        Returns:
            AST дерево
        """
        return parse(source_code, source_bytes)
    
    def parse_file(self, path: str) -> Any:
        """
        Парсит файл в AST.
        
        Args:
            path: Путь к файлу
            
        Returns:
            AST дерево
        """
        return parse_file(path)
    
    def get_outline(self, ast_tree: Any, file_path: str) -> List[CodeUnit]:
        """
        Получает структуру файла (классы, функции и т.д.).
        
        Args:
            ast_tree: AST дерево
            file_path: Путь к файлу
            
        Returns:
            List[CodeUnit]: Список CodeUnit
        """
        return get_outline(ast_tree, file_path)
    
    def extract_dependencies(self, ast_tree: Any) -> List[Dependency]:
        """
        Извлекает зависимости из AST.
        
        Args:
            ast_tree: AST дерево
            
        Returns:
            List[Dependency]: Список Dependency
        """
        return extract_dependencies(ast_tree)
    
    def build_code_units(self, ast_tree: Any, file_path: str) -> List[CodeUnit]:
        """
        Создает CodeUnit из AST.
        
        Args:
            ast_tree: AST дерево
            file_path: Путь к файлу
            
        Returns:
            List[CodeUnit]: Список CodeUnit
        """
        return build_code_units(ast_tree, file_path)
    
    def navigate_symbols(self, code_units: List[CodeUnit], symbol_name: str) -> Optional[CodeUnit]:
        """
        Находит символ в списке CodeUnit.
        
        Args:
            code_units: Список CodeUnit
            symbol_name: Имя символа для поиска
            
        Returns:
            CodeUnit или None
        """
        return navigate_symbols(code_units, symbol_name)
    
    def resolve_import(self, import_name: str, current_file: str, project_files: List[str]) -> Optional[str]:
        """
        Разрешает импорт в путь к файлу.
        
        Args:
            import_name: Имя импорта
            current_file: Текущий файл (относительно которого разрешается импорт)
            project_files: Список файлов проекта
            
        Returns:
            Путь к файлу или None
        """
        return resolve_import(import_name, current_file, project_files)
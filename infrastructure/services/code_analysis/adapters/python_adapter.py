"""
PythonAdapter - адаптер для анализа Python-кода через AST.
"""
from typing import Any, List, Optional, Dict
import ast
import sys
from pathlib import Path

from infrastructure.services.code_analysis.language_registry import LanguageAdapter


class PythonAdapter(LanguageAdapter):
    """
    Адаптер для анализа Python-кода через AST.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (сервис адаптер)
    - Зависимости: от базового класса LanguageAdapter
    - Ответственность: анализ Python-кода через AST
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    def __init__(self):
        """Инициализация Python адаптера."""
        self.language_name = "python"
        self.supported_extensions = [".py", ".pyi"]
        self.initialized = True
    
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
        Парсит исходный Python-код в AST.
        
        Args:
            source_code: Исходный код в виде строки
            source_bytes: Исходный код в виде байтов
            
        Returns:
            Any: AST дерево
        """
        try:
            return ast.parse(source_code)
        except SyntaxError as e:
            raise ValueError(f"Ошибка синтаксиса в Python-коде: {str(e)}")
    
    def get_outline(self, ast_tree: Any, file_path: str) -> List[Dict[str, Any]]:
        """
        Получает структуру Python-файла (классы, функции и т.д.).
        
        Args:
            ast_tree: AST дерево
            file_path: Путь к файлу
            
        Returns:
            List[Dict[str, Any]]: Список элементов структуры
        """
        outline = []
        
        for node in ast.walk(ast_tree):
            item = None
            
            # Обработка функций
            if isinstance(node, ast.FunctionDef):
                item = {
                    'type': 'function',
                    'name': node.name,
                    'line_start': node.lineno,
                    'line_end': self._get_end_line(node),
                    'docstring': ast.get_docstring(node),
                    'parameters': [arg.arg for arg in node.args.args],
                    'file_path': file_path
                }
            elif isinstance(node, ast.AsyncFunctionDef):
                # Обработка асинхронных функций
                item = {
                    'type': 'async_function',
                    'name': node.name,
                    'line_start': node.lineno,
                    'line_end': self._get_end_line(node),
                    'docstring': ast.get_docstring(node),
                    'parameters': [arg.arg for arg in node.args.args],
                    'file_path': file_path
                }
            # Обработка классов
            elif isinstance(node, ast.ClassDef):
                item = {
                    'type': 'class',
                    'name': node.name,
                    'line_start': node.lineno,
                    'line_end': self._get_end_line(node),
                    'docstring': ast.get_docstring(node),
                    'bases': [self._get_base_name(base) for base in node.bases],
                    'file_path': file_path
                }
            # Обработка импортов
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    item = {
                        'type': 'import',
                        'name': alias.name,
                        'alias': alias.asname,
                        'line_start': node.lineno,
                        'line_end': node.lineno,
                        'file_path': file_path
                    }
                    outline.append(item)
                continue  # Пропускаем добавление в конце цикла
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    item = {
                        'type': 'import_from',
                        'name': f"{module}.{alias.name}",
                        'alias': alias.asname,
                        'line_start': node.lineno,
                        'line_end': node.lineno,
                        'module': module,
                        'file_path': file_path
                    }
                    outline.append(item)
                continue  # Прпускаем добавление в конце цикла
            
            # Добавляем элемент в структуру
            if item:
                outline.append(item)
        
        return outline
    
    def resolve_import(self, import_name: str, current_file: str, project_files: List[str]) -> Optional[str]:
        """
        Разрешает импорт Python-модуля в путь к файлу.
        
        Args:
            import_name: Имя импортируемого модуля
            current_file: Текущий файл (относительно которого разрешается импорт)
            project_files: Список файлов проекта
            
        Returns:
            Optional[str]: Путь к файлу или None, если не найден
        """
        # Получаем директорию текущего файла
        current_dir = Path(current_file).parent
        
        # Пытаемся разрешить импорт как абсолютный или относительный
        # Сначала проверяем относительные импорты (начинаются с точки)
        if import_name.startswith('.'):
            # Относительный импорт
            return self._resolve_relative_import(import_name, current_dir, project_files)
        else:
            # Абсолютный импорт
            return self._resolve_absolute_import(import_name, project_files)
    
    def _get_end_line(self, node: ast.AST) -> int:
        """
        Получает номер последней строки узла.
        
        Args:
            node: Узел AST
            
        Returns:
            int: Номер последней строки
        """
        if hasattr(node, 'end_lineno') and node.end_lineno is not None:
            return node.end_lineno
        else:
            # Если end_lineno недоступен, возвращаем lineno
            return node.lineno
    
    def _get_base_name(self, base_node: ast.AST) -> str:
        """
        Получает имя базового класса из узла AST.
        
        Args:
            base_node: Узел AST, представляющий базовый класс
            
        Returns:
            str: Имя базового класса
        """
        if isinstance(base_node, ast.Name):
            return base_node.id
        elif isinstance(base_node, ast.Attribute):
            return f"{self._get_base_name(base_node.value)}.{base_node.attr}"
        else:
            return str(base_node)
    
    def _resolve_relative_import(self, import_name: str, current_dir: Path, project_files: List[str]) -> Optional[str]:
        """
        Разрешает относительный импорт.
        
        Args:
            import_name: Имя импорта (начинается с точки)
            current_dir: Текущая директория
            project_files: Список файлов проекта
            
        Returns:
            Optional[str]: Путь к файлу или None
        """
        # Подсчитываем количество точек в начале
        level = 0
        for char in import_name:
            if char == '.':
                level += 1
            else:
                break
        
        # Получаем оставшуюся часть имени
        remaining_name = import_name[level:]
        
        # Поднимаемся на уровень выше столько раз, сколько точек
        target_dir = current_dir
        for _ in range(level - 1):  # -1 потому что одна точка означает текущую директорию
            target_dir = target_dir.parent
        
        # Преобразуем имя модуля в путь
        module_parts = remaining_name.split('.')
        module_path = target_dir.joinpath(*module_parts[:-1]).joinpath(module_parts[-1] + '.py')
        
        # Проверяем, существует ли такой файл
        if str(module_path) in project_files:
            return str(module_path)
        
        # Также проверяем как пакет (__init__.py)
        package_path = target_dir.joinpath(*module_parts).joinpath('__init__.py')
        if str(package_path) in project_files:
            return str(package_path)
        
        return None
    
    def _resolve_absolute_import(self, import_name: str, project_files: List[str]) -> Optional[str]:
        """
        Разрешает абсолютный импорт.
        
        Args:
            import_name: Имя импорта
            project_files: Список файлов проекта
            
        Returns:
            Optional[str]: Путь к файлу или None
        """
        # Разбиваем имя импорта на части
        module_parts = import_name.split('.')
        
        # Проверяем каждый файл проекта
        for file_path in project_files:
            path_obj = Path(file_path)
            
            # Проверяем соответствие пути имени модуля
            # Например, для import_name = "package.subpackage.module"
            # Путь должен заканчиваться на package/subpackage/module.py или package/subpackage/module/__init__.py
            if self._matches_module_path(path_obj, module_parts):
                return file_path
        
        return None
    
    def _matches_module_path(self, file_path: Path, module_parts: List[str]) -> bool:
        """
        Проверяет, соответствует ли путь файлу имени модуля.
        
        Args:
            file_path: Путь к файлу
            module_parts: Части имени модуля
            
        Returns:
            bool: True, если путь соответствует имени модуля
        """
        # Получаем части пути (без расширения для .py файлов)
        path_parts = list(file_path.parts)
        
        # Если файл заканчивается на .py, убираем расширение из последней части
        if path_parts[-1].endswith('.py'):
            last_part = path_parts[-1][:-3]  # Убираем '.py'
            path_parts = path_parts[:-1] + [last_part]
        # Если файл - это __init__.py, значит это пакет
        elif path_parts[-1] == '__init__.py':
            last_part = path_parts[-2]  # Берем предпоследнюю часть (имя пакета)
            path_parts = path_parts[:-2] + [last_part]
        
        # Сравниваем последние части пути с частями имени модуля
        if len(path_parts) >= len(module_parts):
            path_suffix = path_parts[-len(module_parts):]
            return path_suffix == module_parts
        
        return False
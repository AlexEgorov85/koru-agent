"""
ImportResolver - сервис для разрешения импортов между файлами.
"""
from typing import Dict, List, Optional
from pathlib import Path


class ImportResolver:
    """
    Сервис для разрешения импортов между файлами.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (сервис)
    - Ответственность: разрешение импортов между файлами проекта
    - Принципы: соблюдение единой ответственности (S в SOLID)
    """
    
    def __init__(self):
        """Инициализация резольвера импортов."""
        self._cache: Dict[str, Dict[str, str]] = {}  # кэш разрешенных импортов
    
    def resolve_import(self, import_statement: str, source_file: str, project_files: List[str]) -> Optional[str]:
        """
        Разрешает импорт в путь к файлу.
        
        Args:
            import_statement: Оператор импорта (например, 'from mymodule import MyClass')
            source_file: Файл, из которого осуществляется импорт
            project_files: Список всех файлов проекта
            
        Returns:
            Optional[str]: Путь к файлу, в который импортируется, или None если не найден
        """
        # Очищаем кэш, если он становится слишком большим
        if len(self._cache) > 1000:
            self._cache.clear()
        
        # Проверяем кэш
        cache_key = f"{import_statement}:{source_file}"
        if cache_key in self._cache:
            return self._cache[cache_key].get(import_statement)
        
        # Определяем язык по расширению файла
        source_path = Path(source_file)
        language = self._detect_language(source_path.suffix)
        
        # Разрешаем импорт в зависимости от языка
        resolved_path = None
        if language == "python":
            resolved_path = self._resolve_python_import(import_statement, source_file, project_files)
        elif language in ["javascript", "typescript"]:
            resolved_path = self._resolve_js_ts_import(import_statement, source_file, project_files)
        
        # Кэшируем результат
        if cache_key not in self._cache:
            self._cache[cache_key] = {}
        self._cache[cache_key][import_statement] = resolved_path
        
        return resolved_path
    
    def _detect_language(self, file_extension: str) -> str:
        """
        Определяет язык программирования по расширению файла.
        
        Args:
            file_extension: Расширение файла (например, '.py', '.js')
            
        Returns:
            str: Название языка
        """
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.pyi': 'python'
        }
        
        return language_map.get(file_extension.lower(), 'unknown')
    
    def _resolve_python_import(self, import_statement: str, source_file: str, project_files: List[str]) -> Optional[str]:
        """
        Разрешает Python-импорт в путь к файлу.
        
        Args:
            import_statement: Оператор импорта
            source_file: Файл, из которого осуществляется импорт
            project_files: Список всех файлов проекта
            
        Returns:
            Optional[str]: Путь к файлу или None
        """
        # Удаляем ведущие и завершающие пробелы
        import_stmt = import_statement.strip()
        
        # Определяем тип импорта
        if import_stmt.startswith('import '):
            # Простой импорт: import module
            module_name = import_stmt[7:].split()[0]  # после 'import '
        elif import_stmt.startswith('from '):
            # Импорт из модуля: from module import ...
            parts = import_stmt[5:].split(' import ')  # после 'from '
            module_name = parts[0]
        else:
            # Неизвестный формат импорта
            return None
        
        # Убираем алиасы (например, 'import numpy as np')
        module_name = module_name.split(' as ')[0].split('.')[0]
        
        # Проверяем, является ли это относительным импортом
        if import_stmt.startswith('from .') or import_stmt.startswith('import .'):
            return self._resolve_relative_python_import(module_name, import_stmt, source_file, project_files)
        
        # Для абсолютных импортов ищем файлы с подходящим именем
        return self._find_module_file(module_name, project_files)
    
    def _resolve_relative_python_import(self, module_name: str, import_statement: str, source_file: str, project_files: List[str]) -> Optional[str]:
        """
        Разрешает относительный Python-импорт.
        
        Args:
            module_name: Имя модуля
            import_statement: Оператор импорта
            source_file: Файл, из которого осуществляется импорт
            project_files: Список всех файлов проекта
            
        Returns:
            Optional[str]: Путь к файлу или None
        """
        source_path = Path(source_file)
        source_dir = source_path.parent
        
        # Подсчитываем количество точек для определения уровня
        level = 0
        for char in import_statement:
            if char == '.':
                level += 1
            else:
                break
        
        # Поднимаемся на уровень выше столько раз, сколько точек (за вычетом 1)
        target_dir = source_dir
        for _ in range(level - 1):
            target_dir = target_dir.parent
        
        # Пытаемся найти файл по относительному пути
        # Если module_name состоит из нескольких частей (через точку), обрабатываем как путь
        module_parts = module_name.split('.')
        
        # Сначала пытаемся найти как файл
        potential_file = target_dir.joinpath(*module_parts[:-1]).joinpath(module_parts[-1] + '.py')
        if str(potential_file) in project_files:
            return str(potential_file)
        
        # Затем как пакет (__init__.py)
        potential_package = target_dir.joinpath(*module_parts).joinpath('__init__.py')
        if str(potential_package) in project_files:
            return str(potential_package)
        
        return None
    
    def _find_module_file(self, module_name: str, project_files: List[str]) -> Optional[str]:
        """
        Находит файл модуля по его имени.
        
        Args:
            module_name: Имя модуля
            project_files: Список файлов проекта
            
        Returns:
            Optional[str]: Путь к файлу или None
        """
        # Пытаемся найти файл по имени модуля
        module_parts = module_name.split('.')
        
        # Проверяем каждый файл проекта
        for file_path in project_files:
            path_obj = Path(file_path)
            
            # Проверяем, соответствует ли путь имени модуля
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
    
    def _resolve_js_ts_import(self, import_statement: str, source_file: str, project_files: List[str]) -> Optional[str]:
        """
        Разрешает JavaScript/TypeScript-импорт в путь к файлу.
        
        Args:
            import_statement: Оператор импорта
            source_file: Файл, из которого осуществляется импорт
            project_files: Список всех файлов проекта
            
        Returns:
            Optional[str]: Путь к файлу или None
        """
        # Извлекаем путь из оператора импорта
        # Примеры: import { something } from './path/to/file'; import something from '../file'
        import_path = self._extract_js_ts_import_path(import_statement)
        if not import_path:
            return None
        
        # Определяем, является ли это относительным импортом
        if import_path.startswith('./') or import_path.startswith('../'):
            # Относительный импорт
            source_dir = Path(source_file).parent
            target_path = source_dir.joinpath(import_path).resolve()
            
            # Проверяем, существует ли файл с указанным расширением
            for ext in ['.js', '.ts', '.jsx', '.tsx']:
                full_path = str(target_path.with_suffix(ext))
                if full_path in project_files:
                    return full_path
            
            # Также проверяем как директорию с index.js/ts
            for index_file in ['index.js', 'index.ts', 'index.jsx', 'index.tsx']:
                full_path = str(target_path.joinpath(index_file))
                if full_path in project_files:
                    return full_path
        else:
            # Абсолютный импорт или импорт из node_modules (в проекте мы рассматриваем только внутренние файлы)
            # Проверяем среди файлов проекта
            for file_path in project_files:
                if import_path in file_path or file_path.endswith(import_path + '.js') or file_path.endswith(import_path + '.ts'):
                    return file_path
        
        return None
    
    def _extract_js_ts_import_path(self, import_statement: str) -> Optional[str]:
        """
        Извлекает путь из JS/TS оператора импорта.
        
        Args:
            import_statement: Оператор импорта
            
        Returns:
            Optional[str]: Путь или None
        """
        # Простая реализация - находим путь в кавычках
        import_stmt = import_statement.strip()
        
        # Ищем путь в одинарных или двойных кавычках
        start_quote = -1
        end_quote = -1
        quote_char = None
        
        for i, char in enumerate(import_stmt):
            if char in ['"', "'"]:
                if start_quote == -1:
                    start_quote = i
                    quote_char = char
                elif char == quote_char:
                    end_quote = i
                    break
        
        if start_quote != -1 and end_quote != -1:
            import_path = import_stmt[start_quote+1:end_quote]
            return import_path
        
        return None
    
    def get_all_imports(self, source_file: str, project_files: List[str]) -> List[Dict[str, str]]:
        """
        Получает все импорты из файла.
        
        Args:
            source_file: Исходный файл
            project_files: Список всех файлов проекта
            
        Returns:
            List[Dict[str, str]]: Список словарей с информацией об импортах
        """
        imports = []
        
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            for line_num, line in enumerate(lines, start=1):
                stripped_line = line.strip()
                
                # Проверяем, является ли строка импортом
                if stripped_line.startswith(('import ', 'from ')):
                    resolved_path = self.resolve_import(stripped_line, source_file, project_files)
                    
                    import_info = {
                        'statement': stripped_line,
                        'resolved_path': resolved_path,
                        'line_number': line_num,
                        'source_file': source_file
                    }
                    imports.append(import_info)
        except Exception:
            # Если не можем прочитать файл, возвращаем пустой список
            pass
        
        return imports
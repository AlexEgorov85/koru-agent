"""Компонент для построения структуры проекта.
Отвечает за сборку иерархической структуры проекта из отдельных файлов и CodeUnit.
Выполняет анализ зависимостей и поиск точек входа.
Особенности:
1. Иерархическое представление директорий
2. Анализ зависимостей между файлами
3. Автоматическое определение точек входа
4. Кэширование для производительности
Примеры использования:
1. Построение полной структуры проекта:
```python
builder = ProjectStructureBuilder(project_map_skill)
project_structure = builder.build_project_structure(
root_dir=".",
files_info=[{'path': 'core/main.py', 'size': 1000, 'type': 'file'}],
code_units_by_file={
'core/main.py': [code_unit1, code_unit2]
}
)
```
2. Анализ зависимостей для конкретного файла:
```python
dependencies = builder.analyze_file_dependencies(
file_path="core/main.py",
code_units=[code_unit1, code_unit2]
)
```
3. Поиск точек входа:
```python
entry_points = builder.find_entry_points(code_units_by_file)
```
Компонент интегрируется с ProjectMapSkill и использует его для доступа к инструментам и конфигурации.
"""
from typing import Dict, List, Any, Optional
from core.skills.project_map.components.dependency_analyzer import DependencyAnalyzer
from core.skills.project_map.models.code_unit import CodeUnit
from core.skills.project_map.models.project_map import (
    ProjectStructure, FileInfo, DirectoryInfo,
    EntryPointInfo, FileDependency
)
import os
from pathlib import Path

class ProjectStructureBuilder:
    """Компонент для построения структуры проекта.
    Основная ответственность - сборка полной карты проекта из отдельных компонентов.
    Выполняет несколько ключевых задач:
    1. Построение файловой структуры
    2. Построение иерархической структуры директорий
    3. Анализ зависимостей между файлами
    4. Поиск точек входа в проекте
    Атрибуты:
    - skill_context: контекст навыка для доступа к инструментам и конфигурации
    - dependency_analyzer: анализатор зависимостей
    Пример:
    ```python
    builder = ProjectStructureBuilder(project_map_skill)
    project_structure = builder.build_project_structure(
        root_dir=".",
        files_info=file_list,
        code_units_by_file=code_units_by_file
    )
    ```
    """
    
    def __init__(self, skill_context):
        self.skill_context = skill_context
        self.dependency_analyzer = DependencyAnalyzer(skill_context)  # Используем DependencyAnalyzer
    
    def build_project_structure(self, root_dir: str, files_info: List[Dict[str, Any]],
                               code_units_by_file: Dict[str, List[CodeUnit]]) -> ProjectStructure:
        """
        Построение полной структуры проекта.
        Args:
            root_dir: корневая директория проекта
            files_info: список информации о файлах
            code_units_by_file: словарь CodeUnit по файлам
        Returns:
            ProjectStructure: построенная структура проекта
        """
        project = ProjectStructure()
        project.root_dir = root_dir
        
        # 1. Построение файловой структуры
        self._build_file_structure(project, files_info, code_units_by_file)
        
        # 2. Построение иерархической структуры директорий
        self._build_directory_structure(project, files_info)
        
        # 3. Анализ зависимостей между файлами
        self._analyze_file_dependencies(project, code_units_by_file)
        
        # 4. Поиск точек входа
        self._find_entry_points(project, code_units_by_file)
        
        # 5. Обновление статистики
        project.total_files = len(project.files)
        project.total_code_units = sum(len(units) for units in code_units_by_file.values())
        
        # 6. Добавление CodeUnit в структуру
        for file_path, code_units in code_units_by_file.items():
            for unit in code_units:
                project.code_units[unit.id] = unit
        
        return project
    
    def _build_file_structure(self, project: ProjectStructure, files_info: List[Dict[str, Any]],
                            code_units_by_file: Dict[str, List[CodeUnit]]):
        """Построение файловой структуры с полным анализом imports, exports и dependencies."""
        # Сбор всех путей файлов в проекте для анализа зависимостей
        project_file_paths = {file_info['path'] for file_info in files_info if file_info.get('type') == 'file'}
        
        for file_info in files_info:
            if file_info.get('type') != 'file':
                continue
                
            file_path = file_info['path']
            file_size = file_info.get('size', 0)
            last_modified = file_info.get('last_modified', 0)
            
            # Создание FileInfo
            file_record = FileInfo(file_path, file_size, last_modified)
            
            # Добавление единиц кода
            code_units = code_units_by_file.get(file_path, [])
            file_record.code_unit_ids = [unit.id for unit in code_units]
            
            # Инициализация списков
            imports = []
            exports = []
            dependencies = set()  # Используем set для избежания дубликатов
            
            # Анализ импортов и экспорта
            for unit in code_units:
                # Анализ импортов
                if unit.type.value == 'import' and hasattr(unit, 'metadata'):
                    # Добавляем полную информацию об импорте
                    import_info = {
                        'name': unit.name,
                        'module': unit.metadata.get('module', ''),
                        'alias': unit.metadata.get('alias'),
                        'is_relative': unit.metadata.get('is_relative', False),
                        'import_type': unit.metadata.get('import_type', 'import'),
                        'original_text': unit.metadata.get('original_text', '')
                    }
                    imports.append(import_info)
                    
                    # Анализ зависимостей: проверяем, является ли импорт частью нашего проекта
                    module_name = unit.metadata.get('module', '')
                    if module_name:
                        # Преобразуем имя модуля в путь файла
                        module_path = self._module_name_to_file_path(module_name, file_path)
                        if module_path in project_file_paths:
                            dependencies.add(module_path)
                
                # Анализ экспорта (символы верхнего уровня)
                elif unit.type.value in ['class', 'function', 'variable']:
                    # Экспортируемые символы - те, что определены на верхнем уровне
                    if not unit.parent_id or unit.parent_id.startswith('module_'):
                        export_info = {
                            'name': unit.name,
                            'type': unit.type.value,
                            'line': unit.location.start_line,
                            'signature': unit.get_signature() if hasattr(unit, 'get_signature') else unit.name
                        }
                        exports.append(export_info)
            
            # Добавляем зависимости от родительских модулей
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                init_file_path = os.path.join(parent_dir, '__init__.py')
                if init_file_path in project_file_paths:
                    dependencies.add(init_file_path)
            
            # Записываем информацию в FileInfo
            file_record.imports = imports
            file_record.exports = exports
            file_record.dependencies = list(dependencies)
            
            project.files[file_path] = file_record
    
    def _module_name_to_file_path(self, module_name: str, current_file_path: str) -> str:
        """Преобразует имя модуля в путь файла относительно корня проекта."""
        # Убираем относительные импорты (начинающиеся с точки)
        while module_name.startswith('.'):
            module_name = module_name[1:]
            current_dir = os.path.dirname(current_file_path)
            current_file_path = os.path.join(current_dir, '__init__.py')
        
        # Заменяем точки на разделители пути
        file_path = module_name.replace('.', os.sep) + '.py'
        
        # Проверяем различные варианты пути
        possible_paths = [
            file_path,  # Прямой путь
            os.path.join(os.path.dirname(current_file_path), file_path),  # Относительно текущего файла
            os.path.join('core', file_path) if not file_path.startswith('core') else file_path  # Относительно core
        ]
        
        for path in possible_paths:
            normalized_path = os.path.normpath(path)
            if os.path.exists(normalized_path):
                return normalized_path
        
        return file_path  # Возвращаем исходный путь, если ничего не найдено
    
    def _build_directory_structure(self, project: ProjectStructure, files_info: List[Dict[str, Any]]):
        """Построение иерархической структуры директорий."""
        directories = {}
        for file_info in files_info:
            if file_info.get('type') != 'file':
                continue
                
            file_path = file_info['path']
            path_parts = Path(file_path).parts
            
            # Создание директорий для всех уровней
            current_path = ""
            file_size = file_info.get('size', 0)
            
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:  # Последний элемент - файл
                    break
                    
                current_path = f"{current_path}/{part}" if current_path else part
                
                if current_path not in directories:
                    dir_info = DirectoryInfo(current_path, part)
                    directories[current_path] = dir_info
                
                # Обновление информации о директории
                dir_info = directories[current_path]
                if i == len(path_parts) - 2:  # Родительская директория для файла
                    dir_info.files.append(file_path)
                    dir_info.total_files += 1
                    dir_info.total_size += file_size
                else:  # Промежуточная директория
                    next_dir = f"{current_path}/{path_parts[i+1]}"
                    if next_dir not in dir_info.subdirectories:
                        dir_info.subdirectories.append(next_dir)
        
        project.directory_tree = directories
    
    def _analyze_file_dependencies(self, project: ProjectStructure, code_units_by_file: Dict[str, List[CodeUnit]]):
        """Анализ зависимостей между файлами."""
        # Используем DependencyAnalyzer для анализа зависимостей
        project_dependencies = self.dependency_analyzer.analyze_project_dependencies(project)
        project.file_dependencies = project_dependencies
    
    def _find_entry_points(self, project: ProjectStructure, code_units_by_file: Dict[str, List[CodeUnit]]):
        """Поиск точек входа в проекте."""
        entry_points = []
        for file_path, code_units in code_units_by_file.items():
            # Проверка корневых файлов для main функций
            is_root_file = len(file_path.split('/')) <= 2 or 'main' in file_path.lower()
            
            for unit in code_units:
                # Поиск main функций в корневых файлах
                if is_root_file and unit.type.value == 'function' and unit.name == 'main':
                    entry_points.append(EntryPointInfo(
                        name="main",
                        file_path=file_path,
                        line=unit.location.start_line,
                        entry_type="main"
                    ))
                
                # Поиск классов с определенными паттернами имен
                elif unit.type.value == 'class':
                    class_name_lower = unit.name.lower()
                    if ('app' in class_name_lower or 'service' in class_name_lower or
                        'handler' in class_name_lower or 'manager' in class_name_lower):
                        entry_points.append(EntryPointInfo(
                            name=unit.name,
                            file_path=file_path,
                            line=unit.location.start_line,
                            entry_type="class"
                        ))
                
                # Поиск FastAPI/Flask приложений
                elif unit.type.value == 'variable':
                    if ('app' in unit.name.lower() and 
                        ('fastapi' in str(unit.metadata).lower() or 
                         'flask' in str(unit.metadata).lower() or 
                         'application' in str(unit.metadata).lower())):
                        entry_points.append(EntryPointInfo(
                            name=unit.name,
                            file_path=file_path,
                            line=unit.location.start_line,
                            entry_type="api"
                        ))
            
            # Проверка __main__.py файла
            if '__main__.py' in file_path.lower():
                for unit in code_units:
                    if unit.type.value == 'function':
                        entry_points.append(EntryPointInfo(
                            name=unit.name,
                            file_path=file_path,
                            line=unit.location.start_line,
                            entry_type="main"
                        ))
        
        # Удаление дубликатов
        unique_entry_points = []
        seen = set()
        for ep in entry_points:
            key = (ep.name, ep.file_path, ep.line)
            if key not in seen:
                seen.add(key)
                unique_entry_points.append(ep)
        
        project.entry_points = unique_entry_points
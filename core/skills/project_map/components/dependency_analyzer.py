"""Компонент для анализа зависимостей между файлами и единицами кода.

Отвечает за анализ и построение графа зависимостей в проекте:
- Зависимости между файлами через импорты
- Зависимости между классами через наследование
- Зависимости между функциями через вызовы
- Циклические зависимости

Особенности:
1. Многоуровневый анализ зависимостей
2. Обнаружение циклических зависимостей
3. Расчет метрик связанности
4. Визуализация для отладки

Примеры использования:

1. Анализ зависимостей для файла:
```python
analyzer = DependencyAnalyzer(project_map_skill)
dependencies = analyzer.analyze_file_dependencies(
    file_path="core/skills/project_map/skill.py",
    code_units=file_code_units
)
```

2. Анализ зависимостей для проекта:
```python
project_deps = analyzer.analyze_project_dependencies(project_structure)
```

3. Обнаружение циклических зависимостей:
```python
cycles = analyzer.find_cyclic_dependencies(project_structure)
```

4. Расчет метрик связанности:
```python
metrics = analyzer.calculate_coupling_metrics(project_structure)
```

Компонент интегрируется с ProjectMapSkill и использует его для доступа к инструментам и конфигурации.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from core.skills.project_map.models.code_unit import CodeUnit
from core.skills.project_map.models.project_map import ProjectStructure, FileDependency
import os
from pathlib import Path

class DependencyAnalyzer:
    """Компонент для анализа зависимостей.
    
    Основная ответственность - анализ и построение графа зависимостей
    между различными элементами проекта.
    
    Атрибуты:
    - skill_context: контекст навыка для доступа к инструментам и логированию
    
    Пример:
    ```python
    analyzer = DependencyAnalyzer(project_map_skill)
    dependencies = analyzer.analyze_file_dependencies(file_path, code_units)
    ```
    """
    
    def __init__(self, skill_context):
        self.skill_context = skill_context
    
    def analyze_file_dependencies(self, file_path: str, code_units: List[CodeUnit], 
                                project_files: List[str]) -> List[FileDependency]:
        """Анализ зависимостей для конкретного файла.
        
        Args:
            file_path: путь к анализируемому файлу
            code_units: список CodeUnit из файла
            project_files: список всех файлов проекта для разрешения путей
        
        Returns:
            List[FileDependency]: список зависимостей файла
        
        Анализирует:
        1. Импорты (основной источник зависимостей)
        2. Наследование классов
        3. Типы параметров и возвращаемых значений
        
        Пример:
        ```python
        deps = analyzer.analyze_file_dependencies(
            "core/skills/project_map/skill.py",
            file_code_units,
            all_project_files
        )
        ```
        """
        dependencies = []
        
        # 1. Анализ импортов
        import_deps = self._analyze_import_dependencies(file_path, code_units, project_files)
        dependencies.extend(import_deps)
        
        # 2. Анализ наследования классов
        inheritance_deps = self._analyze_inheritance_dependencies(file_path, code_units, project_files)
        dependencies.extend(inheritance_deps)
        
        # 3. Анализ типов (параметры, возвращаемые значения)
        type_deps = self._analyze_type_dependencies(file_path, code_units, project_files)
        dependencies.extend(type_deps)
        
        # 4. Удаление дубликатов
        return self._remove_duplicate_dependencies(dependencies)
    
    def analyze_project_dependencies(self, project_structure: ProjectStructure) -> Dict[str, List[FileDependency]]:
        """Анализ зависимостей для всего проекта.
        
        Args:
            project_structure: структура проекта
        
        Returns:
            Dict[str, List[FileDependency]]: зависимости для всех файлов
        
        Пример:
        ```python
        project_deps = analyzer.analyze_project_dependencies(project_structure)
        ```
        """
        project_dependencies = {}
        
        for file_path, file_info in project_structure.files.items():
            code_units = project_structure.get_code_units_by_file(file_path)
            deps = self.analyze_file_dependencies(
                file_path,
                code_units,
                list(project_structure.files.keys())
            )
            project_dependencies[file_path] = deps
        
        return project_dependencies
    
    def find_cyclic_dependencies(self, project_structure: ProjectStructure) -> List[List[str]]:
        """Обнаружение циклических зависимостей в проекте.
        
        Args:
            project_structure: структура проекта
        
        Returns:
            List[List[str]]: список циклов, каждый цикл - список файлов
        
        Использует алгоритм DFS для обнаружения циклов в графе зависимостей.
        
        Пример:
        ```python
        cycles = analyzer.find_cyclic_dependencies(project_structure)
        for cycle in cycles:
            print(f"Циклическая зависимость: {' -> '.join(cycle)}")
        ```
        """
        # Построение графа зависимостей
        graph = {}
        for file_path, deps in project_structure.file_dependencies.items():
            graph[file_path] = [dep.target_file for dep in deps]
        
        # Алгоритм DFS для обнаружения циклов
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node, path):
            if node not in graph:
                return
            
            if node in rec_stack:
                # Найден цикл
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                dfs(neighbor, path.copy())
            
            rec_stack.remove(node)
        
        for file_path in project_structure.files.keys():
            dfs(file_path, [])
        
        return cycles
    
    def calculate_coupling_metrics(self, project_structure: ProjectStructure) -> Dict[str, Any]:
        """Расчет метрик связанности проекта.
        
        Args:
            project_structure: структура проекта
        
        Returns:
            Dict[str, Any]: словарь с метриками:
                - afferent_coupling: количество входящих зависимостей
                - efferent_coupling: количество исходящих зависимостей
                - instability: коэффициент нестабильности (0-1)
                - abstractness: степень абстракции
        
        Пример:
        ```python
        metrics = analyzer.calculate_coupling_metrics(project_structure)
        print(f"Средняя нестабильность: {metrics['avg_instability']:.2f}")
        ```
        """
        metrics = {
            'afferent_coupling': {},
            'efferent_coupling': {},
            'instability': {},
            'abstractness': {},
            'total_files': len(project_structure.files),
            'avg_instability': 0.0,
            'avg_abstractness': 0.0
        }
        
        total_instability = 0.0
        total_abstractness = 0.0
        
        for file_path, file_info in project_structure.files.items():
            # Afferent coupling (входящие зависимости)
            afferent = sum(1 for deps in project_structure.file_dependencies.values() 
                         for dep in deps if dep.target_file == file_path)
            
            # Efferent coupling (исходящие зависимости)
            efferent = len(project_structure.file_dependencies.get(file_path, []))
            
            # Instability = efferent / (afferent + efferent)
            total_deps = afferent + efferent
            instability = efferent / total_deps if total_deps > 0 else 0.0
            
            # Abstractness - отношение количества абстрактных классов/интерфейсов
            code_units = project_structure.get_code_units_by_file(file_path)
            abstract_units = [u for u in code_units if self._is_abstract_unit(u)]
            abstractness = len(abstract_units) / len(code_units) if code_units else 0.0
            
            metrics['afferent_coupling'][file_path] = afferent
            metrics['efferent_coupling'][file_path] = efferent
            metrics['instability'][file_path] = instability
            metrics['abstractness'][file_path] = abstractness
            
            total_instability += instability
            total_abstractness += abstractness
        
        if project_structure.files:
            metrics['avg_instability'] = total_instability / len(project_structure.files)
            metrics['avg_abstractness'] = total_abstractness / len(project_structure.files)
        
        return metrics
    
    def _analyze_import_dependencies(self, file_path: str, code_units: List[CodeUnit], 
                                    project_files: List[str]) -> List[FileDependency]:
        """Анализ зависимостей через импорты."""
        dependencies = []
        
        for unit in code_units:
            if unit.type.value == 'import':
                # Разрешение пути импорта
                target_files = self._resolve_import_targets(unit, file_path, project_files)
                for target_file in target_files:
                    if target_file and target_file != file_path:
                        dependencies.append(FileDependency(
                            source_file=file_path,
                            target_file=target_file,
                            dependency_type="import"
                        ))
        
        return dependencies
    
    def _analyze_inheritance_dependencies(self, file_path: str, code_units: List[CodeUnit], 
                                         project_files: List[str]) -> List[FileDependency]:
        """Анализ зависимостей через наследование классов."""
        dependencies = []
        
        for unit in code_units:
            if unit.type.value == 'class':
                bases = unit.metadata.get('bases', [])
                for base in bases:
                    # Поиск файла, содержащего базовый класс
                    target_file = self._find_class_file(base, file_path, project_files)
                    if target_file and target_file != file_path:
                        dependencies.append(FileDependency(
                            source_file=file_path,
                            target_file=target_file,
                            dependency_type="inheritance"
                        ))
        
        return dependencies
    
    def _analyze_type_dependencies(self, file_path: str, code_units: List[CodeUnit], 
                                  project_files: List[str]) -> List[FileDependency]:
        """Анализ зависимостей через типы параметров и возвращаемых значений."""
        dependencies = []
        
        for unit in code_units:
            if unit.type.value in ['function', 'method']:
                # Анализ типов параметров
                params = unit.metadata.get('parameters', [])
                for param in params:
                    type_annotation = param.get('type_annotation')
                    if type_annotation:
                        target_file = self._find_type_file(type_annotation, file_path, project_files)
                        if target_file and target_file != file_path:
                            dependencies.append(FileDependency(
                                source_file=file_path,
                                target_file=target_file,
                                dependency_type="type_annotation"
                            ))
                
                # Анализ типа возвращаемого значения
                return_type = unit.metadata.get('return_type')
                if return_type:
                    target_file = self._find_type_file(return_type, file_path, project_files)
                    if target_file and target_file != file_path:
                        dependencies.append(FileDependency(
                            source_file=file_path,
                            target_file=target_file,
                            dependency_type="return_type"
                        ))
        
        return dependencies
    
    def _resolve_import_targets(self, import_unit: CodeUnit, current_file: str, project_files: List[str]) -> List[str]:
        """Разрешение целевых файлов для импорта."""
        targets = []
        
        if not import_unit.metadata:
            return targets
        
        all_imports = import_unit.metadata.get('all_imports', [])
        if not all_imports:
            return targets
        
        current_dir = os.path.dirname(current_file)
        
        for imp in all_imports:
            module = imp.get('module', imp.get('name', ''))
            if not module:
                continue
            
            # Обработка относительных импортов
            if imp.get('is_relative') or module.startswith('.'):
                target = self._resolve_relative_import(module, current_dir, project_files)
                if target:
                    targets.append(target)
            else:
                # Обработка абсолютных импортов
                target = self._resolve_absolute_import(module, project_files)
                if target:
                    targets.append(target)
        
        return targets
    
    def _resolve_relative_import(self, module: str, current_dir: str, project_files: List[str]) -> Optional[str]:
        """Разрешение относительного импорта."""
        if not module.startswith('.'):
            return None
        
        # Подсчет уровней вверх
        level = 0
        for char in module:
            if char == '.':
                level += 1
            else:
                break
        
        # Очистка от точек
        module_name = module[level:]
        if not module_name:
            return None
        
        # Построение пути
        if level > 1:
            # Подъем на уровень вверх
            parent_dir = current_dir
            for _ in range(level - 1):
                parent_dir = os.path.dirname(parent_dir)
                if not parent_dir:
                    return None
            target_path = os.path.join(parent_dir, module_name.replace('.', '/') + ".py")
        else:
            # Текущая директория
            target_path = os.path.join(current_dir, module_name.replace('.', '/') + ".py")
        
        # Нормализация пути
        target_path = os.path.normpath(target_path)
        
        # Поиск в проекте
        for file_path in project_files:
            if os.path.normpath(file_path) == target_path:
                return file_path
        
        return None
    
    def _resolve_absolute_import(self, module: str, project_files: List[str]) -> Optional[str]:
        """Разрешение абсолютного импорта."""
        # Замена точек на разделители директорий
        module_path = module.replace('.', '/') + ".py"
        
        # Поиск в известных файлах проекта
        for file_path in project_files:
            if file_path.endswith(module_path) or file_path.endswith(os.path.join('core', module_path)):
                return file_path
        
        return None
    
    def _find_class_file(self, class_name: str, current_file: str, project_files: List[str]) -> Optional[str]:
        """Поиск файла, содержащего определение класса."""
        # Упрощенная реализация - будем искать по имени файла
        for file_path in project_files:
            file_name = os.path.basename(file_path).replace('.py', '')
            if class_name.lower() in file_name.lower():
                return file_path
        
        return None
    
    def _find_type_file(self, type_name: str, current_file: str, project_files: List[str]) -> Optional[str]:
        """Поиск файла, содержащего определение типа."""
        return self._find_class_file(type_name, current_file, project_files)
    
    def _is_abstract_unit(self, code_unit: CodeUnit) -> bool:
        """Проверка, является ли единица кода абстрактной."""
        if code_unit.type.value == 'class':
            # Класс считается абстрактным, если:
            # 1. Имеет декоратор @abstractmethod
            # 2. Имеет наследование от ABC
            # 3. Имеет абстрактные методы
            decorators = code_unit.metadata.get('decorators', [])
            bases = code_unit.metadata.get('bases', [])
            
            if any('@abstractmethod' in d for d in decorators):
                return True
            
            if any('ABC' in base for base in bases):
                return True
            
            # Проверка на наличие абстрактных методов
            # (в данном упрощенном варианте не реализовано)
        
        return False
    
    def _remove_duplicate_dependencies(self, dependencies: List[FileDependency]) -> List[FileDependency]:
        """Удаление дубликатов из списка зависимостей."""
        seen = set()
        unique_deps = []
        
        for dep in dependencies:
            key = (dep.source_file, dep.target_file, dep.dependency_type)
            if key not in seen:
                seen.add(key)
                unique_deps.append(dep)
        
        return unique_deps

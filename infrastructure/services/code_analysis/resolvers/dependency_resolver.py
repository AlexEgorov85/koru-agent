"""
DependencyResolver - сервис для анализа графа зависимостей проекта.
"""
from typing import Dict, List, Tuple, Set
from pathlib import Path


class DependencyResolver:
    """
    Сервис для анализа графа зависимостей проекта.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (сервис)
    - Ответственность: анализ зависимостей между файлами проекта
    - Принципы: соблюдение единой ответственности (S в SOLID)
    """
    
    def __init__(self):
        """Инициализация резольвера зависимостей."""
        self.import_resolver = None
        self._dependency_graph: Dict[str, List[str]] = {}
    
    def set_import_resolver(self, import_resolver):
        """
        Устанавливает резольвер импортов.
        
        Args:
            import_resolver: Объект резольвера импортов
        """
        self.import_resolver = import_resolver
    
    def build_dependency_graph(self, project_files: List[str]) -> Dict[str, List[str]]:
        """
        Строит граф зависимостей между файлами проекта.
        
        Args:
            project_files: Список файлов проекта
            
        Returns:
            Dict[str, List[str]]: Граф зависимостей в формате {файл: [зависимые_файлы]}
        """
        dependency_graph = {}
        
        for file_path in project_files:
            dependencies = self._find_direct_dependencies(file_path, project_files)
            dependency_graph[file_path] = dependencies
        
        self._dependency_graph = dependency_graph
        return dependency_graph
    
    def _find_direct_dependencies(self, source_file: str, project_files: List[str]) -> List[str]:
        """
        Находит прямые зависимости для файла.
        
        Args:
            source_file: Исходный файл
            project_files: Список файлов проекта
            
        Returns:
            List[str]: Список файлов, от которых зависит исходный файл
        """
        if not self.import_resolver:
            return []
        
        imports = self.import_resolver.get_all_imports(source_file, project_files)
        dependencies = []
        
        for imp in imports:
            resolved_path = imp.get('resolved_path')
            if resolved_path and resolved_path in project_files:
                dependencies.append(resolved_path)
        
        # Убираем дубликаты
        return list(set(dependencies))
    
    def get_reverse_dependencies(self, file_path: str) -> List[str]:
        """
        Получает список файлов, которые зависят от указанного файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            List[str]: Список файлов, зависящих от указанного
        """
        reverse_deps = []
        
        for src_file, deps in self._dependency_graph.items():
            if file_path in deps:
                reverse_deps.append(src_file)
        
        return reverse_deps
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """
        Находит циклические зависимости в проекте.
        
        Returns:
            List[List[str]]: Список циклов, каждый цикл представлен как список файлов
        """
        circular_deps = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []
        
        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self._dependency_graph.get(node, []):
                if neighbor in rec_stack:
                    # Нашли цикл
                    cycle_start_index = path.index(neighbor)
                    cycle = path[cycle_start_index:] + [neighbor]
                    circular_deps.append(cycle)
                elif neighbor not in visited:
                    dfs(neighbor)
            
            path.pop()
            rec_stack.remove(node)
        
        for file_path in self._dependency_graph:
            if file_path not in visited:
                dfs(file_path)
        
        return circular_deps
    
    def get_topological_order(self) -> List[str]:
        """
        Получает топологическую сортировку файлов проекта.
        
        Returns:
            List[str]: Список файлов в топологическом порядке
        """
        visited: Set[str] = set()
        stack: List[str] = []
        
        def dfs(node: str) -> None:
            visited.add(node)
            
            for neighbor in self._dependency_graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
            
            stack.append(node)
        
        for file_path in self._dependency_graph:
            if file_path not in visited:
                dfs(file_path)
        
        return stack[::-1]  # Обратный порядок
    
    def calculate_dependency_depth(self, file_path: str) -> int:
        """
        Вычисляет глубину зависимостей для файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            int: Глубина зависимостей
        """
        if file_path not in self._dependency_graph:
            return 0
        
        visited: Set[str] = set()
        
        def dfs(node: str, depth: int) -> int:
            if node in visited:
                return depth
            
            visited.add(node)
            max_depth = depth
            
            for neighbor in self._dependency_graph[node]:
                neighbor_depth = dfs(neighbor, depth + 1)
                max_depth = max(max_depth, neighbor_depth)
            
            return max_depth
        
        return dfs(file_path, 0)
    
    def get_most_dependent_files(self, n: int = 5) -> List[Tuple[str, int]]:
        """
        Получает список файлов с наибольшим количеством зависимостей.
        
        Args:
            n: Количество файлов для возврата
            
        Returns:
            List[Tuple[str, int]]: Список файлов и количество их зависимостей
        """
        dependency_counts = [(file_path, len(deps)) for file_path, deps in self._dependency_graph.items()]
        dependency_counts.sort(key=lambda x: x[1], reverse=True)
        
        return dependency_counts[:n]
    
    def get_least_dependent_files(self, n: int = 5) -> List[Tuple[str, int]]:
        """
        Получает список файлов с наименьшим количеством зависимостей.
        
        Args:
            n: Количество файлов для возврата
            
        Returns:
            List[Tuple[str, int]]: Список файлов и количество их зависимостей
        """
        dependency_counts = [(file_path, len(deps)) for file_path, deps in self._dependency_graph.items()]
        dependency_counts.sort(key=lambda x: x[1])
        
        return dependency_counts[:n]
    
    def get_dependency_statistics(self) -> Dict[str, int]:
        """
        Получает статистику зависимостей проекта.
        
        Returns:
            Dict[str, int]: Словарь с различной статистикой
        """
        if not self._dependency_graph:
            return {}
        
        all_deps = [dep for deps in self._dependency_graph.values() for dep in deps]
        unique_deps = set(all_deps)
        
        stats = {
            'total_files': len(self._dependency_graph),
            'total_dependencies': len(all_deps),
            'unique_dependencies': len(unique_deps),
            'average_dependencies_per_file': len(all_deps) / len(self._dependency_graph) if self._dependency_graph else 0,
            'max_dependencies': max(len(deps) for deps in self._dependency_graph.values()) if self._dependency_graph else 0,
            'min_dependencies': min(len(deps) for deps in self._dependency_graph.values()) if self._dependency_graph else 0
        }
        
        return stats
"""
Утилиты для разрешения зависимостей между сервисами с топологической сортировкой.
"""
from typing import Dict, List, Set, Tuple
from collections import defaultdict, deque
from core.application.services.base_service import BaseService
from core.system_context.resource_registry import ResourceInfo


class DependencyGraph:
    """Граф зависимостей сервисов с валидацией циклов."""
    
    def __init__(self):
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.in_degree: Dict[str, int] = defaultdict(int)
    
    def add_service(self, service_name: str, dependencies: List[str]):
        """Добавление сервиса и его зависимостей в граф."""
        self.graph[service_name] = dependencies
        
        # Обновление in-degree для зависимостей
        for dep in dependencies:
            self.in_degree[dep] += 1
        
        # Гарантируем, что сам сервис есть в in_degree
        if service_name not in self.in_degree:
            self.in_degree[service_name] = 0
    
    def detect_cycles(self) -> List[List[str]]:
        """Обнаружение циклических зависимостей (алгоритм поиска в глубину)."""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    # Найден цикл
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                    return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        for node in self.graph:
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    def topological_sort(self) -> Tuple[List[str], bool]:
        """
        Топологическая сортировка (алгоритм Кана).
        Возвращает: (порядок инициализации, есть_ли_циклы)
        """
        # Копируем in-degree для алгоритма
        in_degree_copy = self.in_degree.copy()
        queue = deque([node for node, degree in in_degree_copy.items() if degree == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            
            for neighbor in self.graph.get(node, []):
                in_degree_copy[neighbor] -= 1
                if in_degree_copy[neighbor] == 0:
                    queue.append(neighbor)
        
        # Проверка наличия циклов
        has_cycles = len(result) != len(self.graph)
        return result, has_cycles


class ServiceDescriptor:
    """Дескриптор сервиса для хранения информации о сервисе."""
    
    def __init__(self, name: str, service_class: type):
        self.name = name
        self.service_class = service_class


class DependencyResolver:
    """Резолвер зависимостей для SystemContext."""
    
    @staticmethod
    async def build_dependency_graph(
        service_descriptors: Dict[str, ServiceDescriptor]
    ) -> DependencyGraph:
        """Построение графа зависимостей из дескрипторов сервисов."""
        graph = DependencyGraph()
        
        for name, descriptor in service_descriptors.items():
            deps = getattr(descriptor.service_class, 'DEPENDENCIES', [])
            graph.add_service(name, deps)
        
        return graph
    
    @staticmethod
    async def calculate_initialization_order(
        service_descriptors: Dict[str, ServiceDescriptor]
    ) -> List[str]:
        """Расчёт порядка инициализации с валидацией циклов."""
        graph = await DependencyResolver.build_dependency_graph(service_descriptors)
        
        # Обнаружение циклов
        cycles = graph.detect_cycles()
        if cycles:
            cycle_str = " → ".join(cycles[0])
            from core.errors.architecture_violation import CircularDependencyError
            raise CircularDependencyError(
                f"Обнаружены циклические зависимости между сервисами:\n  {cycle_str}\n"
                f"Полный список циклов: {cycles}"
            )
        
        # Топологическая сортировка
        order, has_cycles = graph.topological_sort()
        if has_cycles:
            from core.errors.architecture_violation import CircularDependencyError
            raise CircularDependencyError(
                "Невозможно определить порядок инициализации из-за циклических зависимостей"
            )
        
        return order
    
    @staticmethod
    async def validate_service_dependencies(
        service_name: str,
        service_class: type,
        available_services: Set[str]
    ) -> List[str]:
        """Валидация, что все зависимости сервиса доступны."""
        missing = []
        for dep in getattr(service_class, 'DEPENDENCIES', []):
            if dep not in available_services:
                missing.append(dep)
        return missing
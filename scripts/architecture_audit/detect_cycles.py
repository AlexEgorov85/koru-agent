#!/usr/bin/env python3
"""
Обнаружение циклических зависимостей между модулями.
"""
import ast
import sys
from pathlib import Path
from typing import Dict, Set, List
from collections import defaultdict

def build_dependency_graph(source_dir: Path) -> Dict[str, Set[str]]:
    """Построение графа зависимостей между модулями."""
    graph = defaultdict(set)
    
    for py_file in source_dir.rglob('*.py'):
        if '__init__.py' in str(py_file):
            continue
        
        rel_path = py_file.relative_to(source_dir)
        module_name = str(rel_path.with_suffix('')).replace('/', '.').replace('\\', '.')
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
        except SyntaxError:
            continue
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    graph[module_name].add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    graph[module_name].add(alias.name)
    
    return graph

def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Поиск циклов в графе зависимостей (алгоритм DFS)."""
    cycles = []
    visited = set()
    rec_stack = set()
    path = []
    
    def dfs(node: str):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                cycle = dfs(neighbor)
                if cycle:
                    return cycle
            elif neighbor in rec_stack:
                # Найден цикл
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]
        
        path.pop()
        rec_stack.remove(node)
        return None
    
    for node in graph:
        if node not in visited:
            cycle = dfs(node)
            if cycle:
                cycles.append(cycle)
    
    return cycles

def main():
    source_dir = Path('core')
    graph = build_dependency_graph(source_dir)
    cycles = find_cycles(graph)
    
    if cycles:
        print("[FAIL] ОБНАРУЖЕНЫ ЦИКЛИЧЕСКИЕ ЗАВИСИМОСТИ:")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n  Цикл {i}:")
            print(f"    {' -> '.join(cycle)}")
        sys.exit(1)
    else:
        print("[PASS] Циклические зависимости отсутствуют")
        sys.exit(0)

if __name__ == '__main__':
    main()
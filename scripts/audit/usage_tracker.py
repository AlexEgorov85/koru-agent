#!/usr/bin/env python3
"""
Отслеживает где и как используется каждый элемент кода.
"""

import ast
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict


class UsageTracker:
    """Отслеживает использования элементов кода"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.definitions: Dict[str, List[Dict]] = defaultdict(list)
        self.usages: Dict[str, List[Dict]] = defaultdict(list)
        self.imports: Dict[str, Set[str]] = defaultdict(set)
    
    def scan_project(self):
        """Сканирование всего проекта"""
        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip(py_file):
                continue
            self._analyze_file(py_file)
    
    def _should_skip(self, file_path: Path) -> bool:
        """Проверка нужно ли пропускать файл"""
        skip_patterns = [
            '__pycache__', '.git', '.venv', 'venv',
            'node_modules', 'build', 'dist',
            'test_', '_test.py', 'mock_', 'fixture',
            'scripts/audit', 'audit_output'
        ]
        return any(p in str(file_path) for p in skip_patterns)

    def _analyze_file(self, file_path: Path):
        """Анализ одного файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
            
            self._collect_definitions(tree, file_path)
            self._collect_usages(tree, file_path)
            self._collect_imports(tree, file_path)
            
        except Exception as e:
            print(f"[WARN] Error analyzing {file_path}: {e}")
    
    def _collect_definitions(self, tree: ast.AST, file_path: Path):
        """Сбор определений классов, функций, методов"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self.definitions[f"class:{node.name}"].append({
                    'file': str(file_path.relative_to(self.project_root)),
                    'line': node.lineno,
                    'docstring': ast.get_docstring(node)
                })
            elif isinstance(node, ast.FunctionDef):
                is_method = any(isinstance(parent, ast.ClassDef) for parent in ast.walk(node))
                key = f"method:{node.name}" if is_method else f"function:{node.name}"
                self.definitions[key].append({
                    'file': str(file_path.relative_to(self.project_root)),
                    'line': node.lineno,
                    'docstring': ast.get_docstring(node)
                })
    
    def _collect_usages(self, tree: ast.AST, file_path: Path):
        """Сбор использований элементов"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.usages[f"function:{node.func.id}"].append({
                        'file': str(file_path.relative_to(self.project_root)),
                        'line': node.lineno
                    })
                    self.usages[f"method:{node.func.id}"].append({
                        'file': str(file_path.relative_to(self.project_root)),
                        'line': node.lineno
                    })
                elif isinstance(node.func, ast.Attribute):
                    self.usages[f"method:{node.func.attr}"].append({
                        'file': str(file_path.relative_to(self.project_root)),
                        'line': node.lineno
                    })
            
            if isinstance(node, ast.Name):
                self.usages[f"var:{node.id}"].append({
                    'file': str(file_path.relative_to(self.project_root)),
                    'line': node.lineno
                })
    
    def _collect_imports(self, tree: ast.AST, file_path: Path):
        """Сбор импортов"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports[str(file_path)].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.imports[str(file_path)].add(node.module)
    
    def find_unused_definitions(self) -> List[Dict]:
        """Поиск неиспользуемых определений"""
        unused = []
        
        for def_key, def_list in self.definitions.items():
            usage_count = 0
            
            for def_info in def_list:
                for usage_key, usage_list in self.usages.items():
                    name = def_key.split(':', 1)[1]
                    usage_name = usage_key.split(':', 1)[1] if ':' in usage_key else usage_key
                    
                    if name == usage_name:
                        usage_count += len(usage_list)
            
            is_exported = any(
                def_info['file'].endswith('__init__.py')
                for def_info in def_list
            )
            
            if usage_count == 0 and not is_exported:
                unused.append({
                    'definition': def_key,
                    'locations': def_list,
                    'usage_count': usage_count
                })
        
        return unused
    
    def find_duplicates(self) -> List[Dict]:
        """Поиск дубликатов по имени"""
        by_name = defaultdict(list)
        
        for def_key, def_list in self.definitions.items():
            if ':' in def_key:
                name = def_key.split(':', 1)[1]
                by_name[name].extend(def_list)
        
        duplicates = []
        for name, locations in by_name.items():
            if len(locations) > 1:
                duplicates.append({
                    'name': name,
                    'locations': locations,
                    'count': len(locations)
                })
        
        return duplicates
    
    def generate_report(self) -> Dict:
        """Генерация отчёта"""
        return {
            'total_definitions': sum(len(v) for v in self.definitions.values()),
            'total_usages': sum(len(v) for v in self.usages.values()),
            'unused': self.find_unused_definitions(),
            'duplicates': self.find_duplicates(),
            'imports_by_file': {k: list(v) for k, v in self.imports.items()}
        }


if __name__ == '__main__':
    import sys
    import json
    
    project_root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'usage_audit.json'
    
    tracker = UsageTracker(project_root)
    tracker.scan_project()
    report = tracker.generate_report()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"Usage audit complete: {report['total_definitions']} definitions, {report['total_usages']} usages")
    print(f"Unused: {len(report['unused'])}, Duplicates: {len(report['duplicates'])}")
    print(f"Results saved to: {output_file}")

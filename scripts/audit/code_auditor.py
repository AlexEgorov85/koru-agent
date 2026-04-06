#!/usr/bin/env python3
"""
Инструмент для детального аудита кода.
Анализирует каждый файл, класс, метод, свойство.
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class CodeElement:
    """Информация об элементе кода"""
    file_path: str
    element_type: str
    name: str
    line_start: int
    line_end: int
    docstring: Optional[str]
    parameters: List[str]
    returns: Optional[str]
    decorators: List[str]
    complexity: int
    lines_of_code: int


class CodeAuditor:
    """Аудитор кода"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.elements: List[CodeElement] = []

    def analyze(self) -> Dict:
        """Анализ всего проекта"""
        files = list(self.project_root.rglob("*.py"))
        
        total_classes = 0
        total_functions = 0
        total_methods = 0
        total_lines = 0

        for py_file in files:
            if self._should_skip(py_file):
                continue
            
            try:
                elements, lines = self._analyze_file(py_file)
                self.elements.extend(elements)
                total_lines += lines
                
                for elem in elements:
                    if elem.element_type == 'class':
                        total_classes += 1
                    elif elem.element_type == 'function':
                        total_functions += 1
                    elif elem.element_type == 'method':
                        total_methods += 1
            except Exception as e:
                print(f"[WARN] Error analyzing {py_file}: {e}")

        return {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'total_files': len([f for f in files if not self._should_skip(f)]),
            'total_classes': total_classes,
            'total_functions': total_functions,
            'total_methods': total_methods,
            'total_lines': total_lines,
            'elements': [asdict(e) for e in self.elements]
        }

    def _should_skip(self, file_path: Path) -> bool:
        """Проверка нужно ли пропускать файл"""
        skip_patterns = [
            '__pycache__', '.git', '.venv', 'venv',
            'node_modules', 'build', 'dist',
            'test_', '_test.py', 'mock_', 'fixture',
            'scripts/audit', 'audit_output'
        ]
        return any(p in str(file_path) for p in skip_patterns)

    def _analyze_file(self, file_path: Path) -> tuple[List[CodeElement], int]:
        """Анализ одного файла"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return [], 0

        elements = []
        lines = len(content.split('\n'))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                elem = self._analyze_class(node, file_path)
                if elem:
                    elements.append(elem)
            elif isinstance(node, ast.FunctionDef):
                if not self._is_method_inside_class(node):
                    elem = self._analyze_function(node, file_path, 'function')
                    if elem:
                        elements.append(elem)

        return elements, lines

    def _is_method_inside_class(self, node: ast.FunctionDef) -> bool:
        """Проверка является ли функция методом класса"""
        for parent in ast.walk(node):
            if isinstance(parent, ast.ClassDef):
                return True
        return False

    def _analyze_class(self, node: ast.ClassDef, file_path: Path) -> Optional[CodeElement]:
        """Анализ класса"""
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        
        return CodeElement(
            file_path=str(file_path.relative_to(self.project_root)),
            element_type='class',
            name=node.name,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            parameters=[],
            returns=None,
            decorators=[a for a in node.decorator_list if isinstance(a, ast.Name)],
            complexity=self._calculate_complexity(node),
            lines_of_code=(node.end_lineno or node.lineno) - node.lineno + 1
        )

    def _analyze_function(self, node: ast.FunctionDef, file_path: Path, elem_type: str) -> Optional[CodeElement]:
        """Анализ функции"""
        params = [a.arg for a in node.args.args]
        
        returns = None
        if node.returns:
            if isinstance(node.returns, ast.Name):
                returns = node.returns.id
            elif isinstance(node.returns, ast.Constant):
                returns = str(node.returns.value)

        decorators = []
        for d in node.decorator_list:
            if isinstance(d, ast.Name):
                decorators.append(d.id)
            elif isinstance(d, ast.Attribute):
                decorators.append(d.attr)

        return CodeElement(
            file_path=str(file_path.relative_to(self.project_root)),
            element_type=elem_type,
            name=node.name,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            parameters=params,
            returns=returns,
            decorators=decorators,
            complexity=self._calculate_complexity(node),
            lines_of_code=(node.end_lineno or node.lineno) - node.lineno + 1
        )

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Расчёт цикломатической сложности"""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity


def find_legacy_markers(project_path: Path) -> Dict:
    """Поиск маркеров легаси кода"""
    
    markers = {
        'deprecated': [],
        'todo': [],
        'fixme': [],
        'hack': [],
        'legacy': [],
        'remove': [],
        'delete': []
    }
    
    patterns = {
        'deprecated': [r'#.*DEPRECATED', r'@deprecated', r'deprecated\('],
        'todo': [r'#.*TODO'],
        'fixme': [r'#.*FIXME'],
        'hack': [r'#.*HACK'],
        'legacy': [r'#.*LEGACY', r'legacy', r'Legacy'],
        'remove': [r'#.*REMOVE'],
        'delete': [r'#.*DELETE']
    }
    
    import re
    
    for py_file in project_path.rglob('*.py'):
        if any(p in str(py_file) for p in ['__pycache__', '.git', 'test_', 'scripts/audit', 'audit_output']):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            for marker_type, pattern_list in patterns.items():
                for pattern in pattern_list:
                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            markers[marker_type].append({
                                'file': str(py_file.relative_to(project_path)),
                                'line': line_num,
                                'content': line.strip()
                            })
        except Exception:
            pass
    
    return {
        'timestamp': datetime.now().isoformat(),
        'project': str(project_path),
        'markers': {k: len(v) for k, v in markers.items()},
        'details': markers
    }


if __name__ == '__main__':
    import sys
    
    project_root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'code_audit.json'
    
    auditor = CodeAuditor(project_root)
    report = auditor.analyze()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"Code audit complete: {report['total_files']} files, {report['total_classes']} classes, {report['total_methods']} methods")
    print(f"Results saved to: {output_file}")

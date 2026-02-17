#!/usr/bin/env python3
"""
Проверка направления зависимостей между слоями.
"""
import ast
import sys
from pathlib import Path
from typing import List, Dict, Set

# Запрещённые импорты по слоям
FORBIDDEN_IMPORTS = {
    'core/application': [
        'core.infrastructure.context',
        'core.infrastructure.storage',
        'core.infrastructure.providers',
    ],
    'core/components': [
        'core.infrastructure.context',
        'core.infrastructure.providers',
    ],
    'core/session_context': [
        'core.infrastructure.context',
        'core.infrastructure.providers',
        'core.application',
    ],
}

class ImportVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.imports: List[str] = []
    
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)

def check_file(filepath: Path, source_dir: Path) -> List[str]:
    """Проверка одного файла на запрещённые импорты."""
    errors = []
    rel_path = filepath.relative_to(source_dir)
    
    # Определяем слой файла
    file_layer = None
    for layer, _ in FORBIDDEN_IMPORTS.items():
        if str(rel_path).startswith(layer):
            file_layer = layer
            break
    
    if not file_layer:
        return errors
    
    # Парсим файл
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        return [f"{rel_path}: SyntaxError"]
    
    visitor = ImportVisitor(filepath)
    visitor.visit(tree)
    
    # Проверяем запрещённые импорты
    for forbidden in FORBIDDEN_IMPORTS[file_layer]:
        for imp in visitor.imports:
            if imp.startswith(forbidden):
                errors.append(
                    f"{rel_path}: Запрещённый импорт '{imp}' из слоя '{file_layer}'"
                )
    
    return errors

def main():
    source_dir = Path('core')
    all_errors = []
    
    for py_file in source_dir.rglob('*.py'):
        errors = check_file(py_file, source_dir)
        all_errors.extend(errors)
    
    if all_errors:
        print("[FAIL] НАРУШЕНИЯ НАПРАВЛЕНИЯ ЗАВИСИМОСТЕЙ:")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("[PASS] Направление зависимостей корректно")
        sys.exit(0)

if __name__ == '__main__':
    main()
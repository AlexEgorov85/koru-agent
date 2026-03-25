#!/usr/bin/env python3
"""
КОМПЛЕКСНЫЙ АУДИТ - без дубликатов в списках
"""

import ast
import re
from pathlib import Path
from collections import defaultdict

# Аналоги
ANALOGS = {
    'BaseTool': ['base_tool.py (2 loc)'],
    'BaseDBProvider': ['base_db.py + base.py'],
    'LoggingConfig': ['config.py + log_config.py'],
    'IMetricsStorage': ['2 файла'],
    'ILogStorage': ['2 файла'],
    'LogLevel': ['3 файла'],
    'LogFormat': ['3 файла'],
}


def get_purpose(name, file_path, bases=None):
    keywords = {
        'config': 'Конфигурация', 'handler': 'Обработчик', 'service': 'Сервис',
        'provider': 'Провайдер', 'storage': 'Хранилище', 'logger': 'Логирование',
        'factory': 'Фабрика', 'tool': 'Инструмент', 'skill': 'Навык',
        'behavior': 'Поведение', 'agent': 'Агент', 'context': 'Контекст',
        'validator': 'Валидатор', 'executor': 'Исполнитель', 'manager': 'Менеджер',
        'error': 'Ошибка', 'exception': 'Исключение', 'interface': 'Интерфейс',
        'base': 'Базовый класс', 'mixin': 'Миксин', 'collector': 'Сборщик',
        'preloader': 'Загрузчик', 'discovery': 'Обнаружение', 'registry': 'Реестр',
    }
    
    name_l = name.lower()
    file_l = file_path.lower()
    
    for kw, p in keywords.items():
        if kw in name_l or kw in file_l:
            return p
    
    if bases:
        for b in bases:
            if 'Error' in b: return 'Ошибка'
            if 'Config' in b: return 'Конфигурация'
            if 'Interface' in b: return 'Интерфейс'
    
    return 'Утилита'


def find_usages(name, exclude_file):
    usages = []
    for py_file in Path('.').rglob("*.py"):
        skip = ['__pycache__', 'test', 'scripts', exclude_file]
        if any(s in str(py_file) for s in skip):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            patterns = [rf'\b{name}\s*\(', rf'\b{name}\.', rf'from\s+.*{name}', rf'import.*{name}']
            
            for p in patterns:
                if re.search(p, content):
                    usages.append(str(py_file).replace('\\', '/'))
                    break
        except:
            pass
    
    return usages


def analyze_project():
    elements = []
    
    for py_file in Path('.').rglob("*.py"):
        if any(s in str(py_file) for s in ['__pycache__', '.git', '.venv', 'test', 'scripts']):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
            
            file_path = str(py_file.relative_to(Path('.'))).replace('\\', '/')
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [b.id if isinstance(b, ast.Name) else str(b) for b in node.bases]
                    doc = ast.get_docstring(node)
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    
                    elements.append({
                        'file': file_path,
                        'name': node.name,
                        'type': 'class',
                        'bases': bases,
                        'docstring': doc,
                        'methods': methods,
                        'methods_count': len(methods)
                    })
                
                elif isinstance(node, ast.FunctionDef):
                    is_method = any(isinstance(parent, ast.ClassDef) for parent in ast.walk(node))
                    if not is_method:
                        doc = ast.get_docstring(node)
                        
                        elements.append({
                            'file': file_path,
                            'name': node.name,
                            'type': 'function',
                            'docstring': doc,
                            'params': len(node.args.args)
                        })
        except:
            pass
    
    return elements


def main():
    print("Анализ...")
    elements = analyze_project()
    print(f"Найдено: {len(elements)} элементов")
    
    # Назначение
    for e in elements:
        e['purpose'] = get_purpose(e['name'], e['file'], e.get('bases'))
        e['analogs'] = ANALOGS.get(e['name'], [])
    
    # Поиск использований
    print("Поиск использований...")
    for i, e in enumerate(elements):
        if e['type'] == 'class':
            if i % 200 == 0:
                print(f"  {i}/{len(elements)}")
            e['usages'] = find_usages(e['name'], e['file'])
        else:
            e['usages'] = []
    
    # Дубликаты - только имена
    name_to_elements = defaultdict(list)
    for e in elements:
        name_to_elements[e['name']].append(e)
    
    duplicates = {k: v for k, v in name_to_elements.items() if len(v) > 1}
    
    # Markdown
    lines = []
    lines.append("# КОМПЛЕКСНЫЙ АУДИТ КОДА")
    lines.append("")
    lines.append(f"**Всего элементов:** {len(elements)}")
    lines.append(f"**Уникальных имён:** {len(name_to_elements)}")
    lines.append(f"**Дубликатов по имени:** {len(duplicates)}")
    lines.append("")
    
    # Сводка по назначению
    by_purpose = defaultdict(list)
    for e in elements:
        by_purpose[e['purpose']].append(e)
    
    lines.append("## СВОДКА ПО НАЗНАЧЕНИЮ")
    lines.append("")
    for purpose, items in sorted(by_purpose.items(), key=lambda x: -len(x[1])):
        lines.append(f"- **{purpose}**: {len(items)}")
    lines.append("")
    
    # Дубликаты - только имена
    lines.append("## ДУБЛИКАТЫ (одинаковое имя в разных файлах)")
    lines.append("")
    for name, items in sorted(duplicates.items(), key=lambda x: -len(x[1]))[:40]:
        files = [i['file'] for i in items]
        lines.append(f"- **{name}**: {len(items)}x - {', '.join([Path(f).stem for f in files[:4]])}")
    lines.append("")
    
    # Элементы - уникальные по имени
    lines.append("## ЭЛЕМЕНТЫ (уникальные имена, первый файл)")
    lines.append("")
    
    for purpose in sorted(by_purpose.keys(), key=lambda x: -len(by_purpose[x])):
        items = by_purpose[purpose]
        
        # Группируем по имени
        by_name = {}
        for item in items:
            name = item['name']
            if name not in by_name:
                by_name[name] = item
        
        unique_items = list(by_name.values())
        unique_items.sort(key=lambda x: -len(x.get('usages', [])))
        
        if not unique_items:
            continue
            
        lines.append(f"### {purpose} ({len(unique_items)} уникальных)")
        lines.append("")
        lines.append("| Имя | Файл | Базовые/Параметры | Методы | Использ. |")
        lines.append("|-----|------|-------------------|--------|----------|")
        
        for item in unique_items[:40]:
            name = item['name']
            file_path = item['file']
            
            if item['type'] == 'class':
                info = ", ".join(item.get('bases', [])[:2]) if item.get('bases') else "-"
                methods = str(item.get('methods_count', 0))
            else:
                info = f"{item.get('params', 0)} params"
                methods = "-"
            
            usages = item.get('usages', [])
            usages_str = str(len(usages)) if usages else "-"
            
            lines.append(f"| `{name}` | {Path(file_path).stem} | {info} | {methods} | {usages_str} |")
        
        lines.append("")
    
    md = "\n".join(lines)
    
    with open('DETAILED_AUDIT_FULL.md', 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"Сохранено: DETAILED_AUDIT_FULL.md ({len(md)} символов)")
    
    # Статистика
    used = sum(1 for e in elements if e.get('usages') and len(e['usages']) > 0)
    print(f"Используется: {used}, Не используется: {len(elements) - used}")


if __name__ == '__main__':
    main()

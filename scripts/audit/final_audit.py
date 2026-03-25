#!/usr/bin/env python3
"""
Финальный аудит - с назначением, использованием и аналогами
"""

import ast
import re
from pathlib import Path
from collections import defaultdict

# Аналоги
ANALOGS = {
    'BaseTool': ['base_tool.py (application/tools + components)'],
    'BaseDBProvider': ['base_db.py + base.py'],
    'LoggingConfig': ['config.py + log_config.py + logging_config.py'],
    'IMetricsStorage': ['metrics_storage.py + metrics_log_interfaces.py'],
    'ILogStorage': ['log_storage.py + metrics_log_interfaces.py'],
    'LogLevel': ['3 файла'],
    'LogFormat': ['3 файла'],
}


def get_purpose(name, file_path, bases=None):
    """Определить назначение"""
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


def analyze_project():
    """Анализ"""
    project_root = Path('.')
    elements = []
    
    for py_file in project_root.rglob("*.py"):
        if any(s in str(py_file) for s in ['__pycache__', '.git', '.venv', 'test', 'scripts']):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
            
            file_path = str(py_file.relative_to(project_root)).replace('\\', '/')
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [b.id if isinstance(b, ast.Name) else str(b) for b in node.bases]
                    
                    elements.append({
                        'file': file_path,
                        'name': node.name,
                        'type': 'class',
                        'bases': bases,
                        'methods': len([n for n in node.body if isinstance(n, ast.FunctionDef)])
                    })
                
                elif isinstance(node, ast.FunctionDef):
                    is_method = any(isinstance(parent, ast.ClassDef) for parent in ast.walk(node))
                    if not is_method and not node.name.startswith('_'):
                        elements.append({
                            'file': file_path,
                            'name': node.name,
                            'type': 'function',
                            'params': len(node.args.args)
                        })
        except:
            pass
    
    return elements


def find_usages_quick(elements, limit=True):
    """Быстрый поиск использований - только для ключевых элементов"""
    print("Finding usages...")
    
    key_classes = ['ApplicationContext', 'InfrastructureContext', 'BaseComponent', 'BaseTool', 
                   'BaseService', 'BaseSkill', 'EventBusLogger', 'UnifiedEventBus', 'DataRepository',
                   'ComponentFactory', 'ResourceDiscovery', 'Config', 'LoggingConfig']
    
    for e in elements:
        if e['type'] != 'class':
            continue
        
        if limit and e['name'] not in key_classes:
            e['usages'] = []
            continue
        
        name = e['name']
        usages = []
        
        for py_file in Path('.').rglob("*.py"):
            skip = ['__pycache__', 'test', 'scripts', e['file']]
            if any(s in str(py_file) for s in skip):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                patterns = [
                    rf'from\s+.*{re.escape(name)}',
                    rf'import.*{re.escape(name)}',
                    rf':\s*{re.escape(name)}\(',
                    rf'\b{re.escape(name)}\(',
                ]
                
                for p in patterns:
                    if re.search(p, content):
                        usages.append(str(py_file))
                        break
            except:
                pass
        
        e['usages'] = usages[:10]
    
    return elements


def main():
    print("Analyzing...")
    elements = analyze_project()
    print(f"Found {len(elements)} elements")
    
    # Назначение и аналоги
    for e in elements:
        e['purpose'] = get_purpose(e['name'], e['file'], e.get('bases'))
        e['analogs'] = ANALOGS.get(e['name'], [])
    
    # Только для ключевых классов
    elements = find_usages_quick(elements)
    
    # Markdown
    lines = []
    lines.append("# КАЧЕСТВЕННЫЙ АУДИТ КОДА")
    lines.append("")
    lines.append(f"**Всего элементов:** {len(elements)}")
    lines.append("")
    lines.append("## Колонки:")
    lines.append("- **Файл** - где определён")
    lines.append("- **Имя** - название класса/функции")
    lines.append("- **Тип** - class или function")
    lines.append("- **Назначение** - определено по коду")
    lines.append("- **Базовые/Параметры** - для классов базовые классы, для функций кол-во параметров")
    lines.append("- **Использ.** - сколько файлов использует")
    lines.append("- **Аналоги** - дубликаты")
    lines.append("")
    
    lines.append("| Файл | Имя | Тип | Назначение | Базовые/Параметры | Использ. | Аналоги |")
    lines.append("|------|-----|-----|-----------|-------------------|----------|---------|")
    
    # Группируем по файлам
    by_file = defaultdict(list)
    for e in elements:
        by_file[e['file']].append(e)
    
    for file_path in sorted(by_file.keys()):
        if not file_path.startswith('core/'):
            continue
        
        for e in by_file[file_path]:
            if e['type'] == 'class':
                info = ", ".join(e.get('bases', [])[:2]) if e.get('bases') else "-"
            else:
                info = f"{e.get('params', 0)} params"
            
            usages = e.get('usages', [])
            usages_count = len(usages)
            
            analogs = e.get('analogs', [])
            analogs_str = ", ".join(analogs[:1]) if analogs else "-"
            
            # Only show if has usages
            usages_str = str(usages_count) if usages_count > 0 else "-"
            
            lines.append(f"| {e['file']} | `{e['name']}` | {e['type']} | {e['purpose']} | {info} | {usages_str} | {analogs_str} |")
    
    md = "\n".join(lines)
    
    with open('DETAILED_AUDIT_FULL.md', 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"Saved ({len(md)} chars)")


if __name__ == '__main__':
    main()

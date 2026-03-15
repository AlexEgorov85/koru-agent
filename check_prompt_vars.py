#!/usr/bin/env python
"""Проверка соответствия переменных в промптах."""
import re
import yaml
from pathlib import Path

def check_prompt_file(filepath):
    """Проверка одного файла промпта."""
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return f"❌ {filepath}: YAML ошибка - {e}"
    
    if not data or 'content' not in data:
        return None  # Пропустить файлы без content
    
    content = data.get('content', '')
    variables = data.get('variables', [])
    
    # Найти все переменные в content {var_name}
    used_vars = set(re.findall(r'\{(\w+)\}', content))
    # Исключить переменные из примеров JSON
    json_vars = set(re.findall(r'"\w+":', content))
    used_vars = used_vars - {v.rstrip(':') for v in json_vars if v.endswith(':')}
    
    # Получить declared variables
    declared_vars = {v.get('name') for v in variables if isinstance(v, dict) and v.get('name')}
    required_vars = {v.get('name') for v in variables if isinstance(v, dict) and v.get('required')}
    
    # Проверки
    issues = []
    
    # 1. Переменные используются но не объявлены
    missing = used_vars - declared_vars
    if missing:
        issues.append(f"Используются но не объявлены: {missing}")
    
    # 2. Обязательные переменные не используются
    unused_required = required_vars - used_vars
    if unused_required:
        issues.append(f"Обязательные но не используются: {unused_required}")
    
    # 3. Объявлены но не используются (не required)
    unused_optional = (declared_vars - used_vars) - required_vars
    if unused_optional:
        issues.append(f"Объявлены но не используются (optional): {unused_optional}")
    
    if issues:
        return f"⚠️ {filepath}:\n   " + "\n   ".join(issues)
    else:
        return f"✅ {filepath}: OK (vars={declared_vars})"

def main():
    prompts_dir = Path(__file__).parent / 'data' / 'prompts'
    issues = []
    ok_count = 0
    
    for filepath in prompts_dir.rglob('*.yaml'):
        if 'tests' in str(filepath):
            continue
        result = check_prompt_file(filepath)
        if result:
            if '❌' in result or '⚠️' in result:
                issues.append(result)
            else:
                ok_count += 1
            print(result)
    
    print(f"\n{'='*60}")
    print(f"Всего проверено: {ok_count + len(issues)} файлов")
    print(f"OK: {ok_count}")
    print(f"Проблемы: {len(issues)}")
    
    if issues:
        print("\n❌ Найдены проблемы:")
        for issue in issues:
            print(issue)
        return 1
    return 0

if __name__ == '__main__':
    exit(main())

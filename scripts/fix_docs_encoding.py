#!/usr/bin/env python3
"""
Скрипт восстановления документации после повреждения.
Запуск: python scripts/fix_docs_encoding.py
"""

import re
from pathlib import Path

def fix_markdown_file(file_path: Path) -> bool:
    """Восстановление разрывов строк в MD файле"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Проверка: если файл в одну строку — он повреждён
    if '\n' not in content:
        print(f"  ❌ {file_path} — повреждён (нет разрывов строк)")
        return False
    
    # Удаление trailing whitespace
    lines = content.split('\n')
    fixed_lines = [line.rstrip() for line in lines]
    fixed_content = '\n'.join(fixed_lines)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"  ✅ {file_path} — исправлен")
    return True

def main():
    docs_path = Path('docs')
    fixed = 0
    damaged = 0
    
    print("🔍 Проверка документации...\n")
    
    for md_file in docs_path.rglob('*.md'):
        if 'templates' in str(md_file):
            continue  # Пропускаем шаблоны
        
        if not fix_markdown_file(md_file):
            damaged += 1
        else:
            fixed += 1
    
    print(f"\n📊 Итоги:")
    print(f"  ✅ Исправлено: {fixed}")
    print(f"  ❌ Повреждено: {damaged}")

if __name__ == '__main__':
    main()

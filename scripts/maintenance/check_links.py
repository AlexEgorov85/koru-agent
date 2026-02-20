"""
Скрипт проверки ссылок в документации.
"""

import re
from pathlib import Path
from typing import List, Tuple


def find_markdown_links(content: str) -> List[str]:
    """Найти все markdown ссылки в контенте."""
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    return re.findall(pattern, content)


def check_link(base_path: Path, link: str) -> bool:
    """Проверить существует ли ссылка."""
    if link.startswith('http'):
        return True  # Внешние ссылки не проверяем
    
    # Относительная ссылка
    if link.startswith('./'):
        link = link[2:]
    elif link.startswith('../'):
        # Поднимаемся на уровень вверх
        parts = link.split('/')
        up_count = link.count('../')
        relative_path = '/'.join(parts[up_count:])
        
        # Вычисляем путь относительно base_path
        check_path = base_path.parent
        for _ in range(up_count - 1):
            check_path = check_path.parent
        check_path = check_path / relative_path
    else:
        check_path = base_path.parent / link
    
    # Удаляем якорь
    if '#' in check_path.name:
        check_path = check_path.parent / check_path.name.split('#')[0]
    
    return check_path.exists()


def audit_documentation(root_dir: str):
    """Аудит документации."""
    root = Path(root_dir)
    issues = []
    
    for md_file in root.rglob('*.md'):
        print(f"Проверка: {md_file.relative_to(root)}")
        
        content = md_file.read_text(encoding='utf-8')
        links = find_markdown_links(content)
        
        for text, link in links:
            if not check_link(md_file, link):
                issues.append((md_file, text, link))
    
    return issues


if __name__ == '__main__':
    print("="*60)
    print("АУДИТ ССЫЛОК В ДОКУМЕНТАЦИИ")
    print("="*60)
    
    issues = audit_documentation('docs')
    
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ")
    print("="*60)
    
    if issues:
        print(f"\nНайдено {len(issues)} битых ссылок:\n")
        for md_file, text, link in issues:
            print(f"  {md_file.name}: [{text}]({link})")
    else:
        print("\n✅ Все ссылки валидны!")
    
    print("\n" + "="*60)

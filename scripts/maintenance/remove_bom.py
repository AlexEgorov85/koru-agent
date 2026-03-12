#!/usr/bin/env python3
"""
Удаление BOM-символов из файлов проекта.

ИСПОЛЬЗОВАНИЕ:
    python scripts/maintenance/remove_bom.py

BOM (Byte Order Mark) может вызывать ошибки парсинга AST.
"""
import os
from pathlib import Path

# BOM символы для UTF-8
UTF8_BOM = b'\xef\xbb\xbf'

def remove_bom_from_file(file_path: Path) -> bool:
    """Удалить BOM из файла."""
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        if content.startswith(UTF8_BOM):
            # Удаляем BOM
            with open(file_path, 'wb') as f:
                f.write(content[3:])
            return True
        return False
    except Exception as e:
        print(f"  [ERROR] {file_path}: {e}")
        return False

def find_python_files(root_dir: Path) -> list:
    """Найти все Python файлы."""
    files = []
    for py_file in root_dir.rglob("*.py"):
        # Пропускаем __pycache__ и .git
        if '__pycache__' in str(py_file) or '.git' in str(py_file):
            continue
        files.append(py_file)
    return files

def main():
    """Основная функция."""
    project_root = Path(__file__).parent.parent.parent
    
    print("[INFO] Поиск файлов с BOM...")
    
    files_with_bom = []
    all_files = find_python_files(project_root / "core")
    
    for file_path in all_files:
        try:
            with open(file_path, 'rb') as f:
                content = f.read(3)
                if content == UTF8_BOM:
                    files_with_bom.append(file_path)
        except Exception:
            pass
    
    if not files_with_bom:
        print("[OK] Файлов с BOM не найдено!")
        return
    
    print(f"\n[INFO] Найдено {len(files_with_bom)} файлов с BOM:\n")
    
    removed_count = 0
    for file_path in files_with_bom:
        relative_path = file_path.relative_to(project_root)
        print(f"  [FIX] {relative_path}")
        if remove_bom_from_file(file_path):
            removed_count += 1
    
    print(f"\n[RESULT] Удалено BOM из {removed_count}/{len(files_with_bom)} файлов")
    
    if removed_count == len(files_with_bom):
        print("[OK] Все BOM-символы удалены!")
    else:
        print(f"[WARN] Не удалось удалить BOM из {len(files_with_bom) - removed_count} файлов")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script to fix encoding issues in project files.
Decodes text that was saved in cp1251 but read as UTF-8.
"""
import os
from pathlib import Path
import sys


def fix_mojibake(content: str) -> str:
    """
    Fixes mojibake (garbled text).
    Decodes text that was in cp1251 but read as UTF-8.
    """
    try:
        fixed = content.encode('utf-8').decode('cp1251')
        return fixed
    except (UnicodeDecodeError, UnicodeError):
        return content


def has_mojibake(content: str) -> bool:
    """Check if text contains mojibake patterns."""
    mojibake_chars = ['Р', 'С', 'в', 'ѓ', '„', '‹', 'ў', 'Ћ', '¦', '§', 'Ё', '©', '«', '¬', '®', '°', '±', 'І', 'µ', '¶', '·', 'ё', '№', '»', 'ј', 'ѕ', 'ѕ']
    return any(c in content for c in mojibake_chars)


def fix_file(file_path: Path) -> bool:
    """Fix encoding issues in file. Returns True if fixed."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if has_mojibake(content):
            fixed_content = fix_mojibake(content)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            print(f"Fixed: {file_path}")
            return True
    except Exception as e:
        print(f"Error {file_path}: {e}")
    
    return False


def main():
    """Main function."""
    project_root = Path(__file__).parent.parent
    
    patterns = ["**/*.py", "**/*.md", "**/*.txt"]
    fixed_count = 0
    total_count = 0
    
    print("Searching for files with encoding issues...")
    
    for pattern in patterns:
        for file_path in project_root.glob(pattern):
            if any(part.startswith('.') or part == '__pycache__' for part in file_path.parts):
                continue
            
            total_count += 1
            if fix_file(file_path):
                fixed_count += 1
    
    print(f"\nDone!")
    print(f"Total files checked: {total_count}")
    print(f"Files fixed: {fixed_count}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

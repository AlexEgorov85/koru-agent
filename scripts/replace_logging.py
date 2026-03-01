"""
Скрипт для массовой замены logging на EventBusLogger.

ЗАМЕНЯЕТ:
1. self.logger.info/debug/warning/error → await self.event_bus_logger.info/debug/warning/error
2. logger.info/debug/warning/error → await self.event_bus_logger.info/debug/warning/error
3. self.logger.exception → await self.event_bus_logger.exception
"""
import os
import re
from pathlib import Path


def replace_logging_in_file(filepath: Path) -> int:
    """Замена logging в файле. Возвращает количество замен."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  SKIP {filepath}: {e}")
        return 0
    
    original = content
    replacements = 0
    
    # Паттерн 1: else:\n            self.logger.XXX(...) → удалить блок else
    pattern_else = r'else:\s*\n(\s+)self\.logger\.(info|debug|warning|error|exception)\('
    matches = list(re.finditer(pattern_else, content))
    if matches:
        for match in reversed(matches):  # С конца чтобы индексы не сбились
            # Находим начало else и конец строки
            else_start = match.start()
            line_end = content.find(')', match.end()) + 1
            # Заменяем на пустоту
            content = content[:else_start] + content[line_end:]
            replacements += 1
    
    # Паттерн 2: if self.event_bus_logger: ... else: self.logger → оставить только if
    # Уже обработано паттерном 1
    
    # Паттерн 3: logger.debug/info(...) без self → заменить на await self.event_bus_logger
    # Осторожно: только внутри методов класса
    pattern_module_logger = r'(?<!self\.)logger\.(info|debug|warning|error)\('
    matches = list(re.finditer(pattern_module_logger, content))
    if matches:
        for match in reversed(matches):
            method = match.group(1)
            # Проверяем что это не внутри строки
            line_start = content.rfind('\n', 0, match.start()) + 1
            line = content[line_start:match.start()]
            if not line.strip().startswith('#'):  # Не комментарий
                replacement = f'self.event_bus_logger.{method}('
                content = content[:match.start()] + replacement + content[match.end():]
                replacements += 1
    
    # Паттерн 4: self.logger.exception → await self.event_bus_logger.exception
    pattern_exception = r'self\.logger\.exception\('
    matches = list(re.finditer(pattern_exception, content))
    if matches:
        for match in reversed(matches):
            content = content[:match.start()] + 'self.event_bus_logger.exception(' + content[match.end():]
            replacements += 1
    
    # Паттерн 5: self.logger.warning/info/debug/error → await self.event_bus_logger
    pattern_self_logger = r'self\.logger\.(info|debug|warning|error)\('
    matches = list(re.finditer(pattern_self_logger, content))
    if matches:
        for match in reversed(matches):
            method = match.group(1)
            replacement = f'self.event_bus_logger.{method}('
            content = content[:match.start()] + replacement + content[match.end():]
            replacements += 1
    
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        print(f"  FIXED {filepath}: {replacements} замен")
    
    return replacements


def main():
    """Основная функция."""
    print("="*70)
    print("МАССОВАЯ ЗАМЕНА logging НА EventBusLogger")
    print("="*70)
    
    # Директории для обработки
    dirs_to_process = [
        Path('core/application'),
        Path('core/infrastructure'),
    ]
    
    # Исключения (файлы которые не нужно трогать)
    exclude_patterns = [
        'logging/',  # Сама система логирования
        'test_',     # Тесты
        '__pycache__',
        'unified_logger.py',  # Новый файл
    ]
    
    total_replacements = 0
    
    for base_dir in dirs_to_process:
        if not base_dir.exists():
            print(f"SKIP {base_dir}: не существует")
            continue
            
        print(f"\n{base_dir}/")
        
        for filepath in base_dir.rglob('*.py'):
            # Проверка исключений
            skip = False
            for pattern in exclude_patterns:
                if pattern in str(filepath):
                    skip = True
                    break
            
            if skip:
                continue
            
            replacements = replace_logging_in_file(filepath)
            total_replacements += replacements
    
    print("\n" + "="*70)
    print(f"ИТОГО: {total_replacements} замен")
    print("="*70)


if __name__ == '__main__':
    main()

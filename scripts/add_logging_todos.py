"""Add TODO comments to lines that need to be migrated from logger to event_bus.publish()"""
import re
from pathlib import Path

PATTERNS = [
    r'^import logging$',
    r'^logger = logging\.getLogger\(',
    r'logger\.(debug|info|warning|error|exception)\(',
    r'from core\.infrastructure\.logging import EventBusLogger',
    r'self\.event_bus_logger = EventBusLogger',
    r'await self\.event_bus_logger\.',
]

TODO_COMMENT = "  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()"

def process_file(filepath):
    modified = False
    lines = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for i, line in enumerate(lines):
        original_line = line
        stripped = line.strip()
        
        # Skip if line already has TODO
        if 'TODO' in stripped and 'event_bus' in stripped:
            new_lines.append(line)
            continue
            
        # Check each pattern
        for pattern in PATTERNS:
            if re.search(pattern, stripped):
                # Add TODO comment after the line
                indent = len(line) - len(line.lstrip())
                spaces = ' ' * indent
                new_lines.append(line)
                new_lines.append(spaces + TODO_COMMENT + '\n')
                modified = True
                break
        else:
            new_lines.append(line)
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    return False

def main():
    core_dir = Path("core")
    processed = 0
    
    for fp in core_dir.rglob("*.py"):
        if process_file(fp):
            processed += 1
            print(f"Processed: {fp}")
    
    print(f"\nTotal files modified: {processed}")

if __name__ == "__main__":
    main()
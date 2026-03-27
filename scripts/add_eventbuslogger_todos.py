"""Add TODO comments for EventBusLogger usages"""
import re
from pathlib import Path

PATTERNS = [
    r'from core\.infrastructure\.logging import EventBusLogger',
    r'self\.event_bus_logger = EventBusLogger',
    r'await self\.event_bus_logger\.',
]

TODO_COMMENT = "  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})"

def process_file(filepath):
    modified = False
    lines = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Skip if line already has TODO
        if 'TODO' in stripped and 'EventBusLogger' in stripped:
            new_lines.append(line)
            continue
            
        # Check each pattern
        for pattern in PATTERNS:
            if re.search(pattern, stripped):
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
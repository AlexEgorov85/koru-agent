#!/usr/bin/env python
"""
Скрипт для массовой замены импортов legacy event_bus на unified_event_bus.
"""
import os
import re

EXCLUDE_FILES = [
    'unified_event_bus.py',
    'event_bus_adapter.py', 
    'event_bus_concurrent.py',
    'domain_event_bus.py',
    'event_bus.py',
    'update_imports.py'  # Этот скрипт
]

EXCLUDE_DIRS = ['__pycache__', '.git', '.qwen']

REPLACEMENTS = [
    ('from core.infrastructure.event_bus.event_bus import EventType',
     'from core.infrastructure.event_bus.unified_event_bus import EventType'),
    ('from core.infrastructure.event_bus.event_bus import Event, EventType',
     'from core.infrastructure.event_bus.unified_event_bus import Event, EventType'),
    ('from core.infrastructure.event_bus.event_bus import get_event_bus, EventType',
     'from core.infrastructure.event_bus.unified_event_bus import get_event_bus, EventType'),
    ('from core.infrastructure.event_bus.event_bus import get_event_bus',
     'from core.infrastructure.event_bus.unified_event_bus import get_event_bus'),
    ('from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType',
     'from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, Event, EventType'),
    ('from core.infrastructure.event_bus.event_bus import EventBus',
     'from core.infrastructure.event_bus.event_bus_concurrent import EventBus as EventBusConcurrent'),
]


def update_file(filepath):
    """Обновление одного файла."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        for old, new in REPLACEMENTS:
            content = content.replace(old, new)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def main():
    files_updated = 0
    
    for root, dirs, files in os.walk('core'):
        # Исключаем директории
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for filename in files:
            if filename.endswith('.py') and filename not in EXCLUDE_FILES:
                filepath = os.path.join(root, filename)
                if update_file(filepath):
                    files_updated += 1
                    print(f"Updated: {filepath}")
    
    print(f"\nTotal files updated: {files_updated}")


if __name__ == '__main__':
    main()

"""Script to find non-target logging usage."""
import re
from pathlib import Path

PATTERNS = [
    (r'^import logging$', 'import logging'),
    (r'^logger = logging\.getLogger\(', 'logger = logging.getLogger'),
    (r'logger\.(debug|info|warning|error|exception)\(', 'logger.info/warning/error'),
    (r'from core\.infrastructure\.logging import EventBusLogger', 'EventBusLogger import'),
    (r'self\.event_bus_logger = EventBusLogger', 'EventBusLogger = new'),
    (r'await self\.event_bus_logger\.', 'event_bus_logger call'),
    (r'await self\.event_bus\.info\(|await self\.event_bus\.debug\(', 'event_bus.info/debug'),
]

def analyze_file(filepath):
    issues = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        for pattern, desc in PATTERNS:
            if re.search(pattern, line.strip()):
                issues.append({'line': i, 'content': line.strip()[:60], 'desc': desc})
    return issues

def main():
    core_dir = Path("core")
    all_issues = []
    for fp in core_dir.rglob("*.py"):
        issues = analyze_file(fp)
        if issues:
            all_issues.append((str(fp), issues))
    
    # Standard logging
    print("=== STANDARD LOGGING ===")
    for fp, issues in all_issues:
        for i in issues:
            if 'logger = logging.getLogger' in i['desc']:
                print(f"{fp}:{i['line']} -> {i['desc']}")
    
    # logger calls
    print("\n=== LOGGER CALLS ===")
    for fp, issues in all_issues:
        for i in issues:
            if 'logger.info' in i['desc']:
                print(f"{fp}:{i['line']} -> {i['desc']}")
    
    # EventBusLogger import
    print("\n=== EVENTBUSLOGGER IMPORT ===")
    for fp, issues in all_issues:
        for i in issues:
            if 'EventBusLogger import' in i['desc']:
                print(f"{fp}:{i['line']}")
    
    # event_bus_logger calls
    print("\n=== EVENT_BUS_LOGGER CALLS ===")
    for fp, issues in all_issues:
        for i in issues:
            if 'event_bus_logger call' in i['desc']:
                print(f"{fp}:{i['line']} -> {i['desc']}")
    
    total = sum(len(i) for _, i in all_issues)
    print(f"\n=== TOTAL: {total} issues ===")

if __name__ == "__main__":
    main()

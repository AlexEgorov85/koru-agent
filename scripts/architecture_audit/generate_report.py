#!/usr/bin/env python3
"""
Генерация сводного отчёта о соответствии архитектуре.
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CHECKS = [
    ("Направление зависимостей", "python scripts/architecture_audit/check_dependencies.py"),
    ("Циклические зависимости", "python scripts/architecture_audit/detect_cycles.py"),
    ("Дублирование конфигурации", "python scripts/architecture_audit/check_config_duplication.py"),
    ("Изоляция кэшей", "python -m pytest tests/architecture/test_cache_isolation.py -v"),
    ("Валидация манифестов", "python -m pytest tests/architecture/test_manifest_validation.py -v"),
    ("E2E архитектура", "python -m pytest tests/architecture/test_e2e_architecture.py -v"),
]

def run_check(name: str, command: str) -> tuple:
    """Запуск проверки и возврат результата."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def main():
    report = []
    report.append("=" * 60)
    report.append("ОТЧЁТ О СООТВЕТСТВИИ АРХИТЕКТУРЕ")
    report.append(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 60)
    report.append("")
    
    passed = 0
    failed = 0
    
    for name, command in CHECKS:
        print(f"Запуск проверки: {name}...")
        success, output = run_check(name, command)
        
        if success:
            status = "[PASS]"
            passed += 1
        else:
            status = "[FAIL]"
            failed += 1
        
        report.append(f"{status} | {name}")
        if not success:
            report.append(f"      {output[:200]}...")
    
    report.append("")
    report.append("=" * 60)
    report.append(f"ИТОГО: {passed} пройдено, {failed} провалено")
    report.append(f"Соответствие: {passed}/{passed+failed} ({100*passed/(passed+failed):.1f}%)")
    report.append("=" * 60)
    
    # Вывод отчёта
    for line in report:
        print(line)
    
    # Сохранение отчёта
    report_path = Path('reports/architecture_audit_report.txt')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"\nОтчёт сохранён: {report_path}")
    
    sys.exit(0 if failed == 0 else 1)

if __name__ == '__main__':
    main()
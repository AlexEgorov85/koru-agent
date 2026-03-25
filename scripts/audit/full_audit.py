#!/usr/bin/env python3
"""
Полный аудит проекта с детализацией по каждому элементу.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

from code_auditor import CodeAuditor, find_legacy_markers
from usage_tracker import UsageTracker


def generate_summary(code_report: Dict, usage_report: Dict, legacy_report: Dict) -> Dict:
    """Генерация сводного отчёта"""

    recommendations = []

    if usage_report.get('unused'):
        recommendations.append({
            'priority': 'HIGH',
            'category': 'DEAD_CODE',
            'description': f"Found {len(usage_report['unused'])} unused elements",
            'action': 'Remove or document',
            'files': list(set(u['locations'][0]['file'] for u in usage_report['unused'][:10]))
        })

    if usage_report.get('duplicates'):
        recommendations.append({
            'priority': 'MEDIUM',
            'category': 'DUPLICATION',
            'description': f"Found {len(usage_report['duplicates'])} duplicates",
            'action': 'Merge or remove',
            'files': list(set(
                loc['file'] for d in usage_report['duplicates'][:10] 
                for loc in d['locations']
            ))
        })

    legacy_markers = legacy_report.get('markers', {})
    if legacy_markers.get('deprecated', 0) > 0:
        recommendations.append({
            'priority': 'HIGH',
            'category': 'DEPRECATED',
            'description': f"Found {legacy_markers['deprecated']} deprecated elements",
            'action': 'Remove after migration',
            'files': list(set(
                m['file'] for m in legacy_report['details']['deprecated'][:10]
            ))
        })

    if legacy_markers.get('todo', 0) > 0:
        recommendations.append({
            'priority': 'MEDIUM',
            'category': 'TODO',
            'description': f"Found {legacy_markers['todo']} TODO items",
            'action': 'Review and complete',
            'files': list(set(
                m['file'] for m in legacy_report['details']['todo'][:10]
            ))
        })

    return {
        'timestamp': datetime.now().isoformat(),
        'code_stats': {
            'total_files': code_report.get('total_files', 0),
            'total_classes': code_report.get('total_classes', 0),
            'total_functions': code_report.get('total_functions', 0),
            'total_methods': code_report.get('total_methods', 0),
            'total_lines': code_report.get('total_lines', 0)
        },
        'usage_stats': {
            'unused_definitions': len(usage_report.get('unused', [])),
            'duplicate_definitions': len(usage_report.get('duplicates', []))
        },
        'legacy_stats': legacy_markers,
        'recommendations': recommendations
    }


def generate_text_summary(summary: Dict) -> str:
    """Генерация текстового отчёта"""

    lines = [
        "=" * 60,
        "PROJECT AUDIT SUMMARY",
        "=" * 60,
        "",
        f"Date: {summary['timestamp']}",
        "",
        "CODE STATISTICS:",
        f"  Files: {summary['code_stats']['total_files']}",
        f"  Classes: {summary['code_stats']['total_classes']}",
        f"  Functions: {summary['code_stats']['total_functions']}",
        f"  Methods: {summary['code_stats']['total_methods']}",
        f"  Lines: {summary['code_stats']['total_lines']}",
        "",
        "ISSUES:",
        f"  Unused elements: {summary['usage_stats']['unused_definitions']}",
        f"  Duplicates: {summary['usage_stats']['duplicate_definitions']}",
        "",
        "LEGACY MARKERS:",
    ]

    for marker_type, count in summary['legacy_stats'].items():
        if count > 0:
            lines.append(f"  {marker_type.upper()}: {count}")

    lines.extend([
        "",
        "RECOMMENDATIONS:",
    ])

    for i, rec in enumerate(summary['recommendations'], 1):
        lines.extend([
            "",
            f"{i}. [{rec['priority']}] {rec['category']}",
            f"   {rec['description']}",
            f"   Action: {rec['action']}",
            f"   Files: {len(rec['files'])}"
        ])

    lines.extend([
        "",
        "=" * 60
    ])

    return "\n".join(lines)


def run_full_audit(project_root: str, output_dir: str):
    """Запуск полного аудита"""

    project_path = Path(project_root)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("FULL PROJECT AUDIT")
    print("=" * 60)
    print(f"Project: {project_path}")
    print(f"Output: {output_path}")
    print()

    print("[1/3] Code audit...")
    code_auditor = CodeAuditor(project_path)
    code_report = code_auditor.analyze()

    with open(output_path / 'code_audit.json', 'w', encoding='utf-8') as f:
        json.dump(code_report, f, indent=2, ensure_ascii=False, default=str)

    print("[2/3] Usage tracking...")
    usage_tracker = UsageTracker(project_path)
    usage_tracker.scan_project()
    usage_report = usage_tracker.generate_report()

    with open(output_path / 'usage_audit.json', 'w', encoding='utf-8') as f:
        json.dump(usage_report, f, indent=2, ensure_ascii=False, default=str)

    print("[3/3] Legacy markers search...")
    legacy_report = find_legacy_markers(project_path)

    with open(output_path / 'legacy_audit.json', 'w', encoding='utf-8') as f:
        json.dump(legacy_report, f, indent=2, ensure_ascii=False, default=str)

    print()
    print("[*] Generating summary...")
    summary = generate_summary(code_report, usage_report, legacy_report)

    with open(output_path / 'audit_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    with open(output_path / 'audit_summary.txt', 'w', encoding='utf-8') as f:
        f.write(generate_text_summary(summary))

    print()
    print("=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)
    print(f"Reports saved to: {output_path}")
    print()

    print(generate_text_summary(summary))

    return summary


if __name__ == '__main__':
    import sys
    
    project_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'audit_output'
    
    run_full_audit(project_root, output_dir)

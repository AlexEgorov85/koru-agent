#!/usr/bin/env python3
"""
Скрипт валидации документации проекта Agent_v5.

Запуск:
    python scripts/validate_docs.py

Проверки:
- Валидность ссылок между документами
- Валидность Mermaid-диаграмм
- Отсутствие placeholder-текста
- Согласованность форматирования
"""

import re
import sys
import io
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

# Исправление кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


@dataclass
class ValidationResult:
    """Результат валидации"""
    file: str
    check: str
    passed: bool
    message: str = ""


class DocumentationValidator:
    """Валидатор документации"""
    
    def __init__(self, docs_path: str):
        self.docs_path = Path(docs_path)
        self.results: List[ValidationResult] = []
    
    def validate_all(self) -> List[ValidationResult]:
        """Запуск всех проверок"""
        self.results = []
        
        md_files = list(self.docs_path.rglob("*.md"))
        
        for file in md_files:
            self._check_links(file)
            self._check_mermaid_syntax(file)
            self._check_placeholders(file)
            self._check_formatting(file)
        
        return self.results
    
    def _check_links(self, file: Path):
        """Проверка валидности ссылок"""
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Поиск относительных ссылок
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        
        for text, link in links:
            if link.startswith("http"):
                continue  # Внешние ссылки не проверяем
            
            if link.startswith("./") or link.startswith("../"):
                # Относительная ссылка
                target = (file.parent / link).resolve()
                if not target.exists():
                    self.results.append(ValidationResult(
                        file=str(file.relative_to(self.docs_path)),
                        check="links",
                        passed=False,
                        message=f"Broken link: {link} -> {target}"
                    ))
    
    def _check_mermaid_syntax(self, file: Path):
        """Проверка синтаксиса Mermaid-диаграмм"""
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Поиск Mermaid блоков
        mermaid_blocks = re.findall(r'```mermaid(.*?)```', content, re.DOTALL)
        
        for i, block in enumerate(mermaid_blocks):
            # Базовая проверка синтаксиса
            if not block.strip():
                self.results.append(ValidationResult(
                    file=str(file.relative_to(self.docs_path)),
                    check="mermaid",
                    passed=False,
                    message=f"Empty mermaid block #{i+1}"
                ))
            
            # Проверка на наличие графа
            if not any(kw in block for kw in ["graph", "sequenceDiagram", "classDiagram", "stateDiagram"]):
                self.results.append(ValidationResult(
                    file=str(file.relative_to(self.docs_path)),
                    check="mermaid",
                    passed=False,
                    message=f"Invalid mermaid diagram type in block #{i+1}"
                ))
    
    def _check_placeholders(self, file: Path):
        """Проверка отсутствия placeholder-текста"""
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Поиск placeholder-паттернов
        placeholders = [
            r'\{\{[^}]+\}\}',  # {{placeholder}}
            r'{{TITLE}}',
            r'{{VERSION}}',
            r'{{DATE}}',
            r'{{STATUS}}',
            r'{{OWNER}}',
            r'{{description}}',
            r'{{Component',
            r'{{component',
        ]
        
        for pattern in placeholders:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                self.results.append(ValidationResult(
                    file=str(file.relative_to(self.docs_path)),
                    check="placeholders",
                    passed=False,
                    message=f"Found placeholder: {matches[0]}"
                ))
    
    def _check_formatting(self, file: Path):
        """Проверка согласованности форматирования"""
        with open(file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Проверка на trailing whitespace
        for i, line in enumerate(lines):
            if line.rstrip() != line.rstrip('\n'):
                self.results.append(ValidationResult(
                    file=str(file.relative_to(self.docs_path)),
                    check="formatting",
                    passed=False,
                    message=f"Line {i+1}: trailing whitespace"
                ))
        
        # Проверка заголовков
        content = "".join(lines)
        if not re.search(r'^#\s+.+$', content, re.MULTILINE):
            self.results.append(ValidationResult(
                file=str(file.relative_to(self.docs_path)),
                check="formatting",
                passed=False,
                message="No H1 heading found"
            ))
    
    def print_report(self):
        """Вывод отчёта о валидации"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        print("\n" + "=" * 60)
        print("📊 ОТЧЁТ О ВАЛИДАЦИИ ДОКУМЕНТАЦИИ")
        print("=" * 60)
        
        if failed == 0:
            print("\n✅ Все проверки пройдены!")
        else:
            print(f"\n❌ Найдено проблем: {failed}")
            print(f"✅ Успешно: {passed}")
            print(f"📁 Всего проверок: {total}")
            
            print("\n" + "-" * 60)
            print("Проблемы:")
            print("-" * 60)
            
            for result in self.results:
                if not result.passed:
                    print(f"\n📄 {result.file}")
                    print(f"   Проверка: {result.check}")
                    print(f"   ❌ {result.message}")
        
        print("\n" + "=" * 60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Валидация документации Agent_v5")
    parser.add_argument(
        "--docs",
        type=str,
        default="docs/",
        help="Директория с документацией"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Путь для сохранения отчёта (опционально)"
    )
    
    args = parser.parse_args()
    
    validator = DocumentationValidator(args.docs)
    results = validator.validate_all()
    validator.print_report()
    
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Отчёт о валидации документации\n\n")
            f.write(f"Всего проверок: {len(results)}\n")
            f.write(f"Успешно: {sum(1 for r in results if r.passed)}\n")
            f.write(f"Провалено: {sum(1 for r in results if not r.passed)}\n\n")
            
            for result in results:
                if not result.passed:
                    f.write(f"- **{result.file}** ({result.check}): {result.message}\n")
        
        print(f"\n📄 Отчёт сохранён: {output_path}")
    
    # Возврат кода выхода
    failed = sum(1 for r in results if not r.passed)
    exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

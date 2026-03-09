#!/usr/bin/env python3
"""
Скрипт для автоматической проверки архитектурных нарушений в навыках.

Проверяет:
1. Прямой доступ к реестру компонентов (application_context.components.get)
2. Прямой доступ к infrastructure_context
3. Импорт ComponentType для получения компонентов
4. Возврат ExecutionResult из _execute_impl (вместо данных)
5. Прямые вызовы LLM API
6. Наличие retry-логики в навыках

Использование:
    python scripts/validation/check_skill_architecture.py

Возвращает:
    - 0 если нарушений нет
    - 1 если найдены нарушения
"""
import ast
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ViolationType(Enum):
    """Типы архитектурных нарушений"""
    DIRECT_COMPONENT_ACCESS = "DIRECT_COMPONENT_ACCESS"
    DIRECT_INFRASTRUCTURE_ACCESS = "DIRECT_INFRASTRUCTURE_ACCESS"
    COMPONENT_TYPE_IMPORT = "COMPONENT_TYPE_IMPORT"
    EXECUTION_RESULT_RETURN = "EXECUTION_RESULT_RETURN"
    DIRECT_LLM_CALL = "DIRECT_LLM_CALL"
    RETRY_LOGIC = "RETRY_LOGIC"
    RANDOM_USAGE = "RANDOM_USAGE"


@dataclass
class Violation:
    """Нарушение архитектуры"""
    file_path: str
    line_number: int
    violation_type: ViolationType
    message: str
    code_snippet: str


# Запрещённые паттерны
FORBIDDEN_PATTERNS = {
    ViolationType.DIRECT_COMPONENT_ACCESS: [
        ".application_context.components.get",
        "application_context.components.get",
    ],
    ViolationType.DIRECT_INFRASTRUCTURE_ACCESS: [
        ".infrastructure_context",
        "application_context.infrastructure_context",
    ],
    ViolationType.DIRECT_LLM_CALL: [
        "openai.ChatCompletion",
        "openai.chat",
        "client.chat",
        "llm_client",
    ],
    ViolationType.RETRY_LOGIC: [
        "for attempt in range",
        "while retry",
        "range(3)",
    ],
    ViolationType.RANDOM_USAGE: [
        "import random",
        "from random",
        "random.",
    ],
}


def check_file_for_violations(file_path: Path) -> List[Violation]:
    """
    Проверка файла на архитектурные нарушения.

    Args:
        file_path: Путь к файлу

    Returns:
        Список нарушений
    """
    violations = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception as e:
        print(f"[WARN] Ошибка чтения файла {file_path}: {e}")
        return violations

    # Проверка на простые строковые паттерны
    for violation_type, patterns in FORBIDDEN_PATTERNS.items():
        for line_num, line in enumerate(lines, 1):
            for pattern in patterns:
                if pattern in line:
                    # Исключения для комментариев и тестов
                    stripped = line.strip()
                    if stripped.startswith('#') or 'test_' in str(file_path):
                        continue

                    violations.append(Violation(
                        file_path=str(file_path),
                        line_number=line_num,
                        violation_type=violation_type,
                        message=f"Найден запрещённый паттерн: {pattern}",
                        code_snippet=stripped[:100]
                    ))

    # Проверка импорта ComponentType
    if "from core.models.enums.common_enums import ComponentType" in content:
        for line_num, line in enumerate(lines, 1):
            if "ComponentType" in line and "import" in line:
                violations.append(Violation(
                    file_path=str(file_path),
                    line_number=line_num,
                    violation_type=ViolationType.COMPONENT_TYPE_IMPORT,
                    message="Импорт ComponentType для прямого доступа к компонентам",
                    code_snippet=line.strip()[:100]
                ))

    # AST-анализ для проверки возврата ExecutionResult из _execute_impl
    try:
        tree = ast.parse(content)
        violations.extend(check_ast_for_execution_result(tree, file_path, lines))
    except SyntaxError as e:
        print(f"[WARN] Ошибка парсинга AST {file_path}: {e}")

    return violations


def check_ast_for_execution_result(tree: ast.AST, file_path: Path, lines: List[str]) -> List[Violation]:
    """
    AST-анализ для проверки возврата ExecutionResult из _execute_impl.

    Args:
        tree: AST дерева
        file_path: Путь к файлу
        lines: Строки исходного кода

    Returns:
        Список нарушений
    """
    violations = []

    class ExecutionResultVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_execute_impl = False
            self.current_function = None

        def visit_FunctionDef(self, node):
            old_function = self.current_function
            self.current_function = node.name

            if node.name == '_execute_impl':
                old_in_execute_impl = self.in_execute_impl
                self.in_execute_impl = True
                self.generic_visit(node)
                self.in_execute_impl = old_in_execute_impl
            else:
                self.generic_visit(node)

            self.current_function = old_function

        def visit_Return(self, node):
            if self.in_execute_impl and node.value:
                # Проверяем возврат ExecutionResult
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Attribute):
                        if node.value.func.attr in ['success', 'failure']:
                            if isinstance(node.value.func.value, ast.Name):
                                if node.value.func.value.id == 'ExecutionResult':
                                    violations.append(Violation(
                                        file_path=str(file_path),
                                        line_number=node.lineno,
                                        violation_type=ViolationType.EXECUTION_RESULT_RETURN,
                                        message="_execute_impl возвращает ExecutionResult вместо данных",
                                        code_snippet=lines[node.lineno - 1].strip()[:100]
                                    ))
            self.generic_visit(node)

    visitor = ExecutionResultVisitor()
    visitor.visit(tree)
    return violations


def check_skills_directory(skills_dir: Path) -> Dict[str, List[Violation]]:
    """
    Проверка всех навыков в директории.

    Args:
        skills_dir: Директория с навыками

    Returns:
        Словарь {file_path: [violations]}
    """
    results = {}

    if not skills_dir.exists():
        print(f"[ERROR] Директория навыков не найдена: {skills_dir}")
        return results

    # Рекурсивный поиск всех .py файлов
    py_files = list(skills_dir.rglob("*.py"))

    for file_path in py_files:
        # Пропускаем тесты и __init__.py
        if 'test_' in str(file_path) or file_path.name == '__init__.py':
            continue

        violations = check_file_for_violations(file_path)
        if violations:
            results[str(file_path)] = violations

    return results


def print_violations_report(results: Dict[str, List[Violation]]) -> None:
    """
    Печать отчёта о нарушениях.

    Args:
        results: Результаты проверки
    """
    if not results:
        print("\n[OK] Нарушений архитектуры не найдено!")
        return

    total_violations = sum(len(v) for v in results.values())
    print(f"\n[ERROR] Найдено нарушений: {total_violations}")
    print("=" * 80)

    # Группировка по типам нарушений
    by_type: Dict[ViolationType, List[Violation]] = {}
    for file_path, violations in results.items():
        for violation in violations:
            if violation.violation_type not in by_type:
                by_type[violation.violation_type] = []
            by_type[violation.violation_type].append(violation)

    for violation_type, violations in by_type.items():
        print(f"\n[TYPE] {violation_type.value}: {len(violations)} нарушений")
        print("-" * 60)
        for v in violations:
            print(f"  [FILE] {v.file_path}:{v.line_number}")
            print(f"         {v.message}")
            print(f"         Код: {v.code_snippet}")
            print()

    print("=" * 80)
    print(f"Всего файлов с нарушениями: {len(results)}")
    print(f"Всего нарушений: {total_violations}")


def main():
    """Основная функция"""
    # Определяем директорию проекта
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    skills_dir = project_root / "core" / "application" / "skills"

    print("[CHECK] Проверка архитектуры навыков...")
    print(f"[CHECK] Директория навыков: {skills_dir}")

    results = check_skills_directory(skills_dir)
    print_violations_report(results)

    # Возвращаем код ошибки если есть нарушения
    sys.exit(1 if results else 0)


if __name__ == "__main__":
    main()

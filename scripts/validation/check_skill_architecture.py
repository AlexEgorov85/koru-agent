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
7. Использование parameters.get() БЕЗ предварительной валидации через input_contract
8. Наличие кастомных Input/Output классов вместо использования контрактов

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
    # Нарушения Declarative Contract Loading
    NO_INPUT_CONTRACT_USAGE = "NO_INPUT_CONTRACT_USAGE"
    NO_OUTPUT_CONTRACT_USAGE = "NO_OUTPUT_CONTRACT_USAGE"
    CUSTOM_INPUT_OUTPUT_CLASSES = "CUSTOM_INPUT_OUTPUT_CLASSES"


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
    # Исключения для retry-логики (допустимые случаи)
    # Retry logic в навыках и сервисах для обработки transient ошибок LLM и коррекции SQL
    # Эти случаи закомментированы в коде с меткой ARCHITECTURE: Retry logic
    ViolationType.RANDOM_USAGE: [
        "import random",
        "from random",
        "random.",
    ],
    # Кастомные Input/Output классы (нарушение Declarative Contract Loading)
    ViolationType.CUSTOM_INPUT_OUTPUT_CLASSES: [
        "class SQLValidatorServiceInput",
        "class SQLValidatorServiceOutput",
        "class ServiceInput:",
        "class ServiceOutput:",
        "Input:\n",
        "Output:\n",
    ],
}

# Паттерны для поиска нарушений Declarative Contract Loading
CONTRACT_VIOLATION_PATTERNS = {
    # Поиск _execute_impl без использования get_input_contract или get_output_contract
    "execute_without_contracts": {
        "violation_type": ViolationType.NO_INPUT_CONTRACT_USAGE,
        "check": "has_execute_impl_no_contracts"
    }
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
                    
                    # Исключение для retry-логики с архитектурным комментарием
                    if violation_type == ViolationType.RETRY_LOGIC:
                        # Проверяем, есть ли в этой или соседних строках комментарий ARCHITECTURE: Retry logic
                        context_start = max(0, line_num - 2)
                        context_end = min(len(lines), line_num + 2)
                        context = '\n'.join(lines[context_start:context_end])
                        if 'ARCHITECTURE: Retry logic' in context:
                            continue  # Пропускаем допустимую retry-логику

                    violations.append(Violation(
                        file_path=str(file_path),
                        line_number=line_num,
                        violation_type=violation_type,
                        message=f"Найден запрещённый паттерн: {pattern}",
                        code_snippet=stripped
                    ))

    # Проверка импорта ComponentType
    # ARCHITECTURE: Импорт ComponentType допускается только в registry/component_registry.py
    if "from core.models.enums.common_enums import ComponentType" in content:
        # Исключение для component_registry.py - это легальное использование
        if 'registry/component_registry.py' not in str(file_path):
            for line_num, line in enumerate(lines, 1):
                if "ComponentType" in line and "import" in line:
                    violations.append(Violation(
                        file_path=str(file_path),
                        line_number=line_num,
                        violation_type=ViolationType.COMPONENT_TYPE_IMPORT,
                        message="Импорт ComponentType для прямого доступа к компонентам",
                        code_snippet=line.strip()
                    ))

    # AST-анализ для проверки возврата ExecutionResult из _execute_impl
    try:
        tree = ast.parse(content)
        violations.extend(check_ast_for_execution_result(tree, file_path, lines))
        # AST-анализ для проверки использования контрактов в _execute_impl
        violations.extend(check_ast_for_contract_usage(tree, file_path, lines))
    except SyntaxError as e:
        print(f"[WARN] Ошибка парсинга AST {file_path}: {e}")

    return violations


def check_ast_for_contract_usage(tree: ast.AST, file_path: Path, lines: List[str]) -> List[Violation]:
    """
    AST-анализ для проверки использования декларативных контрактов в _execute_impl.
    
    Проверяет:
    1. Наличие get_input_contract или get_output_contract в _execute_impl
    2. Отсутствие model_validate для выходных данных
    
    Args:
        tree: AST дерева
        file_path: Путь к файлу
        lines: Строки исходного кода
        
    Returns:
        Список нарушений
    """
    violations = []
    
    class ContractUsageVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_execute_impl = False
            self.has_get_input_contract = False
            self.has_get_output_contract = False
            self.has_model_validate = False
            self.execute_impl_line = 0
            
        def visit_FunctionDef(self, node):
            if node.name == '_execute_impl':
                self.in_execute_impl = True
                self.has_get_input_contract = False
                self.has_get_output_contract = False
                self.has_model_validate = False
                self.execute_impl_line = node.lineno
                self.generic_visit(node)
                
                # После обхода проверяем наличие контрактов
                # Пропускаем сервисы с динамическими схемами (json_parsing)
                file_path_str = str(file_path)
                is_dynamic_schema_service = 'json_parsing' in file_path_str
                
                if not is_dynamic_schema_service:
                    if not self.has_get_input_contract:
                        violations.append(Violation(
                            file_path=str(file_path),
                            line_number=self.execute_impl_line,
                            violation_type=ViolationType.NO_INPUT_CONTRACT_USAGE,
                            message="_execute_impl не использует get_input_contract()",
                            code_snippet=lines[self.execute_impl_line - 1].strip() if self.execute_impl_line <= len(lines) else ""
                        ))
                    
                    if not self.has_get_output_contract and not self.has_model_validate:
                        violations.append(Violation(
                            file_path=str(file_path),
                            line_number=self.execute_impl_line,
                            violation_type=ViolationType.NO_OUTPUT_CONTRACT_USAGE,
                            message="_execute_impl не использует get_output_contract() или model_validate()",
                            code_snippet=lines[self.execute_impl_line - 1].strip() if self.execute_impl_line <= len(lines) else ""
                        ))
                
                self.in_execute_impl = False
            else:
                self.generic_visit(node)
        
        def visit_Call(self, node):
            if self.in_execute_impl:
                # Проверяем вызовы get_input_contract / get_output_contract
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['get_input_contract', 'get_output_contract']:
                        if node.func.attr == 'get_input_contract':
                            self.has_get_input_contract = True
                        elif node.func.attr == 'get_output_contract':
                            self.has_get_output_contract = True
                    # Проверяем model_validate (альтернативный способ валидации выхода)
                    if node.func.attr == 'model_validate':
                        self.has_model_validate = True
            self.generic_visit(node)
    
    visitor = ContractUsageVisitor()
    visitor.visit(tree)
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
                                        code_snippet=lines[node.lineno - 1].strip()
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
    import argparse
    parser = argparse.ArgumentParser(description="Проверка архитектуры компонентов")
    parser.add_argument("--skills", action="store_true", help="Проверить только навыки")
    parser.add_argument("--services", action="store_true", help="Проверить только сервисы")
    parser.add_argument("--tools", action="store_true", help="Проверить только инструменты")
    parser.add_argument("--all", action="store_true", help="Проверить все компоненты")
    parser.add_argument("--quiet", action="store_true", help="Не выводить предупреждения")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    dirs_to_check = []
    if args.all or (not args.skills and not args.services and not args.tools):
        dirs_to_check = [
            project_root / "core" / "components" / "skills",
            project_root / "core" / "components" / "services",
            project_root / "core" / "components" / "tools",
        ]
    else:
        if args.skills:
            dirs_to_check.append(project_root / "core" / "components" / "skills")
        if args.services:
            dirs_to_check.append(project_root / "core" / "components" / "services")
        if args.tools:
            dirs_to_check.append(project_root / "core" / "components" / "tools")

    all_results = {}
    for check_dir in dirs_to_check:
        if not args.quiet:
            print(f"\n[CHECK] Проверка: {check_dir.name}")
        results = check_skills_directory(check_dir)
        all_results.update(results)

    print_violations_report(all_results)
    sys.exit(1 if all_results else 0)


if __name__ == "__main__":
    main()

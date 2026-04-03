"""
AST/YAML валидатор для сгенерированных артефактов компонентов.

АРХИТЕКТУРА:
- ComponentValidator: проверяет Python-файлы через AST и YAML через safe_load
- Поддержка всех типов: skill, tool, service, behavior
- Запрещённые импорты и вызовы блокируются
- Обязательные паттерны (наследование, _execute_impl) проверяются по типу
"""
import ast
import yaml
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


DANGEROUS_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "ctypes",
    "multiprocessing", "socket", "http", "urllib", "requests",
    "pickle", "marshal", "eval", "exec", "__import__",
    "importlib", "importlib.util", "importlib.machinery",
}

SAFE_IMPORTS_PREFIXES = {
    "core.", "typing", "datetime", "json", "re", "pathlib",
    "pydantic", "enum", "abc", "logging", "time", "math",
    "collections", "itertools", "functools", "dataclasses",
    "hashlib", "hmac", "secrets", "string", "textwrap",
    "uuid", "copy", "io", "contextlib",
}

TYPE_BASE_CLASSES = {
    "skill": "BaseSkill",
    "tool": "BaseTool",
    "service": "BaseService",
    "behavior": "BaseBehaviorPattern",
}

TYPE_MAIN_FILES = {
    "skill": "skill.py",
    "tool": None,
    "service": "service.py",
    "behavior": "pattern.py",
}

REQUIRED_METHODS = {"_execute_impl", "get_capabilities"}


class ValidationFinding:
    """Отдельная находка валидатора."""

    def __init__(self, level: str, message: str, file: str = "", line: int = 0):
        self.level = level
        self.message = message
        self.file = file
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "message": self.message,
            "file": self.file,
            "line": self.line,
        }


class ComponentValidator:
    """Валидатор сгенерированных артефактов любого типа компонента."""

    def validate_artifacts(
        self,
        python_files: Dict[str, str],
        yaml_files: Dict[str, str],
        component_name: str = "",
        component_type: str = "skill",
    ) -> Dict[str, Any]:
        """
        Комплексная валидация всех артефактов компонента.

        ARGS:
        - python_files: dict {filename: content}
        - yaml_files: dict {filename: content}
        - component_name: ожидаемое имя компонента
        - component_type: тип — 'skill', 'tool', 'service', 'behavior'

        RETURNS:
        - dict с полями: is_valid, errors, warnings, findings
        """
        findings: List[ValidationFinding] = []

        main_file = self._get_main_file(component_type)

        for filename, content in python_files.items():
            is_main = (filename == main_file) if main_file else (component_name and component_name in filename)
            findings.extend(self._validate_python_file(filename, content, component_name, component_type, is_main))

        for filename, content in yaml_files.items():
            findings.extend(self._validate_yaml_file(filename, content))

        findings.extend(self._validate_cross_artifacts(python_files, yaml_files, component_name, component_type))

        errors = [f for f in findings if f.level == "error"]
        warnings = [f for f in findings if f.level == "warning"]

        return {
            "is_valid": len(errors) == 0,
            "errors": [e.to_dict() for e in errors],
            "warnings": [w.to_dict() for w in warnings],
            "findings": [f.to_dict() for f in findings],
            "error_count": len(errors),
            "warning_count": len(warnings),
        }

    def _get_main_file(self, component_type: str) -> Optional[str]:
        return TYPE_MAIN_FILES.get(component_type)

    def _validate_python_file(
        self,
        filename: str,
        content: str,
        component_name: str = "",
        component_type: str = "skill",
        is_main: bool = False,
    ) -> List[ValidationFinding]:
        """Валидация одного Python-файла через AST."""
        findings: List[ValidationFinding] = []

        if not filename.endswith(".py"):
            return findings

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            findings.append(ValidationFinding(
                level="error",
                message=f"SyntaxError: {e.msg}",
                file=filename,
                line=e.lineno or 0,
            ))
            return findings

        findings.extend(self._check_imports(tree, filename))
        findings.extend(self._check_dangerous_calls(tree, filename))

        if is_main and component_name:
            findings.extend(self._check_component_structure(tree, filename, component_name, component_type))

        return findings

    def _check_imports(
        self, tree: ast.AST, filename: str
    ) -> List[ValidationFinding]:
        """Проверка импортов на безопасность."""
        findings: List[ValidationFinding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._validate_import_name(alias.name, filename, node.lineno, findings)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self._validate_import_name(module, filename, node.lineno, findings)

        return findings

    def _validate_import_name(
        self,
        module: str,
        filename: str,
        lineno: int,
        findings: List[ValidationFinding],
    ) -> None:
        """Проверка одного имени импорта."""
        top_level = module.split(".")[0]

        if top_level in DANGEROUS_IMPORTS or module in DANGEROUS_IMPORTS:
            findings.append(ValidationFinding(
                level="error",
                message=f"Запрещённый импорт: '{module}'",
                file=filename,
                line=lineno,
            ))
            return

        is_safe_prefix = any(
            module.startswith(prefix) for prefix in SAFE_IMPORTS_PREFIXES
        )

        if not is_safe_prefix:
            findings.append(ValidationFinding(
                level="warning",
                message=f"Неизвестный импорт: '{module}' (не в белом списке)",
                file=filename,
                line=lineno,
            ))

    def _check_dangerous_calls(
        self, tree: ast.AST, filename: str
    ) -> List[ValidationFinding]:
        """Поиск вызовов eval(), exec(), compile() и т.д."""
        findings: List[ValidationFinding] = []
        dangerous_funcs = {"eval", "exec", "compile", "__import__"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                func_name = None
                if isinstance(func, ast.Name):
                    func_name = func.id
                elif isinstance(func, ast.Attribute):
                    func_name = func.attr

                if func_name in dangerous_funcs:
                    findings.append(ValidationFinding(
                        level="error",
                        message=f"Запрещённый вызов: '{func_name}()'",
                        file=filename,
                        line=node.lineno,
                    ))

        return findings

    def _check_component_structure(
        self, tree: ast.AST, filename: str, component_name: str, component_type: str
    ) -> List[ValidationFinding]:
        """Проверка структуры: наследование правильного базового класса, обязательные методы."""
        findings: List[ValidationFinding] = []
        expected_base = TYPE_BASE_CLASSES.get(component_type, "BaseSkill")
        suffix = {"skill": "Skill", "tool": "Tool", "service": "Service", "behavior": "Pattern"}.get(component_type, "Skill")
        expected_class = f"{component_name.title().replace('_', '')}{suffix}"
        found_class = ""
        has_correct_base = False
        found_methods: set = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == expected_base:
                        has_correct_base = True
                        found_class = node.name
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name in REQUIRED_METHODS:
                            found_methods.add(item.name)

        if not has_correct_base:
            findings.append(ValidationFinding(
                level="error",
                message=f"Класс должен наследовать {expected_base} (тип: {component_type})",
                file=filename,
            ))

        missing_methods = REQUIRED_METHODS - found_methods
        for method in missing_methods:
            findings.append(ValidationFinding(
                level="error",
                message=f"Отсутствует обязательный метод: '{method}'",
                file=filename,
            ))

        if found_class and found_class != expected_class:
            findings.append(ValidationFinding(
                level="warning",
                message=f"Ожидался класс '{expected_class}', найден '{found_class}'",
                file=filename,
            ))

        return findings

    def _validate_yaml_file(
        self, filename: str, content: str
    ) -> List[ValidationFinding]:
        """Валидация YAML-файла."""
        findings: List[ValidationFinding] = []

        if not filename.endswith((".yaml", ".yml")):
            return findings

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            findings.append(ValidationFinding(
                level="error",
                message=f"YAMLError: {e}",
                file=filename,
            ))
            return findings

        if data is None:
            findings.append(ValidationFinding(
                level="error",
                message="YAML-файл пустой или содержит только комментарии",
                file=filename,
            ))
            return findings

        if not isinstance(data, dict):
            findings.append(ValidationFinding(
                level="error",
                message="YAML-файл должен содержать mapping (dict) на верхнем уровне",
                file=filename,
            ))
            return findings

        is_contract = (
            "contract" in filename.lower()
            or "_input_" in filename.lower()
            or "_output_" in filename.lower()
        )

        if "prompt" in filename.lower() or "system" in filename.lower() or "user" in filename.lower():
            if "content" not in data:
                findings.append(ValidationFinding(
                    level="error",
                    message="Промпт должен содержать поле 'content'",
                    file=filename,
                ))
            if "version" not in data:
                findings.append(ValidationFinding(
                    level="warning",
                    message="Промпт должен содержать поле 'version'",
                    file=filename,
                ))

        if is_contract:
            if "schema_data" not in data:
                findings.append(ValidationFinding(
                    level="error",
                    message="Контракт должен содержать поле 'schema_data'",
                    file=filename,
                ))
            if "direction" not in data:
                findings.append(ValidationFinding(
                    level="warning",
                    message="Контракт должен содержать поле 'direction' (input/output)",
                    file=filename,
                ))

        return findings

    def _validate_cross_artifacts(
        self,
        python_files: Dict[str, str],
        yaml_files: Dict[str, str],
        component_name: str,
        component_type: str,
    ) -> List[ValidationFinding]:
        """Кросс-проверки между артефактами."""
        findings: List[ValidationFinding] = []

        if not python_files:
            findings.append(ValidationFinding(
                level="error",
                message="Отсутствуют Python-файлы",
            ))

        main_file = self._get_main_file(component_type)
        if main_file and component_name:
            has_main = any(fn == main_file for fn in python_files)
            if not has_main:
                findings.append(ValidationFinding(
                    level="error",
                    message=f"Отсутствует основной файл {main_file}",
                ))

        return findings


SkillValidator = ComponentValidator

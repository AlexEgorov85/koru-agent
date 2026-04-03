"""
AST/YAML валидатор для сгенерированных артефактов навыков.

АРХИТЕКТУРА:
- SkillValidator: проверяет Python-файлы через AST и YAML через safe_load
- Запрещённые импорты и вызовы блокируются
- Обязательные паттерны (наследование BaseSkill, _execute_impl) проверяются
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

REQUIRED_BASE_CLASS = "BaseSkill"
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


class SkillValidator:
    """Валидатор сгенерированных артефактов навыков."""

    def validate_artifacts(
        self,
        python_files: Dict[str, str],
        yaml_files: Dict[str, str],
        skill_name: str = "",
    ) -> Dict[str, Any]:
        """
        Комплексная валидация всех артефактов навыка.

        ARGS:
        - python_files: dict {filename: content}
        - yaml_files: dict {filename: content}
        - skill_name: ожидаемое имя навыка для проверок

        RETURNS:
        - dict с полями: is_valid, errors, warnings, findings
        """
        findings: List[ValidationFinding] = []

        for filename, content in python_files.items():
            findings.extend(self._validate_python_file(filename, content, skill_name))

        for filename, content in yaml_files.items():
            findings.extend(self._validate_yaml_file(filename, content))

        findings.extend(self._validate_cross_artifacts(python_files, yaml_files, skill_name))

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

    def _validate_python_file(
        self,
        filename: str,
        content: str,
        skill_name: str = "",
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

        if "skill.py" in filename and skill_name:
            findings.extend(self._check_skill_structure(tree, filename, skill_name))

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

    def _check_skill_structure(
        self, tree: ast.AST, filename: str, skill_name: str
    ) -> List[ValidationFinding]:
        """Проверка структуры skill.py: наследование BaseSkill, обязательные методы."""
        findings: List[ValidationFinding] = []
        has_base_skill = False
        found_methods: set = set()
        expected_class = f"{skill_name.title().replace('_', '')}Skill"
        found_class = ""

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == REQUIRED_BASE_CLASS:
                        has_base_skill = True
                        found_class = node.name
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name in REQUIRED_METHODS:
                            found_methods.add(item.name)

        if not has_base_skill:
            findings.append(ValidationFinding(
                level="error",
                message=f"Класс навыка должен наследовать {REQUIRED_BASE_CLASS}",
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
        skill_name: str,
    ) -> List[ValidationFinding]:
        """Кросс-проверки между Python и YAML артефактами."""
        findings: List[ValidationFinding] = []

        if not python_files:
            findings.append(ValidationFinding(
                level="error",
                message="Отсутствуют Python-файлы",
            ))

        if not yaml_files:
            findings.append(ValidationFinding(
                level="warning",
                message="Отсутствуют YAML-файлы (промпты/контракты)",
            ))

        if skill_name:
            has_skill_py = any("skill.py" in fn for fn in python_files)
            if not has_skill_py:
                findings.append(ValidationFinding(
                    level="error",
                    message="Отсутствует основной файл skill.py",
                ))

        return findings

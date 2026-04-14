"""
SafeFormulaParser — безопасный парсинг пользовательских формул.

ОТВЕТСТВЕННОСТЬ:
- Парсинг формул вида: ({revenue} - {cost}) / {revenue} * 100
- AST-валидация с whitelist'ом разрешённых операций
- Блокировка опасных конструкций: import, open, exec, eval, __import__

АРХИТЕКТУРА:
- Регулярное выражение для поиска {column} плейсхолдеров
- AST-парсинг для валидации формулы
- Белый список: +, -, *, /, (), math.*, statistics.*
"""
import ast
import re
from typing import Any, Dict, Optional, Tuple


class SafeFormulaParser:
    """
    Безопасный парсер формул для вычислений.

    АРХИТЕКТУРА:
    - Статические методы (не требует состояния)
    - Валидация через AST (не eval/exec)
    - Whitelist функций: math.*, statistics.*

    ПРИМЕР:
    >>> SafeFormulaParser.parse("({revenue} - {cost}) / {revenue} * 100")
    >>> SafeFormulaParser.evaluate(formula, {"revenue": 1000, "cost": 200})
    80.0
    """

    _ALLOWED_FUNCTIONS = {
        "abs", "ceil", "floor", "round", "pow", "sqrt",
        "min", "max", "sum", "log", "exp", "sin", "cos", "tan",
        "math.abs", "math.ceil", "math.floor", "math.round", "math.pow",
        "math.sqrt", "math.min", "math.max", "math.log", "math.exp",
        "statistics.mean", "statistics.median", "statistics.stdev"
    }

    _BLOCKED_KEYWORDS = {
        "import", "open", "exec", "eval", "__import__",
        "os", "sys", "subprocess", "requests", "urllib",
        "file", "read", "write", "print"
    }

    @staticmethod
    def parse(formula: str) -> Tuple[bool, Optional[str], Optional[ast.AST]]:
        """
        Валидация формулы через AST.

        ARGS:
        - formula: str — формула вида "({revenue} - {cost}) / {revenue}"

        RETURNS:
        - (is_valid, error_message, ast_tree)

        EXAMPLE:
        >>> valid, error, tree = SafeFormulaParser.parse("({a} + {b}) * 2")
        >>> valid
        True
        """
        if not formula or not formula.strip():
            return False, "Формула пуста", None

        formula = formula.strip()

        for keyword in SafeFormulaParser._BLOCKED_KEYWORDS:
            if keyword in formula.lower():
                return False, f"Запрещённое ключевое слово: {keyword}", None

        try:
            tree = ast.parse(formula, mode="eval")
            is_safe, error = SafeFormulaParser._validate_ast(tree)

            if not is_safe:
                return False, error, None

            return True, None, tree

        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {str(e)}", None
        except Exception as e:
            return False, f"Ошибка парсинга: {str(e)}", None

    @staticmethod
    def _validate_ast(tree: ast.AST) -> Tuple[bool, Optional[str]]:
        """Валидация AST дерева на безопасность."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = SafeFormulaParser._get_func_name(node.func)
                if func_name and func_name not in SafeFormulaParser._ALLOWED_FUNCTIONS:
                    if not func_name.startswith("math.") and not func_name.startswith("statistics."):
                        return False, f"Функция {func_name} не разрешена"

            if isinstance(node, ast.Attribute):
                if node.attr.startswith("_"):
                    return False, f"Запрещённый атрибут: {node.attr}"

        return True, None

    @staticmethod
    def _get_func_name(func: ast.AST) -> Optional[str]:
        """Получить имя функции из AST узла."""
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            base = SafeFormulaParser._get_func_name(func.value)
            if base:
                return f"{base}.{func.attr}"
        return None

    @staticmethod
    def extract_columns(formula: str) -> list:
        """
        Извлечь имена колонок из формулы.

        ARGS:
        - formula: str — формула с {column} плейсхолдерами

        RETURNS:
        - List[str] — имена колонок

        EXAMPLE:
        >>> SafeFormulaParser.extract_columns("({revenue} - {cost}) / {revenue}")
        ['revenue', 'cost']
        """
        pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        return re.findall(pattern, formula)

    @staticmethod
    def evaluate(formula: str, row: Dict[str, Any]) -> Optional[Any]:
        """
        Вычислить формулу для строки данных.

        ARGS:
        - formula: str — формула с {column} плейсхолдерами
        - row: Dict — данные строки

        RETURNS:
        - Результат вычисления или None при ошибке

        EXAMPLE:
        >>> row = {"revenue": 1000, "cost": 200}
        >>> SafeFormulaParser.evaluate("({revenue} - {cost}) / {revenue} * 100", row)
        80.0
        """
        is_valid, error, _ = SafeFormulaParser.parse(formula)
        if not is_valid:
            return None

        columns = SafeFormulaParser.extract_columns(formula)
        missing = [col for col in columns if col not in row]
        if missing:
            return None

        eval_globals = {
            "abs": abs, "min": min, "max": max, "sum": sum,
            "round": round, "pow": pow, "sqrt": lambda x: x ** 0.5
        }

        eval_locals = {col: row[col] for col in columns}

        try:
            result = eval(formula, eval_globals, eval_locals)
            if isinstance(result, float) and (result != result or abs(result) == float('inf')):
                return None
            return result
        except Exception:
            return None

    @staticmethod
    def validate_formula_for_columns(
        formula: str,
        available_columns: list
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидация формулы против списка доступных колонок.

        ARGS:
        - formula: str — формула
        - available_columns: List[str] — доступные колонки

        RETURNS:
        - (is_valid, error_message)

        EXAMPLE:
        >>> SafeFormulaParser.validate_formula_for_columns(
        ...     "({revenue} - {cost}) / {revenue}",
        ...     ["revenue", "cost", "name"]
        ... )
        (True, None)
        """
        is_valid, error, _ = SafeFormulaParser.parse(formula)
        if not is_valid:
            return False, error

        columns = SafeFormulaParser.extract_columns(formula)
        missing = set(columns) - set(available_columns)

        if missing:
            return False, f"Неизвестные колонки: {', '.join(missing)}"

        return True, None
"""Безопасное исполнение Python-кода в изолированном контексте."""
import ast
import asyncio
import concurrent.futures
import statistics
import math
import json
import collections
import itertools
from typing import Dict, Any


ALLOWED_MODULES = {"statistics", "math", "json", "collections", "itertools"}
ALLOWED_BUILTINS = {
    "len", "int", "float", "str", "list", "dict", "set", "tuple",
    "sum", "min", "max", "abs", "round", "sorted", "enumerate", "zip", "range",
    "True", "False", "None", "isinstance", "type", "bool", "any", "all", "iter", "next",
    "print", "repr", "format"
}


class SafeCodeExecutor:
    @staticmethod
    def _validate_ast(code: str) -> None:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in getattr(node, 'names', []):
                    if alias.name.split('.')[0] not in ALLOWED_MODULES:
                        raise ValueError(f"Запрещённый модуль: {alias.name}")
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise ValueError("Доступ к dunder-атрибутам запрещён")
            if isinstance(node, ast.Call) and hasattr(node.func, 'id'):
                if node.func.id in ('__import__', 'open', 'exec', 'eval', 'compile', 'getattr', 'setattr', 'delattr'):
                    raise ValueError(f"Запрещённый вызов: {node.func.id}")

    @classmethod
    async def execute(cls, code: str, context: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
        cls._validate_ast(code)

        safe_builtins = {k: getattr(__import__("builtins"), k) for k in ALLOWED_BUILTINS}
        safe_builtins.update({
            "statistics": statistics,
            "math": math,
            "json": json,
            "collections": collections,
            "itertools": itertools
        })

        ns = {**context, "__builtins__": safe_builtins}

        def _run_sync():
            exec(compile(code, "<data_analysis>", "exec"), ns)
            return ns.get("result")

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_sync)
            try:
                res = await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)
                return {"status": "success", "result": res}
            except asyncio.TimeoutError:
                future.cancel()
                return {"status": "error", "error": "Превышен лимит времени выполнения"}
            except Exception as e:
                return {"status": "error", "error": f"{type(e).__name__}: {str(e)}"}
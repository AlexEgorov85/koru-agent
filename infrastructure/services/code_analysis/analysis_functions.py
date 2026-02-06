"""
Функции для статического анализа Python-кода.
"""
import ast
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid

from domain.models.code.code_unit import CodeUnit, CodeUnitType, Location, CodeSpan
from domain.models.code.signature import ParameterInfo, CodeSignature

# Определяем модели для зависимостей
from pydantic import BaseModel, Field
from enum import Enum

class SymbolType(str, Enum):
    """
    Типы символов в коде.
    """
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    VARIABLE = "variable"
    CONSTANT = "constant"
    PARAMETER = "parameter"
    ATTRIBUTE = "attribute"
    IMPORT = "import"
    IMPORT_FROM = "import_from"
    MODULE = "module"

class Dependency(BaseModel):
    """
    Модель для представления зависимости (импорта).
    """
    type: SymbolType = Field(..., description="Тип символа")
    name: str = Field(..., description="Имя зависимости")
    alias: Optional[str] = Field(None, description="Псевдоним импорта")
    module: Optional[str] = Field(None, description="Имя модуля (для from ... import ...)")
    is_relative: bool = Field(False, description="Относительный импорт")
    level: int = Field(0, description="Уровень вложенности для относительных импортов")


def parse(source_code: str, source_bytes: bytes) -> ast.AST:
    """
    Парсит исходный код в AST.
    
    Args:
        source_code: Исходный код в виде строки
        source_bytes: Исходный код в виде байтов
        
    Returns:
        AST дерево
    """
    try:
        return ast.parse(source_code)
    except SyntaxError as e:
        raise ValueError(f"Ошибка синтаксиса в Python-коде: {str(e)}")


def parse_file(path: str) -> ast.AST:
    """
    Парсит файл в AST.
    
    Args:
        path: Путь к файлу
        
    Returns:
        AST дерево
    """
    with open(path, 'r', encoding='utf-8') as file:
        source_code = file.read()
        source_bytes = source_code.encode('utf-8')
        return parse(source_code, source_bytes)


def get_outline(ast_tree: ast.AST, file_path: str) -> List[CodeUnit]:
    """
    Получает структуру файла (классы, функции и т.д.).
    
    Args:
        ast_tree: AST дерево
        file_path: Путь к файлу
        
    Returns:
        Список CodeUnit
    """
    return build_code_units(ast_tree, file_path)


def extract_dependencies(ast_tree: ast.AST) -> List[Dependency]:
    """
    Извлекает зависимости из AST.
    
    Args:
        ast_tree: AST дерево
        
    Returns:
        Список Dependency
    """
    dependencies = []
    
    for node in ast.walk(ast_tree):
        if isinstance(node, ast.Import):
            # Обработка import x, y, z
            for alias in node.names:
                dependencies.append(
                    Dependency(
                        type=SymbolType.IMPORT,
                        name=alias.name,
                        alias=alias.asname
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            # Обработка from module import x, y, z
            module = node.module or ''
            
            # Проверяем, является ли импорт относительным
            is_relative = node.level > 0
            
            for alias in node.names:
                dependencies.append(
                    Dependency(
                        type=SymbolType.IMPORT_FROM,
                        name=alias.name,
                        alias=alias.asname,
                        module=module,
                        is_relative=is_relative,
                        level=node.level
                    )
                )
    
    return dependencies


def build_code_units(ast_tree: ast.AST, file_path: str) -> List[CodeUnit]:
    """
    Создает CodeUnit из AST.
    
    Args:
        ast_tree: AST дерево
        file_path: Путь к файлу
        
    Returns:
        Список CodeUnit
    """
    units = []
    
    for node in ast.iter_child_nodes(ast_tree):
        unit = _create_code_unit(node, file_path)
        if unit:
            units.append(unit)
    
    return units


def navigate_symbols(code_units: List[CodeUnit], symbol_name: str) -> Optional[CodeUnit]:
    """
    Находит символ в списке CodeUnit.
    
    Args:
        code_units: Список CodeUnit
        symbol_name: Имя символа для поиска
        
    Returns:
        CodeUnit или None
    """
    for unit in code_units:
        if unit.name == symbol_name:
            return unit
        # Проверяем дочерние элементы
        for child in unit.children:
            if child.name == symbol_name:
                return child
    
    return None


def resolve_import(import_name: str, current_file: str, project_files: List[str]) -> Optional[str]:
    """
    Разрешает импорт в путь к файлу.
    
    Args:
        import_name: Имя импорта
        current_file: Текущий файл (относительно которого разрешается импорт)
        project_files: Список файлов проекта
        
    Returns:
        Путь к файлу или None
    """
    current_dir = Path(current_file).parent
    
    # Если имя импорта начинается с точки, это относительный импорт
    if import_name.startswith('.'):
        # Подсчитываем количество точек
        level = 0
        for char in import_name:
            if char == '.':
                level += 1
            else:
                break
        
        # Получаем оставшуюся часть имени
        remaining_name = import_name[level:]
        
        # Поднимаемся на уровень выше столько раз, сколько точек
        target_dir = current_dir
        for _ in range(level - 1):  # -1 потому что одна точка означает текущую директорию
            target_dir = target_dir.parent
        
        # Преобразуем имя модуля в путь
        module_parts = remaining_name.split('.')
        module_path = target_dir.joinpath(*module_parts[:-1]).joinpath(module_parts[-1] + '.py')
        
        # Проверяем, существует ли такой файл
        if str(module_path) in project_files:
            return str(module_path)
        
        # Также проверяем как пакет (__init__.py)
        package_path = target_dir.joinpath(*module_parts).joinpath('__init__.py')
        if str(package_path) in project_files:
            return str(package_path)
        
        return None
    else:
        # Абсолютный импорт - ищем в проекте
        module_parts = import_name.split('.')
        
        for file_path in project_files:
            path_obj = Path(file_path)
            
            # Проверяем соответствие пути имени модуля
            if _matches_module_path(path_obj, module_parts):
                return file_path
        
        return None


def _matches_module_path(file_path: Path, module_parts: List[str]) -> bool:
    """
    Проверяет, соответствует ли путь файлу имени модуля.
    
    Args:
        file_path: Путь к файлу
        module_parts: Части имени модуля
        
    Returns:
        True, если путь соответствует имени модуля
    """
    path_parts = list(file_path.parts)
    
    # Если файл заканчивается на .py, убираем расширение из последней части
    if path_parts[-1].endswith('.py'):
        last_part = path_parts[-1][:-3]  # Убираем '.py'
        path_parts = path_parts[:-1] + [last_part]
    # Если файл - это __init__.py, значит это пакет
    elif path_parts[-1] == '__init__.py':
        last_part = path_parts[-2]  # Берем предпоследнюю часть (имя пакета)
        path_parts = path_parts[:-2] + [last_part]
    
    # Сравниваем последние части пути с частями имени модуля
    if len(path_parts) >= len(module_parts):
        path_suffix = path_parts[-len(module_parts):]
        return path_suffix == module_parts
    
    return False


def _create_code_unit(node: ast.AST, file_path: str) -> Optional[CodeUnit]:
    """
    Создает CodeUnit из узла AST.
    
    Args:
        node: Узел AST
        file_path: Путь к файлу
        
    Returns:
        CodeUnit или None
    """
    if isinstance(node, ast.FunctionDef):
        return _create_function_unit(node, file_path)
    elif isinstance(node, ast.AsyncFunctionDef):
        return _create_function_unit(node, file_path, is_async=True)
    elif isinstance(node, ast.ClassDef):
        return _create_class_unit(node, file_path)
    elif isinstance(node, ast.Import):
        return _create_import_unit(node, file_path)
    elif isinstance(node, ast.ImportFrom):
        return _create_import_from_unit(node, file_path)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        return _create_variable_unit(node, file_path)
    
    return None


def _create_function_unit(node: ast.AST, file_path: str, is_async: bool = False) -> CodeUnit:
    """
    Создает CodeUnit для функции.
    
    Args:
        node: Узел AST (FunctionDef или AsyncFunctionDef)
        file_path: Путь к файлу
        is_async: Является ли функция асинхронной
        
    Returns:
        CodeUnit для функции
    """
    # Извлекаем параметры
    args = node.args
    parameters = []
    
    # Обрабатываем позиционные аргументы
    for arg in args.args:
        parameters.append(arg.arg)
    
    # Обрабатываем аргументы со значениями по умолчанию
    defaults_count = len(args.defaults)
    if defaults_count > 0:
        # Добавляем имена аргументов со значениями по умолчанию
        for i, default in enumerate(args.defaults):
            idx = len(args.args) - defaults_count + i
            if idx < len(args.args):
                # Уже добавлено выше
                pass
    
    # Обрабатываем *args
    if args.vararg:
        parameters.append(f"*{args.vararg.arg}")
    
    # Обрабатываем **kwargs
    if args.kwarg:
        parameters.append(f"**{args.kwarg.arg}")
    
    # Извлекаем декораторы
    decorators = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            decorators.append(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            decorators.append(_get_attribute_name(decorator))
    
    # Создаем локацию
    location = Location(
        file_path=file_path,
        start_line=node.lineno,
        end_line=getattr(node, 'end_lineno', node.lineno),
        start_column=getattr(node, 'col_offset', 0) + 1,
        end_column=getattr(node, 'end_col_offset', 0) + 1
    )
    
    # Извлекаем docstring
    docstring = ast.get_docstring(node)
    
    # Создаем фрагмент кода (берем текст функции из файла)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        func_lines = lines[node.lineno-1:getattr(node, 'end_lineno', node.lineno)]
        source_code = ''.join(func_lines)
    
    # Создаем CodeSpan
    code_span = CodeSpan(source_code=source_code)
    
    # Создаем сигнатуру
    sig_parts = []
    if is_async:
        sig_parts.append("async")
    sig_parts.append(f"def {node.name}({', '.join(parameters)})")
    
    return CodeUnit(
        id=str(uuid.uuid4()),
        type=SymbolType.FUNCTION,
        name=node.name,
        location=location,
        code_span=code_span,
        docstring=docstring,
        parameters=parameters,
        signature=" ".join(sig_parts) + ":",
        decorators=decorators,
        metadata={
            'is_async': is_async,
            'args_count': len(args.args),
            'has_varargs': args.vararg is not None,
            'has_kwargs': args.kwarg is not None
        }
    )


def _create_class_unit(node: ast.ClassDef, file_path: str) -> CodeUnit:
    """
    Создает CodeUnit для класса.
    
    Args:
        node: Узел AST (ClassDef)
        file_path: Путь к файлу
        
    Returns:
        CodeUnit для класса
    """
    # Извлекаем базовые классы
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(_get_attribute_name(base))
    
    # Извлекаем декораторы
    decorators = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            decorators.append(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            decorators.append(_get_attribute_name(decorator))
    
    # Создаем локацию
    location = Location(
        file_path=file_path,
        start_line=node.lineno,
        end_line=getattr(node, 'end_lineno', node.lineno),
        start_column=getattr(node, 'col_offset', 0) + 1,
        end_column=getattr(node, 'end_col_offset', 0) + 1
    )
    
    # Извлекаем docstring
    docstring = ast.get_docstring(node)
    
    # Создаем фрагмент кода (берем текст класса из файла)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        class_lines = lines[node.lineno-1:getattr(node, 'end_lineno', node.lineno)]
        source_code = ''.join(class_lines)
    
    # Создаем CodeSpan
    code_span = CodeSpan(source_code=source_code)
    
    # Извлекаем дочерние элементы (методы, вложенные классы и т.д.)
    children = []
    for child_node in ast.iter_child_nodes(node):
        child_unit = _create_code_unit(child_node, file_path)
        if child_unit:
            children.append(child_unit)
    
    # Создаем сигнатуру
    bases_str = f"({', '.join(bases)})" if bases else ""
    signature = f"class {node.name}{bases_str}:"
    
    return CodeUnit(
        id=str(uuid.uuid4()),
        type=SymbolType.CLASS,
        name=node.name,
        location=location,
        code_span=code_span,
        docstring=docstring,
        signature=signature,
        bases=bases,
        decorators=decorators,
        children=children,
        metadata={
            'methods_count': len([c for c in children if c.type in [SymbolType.FUNCTION, SymbolType.METHOD]]),
            'nested_classes_count': len([c for c in children if c.type == SymbolType.CLASS])
        }
    )


def _create_import_unit(node: ast.Import, file_path: str) -> CodeUnit:
    """
    Создает CodeUnit для import.
    
    Args:
        node: Узел AST (Import)
        file_path: Путь к файлу
        
    Returns:
        CodeUnit для import
    """
    # Создаем локацию
    location = Location(
        file_path=file_path,
        start_line=node.lineno,
        end_line=getattr(node, 'end_lineno', node.lineno),
        start_column=getattr(node, 'col_offset', 0) + 1,
        end_column=getattr(node, 'end_col_offset', 0) + 1
    )
    
    # Создаем фрагмент кода (берем текст импорта из файла)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        import_lines = lines[node.lineno-1:getattr(node, 'end_lineno', node.lineno)]
        source_code = ''.join(import_lines)
    
    # Создаем CodeSpan
    code_span = CodeSpan(source_code=source_code)
    
    # Извлекаем имена импортов
    imported_names = []
    for alias in node.names:
        imported_names.append(alias.name)
    
    return CodeUnit(
        id=str(uuid.uuid4()),
        type=SymbolType.IMPORT,
        name=", ".join(imported_names),
        location=location,
        code_span=code_span,
        signature=f"import {', '.join([alias.name + (f' as {alias.asname}' if alias.asname else '') for alias in node.names])}",
        metadata={'aliases': [(alias.name, alias.asname) for alias in node.names]}
    )


def _create_import_from_unit(node: ast.ImportFrom, file_path: str) -> CodeUnit:
    """
    Создает CodeUnit для from ... import.
    
    Args:
        node: Узел AST (ImportFrom)
        file_path: Путь к файлу
        
    Returns:
        CodeUnit для from ... import
    """
    # Создаем локацию
    location = Location(
        file_path=file_path,
        start_line=node.lineno,
        end_line=getattr(node, 'end_lineno', node.lineno),
        start_column=getattr(node, 'col_offset', 0) + 1,
        end_column=getattr(node, 'end_col_offset', 0) + 1
    )
    
    # Создаем фрагмент кода (берем текст импорта из файла)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        import_lines = lines[node.lineno-1:getattr(node, 'end_lineno', node.lineno)]
        source_code = ''.join(import_lines)
    
    # Создаем CodeSpan
    code_span = CodeSpan(source_code=source_code)
    
    # Извлекаем имена импортов
    imported_names = []
    for alias in node.names:
        imported_names.append(alias.name + (f' as {alias.asname}' if alias.asname else ''))
    
    module = node.module or ''
    
    return CodeUnit(
        id=str(uuid.uuid4()),
        type=SymbolType.IMPORT_FROM,
        name=f"from {module} import {', '.join(imported_names)}",
        location=location,
        code_span=code_span,
        signature=f"from {module} import {', '.join([alias.name + (f' as {alias.asname}' if alias.asname else '') for alias in node.names])}",
        metadata={
            'module': module,
            'names': [alias.name for alias in node.names],
            'aliases': [(alias.name, alias.asname) for alias in node.names],
            'level': node.level
        }
    )


def _create_variable_unit(node: ast.AST, file_path: str) -> CodeUnit:
    """
    Создает CodeUnit для переменной.
    
    Args:
        node: Узел AST (Assign или AnnAssign)
        file_path: Путь к файлу
        
    Returns:
        CodeUnit для переменной
    """
    # Создаем локацию
    location = Location(
        file_path=file_path,
        start_line=node.lineno,
        end_line=getattr(node, 'end_lineno', node.lineno),
        start_column=getattr(node, 'col_offset', 0) + 1,
        end_column=getattr(node, 'end_col_offset', 0) + 1
    )
    
    # Создаем фрагмент кода (берем текст переменной из файла)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        var_lines = lines[node.lineno-1:getattr(node, 'end_lineno', node.lineno)]
        source_code = ''.join(var_lines)
    
    # Создаем CodeSpan
    code_span = CodeSpan(source_code=source_code)
    
    # Извлекаем имя переменной
    var_name = "unknown"
    if isinstance(node, ast.AnnAssign) and hasattr(node.target, 'id'):
        var_name = node.target.id
    elif isinstance(node, ast.Assign) and node.targets:
        target = node.targets[0]
        if isinstance(target, ast.Name):
            var_name = target.id
    
    return CodeUnit(
        id=str(uuid.uuid4()),
        type=SymbolType.VARIABLE,
        name=var_name,
        location=location,
        code_span=code_span,
        signature=f"{var_name} = ...",
        metadata={'is_annotated': isinstance(node, ast.AnnAssign)}
    )


def _get_attribute_name(attr_node: ast.Attribute) -> str:
    """
    Получает полное имя атрибута.
    
    Args:
        attr_node: Узел AST (Attribute)
        
    Returns:
        Полное имя атрибута
    """
    if isinstance(attr_node.value, ast.Name):
        return f"{attr_node.value.id}.{attr_node.attr}"
    elif isinstance(attr_node.value, ast.Attribute):
        return f"{_get_attribute_name(attr_node.value)}.{attr_node.attr}"
    else:
        return attr_node.attr
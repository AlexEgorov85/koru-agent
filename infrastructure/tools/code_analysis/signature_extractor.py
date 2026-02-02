"""
SignatureExtractorTool - инструмент для извлечения сигнатур кода.
"""
from typing import Dict, Any, List
import ast
import inspect
from dataclasses import dataclass

from domain.abstractions.tools.base_tool import BaseTool
from domain.models.resource import Resource


@dataclass
class FunctionSignature:
    """Представление сигнатуры функции"""
    name: str
    parameters: List[Dict[str, str]]
    return_type: str
    decorators: List[str]
    docstring: str


@dataclass
class ClassSignature:
    """Представление сигнатуры класса"""
    name: str
    bases: List[str]
    methods: List[FunctionSignature]
    attributes: List[Dict[str, str]]
    decorators: List[str]
    docstring: str


class SignatureExtractorTool(BaseTool):
    """
    Инструмент для извлечения сигнатур кода (функций, классов, методов).
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (инструмент)
    - Зависимости: от абстракций (BaseTool)
    - Ответственность: извлечение сигнатур из исходного кода
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    name = "signature_extractor"
    
    def __init__(self, **kwargs):
        """Инициализация инструмента извлечения сигнатур."""
        super().__init__(**kwargs)
        self.name = "signature_extractor"
    
    async def execute(self, parameters: Dict[str, Any]) -> Resource:
        """
        Выполнение операции извлечения сигнатур из кода.
        
        Args:
            parameters: Параметры операции, включающие 'code' - исходный код для анализа
        
        Returns:
            Resource: Результат операции извлечения сигнатур
        """
        try:
            code = parameters.get("code")
            if not code:
                raise ValueError("Параметр 'code' обязателен для извлечения сигнатур")
            
            # Извлекаем сигнатуры из кода
            signatures = self._extract_signatures(code)
            
            result_data = {
                "success": True,
                "functions": signatures["functions"],
                "classes": signatures["classes"],
                "total_functions": len(signatures["functions"]),
                "total_classes": len(signatures["classes"])
            }
            
            return Resource(
                id="signatures_extracted",
                name="Extracted Signatures",
                type="signatures",
                data=result_data,
                metadata={
                    "function_count": len(signatures["functions"]), 
                    "class_count": len(signatures["classes"])
                }
            )
            
        except Exception as e:
            error_data = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            return Resource(
                id="signature_extraction_error",
                name="Signature Extraction Error",
                type="error",
                data=error_data,
                metadata={"error_type": type(e).__name__, "exception": str(e)}
            )
    
    def _extract_signatures(self, code: str) -> Dict[str, Any]:
        """
        Извлечение сигнатур из кода.
        
        Args:
            code: Исходный код для анализа
            
        Returns:
            Dict[str, Any]: Словарь с извлеченными сигнатурами
        """
        try:
            # Парсим код в AST
            tree = ast.parse(code)
            
            functions = []
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_sig = self._extract_function_signature(node)
                    functions.append(func_sig)
                elif isinstance(node, ast.AsyncFunctionDef):
                    # Обработка асинхронных функций
                    func_sig = self._extract_function_signature(node)
                    functions.append(func_sig)
                elif isinstance(node, ast.ClassDef):
                    class_sig = self._extract_class_signature(node)
                    classes.append(class_sig)
        
            return {
                "functions": functions,
                "classes": classes
            }
        except SyntaxError as e:
            raise ValueError(f"Ошибка синтаксиса в коде: {str(e)}")
    
    def _extract_function_signature(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """
        Извлечение сигнатуры функции из AST узла.
        
        Args:
            node: Узел AST, представляющий функцию
            
        Returns:
            Dict[str, Any]: Словарь с информацией о сигнатуре функции
        """
        # Извлечение параметров
        args = []
        # Позиционные аргументы
        for arg in node.args.args:
            arg_info = {
                "name": arg.arg,
                "type": self._get_annotation(arg.annotation) if arg.annotation else None
            }
            args.append(arg_info)
        
        # Аргументы с ключевыми словами (kwargs)
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            arg_info = {
                "name": arg.arg,
                "type": self._get_annotation(arg.annotation) if arg.annotation else None,
                "default": self._get_default_value(default) if default else None
            }
            args.append(arg_info)
        
        # Аргументы *args
        if node.args.vararg:
            arg_info = {
                "name": f"*{node.args.vararg.arg}",
                "type": self._get_annotation(node.args.vararg.annotation) if node.args.vararg.annotation else None
            }
            args.append(arg_info)
        
        # Аргументы **kwargs
        if node.args.kwarg:
            arg_info = {
                "name": f"**{node.args.kwarg.arg}",
                "type": self._get_annotation(node.args.kwarg.annotation) if node.args.kwarg.annotation else None
            }
            args.append(arg_info)
        
        # Возвращаемый тип
        return_type = self._get_annotation(node.returns) if node.returns else None
        
        # Декораторы
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        # Документационная строка
        docstring = ast.get_docstring(node) or ""
        
        return {
            "name": node.name,
            "parameters": args,
            "return_type": return_type,
            "decorators": decorators,
            "docstring": docstring,
            "line_number": node.lineno
        }
    
    def _extract_class_signature(self, node: ast.ClassDef) -> Dict[str, Any]:
        """
        Извлечение сигнатуры класса из AST узла.
        
        Args:
            node: Узел AST, представляющий класс
            
        Returns:
            Dict[str, Any]: Словарь с информацией о сигнатуре класса
        """
        # Извлечение базовых классов
        bases = [self._get_attribute_name(base) for base in node.bases]
        
        # Извлечение методов
        methods = []
        attributes = []
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_sig = self._extract_function_signature(item)
                methods.append(method_sig)
            elif isinstance(item, ast.Assign):
                # Обработка атрибутов класса
                for target in item.targets if hasattr(item, 'targets') else [item.target]:
                    if isinstance(target, ast.Name):
                        attr_info = {
                            "name": target.id,
                            "type": self._get_annotation(item.annotation) if hasattr(item, 'annotation') and item.annotation else None
                        }
                        attributes.append(attr_info)
        
        # Декораторы
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        # Документационная строка
        docstring = ast.get_docstring(node) or ""
        
        return {
            "name": node.name,
            "bases": bases,
            "methods": methods,
            "attributes": attributes,
            "decorators": decorators,
            "docstring": docstring,
            "line_number": node.lineno
        }
    
    def _get_annotation(self, annotation) -> str:
        """
        Получение строки аннотации типа.
        
        Args:
            annotation: Узел AST, представляющий аннотацию
            
        Returns:
            str: Строковое представление аннотации
        """
        if annotation is None:
            return ""
        
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return self._get_attribute_name(annotation)
        elif isinstance(annotation, ast.Subscript):
            # Обработка типов с параметрами, например List[str]
            base_type = self._get_annotation(annotation.value)
            slice_val = self._get_annotation(annotation.slice) if hasattr(annotation.slice, 'id') else str(annotation.slice)
            return f"{base_type}[{slice_val}]"
        else:
            return str(annotation)
    
    def _get_attribute_name(self, attr) -> str:
        """
        Получение полного имени атрибута.
        
        Args:
            attr: Узел AST, представляющий атрибут
            
        Returns:
            str: Полное имя атрибута
        """
        if isinstance(attr, ast.Name):
            return attr.id
        elif isinstance(attr, ast.Attribute):
            return f"{self._get_attribute_name(attr.value)}.{attr.attr}"
        else:
            return str(attr)
    
    def _get_decorator_name(self, decorator) -> str:
        """
        Получение имени декоратора.
        
        Args:
            decorator: Узел AST, представляющий декоратор
            
        Returns:
            str: Имя декоратора
        """
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return self._get_attribute_name(decorator)
        elif isinstance(decorator, ast.Call):
            # Декоратор с вызовом, например @property.setter
            return self._get_attribute_name(decorator.func)
        else:
            return str(decorator)
    
    def _get_default_value(self, default_node) -> str:
        """
        Получение строкового представления значения по умолчанию.
        
        Args:
            default_node: Узел AST, представляющий значение по умолчанию
            
        Returns:
            str: Строковое представление значения
        """
        if default_node is None:
            return ""
        
        if isinstance(default_node, ast.Constant):
            return repr(default_node.value)
        elif isinstance(default_node, ast.NameConstant):
            return str(default_node.value)
        else:
            return str(default_node)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Возвращает возможности инструмента.
        """
        return {
            "extract_signatures": {
                "description": "Извлечение сигнатур функций и классов из исходного кода",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Исходный код для анализа"
                        }
                    },
                    "required": ["code"]
                }
            },
            "analyze_code_structure": {
                "description": "Анализ структуры кода для извлечения архитектурных элементов",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Исходный код для анализа"
                        }
                    },
                    "required": ["code"]
                }
            }
        }
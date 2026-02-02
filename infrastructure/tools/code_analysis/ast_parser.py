"""
ASTParserTool - инструмент для парсинга кода в AST (Abstract Syntax Tree).
"""
from typing import Dict, Any
import ast
import sys

from domain.abstractions.tools.base_tool import BaseTool
from domain.models.resource import Resource


class ASTParserTool(BaseTool):
    """
    Инструмент для парсинга кода в AST (Abstract Syntax Tree).
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (инструмент)
    - Зависимости: от абстракций (BaseTool)
    - Ответственность: безопасный парсинг кода в синтаксическое дерево
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    name = "ast_parser"
    
    def __init__(self, **kwargs):
        """Инициализация инструмента парсинга AST."""
        super().__init__(**kwargs)
        self.name = "ast_parser"
    
    async def execute(self, parameters: Dict[str, Any]) -> Resource:
        """
        Выполнение операции парсинга кода в AST.
        
        Args:
            parameters: Параметры операции, включающие 'code' - исходный код для парсинга
        
        Returns:
            Resource: Результат операции парсинга AST
        """
        try:
            code = parameters.get("code")
            language = parameters.get("language", "python")  # По умолчанию Python
            
            if not code:
                raise ValueError("Параметр 'code' обязателен для парсинга AST")
            
            # Парсим код в зависимости от языка
            if language.lower() == "python":
                parsed_ast = self._parse_python_ast(code)
            else:
                raise ValueError(f"Поддержка языка {language} пока не реализована")
            
            result_data = {
                "success": True,
                "language": language,
                "ast": parsed_ast,
                "node_count": self._count_nodes(parsed_ast),
                "has_errors": False
            }
            
            return Resource(
                id="ast_parsed",
                name="Parsed AST",
                type="ast",
                data=result_data,
                metadata={"language": language, "node_count": self._count_nodes(parsed_ast)}
            )
            
        except SyntaxError as e:
            error_data = {
                "success": False,
                "error": "SyntaxError",
                "error_message": str(e),
                "line_number": e.lineno,
                "column_offset": e.offset,
                "text": e.text
            }
            
            return Resource(
                id="ast_syntax_error",
                name="AST Syntax Error",
                type="error",
                data=error_data,
                metadata={"error_type": "SyntaxError", "line_number": e.lineno}
            )
            
        except Exception as e:
            error_data = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            return Resource(
                id="ast_general_error",
                name="AST General Error",
                type="error",
                data=error_data,
                metadata={"error_type": type(e).__name__, "exception": str(e)}
            )
    
    def _parse_python_ast(self, code: str) -> Dict[str, Any]:
        """
        Парсинг Python кода в AST.
        
        Args:
            code: Исходный Python код
            
        Returns:
            Dict[str, Any]: Представление AST в виде словаря
        """
        # Парсим код в AST
        tree = ast.parse(code)
        
        # Конвертируем AST в словарь
        return self._ast_to_dict(tree)
    
    def _ast_to_dict(self, node) -> Dict[str, Any]:
        """
        Конвертация узла AST в словарь.
        
        Args:
            node: Узел AST
            
        Returns:
            Dict[str, Any]: Представление узла в виде словаря
        """
        if isinstance(node, ast.AST):
            result = {'_type': node.__class__.__name__}
            for field, value in ast.iter_fields(node):
                result[field] = self._ast_to_dict(value)
            return result
        elif isinstance(node, list):
            return [self._ast_to_dict(item) for item in node]
        else:
            return node
    
    def _count_nodes(self, ast_dict: Dict[str, Any]) -> int:
        """
        Подсчет количества узлов в AST.
        
        Args:
            ast_dict: AST в виде словаря
            
        Returns:
            int: Количество узлов
        """
        count = 1 # Считаем текущий узел
        
        for key, value in ast_dict.items():
            if key == '_type':
                continue  # Пропускаем служебное поле
            
            if isinstance(value, dict):
                count += self._count_nodes(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        count += self._count_nodes(item)
        
        return count
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Возвращает возможности инструмента.
        """
        return {
            "parse_ast": {
                "description": "Парсинг исходного кода в AST (Abstract Syntax Tree)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Исходный код для парсинга"
                        },
                        "language": {
                            "type": "string",
                            "description": "Язык программирования",
                            "enum": ["python"],
                            "default": "python"
                        }
                    },
                    "required": ["code"]
                }
            },
            "analyze_ast": {
                "description": "Анализ AST для извлечения информации о структуре кода",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ast": {
                            "type": "object",
                            "description": "AST дерево для анализа"
                        }
                    },
                    "required": ["ast"]
                }
            }
        }
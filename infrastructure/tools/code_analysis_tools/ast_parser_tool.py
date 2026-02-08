from dataclasses import dataclass
from typing import Dict, Optional, Any
from tree_sitter import Tree
from tree_sitter import Language, Parser
import tree_sitter_python

from domain.abstractions.event_types import EventType, IEventPublisher
from domain.abstractions.tools.base_tool import BaseTool
from domain.abstractions.tools.base_tool import ToolInput, ToolOutput
from infrastructure.tools.file_tools.file_reader_tool import FileReadInput


@dataclass
class ASTParserInput(ToolInput):
    file_path: str
    max_depth: int = 10  # Для будущего использования при необходимости ограничения глубины

@dataclass
class ASTParserOutput(ToolOutput):
    success: bool
    tree: Optional[Tree] = None  # Исходное дерево tree-sitter
    source_code: str = ""  # Исходный код для референсов
    language: str = "python"
    file_path: str = ""
    error: Optional[str] = None

class ASTParserTool(BaseTool):
    """Инструмент для построения AST дерева из Python кода."""
    name = "ast_parser"
    
    @property
    def description(self) -> str:
        return "Построение AST дерева из файла с кодом с возвратом исходного дерева tree-sitter"
    
    def __init__(self, name: str = "ast_parser", event_publisher: 'IEventPublisher' = None, system_context: Any = None, **kwargs):
        # Изменим инициализацию, чтобы она соответствовала базовому классу
        super().__init__()
        self.name = name
        self.event_publisher = event_publisher
        self.system_context = system_context
    
    async def initialize(self) -> bool:
        """Инициализация инструмента AST парсера."""
        # Получение зависимостей от системы
        try:
            self.file_reader_tool = self.system_context.get_resource("FileReaderTool")
            if not self.file_reader_tool:
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.WARNING,
                        self.name,
                        {"message": "Не удалось получить инструмент file_reader"}
                    )
                return False
        except Exception as e:
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {"message": f"Ошибка получения зависимостей: {str(e)}"}
                )
            return False
        
        # Правильная инициализация парсера для Python
        try:
            # Инициализация парсера с правильным синтаксисом
            PY_LANGUAGE = Language(tree_sitter_python.language())
            self.parser = Parser(language = PY_LANGUAGE)
            
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.INFO,
                    self.name,
                    {"message": "Успешно инициализирован парсер для Python"}
                )
            return True
        except Exception as e:
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {"message": f"Ошибка инициализации парсера Python: {str(e)}"}
                )
            return False
    
    async def _execute_internal(self, input_data: ASTParserInput) -> ASTParserOutput:
        """Внутренняя реализация основного метода выполнения инструмента."""
        try:
            if not hasattr(self, 'parser') or not self.parser:
                return ASTParserOutput(
                    success=False,
                    error="Парсер не инициализирован"
                )
            
            # Чтение файла с помощью FileReaderTool
            file_read_input = FileReadInput(path=input_data.file_path)
            file_read_output = await self.file_reader_tool.execute(file_read_input)
            
            if not file_read_output.success:
                return ASTParserOutput(
                    success=False,
                    file_path=input_data.file_path,
                    error=f"Ошибка чтения файла: {file_read_output.error}"
                )
            
            source_code = file_read_output.content
            
            # Построение AST для Python кода
            try:
                content_bytes = source_code.encode('utf-8')
                tree = self.parser.parse(content_bytes)
                
                return ASTParserOutput(
                    success=True,
                    tree=tree,
                    source_code=source_code,
                    language="python",
                    file_path=input_data.file_path
                )
            except Exception as e:
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.ERROR,
                        self.name,
                        {"message": f"Ошибка парсинга AST: {str(e)}"}
                    )
                return ASTParserOutput(
                    success=False,
                    file_path=input_data.file_path,
                    error=f"Ошибка парсинга AST: {str(e)}"
                )
                
        except Exception as e:
            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    self.name,
                    {"message": f"Критическая ошибка в ASTParserTool: {str(e)}"}
                )
            return ASTParserOutput(
                success=False,
                file_path=getattr(input_data, 'file_path', ''),
                error=f"Критическая ошибка: {str(e)}"
            )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение инструмента согласно новому контракту."""
        # Создаем объект входных данных из параметров
        input_data = ASTParserInput(**parameters)
        # Выполняем внутреннюю логику
        result = await self._execute_internal(input_data)
        # Возвращаем результат виде словаря
        return {
            "success": result.success,
            "source_code": result.source_code,
            "language": result.language,
            "file_path": result.file_path,
            "error": result.error
        }
    
    async def shutdown(self) -> None:
        """Корректное завершение работы инструмента."""
        if hasattr(self, 'parser'):
            self.parser = None
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.INFO,
                self.name,
                {"message": "ASTParserTool завершил работу"}
            )

from dataclasses import dataclass
from typing import Optional
import logging
from tree_sitter import Tree
from tree_sitter import Language, Parser
import tree_sitter_python

from core.infrastructure.tools.base_tool import BaseTool, ToolInput, ToolOutput
from core.infrastructure.tools.file_reader_tool import FileReadInput


logger = logging.getLogger(__name__)


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
    
    async def initialize(self) -> bool:
        """Инициализация инструмента AST парсера."""
        # Получение зависимостей от системы
        try:
            self.file_reader_tool = self.system_context.get_resource("FileReaderTool")
            if not self.file_reader_tool:
                logger.error("Не удалось получить инструмент file_reader")
                return False
        except Exception as e:
            logger.error(f"Ошибка получения зависимостей: {str(e)}")
            return False
        
        # Правильная инициализация парсера для Python
        try:
            # Инициализация парсера с правильным синтаксисом
            PY_LANGUAGE = Language(tree_sitter_python.language())
            self.parser = Parser(language = PY_LANGUAGE)
            
            logger.info("Успешно инициализирован парсер для Python")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации парсера Python: {str(e)}")
            return False
    
    async def execute(self, input_data: ASTParserInput) -> ASTParserOutput:
        """Основной метод выполнения инструмента."""
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
                logger.error(f"Ошибка парсинга AST: {str(e)}", exc_info=True)
                return ASTParserOutput(
                    success=False,
                    file_path=input_data.file_path,
                    error=f"Ошибка парсинга AST: {str(e)}"
                )
                
        except Exception as e:
            logger.error(f"Критическая ошибка в ASTParserTool: {str(e)}", exc_info=True)
            return ASTParserOutput(
                success=False,
                file_path=getattr(input_data, 'file_path', ''),
                error=f"Критическая ошибка: {str(e)}"
            )
    
    async def shutdown(self) -> None:
        """Корректное завершение работы инструмента."""
        if hasattr(self, 'parser'):
            self.parser = None
        logger.info("ASTParserTool завершил работу")
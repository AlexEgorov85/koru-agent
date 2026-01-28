"""
AST Processing Service — работает ТОЛЬКО с AST деревьями.
ОТВЕТСТВЕННОСТЬ:
- Парсинг кода в AST через языковые адаптеры
- Навигация по узлам дерева (без семантического анализа)
- Извлечение текста из узлов
- Базовые операции с деревом (поиск узлов, обход)

ЗАПРЕЩЕНО:
- Анализ типов
- Разрешение импортов
- Построение символьных таблиц
- Любая семантическая логика
- Вызовы к LLM или внешним системам
"""
import logging
import os
from typing import List, Optional, Dict, Any
from core.infrastructure.services.base_service import BaseService
from core.system_context.base_system_contex import BaseSystemContext
from core.infrastructure.services.code_analysis.base import (
    ASTNode, LanguageSupport, Location
)
from core.infrastructure.services.code_analysis.language_registry import LanguageRegistry
from models.code_unit import CodeUnit


logger = logging.getLogger(__name__)


class ASTProcessingService(BaseService):
    """
    Сервис обработки AST — только парсинг и базовые операции с деревом.
    
    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    1. Единственная ответственность: только работа с деревом
    2. Языко-независимость: все операции через абстрактные интерфейсы
    3. Отсутствие состояния: не хранит кэши символов или типов
    4. Минимальные зависимости: зависит только от LanguageRegistry
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        ast_service = system_context.get_resource("ast_processing")
        ast = await ast_service.parse_file("core/main.py", source_code)
        classes = await ast_service.find_nodes_by_type(ast, "class_definition")
    """

    name = "ast_processing"

    # Внутренние кэши
    _outline_cache: Dict[str, List[CodeUnit]] = {}
    _definition_cache: Dict[str, CodeUnit] = {}
    
    def __init__(
        self,
        name: str,
        system_context: Optional[BaseSystemContext] = None,
        **kwargs
    ):
        super().__init__(name, system_context, **kwargs)
        self.language_registry: Optional[LanguageRegistry] = None
        self._initialized = False
        

    async def initialize(self) -> bool:
        """Инициализация сервиса — получение реестра языков из системного контекста."""
        try:
            # Получаем реестр языков из системного контекста (уже должен быть зарегистрирован)
            self.language_registry = self.system_context.get_resource("language_registry")
            
            if not self.language_registry:
                logger.error("Не найден сервис 'language_registry' в системном контексте")
                return False
            
            self._initialized = True
            logger.info("ASTProcessingService успешно инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации ASTProcessingService: {str(e)}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Корректное завершение работы сервиса."""
        self._initialized = False
        logger.info("ASTProcessingService завершил работу")

    async def parse_file(self, file_path: str, source_code: str) -> Optional[ASTNode]:
        """
        Парсит файл в AST дерево с предварительной проверкой поддержки языка.
        
        ВОЗВРАЩАЕТ:
            Корневой узел AST или None если язык не поддерживается или ошибка парсинга
        """
        if not self._initialized:
            raise RuntimeError("ASTProcessingService не инициализирован")
        
        # 1. Проверяем поддержку языка ДО попытки парсинга
        language = await self.get_file_language(file_path)
        if not language:
            logger.debug(f"Язык файла не поддерживается (пропускаем): {file_path}")
            return None
        
        # 2. Получаем адаптер
        adapter = self.language_registry.get_adapter_by_name(language)
        if not adapter:
            logger.warning(f"Не найден адаптер для языка '{language}' файла: {file_path}")
            return None
        
        # 3. Парсим только если адаптер инициализирован
        if not getattr(adapter, 'initialized', False):
            # Пытаемся инициализировать адаптер на лету
            if hasattr(adapter, 'initialize') and callable(adapter.initialize):
                success = await adapter.initialize()
                if not success:
                    logger.error(f"Не удалось инициализировать адаптер для языка '{language}'")
                    return None
            else:
                logger.error(f"Адаптер для языка '{language}' не поддерживает инициализацию")
                return None
        
        try:
            source_bytes = source_code.encode('utf-8')
            ast = await adapter.parse(source_code, source_bytes)
            logger.debug(f"Успешно спарсен файл {file_path} ({language}), корневой узел: {ast.type}")
            return ast
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга файла {file_path} ({language}): {str(e)}")
            return None

    async def get_file_outline(self, file_path: str, source_code: str) -> List[CodeUnit]:
        """
        Получение структуры файла — НАВИГАЦИЯ ВСТРОЕНА В СЕРВИС.
        
        ПРЕИМУЩЕСТВА:
        - Нет избыточного слоя делегирования
        - Прямой доступ к языковому адаптеру через собственный реестр
        - Единая точка кэширования для всех операций с кодом
        """
        # Проверка кэша
        cache_key = f"outline_{file_path}_{hash(source_code) % 10000}"
        if cache_key in self._outline_cache:
            return self._outline_cache[cache_key]
        
        # Определение языка
        language = await self.get_file_language(file_path)
        if not language:
            return []
        
        # Парсинг
        ast = await self.parse_file(file_path, source_code)
        if not ast:
            return []
        
        # Получение структуры через адаптер (без промежуточного сервиса)
        adapter = self.language_registry.get_adapter_by_name(language)
        if not adapter:
            return []
        
        source_bytes = source_code.encode('utf-8')
        outline = await adapter.get_outline(ast, file_path)
        
        # Кэширование
        self._outline_cache[cache_key] = outline
        return outline

    async def get_file_language(self, file_path: str) -> Optional[str]:
        """
        Определяет язык файла по расширению с валидацией.
        ВОЗВРАЩАЕТ:
            Имя языка или None если расширение не поддерживается
        """
        # Извлекаем расширение файла
        if '.' not in os.path.basename(file_path):
            return None
        
        ext = os.path.splitext(file_path)[1][1:].lower()  # Убираем точку
        lang_name = self._extension_map.get(ext)
        
        return lang_name


    async def get_node_text(self, node: ASTNode, source_bytes: bytes) -> str:
        """
        Извлекает текст из узла AST.
        ПАРАМЕТРЫ:
            node: Узел AST
            source_bytes: Байтовое представление исходного кода
        ВОЗВРАЩАЕТ:
            Текст узла
        """
        try:
            return node.get_text(source_bytes)
        except Exception as e:
            logger.warning(f"Ошибка извлечения текста из узла: {str(e)}")
            return ""

    async def find_nodes_by_type(self, ast: ASTNode, node_type: str) -> List[ASTNode]:
        """
        Находит все узлы заданного типа в дереве.
        ПАРАМЕТРЫ:
            ast: Корневой узел дерева
            node_type: Тип узла для поиска
        ВОЗВРАЩАЕТ:
            Список найденных узлов
        """
        result = []
        
        def traverse(node: ASTNode):
            if node.type == node_type:
                result.append(node)
            for child in node.children:
                traverse(child)
        
        traverse(ast)
        return result

    async def find_node_at_location(
        self,
        ast: ASTNode,
        location: Location
    ) -> Optional[ASTNode]:
        """
        Находит узел по местоположению в коде.
        ПАРАМЕТРЫ:
            ast: Корневой узел дерева
            location: Местоположение для поиска
        ВОЗВРАЩАЕТ:
            Узел или None если не найден
        """
        # Простая реализация: обход дерева с проверкой пересечения диапазонов
        def traverse(node: ASTNode) -> Optional[ASTNode]:
            node_loc = node.location
            
            # Проверяем пересечение диапазонов
            if (node_loc.start_line <= location.start_line <= node_loc.end_line or
                location.start_line <= node_loc.start_line <= location.end_line):
                # Нашли подходящий узел, проверяем детей для более точного совпадения
                for child in node.children:
                    child_result = traverse(child)
                    if child_result:
                        return child_result
                return node
            return None
        
        return traverse(ast)

    async def get_file_language(self, file_path: str) -> Optional[str]:
        """
        Определяет язык файла по расширению.
        ВОЗВРАЩАЕТ:
            Имя языка или None если не поддерживается
        """
        adapter = self.language_registry.get_adapter_for_file(file_path)
        return adapter.language_name if adapter else None
"""
ProjectNavigatorSkill — навык для структурной навигации по кодовой базе.
АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
1. Фокус на структурной навигации (не семантическом анализе)
2. Получение ProjectMap из контекста сессии (не перестроение)
3. Использование существующих сервисов (ASTProcessingService)
4. Минимальные зависимости и сложность
5. Четкое разделение ответственности

ИНТЕГРАЦИЯ С СИСТЕМОЙ:
- ProjectMapSkill → ProjectStructure из контекста сессии
- ASTProcessingService → get_file_outline() для детальной структуры
- FileReaderTool → чтение исходного кода
- LanguageRegistry → определение языка файла
"""
import logging
import os
from typing import Dict, Any, List, Optional
from core.infrastructure.tools.file_reader_tool import FileReadInput
from core.skills.base_skill import BaseSkill
from core.system_context.base_system_contex import BaseSystemContext
from core.session_context.model import ContextItemMetadata
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus
from core.skills.project_navigator.schema import (
    NavigationInput,
    SearchInput,
    FindUsagesInput,
    GetInheritanceChainInput,
    NavigationTargetType,
    NavigationDetailLevel
)
from core.skills.project_navigator.models.navigation import NavigationResult
from core.skills.project_navigator.models.search import SearchResultSet, SearchResult
from core.skills.project_navigator.utils import (
    LRUCache,
    normalize_path,
    is_path_match,
    calculate_relevance
)

logger = logging.getLogger(__name__)


class ProjectNavigatorSkill(BaseSkill):
    """
    Навык для структурной навигации по проекту.
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    # Получение навыка из системного контекста
    navigator = system_context.get_resource("project_navigator")
    
    # Навигация к классу
    result = await navigator.execute(
        capability=system_context.get_capability("project_navigator.navigate"),
        parameters={
            "target_type": "class",
            "identifier": "ProjectMapSkill",
            "file_path": "core/skills/project_map/skill.py"
        },
        context=session_context
    )
    
    # Поиск элементов по имени
    result = await navigator.execute(
        capability=system_context.get_capability("project_navigator.search"),
        parameters={
            "query": "build",
            "element_types": ["class", "function"]
        },
        context=session_context
    )
    ```
    """
    name = "project_navigator"

    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        self._file_reader: Optional[Any] = None
        self._ast_service: Optional[Any] = None
        self._file_cache = LRUCache(maxsize=150)  # Кэш содержимого файлов
        self._structure_cache = LRUCache(maxsize=100)  # Кэш структуры файлов
        logger.info(f"Инициализирован навык навигации: {self.name}")

    async def initialize(self) -> bool:
        """
        Инициализация навыка — получение зависимостей из системного контекста.
        
        ВАЖНО: Навык НЕ строит ProjectMap — он использует существующий из контекста.
        """
        try:
            # Получение инструментов и сервисов
            self._file_reader = self.system_context.get_resource("file_reader")
            self._ast_service = self.system_context.get_resource("ast_processing")
            
            if not self._file_reader:
                logger.error("Не найден инструмент 'file_reader' в системном контексте")
                return False
                
            if not self._ast_service:
                logger.error("Не найден сервис 'ast_processing' в системном контексте")
                return False

            logger.info("ProjectNavigatorSkill успешно инициализирован")
            return True

        except Exception as e:
            logger.error(f"Ошибка инициализации ProjectNavigatorSkill: {str(e)}", exc_info=True)
            return False

    def get_capabilities(self) -> List[Capability]:
        """
        Регистрация capability навыка.
        
        СПИСОК CAPABILITY:
        1. project_navigator.navigate — навигация к элементу кода
        2. project_navigator.search — поиск элементов по имени/типу
        3. project_navigator.get_file_structure — получение структуры файла
        4. project_navigator.get_dependencies — получение зависимостей файла
        5. project_navigator.find_usages — поиск мест использования символа
        6. project_navigator.get_inheritance_chain — получение цепочки наследования
        
        ВИДИМОСТЬ:
        - navigate, search — видимы для агента (visiable=True)
        - остальные — скрыты (visiable=False), для внутреннего использования
        """
        return [
            Capability(
                name="project_navigator.navigate",
                description="Навигация к элементу кода (файл, класс, функция, метод)",
                parameters_schema=NavigationInput.model_json_schema(),
                parameters_class=NavigationInput,
                skill_name=self.name,
                visiable=True
            ),
            Capability(
                name="project_navigator.search",
                description="Поиск элементов кода по имени или типу",
                parameters_schema=SearchInput.model_json_schema(),
                parameters_class=SearchInput,
                skill_name=self.name,
                visiable=True
            ),
            Capability(
                name="project_navigator.get_file_structure",
                description="Получение структуры файла (классы, функции, методы)",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Путь к файлу"}
                    },
                    "required": ["file_path"]
                },
                skill_name=self.name,
                visiable=False
            ),
            Capability(
                name="project_navigator.get_dependencies",
                description="Получение зависимостей файла",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Путь к файлу"},
                        "depth": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1}
                    },
                    "required": ["file_path"]
                },
                skill_name=self.name,
                visiable=False
            ),
            Capability(
                name="project_navigator.find_usages",
                description="Поиск мест использования символа в проекте",
                parameters_schema=FindUsagesInput.model_json_schema(),
                parameters_class=FindUsagesInput,
                skill_name=self.name,
                visiable=False
            ),
            Capability(
                name="project_navigator.get_inheritance_chain",
                description="Получение цепочки наследования класса",
                parameters_schema=GetInheritanceChainInput.model_json_schema(),
                parameters_class=GetInheritanceChainInput,
                skill_name=self.name,
                visiable=False
            )
        ]

    async def execute(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        context: Any
    ) -> ExecutionResult:
        """
        Выполнение capability навыка.
        
        МАРШРУТИЗАЦИЯ:
        - navigate → _navigate()
        - search → _search()
        - get_file_structure → _get_file_structure()
        - get_dependencies → _get_dependencies()
        - find_usages → _find_usages()
        - get_inheritance_chain → _get_inheritance_chain()
        """
        try:
            # Маршрутизация по имени capability
            if capability.name == "project_navigator.navigate":
                return await self._navigate(parameters, context)
            elif capability.name == "project_navigator.search":
                return await self._search(parameters, context)
            elif capability.name == "project_navigator.get_file_structure":
                return await self._get_file_structure(parameters, context)
            elif capability.name == "project_navigator.get_dependencies":
                return await self._get_dependencies(parameters, context)
            elif capability.name == "project_navigator.find_usages":
                return await self._find_usages(parameters, context)
            elif capability.name == "project_navigator.get_inheritance_chain":
                return await self._get_inheritance_chain(parameters, context)
            else:
                return self._create_error_result(
                    summary=f"Неизвестная capability: {capability.name}",
                    error="UNKNOWN_CAPABILITY"
                )

        except Exception as e:
            logger.error(
                f"Ошибка выполнения capability '{capability.name}': {str(e)}",
                exc_info=True
            )
            return self._create_error_result(
                summary=f"Ошибка выполнения: {str(e)}",
                error="EXECUTION_ERROR"
            )

    async def _navigate(
        self,
        parameters: Dict[str, Any],
        context: Any
    ) -> ExecutionResult:
        """
        Навигация к элементу кода.
        
        АЛГОРИТМ:
        1. Валидация параметров через NavigationInput
        2. Получение ProjectMap из контекста сессии
        3. Поиск элемента в структуре проекта
        4. Получение исходного кода при необходимости
        5. Формирование результата
        
        ВОЗВРАЩАЕТ:
        ExecutionResult с объектом NavigationResult
        """
        try:
            # 1. Валидация параметров
            try:
                input_data = NavigationInput(**parameters)
            except Exception as e:
                return self._create_error_result(
                    summary=f"Ошибка валидации параметров: {str(e)}",
                    error="VALIDATION_ERROR"
                )

            # 2. Получение ProjectMap из контекста
            project_map = await self._get_project_map(context)
            if not project_map:
                return self._create_error_result(
                    summary="ProjectMap не найден в контексте сессии",
                    error="PROJECT_MAP_NOT_FOUND"
                )

            # 3. Маршрутизация по типу цели
            if input_data.target_type == NavigationTargetType.FILE:
                result = await self._navigate_to_file(input_data, project_map, context)
            elif input_data.target_type == NavigationTargetType.CLASS:
                if not input_data.file_path:
                    return self._create_error_result(
                        summary="Для навигации к классу требуется указать file_path",
                        error="MISSING_PARAMETER"
                    )
                result = await self._navigate_to_class(input_data, project_map, context)
            elif input_data.target_type == NavigationTargetType.FUNCTION:
                if not input_data.file_path:
                    return self._create_error_result(
                        summary="Для навигации к функции требуется указать file_path",
                        error="MISSING_PARAMETER"
                    )
                result = await self._navigate_to_function(input_data, project_map, context)
            elif input_data.target_type == NavigationTargetType.METHOD:
                if not input_data.file_path or not input_data.class_name:
                    return self._create_error_result(
                        summary="Для навигации к методу требуется указать file_path и class_name",
                        error="MISSING_PARAMETER"
                    )
                result = await self._navigate_to_method(input_data, project_map, context)
            else:
                return self._create_error_result(
                    summary=f"Неподдерживаемый тип навигации: {input_data.target_type}",
                    error="UNSUPPORTED_TARGET_TYPE"
                )

            if not result.success:
                return self._create_error_result(
                    summary=result.error or "Неизвестная ошибка навигации",
                    error="NAVIGATION_ERROR"
                )

            # 4. Запись результата в контекст
            observation_id = context.record_observation(
                result.model_dump(),
                source=self.name,
                step_number=getattr(context, 'current_step_number', None),
                metadata=ContextItemMetadata(
                    source="project_navigator_skill",
                    confidence=0.95,
                    step_number=getattr(context, 'current_step_number', None)
                )
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result.model_dump(),
                observation_item_id=observation_id,
                summary=(
                    f"Навигация к {input_data.target_type.value}: {input_data.identifier} "
                    f"в файле {result.file_path}"
                ),
                error=None
            )

        except Exception as e:
            logger.error(f"Ошибка навигации: {str(e)}", exc_info=True)
            return self._create_error_result(
                summary=f"Ошибка навигации: {str(e)}",
                error="NAVIGATION_ERROR"
            )

    async def _search(
        self,
        parameters: Dict[str, Any],
        context: Any
    ) -> ExecutionResult:
        """
        Поиск элементов кода по имени.
        
        АЛГОРИТМ:
        1. Валидация параметров через SearchInput
        2. Получение ProjectMap из контекста
        3. Фильтрация элементов по критериям поиска
        4. Ранжирование по релевантности
        5. Ограничение количества результатов
        
        ВОЗВРАЩАЕТ:
        ExecutionResult с объектом SearchResultSet
        """
        try:
            # 1. Валидация параметров
            try:
                input_data = SearchInput(**parameters)
            except Exception as e:
                return self._create_error_result(
                    summary=f"Ошибка валидации параметров: {str(e)}",
                    error="VALIDATION_ERROR"
                )

            # 2. Получение ProjectMap из контекста
            project_map = await self._get_project_map(context)
            if not project_map:
                return self._create_error_result(
                    summary="ProjectMap не найден в контексте сессии",
                    error="PROJECT_MAP_NOT_FOUND"
                )

            # 3. Определение области поиска
            search_scope = self._determine_search_scope(input_data, project_map)

            # 4. Поиск и ранжирование
            results = []
            for file_path in search_scope:
                # Получаем единицы кода для файла
                file_units = project_map.get_code_units_by_file(file_path)
                
                for unit in file_units:
                    # Фильтрация по типу
                    if unit.type.value not in input_data.element_types:
                        continue
                    
                    # Вычисление релевантности
                    relevance = calculate_relevance(
                        unit.name,
                        input_data.query,
                        input_data.exact_match
                    )
                    
                    if relevance >= 0.3:  # Порог релевантности
                        results.append(
                            SearchResult(
                                name=unit.name,
                                file_path=file_path,
                                type=unit.type.value,
                                line=unit.location.start_line,
                                relevance_score=relevance,
                                context=f"{unit.type.value} '{unit.name}' at line {unit.location.start_line}"
                            )
                        )

            # 5. Сортировка и ограничение
            results.sort(key=lambda x: x.relevance_score, reverse=True)
            limited_results = results[:input_data.max_results]

            # 6. Формирование результата
            search_result = SearchResultSet(
                success=True,
                query=input_data.query,
                results=limited_results,
                total_results=len(results)
            )

            # 7. Запись в контекст
            observation_id = context.record_observation(
                search_result.model_dump(),
                source=self.name,
                step_number=getattr(context, 'current_step_number', None),
                metadata=ContextItemMetadata(
                    source="project_navigator_skill",
                    confidence=0.90,
                    step_number=getattr(context, 'current_step_number', None)
                )
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=search_result.model_dump(),
                observation_item_id=observation_id,
                summary=f"Найдено {len(limited_results)} элементов по запросу '{input_data.query}'",
                error=None
            )

        except Exception as e:
            logger.error(f"Ошибка поиска: {str(e)}", exc_info=True)
            return self._create_error_result(
                summary=f"Ошибка поиска: {str(e)}",
                error="SEARCH_ERROR"
            )

    async def _get_file_structure(
        self,
        parameters: Dict[str, Any],
        context: Any
    ) -> ExecutionResult:
        """
        Получение структуры файла через ASTProcessingService.
        
        ВАЖНО: Использует существующий сервис, а не создает собственный парсер.
        """
        try:
            file_path = parameters.get("file_path")
            if not file_path:
                return self._create_error_result(
                    summary="Не указан параметр 'file_path'",
                    error="MISSING_PARAMETER"
                )

            # Нормализация пути
            file_path = normalize_path(file_path)

            # Проверка кэша
            cache_key = f"structure_{file_path}"
            if cached := self._structure_cache.get(cache_key):
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    result=cached,
                    observation_item_id=None,
                    summary=f"Структура файла {file_path} получена из кэша",
                    error=None
                )

            # Чтение содержимого файла
            file_read_result = await self._file_reader.execute(FileReadInput(path=file_path))
            if not file_read_result.success:
                return self._create_error_result(
                    summary=f"Ошибка чтения файла: {file_read_result.error}",
                    error="FILE_READ_ERROR"
                )

            # Получение структуры через сервис
            code_units = await self._ast_service.get_file_outline(
                file_path=file_path,
                source_code=file_read_result.content
            )

            # Формирование результата
            result = {
                "file_path": file_path,
                "code_units": [unit.to_dict() for unit in code_units],
                "unit_count": len(code_units),
                "language": "python"
            }

            # Кэширование
            self._structure_cache.set(cache_key, result)

            # Запись в контекст
            observation_id = context.record_observation(
                result,
                source=self.name,
                step_number=getattr(context, 'current_step_number', None),
                metadata=ContextItemMetadata(
                    source="project_navigator_skill",
                    confidence=0.95,
                    step_number=getattr(context, 'current_step_number', None)
                )
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result,
                observation_item_id=observation_id,
                summary=f"Получена структура файла {file_path} ({len(code_units)} элементов)",
                error=None
            )

        except Exception as e:
            logger.error(f"Ошибка получения структуры файла: {str(e)}", exc_info=True)
            return self._create_error_result(
                summary=f"Ошибка получения структуры: {str(e)}",
                error="STRUCTURE_ERROR"
            )

    async def _get_dependencies(
        self,
        parameters: Dict[str, Any],
        context: Any
    ) -> ExecutionResult:
        """
        Получение зависимостей файла из ProjectMap.
        
        ВАЖНО: Использует зависимости, уже проанализированные ProjectMapSkill.
        """
        try:
            file_path = parameters.get("file_path")
            depth = parameters.get("depth", 1)
            
            if not file_path:
                return self._create_error_result(
                    summary="Не указан параметр 'file_path'",
                    error="MISSING_PARAMETER"
                )

            # Нормализация пути
            file_path = normalize_path(file_path)

            # Получение ProjectMap из контекста
            project_map = await self._get_project_map(context)
            if not project_map:
                return self._create_error_result(
                    summary="ProjectMap не найден в контексте сессии",
                    error="PROJECT_MAP_NOT_FOUND"
                )

            # Получение зависимостей напрямую из структуры проекта
            dependencies = project_map.file_dependencies.get(file_path, [])
            
            # Удаление дубликатов
            unique_deps = []
            seen_targets = set()
            for dep in dependencies:
                target = dep.target_file if hasattr(dep, 'target_file') else dep.get('target_file')
                if target and target not in seen_targets:
                    seen_targets.add(target)
                    unique_deps.append(dep)

            result = {
                "file_path": file_path,
                "dependencies": [
                    dep.to_dict() if hasattr(dep, 'to_dict') else dep
                    for dep in unique_deps[:50]  # Ограничение для безопасности
                ],
                "dependency_count": len(unique_deps)
            }

            # Запись в контекст
            observation_id = context.record_observation(
                result,
                source=self.name,
                step_number=getattr(context, 'current_step_number', None),
                metadata=ContextItemMetadata(
                    source="project_navigator_skill",
                    confidence=0.90,
                    step_number=getattr(context, 'current_step_number', None)
                )
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result,
                observation_item_id=observation_id,
                summary=f"Получено {len(unique_deps)} зависимостей для файла {file_path}",
                error=None
            )

        except Exception as e:
            logger.error(f"Ошибка получения зависимостей: {str(e)}", exc_info=True)
            return self._create_error_result(
                summary=f"Ошибка получения зависимостей: {str(e)}",
                error="DEPENDENCY_ERROR"
            )

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ НАВИГАЦИИ ====================

    async def _navigate_to_file(
        self,
        input_data: NavigationInput,
        project_map: Any,
        context: Any
    ) -> NavigationResult:
        """Навигация к файлу."""
        # Нормализация пути для поиска
        normalized_identifier = normalize_path(input_data.identifier)
        
        # Поиск файла в структуре проекта
        file_info = None
        for path in project_map.files.keys():
            if is_path_match(path, normalized_identifier):
                file_info = project_map.files[path]
                actual_path = path
                break
        
        # Поиск по частичному совпадению
        if not file_info:
            matches = [
                path for path in project_map.files.keys()
                if normalized_identifier.lower() in normalize_path(path).lower()
            ]
            if matches:
                actual_path = matches[0]
                file_info = project_map.files[actual_path]
        
        if not file_info:
            return NavigationResult(
                success=False,
                target_type=input_data.target_type.value,
                identifier=input_data.identifier,
                file_path=input_data.identifier,
                error=f"Файл не найден: {input_data.identifier}"
            )

        # Получение исходного кода при необходимости
        source_code = None
        signature = None
        location = None
        
        if input_data.detail_level != NavigationDetailLevel.SIGNATURE:
            file_read_result = await self._file_reader.execute(FileReadInput(path=actual_path)
            )
            if file_read_result.success:
                source_code = file_read_result.content

        # Формирование результата
        return NavigationResult(
            success=True,
            target_type=input_data.target_type.value,
            identifier=input_data.identifier,
            file_path=actual_path,
            source_code=source_code,
            signature=signature,
            location=location,
            dependencies=[]
        )

    async def _navigate_to_class(
        self,
        input_data: NavigationInput,
        project_map: Any,
        context: Any
    ) -> NavigationResult:
        """Навигация к классу."""
        # Нормализация пути
        normalized_file_path = normalize_path(input_data.file_path)
        
        # Поиск файла в структуре проекта
        actual_file_path = None
        for path in project_map.files.keys():
            if is_path_match(path, normalized_file_path):
                actual_file_path = path
                break
        
        if not actual_file_path:
            return NavigationResult(
                success=False,
                target_type=input_data.target_type.value,
                identifier=input_data.identifier,
                file_path=input_data.file_path,
                error=f"Файл не найден: {input_data.file_path}"
            )

        # Поиск класса среди единиц кода
        target_unit = None
        for unit in project_map.code_units.values():
            if (unit.type.value == "class" and 
                unit.name == input_data.identifier and 
                is_path_match(unit.location.file_path, normalized_file_path)):
                target_unit = unit
                break

        if not target_unit:
            return NavigationResult(
                success=False,
                target_type=input_data.target_type.value,
                identifier=input_data.identifier,
                file_path=actual_file_path,
                error=f"Класс '{input_data.identifier}' не найден в файле {input_data.file_path}"
            )

        # Получение исходного кода
        source_code = None
        if input_data.detail_level == NavigationDetailLevel.FULL:
            file_read_result = await self._file_reader.execute(FileReadInput(path=actual_file_path))

            if file_read_result.success:
                lines = file_read_result.content.split('\n')
                start = max(0, target_unit.location.start_line - 1)
                end = min(len(lines), target_unit.location.end_line)
                source_code = '\n'.join(lines[start:end])

        # Формирование результата
        return NavigationResult(
            success=True,
            target_type=input_data.target_type.value,
            identifier=input_data.identifier,
            file_path=actual_file_path,
            source_code=source_code,
            signature=target_unit.get_signature(),
            location={
                "start_line": target_unit.location.start_line,
                "end_line": target_unit.location.end_line,
                "start_column": target_unit.location.start_column,
                "end_column": target_unit.location.end_column
            },
            dependencies=[]
        )

    async def _navigate_to_function(
        self,
        input_data: NavigationInput,
        project_map: Any,
        context: Any
    ) -> NavigationResult:
        """Навигация к функции."""
        # Реализация аналогична _navigate_to_class с проверкой unit.type.value == "function"
        normalized_file_path = normalize_path(input_data.file_path)
        actual_file_path = None
        
        for path in project_map.files.keys():
            if is_path_match(path, normalized_file_path):
                actual_file_path = path
                break
        
        if not actual_file_path:
            return NavigationResult(
                success=False,
                target_type=input_data.target_type.value,
                identifier=input_data.identifier,
                file_path=input_data.file_path,
                error=f"Файл не найден: {input_data.file_path}"
            )

        target_unit = None
        for unit in project_map.code_units.values():
            if (unit.type.value == "function" and 
                unit.name == input_data.identifier and 
                is_path_match(unit.location.file_path, normalized_file_path)):
                target_unit = unit
                break

        if not target_unit:
            return NavigationResult(
                success=False,
                target_type=input_data.target_type.value,
                identifier=input_data.identifier,
                file_path=actual_file_path,
                error=f"Функция '{input_data.identifier}' не найдена в файле {input_data.file_path}"
            )

        return NavigationResult(
            success=True,
            target_type=input_data.target_type.value,
            identifier=input_data.identifier,
            file_path=actual_file_path,
            source_code=None,  # Для упрощения не загружаем код
            signature=target_unit.get_signature(),
            location={
                "start_line": target_unit.location.start_line,
                "end_line": target_unit.location.end_line
            },
            dependencies=[]
        )

    async def _navigate_to_method(
        self,
        input_data: NavigationInput,
        project_map: Any,
        context: Any
    ) -> NavigationResult:
        """Навигация к методу."""
        # Реализация аналогична _navigate_to_class с проверкой родительского класса
        normalized_file_path = normalize_path(input_data.file_path)
        actual_file_path = None
        
        for path in project_map.files.keys():
            if is_path_match(path, normalized_file_path):
                actual_file_path = path
                break
        
        if not actual_file_path:
            return NavigationResult(
                success=False,
                target_type=input_data.target_type.value,
                identifier=input_data.identifier,
                file_path=input_data.file_path,
                error=f"Файл не найден: {input_data.file_path}"
            )

        target_unit = None
        for unit in project_map.code_units.values():
            if (unit.type.value == "method" and 
                unit.name == input_data.identifier and 
                is_path_match(unit.location.file_path, normalized_file_path)):
                # Проверка принадлежности к классу через метаданные
                if unit.parent_id and input_data.class_name in unit.parent_id:
                    target_unit = unit
                    break

        if not target_unit:
            return NavigationResult(
                success=False,
                target_type=input_data.target_type.value,
                identifier=input_data.identifier,
                file_path=actual_file_path,
                error=f"Метод '{input_data.identifier}' класса '{input_data.class_name}' не найден в файле {input_data.file_path}"
            )

        return NavigationResult(
            success=True,
            target_type=input_data.target_type.value,
            identifier=input_data.identifier,
            class_name=input_data.class_name,
            file_path=actual_file_path,
            source_code=None,
            signature=target_unit.get_signature(),
            location={
                "start_line": target_unit.location.start_line,
                "end_line": target_unit.location.end_line
            },
            dependencies=[]
        )

    # ==================== ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ====================

    async def _find_usages(
        self,
        parameters: Dict[str, Any],
        context: Any
    ) -> ExecutionResult:
        """
        Поиск мест использования символа в проекте.
        Реализация через поиск по именам в единицах кода.
        """
        try:
            input_data = FindUsagesInput(**parameters)
            project_map = await self._get_project_map(context)
            if not project_map:
                return self._create_error_result(
                    summary="ProjectMap не найден в контексте сессии",
                    error="PROJECT_MAP_NOT_FOUND"
                )

            usages = []
            for unit in project_map.code_units.values():
                # Фильтрация по имени и типу
                if input_data.symbol_name.lower() not in unit.name.lower():
                    continue
                if input_data.symbol_type and unit.type.value != input_data.symbol_type:
                    continue
                if input_data.file_path and not is_path_match(unit.location.file_path, input_data.file_path):
                    continue
                
                usages.append({
                    "name": unit.name,
                    "file_path": unit.location.file_path,
                    "type": unit.type.value,
                    "line": unit.location.start_line,
                    "context": unit.get_signature()[:100] + "..." if unit.get_signature() else ""
                })
                
                if len(usages) >= input_data.max_results:
                    break

            result = {
                "success": True,
                "symbol_name": input_data.symbol_name,
                "usages": usages,
                "total_usages": len(usages)
            }

            observation_id = context.record_observation(
                result,
                source=self.name,
                metadata=ContextItemMetadata(source="project_navigator_skill")
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result,
                observation_item_id=observation_id,
                summary=f"Найдено {len(usages)} мест использования символа '{input_data.symbol_name}'",
                error=None
            )

        except Exception as e:
            logger.error(f"Ошибка поиска использований: {str(e)}", exc_info=True)
            return self._create_error_result(
                summary=f"Ошибка поиска использований: {str(e)}",
                error="USAGE_SEARCH_ERROR"
            )

    async def _get_inheritance_chain(
        self,
        parameters: Dict[str, Any],
        context: Any
    ) -> ExecutionResult:
        """
        Получение цепочки наследования класса.
        Реализация через анализ метаданных классов в ProjectMap.
        """
        try:
            input_data = GetInheritanceChainInput(**parameters)
            project_map = await self._get_project_map(context)
            if not project_map:
                return self._create_error_result(
                    summary="ProjectMap не найден в контексте сессии",
                    error="PROJECT_MAP_NOT_FOUND"
                )

            # Поиск класса
            target_class = None
            for unit in project_map.code_units.values():
                if (unit.type.value == "class" and 
                    unit.name == input_data.class_name and 
                    is_path_match(unit.location.file_path, input_data.file_path)):
                    target_class = unit
                    break

            if not target_class:
                return self._create_error_result(
                    summary=f"Класс '{input_data.class_name}' не найден в файле {input_data.file_path}",
                    error="CLASS_NOT_FOUND"
                )

            # Извлечение базовых классов из метаданных
            bases = target_class.metadata.get("bases", [])
            inheritance_chain = [input_data.class_name] + bases[:input_data.max_depth - 1]

            result = {
                "success": True,
                "class_name": input_data.class_name,
                "file_path": input_data.file_path,
                "inheritance_chain": inheritance_chain,
                "depth": len(inheritance_chain)
            }

            observation_id = context.record_observation(
                result,
                source=self.name,
                metadata=ContextItemMetadata(source="project_navigator_skill")
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result,
                observation_item_id=observation_id,
                summary=f"Получена цепочка наследования для класса {input_data.class_name} (глубина {len(inheritance_chain)})",
                error=None
            )

        except Exception as e:
            logger.error(f"Ошибка получения цепочки наследования: {str(e)}", exc_info=True)
            return self._create_error_result(
                summary=f"Ошибка получения цепочки наследования: {str(e)}",
                error="INHERITANCE_ERROR"
            )

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    async def _get_project_map(self, context: Any) -> Optional[Any]:
        """Получение ProjectMap из контекста сессии."""
        # Приоритет 1: прямой доступ к атрибуту
        if hasattr(context, 'project_map') and context.project_map:
            return context.project_map

        # Приоритет 2: поиск в текущем плане
        current_plan = context.get_current_plan()
        if current_plan and hasattr(current_plan, 'content'):
            plan_data = current_plan.content
            if isinstance(plan_data, dict) and 'project_structure' in plan_data:
                from core.skills.project_map.models.project_map import ProjectStructure
                return ProjectStructure.from_dict(plan_data['project_structure'])

        logger.warning("ProjectMap не найден в контексте, требуется предварительный анализ проекта")
        return None

    def _determine_search_scope(
        self,
        input_data: SearchInput,
        project_map: Any
    ) -> List[str]:
        """Определение области поиска на основе параметров."""
        if input_data.scope == "global":
            return list(project_map.files.keys())
        elif input_data.scope.startswith("file:"):
            file_path = input_data.scope[5:]
            normalized_path = normalize_path(file_path)
            for path in project_map.files.keys():
                if is_path_match(path, normalized_path):
                    return [path]
            return list(project_map.files.keys())
        elif input_data.scope.startswith("module:"):
            module_name = input_data.scope[7:]
            return [
                path for path in project_map.files.keys()
                if module_name in path
            ] or list(project_map.files.keys())
        else:  # global
            return list(project_map.files.keys())

    def _create_error_result(
        self,
        summary: str,
        error: str
    ) -> ExecutionResult:
        """Универсальный метод создания ошибочного результата."""
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            result=None,
            observation_item_id=None,
            summary=summary,
            error=error
        )
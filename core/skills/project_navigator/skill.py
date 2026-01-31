"""
ProjectNavigatorSkill — навык для структурной навигации по кодовой базе.
АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
1. ТОЧНАЯ НОРМАЛИЗАЦИЯ ПУТЕЙ под формат хранения в ProjectMap (обратные слеши, нижний регистр)
2. ЕДИНСТВЕННАЯ ТОЧКА ВХОДА для поиска файлов: _find_file_in_project_map()
3. УНИВЕРСАЛЬНЫЙ ПОИСК элементов кода без избыточного разделения на методы/функции
4. ЛОКАЛИЗОВАННЫЙ ПОИСК: сначала найти файл в структуре проекта → затем получить его CodeUnit
5. РЕЗЕРВНЫЙ МЕХАНИЗМ: если фильтрация по типу не удалась → поиск без фильтрации
6. КЭШИРОВАНИЕ: для производительности при повторных запросах к одному файлу
"""
import logging
import os
import re
from typing import Dict, Any, List, Optional, Tuple
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
    find_best_path_match,
    calculate_relevance,
    extract_error_location
)
from models.code_unit import CodeUnit

logger = logging.getLogger(__name__)


class ProjectNavigatorSkill(BaseSkill):
    """
    Навык для структурной навигации по проекту.
    
    КРИТИЧЕСКИ ВАЖНОЕ ИЗМЕНЕНИЕ:
    Пути в ProjectMap хранятся в специфическом формате:
    - Обратные слеши: 'core\\skills\\project_navigator\\skill.py'
    - Нижний регистр: 'core\\skills\\base_skill.py'
    
    Все операции поиска ДОЛЖНЫ использовать точную нормализацию под этот формат.
    """
    name = "project_navigator"
    
    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        self._file_reader: Optional[Any] = None
        self._ast_service: Optional[Any] = None
        self._file_cache = LRUCache(maxsize=150)           # Кэш содержимого файлов
        self._structure_cache = LRUCache(maxsize=100)       # Кэш структуры файлов
        self._file_code_units_cache = LRUCache(maxsize=200) # Кэш единиц кода по файлу
        self._project_root: Optional[str] = None            # Корень проекта для нормализации
        self._project_map_path_format: Optional[str] = None # Формат путей в ProjectMap ('windows' или 'unix')
        logger.info(f"Инициализирован навык навигации: {self.name}")
    
    async def initialize(self) -> bool:
        """
        Инициализация навыка — получение зависимостей из системного контекста.
        ОПРЕДЕЛЕНИЕ ФОРМАТА ПУТЕЙ в ProjectMap при первом анализе.
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
            
            # Определение корня проекта для нормализации путей
            self._project_root = os.getcwd()
            logger.info(f"Корень проекта определен: {self._project_root}")
            
            logger.info("ProjectNavigatorSkill успешно инициализирован")
            return True
        
        except Exception as e:
            logger.error(f"Ошибка инициализации ProjectNavigatorSkill: {str(e)}", exc_info=True)
            return False
    
    def get_capabilities(self) -> List[Capability]:
        """
        Регистрация capability навыка.
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
        """
        try:
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
        УНИВЕРСАЛЬНАЯ НАВИГАЦИЯ к элементу кода.
        КРИТИЧЕСКИ ВАЖНО: Точная нормализация путей под формат хранения в ProjectMap.
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
                    summary="ProjectMap не найден в контексте сессии. Выполните анализ проекта через ProjectMapSkill.",
                    error="PROJECT_MAP_NOT_FOUND"
                )
            
            # 3. Определение пути для поиска файла
            search_path = input_data.file_path if input_data.file_path else input_data.identifier
            
            # 4. ЕДИНСТВЕННАЯ ТОЧКА ВХОДА: поиск файла с ТОЧНОЙ НОРМАЛИЗАЦИЕЙ под формат ProjectMap
            actual_file_path, file_info = await self._find_file_in_project_map(
                project_map=project_map,
                input_path=search_path
            )
            
            if not actual_file_path:
                # Дополнительная диагностика для отладки
                logger.debug(f"Доступные пути в ProjectMap (первые 10):")
                for i, path in enumerate(list(project_map.files.keys())[:10]):
                    logger.debug(f"  {i+1}. '{path}'")
                return self._create_error_result(
                    summary=f"Файл не найден: {search_path}",
                    error="FILE_NOT_FOUND"
                )
            
            # 5. УНИВЕРСАЛЬНЫЙ ПОИСК элемента кода
            if input_data.target_type == NavigationTargetType.FILE:
                # Навигация к файлу
                source_code = None
                if input_data.detail_level != NavigationDetailLevel.SIGNATURE:
                    file_read_result = await self._file_reader.execute(
                        FileReadInput(path=actual_file_path)
                    )
                    if file_read_result.success:
                        source_code = file_read_result.content
                
                result = NavigationResult(
                    success=True,
                    target_type=input_data.target_type.value,
                    identifier=input_data.identifier,
                    file_path=actual_file_path,
                    source_code=source_code,
                    signature=None,
                    location=None,
                    dependencies=[]
                )
            
            else:
                # Поиск элемента кода в файле БЕЗ фильтрации по типу (резервный механизм)
                target_unit = await self._find_code_unit_in_file(
                    project_map=project_map,
                    file_path=actual_file_path,  # Уже в формате ProjectMap
                    identifier=input_data.identifier,
                    unit_type=None  # None = поиск без фильтрации по типу
                )
                
                if not target_unit:
                    return self._create_error_result(
                        summary=f"Элемент '{input_data.identifier}' не найден в файле {actual_file_path}",
                        error="ELEMENT_NOT_FOUND"
                    )
                
                # Формирование результата
                result = await self._build_navigation_result(
                    target_unit=target_unit,
                    file_path=actual_file_path,
                    detail_level=input_data.detail_level,
                    include_dependencies=input_data.include_dependencies
                )
            
            if not result.success:
                return self._create_error_result(
                    summary=result.error or "Неизвестная ошибка навигации",
                    error="NAVIGATION_ERROR"
                )
            
            # 6. Запись результата в контекст
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
                    f"Навигация к {result.target_type}: {result.identifier} "
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
    
    async def _search(self, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """Поиск элементов кода по имени."""
        try:
            input_data = SearchInput(**parameters)
            project_map = await self._get_project_map(context)
            if not project_map:
                return self._create_error_result(
                    summary="ProjectMap не найден в контексте сессии",
                    error="PROJECT_MAP_NOT_FOUND"
                )
            
            search_scope = self._determine_search_scope(input_data, project_map)
            results = []
            
            for file_path in search_scope:
                # Получаем единицы кода для файла (уже в формате ProjectMap)
                code_units = await self._get_code_units_for_file(project_map, file_path)
                for unit in code_units:
                    if unit.type.value not in input_data.element_types:
                        continue
                    
                    relevance = calculate_relevance(
                        unit.name,
                        input_data.query,
                        input_data.exact_match
                    )
                    if relevance >= 0.3:
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
            
            results.sort(key=lambda x: x.relevance_score, reverse=True)
            limited_results = results[:input_data.max_results]
            
            search_result = SearchResultSet(
                success=True,
                query=input_data.query,
                results=limited_results,
                total_results=len(results)
            )
            
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
    
    async def _get_file_structure(self, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """Получение структуры файла."""
        try:
            file_path = parameters.get("file_path")
            if not file_path:
                return self._create_error_result(
                    summary="Не указан параметр 'file_path'",
                    error="MISSING_PARAMETER"
                )
            
            # Нормализация пути под формат ProjectMap
            normalized_path = self._normalize_path_for_project_map(file_path)
            
            cache_key = f"structure_{normalized_path}"
            if cached := self._structure_cache.get(cache_key):
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    result=cached,
                    observation_item_id=None,
                    summary=f"Структура файла {normalized_path} получена из кэша",
                    error=None
                )
            
            project_map = await self._get_project_map(context)
            if not project_map:
                return self._create_error_result(
                    summary="ProjectMap не найден в контексте сессии",
                    error="PROJECT_MAP_NOT_FOUND"
                )
            
            # Получение единиц кода из файла через кэш (уже в формате ProjectMap)
            code_units = await self._get_code_units_for_file(project_map, normalized_path)
            
            result = {
                "file_path": normalized_path,
                "code_units": [unit.to_dict() for unit in code_units],
                "unit_count": len(code_units),
                "language": "python"
            }
            
            self._structure_cache.set(cache_key, result)
            
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
                summary=f"Получена структура файла {normalized_path} ({len(code_units)} элементов)",
                error=None
            )
        
        except Exception as e:
            logger.error(f"Ошибка получения структуры файла: {str(e)}", exc_info=True)
            return self._create_error_result(
                summary=f"Ошибка получения структуры: {str(e)}",
                error="STRUCTURE_ERROR"
            )
    
    async def _get_dependencies(self, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """Получение зависимостей файла."""
        try:
            file_path = parameters.get("file_path")
            if not file_path:
                return self._create_error_result(
                    summary="Не указан параметр 'file_path'",
                    error="MISSING_PARAMETER"
                )
            
            normalized_path = self._normalize_path_for_project_map(file_path)
            
            project_map = await self._get_project_map(context)
            if not project_map:
                return self._create_error_result(
                    summary="ProjectMap не найден в контексте сессии",
                    error="PROJECT_MAP_NOT_FOUND"
                )
            
            dependencies = project_map.file_dependencies.get(normalized_path, [])
            
            unique_deps = []
            seen_targets = set()
            for dep in dependencies:
                target = dep.target_file if hasattr(dep, 'target_file') else dep.get('target_file')
                if target and target not in seen_targets:
                    seen_targets.add(target)
                    unique_deps.append(dep)
            
            result = {
                "file_path": normalized_path,
                "dependencies": [
                    dep.to_dict() if hasattr(dep, 'to_dict') else dep
                    for dep in unique_deps[:50]
                ],
                "dependency_count": len(unique_deps)
            }
            
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
                summary=f"Получено {len(unique_deps)} зависимостей для файла {normalized_path}",
                error=None
            )
        
        except Exception as e:
            logger.error(f"Ошибка получения зависимостей: {str(e)}", exc_info=True)
            return self._create_error_result(
                summary=f"Ошибка получения зависимостей: {str(e)}",
                error="DEPENDENCY_ERROR"
            )
    
    # ==================== КРИТИЧЕСКИ ВАЖНЫЕ МЕТОДЫ НАВИГАЦИИ ====================
    
    def _normalize_path_for_project_map(self, path: str) -> str:
        """
        ТОЧНАЯ НОРМАЛИЗАЦИЯ ПУТИ под формат хранения в ProjectMap.
        
        ФОРМАТ ХРАНЕНИЯ В ВАШЕМ PROJECTMAP (из лога):
        - Обратные слеши: 'core\\skills\\base_skill.py'
        - Нижний регистр: 'core\\skills\\base_skill.py'
        - Без начальных/конечных слешей
        
        Примеры преобразований:
        >>> _normalize_path_for_project_map("C:/Users/Алексей/Documents/WORK/Agent_code/core/skills/project_navigator/skill.py")
        'core\\skills\\project_navigator\\skill.py'
        
        >>> _normalize_path_for_project_map("./core/skills/project_navigator/skill.py")
        'core\\skills\\project_navigator\\skill.py'
        
        >>> _normalize_path_for_project_map("core/skills/project_navigator/skill.py")
        'core\\skills\\project_navigator\\skill.py'
        """
        if not path:
            return ""
        
        # 1. Замена всех разделителей на обратные слеши (формат Windows)
        normalized = path.replace('/', '\\').replace('//', '\\')
        
        # 2. Удаление ./ и ../ в начале
        while normalized.startswith('.\\'):
            normalized = normalized[2:]
        while normalized.startswith('..\\'):
            normalized = normalized[3:]
        
        # 3. Удаление префикса диска Windows (C:\\, D:\\ и т.д.)
        disk_match = re.match(r'^[a-zA-Z]:\\', normalized)
        if disk_match:
            normalized = normalized[disk_match.end():]
        
        # 4. Удаление префикса корня проекта (все, что до "Agent_code\\" или "agent_code\\")
        agent_code_pos = normalized.lower().find('agent_code\\')
        if agent_code_pos != -1:
            normalized = normalized[agent_code_pos + len('agent_code\\'):]
        
        # 5. Удаляем начальные и конечные слеши
        normalized = normalized.strip('\\')
        
        # 6. Приводим к нижнему регистру (как в вашем ProjectMap)
        normalized = normalized.lower()
        
        return normalized
    
    async def _find_file_in_project_map(
        self,
        project_map: Any,
        input_path: str
    ) -> Tuple[Optional[str], Optional[Any]]:
        """
        ЕДИНСТВЕННАЯ ТОЧКА ВХОДА для поиска файла в структуре проекта.
        
        КРИТИЧЕСКИ ВАЖНО: Использует ТОЧНУЮ НОРМАЛИЗАЦИЮ под формат хранения в ProjectMap.
        """
        if not input_path:
            return None, None
        
        # Шаг 1: Нормализуем входной путь ПОД ФОРМАТ PROJECTMAP
        normalized_input = self._normalize_path_for_project_map(input_path)
        logger.debug(f"Поиск файла по нормализованному пути (формат ProjectMap): '{normalized_input}'")
        
        # Шаг 2: Проверяем точное совпадение в словаре файлов
        if normalized_input in project_map.files:
            logger.debug(f"Точное совпадение найдено: '{normalized_input}'")
            return normalized_input, project_map.files[normalized_input]
        
        # Шаг 3: Поиск по частичному совпадению (последние компоненты пути)
        # Анализируем формат путей в ProjectMap для адаптации поиска
        input_parts = normalized_input.split('\\')
        input_filename = input_parts[-1] if input_parts else normalized_input
        
        # Сначала ищем по полному совпадению последних компонентов
        best_match = None
        best_match_count = 0
        
        for stored_path in project_map.files.keys():
            stored_parts = stored_path.split('\\')
            
            # Считаем количество совпавших последних компонентов
            match_count = 0
            for i in range(1, min(len(stored_parts), len(input_parts)) + 1):
                if stored_parts[-i] == input_parts[-i]:
                    match_count += 1
                else:
                    break
            
            # Выбираем путь с максимальным количеством совпавших компонентов
            if match_count > best_match_count:
                best_match = stored_path
                best_match_count = match_count
        
        if best_match:
            logger.debug(
                f"Частичное совпадение найдено ({best_match_count} компонентов): "
                f"'{normalized_input}' → '{best_match}'"
            )
            return best_match, project_map.files[best_match]
        
        # Шаг 4: Поиск только по имени файла (последний резорт)
        for stored_path in project_map.files.keys():
            stored_filename = stored_path.split('\\')[-1]
            if stored_filename == input_filename:
                logger.debug(f"Совпадение по имени файла найдено: '{input_filename}' → '{stored_path}'")
                return stored_path, project_map.files[stored_path]
        
        # Шаг 5: Поиск по подстроке в имени файла
        for stored_path in project_map.files.keys():
            stored_filename = stored_path.split('\\')[-1]
            if input_filename in stored_filename:
                logger.debug(f"Подстрочное совпадение найдено: '{input_filename}' → '{stored_path}'")
                return stored_path, project_map.files[stored_path]
        
        # Шаг 6: Попытка извлечь путь из стека ошибок
        error_location = extract_error_location(input_path)
        if error_location:
            file_from_error, line, method, class_name = error_location
            # Повторяем поиск с извлеченным путем из стека
            return await self._find_file_in_project_map(project_map, file_from_error)
        
        logger.warning(f"Файл не найден в структуре проекта: '{input_path}' (нормализовано: '{normalized_input}')")
        logger.debug(f"Доступные пути (первые 5): {[p for p in list(project_map.files.keys())[:5]]}")
        return None, None
    
    async def _find_code_unit_in_file(
        self,
        project_map: Any,
        file_path: str,  # УЖЕ В ФОРМАТЕ PROJECTMAP
        identifier: str,
        unit_type: Optional[str] = None
    ) -> Optional[CodeUnit]:
        """
        УНИВЕРСАЛЬНЫЙ МЕТОД ПОИСКА элемента кода в файле.
        
        АЛГОРИТМ:
        1. Сначала находим файл в структуре проекта по точному совпадению пути
        2. Затем фильтруем ВСЕ единицы кода проекта по совпадению file_path
        3. Применяем фильтрацию по имени (и опционально по типу)
        
        КРИТИЧЕСКИ ВАЖНО: 
        - file_path ДОЛЖЕН быть в точном формате хранения ProjectMap
        - Сравнение путей — точное совпадение (без дополнительной нормализации)
        """
        # Шаг 1: Убедимся, что путь в правильном формате
        # (должен быть уже нормализован при вызове _find_file_in_project_map)
        search_path = file_path
        
        # Шаг 2: Получаем ВСЕ единицы кода проекта
        # ВАЖНО: Не используем project_map.get_code_units_by_file() — он может быть ненадежным
        # Вместо этого фильтруем напрямую по атрибуту location.file_path
        all_code_units = getattr(project_map, 'code_units', {})
        
        if not all_code_units:
            logger.warning("ProjectMap не содержит единиц кода")
            return None
        
        # Шаг 3: Фильтрация единиц кода по пути файла
        # КРИТИЧЕСКИ ВАЖНО: Сравниваем напрямую без дополнительной нормализации
        # Потому что location.file_path уже хранится в формате ProjectMap
        file_units = [
            unit for unit in all_code_units.values()
            if hasattr(unit, 'location') and 
               hasattr(unit.location, 'file_path') and
               unit.location.file_path == search_path  # ТОЧНОЕ СОВПАДЕНИЕ
        ]
        
        if not file_units:
            # Дополнительная диагностика
            logger.warning(
                f"Не найдены единицы кода для файла '{search_path}'. "
                f"Примеры путей из единиц кода (первые 5): "
                f"{[u.location.file_path for u in list(all_code_units.values())[:5] if hasattr(u, 'location')]}"
            )
            return None
        
        logger.debug(f"Найдено {len(file_units)} единиц кода в файле '{search_path}'")
        
        # Шаг 4: Поиск по имени (с резервным механизмом)
        candidates = []
        
        # Сначала поиск с точным совпадением имени и типа (если тип указан)
        if unit_type:
            candidates = [
                unit for unit in file_units
                if unit.name == identifier and unit.type.value == unit_type
            ]
            if candidates:
                logger.debug(
                    f"Найдено {len(candidates)} элементов типа '{unit_type}' с именем '{identifier}' "
                    f"в файле {search_path}"
                )
                return min(candidates, key=lambda u: u.location.start_line)
        
        # Резервный поиск без фильтрации по типу
        candidates = [
            unit for unit in file_units
            if unit.name == identifier
        ]
        
        if not candidates:
            # Поиск с игнорированием регистра
            candidates = [
                unit for unit in file_units
                if unit.name.lower() == identifier.lower()
            ]
        
        if candidates:
            logger.debug(
                f"Найдено {len(candidates)} элементов с именем '{identifier}' в файле {search_path} "
                f"(без фильтрации по типу). Выбран элемент на строке {min(candidates, key=lambda u: u.location.start_line).location.start_line}."
            )
            return min(candidates, key=lambda u: u.location.start_line)
        
        logger.warning(
            f"Элемент '{identifier}' не найден в файле {search_path}. "
            f"Доступные элементы: {[u.name for u in file_units[:10]]}"
        )
        return None
    
    async def _get_code_units_for_file(
        self,
        project_map: Any,
        file_path: str  # УЖЕ В ФОРМАТЕ PROJECTMAP
    ) -> List[CodeUnit]:
        """
        Получение единиц кода для файла с кэшированием.
        КРИТИЧЕСКИ ВАЖНО: Использует прямую фильтрацию по location.file_path.
        """
        # Проверка кэша
        cache_key = f"units_{file_path}"
        cached = self._file_code_units_cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Получение всех единиц кода проекта
        all_code_units = getattr(project_map, 'code_units', {})
        
        if not all_code_units:
            return []
        
        # Фильтрация по точному совпадению пути файла
        code_units = [
            unit for unit in all_code_units.values()
            if hasattr(unit, 'location') and 
               hasattr(unit.location, 'file_path') and
               unit.location.file_path == file_path  # ТОЧНОЕ СОВПАДЕНИЕ
        ]
        
        # Кэширование
        self._file_code_units_cache.set(cache_key, code_units)
        return code_units
    
    async def _build_navigation_result(
        self,
        target_unit: CodeUnit,
        file_path: str,
        detail_level: NavigationDetailLevel,
        include_dependencies: bool
    ) -> NavigationResult:
        """Формирование результата навигации."""
        source_code = None
        if detail_level == NavigationDetailLevel.FULL:
            file_read_result = await self._file_reader.execute(
                FileReadInput(path=file_path)
            )
            if file_read_result.success:
                lines = file_read_result.content.split('\n')
                start = max(0, target_unit.location.start_line - 1)
                end = min(len(lines), target_unit.location.end_line)
                source_code = '\n'.join(lines[start:end])
        
        # Безопасное получение сигнатуры
        try:
            signature = target_unit.get_signature()
        except Exception as e:
            logger.warning(
                f"Ошибка получения сигнатуры для {target_unit.type.value} '{target_unit.name}' "
                f"в файле {file_path}: {str(e)}"
            )
            signature = f"{target_unit.type.value} {target_unit.name}"
        
        return NavigationResult(
            success=True,
            target_type=target_unit.type.value,
            identifier=target_unit.name,
            file_path=file_path,
            source_code=source_code,
            signature=signature,
            location={
                "start_line": target_unit.location.start_line,
                "end_line": target_unit.location.end_line,
                "start_column": target_unit.location.start_column,
                "end_column": target_unit.location.end_column
            },
            dependencies=[] if not include_dependencies else self._extract_dependencies(target_unit)
        )
    
    def _extract_dependencies(self, code_unit: CodeUnit) -> List[Dict[str, str]]:
        """Извлечение зависимостей из метаданных."""
        dependencies = []
        metadata = code_unit.metadata or {}
        
        imports = metadata.get("imports", [])
        for imp in imports:
            dependencies.append({
                "target_file": imp.get("module", "unknown"),
                "type": "import",
                "name": imp.get("name", "unknown")
            })
        
        if code_unit.type.value == "class":
            bases = metadata.get("bases", [])
            for base in bases:
                dependencies.append({
                    "target_file": "unknown",
                    "type": "inheritance",
                    "name": base.get("name", str(base)) if isinstance(base, dict) else str(base)
                })
        
        return dependencies[:10]
    
    async def _get_project_map(self, context: Any) -> Optional[Any]:
        """Получение ProjectMap из контекста сессии."""
        if hasattr(context, 'project_map') and context.project_map:
            return context.project_map
        
        current_plan = context.get_current_plan()
        if current_plan and hasattr(current_plan, 'content'):
            plan_data = current_plan.content
            if isinstance(plan_data, dict) and 'project_structure' in plan_data:
                from core.skills.project_map.models.project_map import ProjectStructure
                return ProjectStructure.from_dict(plan_data['project_structure'])
        
        logger.warning("ProjectMap не найден в контексте")
        return None
    
    def _determine_search_scope(self, input_data: SearchInput, project_map: Any) -> List[str]:
        """Определение области поиска."""
        if input_data.scope == "global":
            return list(project_map.files.keys())
        elif input_data.scope.startswith("file:"):
            file_path = input_data.scope[5:]
            normalized_path = self._normalize_path_for_project_map(file_path)
            best_path, _ = find_best_path_match(normalized_path, list(project_map.files.keys()))
            if best_path:
                return [best_path]
            return list(project_map.files.keys())
        elif input_data.scope.startswith("module:"):
            module_name = input_data.scope[7:]
            return [
                path for path in project_map.files.keys()
                if module_name in path
            ] or list(project_map.files.keys())
        else:
            return list(project_map.files.keys())
    
    def _create_error_result(self, summary: str, error: str) -> ExecutionResult:
        """Универсальный метод создания ошибочного результата."""
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            result=None,
            observation_item_id=None,
            summary=summary,
            error=error
        )
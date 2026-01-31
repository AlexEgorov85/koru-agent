"""
ProjectMapSkill - навык для создания карты проекта через сервисы анализа кода.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Работа с объектами CodeUnit вместо словарей
2. Агрегация данных от сервисов (не создание объектов)
3. Упрощённая логика — адаптеры возвращают готовые данные
4. Прямое использование инфраструктурных моделей

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Сервисы предоставляют готовые объекты CodeUnit
- Навык агрегирует и строит структуру проекта
- Минимальная логика создания объектов в навыке
- Чёткое разделение: инфраструктура (сервисы) vs бизнес-логика (навык)
"""
import logging
import os
import time
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

from core.skills.base_skill import BaseSkill
from core.system_context.base_system_contex import BaseSystemContext
from core.session_context.model import ContextItemMetadata
from models.capability import Capability
from models.code_unit import CodeUnit, CodeUnitType
from models.execution import ExecutionResult, ExecutionStatus
from pydantic import ValidationError

# Используем инфраструктурные модели вместо моделей навыка

from core.skills.project_map.models.project_map import (
    ProjectStructure, FileInfo, FileDependency, EntryPointInfo
)

# Схемы валидации
from core.skills.project_map.schema import (
    AnalyzeProjectInput, GetFileCodeUnitsInput,
    AnalyzeProjectOutput, GetFileCodeUnitsOutput
)

# Инструменты
from core.infrastructure.tools.file_lister_tool import FileListerInput
from core.infrastructure.tools.file_reader_tool import FileReadInput

logger = logging.getLogger(__name__)


class ProjectMapSkill(BaseSkill):
    """
    Навык для создания карты проекта и анализа структуры кода через сервисы.
    
    КЛЮЧЕВЫЕ ОТЛИЧИЯ от предыдущей версии:
    - НЕ создаём CodeUnit вручную — получаем готовые объекты от адаптера
    - НЕ извлекаем данные из словарей — работаем с объектами напрямую
    - Агрегируем данные от сервисов, а не создаём их
    """
    
    name = "project_map"
    
    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        logger.info(f"Инициализирован навык карты проекта: {self.name}")
        
        # ИНСТРУМЕНТЫ (низкоуровневые операции)
        self.file_lister_tool: Optional[Any] = None
        self.file_reader_tool: Optional[Any] = None
        
        # СЕРВИСЫ (инфраструктурный анализ кода)
        self.ast_service: Optional[Any] = None
        
        # КЭШИ
        self._file_cache: Dict[str, List[CodeUnit]] = {}  # file_path -> code_units
        self._project_cache: Dict[str, ProjectStructure] = {}  # cache_key -> ProjectStructure
        
        # Список файлов проекта для быстрого поиска
        self.project_files: List[str] = []
    
    async def initialize(self) -> bool:
        """Инициализация навыка и зависимостей."""
        try:
            # 1. Получение инструментов
            self.file_lister_tool = self.system_context.get_resource("file_lister")
            self.file_reader_tool = self.system_context.get_resource("file_reader")
            
            if not all([self.file_lister_tool, self.file_reader_tool]):
                logger.error("Не удалось получить все необходимые инструменты")
                return False
            
            # 2. Получение сервисов анализа кода
            self.ast_service = self.system_context.get_resource("ast_processing")
            
            if self.ast_service:
                logger.error("Не удалось получить сервис анализа кода (ast_processing)")
                return False
            
            logger.info("ProjectMapSkill успешно инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации ProjectMapSkill: {str(e)}", exc_info=True)
            return False
    
    def get_capabilities(self) -> List[Capability]:
        """Получение списка capability навыка."""
        return [
            Capability(
                name="project_map.analyze_project",
                description="Анализ структуры проекта и создание карты кодовой базы через сервисы",
                parameters_schema=AnalyzeProjectInput.model_json_schema(),
                parameters_class=AnalyzeProjectInput,
                skill_name=self.name
            ),
            Capability(
                name="project_map.get_file_code_units",
                description="Получение всех единиц кода (классов, функций) из файла через сервисы анализа",
                parameters_schema=GetFileCodeUnitsInput.model_json_schema(),
                parameters_class=GetFileCodeUnitsInput,
                skill_name=self.name
            )
        ]
    
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """Выполнение capability навыка."""
        try:
            # Валидация параметров через Pydantic модели
            # if isinstance(parameters, ExecutionResult):
            #    return parameters
            
            # Маршрутизация по capability
            if capability.name == "project_map.analyze_project":
                if isinstance(parameters, Dict):
                    param = AnalyzeProjectInput(**parameters)
                else:
                    param = parameters
                return await self._analyze_project(param, context)
            elif capability.name == "project_map.get_file_code_units":
                if isinstance(parameters, Dict):
                    param = GetFileCodeUnitsInput(**parameters)
                else:
                    param = parameters
                return await self._get_file_code_units(param, context)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Неизвестная capability: {capability.name}",
                    error="UNKNOWN_CAPABILITY"
                )
                
        except Exception as e:
            logger.error(f"Ошибка выполнения capability {capability.name}: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка выполнения: {str(e)}",
                error="EXECUTION_ERROR"
            )
    
    async def _analyze_project(self, parameters: AnalyzeProjectInput, context: Any) -> ExecutionResult:
        """
        Анализ структуры проекта с использованием сервисов анализа кода.
        
        КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ:
        - Получаем готовые объекты CodeUnit от сервисов
        - Не создаём объекты вручную — только агрегируем
        - Все метаданные уже содержатся в объектах от адаптера
        """
        try:
            # 1. Проверка кэша
            cache_key = (
                f"{parameters.directory}_{parameters.max_items}_{parameters.include_tests}_"
                f"{parameters.include_hidden}_{','.join(sorted(parameters.file_extensions or []))}"
            )
            
            if cache_key in self._project_cache:
                cached_project_structure = self._project_cache[cache_key]
                logger.info(
                    f"Использован кэшированный результат: "
                    f"{cached_project_structure.total_files} файлов, "
                    f"{cached_project_structure.total_code_units} единиц кода"
                )
                
                observation_id = context.record_observation(
                    {
                        'success': True,
                        'project_structure': cached_project_structure.to_dict(),
                        'file_count': cached_project_structure.total_files,
                        'code_unit_count': cached_project_structure.total_code_units
                    },
                    source=self.name,
                    step_number=getattr(context, 'current_step_number', None),
                    metadata=ContextItemMetadata(
                        source="project_map_skill",
                        confidence=0.95,
                        step_number=getattr(context, 'current_step_number', None)
                    )
                )
                
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    result=cached_project_structure,
                    observation_item_id=observation_id,
                    summary=(
                        f"Кэшированный результат: {cached_project_structure.total_files} файлов, "
                        f"{cached_project_structure.total_code_units} единиц кода"
                    ),
                    error=None
                )
            
            # 2. Получение списка файлов
            file_list_input = FileListerInput(**parameters.to_file_lister_dict)
            file_list_result = await self.file_lister_tool.execute(file_list_input)
            
            if not file_list_result or not file_list_result.items:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary="Не удалось получить список файлов проекта",
                    error="FILE_LIST_ERROR"
                )
            
            files = file_list_result.items
            logger.info(f"Получено файлов от инструмента: {len(files)}")
            
            # 3. Анализ файлов с фильтрацией неподдерживаемых расширений
            self.project_files = []
            code_units_by_file: Dict[str, List[CodeUnit]] = {}
            file_infos: Dict[str, FileInfo] = {}
            
            total_code_units = 0
            scan_start = time.time()
            supported_files_count = 0
            
            for file_item in files:
                if file_item.type != "file":
                    continue
                
                file_path = file_item.path
                
                # Пропускаем слишком большие файлы (>1MB)
                if file_item.size > 1024 * 1024:
                    logger.debug(f"Пропущен большой файл (>1MB): {file_path}")
                    continue
                
                # КРИТИЧЕСКАЯ ФИЛЬТРАЦИЯ: проверяем поддержку языка ДО анализа
                language = await self.ast_service.get_file_language(file_path)
                if not language:
                    logger.debug(f"Пропущен файл с неподдерживаемым расширением: {file_path}")
                    continue
                
                # Анализируем только поддерживаемые файлы
                self.project_files.append(file_path)
                file_units = await self._analyze_file(file_path, parameters.include_code_units)
                
                if file_units:
                    code_units_by_file[file_path] = file_units
                    total_code_units += len(file_units)
                    supported_files_count += 1
                    
                    # Создание FileInfo с готовыми объектами CodeUnit
                    file_info = FileInfo(
                        file_path=file_path,
                        size=file_item.size,
                        last_modified=file_item.last_modified
                    )
                    file_info.code_units = file_units  # Прямое присваивание списка объектов
                    
                    # Извлечение импортов и экспорта из объектов CodeUnit
                    file_info.imports = [
                        unit.name for unit in file_units
                        if unit.type in [CodeUnitType.IMPORT, CodeUnitType.IMPORT_FROM]
                    ]
                    
                    file_info.exports = [
                        unit.name for unit in file_units
                        if unit.type in [CodeUnitType.CLASS, CodeUnitType.FUNCTION]
                        and (unit.parent_id is None or unit.parent_id.endswith(file_path))
                        and not unit.name.startswith('_')
                    ]
                    
                    file_infos[file_path] = file_info
            
            logger.info(
                f"Проанализировано файлов: {supported_files_count} из {len(files)} "
                f"(поддерживаемые расширения: {parameters.file_extensions})"
            )
            
            # 4. Построение структуры проекта
            project_structure = ProjectStructure()
            project_structure.root_dir = parameters.directory
            project_structure.scan_time = time.time()
            project_structure.total_files = len(file_infos)
            project_structure.total_code_units = total_code_units
            
            # Добавление файлов в структуру
            for file_path, file_info in file_infos.items():
                project_structure.files[file_path] = file_info
            
            # Добавление единиц кода в глобальный реестр (из объектов от адаптера)
            for file_path, code_units in code_units_by_file.items():
                for unit in code_units:
                    project_structure.code_units[unit.id] = unit
            
            # 5. Анализ зависимостей и точек входа
            await self._analyze_project_dependencies(project_structure, code_units_by_file)
            await self._find_entry_points(project_structure, code_units_by_file)
            
            # 6. Кэширование и возврат
            self._project_cache[cache_key] = project_structure
            scan_duration = time.time() - scan_start
            
            observation_data = {
                'success': True,
                'project_structure': project_structure.to_dict(),
                'file_count': len(file_infos),
                'code_unit_count': total_code_units,
                'scan_duration': round(scan_duration, 2),
                'supported_files': supported_files_count,
                'total_files_scanned': len(files)
            }
            
            observation_id = context.record_observation(
                observation_data,
                source=self.name,
                step_number=getattr(context, 'current_step_number', None),
                metadata=ContextItemMetadata(
                    source="project_map_skill",
                    confidence=0.95,
                    step_number=getattr(context, 'current_step_number', None)
                )
            )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=project_structure,
                observation_item_id=observation_id,
                summary=(
                    f"Проанализировано {supported_files_count} файлов ({project_structure.total_code_units} единиц кода) "
                    f"за {scan_duration:.2f} сек"
                ),
                error=None
            )
            
        except Exception as e:
            logger.error(f"Ошибка анализа проекта: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка анализа проекта: {str(e)}",
                error="PROJECT_ANALYSIS_ERROR"
            )
    
    async def _analyze_file(self, file_path: str, include_code_units: bool = True) -> List[CodeUnit]:
        """
        Анализ отдельного файла через сервисы.
        
        КЛЮЧЕВОЕ ИЗМЕНЕНИЕ:
        - Получаем готовые объекты CodeUnit от сервиса навигации
        - НЕ создаём объекты вручную — только фильтруем и возвращаем
        """
        # Проверка кэша
        if file_path in self._file_cache:
            return self._file_cache[file_path]
        
        # Проверка поддержки языка
        language = await self.ast_service.get_file_language(file_path)
        if not language:
            logger.debug(f"Пропускаем файл с неподдерживаемым расширением: {file_path}")
            return []
        
        try:
            # 1. Чтение содержимого файла
            file_read_input = FileReadInput(path=file_path)
            file_read_result = await self.file_reader_tool.execute(file_read_input)
            
            if not file_read_result or not file_read_result.content:
                logger.warning(f"Не удалось прочитать файл: {file_path}")
                return []
            
            source_code = file_read_result.content
            source_bytes = source_code.encode('utf-8')
            
            # 2. Парсинг в AST через сервис
            ast = await self.ast_service.parse_file(file_path, source_code)
            if not ast:
                logger.debug(f"Не удалось спарсить файл (язык {language}): {file_path}")
                return []
            
            # 3. Получение структуры файла — ПОЛУЧАЕМ ГОТОВЫЕ ОБЪЕКТЫ CodeUnit
            outline = await self.ast_service.get_file_outline(file_path, source_code)
            
            # 4. outline уже содержит список объектов CodeUnit — просто возвращаем
            if include_code_units:
                # logger.debug(f"Успешно проанализирован файл {file_path}: найдено {len(outline)} единиц кода")
                self._file_cache[file_path] = outline
                return outline
            
            return []
            
        except Exception as e:
            logger.warning(f"Ошибка анализа файла {file_path} ({language}): {str(e)}", exc_info=True)
            return []
    
    async def _analyze_project_dependencies(
        self,
        project_structure: ProjectStructure,
        code_units_by_file: Dict[str, List[CodeUnit]]
    ) -> None:
        """
        Анализ зависимостей между файлами на основе импортов.
        
        РАБОТАЕМ С ОБЪЕКТАМИ:
        - Извлекаем импорты из объектов CodeUnit
        - Разрешаем имена через сервис навигации
        """
        try:
            for file_path, code_units in code_units_by_file.items():
                dependencies: List[FileDependency] = []
                
                # Сбор импортов из объектов CodeUnit
                import_names = [
                    unit.name for unit in code_units
                    if unit.type in [CodeUnitType.IMPORT, CodeUnitType.IMPORT_FROM]
                ]
                
                # Разрешение импортов в пути файлов
                for import_name in import_names:
                    resolved_path = await self._resolve_import_to_file(
                        import_name=import_name,
                        current_file=file_path,
                        project_files=list(code_units_by_file.keys())
                    )
                    
                    if resolved_path:
                        dependencies.append(FileDependency(
                            source_file=file_path,
                            target_file=resolved_path,
                            dependency_type="import"
                        ))
                
                # Добавление зависимостей в структуру
                if dependencies:
                    project_structure.file_dependencies[file_path] = dependencies
            
            logger.debug(f"Проанализированы зависимости для {len(project_structure.file_dependencies)} файлов")
            
        except Exception as e:
            logger.warning(f"Ошибка анализа зависимостей: {str(e)}", exc_info=True)
    
    async def _resolve_import_to_file(
        self,
        import_name: str,
        current_file: str,
        project_files: List[str]
    ) -> Optional[str]:
        """
        Разрешение имени импорта в путь к файлу проекта через адаптер языка.
        """
        try:
            # Получаем адаптер языка через сервис
            language = await self.ast_service.get_file_language(current_file)
            if not language:
                return None
            
            adapter = self.ast_service.language_registry.get_adapter_by_name(language)
            if not adapter:
                return None
            
            # Разрешаем импорт через адаптер
            return await adapter.resolve_import(import_name, current_file, project_files)
            
        except Exception as e:
            logger.debug(f"Не удалось разрешить импорт '{import_name}': {str(e)}")
            return None
    
    async def _find_entry_points(
        self,
        project_structure: ProjectStructure,
        code_units_by_file: Dict[str, List[CodeUnit]]
    ) -> None:
        """
        Поиск точек входа в проекте:
        1. Файлы __main__.py
        2. Блоки if __name__ == "__main__" (будет реализовано позже)
        """
        entry_points: List[EntryPointInfo] = []
        
        for file_path in code_units_by_file.keys():
            # 1. Проверка __main__.py
            if '__main__.py' in file_path.lower():
                entry_points.append(EntryPointInfo(
                    name=os.path.basename(file_path),
                    file_path=file_path,
                    line=1,
                    entry_type="main"
                ))
            
            # 2. Поиск блоков if __name__ == "__main__" (упрощённая реализация)
            # В реальной реализации нужно анализировать AST на наличие таких конструкций
            
        # Удаление дубликатов
        unique_entry_points = []
        seen = set()
        for ep in entry_points:
            key = (ep.name, ep.file_path, ep.line)
            if key not in seen:
                seen.add(key)
                unique_entry_points.append(ep)
        
        project_structure.entry_points = unique_entry_points
    
    async def _get_file_code_units(self, parameters: GetFileCodeUnitsInput, context: Any) -> ExecutionResult:
        """
        Получение единиц кода из конкретного файла.
        
        ВОЗВРАЩАЕТ:
            ExecutionResult с сериализованными объектами CodeUnit
        """
        try:
            # Проверка существования файла
            if not os.path.exists(parameters.file_path):
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Файл не найден: {parameters.file_path}",
                    error="FILE_NOT_FOUND"
                )
            
            # Анализ файла — получаем объекты от сервиса
            code_units = await self._analyze_file(
                parameters.file_path,
                include_code_units=True
            )
            
            # Формирование результата — сериализуем объекты в словари
            result_data = GetFileCodeUnitsOutput(
                success=True,
                file_path=parameters.file_path,
                code_units=code_units,  # Сериализация объектов
                unit_count=len(code_units),
                error=None
            )
            
            # Запись в контекст
            observation_id = context.record_observation(
                result_data.model_dump(),
                source=self.name,
                step_number=getattr(context, 'current_step_number', None),
                metadata=ContextItemMetadata(
                    source="project_map_skill",
                    confidence=0.90,
                    step_number=getattr(context, 'current_step_number', None)
                )
            )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=observation_id,
                summary=f"Найдено {len(code_units)} единиц кода в файле {parameters.file_path}",
                error=None
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения единиц кода из файла {parameters.file_path}: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка получения единиц кода: {str(e)}",
                error="CODE_UNITS_ERROR"
            )
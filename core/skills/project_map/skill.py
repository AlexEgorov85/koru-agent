"""ProjectMapSkill - навык для создания карты проекта.
ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Возврат объекта ProjectStructure вместо словаря
2. Корректное кэширование объектов ProjectStructure
3. Единообразный интерфейс для обоих capability
4. Полное устранение дублирования кода
Архитектурный принцип:
- Все capability возвращают типизированные объекты
- ProjectMapSkill работает с объектами, а не со словарями
- Сериализация происходит только при записи в контекст
Пример использования:
```python
# В другом навыке
project_map_skill = system_context.get_resource("ProjectMapSkill")
if project_map_skill:
    result = await project_map_skill.execute(
        capability=system_context.get_capability("project_map.analyze_project"),
        parameters={
            "root_dir": ".",
            "max_depth": 3,
            "include_tests": False,
            "file_extensions": ["py"]
        },
        context=session_context
    )
# result.result теперь содержит объект ProjectStructure
project_structure = result.result
print(f"Проанализировано файлов: {project_structure.total_files}")
```
"""
import logging
import os
import time
from typing import Dict, Any, List, Optional
from core.skills.base_skill import BaseSkill
from core.skills.project_map.components.ast_processor import ASTProcessor
from core.skills.project_map.components.project_structure_builder import ProjectStructureBuilder
from core.skills.project_map.components.dependency_analyzer import DependencyAnalyzer
from core.skills.project_map.models.code_unit import CodeUnit
from core.skills.project_map.models.project_map import FileInfo
from core.skills.project_map.schema import AnalyzeProjectInput, GetFileCodeUnitsInput
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus
from core.session_context.model import ContextItemMetadata
from pydantic import ValidationError

# Импорт DTO моделей для capability
from core.infrastructure.tools.file_lister_tool import FileListerInput
from core.infrastructure.tools.file_reader_tool import FileReadInput
from core.infrastructure.tools.ast_parser_tool import ASTParserInput

logger = logging.getLogger(__name__)

class ProjectMapSkill(BaseSkill):
    """Навык для создания карты проекта и анализа структуры кода."""
    name = "project_map"

    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        logger.info(f"Инициализирован навык карты проекта: {self.name}")
        # Компоненты навыка
        self.ast_processor = ASTProcessor(self)
        self.structure_builder = ProjectStructureBuilder(self)
        self.dependency_analyzer = DependencyAnalyzer(self)
        # Инструменты будут получены динамически
        self.file_lister_tool = None
        self.file_reader_tool = None
        self.ast_parser_tool = None
        # Кэш для хранения проанализированных структур
        self._file_cache = {}
        self._project_cache = {}
        # Список файлов проекта для быстрого поиска
        self.project_files = []

    async def initialize(self) -> bool:
        """Инициализация навыка."""
        try:
            # Получение инструментов
            self.file_lister_tool = self.system_context.get_resource("FileListerTool")
            self.file_reader_tool = self.system_context.get_resource("FileReaderTool")
            self.ast_parser_tool = self.system_context.get_resource("ASTParserTool")
            if not all([self.file_lister_tool, self.file_reader_tool, self.ast_parser_tool]):
                logger.error("Не удалось получить все необходимые инструменты")
                return False
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации ProjectMapSkill: {str(e)}")
            return False

    def get_capabilities(self) -> List[Capability]:
        """Получение списка capability навыка."""
        return [
            Capability(
                name="project_map.analyze_project",
                description="Анализ структуры проекта и создание карты кодовой базы",
                parameters_schema=AnalyzeProjectInput.model_json_schema(),
                parameters_class=AnalyzeProjectInput,
                skill_name=self.name
            ),
            Capability(
                name="project_map.get_file_code_units",
                description="Получение всех единиц кода (классов, функций) из файла",
                parameters_schema=GetFileCodeUnitsInput.model_json_schema(),
                parameters_class=GetFileCodeUnitsInput,
                skill_name=self.name
            )
        ]

    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """Выполнение capability навыка."""
        try:
            # Валидация параметров через Pydantic модели
            if isinstance(parameters, dict):
                if capability.name == "project_map.analyze_project":
                    try:
                        parameters = AnalyzeProjectInput(**parameters)
                    except ValidationError as e:
                        logger.error(f"Ошибка валидации параметров analyze_project: {str(e)}")
                        return ExecutionResult(
                            status=ExecutionStatus.FAILED,
                            result=None,
                            observation_item_id=None,
                            summary=f"Ошибка валидации параметров: {str(e)}",
                            error="INVALID_PARAMETERS"
                        )
                elif capability.name == "project_map.get_file_code_units":
                    try:
                        parameters = GetFileCodeUnitsInput(**parameters)
                    except ValidationError as e:
                        logger.error(f"Ошибка валидации параметров get_file_code_units: {str(e)}")
                        return ExecutionResult(
                            status=ExecutionStatus.FAILED,
                            result=None,
                            observation_item_id=None,
                            summary=f"Ошибка валидации параметров: {str(e)}",
                            error="INVALID_PARAMETERS"
                        )
            
            # Выполнение capability
            if capability.name == "project_map.analyze_project":
                return await self._analyze_project(parameters, context)
            elif capability.name == "project_map.get_file_code_units":
                return await self._get_file_code_units(parameters, context)
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
        """Анализ структуры проекта с возвратом объекта ProjectStructure."""
        try:
            # Проверка кэша
            cache_key = f"{parameters.root_dir}_{parameters.max_depth}_{parameters.include_tests}_{','.join(sorted(parameters.file_extensions))}"
            if cache_key in self._project_cache:
                logger.info("Использование кэшированного результата анализа проекта")
                cached_project_structure = self._project_cache[cache_key]
                
                # Запись сериализованного объекта в контекст
                observation_id = context.record_observation(
                    cached_project_structure.to_dict(),
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
                    result=cached_project_structure,  # Возвращаем объект
                    observation_item_id=observation_id,
                    summary=f"Использован кэшированный результат анализа проекта с {cached_project_structure.total_files} файлами",
                    error=None
                )

            # 1. Получение списка файлов с помощью инструмента
            file_list_input = FileListerInput(
                path=parameters.root_dir,
                recursive=True,
                max_items=1000,
                include_files=True,
                include_directories=True,
                extensions=parameters.file_extensions
            )
            file_list_result = await self.file_lister_tool.execute(file_list_input)
            if not file_list_result.success:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Ошибка получения списка файлов: {file_list_result.error}",
                    error="FILE_LIST_ERROR"
                )
            files = file_list_result.items or []
            logger.info(f"Найдено файлов для анализа: {len(files)}")

            # 2. Фильтрация файлов (исключение тестов если нужно)
            if not parameters.include_tests:
                files = [f for f in files if "/test/" not in f.path.lower() and "/tests/" not in f.path.lower()]

            # 3. Анализ каждого файла
            self.project_files = [f.path for f in files if f.type == "file"]
            code_units_by_file = {}
            for file_item in files:
                if file_item.type != "file":
                    continue
                file_path = file_item.path
                # Анализ файла
                file_units = await self._analyze_file(file_path)
                if file_units:
                    code_units_by_file[file_path] = file_units

            # 4. Построение структуры проекта через ProjectStructureBuilder
            project_structure = self.structure_builder.build_project_structure(
                root_dir=parameters.root_dir,
                files_info=[{
                    'path': f.path,
                    'size': f.size,
                    'type': f.type,
                    'last_modified': f.last_modified
                } for f in files],
                code_units_by_file=code_units_by_file
            )

            # 5. Сохранение в кэш (кэшируем объект, а не словарь)
            self._project_cache[cache_key] = project_structure

            # 6. Подготовка результата для контекста (сериализация)
            observation_data = {
                'success': True,
                'project_structure': project_structure.to_dict(),
                'file_count': len(files),
                'code_unit_count': sum(len(units) for units in code_units_by_file.values())
            }

            # 7. Запись в контекст
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
            
            # 8. Возврат объекта ProjectStructure
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=project_structure,  # Возвращаем объект ProjectStructure
                observation_item_id=observation_id,
                summary=f"Успешно проанализирован проект: {project_structure.total_files} файлов, {project_structure.total_code_units} единиц кода",
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

    async def _analyze_file(self, file_path: str) -> List[CodeUnit]:
        """Анализ отдельного файла с корректной обработкой AST."""
        try:
            # Проверка кэша
            if file_path in self._file_cache:
                logger.debug(f"Использование кэшированного результата для файла: {file_path}")
                return self._file_cache[file_path]

            # 1. Чтение файла
            file_read_input = FileReadInput(path=file_path)
            file_read_result = await self.file_reader_tool.execute(file_read_input)
            if not file_read_result.success:
                logger.warning(f"Ошибка чтения файла {file_path}: {file_read_result.error}")
                return []
            source_code = file_read_result.content
            source_bytes = source_code.encode('utf-8')  # Важно: байтовое представление

            # 2. Получение AST дерева
            ast_parser_input = ASTParserInput(file_path=file_path, max_depth=15)
            ast_parser_result = await self.ast_parser_tool.execute(ast_parser_input)
            if not ast_parser_result.success:
                logger.warning(f"Ошибка получения AST для файла {file_path}: {ast_parser_result.error}")
                return []

            # 3. Обработка AST с корректным извлечением текста
            tree = ast_parser_result.tree
            code_units = self.ast_processor.process_file_ast(
                tree=tree,
                file_path=file_path,
                source_code=source_code,
                source_bytes=source_bytes  # Передаем байтовое представление
            )

            # 4. Сохранение в кэш
            self._file_cache[file_path] = code_units
            logger.debug(f"Проанализирован файл {file_path}: найдено {len(code_units)} единиц кода")
            return code_units
        except Exception as e:
            logger.error(f"Ошибка анализа файла {file_path}: {str(e)}", exc_info=True)
            return []

    async def _get_file_code_units(self, parameters: GetFileCodeUnitsInput, context: Any) -> ExecutionResult:
        """Получение единиц кода из файла с возвратом объекта FileInfo."""
        try:
            # 1. Анализ файла
            code_units = await self._analyze_file(parameters.file_path)
            if not code_units:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Не найдены единицы кода в файле {parameters.file_path}",
                    error="NO_CODE_UNITS_FOUND"
                )

            # 2. Получение информации о файле
            file_list_input = FileListerInput(
                path=parameters.file_path,
                recursive=False,
                max_items=1,
                include_files=True,
                include_directories=False
            )
            file_list_result = await self.file_lister_tool.execute(file_list_input)
            if not file_list_result.success or not file_list_result.items:
                logger.warning(f"Не удалось получить информацию о файле {parameters.file_path}")
                file_size = 0
                last_modified = time.time()
            else:
                file_item = file_list_result.items[0]
                file_size = file_item.size
                last_modified = file_item.last_modified

            # 3. Построение FileInfo через ProjectStructureBuilder
            files_info = [{
                'path': parameters.file_path,
                'size': file_size,
                'last_modified': last_modified,
                'type': 'file'
            }]
            
            code_units_by_file = {parameters.file_path: code_units}
            
            # Создаем временную ProjectStructure только для этого файла
            temp_project = await self.structure_builder.build_project_structure(
                root_dir=os.path.dirname(parameters.file_path),
                files_info=files_info,
                code_units_by_file=code_units_by_file
            )

            # 4. Извлечение FileInfo для данного файла
            file_info = temp_project.files.get(parameters.file_path)
            if not file_info:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Не удалось построить структуру для файла {parameters.file_path}",
                    error="STRUCTURE_BUILD_FAILED"
                )

            # 5. Формирование результата с правильной сериализацией
            result_units = []
            for unit_id in file_info.code_unit_ids:
                unit = next((u for u in code_units if u.id == unit_id), None)
                if unit:
                    unit_dict = unit.to_dict()
                    if not parameters.include_source_code:
                        unit_dict.pop('source_code', None)
                        unit_dict.pop('source_hash', None)
                    result_units.append(unit_dict)

            # 6. Создание объекта FileInfo для возврата
            result_file_info = FileInfo(
                file_path=parameters.file_path,
                size=file_info.size,
                last_modified=file_info.last_modified
            )
            result_file_info.code_unit_ids = file_info.code_unit_ids
            result_file_info.imports = file_info.imports
            result_file_info.exports = file_info.exports
            result_file_info.dependencies = file_info.dependencies
            result_file_info.code_units = result_units  # Для совместимости с API
            result_file_info.unit_count = len(result_units)

            # 7. Подготовка данных для контекста
            observation_data = {
                'success': True,
                'file_info': result_file_info.to_dict(),
                'file_path': parameters.file_path,
                'unit_count': len(result_units),
                'imports_count': len(result_file_info.imports),
                'exports_count': len(result_file_info.exports),
                'dependencies_count': len(result_file_info.dependencies)
            }

            # 8. Запись наблюдения
            observation_id = context.record_observation(
                observation_data,
                source=self.name,
                step_number=getattr(context, 'current_step_number', None),
                metadata=ContextItemMetadata(
                    source="project_map_skill",
                    confidence=0.90,
                    step_number=getattr(context, 'current_step_number', None)
                )
            )

            # 9. Возврат объекта FileInfo
            result = ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_file_info,  # Возвращаем объект FileInfo
                observation_item_id=observation_id,
                summary=f"Найдено {len(result_units)} единиц кода в файле {parameters.file_path}",
                error=None
            )

            # 10. Кэширование результата для последующего использования
            self._file_cache[parameters.file_path] = code_units
            
            return result

        except Exception as e:
            logger.error(f"Ошибка получения единиц кода из файла {parameters.file_path}: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка получения единиц кода: {str(e)}",
                error="CODE_UNITS_ERROR"
            )
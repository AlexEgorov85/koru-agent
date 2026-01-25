"""ProjectMapSkill - навык для создания карты проекта.

ОСНОВНЫЕ ИСПРАВЛЕНИЯ:
1. Корректная обработка параметров (словарь -> Pydantic модель)
2. Правильная работа с контекстом через record_observation()
3. Безопасное извлечение текста из AST узлов
4. Соответствие архитектуре проекта

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
            "file_extensions": [".py"]
        },
        context=session_context
    )
```
"""

import logging
from typing import Dict, Any, List, Optional
from core.skills.base_skill import BaseSkill
from core.skills.project_map.components.ast_processor import ASTProcessor
from core.skills.project_map.components.project_structure_builder import ProjectStructureBuilder
from core.skills.project_map.models.code_unit import CodeUnit
from core.skills.project_map.schema import AnalyzeProjectInput, GetFileCodeUnitsInput
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus
from pydantic import BaseModel, Field, ValidationError
from core.session_context.model import ContextItemMetadata, ContextItemType
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
        # self.structure_builder = ProjectStructureBuilder(self)
        
        # Инструменты будут получены динамически
        self.file_lister_tool = None
        self.file_reader_tool = None
        self.ast_parser_tool = None
        
        # Кэш для хранения проанализированных файлов
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
        """Анализ структуры проекта."""
        try:
            # Проверка кэша
            cache_key = f"{parameters.root_dir}_{parameters.max_depth}_{parameters.include_tests}_{','.join(sorted(parameters.file_extensions))}"
            if cache_key in self._project_cache:
                logger.info("Использование кэшированного результата анализа проекта")
                cached_result = self._project_cache[cache_key]
                
                # Запись в контекст ===
                observation_id = context.record_observation(
                    cached_result,
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
                    result=cached_result,
                    observation_item_id=observation_id,
                    summary=f"Использован кэшированный результат анализа проекта с {cached_result.get('file_count', 0)} файлами",
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
            
            # 4. Построение структуры проекта
            project_structure = await self._build_project_structure(
                root_dir=parameters.root_dir,
                files=files,
                code_units_by_file=code_units_by_file
            )
            
            # 5. Подготовка результата
            result_data = {
                'success': True,
                'project_structure': project_structure,
                'file_count': len(files),
                'code_unit_count': sum(len(units) for units in code_units_by_file.values())
            }
            
            # Сохранение в кэш
            self._project_cache[cache_key] = result_data
            
            # === ИСПРАВЛЕНО: Правильная запись в контекст ===
            observation_id = context.record_observation(
                result_data,
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
                result=result_data,
                observation_item_id=observation_id,
                summary=f"Успешно проанализирован проект: {len(files)} файлов, {sum(len(units) for units in code_units_by_file.values())} единиц кода",
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
            
            logger.info(f"Проанализирован файл {file_path}: найдено {len(code_units)} единиц кода")
            return code_units
            
        except Exception as e:
            logger.error(f"Ошибка анализа файла {file_path}: {str(e)}", exc_info=True)
            return []
        
    async def _extract_class_definition(self, node, file_path: str, source_code: str) -> Optional[Dict[str, Any]]:
        """Извлечение определения класса с корректной обработкой имен."""
        try:
            # Извлечение имени класса
            name_node = node.child_by_field_name('name')
            if not name_node:
                return None
            
            # Использование .start_byte и .end_byte для получения текста
            class_name = source_code[name_node.start_byte:name_node.end_byte].strip()
            
            if not class_name:
                return None
            
            # Получение текста всего класса
            class_text = source_code[node.start_byte:node.end_byte]
            
            # Извлечение docstring
            docstring = await self._extract_docstring(node, source_code)
            
            # Создание location
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            return {
                'id': f"class_{class_name}_{hash(class_text) % 10000}",
                'name': class_name,
                'type': 'class',
                'location': {
                    'file_path': file_path,
                    'start_line': start_line,
                    'end_line': end_line,
                    'start_column': node.start_point[1] + 1,
                    'end_column': node.end_point[1] + 1
                },
                'source_code': class_text,
                'metadata': {
                    'docstring': docstring,
                    'methods_count': len([c for c in node.children if c.type in ['function_definition', 'async_function_definition']])
                }
            }
        except Exception as e:
            logger.error(f"Ошибка извлечения класса в {file_path}: {str(e)}", exc_info=True)
            return None
    
    async def _extract_function_definition(self, node, file_path: str, source_code: str) -> Optional[Dict[str, Any]]:
        """Извлечение определения функции с корректной обработкой имен."""
        try:
            # Извлечение имени функции
            name_node = node.child_by_field_name('name')
            if not name_node:
                return None
            
            func_name = source_code[name_node.start_byte:name_node.end_byte].strip()
            
            if not func_name:
                return None
            
            # Получение текста всей функции
            func_text = source_code[node.start_byte:node.end_byte]
            
            # Извлечение docstring
            docstring = await self._extract_docstring(node, source_code)
            
            # Создание location
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            return {
                'id': f"func_{func_name}_{hash(func_text) % 10000}",
                'name': func_name,
                'type': 'function',
                'location': {
                    'file_path': file_path,
                    'start_line': start_line,
                    'end_line': end_line,
                    'start_column': node.start_point[1] + 1,
                    'end_column': node.end_point[1] + 1
                },
                'source_code': func_text,
                'metadata': {
                    'docstring': docstring,
                    'is_async': node.type == 'async_function_definition'
                }
            }
        except Exception as e:
            logger.error(f"Ошибка извлечения функции {func_name} в {file_path}: {str(e)}", exc_info=True)
            return None
    
    async def _extract_imports(self, node, file_path: str, source_code: str) -> List[Dict[str, Any]]:
        """Извлечение всех импортов из AST с корректной обработкой."""
        imports = []
        
        def walk_imports(current_node):
            if current_node.type in ['import_statement', 'import_from_statement']:
                # Получение текста импорта
                import_text = source_code[current_node.start_byte:current_node.end_byte]
                
                # Извлечение имен из импорта
                import_names = self._extract_import_names(current_node, source_code)
                
                for name in import_names:
                    if name:
                        imports.append({
                            'id': f"import_{name}_{hash(import_text) % 10000}",
                            'name': name,
                            'type': 'import',
                            'location': {
                                'file_path': file_path,
                                'start_line': current_node.start_point[0] + 1,
                                'end_line': current_node.end_point[0] + 1,
                                'start_column': current_node.start_point[1] + 1,
                                'end_column': current_node.end_point[1] + 1
                            },
                            'source_code': import_text,
                            'metadata': {
                                'import_type': 'from_import' if current_node.type == 'import_from_statement' else 'import'
                            }
                        })
            
            for child in current_node.children:
                walk_imports(child)
        
        walk_imports(node)
        return imports
    
    def _extract_import_names(self, node, source_code: str) -> List[str]:
        """Извлечение имен из узла импорта."""
        names = []
        
        if node.type == 'import_statement':
            for child in node.children:
                if child.type == 'dotted_name':
                    name = source_code[child.start_byte:child.end_byte].split('.')[-1]
                    names.append(name)
        
        elif node.type == 'import_from_statement':
            imports_node = node.child_by_field_name('imports')
            if imports_node:
                for child in imports_node.children:
                    if child.type == 'dotted_name':
                        name = source_code[child.start_byte:child.end_byte].split('.')[-1]
                        names.append(name)
        
        return names
    
    async def _extract_docstring(self, node, source_code: str) -> Optional[str]:
        """Извлечение docstring из узла."""
        try:
            # Поиск тела узла
            body_node = node.child_by_field_name('body')
            if not body_node:
                return None
            
            # Поиск первого выражения в теле
            for child in body_node.children:
                if child.type == 'expression_statement':
                    for grandchild in child.children:
                        if grandchild.type == 'string':
                            # Извлечение текста строкового литерала
                            string_content = source_code[grandchild.start_byte:grandchild.end_byte]
                            # Очистка от кавычек
                            return string_content.strip('"\'')
            return None
        except Exception as e:
            logger.error(f"Ошибка извлечения docstring: {str(e)}")
            return None
    
    async def _extract_class_methods(self, node, file_path: str, source_code: str) -> List[Dict[str, Any]]:
        """Извлечение методов класса."""
        methods = []
        
        # Поиск тела класса
        body_node = node.child_by_field_name('body')
        if not body_node:
            return methods
        
        for child in body_node.children:
            if child.type in ['function_definition', 'async_function_definition']:
                method_unit = await self._extract_function_definition(child, file_path, source_code)
                if method_unit:
                    method_unit['type'] = 'method'  # Изменение типа на метод
                    methods.append(method_unit)
        
        return methods
    
    async def _build_project_structure(self, root_dir: str, files: List[Any], code_units_by_file: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Построение структуры проекта."""
        try:
            # Создание иерархической структуры директорий
            directory_structure = self._build_directory_structure(root_dir, files)
            
            # Анализ зависимостей между файлами
            dependencies = self._analyze_dependencies(code_units_by_file)
            
            # Поиск точек входа
            entry_points = self._find_entry_points(code_units_by_file)
            
            return {
                'root_dir': root_dir,
                'total_files': len(files),
                'total_code_units': sum(len(units) for units in code_units_by_file.values()),
                'directory_structure': directory_structure,
                'dependencies': dependencies,
                'entry_points': entry_points,
                'file_summary': self._get_file_summary(files)
            }
        except Exception as e:
            logger.error(f"Ошибка построения структуры проекта: {str(e)}", exc_info=True)
            return {
                'root_dir': root_dir,
                'total_files': len(files),
                'total_code_units': 0,
                'error': str(e)
            }
    
    def _build_directory_structure(self, root_dir: str, files: List[Any]) -> Dict[str, Any]:
        """Построение иерархической структуры директорий."""
        structure = {'name': root_dir, 'type': 'directory', 'children': []}
        directories = {}
        
        for file_item in files:
            file_path = file_item.path
            parts = file_path.split('/')
            
            current = structure
            path_so_far = root_dir
            
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Последняя часть - файл
                    current['children'].append({
                        'name': part,
                        'type': 'file',
                        'path': file_path,
                        'size': file_item.size,
                        'last_modified': file_item.last_modified
                    })
                else:  # Промежуточная директория
                    path_so_far = f"{path_so_far}/{part}" if path_so_far != root_dir else part
                    dir_key = f"dir_{path_so_far}"
                    
                    if dir_key not in directories:
                        new_dir = {'name': part, 'type': 'directory', 'children': []}
                        current['children'].append(new_dir)
                        directories[dir_key] = new_dir
                    
                    current = directories[dir_key]
        
        return structure
    
    def _analyze_dependencies(self, code_units_by_file: Dict[str, List[CodeUnit]]) -> Dict[str, List[str]]:
        """Анализ зависимостей между файлами."""
        dependencies = {}
        for file_path, code_units in code_units_by_file.items():
            deps = []
            for unit in code_units:
                if unit.type.value == 'import':
                    # Простая эвристика для поиска зависимостей
                    import_name = unit.name
                    for other_file in code_units_by_file.keys():
                        if import_name.lower() in other_file.lower():
                            deps.append(other_file)
            dependencies[file_path] = deps
        return dependencies
    
    def _find_entry_points(self, code_units_by_file: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Поиск точек входа в проекте."""
        entry_points = []
        
        for file_path, code_units in code_units_by_file.items():
            for unit in code_units:
                # Поиск main функций
                if unit.type.value == 'function' and unit.name == 'main':
                    entry_points.append({
                        'name': 'main',
                        'file_path': file_path,
                        'line': unit.location.start_line,
                        'type': 'main'
                    })
                
                # Поиск классов с определенными паттернами имен
                elif unit.type.value == 'class':
                    class_name_lower = unit.name.lower()
                    if ('app' in class_name_lower or 'service' in class_name_lower or 
                        'handler' in class_name_lower):
                        entry_points.append({
                            'name': unit.name,
                            'file_path': file_path,
                            'line': unit.location.start_line,
                            'type': 'class'
                        })
        
        return entry_points
    
    def _get_file_summary(self, files: List[Any]) -> Dict[str, int]:
        """Получение сводки по типам файлов."""
        summary = {}
        for file_item in files:
            if file_item.type == 'file':
                ext = file_item.path.split('.')[-1]
                summary[ext] = summary.get(ext, 0) + 1
        return summary
    
    async def _get_file_code_units(self, parameters: GetFileCodeUnitsInput, context: Any) -> ExecutionResult:
        """Получение единиц кода из файла."""
        try:
            # Анализ файла
            code_units = await self._analyze_file(parameters.file_path)
            
            if not code_units:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Не найдены единицы кода в файле {parameters.file_path}",
                    error="NO_CODE_UNITS_FOUND"
                )
            
            # Подготовка результата
            # if not parameters.include_source_code:
            #     for unit in code_units:
            #         unit.pop('source_code', None)

            result_units = []
            for unit in code_units:
                unit_dict = unit.to_dict()
                # Удаление source_code если не запрошено
                if not parameters.include_source_code:
                    unit_dict.pop('source_code', None)
                    unit_dict.pop('source_hash', None)
                result_units.append(unit_dict)
            
            result_data = {
                'success': True,
                'file_path': parameters.file_path,
                'code_units': result_units,
                'unit_count': len(result_units)
            }
            
            # Запись в контекст
            observation_id = context.record_observation(
                result_data,
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
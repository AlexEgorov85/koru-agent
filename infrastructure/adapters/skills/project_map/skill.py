"""
ProjectMapSkill - навык для создания карты проекта через сервисы анализа кода.
"""
from typing import Dict, Any, List, Optional
import os
from datetime import datetime
import pathlib

from domain.abstractions.skills.base_skill import BaseSkill
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus
from domain.models.capability import Capability
from infrastructure.tools.safe_file_reader_tool import SafeFileReaderTool
from infrastructure.services.code_analysis.python_adapter import PythonLanguageAdapter
from domain.models.project.project_structure import ProjectStructure
from domain.models.project.file_info import FileInfo
from domain.models.project.file_dependency import FileDependency
from domain.models.code.code_unit import CodeUnit


class ProjectMapSkill(BaseSkill):
    """
    Навык для создания карты проекта через инфраструктурные сервисы.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (адаптер)
    - Зависимости: только от абстракций (BaseSkill)
    - Ответственность: агрегация данных от сервисов в доменную модель
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    name = "project_map"
    
    def __init__(self, file_reader_tool=None):
        """Инициализация навыка."""
        self.name = "project_map"
        self.file_reader_tool = file_reader_tool
        self.python_adapter = PythonLanguageAdapter()
    
    def get_capabilities(self) -> List[Capability]:
        """Получение списка capability навыка."""
        return [
            Capability(
                name="project_map.analyze_project",
                description="Анализ структуры проекта и создание карты кодовой базы",
                parameters_schema=None,
                parameters_class=None,
                skill_name=self.name
            )
        ]
    
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """Выполнение capability навыка."""
        try:
            # Маршрутизация по capability
            if capability.name == "project_map.analyze_project":
                return await self._analyze_project(parameters, context)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Неизвестная capability: {capability.name}",
                    error="UNKNOWN_CAPABILITY"
                )
                
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка выполнения: {str(e)}",
                error="EXECUTION_ERROR"
            )
    
    async def _get_file_reader_tool(self, context: Any) -> Optional[SafeFileReaderTool]:
        """Получение FileReaderTool из контекста."""
        if context and isinstance(context, dict):
            return context.get("file_reader_tool")
        return self.file_reader_tool

    def _find_python_files(self, directory: str, max_depth: int = 10, include_hidden: bool = False) -> List[str]:
        """Поиск Python-файлов в директории с ограничением по глубине."""
        python_files = []
        # Используем pathlib для более надежной обработки путей
        start_path = pathlib.Path(directory).resolve()
        start_depth = len(start_path.parts)
        
        for root, dirs, files in os.walk(directory):
            # Ограничение по глубине
            current_path = pathlib.Path(root).resolve()
            current_depth = len(current_path.parts) - start_depth
            if current_depth > max_depth:
                dirs.clear()  # Не заходить глубже
                continue
            
            # Фильтрация скрытых директорий
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            # Поиск Python-файлов
            for file in files:
                if file.endswith('.py') and (include_hidden or not file.startswith('.')):
                    full_file_path = os.path.join(root, file)
                    # Возвращаем относительный путь от директории проекта
                    relative_path = os.path.relpath(full_file_path, directory)
                    python_files.append(relative_path)
        
        return python_files

    async def _read_file_safely(self, file_reader_tool, file_path: str) -> Optional[str]:
        """Безопасное чтение файла через FileReaderTool."""
        try:
            # file_path теперь уже является относительным путем от корня проекта
            # SafeFileReaderTool ожидает пути относительно своего корня
            result = await file_reader_tool.execute({
                "path": file_path,  # file_path уже относительный путь
                "encoding": "utf-8"
            })
            
            if result.get("success", False):
                return result.get("content", "")
            return None
        except Exception:
            return None

    async def _create_file_info(self, file_path: str) -> FileInfo:
        """Создание FileInfo для файла."""
        # Получение информации о файле
        size = 0
        last_modified = 0
        
        # Если file_path - относительный путь, попробуем найти файл в текущей директории
        try:
            full_path = os.path.abspath(file_path)
            stat_info = os.stat(full_path)
            size = stat_info.st_size
            last_modified = stat_info.st_mtime
        except:
            pass
        
        return FileInfo(
            file_path=file_path,
            size=size,
            last_modified=last_modified
        )

    def _resolve_dependencies(self, dependencies, current_file: str, all_files: List[str]) -> List[FileDependency]:
        """Разрешение зависимостей в пути к файлам."""
        from infrastructure.services.code_analysis.analysis_functions import resolve_import
        resolved_deps = []
        
        for dep in dependencies:
            resolved_path = resolve_import(dep.name, current_file, all_files)
            if resolved_path:
                resolved_deps.append(FileDependency(
                    from_file=current_file,
                    to_file=resolved_path,
                    dependency_type=dep.type.value,
                    name=dep.name,
                    alias=dep.alias
                ))
        
        return resolved_deps

    def _validate_project_structure(self, structure: ProjectStructure) -> List[str]:
        """Валидация заполнения полей ProjectStructure."""
        errors = []
        
        if not structure.root_dir:
            errors.append("root_dir не заполнен")
        
        if structure.total_files < 0:
            errors.append("total_files имеет некорректное значение")
        
        if structure.total_code_units < 0:
            errors.append("total_code_units имеет некорректное значение")
        
        # Проверка соответствия счетчиков и фактических данных
        if len(structure.files) != structure.total_files:
            errors.append("Несоответствие между количеством файлов и total_files")
        
        if len(structure.code_units) != structure.total_code_units:
            errors.append("Несоответствие между количеством CodeUnit и total_code_units")
        
        return errors

    async def _analyze_project(self, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """
        Анализ структуры проекта с использованием сервисов анализа кода.
        
        ИНТЕГРАЦИЯ:
        - SafeFileReaderTool: через контекст для безопасного чтения файлов
        - PythonLanguageAdapter: для парсинга Python-файлов и извлечения структуры
        - ProjectStructure: формирование результирующей структуры
        
        ПРОЦЕСС:
        1. Сканирование директории на наличие Python-файлов
        2. Чтение каждого файла через SafeFileReaderTool
        3. Парсинг через PythonLanguageAdapter
        4. Извлечение CodeUnit и зависимостей
        5. Построение полной структуры проекта
        """
        try:
            # Получение параметров
            directory = parameters.get("directory", ".")
            max_depth = parameters.get("max_depth", 10)
            include_hidden = parameters.get("include_hidden", False)
            
            # Валидация входных параметров
            if not os.path.isdir(directory):
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Директория не существует: {directory}",
                    error="INVALID_DIRECTORY"
                )
            
            # Получение инструментов
            file_reader_tool = await self._get_file_reader_tool(context)
            if not file_reader_tool:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary="SafeFileReaderTool не доступен в контексте",
                    error="MISSING_TOOL"
                )
            
            # Инициализация анализатора
            python_adapter = PythonLanguageAdapter()
            
            # Создание структуры проекта
            project_structure = ProjectStructure()
            project_structure.root_dir = os.path.abspath(directory)
            
            # Сбор Python-файлов
            py_files = self._find_python_files(directory, max_depth, include_hidden)
            
            # Инициализация счетчиков
            total_files = 0
            total_code_units = 0
            
            # Хранилища для данных
            all_files = {}
            all_code_units = {}
            all_dependencies = {}
            
            # Анализ каждого файла
            for file_path in py_files:
                try:
                    # Чтение файла
                    file_content = await self._read_file_safely(file_reader_tool, file_path)
                    if file_content is None:
                        continue  # Пропускаем недоступные файлы
                    
                    # Парсинг через PythonLanguageAdapter
                    try:
                        ast_tree = python_adapter.parse(file_content, file_content.encode('utf-8'))
                        
                        # Для передачи в PythonLanguageAdapter используем абсолютный путь, 
                        # чтобы он мог корректно читать файлы для создания CodeSpan
                        absolute_file_path = os.path.join(directory, file_path)
                        
                        # Извлечение структуры
                        code_units = python_adapter.build_code_units(ast_tree, absolute_file_path)
                        dependencies = python_adapter.extract_dependencies(ast_tree)
                        
                        # Обновление структуры проекта
                        file_info = await self._create_file_info(file_path)
                        all_files[file_path] = file_info
                        total_files += 1
                        
                        # Добавление CodeUnit
                        def update_location_recursive(item):
                            """Рекурсивное обновление путей в юните и его потомках."""
                            if hasattr(item, 'location') and hasattr(item.location, 'file_path'):
                                item.location.file_path = file_path
                            if hasattr(item, 'children') and item.children:
                                for child in item.children:
                                    update_location_recursive(child)

                        for unit in code_units:
                            # Обновляем пути в юните и всех его потомках
                            update_location_recursive(unit)
                            all_code_units[unit.id] = unit
                            total_code_units += 1
                        
                        # Обработка зависимостей
                        resolved_deps = self._resolve_dependencies(dependencies, file_path, py_files)
                        if resolved_deps:
                            all_dependencies[file_path] = resolved_deps
                            
                    except Exception as e_parse:
                        # Логируем ошибки парсинга и продолжаем с следующим файлом
                        continue
                        
                except Exception as e:
                    # Логируем ошибки обработки конкретного файла
                    continue
            
            # Заполнение итоговой структуры
            project_structure.files = all_files
            project_structure.code_units = all_code_units
            project_structure.file_dependencies = all_dependencies
            project_structure.total_files = total_files
            project_structure.total_code_units = total_code_units
            project_structure.scan_time = datetime.utcnow()
            
            # Валидация результата
            validation_errors = self._validate_project_structure(project_structure)
            if validation_errors:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Ошибка валидации структуры проекта: {validation_errors}",
                    error="VALIDATION_ERROR"
                )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=project_structure,
                observation_item_id=None,
                summary=f"Проект успешно проанализирован: {total_files} файлов, {total_code_units} единиц кода",
                error=None
            )
        
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Критическая ошибка анализа проекта: {str(e)}",
                error="CRITICAL_ERROR"
            )
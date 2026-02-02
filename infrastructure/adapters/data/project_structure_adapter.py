"""
Преобразование структуры проекта
"""
from typing import Dict, Any, List
from domain.models.project.project_structure import ProjectStructure
from domain.models.code.code_unit import CodeUnit
from domain.models.project.file_info import FileInfo
from domain.models.project.file_dependency import FileDependency
from domain.models.project.entry_point import EntryPointInfo


class ProjectStructureAdapter:
    """
    Адаптер для преобразования структуры проекта между инфраструктурными и доменными моделями
    """
    
    @staticmethod
    def to_domain_model(data: Dict[str, Any]) -> ProjectStructure:
        """
        Преобразование данных из инфраструктурного слоя в доменную модель ProjectStructure
        """
        project_structure = ProjectStructure()
        
        # Заполнение основных полей
        project_structure.root_dir = data.get('root_dir', '')
        project_structure.scan_time = data.get('scan_time')
        project_structure.total_files = data.get('total_files', 0)
        project_structure.total_code_units = data.get('total_code_units', 0)
        
        # Заполнение файлов
        raw_files = data.get('files', {})
        for file_path, file_info_data in raw_files.items():
            file_info = FileInfo(
                file_path=file_info_data.get('file_path', ''),
                size=file_info_data.get('size', 0),
                last_modified=file_info_data.get('last_modified')
            )
            # Добавление единиц кода
            raw_code_units = file_info_data.get('code_units', [])
            for unit_data in raw_code_units:
                code_unit = CodeUnit(
                    id=unit_data.get('id'),
                    name=unit_data.get('name', ''),
                    type=unit_data.get('type', ''),
                    file_path=unit_data.get('file_path', ''),
                    line_start=unit_data.get('line_start'),
                    line_end=unit_data.get('line_end'),
                    parent_id=unit_data.get('parent_id'),
                    children_ids=unit_data.get('children_ids', []),
                    content=unit_data.get('content', ''),
                    metadata=unit_data.get('metadata', {})
                )
                file_info.code_units.append(code_unit)
            
            project_structure.files[file_path] = file_info
        
        # Заполнение единиц кода
        raw_code_units = data.get('code_units', {})
        for unit_id, unit_data in raw_code_units.items():
            code_unit = CodeUnit(
                id=unit_id,
                name=unit_data.get('name', ''),
                type=unit_data.get('type', ''),
                file_path=unit_data.get('file_path', ''),
                line_start=unit_data.get('line_start'),
                line_end=unit_data.get('line_end'),
                parent_id=unit_data.get('parent_id'),
                children_ids=unit_data.get('children_ids', []),
                content=unit_data.get('content', ''),
                metadata=unit_data.get('metadata', {})
            )
            project_structure.code_units[unit_id] = code_unit
        
        # Заполнение зависимостей
        raw_dependencies = data.get('file_dependencies', {})
        for file_path, deps_data in raw_dependencies.items():
            dependencies = []
            for dep_data in deps_data:
                dependency = FileDependency(
                    source_file=dep_data.get('source_file', ''),
                    target_file=dep_data.get('target_file', ''),
                    dependency_type=dep_data.get('dependency_type', 'import')
                )
                dependencies.append(dependency)
            project_structure.file_dependencies[file_path] = dependencies
        
        # Заполнение точек входа
        raw_entry_points = data.get('entry_points', [])
        entry_points = []
        for ep_data in raw_entry_points:
            entry_point = EntryPointInfo(
                name=ep_data.get('name', ''),
                file_path=ep_data.get('file_path', ''),
                line=ep_data.get('line', 1),
                entry_type=ep_data.get('entry_type', 'main')
            )
            entry_points.append(entry_point)
        
        project_structure.entry_points = entry_points
        
        return project_structure
    
    @staticmethod
    def to_infrastructure_model(project_structure: ProjectStructure) -> Dict[str, Any]:
        """
        Преобразование доменной модели ProjectStructure в формат инфраструктурного слоя
        """
        result = {
            'root_dir': project_structure.root_dir,
            'scan_time': project_structure.scan_time,
            'total_files': project_structure.total_files,
            'total_code_units': project_structure.total_code_units,
            'files': {},
            'code_units': {},
            'file_dependencies': {},
            'entry_points': []
        }
        
        # Преобразование файлов
        for file_path, file_info in project_structure.files.items():
            result['files'][file_path] = {
                'file_path': file_info.file_path,
                'size': file_info.size,
                'last_modified': file_info.last_modified,
                'code_units': [
                    {
                        'id': unit.id,
                        'name': unit.name,
                        'type': unit.type,
                        'file_path': unit.file_path,
                        'line_start': unit.line_start,
                        'line_end': unit.line_end,
                        'parent_id': unit.parent_id,
                        'children_ids': unit.children_ids,
                        'content': unit.content,
                        'metadata': unit.metadata
                    }
                    for unit in file_info.code_units
                ]
            }
        
        # Преобразование единиц кода
        for unit_id, code_unit in project_structure.code_units.items():
            result['code_units'][unit_id] = {
                'id': code_unit.id,
                'name': code_unit.name,
                'type': code_unit.type,
                'file_path': code_unit.file_path,
                'line_start': code_unit.line_start,
                'line_end': code_unit.line_end,
                'parent_id': code_unit.parent_id,
                'children_ids': code_unit.children_ids,
                'content': code_unit.content,
                'metadata': code_unit.metadata
            }
        
        # Преобразование зависимостей
        for file_path, dependencies in project_structure.file_dependencies.items():
            result['file_dependencies'][file_path] = [
                {
                    'source_file': dep.source_file,
                    'target_file': dep.target_file,
                    'dependency_type': dep.dependency_type
                }
                for dep in dependencies
            ]
        
        # Преобразование точек входа
        for entry_point in project_structure.entry_points:
            result['entry_points'].append({
                'name': entry_point.name,
                'file_path': entry_point.file_path,
                'line': entry_point.line,
                'entry_type': entry_point.entry_type
            })
        
        return result
    
    @staticmethod
    def merge_project_structures(base_structure: ProjectStructure, new_structure: ProjectStructure) -> ProjectStructure:
        """
        Объединение двух структур проекта
        """
        merged = ProjectStructure()
        
        # Копируем основную информацию из базовой структуры
        merged.root_dir = base_structure.root_dir
        merged.scan_time = max(base_structure.scan_time or 0, new_structure.scan_time or 0)
        merged.total_files = len(set(base_structure.files.keys()) | set(new_structure.files.keys()))
        
        # Объединяем файлы
        for file_path, file_info in base_structure.files.items():
            merged.files[file_path] = file_info
        
        for file_path, file_info in new_structure.files.items():
            if file_path not in merged.files:
                merged.files[file_path] = file_info
            else:
                # Если файл уже существует, объединяем информацию о нем
                base_info = merged.files[file_path]
                # Объединяем единицы кода
                existing_ids = {unit.id for unit in base_info.code_units}
                new_units = [unit for unit in file_info.code_units if unit.id not in existing_ids]
                base_info.code_units.extend(new_units)
        
        # Объединяем единицы кода
        for unit_id, code_unit in base_structure.code_units.items():
            merged.code_units[unit_id] = code_unit
        
        for unit_id, code_unit in new_structure.code_units.items():
            if unit_id not in merged.code_units:
                merged.code_units[unit_id] = code_unit
        
        # Объединяем зависимости
        for file_path, dependencies in base_structure.file_dependencies.items():
            merged.file_dependencies[file_path] = dependencies
        
        for file_path, dependencies in new_structure.file_dependencies.items():
            if file_path not in merged.file_dependencies:
                merged.file_dependencies[file_path] = dependencies
            else:
                # Объединяем зависимости
                existing_deps = set((dep.source_file, dep.target_file) for dep in merged.file_dependencies[file_path])
                new_deps = [dep for dep in dependencies if (dep.source_file, dep.target_file) not in existing_deps]
                merged.file_dependencies[file_path].extend(new_deps)
        
        # Объединяем точки входа
        merged.entry_points = base_structure.entry_points + [
            ep for ep in new_structure.entry_points
            if not any(ex_ep.file_path == ep.file_path and ex_ep.line == ep.line for ex_ep in base_structure.entry_points)
        ]
        
        # Пересчитываем количество единиц кода
        merged.total_code_units = len(merged.code_units)
        
        return merged
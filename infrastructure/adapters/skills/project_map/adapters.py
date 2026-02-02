"""
Адаптеры преобразования для ProjectMapSkill
"""
from typing import List, Dict, Any, Optional
from domain.models.code.code_unit import CodeUnit
from domain.models.project.project_structure import ProjectStructure


def adapt_code_units(raw_code_units: List[Dict[str, Any]]) -> List[CodeUnit]:
    """
    Преобразование сырых данных о единицах кода в доменные модели CodeUnit
    """
    adapted_units = []
    for unit_data in raw_code_units:
        # Создание CodeUnit из словаря
        code_unit = CodeUnit(
            id=unit_data.get('id'),
            name=unit_data.get('name'),
            type=unit_data.get('type'),
            file_path=unit_data.get('file_path'),
            line_start=unit_data.get('line_start'),
            line_end=unit_data.get('line_end'),
            parent_id=unit_data.get('parent_id'),
            children_ids=unit_data.get('children_ids', []),
            content=unit_data.get('content'),
            metadata=unit_data.get('metadata', {})
        )
        adapted_units.append(code_unit)
    
    return adapted_units


def adapt_project_structure(raw_structure: Dict[str, Any]) -> ProjectStructure:
    """
    Преобразование сырой структуры проекта в доменную модель ProjectStructure
    """
    project_structure = ProjectStructure()
    
    # Заполнение основных полей
    project_structure.root_dir = raw_structure.get('root_dir', '')
    project_structure.scan_time = raw_structure.get('scan_time')
    project_structure.total_files = raw_structure.get('total_files', 0)
    project_structure.total_code_units = raw_structure.get('total_code_units', 0)
    
    # Заполнение файлов и единиц кода
    raw_files = raw_structure.get('files', {})
    for file_path, file_info in raw_files.items():
        # Здесь нужно адаптировать информацию о файле
        project_structure.files[file_path] = file_info
    
    raw_units = raw_structure.get('code_units', {})
    for unit_id, unit_data in raw_units.items():
        # Преобразование и добавление единиц кода
        code_unit = CodeUnit(
            id=unit_data.get('id'),
            name=unit_data.get('name'),
            type=unit_data.get('type'),
            file_path=unit_data.get('file_path'),
            line_start=unit_data.get('line_start'),
            line_end=unit_data.get('line_end'),
            parent_id=unit_data.get('parent_id'),
            children_ids=unit_data.get('children_ids', []),
            content=unit_data.get('content'),
            metadata=unit_data.get('metadata', {})
        )
        project_structure.code_units[unit_id] = code_unit
    
    return project_structure
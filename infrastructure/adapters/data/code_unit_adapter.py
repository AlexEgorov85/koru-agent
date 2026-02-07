"""
Преобразование между инфраструктурными и доменными моделями кода
"""
from typing import List, Dict, Any, Union
from domain.core.project.value_objects.code_unit import CodeUnit


class CodeUnitAdapter:
    """
    Адаптер для преобразования между инфраструктурными и доменными моделями CodeUnit
    """
    
    @staticmethod
    def to_domain_model(data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Union[CodeUnit, List[CodeUnit]]:
        """
        Преобразование данных из инфраструктурного слоя в доменную модель CodeUnit
        """
        if isinstance(data, list):
            return [CodeUnitAdapter._dict_to_code_unit(item) for item in data]
        else:
            return CodeUnitAdapter._dict_to_code_unit(data)
    
    @staticmethod
    def to_infrastructure_model(code_unit: Union[CodeUnit, List[CodeUnit]]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Преобразование доменной модели CodeUnit в формат инфраструктурного слоя
        """
        if isinstance(code_unit, list):
            return [CodeUnitAdapter._code_unit_to_dict(item) for item in code_unit]
        else:
            return CodeUnitAdapter._code_unit_to_dict(code_unit)
    
    @staticmethod
    def _dict_to_code_unit(data: Dict[str, Any]) -> CodeUnit:
        """
        Преобразование словаря в объект CodeUnit
        """
        return CodeUnit(
            id=data.get('id'),
            name=data.get('name', ''),
            type=data.get('type', ''),
            file_path=data.get('file_path', ''),
            line_start=data.get('line_start'),
            line_end=data.get('line_end'),
            parent_id=data.get('parent_id'),
            children_ids=data.get('children_ids', []),
            content=data.get('content', ''),
            metadata=data.get('metadata', {})
        )
    
    @staticmethod
    def _code_unit_to_dict(code_unit: CodeUnit) -> Dict[str, Any]:
        """
        Преобразование объекта CodeUnit в словарь
        """
        return {
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
    
    @staticmethod
    def merge_code_units(existing_units: List[CodeUnit], new_units: List[CodeUnit]) -> List[CodeUnit]:
        """
        Объединение существующих и новых единиц кода с избежанием дубликатов
        """
        existing_ids = {unit.id for unit in existing_units}
        unique_new_units = [unit for unit in new_units if unit.id not in existing_ids]
        
        return existing_units + unique_new_units
    
    @staticmethod
    def filter_code_units(units: List[CodeUnit], filters: Dict[str, Any]) -> List[CodeUnit]:
        """
        Фильтрация единиц кода по заданным критериям
        """
        filtered_units = units
        
        # Фильтрация по типу
        if 'type' in filters:
            filtered_units = [unit for unit in filtered_units if unit.type == filters['type']]
        
        # Фильтрация по файлу
        if 'file_path' in filters:
            filtered_units = [unit for unit in filtered_units if unit.file_path == filters['file_path']]
        
        # Фильтрация по имени
        if 'name' in filters:
            filtered_units = [unit for unit in filtered_units if filters['name'] in unit.name]
        
        # Фильтрация по родительскому элементу
        if 'parent_id' in filters:
            filtered_units = [unit for unit in filtered_units if unit.parent_id == filters['parent_id']]
        
        return filtered_units
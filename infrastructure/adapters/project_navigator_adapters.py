"""
Адаптеры преобразования для ProjectNavigatorSkill
"""
from typing import List, Dict, Any, Optional
from domain.core.project.value_objects.code_unit import CodeUnit


def adapt_code_unit_navigation(raw_code_unit: Dict[str, Any]) -> CodeUnit:
    """
    Преобразование сырой информации о единице кода в доменную модель CodeUnit
    для целей навигации
    """
    code_unit = CodeUnit(
        id=raw_code_unit.get('id'),
        name=raw_code_unit.get('name'),
        type=raw_code_unit.get('type'),
        file_path=raw_code_unit.get('file_path'),
        line_start=raw_code_unit.get('line_start'),
        line_end=raw_code_unit.get('line_end'),
        parent_id=raw_code_unit.get('parent_id'),
        children_ids=raw_code_unit.get('children_ids', []),
        content=raw_code_unit.get('content'),
        metadata=raw_code_unit.get('metadata', {})
    )
    
    return code_unit


def adapt_navigation_results(raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Преобразование результатов навигации к стандартному формату
    """
    adapted_results = []
    for result in raw_results:
        adapted_result = {
            'element': result.get('element', {}),
            'location': result.get('location', {}),
            'context': result.get('context', ''),
            'score': result.get('score', 0.0),
            'type': result.get('type', 'unknown')
        }
        adapted_results.append(adapted_result)
    
    return adapted_results


def adapt_dependency_relationships(raw_relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Преобразование отношений зависимостей к стандартному формату
    """
    adapted_relationships = []
    for relationship in raw_relationships:
        adapted_relationship = {
            'source': relationship.get('source', ''),
            'target': relationship.get('target', ''),
            'type': relationship.get('type', 'unknown'),
            'strength': relationship.get('strength', 1.0),
            'context': relationship.get('context', {})
        }
        adapted_relationships.append(adapted_relationship)
    
    return adapted_relationships
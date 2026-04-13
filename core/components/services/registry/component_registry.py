"""
Реестр компонентов прикладного контекста.

ЕДИНОЕ место хранения всех компонентов:
- Сервисы (PromptService, ContractService, ...)
- Навыки (PlanningSkill, DataAnalysisSkill, ...)
- Инструменты (BaseTool подклассы)
- Паттерны поведения (ReActPattern, ...)
"""
from typing import Dict, List, Optional
from core.models.enums.common_enums import ComponentType


class ComponentRegistry:
    """
    Единый реестр ВСЕХ компонентов прикладного контекста.
    
    THREAD-SAFE: Все операции атомарные.
    
    USAGE:
    ```python
    registry = ComponentRegistry()
    
    # Регистрация
    registry.register(ComponentType.SERVICE, "prompt_service", service_instance)
    registry.register(ComponentType.SKILL, "planning", skill_instance)

    # Получение
    service = registry.get(ComponentType.SERVICE, "prompt_service")
    skill = registry.get(ComponentType.SKILL, "planning")
    
    # Все компоненты типа
    all_skills = registry.all_of_type(ComponentType.SKILL)
    
    # Все компоненты
    all_components = registry.all_components()
    ```
    """

    def __init__(self):
        """
        Инициализация реестра.
        
        СТРУКТУРА:
        {
            ComponentType.SERVICE: {"prompt_service": instance, ...},
            ComponentType.SKILL: {"planning": instance, ...},
            ComponentType.TOOL: {"search_tool": instance, ...},
            ComponentType.BEHAVIOR: {"react": instance, ...}
        }
        """
        # {component_type: {component_name: component_instance}}
        self._components: Dict[ComponentType, Dict[str, object]] = {
            t: {} for t in ComponentType
        }

    def register(
        self,
        component_type: ComponentType,
        name: str,
        component: object
    ) -> None:
        """
        Зарегистрировать компонент.
        
        ARGS:
        - component_type: Тип компонента (SERVICE, SKILL, TOOL, BEHAVIOR)
        - name: Уникальное имя компонента
        - component: Экземпляр компонента
        
        RAISES:
        - ValueError: Если компонент с таким именем уже зарегистрирован
        """
        if name in self._components[component_type]:
            raise ValueError(
                f"Компонент {component_type.value}.{name} уже зарегистрирован"
            )
        self._components[component_type][name] = component

    def get(
        self,
        component_type: ComponentType,
        name: str
    ) -> Optional[object]:
        """
        Получить компонент по имени.
        
        ARGS:
        - component_type: Тип компонента
        - name: Имя компонента
        
        RETURNS:
        - Экземпляр компонента или None если не найден
        """
        return self._components[component_type].get(name)

    def all_of_type(self, component_type: ComponentType) -> List[object]:
        """
        Получить все компоненты указанного типа.
        
        ARGS:
        - component_type: Тип компонентов
        
        RETURNS:
        - Список экземпляров компонентов
        """
        return list(self._components[component_type].values())

    def all_components(self) -> List[object]:
        """
        Получить все компоненты.
        
        RETURNS:
        - Плоский список всех зарегистрированных компонентов
        """
        return [
            comp
            for comps in self._components.values()
            for comp in comps.values()
        ]

    def clear(self) -> None:
        """
        Очистить реестр.
        
        ВАЖНО: Не вызывает shutdown() у компонентов.
        """
        for components in self._components.values():
            components.clear()

    def count(self, component_type: Optional[ComponentType] = None) -> int:
        """
        Подсчитать количество компонентов.
        
        ARGS:
        - component_type: Тип компонентов (None = все типы)
        
        RETURNS:
        - Количество компонентов
        """
        if component_type is None:
            return sum(len(comps) for comps in self._components.values())
        return len(self._components[component_type])

    def exists(
        self,
        component_type: ComponentType,
        name: str
    ) -> bool:
        """
        Проверить наличие компонента.
        
        ARGS:
        - component_type: Тип компонента
        - name: Имя компонента
        
        RETURNS:
        - True если компонент зарегистрирован
        """
        return name in self._components[component_type]

    def __repr__(self) -> str:
        counts = {
            t.value: len(comps)
            for t, comps in self._components.items()
            if comps
        }
        return f"ComponentRegistry({counts})"

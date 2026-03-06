"""
Валидатор контекста — проверка состояния компонентов.

СОДЕРЖИТ:
- ValidationResult: результат валидации
- ContextValidator: валидация состояния прикладного контекста
"""
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """
    Результат валидации контекста.
    
    USAGE:
    ```python
    result = validator.validate_all_initialized()
    
    if not result.is_valid:
        for error in result.errors:
            logger.error(error)
        for warning in result.warnings:
            logger.warning(warning)
    ```
    """
    
    # Список ошибок (критичные проблемы)
    errors: List[str] = field(default_factory=list)
    
    # Список предупреждений (некритичные проблемы)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Проверка отсутствия ошибок."""
        return len(self.errors) == 0
    
    @property
    def has_warnings(self) -> bool:
        """Проверка наличия предупреждений."""
        return len(self.warnings) > 0
    
    def add_error(self, message: str) -> None:
        """Добавить ошибку."""
        self.errors.append(message)
    
    def add_warning(self, message: str) -> None:
        """Добавить предупреждение."""
        self.warnings.append(message)
    
    def merge(self, other: 'ValidationResult') -> None:
        """
        Объединить с другим результатом валидации.
        
        ARGS:
        - other: Другой результат для объединения
        """
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
    
    def __repr__(self) -> str:
        status = "✓ VALID" if self.is_valid else "✗ INVALID"
        return f"ValidationResult({status}, errors={len(self.errors)}, warnings={len(self.warnings)})"


class ContextValidator:
    """
    Валидатор состояния прикладного контекста.
    
    ПРОВЕРКИ:
    1. Все компоненты инициализированы (READY)
    2. Нет компонентов в состоянии FAILED
    3. Зависимости между компонентами разрешены
    4. Конфигурация корректна
    
    USAGE:
    ```python
    validator = ContextValidator(registry)
    
    # Проверка инициализации
    result = validator.validate_all_initialized()
    if not result.is_valid:
        raise ValidationError(result.errors)
    
    # Проверка зависимостей
    result = validator.validate_dependencies()
    ```
    """
    
    def __init__(self, registry):
        """
        Инициализация валидатора.
        
        ARGS:
        - registry: ComponentRegistry для проверки компонентов
        """
        self._registry = registry
    
    def validate_all_initialized(self) -> ValidationResult:
        """
        Проверить, что все компоненты инициализированы.
        
        ПРОВЕРКА:
        - У каждого компонента state == READY или is_initialized == True
        
        RETURNS:
        - ValidationResult с ошибками если есть неинициализированные
        """
        result = ValidationResult()
        
        for component in self._registry.all_components():
            # Проверка через атрибут state (если есть)
            if hasattr(component, 'state'):
                state_value = component.state
                if hasattr(state_value, 'value'):
                    # ComponentState enum
                    if state_value.value not in ('ready', 'initialized', 'shutdown'):
                        component_name = getattr(component, 'name', str(component))
                        result.add_error(
                            f"Компонент '{component_name}' не инициализирован "
                            f"(state={state_value.value})"
                        )
                elif not state_value:
                    component_name = getattr(component, 'name', str(component))
                    result.add_error(
                        f"Компонент '{component_name}' не инициализирован "
                        f"(state={state_value})"
                    )
            
            # Проверка через атрибут is_initialized (если есть)
            elif hasattr(component, 'is_initialized'):
                if not component.is_initialized:
                    component_name = getattr(component, 'name', str(component))
                    result.add_error(
                        f"Компонент '{component_name}' не инициализирован"
                    )
            
            # Проверка через атрибут _initialized (если есть)
            elif hasattr(component, '_initialized'):
                if not component._initialized:
                    component_name = getattr(component, 'name', str(component))
                    result.add_error(
                        f"Компонент '{component_name}' не инициализирован"
                    )
        
        return result
    
    def validate_no_failed_components(self) -> ValidationResult:
        """
        Проверить, что нет компонентов в состоянии FAILED.
        
        RETURNS:
        - ValidationResult с ошибками если есть упавшие компоненты
        """
        result = ValidationResult()
        
        for component in self._registry.all_components():
            # Проверка через атрибут is_failed
            if hasattr(component, 'is_failed'):
                if component.is_failed:
                    component_name = getattr(component, 'name', str(component))
                    result.add_error(
                        f"Компонент '{component_name}' в состоянии FAILED"
                    )
            
            # Проверка через атрибут state
            elif hasattr(component, 'state'):
                state_value = component.state
                if hasattr(state_value, 'value'):
                    if state_value.value == 'failed':
                        component_name = getattr(component, 'name', str(component))
                        result.add_error(
                            f"Компонент '{component_name}' в состоянии FAILED"
                        )
        
        return result
    
    def validate_dependencies(self) -> ValidationResult:
        """
        Проверить зависимости между компонентами.
        
        ПРОВЕРКА:
        - Если компонент имеет DEPENDENCIES, все зависимости должны существовать
        
        RETURNS:
        - ValidationResult с ошибками если есть неразрешённые зависимости
        """
        result = ValidationResult()
        
        for component in self._registry.all_components():
            # Проверка атрибута DEPENDENCIES
            if hasattr(component, 'DEPENDENCIES'):
                dependencies = getattr(component, 'DEPENDENCIES', [])
                component_name = getattr(component, 'name', str(component))
                
                for dep_name in dependencies:
                    if not self._dependency_exists(dep_name):
                        result.add_error(
                            f"Компонент '{component_name}' требует зависимость "
                            f"'{dep_name}', которая не найдена"
                        )
            
            # Проверка атрибута _dependencies
            if hasattr(component, '_dependencies'):
                dependencies = getattr(component, '_dependencies', [])
                component_name = getattr(component, 'name', str(component))
                
                for dep_name in dependencies:
                    if not self._dependency_exists(dep_name):
                        result.add_warning(
                            f"Компонент '{component_name}' имеет необязательную "
                            f"зависимость '{dep_name}'"
                        )
        
        return result
    
    def validate_registry_not_empty(self) -> ValidationResult:
        """
        Проверить, что реестр не пуст.
        
        RETURNS:
        - ValidationResult с предупреждением если реестр пуст
        """
        result = ValidationResult()
        
        if self._registry.count() == 0:
            result.add_warning("Реестр компонентов пуст")
        
        return result
    
    def validate_all(self) -> ValidationResult:
        """
        Выполнить все проверки.
        
        RETURNS:
        - Объединённый результат всех проверок
        """
        result = ValidationResult()
        
        # Выполняем все проверки
        result.merge(self.validate_registry_not_empty())
        result.merge(self.validate_all_initialized())
        result.merge(self.validate_no_failed_components())
        result.merge(self.validate_dependencies())
        
        return result
    
    def _dependency_exists(self, dep_name: str) -> bool:
        """
        Проверить существование зависимости.
        
        ARGS:
        - dep_name: Имя зависимости
        
        RETURNS:
        - True если зависимость найдена в любом типе компонентов
        """
        from core.models.enums.common_enums import ComponentType
        
        # Проверяем во всех типах компонентов
        for component_type in ComponentType:
            if self._registry.exists(component_type, dep_name):
                return True
        
        return False
    
    def __repr__(self) -> str:
        return f"ContextValidator(components={self._registry.count()})"

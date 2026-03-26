"""
ValidationService — сервис для валидации данных через Pydantic схемы.

АРХИТЕКТУРА:
- Не зависит от компонентов (BaseComponent, ApplicationContext)
- Используется через ActionExecutor ("validation.validate")
- Локальная валидация без дополнительных вызовов executor
- Минимальная ответственность: только валидация

ЖИЗНЕННЫЙ ЦИКЛ:
- Создаётся как обычный сервис
- Не требует инициализации (нет внешних зависимостей)
"""
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, ValidationError


class ValidationResult:
    """Результат валидации."""
    
    def __init__(
        self,
        is_valid: bool,
        validated_data: Optional[BaseModel] = None,
        error: Optional[str] = None
    ):
        self.is_valid = is_valid
        self.validated_data = validated_data
        self.error = error
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def model_dump(self) -> Dict[str, Any]:
        """Сериализация результата."""
        return {
            "is_valid": self.is_valid,
            "validated_data": self.validated_data.model_dump() if self.validated_data else None,
            "error": self.error
        }


class ValidationService:
    """
    Сервис валидации данных через Pydantic схемы.
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    service = ValidationService()
    
    # Валидация с возвратом результата
    result = service.validate(MySchema, {"field": "value"})
    if result.is_valid:
        data = result.validated_data.field
    else:
        print(f"Ошибка: {result.error}")
    
    # Быстрая проверка
    if service.is_valid(MySchema, data):
        ...
    
    # Валидация без схемы (базовая проверка)
    result = service.validate_dict({"key": "value"})
    ```
    """
    
    def validate(
        self,
        schema: Type[BaseModel],
        data: Any
    ) -> ValidationResult:
        """
        Валидация данных через Pydantic схему.
        
        ПАРАМЕТРЫ:
        - schema: Pydantic модель для валидации
        - data: Данные для валидации (dict или любая структура)
        
        ВОЗВРАЩАЕТ:
        - ValidationResult: результат валидации
        
        ПРИМЕР:
        ```python
        result = service.validate(UserSchema, {"name": "John", "age": 30})
        if result.is_valid:
            user = result.validated_data  # UserSchema instance
        ```
        """
        try:
            validated = schema.model_validate(data)
            return ValidationResult(is_valid=True, validated_data=validated)
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                error=f"Validation error: {e.error_count()} errors"
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def is_valid(self, schema: Type[BaseModel], data: Any) -> bool:
        """
        Быстрая проверка валидности без возврата данных.
        
        ПАРАМЕТРЫ:
        - schema: Pydantic модель для валидации
        - data: Данные для валидации
        
        ВОЗВРАЩАЕТ:
        - bool: True если валидация пройдена
        
        ПРИМЕР:
        ```python
        if service.is_valid(UserSchema, data):
            # Данные валидны
        ```
        """
        try:
            schema.model_validate(data)
            return True
        except Exception:
            return False
    
    def validate_dict(self, data: Any) -> ValidationResult:
        """
        Базовая валидация словаря (без схемы).
        
        ПАРАМЕТРЫ:
        - data: Данные для валидации
        
        ВОЗВРАЩАЕТ:
        - ValidationResult: результат валидации
        
        ПРИМЕЧАНИЕ:
        Проверяет только что data является dict и не None.
        """
        if data is None:
            return ValidationResult(is_valid=False, error="Data is None")
        
        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                error=f"Expected dict, got {type(data).__name__}"
            )
        
        return ValidationResult(is_valid=True, validated_data=data)
    
    def validate_batch(
        self,
        schema: Type[BaseModel],
        items: list
    ) -> list[ValidationResult]:
        """
        Пакетная валидация списка данных.
        
        ПАРАМЕТРЫ:
        - schema: Pydantic модель для валидации
        - items: Список данных для валидации
        
        ВОЗВРАЩАЕТ:
        - list[ValidationResult]: результаты для каждого элемента
        
        ПРИМЕР:
        ```python
        results = service.validate_batch(UserSchema, [data1, data2, data3])
        valid_items = [
            r.validated_data for r in results if r.is_valid
        ]
        ```
        """
        return [self.validate(schema, item) for item in items]

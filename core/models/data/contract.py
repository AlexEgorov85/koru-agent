"""
Типизированная модель контракта с встроенной Pydantic-схемой.
"""
from pydantic import BaseModel, Field, root_validator, ConfigDict
from typing import Dict, Optional, Type, Any
import json
from jsonschema import validate as jsonschema_validate, ValidationError as JsonSchemaError

from core.models.data.base_template_validator import TemplateValidatorMixin
from core.models.enums.common_enums import ComponentType, ContractDirection, PromptStatus


class Contract(TemplateValidatorMixin, BaseModel):
    """
    Типизированный объект контракта с ленивой компиляцией в Pydantic-схему.
    """
    model_config = ConfigDict(frozen=True)
    
    capability: str = Field(
        ...,
        description="Имя capability",
        min_length=3,
        pattern=r"^[a-z_]+(\.[a-z_]+)*$"  # Allow single names or compound names with dots (e.g., behavior or behavior.planning.decompose)
    )

    version: str = Field(
        ...,
        description="Семантическая версия",
        pattern=r"^v\d+\.\d+\.\d+$"
    )

    status: PromptStatus = Field(...)  # Используем тот же статус что и у промптов

    component_type: ComponentType = Field(...)

    direction: ContractDirection = Field(...)

    schema_data: Dict[str, Any] = Field(
        ...,
        description="JSON Schema в виде словаря (валидируется при создании)"
    )

    description: str = Field(
        default="",
        description="Человекочитаемое описание контракта"
    )

    # === КЭШИРОВАННАЯ Pydantic-схема (ленивая загрузка) ===
    _pydantic_schema: Optional[Type[BaseModel]] = None

    @root_validator(skip_on_failure=True)
    def validate_json_schema(cls, values):
        """Валидация структуры JSON Schema при создании объекта"""
        schema_data = values.get('schema_data', {})

        # Минимальная валидация: должен быть $schema или type
        if '$schema' not in schema_data and 'type' not in schema_data:
            raise ValueError("Невалидная JSON Schema: отсутствуют обязательные поля '$schema' или 'type'")

        # Опционально: полная валидация через jsonschema
        try:
            jsonschema_validate(instance=schema_data, schema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "required": ["type"]
            })
        except JsonSchemaError as e:
            raise ValueError(f"Невалидная JSON Schema: {e.message}")

        return values

    @property
    def pydantic_schema(self) -> Type[BaseModel]:
        """
        Ленивая компиляция JSON Schema → Pydantic модель.
        Кэшируется после первого вызова.
        """
        if self._pydantic_schema is None:
            self._pydantic_schema = self._compile_to_pydantic()
        return self._pydantic_schema

    def _compile_to_pydantic(self) -> Type[BaseModel]:
        """
        Компилирует JSON Schema в валидированную Pydantic-модель.
        Реализация через динамическое создание класса.
        """
        # Упрощённая реализация для примера
        # В продакшене использовать библиотеку:
        #   - https://github.com/pydantic/pydantic-jsonschema
        #   - или собственную компиляцию

        # Извлекаем поля из JSON Schema
        properties = self.schema_data.get('properties', {})
        required = self.schema_data.get('required', [])

        # Создаём аннотации типов
        annotations = {}
        field_definitions = {}

        for field_name, field_schema in properties.items():
            field_type = self._json_schema_type_to_python(field_schema.get('type', 'string'))
            annotations[field_name] = field_type

            field_kwargs = {'description': field_schema.get('description', '')}
            if field_name in required:
                field_kwargs['default'] = ...  # Обязательное поле
            else:
                field_kwargs['default'] = None  # Опциональное поле

            field_definitions[field_name] = (field_type, Field(**field_kwargs))

        # Создаём динамическую модель
        class_name = f"{self.capability.replace('.', '').title()}{self.direction.value.title()}Schema"

        return type(class_name, (BaseModel,), {
            '__annotations__': annotations,
            **{name: field for name, field in field_definitions.items()},
            'model_config': ConfigDict(extra='forbid')  # Запрет неизвестных полей
        })

    def _json_schema_type_to_python(self, json_type: str) -> type:
        """Преобразует тип из JSON Schema в Python тип"""
        type_map = {
            'string': str,
            'integer': int,
            'number': float,
            'boolean': bool,
            'array': list,
            'object': dict
        }
        return type_map.get(json_type, str)

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Валидация данных через скомпилированную схему"""
        try:
            self.pydantic_schema.model_validate(data)
            return True
        except Exception as e:
            raise ValueError(
                f"Данные не соответствуют контракту {self.capability}@{self.version} "
                f"({self.direction.value}): {e}"
            )

    def validate_templates(self) -> list[str]:
        """
        Валидация всех шаблонов в контракте.
        Сейчас контракты не содержат шаблонов, но метод предусмотрен для унификации.
        
        Returns:
            list: список предупреждений
        """
        # Контракты не содержат шаблонов, поэтому возвращаем пустой список
        return []
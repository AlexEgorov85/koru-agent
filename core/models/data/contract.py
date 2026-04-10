"""
Типизированная модель контракта с встроенной Pydantic-схемой.
"""
from pydantic import BaseModel, Field, model_validator, ConfigDict, field_validator
from typing import Dict, Optional, Type, Any, Literal, get_args
import json
from jsonschema import validate as jsonschema_validate, ValidationError as JsonSchemaError

from core.models.data.base_template_validator import TemplateValidatorMixin
from core.models.enums.common_enums import ComponentType, ContractDirection, PromptStatus


# Допустимые JSON Schema типы (без fallback!)
_VALID_JSON_SCHEMA_TYPES = frozenset({
    "string", "integer", "number", "boolean", "array", "object"
})

# Маппинг JSON Schema типов → Python типы
_JSON_TO_PYTHON_TYPE = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class Contract(TemplateValidatorMixin, BaseModel):
    """
    Типизированный объект контракта с ленивой компиляцией в Pydantic-схему.
    """
    model_config = ConfigDict(frozen=True)
    
    capability: str = Field(
        ...,
        description="Имя capability",
        min_length=3,
        pattern=r"^[a-z_]+(\.[a-z_]+)*$"
    )

    version: str = Field(
        ...,
        description="Семантическая версия",
        pattern=r"^v\d+\.\d+\.\d+$"
    )

    status: PromptStatus = Field(...)

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

    _pydantic_schema: Optional[Type[BaseModel]] = None

    @model_validator(mode="after")
    def validate_json_schema(self):
        """Валидация структуры JSON Schema при создании объекта"""
        if "$schema" not in self.schema_data and "type" not in self.schema_data:
            raise ValueError("Невалидная JSON Schema: отсутствуют обязательные поля")
        try:
            jsonschema_validate(instance=self.schema_data, schema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "required": ["type"]
            })
        except JsonSchemaError as e:
            raise ValueError(f"Невалидная JSON Schema: {e.message}")
        return self

    @property
    def pydantic_schema(self) -> Type[BaseModel]:
        if self._pydantic_schema is None:
            self._pydantic_schema = self._compile_to_pydantic()
        return self._pydantic_schema

    def _compile_to_pydantic(self) -> Type[BaseModel]:
        """
        Компиляция JSON Schema в Pydantic-модель.

        ПОДДЕРЖИВАЕТ:
        - Вложенные object → рекурсивные Pydantic-модели
        - array с items → list[ItemType] (с рекурсией)
        - enum → Literal[...]
        - minimum/maximum → Field(ge=..., le=...)
        - exclusiveMinimum/exclusiveMaximum → Field(gt=..., lt=...)
        - multipleOf → валидатор
        - nullable → Optional[...]
        - additionalProperties → extra="allow"/"forbid"
        - Строгая валидация типов (без fallback на str)
        """
        from typing import Optional, get_origin

        properties = self.schema_data.get("properties", {})
        required = self.schema_data.get("required", [])
        additional_properties = self.schema_data.get("additionalProperties", True)

        # Определяем политику extra по additionalProperties
        extra_policy = "allow" if additional_properties else "forbid"

        annotations: Dict[str, Any] = {}
        field_definitions: Dict[str, Any] = {}
        validators: Dict[str, Any] = {}

        for field_name, field_schema in properties.items():
            # Рекурсивная компиляция типа (поддержка вложенных object/array)
            field_type = self._compile_field_schema(field_name, field_schema)

            # Обработка nullable
            is_nullable = field_schema.get("nullable", False)
            if is_nullable:
                # Проверяем, не уже ли Optional
                if get_origin(field_type) is not Optional:
                    field_type = Optional[field_type]

            annotations[field_name] = field_type

            # Формируем Field() с ограничениями
            field_kwargs = self._build_field_kwargs(field_name, field_schema, required)
            field_definitions[field_name] = Field(**field_kwargs)

            # Добавляем валидатор для multipleOf
            if "multipleOf" in field_schema:
                validator_name = f"validate_multiple_of_{field_name}"
                multiple_of = field_schema["multipleOf"]
                validators[validator_name] = field_validator(field_name)(
                    self._make_multiple_of_validator(multiple_of)
                )

        class_name = f"{self.capability.replace('.', '').title()}{self.direction.value.title()}Schema"

        # Формируем тело класса
        class_body = {
            "__annotations__": annotations,
            **field_definitions,
            "model_config": ConfigDict(extra=extra_policy),
        }

        # Добавляем валидаторы если есть
        if validators:
            class_body.update(validators)

        return type(class_name, (BaseModel,), class_body)

    def _compile_field_schema(self, field_name: str, field_schema: Dict[str, Any]) -> Any:
        """
        Рекурсивная компиляция схемы поля в Python тип.

        ARGS:
        - field_name: Имя поля (для ошибок)
        - field_schema: JSON Schema фрагмент поля

        RETURNS:
        - Python тип (str, int, float, bool, list[X], dict, NestedModel, Literal[...])

        RAISES:
        - ValueError: если тип неизвестен или не указан
        """
        json_type = field_schema.get("type")

        # Строгая проверка типа
        if json_type is None:
            raise ValueError(
                f"Поле '{field_name}': отсутствует 'type' в JSON Schema. "
                f"Укажите один из: {', '.join(sorted(_VALID_JSON_SCHEMA_TYPES))}"
            )

        if json_type not in _VALID_JSON_SCHEMA_TYPES:
            raise ValueError(
                f"Поле '{field_name}': неизвестный тип '{json_type}'. "
                f"Допустимые: {', '.join(sorted(_VALID_JSON_SCHEMA_TYPES))}"
            )

        # enum → Literal
        enum_values = field_schema.get("enum")
        if enum_values:
            if not enum_values:
                raise ValueError(f"Поле '{field_name}': enum не может быть пустым")
            return Literal[tuple(enum_values)]

        # array → list[ItemType]
        if json_type == "array":
            items_schema = field_schema.get("items")
            if items_schema:
                item_type = self._compile_field_schema(f"{field_name}[]", items_schema)
                return list[item_type]
            return list

        # object → вложенная Pydantic-модель
        if json_type == "object":
            nested_properties = field_schema.get("properties")
            if nested_properties:
                return self._compile_nested_object(field_name, field_schema)
            return dict

        # Примитивы: string, integer, number, boolean
        return _JSON_TO_PYTHON_TYPE[json_type]

    def _compile_nested_object(
        self,
        parent_name: str,
        field_schema: Dict[str, Any]
    ) -> Type[BaseModel]:
        """
        Компиляция вложенного object в отдельную Pydantic-модель.

        ARGS:
        - parent_name: Имя родительского поля
        - field_schema: JSON Schema объекта (с properties, required и т.д.)

        RETURNS:
        - Класс унаследованный от BaseModel
        """
        nested_properties = field_schema.get("properties", {})
        nested_required = field_schema.get("required", [])
        nested_additional = field_schema.get("additionalProperties", True)
        nested_extra = "allow" if nested_additional else "forbid"

        annotations: Dict[str, Any] = {}
        field_defs: Dict[str, Any] = {}

        for prop_name, prop_schema in nested_properties.items():
            prop_type = self._compile_field_schema(
                f"{parent_name}.{prop_name}", prop_schema
            )

            # Nullable
            if prop_schema.get("nullable", False):
                prop_type = Optional[prop_type]

            annotations[prop_name] = prop_type
            field_defs[prop_name] = Field(
                **self._build_field_kwargs(prop_name, prop_schema, nested_required)
            )

        class_name = f"{parent_name.replace('.', '').title()}Nested"
        return type(class_name, (BaseModel,), {
            "__annotations__": annotations,
            **field_defs,
            "model_config": ConfigDict(extra=nested_extra),
        })

    def _build_field_kwargs(
        self,
        field_name: str,
        field_schema: Dict[str, Any],
        required: list
    ) -> Dict[str, Any]:
        """
        Формирование аргументов для Field() с учётом ограничений JSON Schema.

        ПОДДЕРЖИВАЕТ:
        - description
        - default (явный или из схемы)
        - required (default=...)
        - minimum/maximum → ge/le
        - exclusiveMinimum/exclusiveMaximum → gt/lt
        - min_length/max_length → для строк
        - pattern → regex для строк
        """
        kwargs: Dict[str, Any] = {
            "description": field_schema.get("description", "")
        }

        if field_name in required:
            kwargs["default"] = ...
        else:
            if "default" in field_schema:
                kwargs["default"] = field_schema["default"]
            else:
                kwargs["default"] = None

        # Числовые ограничения
        if "minimum" in field_schema:
            kwargs["ge"] = field_schema["minimum"]
        if "maximum" in field_schema:
            kwargs["le"] = field_schema["maximum"]
        if "exclusiveMinimum" in field_schema:
            kwargs["gt"] = field_schema["exclusiveMinimum"]
        if "exclusiveMaximum" in field_schema:
            kwargs["lt"] = field_schema["exclusiveMaximum"]

        # Строковые ограничения
        if "minLength" in field_schema:
            kwargs["min_length"] = field_schema["minLength"]
        if "maxLength" in field_schema:
            kwargs["max_length"] = field_schema["maxLength"]
        if "pattern" in field_schema:
            kwargs["pattern"] = field_schema["pattern"]

        return kwargs

    def _make_multiple_of_validator(self, multiple_of: float):
        """Создаёт валидатор для multipleOf."""
        def validate(value):
            if value % multiple_of != 0:
                raise ValueError(
                    f"Значение {value} не кратно {multiple_of}"
                )
            return value
        return staticmethod(validate)

    def validate_data(self, data: Dict[str, Any]) -> bool:
        try:
            self.pydantic_schema.model_validate(data)
            return True
        except Exception as e:
            raise ValueError(f"Данные не соответствуют контракту {self.capability}@{self.version}: {e}")

    def validate_templates(self) -> list[str]:
        return []

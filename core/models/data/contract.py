"""
Типизированная модель контракта с встроенной Pydantic-схемой.
"""
from pydantic import BaseModel, Field, model_validator, ConfigDict
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
        properties = self.schema_data.get("properties", {})
        required = self.schema_data.get("required", [])
        annotations = {}
        field_definitions = {}
        for field_name, field_schema in properties.items():
            field_type = self._json_schema_type_to_python(field_schema.get("type", "string"))
            annotations[field_name] = field_type
            field_kwargs = {"description": field_schema.get("description", "")}
            if field_name in required:
                field_kwargs["default"] = ...
            else:
                # Проверяем есть ли default в схеме
                if "default" in field_schema:
                    field_kwargs["default"] = field_schema["default"]
                else:
                    field_kwargs["default"] = None
            # Pydantic v2 синтаксис: просто Field(), аннотации отдельно
            field_definitions[field_name] = Field(**field_kwargs)
        class_name = f"{self.capability.replace('.', '').title()}{self.direction.value.title()}Schema"
        return type(class_name, (BaseModel,), {
            "__annotations__": annotations,
            **field_definitions,
            "model_config": ConfigDict(extra="forbid")
        })

    def _json_schema_type_to_python(self, json_type: str) -> type:
        type_map = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}
        return type_map.get(json_type, str)

    def validate_data(self, data: Dict[str, Any]) -> bool:
        try:
            self.pydantic_schema.model_validate(data)
            return True
        except Exception as e:
            raise ValueError(f"Данные не соответствуют контракту {self.capability}@{self.version}: {e}")

    def validate_templates(self) -> list[str]:
        return []

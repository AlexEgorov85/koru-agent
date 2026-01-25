"""
Structured Actions

Назначение:
- ввести строгую схему action payload
- валидировать действия агента ДО execution
- классифицировать ошибки как INVALID_INPUT

Этот слой:
AgentRuntime -> ActionBuilder -> SchemaValidator -> ExecutionGateway
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type
from abc import ABC, abstractmethod

from core.retry_policy.retry_and_error_policy import ExecutionErrorInfo, ErrorCategory


# ==========================================================
# Action schema base
# ==========================================================
class ActionSchema(ABC):
    """
    Базовый контракт для structured action.
    Каждая capability должна иметь схему.
    """

    @classmethod
    @abstractmethod
    def validate(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидирует и нормализует payload.
        Должен:
        - выбросить ValueError при ошибке
        - вернуть нормализованный payload
        """
        raise NotImplementedError


# ==========================================================
# Example schemas
# ==========================================================
class TextInputSchema(ActionSchema):
    @classmethod
    def validate(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if "input" not in payload:
            raise ValueError("Missing 'input' field")
        if not isinstance(payload["input"], str):
            raise ValueError("'input' must be string")
        return {"input": payload["input"].strip()}


class KeyValueSchema(ActionSchema):
    @classmethod
    def validate(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Payload must be object")
        return payload


# ==========================================================
# Action schema registry
# ==========================================================
class ActionSchemaRegistry:
    def __init__(self):
        self._schemas: Dict[str, Type[ActionSchema]] = {}

    def register(self, capability_name: str, schema: Type[ActionSchema]):
        self._schemas[capability_name] = schema

    def get(self, capability_name: str) -> Optional[Type[ActionSchema]]:
        return self._schemas.get(capability_name)


# ==========================================================
# Validator
# ==========================================================
class ActionValidator:
    def __init__(self, registry: ActionSchemaRegistry):
        self.registry = registry

    def validate(
        self,
        *,
        capability_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        schema = self.registry.get(capability_name)
        if not schema:
            # no schema == raw passthrough (allowed but discouraged)
            return payload

        try:
            return schema.validate(payload)
        except Exception as e:
            raise StructuredActionError(str(e))


# ==========================================================
# Errors
# ==========================================================
class StructuredActionError(Exception):
    def to_execution_error(self) -> ExecutionErrorInfo:
        return ExecutionErrorInfo(
            category=ErrorCategory.INVALID_INPUT,
            message=str(self),
            raw_error=self,
        )

"""Модели для представления сигнатур кода.

Этот модуль содержит модели для работы с сигнатурками кода:
- CodeSignature - представление сигнатуры элемента кода
- ParameterInfo - информация о параметре функции/метода

Модели разработаны для:
1. Представления сигнатур в унифицированном формате
2. Поддержки метаданных параметров
3. Эффективного анализа и сопоставления сигнатур
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


class ParameterKind(str, Enum):
    """Типы параметров функций/методов."""
    
    POSITIONAL_ONLY = "positional_only"      # /
    POSITIONAL_OR_KEYWORD = "positional_or_keyword"  # обычный параметр
    VAR_POSITIONAL = "var_positional"       # *args
    KEYWORD_ONLY = "keyword_only"           # после *
    VAR_KEYWORD = "var_keyword"             # **kwargs


class ParameterInfo(BaseModel):
    """Информация о параметре функции/метода.
    
    Атрибуты:
    - name: имя параметра
    - type_annotation: аннотация типа параметра
    - default_value: значение по умолчанию
    - kind: тип параметра (из ParameterKind)
    - is_optional: является ли параметр опциональным
    
    Пример:
    ```python
    param = ParameterInfo(
        name="count",
        type_annotation="int",
        default_value=1,
        kind=ParameterKind.POSITIONAL_OR_KEYWORD,
        is_optional=True
    )
    ```
    """
    
    name: str = Field(..., description="Имя параметра")
    type_annotation: Optional[str] = Field(None, description="Аннотация типа параметра")
    default_value: Optional[Any] = Field(None, description="Значение по умолчанию")
    kind: ParameterKind = Field(ParameterKind.POSITIONAL_OR_KEYWORD, description="Тип параметра (из ParameterKind)")
    is_optional: bool = Field(False, description="Является ли параметр опциональным")
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        return {
            'name': self.name,
            'type_annotation': self.type_annotation,
            'default_value': self.default_value,
            'kind': self.kind.value,
            'is_optional': self.is_optional
        }


class CodeSignature(BaseModel):
    """Представление сигнатуры элемента кода.
    
    Атрибуты:
    - name: имя элемента
    - parameters: список параметров
    - return_type: тип возвращаемого значения
    - decorators: список декораторов
    - visibility: уровень видимости (public, private, protected)
    - is_async: является ли асинхронным
    - is_static: является ли статическим (для методов)
    - is_class_method: является ли методом класса (для методов)
    
    Пример:
    ```python
    signature = CodeSignature(
        name="process_data",
        parameters=[
            ParameterInfo(name="input_data", type_annotation="str", is_optional=False),
            ParameterInfo(name="options", type_annotation="dict", default_value={}, is_optional=True)
        ],
        return_type="ProcessResult",
        decorators=["staticmethod"],
        is_async=True
    )
    ```
    """
    
    name: str = Field(..., description="Имя элемента")
    parameters: List[ParameterInfo] = Field(default_factory=list, description="Список параметров")
    return_type: Optional[str] = Field(None, description="Тип возвращаемого значения")
    decorators: List[str] = Field(default_factory=list, description="Список декораторов")
    visibility: str = Field("public", description="Уровень видимости (public, private, protected)")  # public, private, protected
    is_async: bool = Field(False, description="Является ли асинхронным")
    is_static: bool = Field(False, description="Является ли статическим (для методов)")
    is_class_method: bool = Field(False, description="Является ли методом класса (для методов)")
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        return {
            'name': self.name,
            'parameters': [param.to_dict() for param in self.parameters],
            'return_type': self.return_type,
            'decorators': self.decorators,
            'visibility': self.visibility,
            'is_async': self.is_async,
            'is_static': self.is_static,
            'is_class_method': self.is_class_method
        }
    
    def get_full_signature(self) -> str:
        """Получение полной строки сигнатуры."""
        params_str = ", ".join([
            f"{param.name}: {param.type_annotation}" if param.type_annotation else param.name
            for param in self.parameters
        ])
        
        prefix = ""
        if self.is_async:
            prefix += "async "
        if self.is_static:
            prefix += "static "
        if self.is_class_method:
            prefix += "classmethod "
        
        return_type_str = f" -> {self.return_type}" if self.return_type else ""
        
        return f"{prefix}{self.name}({params_str}){return_type_str}"

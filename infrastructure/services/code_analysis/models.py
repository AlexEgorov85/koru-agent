"""
Pydantic-модели для представления данных статического анализа кода.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SymbolType(str, Enum):
    """
    Типы символов в коде.
    """
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    VARIABLE = "variable"
    CONSTANT = "constant"
    PARAMETER = "parameter"
    ATTRIBUTE = "attribute"
    IMPORT = "import"
    IMPORT_FROM = "import_from"
    MODULE = "module"


class Location(BaseModel):
    """
    Информация о местоположении элемента кода в файле.
    """
    file_path: str = Field(..., description="Путь к файлу")
    start_line: int = Field(..., description="Начальная строка (1-based)")
    end_line: int = Field(..., description="Конечная строка (1-based)")
    start_column: int = Field(..., description="Начальная колонка (1-based)")
    end_column: int = Field(..., description="Конечная колонка (1-based)")


class Dependency(BaseModel):
    """
    Модель для представления зависимости (импорта).
    """
    type: SymbolType = Field(..., description="Тип символа")
    name: str = Field(..., description="Имя зависимости")
    alias: Optional[str] = Field(None, description="Псевдоним импорта")
    module: Optional[str] = Field(None, description="Имя модуля (для from ... import ...)")
    is_relative: bool = Field(False, description="Относительный импорт")
    level: int = Field(0, description="Уровень вложенности для относительных импортов")


class CodeUnit(BaseModel):
    """
    Модель для представления единицы кода (функция, класс, переменная и т.д.).
    """
    type: SymbolType = Field(..., description="Тип символа")
    name: str = Field(..., description="Имя символа")
    location: Location = Field(..., description="Местоположение символа")
    signature: Optional[str] = Field(None, description="Сигнатура символа")
    docstring: Optional[str] = Field(None, description="Документация символа")
    parameters: List[str] = Field(default_factory=list, description="Параметры (для функций/методов)")
    bases: List[str] = Field(default_factory=list, description="Базовые классы (для классов)")
    decorators: List[str] = Field(default_factory=list, description="Декораторы")
    children: List['CodeUnit'] = Field(default_factory=list, description="Дочерние элементы")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные")

    class Config:
        # Позволяет рекурсивные модели
        arbitrary_types_allowed = True
        # Позволяет установить пользовательские типы
        json_encoders = {Enum: lambda v: v.value}


# Обновляем модель CodeUnit, чтобы корректно обработать рекурсивную ссылку
CodeUnit.update_forward_refs()
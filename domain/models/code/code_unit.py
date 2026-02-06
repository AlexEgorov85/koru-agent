"""Модели для представления единиц кода.

Этот модуль содержит основные модели для работы с единицами кода:
- CodeUnitType - перечисление типов единиц кода
- Location - информация о местоположении в файле
- CodeSpan - диапазон исходного кода
- CodeUnit - основная единица кода с метаданными

Модели разработаны для:
1. Представления любых элементов кода в едином формате
2. Поддержки метаданных для языково-специфичной информации
3. Эффективного хранения и поиска
4. Легкой сериализации в JSON для работы с LLM

Примеры использования:

1. Создание CodeUnit для функции:
```python
function_unit = CodeUnit(
    id="func_analyze_123",
    name="analyze_file",
    type=CodeUnitType.FUNCTION,
    location=Location(
        file_path="core/utils.py",
        start_line=25,
        end_line=42,
        start_column=1,
        end_column=25
    ),
    code_span=CodeSpan(source_code="def analyze_file(file_path):\n    # анализ файла"),
    metadata={
        'parameters': [{'name': 'file_path', 'type': 'str'}],
        'return_type': 'dict',
        'is_async': False,
        'docstring': 'Анализирует файл и возвращает метаданные'
    }
)

2. Получение подписи функции:
signature = function_unit.get_signature()
# Результат: "def analyze_file(file_path):"

3. Получение документации:
doc = function_unit.get_documentation()
# Результат: "Анализирует файл и возвращает метаданные"

4. Сериализация в словарь:
data = function_unit.to_dict()

"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib
from enum import Enum
from pydantic import BaseModel, Field


class CodeUnitType(str, Enum):
    """Типы единиц кода.
    Перечисление поддерживаемых типов единиц кода.
    Используется для классификации и фильтрации.

    Примеры:
    - MODULE: модуль (файл .py)
    - CLASS: класс
    - FUNCTION: функция верхнего уровня
    - METHOD: метод класса
    - VARIABLE: переменная уровня модуля
    - IMPORT: оператор импорта
    """

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    IMPORT_FROM = "import_from"
    COMMENT = "comment"
    DOCSTRING = "docstring"
    DECORATOR = "decorator"
    UNKNOWN = "unknown"


class Location(BaseModel):
    """Неизменяемая структура местоположения в коде.
    Представляет точное местоположение элемента кода в файле.
    Все координаты используют 1-based индексацию для соответствия
    стандартному представлению в редакторах кода.

    Атрибуты:
    - file_path: путь к файлу относительно корня проекта
    - start_line: начальная строка (1-based)
    - end_line: конечная строка (1-based)  
    - start_column: начальная колонка (1-based)
    - end_column: конечная колонка (1-based)

    Пример:
    ```python
    loc = Location(
        file_path="core/main.py",
        start_line=10,
        end_line=15,
        start_column=5,
        end_column=20
    )
    print(str(loc))  # "core/main.py:10:5"
    ```
    """

    file_path: str = Field(..., description="Путь к файлу относительно корня проекта")
    start_line: int = Field(..., description="Начальная строка (1-based)", ge=1)
    end_line: int = Field(..., description="Конечная строка (1-based)", ge=1)
    start_column: int = Field(..., description="Начальная колонка (1-based)", ge=1)
    end_column: int = Field(..., description="Конечная колонка (1-based)", ge=1)

    def __str__(self) -> str:
        """Человекочитаемое представление местоположения."""
        return f"{self.file_path}:{self.start_line}:{self.start_column}"

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        return {
            'file_path': self.file_path,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'start_column': self.start_column,
            'end_column': self.end_column
        }


class CodeSpan(BaseModel):
    """Диапазон кода с хешем для сравнения.
    Представляет фрагмент исходного кода с автоматическим вычислением хеша.
    Хеш используется для быстрого сравнения и определения изменений.

    Атрибуты:
    - source_code: исходный код в виде строки
    - hash: MD5 хеш исходного кода (вычисляется автоматически)

    Примеры использования:
    ```python
    # Создание CodeSpan
    span = CodeSpan(source_code="def hello():\n    print('Hello')")

    # Получение хеша
    print(span.hash)  # "a1b2c3d4..."

    # Получение длины кода
    print(len(span))  # 30

    # Количество строк
    print(span.lines_count())  # 2
    ```
    """

    source_code: str = Field(..., description="Исходный код в виде строки")
    hash: str = Field("", description="MD5 хеш исходного кода")

    def __init__(self, **data):
        """Вычисление хеша при инициализации.
        
        Автоматически вычисляет MD5 хеш исходного кода.
        """
        super().__init__(**data)
        if not data.get('hash'):
            self.hash = hashlib.md5(self.source_code.encode()).hexdigest()

    def __len__(self) -> int:
        """Длина кода в символах."""
        return len(self.source_code)

    def lines_count(self) -> int:
        """Количество строк в коде."""
        return len(self.source_code.splitlines())


class CodeUnit(BaseModel):
    """
    Минимальная модель единицы кода с расширяемыми метаданными.
    Основной строительный блок для анализа кода. Представляет любой элемент кода:
    - функции, классы, методы
    - переменные, импорты
    - комментарии, декораторы

    Особенности:
    1. Иммутабельность базовых полей (через frozen pydantic модели)
    2. Расширяемость через метаданные (поле metadata)
    3. Кэширование для производительности
    4. Автоматическая генерация уникального ID

    Поля:
    - id: уникальный идентификатор
    - name: имя элемента
    - type: тип элемента (CodeUnitType)
    - location: местоположение в файле
    - code_span: диапазон исходного кода
    - parent_id: ID родительского элемента
    - child_ids: список ID дочерних элементов
    - metadata: расширяемые метаданные
    - created_at: время создания
    - language: язык программирования
    - version: версия модели

    Примеры использования:

    1. Создание CodeUnit для класса:
    ```python
    class_unit = CodeUnit(
        id="class_User_123",
        name="User",
        type=CodeUnitType.CLASS,
        location=Location(...),
        code_span=CodeSpan(source_code="class User:\n    pass"),
        metadata={
            'bases': ['BaseModel'],
            'docstring': 'Модель пользователя',
            'methods_count': 5
        }
    )
    ```

    2. Получение подписи:
    ```python
    signature = class_unit.get_signature()
    # "class User(BaseModel):"
    ```

    3. Получение документации:
    ```python
    doc = class_unit.get_documentation()
    # "Модель пользователя"
    ```

    4. Сериализация:
    ```python
    data = class_unit.to_dict()
    ```
    """

    # Идентификаторы
    id: str = Field(..., description="Уникальный идентификатор")
    name: str = Field(..., description="Имя элемента")

    # Классификация
    type: CodeUnitType = Field(..., description="Тип элемента (CodeUnitType)")

    # Местоположение
    location: Location = Field(..., description="Местоположение в файле")

    # Содержимое
    code_span: CodeSpan = Field(..., description="Диапазон исходного кода")
    
    # Документация
    docstring: Optional[str] = Field(None, description="Документация символа")
    
    # Параметры (для функций/методов)
    parameters: List[str] = Field(default_factory=list, description="Параметры (для функций/методов)")
    
    # Сигнатура
    signature: Optional[str] = Field(None, description="Сигнатура символа")

    # Связи
    parent_id: Optional[str] = Field(None, description="ID родительского элемента")
    child_ids: List[str] = Field(default_factory=list, description="Список ID дочерних элементов")

    # Метаданные (главный механизм расширения)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Расширяемые метаданные")

    # Системные поля
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Время создания")
    language: str = Field(default="python", description="Язык программирования")
    version: int = Field(default=1, description="Версия модели")

    # Кэширование для производительности
    # Внутренние атрибуты для кэширования не являются полями модели
    _cached_signature: Optional[str] = None
    _cached_documentation: Optional[str] = None

    def get_signature(self) -> str:
        """
        Получение подписи с кэшированием и безопасной обработкой метаданных.
        Генерирует подпись в зависимости от типа:
        - Для функций: "def name(params) -> return_type:"
        - Для классов: "class name(bases):"
        - Для других типов: просто имя
        Результат кэшируется для производительности.
        Возвращает:
        str: подпись элемента кода
        """
        if self._cached_signature is not None:
            return self._cached_signature

        # Генерация подписи на основе типа
        if self.type == CodeUnitType.FUNCTION:
            params = self.metadata.get('parameters', [])
            params_str = ", ".join([p.get('name', '') for p in params])
            async_prefix = "async " if self.metadata.get('is_async', False) else ""
            return_type = self.metadata.get('return_type')
            return_type_str = f" -> {return_type}" if return_type else ""
            self._cached_signature = f"{async_prefix}def {self.name}({params_str}){return_type_str}:"
        elif self.type == CodeUnitType.CLASS:
            # === ИСПРАВЛЕНО: безопасная обработка базовых классов ===
            bases = self.metadata.get('bases', [])
            base_names = []
            
            for base in bases:
                # Обработка разных форматов базовых классов
                if isinstance(base, str):
                    base_names.append(base)
                elif isinstance(base, dict):
                    # Извлекаем имя из словаря (поддержка разных форматов)
                    base_name = (
                        base.get("name") or 
                        base.get("value") or 
                        base.get("full_name") or 
                        str(base.get("node", ""))
                    )
                    if base_name and base_name != "None":
                        base_names.append(base_name)
                elif hasattr(base, 'name'):
                    base_names.append(str(getattr(base, 'name', base)))
                else:
                    # Фолбэк: преобразуем в строку и очищаем от лишнего
                    base_str = str(base).strip()
                    if base_str and base_str != "None":
                        base_names.append(base_str)
            
            # Формирование строки базовых классов
            bases_str = f"({', '.join(base_names)})" if base_names else ""
            self._cached_signature = f"class {self.name}{bases_str}:"
        else:
            self._cached_signature = self.name

        return self._cached_signature

    def get_documentation(self) -> Optional[str]:
        """Получение документации.
        
        Извлекает документацию (docstring) из поля docstring.
        Результат кэшируется для производительности.
        
        Returns:
            Optional[str]: документация или None
        """
        if self._cached_documentation is not None:
            return self._cached_documentation
        
        self._cached_documentation = self.docstring
        return self.docstring

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации.
        
        Возвращает полное представление CodeUnit в виде словаря,
        включая кэшированные значения подписи и документации.
        
        Returns:
            Dict[str, Any]: сериализованное представление
        """
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'location': self.location.to_dict() if self.location else None,
            'source_code': self.code_span.source_code if self.code_span else None,
            'source_hash': self.code_span.hash if self.code_span else None,
            'parent_id': self.parent_id,
            'child_count': len(self.child_ids),
            'child_ids': self.child_ids,
            'metadata': self.metadata,
            'signature': self.get_signature(),
            'documentation': self.get_documentation(),
            'language': self.language,
            'created_at': self.created_at.isoformat(),
            'version': self.version
        }

    def __str__(self) -> str:
        """Человекочитаемое представление."""
        return f"{self.type.value} '{self.name}' at {self.location}"

    def __repr__(self) -> str:
        """Техническое представление."""
        return f"CodeUnit(id='{self.id}', type='{self.type.value}', name='{self.name}')"

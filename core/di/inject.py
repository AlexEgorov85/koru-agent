"""
Декораторы и утилиты для автоматического внедрения зависимостей.
"""

from typing import Type, Any, Callable, get_type_hints, get_origin, get_args, Optional, Dict, List
from functools import wraps
from inspect import signature, Parameter


def inject(func: Callable) -> Callable:
    """
    Декоратор для автоматического внедрения зависимостей.
    
    Автоматически разрешает зависимости из контейнера на основе аннотаций типов.
    
    USAGE:
    ```python
    @inject
    def create_skill(
        container: DependencyContainer,
        db: DatabaseInterface,
        llm: LLMInterface
    ):
        return MySkill(db=db, llm=llm)
    
    # Использование
    skill = create_skill(container)
    ```
    
    ARGS:
    - func: Функция с аннотированными параметрами
    
    RETURNS:
    - Обёрнутая функция с автоматическим DI
    """
    @wraps(func)
    def wrapper(container: 'DependencyContainer', *args, **kwargs):
        from core.di.container import DependencyContainer
        
        if not isinstance(container, DependencyContainer):
            raise TypeError(
                f"First argument must be DependencyContainer, got {type(container)}"
            )
        
        # Получаем аннотации типов
        try:
            hints = get_type_hints(func)
        except Exception:
            # Если не удалось получить аннотации, вызываем как есть
            return func(container, *args, **kwargs)
        
        # Получаем сигнатуру функции
        sig = signature(func)
        params = sig.parameters
        
        # Заполняем недостающие параметры из контейнера
        for param_name, param in params.items():
            # Пропускаем уже переданные аргументы
            if param_name in kwargs:
                continue
            
            # Пропускаем позиционные аргументы
            if len(args) > list(params.keys()).index(param_name):
                continue
            
            # Пропускаем container
            if param_name == 'container':
                continue
            
            # Получаем тип параметра
            param_type = hints.get(param_name)
            if param_type is None:
                continue
            
            # Проверяем, это ли Protocol (интерфейс)
            if _is_protocol_or_interface(param_type):
                try:
                    kwargs[param_name] = container.resolve(param_type)
                except ValueError as e:
                    # Если не найдено, используем значение по умолчанию
                    if param.default is not Parameter.empty:
                        kwargs[param_name] = param.default
            
            # Проверяем, это ли Optional[Protocol]
            elif _is_optional_protocol(param_type):
                inner_type = _get_optional_inner_type(param_type)
                try:
                    kwargs[param_name] = container.resolve(inner_type)
                except ValueError:
                    kwargs[param_name] = None
        
        return func(container, *args, **kwargs)
    
    return wrapper


def _is_protocol_or_interface(type_hint: Type) -> bool:
    """
    Проверить, является ли тип Protocol (интерфейсом).
    
    ARGS:
    - type_hint: Тип для проверки
    
    RETURNS:
    - True если это Protocol или интерфейс
    """
    # Проверяем на Protocol
    if hasattr(type_hint, '__protocol_attrs__'):
        return True
    
    # Проверяем на наличие _is_protocol (для старых версий typing)
    if getattr(type_hint, '_is_protocol', False):
        return True
    
    # Проверяем по имени модуля (наши интерфейсы в core.interfaces)
    if hasattr(type_hint, '__module__'):
        module_name = type_hint.__module__
        if module_name and module_name.startswith('core.interfaces'):
            return True
    
    return False


def _is_optional_protocol(type_hint: Type) -> bool:
    """
    Проверить, является ли тип Optional[Protocol].
    
    ARGS:
    - type_hint: Тип для проверки
    
    RETURNS:
    - True если это Optional[Protocol]
    """
    origin = get_origin(type_hint)
    
    # Проверяем на Union
    if origin is not None:
        # Для Python 3.10+ с использованием |
        if origin is Union:
            args = get_args(type_hint)
            # Optional[X] = Union[X, None]
            if len(args) == 2 and type(None) in args:
                inner_type = args[0] if args[1] is type(None) else args[1]
                return _is_protocol_or_interface(inner_type)
    
    return False


def _get_optional_inner_type(type_hint: Type) -> Optional[Type]:
    """
    Получить внутренний тип из Optional[Type].
    
    ARGS:
    - type_hint: Optional[Type]
    
    RETURNS:
    - Внутренний тип или None
    """
    origin = get_origin(type_hint)
    if origin is not None:
        args = get_args(type_hint)
        if len(args) == 2 and type(None) in args:
            return args[0] if args[1] is type(None) else args[1]
    return None


# Импортируем Union для проверки
try:
    from typing import Union
except ImportError:
    Union = None


class Injectable:
    """
    Дескриптор класса для автоматического внедрения зависимостей.
    
    USAGE:
    ```python
    class MySkill:
        db: DatabaseInterface = inject_field()
        llm: LLMInterface = inject_field()
        
        def __init__(self, container: DependencyContainer):
            container.inject_into(self)
    ```
    """
    
    def __init__(self, interface: Optional[Type] = None):
        self.interface = interface
        self._cache_name = None
    
    def __set_name__(self, owner: Type, name: str):
        """Вызывается при создании класса."""
        self._cache_name = f"_injected_{name}"
        
        # Если интерфейс не указан, пытаемся определить из аннотации
        if self.interface is None:
            annotations = getattr(owner, '__annotations__', {})
            self.interface = annotations.get(name)
    
    def __get__(self, obj: Any, objtype: Optional[Type] = None) -> Any:
        """Получить значение поля."""
        if obj is None:
            return self
        
        if not hasattr(obj, self._cache_name):
            raise AttributeError(
                f"Field '{self._cache_name[9:]}' not injected. "
                f"Call container.inject_into(instance) first."
            )
        
        return getattr(obj, self._cache_name)
    
    def __set__(self, obj: Any, value: Any):
        """Установить значение поля."""
        setattr(obj, self._cache_name, value)


def inject_field(interface: Optional[Type] = None) -> Injectable:
    """
    Создать дескриптор для внедрения поля.
    
    USAGE:
    ```python
    class MySkill:
        db: DatabaseInterface = inject_field()
        llm: LLMInterface = inject_field()
    ```
    
    ARGS:
    - interface: Тип интерфейса (опционально, определяется из аннотации)
    
    RETURNS:
    - Injectable дескриптор
    """
    return Injectable(interface)


def resolve_dependencies(
    container: 'DependencyContainer',
    instance: Any,
    ignore_errors: bool = False
) -> None:
    """
    Автоматически внедрить зависимости в экземпляр класса.
    
    Сканирует аннотации полей и внедряет зависимости из контейнера.
    
    USAGE:
    ```python
    skill = MySkill(...)
    resolve_dependencies(container, skill)
    ```
    
    ARGS:
    - container: DI контейнер
    - instance: Экземпляр для внедрения
    - ignore_errors: Игнорировать ошибки разрешения
    """
    if not hasattr(instance, '__annotations__'):
        return
    
    annotations = instance.__annotations__
    
    for field_name, field_type in annotations.items():
        # Пропускаем приватные поля
        if field_name.startswith('_'):
            continue
        
        # Проверяем, это ли интерфейс
        if _is_protocol_or_interface(field_type):
            try:
                value = container.resolve(field_type)
                setattr(instance, field_name, value)
            except ValueError as e:
                if not ignore_errors:
                    raise ValueError(
                        f"Cannot resolve dependency '{field_name}' of type {field_type.__name__}: {e}"
                    )
        
        # Проверяем Optional[Interface]
        elif _is_optional_protocol(field_type):
            inner_type = _get_optional_inner_type(field_type)
            try:
                value = container.resolve(inner_type)
                setattr(instance, field_name, value)
            except ValueError:
                setattr(instance, field_name, None)

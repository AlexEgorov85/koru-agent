"""Утилиты для обработки параметров в handler'ах."""
from typing import Any, Dict


def params_to_dict(params: Any) -> Dict[str, Any]:
    """
    Преобразует параметры в dict — работает и с Pydantic моделью, и с dict.

    ARGS:
    - params: Pydantic модель или dict

    RETURNS:
    - Dict[str, Any]: параметры как словарь
    """
    if hasattr(params, 'model_dump'):
        return params.model_dump()
    elif hasattr(params, 'dict'):
        return params.dict()
    elif isinstance(params, dict):
        return params
    return {}


def get_param(params: Any, name: str, default: Any = None) -> Any:
    """
    Безопасно получает параметр из dict или Pydantic модели.

    ARGS:
    - params: Pydantic модель или dict
    - name: имя параметра
    - default: значение по умолчанию

    RETURNS:
    - Any: значение параметра или default
    """
    if hasattr(params, 'model_dump') or hasattr(params, 'dict'):
        return getattr(params, name, default)
    elif isinstance(params, dict):
        return params.get(name, default)
    return default

"""
Интерфейсы (абстракции) для архитектуры с внедрением зависимостей.

ИНТЕРФЕЙСЫ = Абстракции, которые определяют ЧТО компонент умеет делать.
ПРОВАЙДЕРЫ = Конкретные реализации интерфейсов.

ИСПОЛЬЗОВАНИЕ:
```python
from core.interfaces import DatabaseInterface, LLMInterface

class MySkill:
    def __init__(
        self,
        db: DatabaseInterface,  # ← Зависимость от абстракции
        llm: LLMInterface,
    ):
        self._db = db
        self._llm = llm
```
"""

from core.interfaces.database import DatabaseInterface
from core.interfaces.llm import LLMInterface
from core.interfaces.vector import VectorInterface
from core.interfaces.cache import CacheInterface
from core.interfaces.prompt_storage import PromptStorageInterface
from core.interfaces.contract_storage import ContractStorageInterface
from core.interfaces.metrics_storage import MetricsStorageInterface
from core.interfaces.log_storage import LogStorageInterface
from core.interfaces.event_bus import EventBusInterface

__all__ = [
    "DatabaseInterface",
    "LLMInterface",
    "VectorInterface",
    "CacheInterface",
    "PromptStorageInterface",
    "ContractStorageInterface",
    "MetricsStorageInterface",
    "LogStorageInterface",
    "EventBusInterface",
]

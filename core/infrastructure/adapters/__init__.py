"""
Адаптеры для архитектуры Ports & Adapters.

АДАПТЕРЫ = Конкретные реализации портов для различных технологий.

ИМПОРТЫ:
```python
from core.infrastructure.adapters import (
    PostgreSQLAdapter,
    LlamaCppAdapter,
    FAISSAdapter,
    MemoryCacheAdapter,
)
```
"""

# Database adapters
from core.infrastructure.adapters.database import (
    PostgreSQLAdapter,
    SQLiteAdapter,
)

# LLM adapters
from core.infrastructure.adapters.llm import (
    LlamaCppAdapter,
    MockLLMAdapter,
)

# Vector adapters
from core.infrastructure.adapters.vector import (
    FAISSAdapter,
    MockVectorAdapter,
)

# Cache adapters
from core.infrastructure.adapters.cache import (
    MemoryCacheAdapter,
    RedisCacheAdapter,
)

__all__ = [
    # Database
    "PostgreSQLAdapter",
    "SQLiteAdapter",
    
    # LLM
    "LlamaCppAdapter",
    "MockLLMAdapter",
    
    # Vector
    "FAISSAdapter",
    "MockVectorAdapter",
    
    # Cache
    "MemoryCacheAdapter",
    "RedisCacheAdapter",
]

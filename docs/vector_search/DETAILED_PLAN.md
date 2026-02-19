# 📋 Детальный план разработки Vector Search

**Версия:** 1.0.0  
**Дата:** 2026-02-19  
**Статус:** ⏳ На согласовании

---

## 📊 Обзор этапов

| Этап | Название | Длительность | Статус | Зависимости |
|------|----------|--------------|--------|-------------|
| **ЭТАП 0** | Подготовка | 2-4 часа | ✅ Завершён | - |
| **ЭТАП 1** | Модели данных | 4-6 часов | ⏳Pending | ЭТАП 0 |
| **ЭТАП 2** | Тесты (TDD) | 6-8 часов | ⏳ Pending | ЭТАП 1 |
| **ЭТАП 3** | Реализация | 12-16 часов | ⏳ Pending | ЭТАП 2 |
| **ЭТАП 4** | Верификация | 4-6 часов | ⏳ Pending | ЭТАП 3 |
| **ЭТАП 5** | Документация | 2-4 часа | ⏳ Pending | ЭТАП 4 |

**Общая длительность:** 30-44 часа

---

# ЭТАП 1: Модели данных (4-6 часов)

## Цель
Создать все модели данных, контракты и конфигурацию для векторного поиска.

---

## 1.1 Модели данных (Core)

### Задачи:
- [ ] Создать `VectorSearchResult` — результат поиска
- [ ] Создать `VectorQuery` — запрос на поиск
- [ ] Создать `VectorDocument` — документ для индексации
- [ ] Создать `VectorChunk` — чанк документа
- [ ] Создать `VectorIndexInfo` — информация об индексе
- [ ] Создать `VectorSearchStats` — статистика поиска

### Файлы:
```
core/models/types/vector_types.py
```

### Структура файла:
```python
# core/models/types/vector_types.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class VectorSearchResult(BaseModel):
    """Результат векторного поиска."""
    id: str
    score: float
    content: str
    metadata: Dict[str, Any]
    chunk_id: Optional[str] = None
    document_id: str


class VectorQuery(BaseModel):
    """Запрос на векторный поиск."""
    query: Optional[str] = None
    vector: Optional[List[float]] = None
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None
    offset: int = Field(default=0, ge=0)


class VectorDocument(BaseModel):
    """Документ для индексации."""
    id: Optional[str] = None
    content: str
    metadata: Dict[str, Any]
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)


class VectorChunk(BaseModel):
    """Чанк документа."""
    id: str
    document_id: str
    content: str
    vector: Optional[List[float]] = None
    metadata: Dict[str, Any]
    index: int


class VectorIndexInfo(BaseModel):
    """Информация об индексе."""
    total_documents: int
    total_chunks: int
    index_size_mb: float
    dimension: int
    index_type: str
    created_at: datetime
    updated_at: datetime


class VectorSearchStats(BaseModel):
    """Статистика поиска."""
    query_time_ms: float
    total_found: int
    returned_count: int
    filters_applied: List[str]
```

### Тесты:
```
tests/unit/models/test_vector_types.py
```

### Критерии завершения:
- [ ] Все модели валидируются Pydantic
- [ ] Покрытие тестами ≥ 90%
- [ ] Документация моделей (docstrings)

---

## 1.2 Конфигурационные модели

### Задачи:
- [ ] Создать `VectorProviderConfig` — конфиг провайдера
- [ ] Создать `FAISSConfig` — конфиг FAISS
- [ ] Создать `EmbeddingConfig` — конфиг эмбеддингов
- [ ] Создать `ChunkingConfig` — конфиг chunking
- [ ] Создать `VectorSearchConfig` — общий конфиг
- [ ] Обновить `SystemConfig` для поддержки vector_search

### Файлы:
```
core/config/vector_config.py      ← Новые модели
core/config/models.py             ← Обновление SystemConfig
```

### Структура файла:
```python
# core/config/vector_config.py

from pydantic import BaseModel, Field
from typing import Optional, Literal


class FAISSConfig(BaseModel):
    """Конфигурация FAISS индекса."""
    index_type: Literal["Flat", "IVF", "HNSW"] = "IVF"
    nlist: int = Field(default=100, ge=1)
    nprobe: int = Field(default=10, ge=1)
    metric: Literal["L2", "IP"] = "IP"  # Inner Product для косинусного


class EmbeddingConfig(BaseModel):
    """Конфигурация эмбеддингов."""
    model_name: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    device: Literal["cpu", "cuda"] = "cpu"
    batch_size: int = 32
    max_length: int = 512


class ChunkingConfig(BaseModel):
    """Конфигурация chunking."""
    enabled: bool = True
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)


class VectorStorageConfig(BaseModel):
    """Конфигурация хранилища."""
    index_path: str = "./data/vector/index.faiss"
    metadata_path: str = "./data/vector/metadata.json"
    backup_enabled: bool = True
    backup_interval_hours: int = 24


class VectorSearchConfig(BaseModel):
    """Общая конфигурация векторного поиска."""
    enabled: bool = True
    faiss: FAISSConfig = Field(default_factory=FAISSConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    storage: VectorStorageConfig = Field(default_factory=VectorStorageConfig)
    
    # Поиск
    default_top_k: int = 10
    max_top_k: int = 100
    default_min_score: float = 0.5
    
    # Производительность
    max_workers: int = 4
    timeout_seconds: float = 30.0
```

### Обновление SystemConfig:
```python
# core/config/models.py

class SystemConfig(BaseModel):
    """Системная конфигурация."""
    # ... существующие поля ...
    
    vector_search: Optional[VectorSearchConfig] = None
    
    @validator('vector_search', pre=True, always=True)
    def set_default_vector_config(cls, v):
        if v is None:
            return VectorSearchConfig()
        return v
```

### Тесты:
```
tests/unit/config/test_vector_config.py
```

### Критерии завершения:
- [ ] Все конфиги валидируются
- [ ] Значения по умолчанию работают
- [ ] Интеграция с SystemConfig

---

## 1.3 YAML контракты

### Задачи:
- [ ] Создать контракт input для поиска
- [ ] Создать контракт output для поиска
- [ ] Создать контракт input для добавления документа
- [ ] Создать контракт output для добавления документа
- [ ] Валидировать контракты

### Файлы:
```
data/contracts/tool/vector_search/
├── search_input_v1.0.0.yaml
├── search_output_v1.0.0.yaml
├── add_document_input_v1.0.0.yaml
└── add_document_output_v1.0.0.yaml
```

### Пример контракта:
```yaml
# data/contracts/tool/vector_search/search_input_v1.0.0.yaml

$schema: "http://json-schema.org/draft-07/schema#"
type: object
title: "VectorSearchInput"
description: "Входные данные для векторного поиска"
version: "1.0.0"

properties:
  query:
    type: string
    description: "Текст запроса"
    minLength: 1
    maxLength: 10000
  
  vector:
    type: array
    description: "Вектор запроса (альтернатива query)"
    items:
      type: number
  
  top_k:
    type: integer
    description: "Количество результатов"
    default: 10
    minimum: 1
    maximum: 100
  
  min_score:
    type: number
    description: "Минимальный порог схожести"
    default: 0.5
    minimum: 0.0
    maximum: 1.0
  
  filters:
    type: object
    description: "Фильтры по метаданным"
    properties:
      category:
        type: array
        items:
          type: string
      tags:
        type: array
        items:
          type: string
      date_from:
        type: string
        format: date
      date_to:
        type: string
        format: date
      author:
        type: string
  
  offset:
    type: integer
    description: "Смещение для пагинации"
    default: 0
    minimum: 0

required:
  - query

additionalProperties: false
```

### Тесты:
```
tests/unit/contracts/test_vector_contracts.py
```

### Критерии завершения:
- [ ] Все контракты валидны (JSON Schema)
- [ ] Контракты загружаются через DataRepository
- [ ] Примеры данных проходят валидацию

---

## 1.4 Манифест инструмента

### Задачи:
- [ ] Создать манифест VectorTool
- [ ] Определить capabilities
- [ ] Определить prompts (если нужны)

### Файлы:
```
data/manifests/tools/vector_tool/
└── manifest.yaml
```

### Пример манифеста:
```yaml
# data/manifests/tools/vector_tool/manifest.yaml

name: "vector_tool"
version: "1.0.0"
description: "Инструмент векторного поиска по базе знаний"

type: "tool"
category: "search"

capabilities:
  - name: "vector_search"
    description: "Поиск документов по тексту или вектору"
    input_contract: "vector_search.search_input_v1.0.0"
    output_contract: "vector_search.search_output_v1.0.0"
  
  - name: "add_document"
    description: "Добавление документа в индекс"
    input_contract: "vector_search.add_document_input_v1.0.0"
    output_contract: "vector_search.add_document_output_v1.0.0"
  
  - name: "delete_document"
    description: "Удаление документа из индекса"
    input_contract: "vector_search.delete_document_input_v1.0.0"
    output_contract: "vector_search.delete_document_output_v1.0.0"
  
  - name: "get_index_info"
    description: "Получение информации об индексе"
    input_contract: "vector_search.get_index_info_input_v1.0.0"
    output_contract: "vector_search.get_index_info_output_v1.0.0"

dependencies:
  infrastructure:
    - "vector_provider"
    - "embedding_provider"
  services:
    - "vector_search_service"

config:
  enabled: true
  default_top_k: 10
  max_top_k: 100
```

### Критерии завершения:
- [ ] Манифест загружается через DataRepository
- [ ] Все capabilities определены
- [ ] Контракты связаны

---

## 1.5 Обновление реестра (registry.yaml)

### Задачи:
- [ ] Добавить vector_search в registry.yaml
- [ ] Определить профили (dev, prod)
- [ ] Протестировать загрузку

### Файлы:
```
registry.yaml  ← Обновление
```

### Пример обновления:
```yaml
# registry.yaml

profiles:
  dev:
    vector_search:
      enabled: true
      faiss:
        index_type: "Flat"  # Проще для отладки
        nlist: 10
        nprobe: 5
      embedding:
        model_name: "all-MiniLM-L6-v2"
        device: "cpu"
      storage:
        index_path: "./data/vector/dev_index.faiss"
        metadata_path: "./data/vector/dev_metadata.json"
  
  prod:
    vector_search:
      enabled: true
      faiss:
        index_type: "IVF"
        nlist: 100
        nprobe: 10
      embedding:
        model_name: "all-MiniLM-L6-v2"
        device: "cpu"
      storage:
        index_path: "./data/vector/prod_index.faiss"
        metadata_path: "./data/vector/prod_metadata.json"
```

### Критерии завершения:
- [ ] AppConfig.from_registry() загружает vector_search
- [ ] Профили dev/prod работают
- [ ] Значения по умолчанию применяются

---

## Итоги ЭТАПА 1

### Артефакты:
```
core/models/types/vector_types.py          ← Модели данных
core/config/vector_config.py               ← Конфигурация
core/config/models.py                      ← Обновление SystemConfig
data/contracts/tool/vector_search/         ← Контракты
  ├── search_input_v1.0.0.yaml
  ├── search_output_v1.0.0.yaml
  ├── add_document_input_v1.0.0.yaml
  ├── add_document_output_v1.0.0.yaml
  ├── delete_document_input_v1.0.0.yaml
  ├── delete_document_output_v1.0.0.yaml
  ├── get_index_info_input_v1.0.0.yaml
  └── get_index_info_output_v1.0.0.yaml
data/manifests/tools/vector_tool/          ← Манифест
  └── manifest.yaml
registry.yaml                              ← Обновление
```

### Тесты:
```
tests/unit/models/test_vector_types.py     ← Тесты моделей
tests/unit/config/test_vector_config.py    ← Тесты конфигурации
tests/unit/contracts/test_vector_contracts.py ← Тесты контрактов
```

### Критерии завершения этапа:
- [ ] Все модели созданы и валидны
- [ ] Все конфиги работают
- [ ] Все контракты созданы и валидны
- [ ] Манифест загружается
- [ ] Registry обновлён
- [ ] Unit тесты проходят (≥ 90% покрытие)

---

# ЭТАП 2: Тесты (Test-First) (6-8 часов)

## Цель
Написать все тесты ДО реализации (TDD).

---

## 2.1 Mock провайдеры

### Задачи:
- [ ] Создать `MockEmbeddingProvider`
- [ ] Создать `MockFAISSProvider`
- [ ] Создать `MockVectorSearchService`

### Файлы:
```
core/infrastructure/providers/vector/mock_provider.py
tests/mocks/vector_mocks.py
```

### Критерии завершения:
- [ ] Mock провайдеры имитируют реальное поведение
- [ ] Mock провайдеры не требуют внешних зависимостей
- [ ] Mock провайдеры используются в тестах

---

## 2.2 Unit тесты интерфейсов

### Задачи:
- [ ] Тесты `BaseVectorProvider`
- [ ] Тесты `FAISSProvider` (с Mock)
- [ ] Тесты `EmbeddingProvider` (с Mock)
- [ ] Тесты `VectorSearchService`
- [ ] Тесты `ChunkingService`

### Файлы:
```
tests/unit/infrastructure/vector/
├── test_base_vector_provider.py
├── test_faiss_provider.py
├── test_embedding_provider.py
└── test_chunking_service.py

tests/unit/services/
└── test_vector_search_service.py
```

### Критерии завершения:
- [ ] Все тесты написаны
- [ ] Тесты падают (ожидаемое поведение TDD)
- [ ] Покрытие ≥ 85%

---

## 2.3 Integration тесты

### Задачи:
- [ ] Тесты интеграции с InfrastructureContext
- [ ] Тесты интеграции с ApplicationContext
- [ ] Тесты с реальным FAISS (если возможно)

### Файлы:
```
tests/integration/vector/
├── test_vector_provider_integration.py
├── test_vector_service_integration.py
└── test_vector_tool_integration.py
```

### Критерии завершения:
- [ ] Интеграция с контекстами работает
- [ ] Тесты изолированы
- [ ] Тесты воспроизводимы

---

## 2.4 E2E тесты сценариев

### Задачи:
- [ ] Сценарий: Поиск по тексту
- [ ] Сценарий: Добавление документа
- [ ] Сценарий: Обновление документа
- [ ] Сценарий: Удаление документа
- [ ] Сценарий: Поиск с фильтрами

### Файлы:
```
tests/e2e/vector/
├── test_search_e2e.py
├── test_add_document_e2e.py
├── test_update_document_e2e.py
├── test_delete_document_e2e.py
└── test_filtered_search_e2e.py
```

### Критерии завершения:
- [ ] Все сценарии покрыты
- [ ] Тесты проходят на CI/CD
- [ ] Тесты независимы

---

## Итоги ЭТАПА 2

### Артефакты:
```
core/infrastructure/providers/vector/mock_provider.py
tests/mocks/vector_mocks.py
tests/unit/infrastructure/vector/*.py
tests/unit/services/test_vector_search_service.py
tests/integration/vector/*.py
tests/e2e/vector/*.py
```

### Критерии завершения этапа:
- [ ] Все тесты написаны ДО реализации
- [ ] Mock провайдеры созданы
- [ ] Тесты падают (TDD)
- [ ] Покрытие ≥ 85%
- [ ] CI/CD настроен на запуск тестов

---

# ЭТАП 3: Реализация (12-16 часов)

## Цель
Реализовать все компоненты векторного поиска.

---

## 3.1 Infrastructure слой

### Задачи:
- [ ] Создать `BaseVectorProvider` (абстракция)
- [ ] Реализовать `FAISSProvider`
- [ ] Реализовать `EmbeddingProvider`
- [ ] Реализовать `ChunkingService`
- [ ] Создать фабрику провайдеров

### Файлы:
```
core/infrastructure/providers/vector/
├── base_vector.py          ← Базовый класс
├── factory.py              ← Фабрика провайдеров
├── faiss_provider.py       ← FAISS реализация
├── embedding_provider.py   ← SentenceTransformers
├── chunking_service.py     ← Chunking
└── mock_provider.py        ← Mock для тестов
```

### Критерии завершения:
- [ ] BaseVectorProvider определён
- [ ] FAISSProvider реализован
- [ ] EmbeddingProvider реализован
- [ ] ChunkingService реализован
- [ ] Все тесты проходят

---

## 3.2 Application слой

### Задачи:
- [ ] Реализовать `VectorSearchService`
- [ ] Реализовать `DocumentManager`
- [ ] Реализовать `VectorTool`
- [ ] Интегрировать с EventBus
- [ ] Интегрировать с MetricsCollector

### Файлы:
```
core/application/services/
├── vector_search_service.py
└── document_manager.py

core/application/tools/
└── vector_tool.py
```

### Критерии завершения:
- [ ] VectorSearchService реализован
- [ ] DocumentManager реализован
- [ ] VectorTool реализован
- [ ] Интеграция с EventBus
- [ ] Интеграция с MetricsCollector
- [ ] Все тесты проходят

---

## 3.3 Интеграция с контекстами

### Задачи:
- [ ] Интегрировать с `InfrastructureContext`
- [ ] Интегрировать с `ApplicationContext`
- [ ] Обновить `DependencyInjection`

### Файлы:
```
core/infrastructure/context/infrastructure_context.py  ← Обновление
core/application/context/application_context.py        ← Обновление
```

### Критерии завершения:
- [ ] VectorProvider доступен через InfrastructureContext
- [ ] VectorSearchService доступен через ApplicationContext
- [ ] VectorTool зарегистрирован
- [ ] Все тесты проходят

---

## 3.4 Обработка ошибок и логирование

### Задачи:
- [ ] Определить исключения (`VectorSearchError`, `IndexNotFoundError`, etc.)
- [ ] Реализовать обработку ошибок
- [ ] Добавить логирование
- [ ] Добавить retry logic (если нужно)

### Файлы:
```
core/common/exceptions/vector_exceptions.py
core/infrastructure/providers/vector/error_handler.py
```

### Критерии завершения:
- [ ] Все исключения определены
- [ ] Обработка ошибок реализована
- [ ] Логирование добавлено
- [ ] Тесты на ошибки написаны

---

## Итоги ЭТАПА 3

### Артефакты:
```
core/infrastructure/providers/vector/*.py
core/application/services/vector_search_service.py
core/application/services/document_manager.py
core/application/tools/vector_tool.py
core/common/exceptions/vector_exceptions.py
```

### Критерии завершения этапа:
- [ ] BaseVectorProvider реализован
- [ ] FAISSProvider реализован
- [ ] EmbeddingProvider реализован
- [ ] VectorSearchService реализован
- [ ] VectorTool реализован
- [ ] Интеграция с контекстами завершена
- [ ] Обработка ошибок реализована
- [ ] Логирование добавлено
- [ ] Все тесты проходят

---

# ЭТАП 4: Верификация (4-6 часов)

## Цель
Верифицировать корректность и производительность.

---

## 4.1 Запуск всех тестов

### Задачи:
- [ ] Запустить unit тесты
- [ ] Запустить integration тесты
- [ ] Запустить e2e тесты
- [ ] Исправить failing тесты

### Команды:
```bash
pytest tests/unit/vector/ -v --cov
pytest tests/integration/vector/ -v
pytest tests/e2e/vector/ -v
```

### Критерии завершения:
- [ ] Все unit тесты проходят (100%)
- [ ] Все integration тесты проходят
- [ ] Все e2e тесты проходят
- [ ] Покрытие ≥ 85%

---

## 4.2 Performance тесты

### Задачи:
- [ ] Создать benchmark для поиска
- [ ] Измерить p50/p95/p99
- [ ] Измерить recall@k
- [ ] Оптимизировать при необходимости

### Файлы:
```
benchmarks/test_vector_search.py
```

### Критерии завершения:
- [ ] p95 < 1000ms
- [ ] recall@10 > 0.90
- [ ] Результаты задокументированы

---

## 4.3 Code review

### Задачи:
- [ ] Проверить архитектуру
- [ ] Проверить код на соответствие стандартам
- [ ] Проверить обработку ошибок
- [ ] Проверить безопасность

### Чек-лист:
- [ ] Код соответствует PEP 8
- [ ] Типизация добавлена
- [ ] Docstrings написаны
- [ ] Исключения обрабатываются
- [ ] Нет уязвимостей безопасности

---

## Итоги ЭТАПА 4

### Критерии завершения этапа:
- [ ] Все тесты проходят (100%)
- [ ] Performance тесты соответствуют требованиям
- [ ] Code review завершён без критических замечаний
- [ ] Уязвимости безопасности проверены
- [ ] Отчёт о тестировании создан

---

# ЭТАП 5: Документация (2-4 часа)

## Цель
Создать полную документацию для разработчиков и пользователей.

---

## 5.1 API документация

### Задачи:
- [ ] Документировать VectorSearchService
- [ ] Документировать VectorTool
- [ ] Документировать контракты
- [ ] Создать примеры использования

### Файлы:
```
docs/api/vector_search_api.md
docs/api/vector_tool_api.md
```

---

## 5.2 Руководства

### Задачи:
- [ ] Руководство для разработчиков
- [ ] Руководство для пользователей
- [ ] FAQ

### Файлы:
```
docs/guides/vector_search.md
docs/guides/vector_search_faq.md
```

---

## 5.3 Примеры

### Задачи:
- [ ] Примеры использования VectorTool
- [ ] Примеры настройки
- [ ] Примеры интеграции

### Файлы:
```
examples/vector_search_examples.py
```

---

## 5.4 Обновление CHANGELOG

### Задачи:
- [ ] Добавить изменения в CHANGELOG.md
- [ ] Обновить версию

### Файлы:
```
CHANGELOG.md
```

---

## Итоги ЭТАПА 5

### Критерии завершения этапа:
- [ ] API документация обновлена
- [ ] Руководства созданы
- [ ] Примеры использования добавлены
- [ ] CHANGELOG обновлён
- [ ] Документация проверена

---

# 📊 Сводный чек-лист проекта

## ЭТАП 0: Подготовка ✅
- [x] Все вопросы отвечены
- [x] Архитектурные решения задокументированы
- [x] Требования определены
- [x] Риски оценены

## ЭТАП 1: Модели данных ⏳
- [ ] Модели данных созданы
- [ ] Конфигурация создана
- [ ] Контракты YAML созданы
- [ ] Манифест создан
- [ ] Registry обновлён
- [ ] Unit тесты моделей проходят

## ЭТАП 2: Тесты ⏳
- [ ] Mock провайдеры созданы
- [ ] Unit тесты интерфейсов написаны
- [ ] Integration тесты написаны
- [ ] E2E тесты написаны
- [ ] Покрытие ≥ 85%

## ЭТАП 3: Реализация ⏳
- [ ] BaseVectorProvider реализован
- [ ] FAISSProvider реализован
- [ ] EmbeddingProvider реализован
- [ ] VectorSearchService реализован
- [ ] VectorTool реализован
- [ ] Интеграция с контекстами завершена
- [ ] Обработка ошибок реализована

## ЭТАП 4: Верификация ⏳
- [ ] Все тесты проходят
- [ ] Performance тесты соответствуют требованиям
- [ ] Code review завершён
- [ ] Безопасность проверена

## ЭТАП 5: Документация ⏳
- [ ] API документация обновлена
- [ ] Руководства созданы
- [ ] Примеры добавлены
- [ ] CHANGELOG обновлён

---

*Документ создан: 2026-02-19*  
*Версия: 1.0.0*  
*Статус: ⏳ На согласовании*

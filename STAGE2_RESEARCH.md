# ЭТАП 2: РЕЗУЛЬТАТЫ ИССЛЕДОВАНИЯ

---

## 2.1 Logging Config

### Файлы:
| Файл | Использований | Статус |
|------|-------------|--------|
| `core/config/logging_config.py` | 8 | **ОСТАВИТЬ** |
| `core/infrastructure/logging/log_config.py` | 0 | УДАЛИТЬ |
| `core/infrastructure/logging/config.py` | - | УДАЛЁН |

### Решение:
Оставить `core/config/logging_config.py`, удалить `log_config.py`

### В файле logging_config.py:
- `LoggingConfig` - класс конфигурации
- `LogLevel` - enum (используется)
- `LogFormat` - enum (используется)

---

## 2.2 LogLevel / LogFormat

### Определения:
| Класс | Файл | Использований |
|-------|------|--------------|
| `LogLevel` | `core/config/logging_config.py` | 8 |
| `LogLevel` | `core/infrastructure/logging/log_config.py` | 0 |
| `LogFormat` | `core/config/logging_config.py` | 8 |
| `LogFormat` | `core/infrastructure/logging/log_config.py` | 0 |

### Решение:
Оставить в `core/config/logging_config.py`, удалить из `log_config.py`

---

## 2.3 Interface Duplicates

### IMetricsStorage:
| Интерфейс | Файл | Тип | Использований |
|-----------|------|-----|--------------|
| `IMetricsStorage` | `core/infrastructure/interfaces/metrics_log_interfaces.py` | ABC | 6 |
| `MetricsStorageInterface` | `core.interfaces.metrics_storage.py` | Protocol | 3 |

### ILogStorage:
| Интерфейс | Файл | Тип | Использований |
|-----------|------|-----|--------------|
| `ILogStorage` | `core/infrastructure/interfaces/metrics_log_interfaces.py` | ABC | 4 |
| `LogStorageInterface` | `core.interfaces.log_storage.py` | Protocol | 3 |

### Решение:
Объединить на основе `core.infrastructure.interfaces.metrics_log_interfaces`:
- Оставить `IMetricsStorage` и `ILogStorage`
- Удалить `core.interfaces.metrics_storage.py`
- Удалить `core.interfaces.log_storage.py`
- Обновить импорты в:
  - `core/components/base_component.py`
  - `core/application/services/base_service.py`

---

## 2.4 ComponentStatus

### Определения:
| Файл | Определений | Использований |
|------|------------|--------------|
| `core/models/enums/common_enums.py` | 1 | 20+ |
| `core/models/data/manifest.py` | 1 | 5 |
| `core/components/component_discovery.py` | 1 | 5 |

### Решение:
Оставить в `core/models/enums/common_enums.py` (самое популярное), удалить дубликаты из:
- `core/models/data/manifest.py`
- `core/components/component_discovery.py`

---

## ПЛАН ДЕЙСТВИЙ:

### Шаг 1: Удалить `log_config.py`
```bash
rm core/infrastructure/logging/log_config.py
```

### Шаг 2: Объединить interfaces
- Удалить `core/interfaces/metrics_storage.py`
- Удалить `core/interfaces/log_storage.py`
- Обновить импорты в 5 файлах

### Шаг 3: Объединить ComponentStatus
- Удалить из `manifest.py`
- Удалить из `component_discovery.py`
- Обновить импорты

---

## ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ:

### К удалению:
1. `core/infrastructure/logging/log_config.py`
2. `core/interfaces/metrics_storage.py`
3. `core/interfaces/log_storage.py`
4. `core/models/data/manifest.py` (частично - ComponentStatus)
5. `core/components/component_discovery.py` (частично - ComponentStatus)

### К изменению:
1. `core/components/base_component.py` - импорт
2. `core/application/services/base_service.py` - импорт
3. `core/infrastructure/context/infrastructure_context.py` - ?
4. `core/models/enums/common_enums.py` - проверить

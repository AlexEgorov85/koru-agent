# План доработки конфигурации

**Дата:** 5 апреля 2026 г.
**Объект:** Система конфигурации Agent_v5

---

## 🔍 Текущее состояние

### Файлы конфигурации:
| Файл | Назначение | Статус |
|------|-----------|--------|
| `core/config/defaults/dev.yaml` | Инфраструктура dev | ⚠️ |
| `core/config/defaults/prod.yaml` | Инфраструктура prod | ⚠️ |
| `core/config/defaults/test.yaml` | Инфраструктура test | ✅ |
| `core/config/defaults/base.yaml` | Базовые настройки | ❓ |
| `core/config/defaults/secrets_dev.yaml` | Секреты dev | ⚠️ |
| `core/config/app_config.py` | AppConfig (единая) | ⚠️ |
| `core/config/__init__.py` | Точка входа | ✅ |
| `data/registry.test.yaml` | Тестовый registry | ✅ |
| `data/registry.yaml` | **ОТСУТСТВУЕТ** | ❌ |

---

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### 1. API-ключ захардкожен в dev.yaml и prod.yaml
**Файлы:** `dev.yaml`, `prod.yaml`

```yaml
api_key: "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"
```

**Проблема:** Секрет хранится в исходном коде.
**Решение:** Вынести в `secrets_dev.yaml` / `.env` / переменные окружения.

### 2. Нет `data/registry.yaml`
**Файл:** `data/registry.yaml`

**Проблема:** Файл отсутствует. AppConfig.from_discovery() работает без registry, но документация ссылается на него.
**Решение:** Создать пустой registry.yaml или удалить все ссылки на него.

### 3. Profile определён в обоих слоях
**Файлы:** `dev.yaml` (строка `profile: dev`), `prod.yaml` (строка `profile: prod`)

**Проблема:** По AGENTS.md, `profile` — параметр AppConfig (Application слой), а не InfraConfig. Это дублирование.
**Решение:** Убрать `profile` из YAML файлов, передавать только через `from_discovery(profile=...)`.

### 4. `agent` секция в YAML — дублирование
**Файлы:** `dev.yaml`, `prod.yaml`

```yaml
agent:
  default_strategy: react
  max_steps: 10
  temperature: 0.2
  ...
```

**Проблема:** По AGENTS.md, `max_steps`, `temperature` — это AgentConfig (Session слой), не InfraConfig. Эти параметры не должны быть в YAML.
**Решение:** Убрать `agent` секцию из YAML, оставить только `llm_providers`, `db_providers`, `data_dir`, `log_dir`.

### 5. `version: 5.15.0` в YAML
**Файлы:** `dev.yaml`, `prod.yaml`

**Проблема:** Версия в InfraConfig не имеет смысла. Версия приложения должна быть в одном месте (CHANGELOG, __version__).
**Решение:** Убрать `version` из YAML файлов.

### 6. `providers.cache` и `providers.monitoring` — неизвестные провайдеры
**Файлы:** `dev.yaml`, `prod.yaml`

```yaml
providers:
  cache:
    enabled: true
    ttl: 300
    type: memory
  monitoring:
    enabled: true
    endpoint: http://localhost:9090
```

**Проблема:** Нет кода, который читает эти секции. Мёртвый конфиг.
**Решение:** Удалить или реализовать поддержку.

### 7. `security.secrets_path` — файл не загружается
**Файлы:** `dev.yaml` (`secrets_path: core/config/defaults/secrets_dev.yaml`), `prod.yaml` (`secrets_path: null`)

**Проблема:** Нет кода, который загружает secrets_path. Мёртвый конфиг.
**Решение:** Удалить или реализовать загрузку секретов.

### 8. `debug: true/false` — дублирование профиля
**Файлы:** `dev.yaml`, `prod.yaml`

**Проблема:** `debug` уже определяется через `profile == "dev"` в `AppConfig.from_discovery()`.
**Решение:** Убрать `debug` из YAML.

---

## ⚠️ ПРЕДУПРЕЖДЕНИЯ

### 9. `default_llm_2` в prod.yaml отключён
**Файл:** `prod.yaml`

```yaml
default_llm_2:
  enabled: false
  ...
```

**Проблема:** Мёртвый конфиг. Если не используется — удалить.
**Решение:** Удалить или документировать зачем нужен.

### 10. `llm_timeout_seconds: 1200.0` и `timeout_seconds: 300.0`
**Файлы:** `dev.yaml`, `prod.yaml`

**Проблема:** Два таймаута на разных уровнях. `agent.llm_timeout_seconds: 1200` vs `llm_providers.default_llm.timeout_seconds: 300`.
**Решение:** Оставить один — на уровне провайдера.

### 11. `vector_search.indexes.authors` — отдельный индекс
**Файлы:** `dev.yaml`, `prod.yaml`

```yaml
indexes:
  authors: authors_index.faiss
```

**Проблема:** Нет документации по authors_index. Не используется?
**Решение:** Проверить код, удалить если не используется.

### 12. `vector_search.embedding.model_name: models/embedding/all-MiniLM-L6-v2`
**Файлы:** `dev.yaml`, `prod.yaml`

**Проблема:** Относительный путь без base_path. Файл модели может не найтись.
**Решение:** Проверить что модель существует по этому пути.

---

## 📋 ЧТО НЕ ХВАТИТ

### 13. Нет `.env.example`
**Решение:** Создать `.env.example` с placeholder-значениями для всех AGENT_* переменных.

### 14. Нет документации по конфигурации
**Решение:** Создать `docs/guides/configuration.md` с описанием:
- Трёхуровневая архитектура (InfraConfig/AppConfig/AgentConfig)
- Какие параметры где должны быть
- Как добавить новый провайдер
- Как работают профили

### 15. Нет валидации YAML
**Решение:** Добавить скрипт `scripts/validation/check_yaml_syntax.py` (уже есть по AGENTS.md, проверить).

---

## 📋 ПЛАН ИСПРАВЛЕНИЙ

### P0 — Критические (безопасность)
| # | Задача | Файлы |
|---|--------|-------|
| 1 | Вынести API-ключ из dev.yaml | `dev.yaml` |
| 2 | Вынести API-ключ из prod.yaml | `prod.yaml` |
| 3 | Создать `.env.example` | `.env.example` |

### P1 — Архитектурные (соответствие AGENTS.md)
| # | Задача | Файлы |
|---|--------|-------|
| 4 | Убрать `profile` из YAML | `dev.yaml`, `prod.yaml` |
| 5 | Убрать `agent` секцию из YAML | `dev.yaml`, `prod.yaml` |
| 6 | Убрать `version` из YAML | `dev.yaml`, `prod.yaml` |
| 7 | Убрать `debug` из YAML | `dev.yaml`, `prod.yaml` |
| 8 | Убрать `providers` секцию | `dev.yaml`, `prod.yaml` |
| 9 | Убрать `security` секцию | `dev.yaml`, `prod.yaml` |
| 10 | Убрать дублирующий таймаут | `dev.yaml`, `prod.yaml` |

### P2 — Чистка
| # | Задача | Файлы |
|---|--------|-------|
| 11 | Удалить/документировать `default_llm_2` | `prod.yaml` |
| 12 | Проверить `authors` индекс | `dev.yaml`, `prod.yaml` |
| 13 | Проверить путь к embedding модели | `dev.yaml`, `prod.yaml` |

### P3 — Документация
| # | Задача | Файлы |
|---|--------|-------|
| 14 | Создать `docs/guides/configuration.md` | новый |
| 15 | Обновить ссылки на registry.yaml | docs/* |
| 16 | Создать `data/registry.yaml` или удалить ссылки | `data/registry.yaml` |

---

## 🎯 ЦЕЛЕВОЕ СОСТОЯНИЕ YAML

После исправлений, `dev.yaml` должен выглядеть так:

```yaml
# InfraConfig ONLY — тяжёлые ресурсы (общие для всех агентов)
data_dir: data
log_dir: logs/dev
log_level: DEBUG

llm_providers:
  default_llm:
    provider_type: openrouter
    model_name: qwen/qwen3.6-plus:free
    enabled: true
    # api_key — из .env / secrets_dev.yaml
    parameters:
      temperature: 0.2
      max_tokens: 4096
      timeout_seconds: 120.0
    timeout_seconds: 300.0

db_providers:
  books_db:
    provider_type: sqlite
    enabled: true
    parameters:
      db_path: data/books.db
      timeout: 30.0
  default_db:
    provider_type: postgres
    enabled: true
    parameters:
      host: localhost
      port: 5432
      database: postgres
      username: postgres
      password: '1'  # TODO: вынести в секреты
      pool_size: 5
      timeout: 30.0
      sslmode: disable

vector_search:
  enabled: true
  indexes:
    books: books_index.faiss
    docs: docs_index.faiss
    history: history_index.faiss
    knowledge: knowledge_index.faiss
  embedding:
    model_name: models/embedding/all-MiniLM-L6-v2
    dimension: 384
  chunking:
    chunk_size: 500
    chunk_overlap: 50
    min_chunk_size: 50
  faiss:
    index_type: Flat
    metric: IP
  storage:
    base_path: data/vector
```

**Удалено:**
- ❌ `agent` (→ AgentConfig, session уровень)
- ❌ `profile` (→ AppConfig.from_discovery(profile=...))
- ❌ `debug` (→ определяется из профиля)
- ❌ `version` (→ CHANGELOG)
- ❌ `providers` (мёртвый конфиг)
- ❌ `security` (мёртвый конфиг)
- ❌ `api_key` (→ .env / secrets)
- ❌ `default_llm_2` (мёртвый конфиг)

---

*План сформирован автоматически, 5 апреля 2026 г.*

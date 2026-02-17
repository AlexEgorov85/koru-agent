# ⚙️ Руководство по конфигурации Agent_v5

> **Версия:** 5.1.0
> **Дата обновления:** 2026-02-17
> **Статус:** approved
> **Владелец:** @system

---

## 📋 Оглавление

- [Обзор](#-обзор)
- [Система конфигурации](#-система-конфигурации)
- [Файлы конфигурации](#-файлы-конфигурации)
- [Профили окружения](#-профили-окружения)
- [Конфигурация компонентов](#-конфигурация-компонентов)
- [Переменные окружения](#-переменные-окружения)
- [Валидация](#-валидация)

---

## 🔍 Обзор

Система конфигурации использует YAML-файлы с поддержкой профилей и переменных окружения.

### Уровни конфигурации

```
SystemConfig (инфраструктура)
    ↓
AppConfig (глобальная)
    ↓
ComponentConfig (локальная)
```

| Тип | Класс | Источник | Назначение |
|-----|-------|----------|------------|
| **SystemConfig** | `SystemConfig` | `core/config/defaults/{profile}.yaml` | Инфраструктура, провайдеры |
| **AppConfig** | `AppConfig` | `data/registry.yaml` | Глобальные настройки |
| **ComponentConfig** | `ComponentConfig` | Генерируется из AppConfig | Конфигурация компонента |

---

## 📄 Файлы конфигурации

### registry.yaml

Основной файл конфигурации приложения.

```yaml
# data/registry.yaml
profile: prod

behaviors:
  react_pattern:
    enabled: true
    dependencies: []
    parameters:
      max_thoughts: 5
    prompt_versions:
      behavior.react.think: v1.0.0
    manifest_path: data/manifests/behaviors/react_pattern/manifest.yaml

services:
  prompt_service:
    enabled: true
    dependencies: []
    manifest_path: data/manifests/services/prompt_service/manifest.yaml

  sql_generation_service:
    enabled: true
    dependencies: []
    parameters:
      max_retries: 3
      timeout: 30
    manifest_path: data/manifests/services/sql_generation_service/manifest.yaml
```

### Базовая конфигурация

```yaml
# core/config/defaults/base.yaml
profile: dev
log_level: DEBUG
log_dir: logs

providers:
  llm:
    provider_type: llama_cpp
    model_name: mistral-7b-instruct-v0.2
    parameters:
      n_ctx: 4096
      n_threads: 4
  
  database:
    provider_type: mock
```

---

## 🔄 Профили окружения

| Профиль | Назначение | Версии | Побочные эффекты |
|---------|------------|--------|------------------|
| **dev** | Разработка | active, draft | Разрешены |
| **test** | Тестирование | active | Разрешены (mock) |
| **prod** | Продакшен | active | Разрешены |
| **sandbox** | Песочница | все | Заблокированы |

### Переключение профиля

```bash
# Через переменную окружения
export AGENT_PROFILE=prod
python main.py

# Через аргумент командной строки
python main.py --profile=prod
```

---

## 🧩 Конфигурация компонентов

### ComponentConfig

```python
class ComponentConfig:
    prompt_versions: Dict[str, str] = {}
    input_contract_versions: Dict[str, str] = {}
    output_contract_versions: Dict[str, str] = {}
    parameters: Dict[str, Any] = {}
    base_path: str = ""
    status: str = "active"
```

### Получение ComponentConfig

```python
component_config = app_context.get_component_config("sql_generation_service")

# Доступ к параметрам
max_retries = component_config.parameters.get("max_retries", 3)
timeout = component_config.parameters.get("timeout", 30)

# Доступ к версиям ресурсов
prompt_version = component_config.prompt_versions["sql_generation.generate_query"]
```

---

## 🔐 Переменные окружения

### Синтаксис

```yaml
providers:
  database:
    parameters:
      # Простая подстановка
      host: ${DB_HOST}
      
      # Значение по умолчанию
      port: ${DB_PORT|5432}
      
      # Путь к файлу
      password_file: ${DB_PASSWORD_FILE|/run/secrets/db_password}
```

### Пример .env файла

```bash
# .env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=agent_db
DB_USER=agent
DB_PASSWORD=secret_password

LLM_API_KEY=your_api_key_here
LOG_LEVEL=INFO
```

### Загрузка переменных

```bash
# Создание .env
cp .env.example .env

# Загрузка
source .env
export $(cat .env | xargs)
```

---

## ✅ Валидация

### Автоматическая валидация

```bash
# Проверка конфигурации
python scripts/validate_registry.py

# Проверка манифестов
python scripts/validate_all_manifests.py

# Проверка YAML-синтаксиса
python scripts/check_yaml_syntax.py
```

### Проверки валидации

| Проверка | Описание |
|----------|----------|
| **Существование файлов** | Манифесты, промпты, контракты существуют |
| **Версии ресурсов** | Версии существуют в хранилище |
| **Зависимости** | Зависимые компоненты включены |
| **Статусы версий** | Prod принимает только active версии |

### Обработка ошибок

```python
from core.config import get_config
from core.models.errors.architecture_violation import ConfigurationError

try:
    config = get_config(profile="prod")
except ConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    config = get_config(profile="dev")  # Fallback
```

---

## 🔗 Ссылки

- [Обзор архитектуры](./ARCHITECTURE_OVERVIEW.md)
- [Развёртывание](./DEPLOYMENT_GUIDE.md)
- [registry.yaml](../registry.yaml)
- [config_loader.py](../core/config/config_loader.py)

---

*Документ автоматически сгенерирован. Не редактируйте вручную.*

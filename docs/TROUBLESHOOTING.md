# 🐛 Устранение неполадок Agent_v5

> **Версия:** 5.1.0
> **Дата обновления:** 2026-02-17
> **Статус:** approved
> **Владелец:** @system

---

## 📋 Оглавление

- [Обзор](#-обзор)
- [Диагностика](#-диагностика)
- [Частые ошибки](#-частые-ошибки)
- [Проблемы конфигурации](#-проблемы-конфигурации)
- [Проблемы компонентов](#-проблемы-компонентов)
- [Восстановление](#-восстановление)

---

## 🔍 Обзор

Руководство по диагностике и устранению проблем в Agent_v5.

---

## 🔬 Диагностика

### Быстрая проверка

```bash
# Конфигурация
python scripts/validate_registry.py

# Манифесты
python scripts/validate_all_manifests.py

# Зависимости
pip check

# Python версия
python --version  # Должно быть 3.10+
```

### Диагностика через логи

```bash
# Отладочное логирование
export LOG_LEVEL=DEBUG
python main.py --debug

# Просмотр логов
tail -f logs/agent_*.log

# Поиск ошибок
grep -i error logs/agent_*.log
```

---

## ❌ Частые ошибки

### ConfigurationError

**Симптом**:
```
ConfigurationError: Invalid configuration: missing required field 'provider_type'
```

**Решение**:
```bash
# Проверка registry.yaml
python scripts/check_yaml_syntax.py registry.yaml

# Проверка переменных
env | grep DB_
env | grep LLM_
```

### ComponentNotInitializedError

**Симптом**:
```
ComponentNotInitializedError: Component 'sql_generation_service' not initialized
```

**Решение**:
```python
# Правильный порядок
component = MyComponent(config, app_context)
await component.initialize()  # Обязательно!
result = await component.execute(params)
```

### PromptNotFound

**Симптом**:
```
PromptNotFound: Prompt 'planning.create_plan' not found in cache
```

**Решение**:
```yaml
# registry.yaml - добавьте prompt_versions
skills:
  planning:
    enabled: true
    prompt_versions:
      planning.create_plan: v1.0.0
```

```bash
# Проверка манифеста
ls -la data/manifests/skills/planning/manifest.yaml
```

### ContractValidationError

**Симптом**:
```
ContractValidationError: Input validation failed: missing required field 'query'
```

**Решение**:
```python
# Проверка схемы
schema = component.get_input_contract("my_component.execute")
print(schema)

# Исправление входных данных
params = {
    "query": "SELECT * FROM table",  # Обязательно
    "limit": 100
}
```

### ProviderNotAvailable

**Симптом**:
```
ProviderNotAvailable: LLM provider 'vllm' is not available
```

**Решение**:
```bash
# Проверка пакетов
pip list | grep vllm

# Установка
pip install vllm
```

### PathTraversalError

**Симптом**:
```
PathTraversalError: Attempted path traversal detected
```

**Решение**:
```python
# Проверка base_path
print(component.config.base_path)

# Безопасные пути
from pathlib import Path
base = Path(component.config.base_path).resolve()
target = (base / user_path).resolve()

if not str(target).startswith(str(base)):
    raise PathTraversalError()
```

---

## ⚙️ Проблемы конфигурации

### Неправильный профиль

**Диагностика**:
```bash
python -c "from core.config import get_config; print(get_config().profile)"
```

**Решение**:
```bash
export AGENT_PROFILE=prod
python main.py --profile=prod
```

### Переменные окружения

**Симптом**:
```
EnvironmentError: Required variable 'DB_PASSWORD' is not set
```

**Решение**:
```bash
cp .env.example .env
nano .env
source .env
```

---

## 🧩 Проблемы компонентов

### Компонент не загружает промпты

**Диагностика**:
```python
print(component._cached_prompts)
print(component.config.prompt_versions)
```

**Решение**:
```python
await component.reload_prompts()
```

### Зависимости не доступны

**Решение**:
```yaml
services:
  prompt_service:
    enabled: true  # Включите сервис
  
  my_service:
    dependencies:
      - prompt_service
```

---

## 🔄 Восстановление

### После сбоя

```bash
# Остановка
sudo supervisorctl stop agent

# Очистка кэшей
rm -rf /var/cache/agent/*

# Проверка
python scripts/validate_registry.py

# Запуск
sudo supervisorctl start agent
```

### Откат конфигурации

```bash
# Бэкап
cp data/registry.yaml data/registry.yaml.backup

# Восстановление
git checkout HEAD~1 -- data/registry.yaml

# Перезагрузка
sudo supervisorctl restart agent
```

### Аварийный режим

```bash
# Sandbox (без побочных эффектов)
export AGENT_PROFILE=sandbox
python main.py --sandbox

# Минимальная конфигурация
python main.py --config=minimal_registry.yaml
```

---

## 🔗 Ссылки

- [Развёртывание](./DEPLOYMENT_GUIDE.md)
- [Конфигурация](./CONFIGURATION_MANUAL.md)
- [validate_registry.py](../scripts/validate_registry.py)

---

*Документ автоматически сгенерирован. Не редактируйте вручную.*

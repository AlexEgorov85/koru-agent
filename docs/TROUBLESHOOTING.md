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
- [Проблемы производительности](#-проблемы-производительности)
- [Восстановление](#-восстановление)

---

## 🔍 Обзор

Руководство по диагностике и устранению распространённых проблем в Agent_v5.

### Назначение
- **Быстрая диагностика**: Определение корневой причины проблемы
- **Пошаговые решения**: Конкретные шаги для устранения
- **Профилактика**: Предотвращение повторения проблем

### Ключевые возможности
- ✅ **Диагностические скрипты**: Автоматическая проверка состояния
- ✅ **Структурированные логи**: JSON-логи для анализа
- ✅ **Health checks**: Проверка работоспособности компонентов
- ✅ **Метрики**: Мониторинг производительности

---

## 🔬 Диагностика

### Быстрая проверка

```bash
# Проверка конфигурации
python scripts/validate_registry.py

# Проверка манифестов
python scripts/validate_all_manifests.py

# Проверка зависимостей
pip check

# Проверка версии Python
python --version  # Должно быть 3.10+
```

### Диагностика через логи

```bash
# Включение отладочного логирования
export LOG_LEVEL=DEBUG
python main.py --debug

# Просмотр логов в реальном времени
tail -f logs/agent_*.log

# Поиск ошибок
grep -i error logs/agent_*.log

# Анализ JSON-логов
cat logs/agent_*.log | python -m json.tool
```

### Диагностика через метрики

```python
# Проверка метрик
from prometheus_client import generate_latest

metrics = generate_latest()
print(metrics.decode())
```

### Диагностический скрипт

```bash
python scripts/diagnose.py
```

---

## ❌ Частые ошибки

### Ошибка: `ConfigurationError`

**Симптом**:
```
ConfigurationError: Invalid configuration: missing required field 'provider_type'
```

**Причины**:
- Отсутствует обязательное поле в конфигурации
- Неправильный формат YAML
- Переменная окружения не установлена

**Решение**:
```bash
# Проверка registry.yaml
python scripts/check_yaml_syntax.py registry.yaml

# Проверка переменных окружения
env | grep DB_
env | grep LLM_

# Исправление конфигурации
# Убедитесь, что все provider_type указаны корректно
```

### Ошибка: `ComponentNotInitializedError`

**Симптом**:
```
ComponentNotInitializedError: Component 'sql_generation_service' not initialized
```

**Причины**:
- Компонент используется до вызова `initialize()`
- Ошибка при инициализации компонента

**Решение**:
```python
# Правильный порядок инициализации
component = MyComponent(config, app_context)
await component.initialize()  # Обязательно перед использованием
result = await component.execute(params)
```

### Ошибка: `PromptNotFound`

**Симптом**:
```
PromptNotFound: Prompt 'planning.create_plan' not found in cache
```

**Причины**:
- Промпт не указан в `prompt_versions` конфигурации
- Манифест компонента отсутствует
- Версия промта не существует

**Решение**:
```yaml
# registry.yaml - добавьте prompt_versions
skills:
  planning:
    enabled: true
    prompt_versions:
      planning.create_plan: v1.0.0  # Добавьте эту строку
    manifest_path: data/manifests/skills/planning/manifest.yaml
```

```bash
# Проверка существования манифеста
ls -la data/manifests/skills/planning/manifest.yaml

# Проверка промта
ls -la data/prompts/skills/planning/
```

### Ошибка: `ContractValidationError`

**Симптом**:
```
ContractValidationError: Input validation failed: missing required field 'query'
```

**Причины**:
- Входные данные не соответствуют схеме контракта
- Изменилась схема контракта, но код не обновлён

**Решение**:
```python
# Проверка схемы контракта
schema = component.get_input_contract("my_component.execute")
print(schema)

# Исправление входных данных
params = {
    "query": "SELECT * FROM table",  # Обязательное поле
    "limit": 100  # Опциональное поле
}
```

### Ошибка: `ProviderNotAvailable`

**Симптом**:
```
ProviderNotAvailable: LLM provider 'vllm' is not available
```

**Причины**:
- Провайдер не установлен в requirements
- Ошибка инициализации провайдера
- Неправильный `provider_type`

**Решение**:
```bash
# Проверка установленных пакетов
pip list | grep vllm

# Установка провайдера
pip install vllm

# Проверка конфигурации
# Убедитесь, что provider_type указан корректно
```

```yaml
# core/config/defaults/prod.yaml
providers:
  llm:
    provider_type: vllm  # Проверьте это значение
```

### Ошибка: `PathTraversalError`

**Симптом**:
```
PathTraversalError: Attempted path traversal detected: ../../../etc/passwd
```

**Причины**:
- Попытка доступа к файлу вне разрешённой директории
- Неправильный `base_path` в конфигурации

**Решение**:
```python
# Проверка base_path
print(component.config.base_path)

# Использование безопасных путей
from pathlib import Path

base = Path(component.config.base_path).resolve()
target = (base / user_path).resolve()

if not str(target).startswith(str(base)):
    raise PathTraversalError()
```

---

## ⚙️ Проблемы конфигурации

### Проблема: Неправильный профиль

**Симптом**: Агент использует dev-конфигурацию в production

**Диагностика**:
```bash
# Проверка текущего профиля
python -c "from core.config import get_config; print(get_config().profile)"
```

**Решение**:
```bash
# Установка правильного профиля
export AGENT_PROFILE=prod
python main.py

# Или через аргумент
python main.py --profile=prod
```

### Проблема: Переменные окружения не загружаются

**Симптом**:
```
EnvironmentError: Required variable 'DB_PASSWORD' is not set
```

**Диагностика**:
```bash
# Проверка переменных
env | grep DB_

# Проверка .env файла
cat .env
```

**Решение**:
```bash
# Создание .env файла
cp .env.example .env

# Редактирование
nano .env

# Загрузка переменных
source .env
export $(cat .env | xargs)
```

### Проблема: Версии ресурсов не совпадают

**Симптом**:
```
VersionMismatch: Prompt version 'v2.0.0' not found in manifests
```

**Диагностика**:
```bash
# Проверка версий в registry.yaml
grep -A5 "prompt_versions" registry.yaml

# Проверка существующих версий
find data/manifests -name "*.yaml" -exec grep -l "v2.0.0" {} \;
```

**Решение**:
```yaml
# Исправление версий в registry.yaml
services:
  my_service:
    prompt_versions:
      my_service.execute: v1.0.0  # Измените на существующую версию
```

---

## 🧩 Проблемы компонентов

### Проблема: Компонент не загружает промпты

**Симптом**: Пустой кэш промптов после инициализации

**Диагностика**:
```python
# Проверка кэша компонента
print(component._cached_prompts)

# Проверка конфигурации
print(component.config.prompt_versions)
```

**Решение**:
```python
# Принудительная перезагрузка промптов
await component.reload_prompts()

# Проверка манифеста
manifest = load_manifest(component.config.manifest_path)
print(manifest.prompts)
```

### Проблема: Зависимости компонента не доступны

**Симптом**:
```
DependencyError: Required component 'prompt_service' is not enabled
```

**Диагностика**:
```bash
# Проверка зависимостей
grep -A10 "dependencies" registry.yaml
```

**Решение**:
```yaml
# registry.yaml - включите зависимость
services:
  prompt_service:
    enabled: true  # Включите сервис
  
  my_service:
    enabled: true
    dependencies:
      - prompt_service  # Зависимость будет доступна
```

### Проблема: Кэши не изолированы

**Симптом**: Данные одного агента видны другому

**Диагностика**:
```python
# Проверка изоляции кэшей
print(f"Agent 1 prompts: {id(agent1._cached_prompts)}")
print(f"Agent 2 prompts: {id(agent2._cached_prompts)}")
# ID должны быть разными
```

**Решение**:
```python
# Убедитесь, что каждый агент имеет свой ApplicationContext
app_context1 = ApplicationContext(infrastructure_context)
app_context2 = ApplicationContext(infrastructure_context)

component1 = MyComponent(config1, app_context1)
component2 = MyComponent(config2, app_context2)
```

---

## 📊 Проблемы производительности

### Проблема: Высокое потребление памяти

**Симптом**: >4 ГБ памяти на 10 агентов

**Диагностика**:
```bash
# Проверка памяти
ps aux | grep agent | awk '{print $6}'

# Профилирование памяти
python -m memory_profiler main.py
```

**Решение**:
```yaml
# Уменьшение размера контекста
providers:
  llm:
    parameters:
      n_ctx: 2048  # Вместо 8192
```

```python
# Очистка кэшей
import gc

for agent in agents:
    agent.clear_unused_caches()

gc.collect()
```

### Проблема: Медленная инициализация

**Симптом**: >1 секунды на инициализацию агента

**Диагностика**:
```bash
# Профилирование инициализации
python -m cProfile -o profile.stats main.py
python -m pstats profile.stats
```

**Решение**:
```python
# Предзагрузка ресурсов при старте приложения
from core.infrastructure.context.infrastructure_context import InfrastructureContext

# Инициализация при старте
infrastructure_context = await InfrastructureContext.create()
# Ресурсы предзагружены

# Быстрое создание агентов
agent = await create_agent(infrastructure_context)  # ~100 мс
```

### Проблема: Блокирующие I/O операции

**Симптом**: Агент «зависает» во время выполнения

**Диагностика**:
```python
# Включение отладки I/O
import asyncio
asyncio.get_event_loop().set_debug(True)
```

**Решение**:
```python
# Использование асинхронных операций
async def execute(self, params: Dict) -> Dict:
    # Вместо blocking_call()
    result = await async_call()
    
    # Для CPU-интенсивных операций
    from concurrent.futures import ThreadPoolExecutor
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(executor, cpu_intensive_func)
```

---

## 🔄 Восстановление

### Восстановление после сбоя

```bash
# Остановка агента
sudo supervisorctl stop agent

# Очистка кэшей
rm -rf /var/cache/agent/*

# Проверка конфигурации
python scripts/validate_registry.py

# Запуск
sudo supervisorctl start agent

# Проверка статуса
sudo supervisorctl status agent
```

### Откат конфигурации

```bash
# Резервное копирование текущей конфигурации
cp data/registry.yaml data/registry.yaml.backup

# Восстановление предыдущей версии
git checkout HEAD~1 -- data/registry.yaml

# Перезагрузка
sudo supervisorctl restart agent
```

### Восстановление базы данных

```bash
# Создание бэкапа
pg_dump -h localhost -U agent agent_db > backup.sql

# Восстановление
psql -h localhost -U agent agent_db < backup.sql
```

### Аварийный режим

```bash
# Запуск в sandbox-режиме (без побочных эффектов)
export AGENT_PROFILE=sandbox
python main.py --sandbox

# Запуск с минимальной конфигурацией
python main.py --config=minimal_registry.yaml
```

---

## 📞 Поддержка

### Сбор диагностической информации

```bash
# Скрипт сбора информации
python scripts/collect_diagnostics.py

# Создаст архив с:
# - Логами
# - Конфигурацией
# - Метриками
# - Версиями зависимостей
```

### Контакты

| Канал | Описание |
|-------|----------|
| **GitHub Issues** | Баг-репорты и фичи |
| **Discussions** | Вопросы и обсуждения |
| **Email** | Экстренная поддержка |

---

## 🔗 Ссылки

### Документы
- [Развёртывание](./DEPLOYMENT_GUIDE.md)
- [Конфигурация](./CONFIGURATION_MANUAL.md)
- [Мониторинг](./DEPLOYMENT_GUIDE.md#мониторинг)

### Скрипты
- [validate_registry.py](../scripts/validate_registry.py)
- [validate_all_manifests.py](../scripts/validate_all_manifests.py)
- [diagnose.py](../scripts/diagnose.py)

### Логи
- [Расположение логов](./DEPLOYMENT_GUIDE.md#логирование)

---

*Документ автоматически сгенерирован. Не редактируйте вручную.*

# 📋 ПОДРОБНЫЙ ПЛАН РЕФАКТОРИНГА PROJEKT Agent_v5

---

## 📊 РЕЗУЛЬТАТЫ АУДИТА

| Метрика | Значение |
|---------|----------|
| Всего элементов | 1886 |
| Уникальных имён | 1295 |
| Дубликатов | 188 |
| Используется | 509 |
| Не используется | 1377 |

---

## 🎯 ЭТАП 1: КРИТИЧЕСКИЕ ПРОБЛЕМЫ (P0)

### 1.1 Удаление явных дубликатов файлов

| # | Файл | Проблема | Действие |
|---|------|----------|----------|
| 1 | `core/components/base_tool.py` | Дубликат BaseTool в `core/application/tools/base_tool.py` | УДАЛИТЬ |
| 2 | `core/infrastructure/providers/database/base.py` | Дубликат BaseDBProvider в `base_db.py` | УДАЛИТЬ |
| 3 | `core/infrastructure/logging/config.py` | Дубликат LoggingConfig в `log_config.py` | УДАЛИТЬ |
| 4 | `core/infrastructure/interfaces/__init__.py` | Дубликат ре-экспорт из `core/interfaces/__init__.py` | УДАЛИТЬ |
| 5 | `core/config/registry_loader.py` | DEPRECATED, заменён AppConfig.from_discovery | УДАЛИТЬ |
| 6 | `core/config/settings.py` | Только re-export, не используется | УДАЛИТЬ |
| 7 | `core/config/timeout_config.py` | Не используется | УДАЛИТЬ |

**Команды:**
```bash
rm core/components/base_tool.py
rm core/infrastructure/providers/database/base.py
rm core/infrastructure/logging/config.py
rm core/infrastructure/interfaces/__init__.py
rm core/config/registry_loader.py
rm core/config/settings.py
rm core/config/timeout_config.py
```

### 1.2 Удаление неиспользуемых файлов

| Категория | Файлы | Действие |
|-----------|-------|----------|
| tests/mocks/* | 20+ mock классов | Очистить неиспользуемые |
| scripts/* | Утилиты | Проверить и удалить неиспользуемые |

---

## 🎯 ЭТАП 2: ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ (P1)

### 2.1 Logging - 3 файла

**Проблема:** Три файла с LoggingConfig:
- `core/config/logging_config.py`
- `core/infrastructure/logging/config.py`  
- `core/infrastructure/logging/log_config.py`

**Решение:** Оставить `core/infrastructure/logging/log_config.py` (самый полный)

| Что сделать | Файл |
|-------------|------|
| Оставить | `core/infrastructure/logging/log_config.py` |
| Удалить | `core/infrastructure/logging/config.py` |
| Удалить | `core/config/logging_config.py` (слить в log_config) |

**Примечание:** Нужно обновить импорты во всех файлах.

### 2.2 LogFormat/LogLevel - 3 файла

**Проблема:** Enum определены в 3 местах.

| Класс | Файлы |
|-------|-------|
| LogLevel | logging_config.py, config.py, log_config.py |
| LogFormat | logging_config.py, config.py, log_config.py |

**Решение:** Объединить в `core/infrastructure/logging/log_config.py`

### 2.3 Interface Duplicates

**Проблема:** Интерфейсы дублируются:

| Интерфейс | Файл 1 | Файл 2 |
|-----------|--------|---------|
| IMetricsStorage | `core/interfaces/metrics_storage.py` | `core/infrastructure/interfaces/metrics_log_interfaces.py` |
| ILogStorage | `core/interfaces/log_storage.py` | `core/infrastructure/interfaces/metrics_log_interfaces.py` |

**Решение:** Оставить в `core/infrastructure/interfaces/metrics_log_interfaces.py`, удалить дубликаты.

---

## 🎯 ЭТАП 3: ОЧИСТКА НЕИСПОЛЬЗУЕМОГО КОДА (P2)

### 3.1 Component Discovery - проверка использования

Из аудита: ComponentDiscovery используется в 0 местах напрямую (но нужен для инициализации).

**Проверить:**
```bash
grep -r "ComponentDiscovery" core/ --include="*.py"
```

### 3.2 Optimization Module - весь модуль

| Файл | Строк | Проблема |
|------|-------|----------|
| core/application/components/optimization/*.py | ~5000 | Используется 1 раз |

**Действие:** Проверить нужен ли этот модуль, если нет - удалить или закомментировать.

### 3.3 Session Context Files

| Файл | Использований |
|------|--------------|
| core/session_context/step_context.py | 1 |
| core/session_context/data_context.py | 1 |

**Действие:** Проверить можно ли удалить.

### 3.4 Services с низким использованием

| Service | Файлов использует |
|---------|------------------|
| DocumentIndexingService | 1 |
| MetricsPublisher | 3 |
| TableDescriptionService | ? |

**Действие:** Проверить и удалить или оставить.

---

## 🎯 ЭТАП 4: РЕФАКТОРИНГ АРХИТЕКТУРЫ (P3)

### 4.1 Унификация базовых классов

**Проблема:** Несколько базовых классов с похожим функционалом:

| Базовый класс | Где используется |
|---------------|-----------------|
| BaseComponent | skills, tools, services |
| BaseSkill | skills |
| BaseTool | tools |
| BaseService | services |

**Предложение:** Проверить можно ли объединить логику.

### 4.2 Event Bus Consolidation

**Текущее состояние:**
- `core/infrastructure/event_bus/unified_event_bus.py` - основной (исп. 62 раза)
- `core/events/event_bus.py` - возможно legacy

**Действие:** Проверить и удалить legacy.

### 4.3 Config Consolidation

**Текущее:**
- `core/config/app_config.py` - основной (исп. 21 раз)
- `core/config/component_config.py` - дополнительный (исп. 24 раза)
- `core/config/models.py` - legacy (исп. 6 раз)
- `core/config/agent_config.py` - дополнительный (исп. 3 раза)

**Предложение:** Оставить app_config + component_config, удалить models (если не нужен).

---

## 🎯 ЭТАП 5: ОПТИМИЗАЦИЯ (P4)

### 5.1 Удаление пустых __init__.py

Многие `__init__.py` содержат только импорты - это нормально, но проверить на пустые.

### 5.2 Сокращение docstrings

Многие docstrings очень длинные - можно сократить.

### 5.3 Типизация

Проверить использование type hints - многие функции используют `Any` или не типизированы.

---

## 📋 ПОДРОБНЫЙ ЧЕКЛИСТ

### ЭТАП 1: Критические (выполнить сначала)

- [ ] 1.1.1 Удалить `core/components/base_tool.py`
- [ ] 1.1.2 Удалить `core/infrastructure/providers/database/base.py`
- [ ] 1.1.3 Удалить `core/infrastructure/logging/config.py`
- [ ] 1.1.4 Удалить `core/infrastructure/interfaces/__init__.py`
- [ ] 1.1.5 Удалить `core/config/registry_loader.py`
- [ ] 1.1.6 Удалить `core/config/settings.py`
- [ ] 1.1.7 Удалить `core/config/timeout_config.py`

**После каждого удаления:**
```bash
python -c "from core.config import get_config; print('OK')"
python main.py --help
```

### ЭТАП 2: Объединение

- [ ] 2.1.1 Объединить LoggingConfig (оставить log_config.py)
- [ ] 2.1.2 Объединить LogLevel/LogFormat
- [ ] 2.1.3 Удалить дубликаты интерфейсов

### ЭТАП 3: Очистка

- [ ] 3.1.1 Проверить optimization модуль
- [ ] 3.1.2 Проверить session context
- [ ] 3.1.3 Очистить неиспользуемые services
- [ ] 3.1.4 Очистить тестовые mocks

### ЭТАП 4: Архитектура

- [ ] 4.1.1 Проверить EventBus legacy
- [ ] 4.1.2 Проверить Config модели
- [ ] 4.1.3 Унифицировать базовые классы

### ЭТАП 5: Оптимизация

- [ ] 5.1.1 Проверить пустые __init__.py
- [ ] 5.1.2 Оптимизировать docstrings
- [ ] 5.1.3 Улучшить типизацию

---

## ⚠️ ВАЖНЫЕ ПРАВИЛА

1. **После каждого изменения тестировать:**
   ```bash
   python -c "from core.config import get_config; print('OK')"
   python main.py --help
   ```

2. **Не удалять сразу много** - делать постепенно и тестировать

3. **Делать backup** перед крупными изменениями

4. **Документировать** все удалённые файлы в CHANGELOG.md

---

## 📊 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После полного выполнения:

| Метрика | До | После |
|---------|-----|-------|
| Файлов | ~306 | ~290 |
| Дубликатов | 188 | ~50 |
| Неиспользуемых | 1377 | ~500 |
| Строк кода | 68225 | ~60000 |

---

## 🚀 КАК НАЧАТЬ

1. **Создать backup:**
   ```bash
   git add -A
   git commit -m "Before refactoring"
   ```

2. **Начать с Этапа 1** - удалить явные дубликаты

3. **Тестировать после каждого удаления**

4. **Запустить полный тест:**
   ```bash
   pytest tests/ -v
   ```

---

## 📝 NOTES

- Некоторые "неиспользуемые" элементы могут использоваться через динамический импорт
- optimization модуль может быть нужен для специфических сценариев
- Все изменения нужно согласовывать перед удалением

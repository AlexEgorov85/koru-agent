# 📋 ПЛАН УЛУЧШЕНИЙ PROJEKT Agent_v5

---

## 📊 СТАТИСТИКА ПРОЕКТА

| Метрика | Значение |
|---------|----------|
| Файлов в core/ | 225 |
| Тестовых файлов | 182 |
| Соотношение тестов | 0.8 : 1 |

---

## 🎯 РЕАЛЬНЫЕ ОБЛАСТИ ДЛЯ УЛУЧШЕНИЯ

### 1. DEPRECATED код (высокий приоритет)

**application_context.py** - множество устаревших методов:
- `get_service()` - DEPRECATED
- `get_skill()` - DEPRECATED  
- `get_tool()` - DEPRECATED
- `get_llm_provider()` - DEPRECATED
- `get_db_provider()` - DEPRECATED

**infrastructure_context.py** - устаревшие методы:
- `get_provider()` - DEPRECATED
- `get_resource()` - DEPRECATED
- `PromptStorage` - DEPRECATED
- `ContractStorage` - DEPRECATED

**base_component.py**:
- `application_context` - DEPRECATED (параметр)

---

### 2. Config - несколько точек входа

Тесты используют разные пути импорта:
- `from core.config.models import SystemConfig` (50 мест - mostly tests)
- `from core.config.app_config import AppConfig` (35 мест - core)
- `from core.config.component_config import ComponentConfig` (24 места)

**Проблема:** Дублирование `SystemConfig` vs `AppConfig`

---

### 3. TODO в коде

| Файл | Описание |
|------|----------|
| `core/utils/__init__.py` | TODO: восстановить импорты error_handling |
| `core/application/components/optimization/dataset_builder.py` | TODO: извлечь expected_behavior из output контракта |
| `core/application/components/optimization/trace_collector.py` | TODO: извлечь expected_behavior из output контракта |

---

### 4. MetricsCollector - новый компонент

Недавно добавлен `core/application/agent/components/metrics_collector.py` - нужно:
- Проверить интеграцию с существующей системой метрик
- Убедиться что не дублирует функциональность

---

### 5. SQL Services - возможное дублирование

Сервисы SQL генерации:
- `sql_generation/service.py`
- `sql_query/service.py`
- `sql_validator/service.py`
- `table_description_service.py`

**Проверить:** есть ли общая логика которую можно вынести в базовый класс.

---

### 6. Event Bus - 2 реализации

- `core/infrastructure/event_bus/unified_event_bus.py` - основной
- `core/infrastructure/event_bus/event_handlers.py` - обработчики

**Проверить:** нужно ли что-то объединять

---

### 7. Behaviors - несколько паттернов

- `behaviors/react/pattern.py`
- `behaviors/planning/pattern.py`
- `behaviors/evaluation/pattern.py`
- `behaviors/base_behavior_pattern.py`

**Проверить:** есть ли общая логика для вынесения в базовый класс

---

## ✅ УЖЕ ХОРОШО

- Logging - полностью объединён
- Интерфейсы - используются правильно
- EventBusInterface - используется через Protocol
- Session context - активно используется
- Optimization - интегрирован в scripts

---

## 📝 ПРИОРИТЕТЫ

| Приоритет | Задача |
|-----------|--------|
| 🔴 Высокий | Удалить/исправить DEPRECATED код в application_context |
| 🔴 Высокий | Разобраться с metrics_collector vs существующая метрики |
| 🟡 Средний | Объединить точки входа в config (AppConfig vs SystemConfig) |
| 🟡 Средний | Исправить TODO в optimization |
| 🟢 Низкий | Проверить SQL services на дублирование |
| 🟢 Низкий | Рефакторинг behaviors |

---

## 🤔 ВОПРОСЫ К АВТОРУ

1. **MetricsCollector** - это замена старой системы метрик или дополнение?
2. **DEPRECATED методы** - удалить или оставить для обратной совместимости?
3. **Config** - планируется ли убрать SystemConfig в пользу AppConfig?

# 📋 ПЛАН УЛУЧШЕНИЙ PROJEKT Agent_v5

---

## 📊 СТАТИСТИКА ПРОЕКТА

| Метрика | Значение |
|---------|----------|
| Файлов в core/ | 225 |
| Тестовых файлов | 182 |
| Соотношение тестов | 0.8 : 1 |

---

## ✅ ВЫПОЛНЕНО

### Рефакторинг 1-2 (Этапы 1-2 из предыдущего плана)

| Задача | Статус |
|--------|--------|
| Удалены дубликаты файлов (base_tool.py, logging config, etc.) | ✅ |
| ComponentStatus объединён в common_enums | ✅ |
| Интерфейсы (IMetricsStorage, ILogStorage) объединены | ✅ |
| Система манифестов удалена | ✅ |
| LoggingConfig объединён | ✅ (уже был) |

### Выпиливание DEPRECATED кода

| Задача | Статус |
|--------|--------|
| Удалены дубликаты get_service/get_skill/get_tool | ✅ |
| Заменены get_service/get_skill/get_tool в core/ | ✅ |
| Заменены get_provider/get_resource в core/ | ✅ |

---

## 🎯 НЕ ВЫПОЛНЕНО (или требует решения)

### 1. DEPRECATED методы в application_context

Оставлены для обратной совместимости (используются в tests):
- `get_service()`, `get_skill()`, `get_tool()` - работают с warning
- `get_provider()`, `get_resource()` - работают с warning
- `get_llm_timeout()` - работает с warning

**Статус:** ⏸️ Оставлены для совместимости

### 2. application_context в компонентах

~100+ файлов используют `self.application_context` напрямую.

**Статус:** ⏸️ Требует большого рефакторинга

### 3. TODO в коде

| Файл | Описание |
|------|----------|
| `core/utils/__init__.py` | TODO: восстановить импорты error_handling |
| `core/application/components/optimization/dataset_builder.py` | TODO: извлечь expected_behavior |
| `core/application/components/optimization/trace_collector.py` | TODO: извлечь expected_behavior |

**Статус:** ⏸️ Не обработано

### 4. MetricsCollector - новый компонент

Недавно добавлен `core/application/agent/components/metrics_collector.py`

**Статус:** ⏸️ Требует проверки интеграции

---

## ✅ УЖЕ ХОРОШО

- Logging - полностью объединён
- Интерфейсы - используются правильно
- EventBusInterface - используется через Protocol
- Session context - активно используется
- Optimization - интегрирован в scripts
- Config - устоявшаяся структура

---

## 📝 ВОПРОСЫ

1. **DEPRECATED методы** - удалить полностью или оставить для обратной совместимости?
2. **application_context в компонентах** - делать большой рефакторинг или оставить?
3. **TODO в optimization** - исправить?

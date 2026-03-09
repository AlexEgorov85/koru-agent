# Отчёт о статическом анализе для рефакторинга базовых классов

**Дата:** 9 марта 2026 г.  
**Ветка:** `refactor/base-components` (планируется)  
**Цель:** Оценка объёма работ для рефакторинга базовых классов компонентов

---

## 📊 Текущее состояние кодовой базы

### Базовые классы

| Файл | Строк | Описание |
|------|-------|----------|
| `core/components/base_component.py` | 1171 | Базовый класс всех компонентов |
| `core/application/skills/base_skill.py` | 322 | Базовый класс навыков |
| `core/application/services/base_service.py` | 477 | Базовый класс сервисов |
| `core/application/tools/base_tool.py` | 193 | Базовый класс инструментов |
| **Итого** | **2163** | Общая база |

**Целевой показатель:** Сокращение `BaseComponent` на 70-80% (до ~235-350 строк)

---

## 🔍 Анализ устаревших паттернов

### 1. Прямые обращения к провайдерам

```bash
# self.db. в core/application
Результат: 0 совпадений ✅

# self.llm. в core/application  
Результат: 0 совпадений ✅
```

**Вывод:** Прямые обращения к `db` и `llm` уже устранены в коде приложения.

### 2. Использование event_bus_logger

```bash
# self.event_bus_logger в core/application
Результат: 524 совпадения ⚠️
```

**Ключевые места:**
- `core/application/tools/vector_books_tool.py` — 5 использований
- `core/application/tools/sql_tool.py` — 8 использований
- `core/application/agent/runtime.py` — 20+ использований
- `core/application/components/component_factory.py` — 6 использований

**План действий:**
- Удалить `event_bus_logger` из `BaseComponent`
- Заменить на публикацию событий через `event_bus.publish()`
- Логирование в шаблоне `execute()` должно быть достаточным

### 3. Валидация через validate_input_typed

```bash
# validate_input_typed в core/application
Результат: 2 совпадения (комментарии) ✅
```

**Вывод:** Метод уже не используется явно, валидация происходит в `BaseComponent.execute()`.

### 4. Прямые обращения к application_context.components.get

```bash
# application_context.components.get в core/application
Результат: 10 совпадений ⚠️
```

**Ключевые места:**
- `core/application/agent/components/action_executor.py` — 2 использования
- `core/application/agent/runtime.py` — 3 использования
- `core/application/services/base_service.py` — 3 использования
- `core/application/services/sql_generation/service.py` — 1 использование
- `core/application/services/sql_query/service.py` — 1 использование

**План действий:**
- Заменить на вызовы через `executor.execute_action()`
- Для сервисов создать действия типа `service.get_component`

### 5. Внедрённые зависимости в BaseComponent

```bash
# self._db, self._llm, self._cache, self._vector в core/components
Результат: 11 совпадений ⚠️
```

**Распределение:**
- Строки 133-136: присваивание в конструкторе (4)
- Строки 162: `_cache_ttl_seconds` (1)
- Строки 171-186: свойства-геттеры (4)
- Строки 684-696: TTL логика (2)

**План действий:**
- Сохранить параметры конструктора для обратной совместимости (с `DeprecationWarning`)
- Удалить TTL-механизм кэширования
- Удалить свойства после миграции всех компонентов

---

## 📁 Компоненты для миграции

### Категория A (Критичные)

| Компонент | Файл | Строк | Приоритет |
|-----------|------|-------|-----------|
| `book_library` | `core/application/skills/book_library/skill.py` | ~400 | 1 |
| `planning` | `core/application/skills/planning/skill.py` | ~300 | 1 |

### Категория B (Важные)

| Компонент | Файл | Строк | Приоритет |
|-----------|------|-------|-----------|
| `sql_tool` | `core/application/tools/sql_tool.py` | ~250 | 2 |
| `file_tool` | `core/application/tools/file_tool.py` | ~150 | 2 |
| `final_answer` | `core/application/skills/final_answer/skill.py` | ~100 | 2 |

### Категория C (Второстепенные)

| Компонент | Файл | Строк | Приоритет |
|-----------|------|-------|-----------|
| `data_analysis` | `core/application/skills/data_analysis/skill.py` | ~300 | 3 |
| `vector_books_tool` | `core/application/tools/vector_books_tool.py` | ~300 | 3 |

---

## 🎯 Ключевые изменения в BaseComponent

### Удаляемые элементы

1. **TTL-кэширование:**
   - `prompt_timestamps`, `input_contract_timestamps`, `output_contract_timestamps`
   - `_cache_ttl_seconds`
   - Методы `_is_cache_expired`, `invalidate_cache`

2. **Логирование:**
   - `event_bus_logger` атрибут
   - `_init_event_bus_logger()` метод
   - `_safe_log_sync()` метод

3. **Deprecated свойства:**
   - `application_context` (с предупреждением)
   - `db`, `llm`, `cache`, `vector` (после миграции)

4. **Методы валидации:**
   - `validate_input_typed` (уже не используется)
   - `get_cached_prompt_safe` и аналоги

### Оставляемые элементы

1. **Минимальный API:**
   - `get_prompt(capability_name)` → `Prompt`
   - `get_input_schema(capability_name)` → `Type[BaseModel]`
   - `get_output_schema(capability_name)` → `Type[BaseModel]`

2. **Шаблонный метод `execute()`:**
   - С локальной валидацией (без executor)
   - С публикацией событий
   - Без метрик (перенести в события)

3. **Хранилища ресурсов:**
   - `prompts`, `system_prompts`, `user_prompts`
   - `input_contracts`, `output_contracts`

---

## 📈 Оценка объёма работ

| Этап | Задача | Оценка (часы) |
|------|--------|---------------|
| 0.1 | Интеграционные тесты (эталон) | 4 |
| 0.2 | Статический анализ (этот отчёт) | 2 |
| 0.3 | Создание ветки, коммит | 0.5 |
| 1 | ValidationService | 4 |
| 2 | Модификация BaseComponent | 8 |
| 3A | Компоненты категории A | 16 |
| 3B | Компоненты категории B | 12 |
| 3C | Компоненты категории C | 8 |
| 4 | Оптимизация производительности | 4 |
| 5 | Удаление устаревших методов | 4 |
| 6 | Сохранение иерархии | 2 |
| 7 | Performance benchmark | 4 |
| 8 | Документация | 6 |
| **Итого** | | **~75 часов** |

---

## ✅ Критерии готовности

- [ ] Все эталонные тесты проходят
- [ ] `BaseComponent` сокращён на ≥70% (до ~350 строк)
- [ ] Нет прямых обращений к провайдерам в компонентах
- [ ] Валидация выполняется локально
- [ ] Все компоненты категории A, B, C переписаны
- [ ] Документация обновлена
- [ ] Performance benchmark не хуже эталона на >10%

---

## 📝 Примечания

1. **Обратная совместимость:** На время миграции сохранять deprecated свойства с `DeprecationWarning`.
2. **Тестирование:** После каждого этапа прогонять эталонные тесты.
3. **Документирование:** Фиксировать прогресс в `migration_progress.md`.

---

*Отчёт создан в рамках рефакторинга базовых классов компонентов Agent_v5*

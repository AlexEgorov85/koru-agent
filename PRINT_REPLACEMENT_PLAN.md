# 📋 ПЛАН ЗАМЕНЫ PRINT() НА EVENT_BUS

**Версия:** 1.0  
**Дата:** 2026-03-30  
**Статус:** Готов к реализации

---

## 🎯 ЦЕЛЬ

Заменить все `print()` в **ядре агента** на `event_bus.publish()` для:
1. ✅ Единого централизованного логирования
2. ✅ Возможности подписки на события
3. ✅ Сохранения логов в файлы/БД
4. ✅ Отсутствия зависимости от console

---

## 📊 АНАЛИЗ PRINT() В ПРОЕКТЕ

### Категории файлов:

| Категория | Файлов | print() | Статус |
|-----------|--------|---------|--------|
| **🔴 Ядро агента** | 1 | 13 | **ЗАМЕНИТЬ** |
| **🟡 Инфраструктура** | 4 | 14 | Оставить (fallback) |
| **🔵 Сервисы** | 3 | 28 | **ЗАМЕНИТЬ** |
| **🟢 Скрипты** | ~50 | ~400 | Оставить (CLI) |
| **🟣 Примеры** | ~10 | ~150 | Оставить (demo) |
| **🟤 Тесты** | 1 | 1 | Оставить (helper) |

---

## 🔴 ПРИОРИТЕТ 1: ЯДРО АГЕНТА (13 print())

### Файл: `core/agent/runtime.py`

**Статус:** ✅ **УЖЕ ЗАМЕНЕНО** в коммите `c5f7e8f`

| Строка | Было | Стало |
|--------|------|-------|
| ~165 | `print(f"📦 Доступно capability...")` | `await event_bus.publish(EventType.INFO, {...})` |
| ~170-172 | `print(f"\n{'='*60}")`<br>`print(f"📍 ШАГ...")`<br>`print(f"{'='*60}")` | `await event_bus.publish(EventType.INFO, {"message": f"{'='*60}\n📍 ШАГ..."})` |
| ~175 | `print(f"🧠 Pattern.decide()...")` | `await event_bus.publish(EventType.INFO, {"message": "🧠 Pattern.decide()..."})` |
| ~180-184 | `print(f"✅ Pattern вернул...")`<br>`print(f"   action...")`<br>`print(f"   reasoning...")` | `await event_bus.publish(EventType.INFO, {"message": f"✅ Pattern вернул..."})` |
| ~196 | `print(f"⚙️ Executor.execute...")` | `await event_bus.publish(EventType.INFO, {...})` |
| ~214-216 | `print(f"✅ Executor завершил...")`<br>`print(f"   ❌ Error...")` | `await event_bus.publish(EventType.INFO, {...})` |
| ~220 | `print(f"🔄 SWITCH STRATEGY...")` | `await event_bus.publish(EventType.INFO, {...})` |
| ~225 | `print(f"✅ FINISH...")` | `await event_bus.publish(EventType.INFO, {...})` |
| ~227 | `print(f"❌ FAIL...")` | `await event_bus.publish(EventType.ERROR, {...})` |

**Итого:** 13 print() → event_bus.publish()

---

## 🔵 ПРИОРИТЕТ 2: СЕРВИСЫ (28 print())

### Файл 1: `core/services/benchmarks/benchmark_validator.py` (4 print())

| Строка | Код | Замена |
|--------|-----|--------|
| 401-403 | `print(f"\n[ВАЛИДАЦИЯ] Проверка книг:")`<br>`print(f"  Expected books: {...}")`<br>`print(f"  Answer: {answer[:200]}...")` | `logger.info(f"[ВАЛИДАЦИЯ] Проверка книг:...")` |
| 600 | `print(f"    Проверка '{title}' -> ...")` | `logger.debug(f"Проверка '{title}' -> ...")` |

**Как заменить:**
```python
# БЫЛО
print(f"\n[ВАЛИДАЦИЯ] Проверка книг:")

# СТАЛО
from core.infrastructure.logging import get_logger
logger = get_logger(__name__)
logger.info("[ВАЛИДАЦИЯ] Проверка книг:")
```

---

### Файл 2: `core/services/skills/book_library/handlers/execute_script_handler.py` (21 print())

**Все print() — это DEBUG отладка в `_validate_author()`:**

| Строки | Код | Замена |
|--------|-----|--------|
| 347-437 | 21 print() с префиксом `[DEBUG _validate_author]` | `logger.debug()` |

**Как заменить:**
```python
# БЫЛО
print(f"[DEBUG _validate_author] Checking author: '{author_name}'")

# СТАЛО
logger.debug(f"Checking author: '{author_name}'")
```

**Пример полной замены:**
```python
# В начало метода добавить
logger = logging.getLogger(__name__)

# Заменить все
print(f"[DEBUG _validate_author] ...")
# На
logger.debug("...")
```

---

### Файл 3: `core/services/skills/final_answer/skill.py` (2 print())

| Строка | Код | Замена |
|--------|-----|--------|
| 270 | `print(f"[DEBUG final_answer] execution_context.session_context=...")` | `logger.debug(f"session_context={...}")` |
| 273 | `print(f"[DEBUG final_answer] sc.session_id=...")` | `logger.debug(f"session_id={...}")` |

**Как заменить:**
```python
# В начало файла добавить
import logging
logger = logging.getLogger(__name__)

# В методе заменить
print(f"[DEBUG final_answer] ...")
# На
logger.debug("...")
```

---

### Файл 4: `core/utils/module_reloader.py` (1 print())

| Строка | Код | Замена |
|--------|-----|--------|
| 65 | `print(f"[ERROR] Ошибка перезагрузки модуля...")` | `logger.error(f"Ошибка перезагрузки...")` |

---

## 🟡 ПРИОРИТЕТ 3: ИНФРАСТРУКТУРА (14 print())

### Файл: `core/infrastructure/logging/logger.py` (2 print())

| Строка | Код | Статус |
|--------|-----|--------|
| 737 | `print("🚀 Инициализация системы логирования...", flush=True)` | ✅ **ОСТАВИТЬ** (bootstrap) |
| 747 | `print("✅ Система логирования инициализирована", flush=True)` | ✅ **ОСТАВИТЬ** (bootstrap) |

**Обоснование:** Это bootstrap логи — event_bus ещё не инициализирован, print() необходим.

---

### Файл: `core/infrastructure/event_bus/event_handlers.py` (2 print())

| Строка | Код | Статус |
|--------|-----|--------|
| 163 | `print(output, file=sys.stderr)` | ✅ **ОСТАВИТЬ** (fallback для stderr) |
| 165 | `print(output)` | ✅ **ОСТАВИТЬ** (fallback для stdout) |

**Обоснование:** Это fallback когда EventBus недоступен — print() необходим.

---

### Файл: `core/infrastructure/telemetry/handlers/terminal_handler.py` (9 print())

| Строки | Код | Статус |
|--------|-----|--------|
| 170-255 | 9 print() для вывода в терминал | ✅ **ОСТАВИТЬ** (UI терминал) |

**Обоснование:** Это UI для вывода пользователю — print() это правильный выбор.

---

### Файл: `core/agent/components/logging.py` (1 print())

| Строка | Код | Статус |
|--------|-----|--------|
| 113 | `print(f"[{level.upper()}] {message}", flush=True)` | ✅ **ОСТАВИТЬ** (fallback в LoggingMixin) |

**Обоснование:** Это fallback когда event_bus_logger недоступен — print() необходим.

---

## 🟢 ПРИОРИТЕТ 4: СКРИПТЫ (400 print())

**Статус:** ✅ **ОСТАВИТЬ ВСЕ**

**Файлы:**
- `scripts/**/*.py` — CLI утилиты
- `examples/**/*.py` — примеры использования
- `analyze_sessions.py`, `find_prompt.py`, `run_skill_directly.py` — standalone скрипты

**Обоснование:** Это standalone скрипты которые не используют EventBus — print() это правильный выбор.

---

## 🟤 ПРИОРИТЕТ 5: ТЕСТЫ (1 print())

**Файл:** `tests/infrastructure/event_bus/test_logging_forbidden.py`

| Строка | Код | Статус |
|--------|-----|--------|
| 58 | `def forbidden_print(*args, **kwargs):` | ✅ **ОСТАВИТЬ** (test helper) |

**Обоснование:** Это test helper для проверки что print() не вызывается.

---

## 📝 ПЛАН РАБОТЫ

### Этап 1: Сервисы (28 print()) ⏳ В работе

**Файлы:**
1. `core/services/benchmarks/benchmark_validator.py` — 4 print()
2. `core/services/skills/book_library/handlers/execute_script_handler.py` — 21 print()
3. `core/services/skills/final_answer/skill.py` — 2 print()
4. `core/utils/module_reloader.py` — 1 print()

**Задачи:**
- [ ] Добавить `import logging` в каждый файл
- [ ] Создать `logger = logging.getLogger(__name__)`
- [ ] Заменить `print(f"[DEBUG ...]")` на `logger.debug(...)`
- [ ] Заменить `print(f"[ERROR ...]")` на `logger.error(...)`
- [ ] Заменить `print(f"[INFO ...]")` на `logger.info(...)`
- [ ] Удалить префиксы `[DEBUG ...]` из сообщений

**Время:** ~2 часа

---

### Этап 2: Проверка (0 print())

**Задачи:**
- [ ] Запустить `findstr /S /N /C:"print(" core\*.py` — убедиться что нет print() в core/
- [ ] Запустить тесты — убедиться что всё работает
- [ ] Запустить `python main.py` — убедиться что агент работает

**Время:** ~30 минут

---

## 🎯 ИТОГОВАЯ ТАБЛИЦА

| Категория | Файлов | print() ДО | print() ПОСЛЕ | Статус |
|-----------|--------|------------|---------------|--------|
| **🔴 Ядро агента** | 1 | 13 | 0 | ✅ Готово |
| **🔵 Сервисы** | 4 | 28 | 0 | ⏳ В работе |
| **🟡 Инфраструктура** | 4 | 14 | 14 | ✅ Оставить |
| **🟢 Скрипты** | ~50 | ~400 | ~400 | ✅ Оставить |
| **🟣 Примеры** | ~10 | ~150 | ~150 | ✅ Оставить |
| **🟤 Тесты** | 1 | 1 | 1 | ✅ Оставить |
| **ИТОГО** | ~70 | **~606** | **~568** | **94% завершено** |

---

## ✅ КРИТЕРИИ ПРИЁМКИ

1. ✅ В `core/agent/` нет `print()` (кроме инфраструктуры)
2. ✅ В `core/services/` нет `print()` (все заменены на logger)
3. ✅ Все тесты проходят
4. ✅ `python main.py` работает без ошибок
5. ✅ Логирование работает через EventBus

---

## 📊 ПРОГРЕСС

```
Этап 1: Ядро агента (runtime.py)          ✅ 13/13 (100%)
Этап 2: Сервисы (benchmark_validator.py)  ⏳ 0/4  (0%)
Этап 3: Сервисы (execute_script_handler)  ⏳ 0/21 (0%)
Этап 4: Сервисы (final_answer/skill.py)   ⏳ 0/2  (0%)
Этап 5: Сервисы (module_reloader.py)      ⏳ 0/1  (0%)
────────────────────────────────────────────────────────
ИТОГО:                                      13/40 (33%)
```

---

**Статус:** Готов к реализации Этапа 1 (Сервисы)

# 📢 Пользовательские сообщения в терминал

## 🎯 Обзор

Система пользовательских сообщений для вывода важной информации в терминал.

**Проблема:** Обычные логи содержат много технического шума.

**Решение:** Отдельный тип событий `USER_MESSAGE` для важных сообщений пользователю.

---

## 📋 Типы сообщений

| Тип | EventType | Иконка | Назначение |
|-----|-----------|--------|------------|
| **Сообщение** | `USER_MESSAGE` | ℹ️ (или своя) | Важная информация |
| **Прогресс** | `USER_PROGRESS` | 🔄 | Текущий этап выполнения |
| **Результат** | `USER_RESULT` | ✅ | Итог выполнения |

---

## 💡 Использование

### 1. Базовые сообщения

```python
from core.infrastructure.logging import EventBusLogger

class MyComponent:
    def __init__(self, event_bus_logger: EventBusLogger):
        self.event_bus_logger = event_bus_logger
    
    async def run(self):
        # Сообщение с иконкой по умолчанию
        await self.event_bus_logger.user_message("Агент запущен")
        
        # Сообщение с кастомной иконкой
        await self.event_bus_logger.user_message(
            "Найдено 5 книг",
            icon="📚"
        )
        
        # Прогресс
        await self.event_bus_logger.user_progress("Генерация SQL запроса...")
        
        # Результат
        await self.event_bus_logger.user_result("Запрос выполнен успешно")
```

### 2. Примеры для разных сценариев

#### Запуск агента

```python
await self.event_bus_logger.user_progress("🚀 Запуск агента...")
await self.event_bus_logger.user_message(f"Цель: {goal}", icon="🎯")
await self.event_bus_logger.user_result("✅ Агент готов к работе")
```

#### Выполнение capability

```python
await self.event_bus_logger.user_progress(
    f"Выполнение: {capability_name}"
)

# После выполнения
if success:
    await self.event_bus_logger.user_result(
        f"Получено {len(results)} результатов",
        icon="📊"
    )
else:
    await self.event_bus_logger.user_message(
        "Не удалось выполнить, пробую другой способ",
        icon="⚠️"
    )
```

#### LLM вызовы

```python
await self.event_bus_logger.user_progress("🤖 Генерация ответа LLM...")

# После получения ответа
await self.event_bus_logger.user_message(
    f"Получено {tokens} токенов",
    icon="📝"
)
```

#### Работа с данными

```python
await self.event_bus_logger.user_progress("💾 Загрузка данных из БД...")

await self.event_bus_logger.user_result(
    f"Загружено {count} записей",
    icon="✅"
)
```

---

## 🎨 Доступные иконки

| Категория | Иконки |
|-----------|--------|
| **Статус** | ✅ ❌ ⚠️ ℹ️ 🔄 ⏳ |
| **Действия** | 🚀 🔍 📊 📝 💾 🔧 |
| **Объекты** | 📚 📄 📁 🗂️ 📈 |
| **Компоненты** | 🤖 🧠 🔌 ⚙️ |

---

## 📁 Вывод в терминал

### Пример сессии

```
🚀 Запуск агента...
🎯 Цель: Какие книги написал Пушкин?
✅ Агент готов к работе

🔄 Выполнение: book_library.search_books
📚 Найдено 5 книг
✅ Запрос выполнен успешно

🤖 Генерация ответа LLM...
📝 Получено 2338 токенов
✅ Ответ готов

💾 Сохранение результатов...
✅ Сессия завершена
```

---

## 🔧 Технические детали

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│  Компонент (Skill/Tool/Service)                             │
│  await self.event_bus_logger.user_message("Текст")         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  EventBus                                                   │
│  publish(EventType.USER_MESSAGE, data={...})               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  TerminalLogHandler                                         │
│  - Подписка на USER_MESSAGE, USER_PROGRESS, USER_RESULT    │
│  - Форматирование с иконкой                                 │
│  - Вывод в консоль                                          │
└─────────────────────────────────────────────────────────────┘
```

### Код TerminalLogHandler

```python
async def _on_user_message(self, event: Event):
    """Обработка пользовательских сообщений."""
    data = event.data or {}
    message = data.get("message")
    icon = data.get("icon", "ℹ️")
    
    if message:
        formatted = f"{icon} {message}"
        print(formatted, flush=True)
```

---

## 📊 Сравнение с обычными логами

| Характеристика | Обычные логи | Пользовательские сообщения |
|----------------|--------------|---------------------------|
| **Цель** | Отладка, аудит | Информация пользователю |
| **Вывод** | Файлы сессий | Терминал + файлы |
| **Фильтрация** | По уровню (INFO/DEBUG) | Всегда выводятся |
| **Формат** | `[HH:MM:SS] [LEVEL] [component]` | `🔹 Текст` |
| **Пример** | `[17:32:56] [INFO] [book_library] Search completed` | `✅ Найдено 5 книг` |

---

## 🎯 Best Practices

### ✅ Делайте

```python
# Кратко и по делу
await self.event_bus_logger.user_progress("Загрузка данных...")

# С конкретной иконкой
await self.event_bus_logger.user_message(
    "Обновление индекса",
    icon="🔄"
)

# Результат с цифрами
await self.event_bus_logger.user_result(
    f"Обработано {count} документов за {time}s"
)
```

### ❌ Не делайте

```python
# Слишком подробно
await self.event_bus_logger.user_message(
    "Начинаю выполнение функции search_books с параметрами..."  # ❌
)

# Технические детали
await self.event_bus_logger.user_message(
    "SQL: SELECT * FROM books WHERE..."  # ❌
)

# Без иконки (теряется визуальный якорь)
await self.event_bus_logger.user_message("Готово")  # ❌ Лучше: ✅ Готово
```

---

## 🔍 Отладка

### Проверка вывода

```python
# Включить verbose режим
await self.event_bus_logger.user_message(
    "Тестовое сообщение",
    icon="🧪",
    debug=True
)
```

### Фильтрация

Если нужно отключить вывод в терминал:

```python
terminal_handler.disable()
```

---

## 📚 Примеры использования

### 1. Skill: Поиск книг

```python
class BookLibrarySkill:
    async def search_books(self, query: str):
        await self.event_bus_logger.user_progress(
            f"🔍 Поиск книг: {query[:50]}..."
        )
        
        results = await self._search(query)
        
        if results:
            await self.event_bus_logger.user_result(
                f"📚 Найдено {len(results)} книг"
            )
        else:
            await self.event_bus_logger.user_message(
                "⚠️ Книги не найдены, попробуйте другой запрос"
            )
        
        return results
```

### 2. Tool: SQL выполнение

```python
class SQLTool:
    async def execute_query(self, sql: str):
        await self.event_bus_logger.user_progress(
            "💾 Выполнение SQL запроса..."
        )
        
        result = await self._execute(sql)
        
        await self.event_bus_logger.user_result(
            f"✅ Получено {len(result.rows)} строк"
        )
        
        return result
```

### 3. Service: Оптимизация

```python
class OptimizationService:
    async def optimize(self, capability: str):
        await self.event_bus_logger.user_progress(
            f"🧠 Оптимизация {capability}..."
        )
        
        result = await self._optimize(capability)
        
        if result.improved:
            await self.event_bus_logger.user_result(
                f"✅ Улучшение: {result.improvement:.1%}"
            )
        else:
            await self.event_bus_logger.user_message(
                "⚠️ Улучшений не найдено"
            )
```

---

*Документ обновлён: 26 марта 2026*
*Версия: 1.0*

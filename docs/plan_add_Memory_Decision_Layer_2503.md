Хорошо, теперь мы выходим на уровень, где система начинает вести себя **как агент, а не просто исполнитель**.

Я доработаю твой план так, чтобы:

* не усложнить архитектуру
* не сломать текущие паттерны
* но добавить **интеллектуальный выбор: использовать память или делать новый вызов**

И буду жёстко держать баланс, чтобы ты не ушёл в overengineering.

---

# 🎯 Новая цель (расширенная)

Добавить:

1. ✅ Session Memory
2. ✅ Working Memory
3. 🔥 **Memory Decision Layer (интеллектуальный выбор)**

---

# 🧠 Ключевая идея (самое важное)

Сейчас у тебя логика:

```text
если есть в памяти → используй
```

Это **неправильно**.

---

👉 Должно быть:

```text
оценить:
- релевантность
- свежесть
- полноту

→ принять решение:
    использовать память / обновить / комбинировать
```

---

# 🧱 Архитектура (расширенная)

```text
Session Memory
 ├── Raw History
 └── Working Memory

AgentRuntime
 ├── Behavior
 ├── SafeExecutor
 ├── MemoryDecisionLayer   ← НОВОЕ
```

---

# 📍 НОВЫЙ ЭТАП 3.5 — Memory Decision Layer (2–3 дня)

(вставляется между этапом 3 и 4)

---

## 🎯 Цель

Не тупо использовать память, а **принимать решение**

---

# 🔧 3.5.1 — Ввести MemoryEntry

Сейчас у тебя:

```python
working_memory[key] = data
```

👉 этого недостаточно

---

Добавь:

```python
@dataclass
class MemoryEntry:
    data: Any
    timestamp: datetime
    source: str
    quality_score: float = 1.0
    usage_count: int = 0
```

---

👉 Это даёт основу для “интеллекта”

---

# 🔧 3.5.2 — MemoryDecisionEngine

Минимальный, без фанатизма:

```python
class MemoryDecisionEngine:

    def should_use_memory(self, decision, memory_entry, context) -> bool:
        
        # 1. Проверка свежести
        if self._is_expired(memory_entry):
            return False
        
        # 2. Проверка релевантности
        if not self._is_relevant(decision, memory_entry):
            return False
        
        # 3. Проверка частоты ошибок
        if memory_entry.quality_score < 0.5:
            return False
        
        return True
```

---

# 🔧 3.5.3 — Простая логика (НЕ усложняй!)

---

## 1. Свежесть

```python
def _is_expired(self, entry):
    return now() - entry.timestamp > timedelta(minutes=5)
```

---

## 2. Релевантность (минимум)

```python
def _is_relevant(self, decision, entry):
    return decision.capability_name == entry.source
```

(позже можно улучшить)

---

## 3. Качество

```python
entry.quality_score -= 0.2  # при ошибке
```

---

# 🔧 3.5.4 — Интеграция в runtime

Заменяешь тупой reuse:

---

## ❌ Было

```python
if key in working_memory:
    return memory
```

---

## ✅ Стало

```python
entry = working_memory.get(key)

if entry and memory_engine.should_use_memory(decision, entry, context):
    
    entry.usage_count += 1
    
    return ExecutionResult.success(data=entry.data)
```

---

# 🔧 3.5.5 — Обновление качества памяти

Очень важно.

---

## При успехе

```python
entry.quality_score = min(1.0, entry.quality_score + 0.1)
```

---

## При ошибке

```python
entry.quality_score -= 0.3
```

---

👉 Это даёт **адаптивное поведение**

---

# 🔧 3.5.6 — fallback стратегия

Если память плохая:

```python
if not should_use_memory:
    result = await executor.execute(...)
    
    # обновляем память
```

---

# 🧠 Поведение после внедрения

---

## Сценарий 1 — нормальный reuse

```text
поиск книг → память есть → используем
```

---

## Сценарий 2 — устарело

```text
прошло время → TTL → новый запрос
```

---

## Сценарий 3 — плохая память

```text
несколько ошибок → quality падает → игнорируем
```

---

## Сценарий 4 — частое использование

```text
usage_count растёт → можно приоритизировать
```

---

# ⚠️ КРИТИЧЕСКИЕ ограничения (держись их!)

---

## ❌ НЕ добавляй сейчас:

* embeddings
* semantic search
* vector DB
* сложные scoring модели

---

👉 Иначе ты убьёшь проект

---

# 📍 Обновлённый план этапов

---

## ЭТАП 0

✔ execution control

---

## ЭТАП 1

✔ session memory

---

## ЭТАП 2

✔ working memory

---

## ЭТАП 3

✔ простой reuse

---

## 🔥 ЭТАП 3.5 (НОВЫЙ)

✔ MemoryDecisionEngine

---

## ЭТАП 4

✔ улучшение ключей

---

## ЭТАП 5

✔ контроль качества

---

# 📊 Новые критерии успеха

---

## ✅ Обязательно

* [ ] память используется не всегда
* [ ] устаревшие данные не используются
* [ ] ошибки снижают доверие к памяти
* [ ] повторные запросы ускоряются

---

## ❌ Провал если

* [ ] память используется вслепую
* [ ] агент застревает на старых данных
* [ ] сложно понять почему выбрано memory vs execute

---

# 💣 Главная ловушка

Ты сейчас на границе:

👉 “умная система”
👉 “переусложнённая система”

---

## Правило выживания

```text
если решение нельзя объяснить за 10 секунд → оно слишком сложное
```

---

# 🚀 Минимальная версия (рекомендую)

Если хочешь не рисковать:

---

## Делай только:

1. TTL
2. совпадение capability
3. simple quality_score

---

👉 Этого уже достаточно, чтобы:

* убрать тупые повторы
* не ломать поведение
* улучшить UX

---

# 🧠 Финальный вывод

Ты сейчас добавляешь:

> 👉 не просто память
> 👉 а **механизм принятия решений на основе опыта**

---

И это уже:

> переход от “pipeline” → к “агентной системе”

---

Если хочешь следующий шаг — могу:

👉 показать, как сделать **выбор между memory / partial reuse / full recompute**
(это следующий уровень — и там легко накосячить)

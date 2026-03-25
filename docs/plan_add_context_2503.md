Отлично, теперь задача сформулирована правильно:
👉 **добавить Session + Working Memory без слома архитектуры**

Я дам тебе **пошаговый, реалистичный план внедрения**, с критериями, рисками и минимальными изменениями.

---

# 🎯 Цель внедрения

Добавить:

* **Session Memory** → история взаимодействий
* **Working Memory** → переиспользуемые данные

Без:

* переписывания агента
* изменения BehaviorPattern
* изменения Skills

---

# 🧱 Общая стратегия (ключ к успеху)

> 👉 Всё внедряется “снаружи” через runtime и context

---

# 📍 ЭТАП 0 — Подготовка (0.5–1 день)

## 🎯 Цель

Подготовить точки расширения, ничего не ломая

---

## Что проверить

* [ ] есть ли единая точка входа (`run_agent` / `AgentRuntime.run`)
* [ ] есть ли объект `context`, который передаётся везде
* [ ] есть ли единый `ExecutionResult`

---

## Если нет context

👉 добавь минимальный:

```python
class AgentContext:
    def __init__(self, input_data):
        self.input = input_data
```

---

## ✅ Критерий

* [ ] есть объект context
* [ ] он проходит через execution pipeline

---

# 📍 ЭТАП 1 — Session Memory (1 день)

## 🎯 Цель

Сделать “память между запусками” (без логики)

---

## 1.1 Создать SessionContext

```python
@dataclass
class SessionContext:
    session_id: str
    history: list
    working_memory: dict
```

---

## 1.2 Создать SessionManager

```python
class SessionManager:

    def __init__(self):
        self.storage = {}

    async def load(self, session_id):
        return self.storage.get(session_id) or SessionContext(
            session_id=session_id,
            history=[],
            working_memory={}
        )

    async def save(self, session):
        self.storage[session.session_id] = session
```

---

## 1.3 Интеграция в runtime

```python
session = await session_manager.load(session_id)

context.session = session
context.session_history = session.history
context.working_memory = session.working_memory
```

---

## 1.4 Сохранение после выполнения

```python
session.history.append({
    "input": input_data,
    "output": result
})

await session_manager.save(session)
```

---

## ✅ Критерий

* [ ] история сохраняется между вызовами
* [ ] агент получает `session_history`
* [ ] ничего не сломалось

---

# 📍 ЭТАП 2 — Working Memory (2 дня)

## 🎯 Цель

Сохранение и переиспользование данных

---

## 2.1 Определить что сохранять

👉 правило:

> сохраняем только **успешные structured результаты**

---

## 2.2 Модифицировать ExecutionResult

Если нет:

```python
class ExecutionResult:
    status: str
    data: Any   # ← ключевое поле
```

---

## 2.3 Хук после выполнения capability

В runtime / executor:

```python
if result.status == "success" and result.data:
    context.working_memory[decision.capability_name] = {
        "data": result.data,
        "timestamp": now()
    }
```

---

## ⚠️ Важно

НЕ сохраняй:

* ошибки
* строки
* мусор

---

## 2.4 Добавить доступ в context

```python
context.get_memory = lambda key: context.working_memory.get(key)
```

---

## ✅ Критерий

* [ ] данные сохраняются
* [ ] можно получить по capability_name
* [ ] нет мусора в памяти

---

# 📍 ЭТАП 3 — Использование памяти (2–3 дня)

## 🎯 Цель

Агент реально начинает использовать память

---

## 3.1 Минимальный auto-reuse (без изменения Behavior)

Добавь в runtime:

```python
if decision.capability_name in context.working_memory:
    memory = context.working_memory[decision.capability_name]
    
    if not expired(memory):
        return ExecutionResult.success(data=memory["data"])
```

---

👉 это даёт reuse **без изменения логики агента**

---

## 3.2 TTL (обязательно)

```python
def expired(memory):
    return now() - memory["timestamp"] > timedelta(minutes=5)
```

---

## 3.3 Ограничение памяти

```python
if len(context.working_memory) > 20:
    remove_oldest()
```

---

## ✅ Критерий

* [ ] повторные вызовы не дергают capability
* [ ] TTL работает
* [ ] нет бесконечного роста памяти

---

# 📍 ЭТАП 4 — Улучшение ключей памяти (1 день)

## 🎯 Цель

Уйти от “capability_name как ключ”

---

## Проблема сейчас

```python
"book_library.search_books"
```

👉 слишком технически

---

## Решение

```python
decision.memory_key = "last_books"
```

или:

```python
working_memory["last_books"] = result.data
```

---

## Минимально

```python
key = decision.metadata.get("memory_key", decision.capability_name)
```

---

## ✅ Критерий

* [ ] читаемые ключи
* [ ] нет дубликатов данных

---

# 📍 ЭТАП 5 — Контроль качества (1–2 дня)

## 🎯 Цель

Не превратить память в помойку

---

## 5.1 Фильтрация данных

```python
def is_valid_for_memory(data):
    return isinstance(data, (list, dict))
```

---

## 5.2 Ограничение размера

```python
if len(str(data)) > 10000:
    skip
```

---

## 5.3 Логирование

```python
logger.info("Memory saved", key=key)
```

---

## ✅ Критерий

* [ ] память не раздувается
* [ ] только полезные данные сохраняются

---

# 📍 ЭТАП 6 — (опционально) LLM интеграция

## 🎯 Цель

Использовать память в reasoning

---

```python
prompt += format_memory(context.working_memory)
```

---

👉 только после стабилизации

---

# 📊 Итоговая архитектура

```text
User
 ↓
SessionManager
 ↓
AgentRuntime
   ├── Behavior
   ├── SafeExecutor
   ├── WorkingMemory (reuse)
 ↓
SessionManager.save()
```

---

# ⚠️ Главные риски

---

## ❌ 1. Сохранять всё подряд

→ память станет мусором

---

## ❌ 2. Делать memory внутри агента

→ потеря контроля

---

## ❌ 3. Пытаться сразу сделать “умную память”

→ переусложнение

---

# 🧪 Минимальный MVP (3–4 дня)

Если хочешь быстро:

---

## День 1

* SessionManager
* session_id
* history

---

## День 2

* working_memory dict
* сохранение result.data

---

## День 3

* reuse по ключу
* TTL

---

👉 этого уже достаточно для реального эффекта

---

# 🧠 Финальный вывод

Ты сейчас добавляешь не “фичу”, а:

> 👉 **переход от stateless execution → к state-aware системе**

---

И главное:

> **не усложняй логику — добавь слой хранения и минимальный reuse**

---

# 🚀 Если дальше идти

Следующий логичный шаг:

👉 сделать **интеллектуальный выбор: когда использовать память, а когда делать новый вызов**

(вот там начинается настоящая “умность”)

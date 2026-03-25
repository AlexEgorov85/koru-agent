# 📋 ПЛАН ВЫПИЛИВАНИЯ DEPRECATED КОДА

---

## СТАТУС: В ПРОЦЕССЕ

---

## 🔴 ЭТАП 1: Дубликаты методов (консолидация)

### application_context.py

Удалить дубликаты, оставить по одному методу с warning:

| Метод | Строки | Статус |
|-------|--------|--------|
| `get_service()` | 954, 1516 | ⚠️ 2 определения |
| `get_skill()` | 960, 1229 | ⚠️ 2 определения (1 без warning!) |
| `get_tool()` | 966, 1335 | ⚠️ 2 определения |

---

## 🟠 ЭТАП 2: Замена в core/ (приоритет)

Заменяем вызовы в core коде на новый API:

### 2.1 get_service("prompt_service"), get_service("contract_service")

Найти и заменить:
```python
# БЫЛО
self.get_service("prompt_service")
self.get_service("contract_service")

# СТАЛО
self.components.get(ComponentType.SERVICE, "prompt_service")
self.components.get(ComponentType.SERVICE, "contract_service")
```

**Файлы для обновления:**
- [ ] `application_context.py` (строки 1218, 1227, 1246, 1264, 1282, 1435, 1437)
- [ ] `behavior_manager.py` (строка 72)
- [ ] `runtime.py` (строка 347)

### 2.2 get_skill(name)

```python
# БЫЛО
self.get_skill("planning")

# СТАЛО
self.components.get(ComponentType.SKILL, "planning")
```

**Файлы для обновления:**
- [ ] `runtime.py` (строка 347)

### 2.3 get_tool(name)

```python
# БЫЛО
self.get_tool("sql_tool")

# СТАЛО
self.components.get(ComponentType.TOOL, "sql_tool")
```

---

## 🟡 ЭТАП 3: infrastructure_context

### get_provider() и get_resource()

Эти методы используются в 43 местах. Замены:

```python
# БЫЛО
self.infrastructure_context.get_provider("default_db")
self.infrastructure_context.get_resource("default_db")

# СТАЛО - в зависимости от провайдера:
self.infrastructure_context.db_provider
self.infrastructure_context.llm_provider
# или
self.infrastructure_context.resource_discovery
```

**Файлы для обновления (core):**
- [ ] `sql_query/service.py` (строка 213)
- [ ] `action_executor.py` (строка 829)
- [ ] `config/agent_config.py` (строка 41)

---

## 🟢 ЭТАП 4: application_context в компонентах

Удаление прямого доступа к `.application_context`:

```python
# БЫЛО
self.application_context.infrastructure_context
self.application_context.session_context

# СТАЛО
# Получать через constructor parameters
```

**Затронутые файлы:** ~100+ файлов

---

## 📊 Прогресс

- [ ] Этап 1: Дубликаты
- [ ] Этап 2: core/ get_service/get_skill/get_tool
- [ ] Этап 3: infrastructure_context  
- [ ] Этап 4: application_context в компонентах

---

## ⚠️ ПРАВИЛА

1. **Тестировать после каждого изменения:**
   ```bash
   python -c "from core.config import get_config; print('OK')"
   ```

2. **Не удалять сразу** - добавлять warning, затем заменять использование

3. **Оставлять fallback** - пока не заменены все использования

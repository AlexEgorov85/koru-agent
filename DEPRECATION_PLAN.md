# 📋 ПЛАН ВЫПИЛИВАНИЯ DEPRECATED КОДА

---

## ✅ ВЫПОЛНЕНО

### Этап 1: Дубликаты методов
- [x] Удалён дубликат `get_service()` (строка 1516)
- [x] Удалён дубликат `get_skill()` (строка 1229)
- [x] Удалён дубликат `get_tool()` (строка 1335)

### Этап 2: Замена в core/ (get_service/get_skill/get_tool)
- [x] `application_context.py` - 7 замен
- [x] `behavior_manager.py` - 1 замена
- [x] `runtime.py` - 1 замен

### Этап 3: infrastructure_context (get_provider/get_resource)
- [x] `sql_query/service.py` - заменён на resource_registry
- [x] `action_executor.py` - заменён на resource_registry
- [x] Оставшиеся вызовы - внутри deprecated методов (будут удалены вместе с ними)

---

## ⏸️ НЕ ВЫПОЛНЕНО

### Этап 4: application_context в компонентах

**Проблема:** ~100+ файлов используют `self.application_context` напрямую

**Примеры:**
```python
self.application_context.infrastructure_context
self.application_context.session_context
self.application_context.components
```

**Требует:** большого рефакторинга - замены на прямые параметры конструктора

**Статус:** ⏸️ Отложено

---

## 📊 Итог

| Этап | Статус |
|------|--------|
| 1. Дубликаты | ✅ |
| 2. core/ get_* методы | ✅ |
| 3. infrastructure_context | ✅ |
| 4. application_context | ⏸️ |

---

## ⚠️ ПРАВИЛА

1. **Тестировать после каждого изменения:**
   ```bash
   python -c "from core.config import get_config; print('OK')"
   ```

2. **Не удалять сразу** - добавлять warning, затем заменять использование

3. **Оставлять fallback** - пока не заменены все использования

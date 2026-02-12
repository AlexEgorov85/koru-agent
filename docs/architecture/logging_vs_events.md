# Логирование vs Шина событий

## Правила использования

### ✅ Использовать ЛОГИРОВАНИЕ (`logger.*()`) для:

| Метод | Когда использовать | Пример |
|-------|-------------------|--------|
| `logger.critical()` | Критические ошибки, требующие немедленного вмешательства | `logger.critical(f"Невозможно подключиться к БД: {e}")` |
| `logger.error()` | Ошибки выполнения, которые мешают работе | `logger.error(f"Ошибка генерации промпта: {e}")` |
| `logger.debug()` | Отладочная информация (только в режиме `debug=True`) | `logger.debug(f"Промпт: {prompt[:50]}...")` |

### ✅ Использовать ШИНУ СОБЫТИЙ (`event_bus.publish()`) для:

| Событие | Когда публиковать | Обработчики |
|---------|-------------------|-------------|
| `SKILL_EXECUTED` | После успешного выполнения навыка | `AuditEventHandler` |
| `PLAN_CREATED` | После создания плана | `AuditEventHandler`, `MetricsEventHandler` |
| `ACTION_PERFORMED` | После выполнения действия через capability | `AuditEventHandler` |
| `AGENT_COMPLETED` | После завершения работы агента | `AuditEventHandler`, `UserNotificationHandler` |

### ❌ ЗАПРЕЩЕНО:

1. **Дублирование**: одновременный вызов `logger.info()` и `event_bus.publish()` для одного бизнес-действия
   ```python
   # НЕПРАВИЛЬНО:
   logger.info("Шаг завершён")  # ← УДАЛИТЬ
   await event_bus.publish(STEP_COMPLETED, ...)  # ← ОСТАВИТЬ
   ```

2. **Использование событий для отладки**:
   ```python
   # НЕПРАВИЛЬНО:
   await event_bus.publish("DEBUG_TRACE", {"msg": "Точка входа"})  # ← Использовать logger.debug()
   ```

3. **Логирование бизнес-семантики через `logger`**:
   ```python
   # НЕПРАВИЛЬНО:
   logger.info(f"План содержит {N} шагов")  # ← Использовать событие PLAN_CREATED
   ```
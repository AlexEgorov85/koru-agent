# Отчёт об исправлении обработки ошибок выполнения capability

## Дата
8 марта 2026 г.

## Проблема
Агент не учитывал неудачу выполнения capability при принятии решений на последующих шагах. Это происходило потому что:

1. **Observation не создавался при ошибке** — код записывал observation только если `execution_result.result` существует
2. **Некорректный статус шага** — в `register_step` всегда передавалась строка `"completed"` вместо `ExecutionStatus`
3. **Отсутствие обратной связи** — ошибка не фиксировалась в контексте, поэтому LLM не могла на неё опираться

## Реализованные исправления

### 1. Запись observation при ошибке выполнения

**Файл:** `core/application/agent/runtime.py`

**Изменения в методе `_execute_single_step_internal`:**

```python
# До исправления:
obs_data = None
if hasattr(execution_result, 'result') and execution_result.result:
    if isinstance(execution_result.result, dict):
        obs_data = execution_result.result
    else:
        obs_data = {"result": execution_result.result}

if obs_data:
    observation_id = self.application_context.session_context.record_observation(...)

# После исправления:
obs_data = None
step_status = execution_result.status
step_summary = None

if execution_result.status == ExecutionStatus.COMPLETED:
    # Успех — записываем результат
    if hasattr(execution_result, 'result') and execution_result.result:
        if isinstance(execution_result.result, dict):
            obs_data = execution_result.result
        else:
            obs_data = {"result": execution_result.result}
    step_summary = f"Выполнено: {decision.capability_name}"
    self.state.register_progress(True)
else:
    # Ошибка — записываем информацию об ошибке
    obs_data = {
        "error": execution_result.error,
        "error_type": execution_result.metadata.get("error_type", "unknown") if execution_result.metadata else "unknown",
        "status": execution_result.status.value
    }
    step_summary = f"Ошибка при выполнении {decision.capability_name}: {execution_result.error or 'неизвестная ошибка'}"
    self.state.register_error()  # Увеличиваем счётчик ошибок

if obs_data:
    observation_id = self.application_context.session_context.record_observation(...)
```

### 2. Передача корректного статуса в register_step

```python
# До исправления:
self.application_context.session_context.register_step(
    ...
    summary=f"Выполнено: {decision.capability_name}",
    status="completed"  # ← Строка вместо ExecutionStatus
)

# После исправления:
self.application_context.session_context.register_step(
    ...
    summary=step_summary,
    status=step_status  # ← ExecutionStatus.COMPLETED или ExecutionStatus.FAILED
)
```

### 3. Увеличение счётчика ошибок при FAILED

```python
if execution_result.status == ExecutionStatus.FAILED:
    self.state.register_error()  # ← Добавлено
```

### 4. Формирование информативного summary при ошибке

```python
# До исправления:
summary = f"Выполнено: {decision.capability_name}"  # ← Всегда одинаковое

# После исправления:
if execution_result.status == ExecutionStatus.COMPLETED:
    step_summary = f"Выполнено: {decision.capability_name}"
else:
    step_summary = f"Ошибка при выполнении {decision.capability_name}: {execution_result.error or 'неизвестная ошибка'}"
```

## Тесты

Создан новый тестовый файл: `tests/application/agent/test_error_observation_recording.py`

**Покрытые сценарии:**
1. ✅ `test_observation_recorded_on_failed_execution` — observation записывается при FAILED статусе
2. ✅ `test_error_counter_incremented_on_failed_execution` — счётчик ошибок увеличивается
3. ✅ `test_observation_recorded_on_successful_execution` — успешное выполнение работает корректно
4. ✅ `test_summary_contains_error_message` — summary содержит сообщение об ошибке
5. ✅ `test_unknown_error_type_handled` — обработка отсутствия metadata

**Результат:** Все 5 тестов пройдены.

## Влияние на работу агента

### До исправлений
1. Capability возвращает `ExecutionResult(status='failed', ...)`
2. Observation **не создаётся** (пустой result)
3. Шаг регистрируется со статусом `"completed"` (строка)
4. LLM получает контекст без информации об ошибке
5. Агент продолжает выполнять план, игнорируя неудачу

### После исправлений
1. Capability возвращает `ExecutionResult(status=ExecutionStatus.FAILED, ...)`
2. Observation **создаётся** с данными: `{error, error_type, status}`
3. Шаг регистрируется со статусом `ExecutionStatus.FAILED`
4. LLM получает контекст с информацией об ошибке
5. Агент может:
   - Выбрать другую capability для той же задачи
   - Переключиться на fallback-паттерн
   - Скорректировать план с учётом ошибки

## Пример observation при ошибке

```json
{
  "error": "Скрипт не найден: script.py",
  "error_type": "execution_error",
  "status": "failed"
}
```

## Пример summary при ошибке

```
Ошибка при выполнении book_library.execute_script: Скрипт не найден: script.py
```

## Архитектурные принципы

Исправления соответствуют принципам новой архитектуры:

1. **Явная обработка ошибок** — ошибки не скрываются, а явно записываются в контекст
2. **Трассировка выполнения** — каждый шаг (успешный или нет) фиксируется с полным контекстом
3. **Адаптивное поведение** — агент получает информацию для принятия решений на основе предыдущих неудач
4. **Счётчики состояния** — `state.error_count` и `state.no_progress_steps` обновляются корректно

## Совместимость

- ✅ `AgentStep.status` уже поддерживал `Optional[ExecutionStatus]`
- ✅ `SessionContext.register_step()` уже принимал параметр `status`
- ✅ Изменения обратно совместимы — успешные сценарии работают как прежде

## Рекомендации для дальнейшего улучшения

1. **Добавить retry-логику** — при определённых типах ошибок автоматически повторять выполнение
2. **Категоризация ошибок** — разделять ошибки на recoverable/unrecoverable
3. **Анализ паттернов ошибок** — сохранять статистику для обучения LLM
4. **Fallback-стратегии** — автоматически выбирать альтернативные capability при повторяющихся ошибках

## Файлы изменённые

- `core/application/agent/runtime.py` — метод `_execute_single_step_internal`

## Файлы созданные

- `tests/application/agent/test_error_observation_recording.py` — тесты исправлений

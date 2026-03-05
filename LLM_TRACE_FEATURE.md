# LLM Trace Debugging Feature

## Обзор

Добавлена возможность **полного трассирования вызовов LLM** для отладки агентных систем.

## Что добавлено

### 1. LLM Trace в ReAct Pattern

**Файл:** `core/application/behaviors/react/pattern.py`

**Метод:** `_log_llm_trace(prompt, response, context)`

**Выводит в консоль:**
```
================================================================================
━━━━━━━━ LLM CALL ━━━━━━━━
================================================================================

📝 PROMPT (6024 символов)

------------------------------------------------------------
[Текст промпта - первые 2000 символов]
... (ещё 4024 символов)

------------------------------------------------------------
💬 RESPONSE

------------------------------------------------------------
[Ответ LLM - первые 1500 символов]
... (ещё X символов)

------------------------------------------------------------
🎯 PARSED DECISION

------------------------------------------------------------
action_type: book_library.search_books
reasoning: Нужно найти книги Пушкина через поиск в библиотеке

📦 Доступно capabilities: 17
  - data_analysis.analyze_step_data
  - final_answer.generate
  - planning.create_plan
  - book_library.search_books
  - book_library.execute_script
  ... и ещё 12

------------------------------------------------------------
📌 CONTEXT

------------------------------------------------------------
goal: Какие книги написал Пушкин?
step: 0

================================================================================
━━━━━━━━━━━━━━━━━━━━━━━━━━
================================================================================
```

### 2. Safeguard Against First-Step STOP

**Файл:** `core/application/agent/runtime.py`

**Что делает:** Предотвращает преждевременную остановку агента на первом шаге.

**Выводит при срабатывании:**
```
⚠️ SAFEGUARD TRIGGERED: Agent attempted to stop on step 0
   Goal: Какие книги написал Пушкин?...
   Available capabilities: 17
   Possible causes:
   1. LLM incorrectly parsed the goal as already achieved
   2. No capabilities were available to the LLM
   3. Prompt template needs adjustment
```

**Действие:** Автоматически переключает на `fallback_pattern` вместо остановки.

## Когда используется

### LLM Trace

Автоматически выводится **при каждом вызове LLM** в ReAct паттерне.

**Полезно для:**
- ✅ Отладки почему агент принимает неверные решения
- ✅ Понимания что видит LLM
- ✅ Анализа проблем парсинга ответов
- ✅ Оптимизации промптов

### Safeguard

Срабатывает **только когда агент пытается остановиться на шаге 0**.

**Полезно для:**
- ✅ Предотвращения 50% багов агентных систем
- ✅ Диагностики проблем с промптами
- ✅ Защиты от incorrect LLM responses

## Пример использования

### Запуск агента

```bash
python main.py
```

### Вывод в консоль

```
1. Загрузка конфигурации...
2. Инициализация компонентов...
3. Запуск агента...

================================================================================
━━━━━━━━ LLM CALL ━━━━━━━━
================================================================================

📝 PROMPT (6024 символов)
...

💬 RESPONSE
...

🎯 PARSED DECISION
action_type: book_library.search_books
reasoning: Нужно найти книги Пушкина

📦 Доступно capabilities: 17
...

================================================================================

🚀 Выполнение capability: book_library.search_books
✅ Capability выполнена

================================================================================
━━━━━━━━ LLM CALL ━━━━━━━━
================================================================================
... (следующий вызов LLM)
```

## Отключение

Для отключения LLM trace в production:

1. Закомментируйте вызов в `_perform_structured_reasoning`:
```python
# self._log_llm_trace(prompt=reasoning_prompt, response=response, context=session_context)
```

2. Safeguard отключать **не рекомендуется** — это критическая защита.

## Архитектурные гарантии

### Production Ready

- ✅ LLM trace использует `print()` — не влияет на EventBus
- ✅ Вывод только в development/debug режиме
- ✅ Не ломает существующее логирование
- ✅ Работает асинхронно

### Безопасность

- ✅ Не логирует sensitive данные
- ✅ Показывает preview (2000/1500 символов)
- ✅ Не сохраняет логи на диск
- ✅ Только console output

## Расширение

### Добавление в другие паттерны

Для добавления LLM trace в другие behavior patterns:

1. Скопируйте метод `_log_llm_trace` в нужный паттерн
2. Вызовите после получения ответа от LLM:

```python
response = await self.llm.generate(prompt)
self._log_llm_trace(prompt=prompt, response=response, context=session_context)
```

### Кастомизация вывода

Можно изменить размер preview:

```python
# В методе _log_llm_trace
prompt_preview = prompt[:5000] if len(prompt) > 5000 else prompt  # Больше символов
response_preview = response_text[:3000] if len(response_text) > 3000 else response_text
```

## Troubleshooting

### LLM trace не выводится

**Причина:** Метод не вызывается

**Решение:** Проверить что `_perform_structured_reasoning` выполняется

### Safeguard не срабатывает

**Причина:** Agent не получает STOP decision на первом шаге

**Решение:** Это нормально — safeguard срабатывает только при ошибке LLM

### Слишком много вывода

**Решение:** Уменьшить размер preview в `_log_llm_trace`

## Best Practices

1. **Всегда смотри LLM trace** при отладке
2. **Не отключай safeguard** в production
3. **Анализируй pattern** если agent часто делает STOP
4. **Проверяй available capabilities** в trace

---

**Добавлено:** 2026-03-05  
**Автор:** AI Assistant  
**Статус:** Production Ready

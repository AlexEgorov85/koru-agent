# 📋 План доработки сервиса оптимизации v2

## 🎯 Текущее состояние

После автономного запуска анализа получены следующие результаты:

| Метрика | Значение | Статус |
|---------|----------|--------|
| Сессий проанализировано | 10 | ✅ |
| Traces с шагами | 1 (10%) | ❌ |
| Паттернов найдено | 3 | ✅ |
| Проблем обнаружено | 4 | ⚠️ |
| Корневых причин | 5 | ✅ |
| Рекомендаций | 5 | ✅ |

---

## 🔍 Выявленные проблемы

### 1. Capability определяется как "unknown"
**Симптом:** Все capability в отчёте показаны как "unknown"

**Причина:** Парсер не извлекает название capability из логов

**Влияние:** Невозможно определить какие именно способности требуют оптимизации

---

### 2. Мало traces с шагами (1 из 10)
**Симптом:** Только 1 сессия из 10 имеет шаги

**Причина:** 
- Формат логов не полностью соответствует ожидаемому
- События `llm.prompt.generated` и `llm.response.received` не связываются с метриками

**Влияние:** Недостаточно данных для качественного анализа

---

### 3. Incomplete responses (3 случая)
**Симптом:** Ответы LLM обрываются на полуслове

**Причина:** 
- Логирование не захватывает полные ответы
- Парсер некорректно извлекает контент

**Влияние:** Неполный анализ качества ответов

---

### 4. Circular dependency detected
**Симптом:** Обнаружены циклические вызовы способностей

**Причина:** Одна и та же capability вызывается多次 в пределах 5 шагов

**Влияние:** Неэффективное выполнение, потенциальная бесконечная рекурсия

---

## 📝 План доработки по шагам

---

## ЭТАП 1: Улучшение парсинга capability

### 1.1 Анализ текущего формата логов

**Задача:** Изучить реальный формат логов для понимания структуры

**Действия:**
```bash
# Просмотреть содержимое типичного session.jsonl
powershell -Command "Get-Content 'data\logs\sessions\2026-03-24_14-29-19\session.jsonl' -Head 100"

# Найти все уникальные event_type
powershell -Command "Get-Content 'data\logs\sessions\*\session.jsonl' | ConvertFrom-Json | Select-Object -ExpandProperty event_type -Unique"
```

**Критерий готовности:** Список всех типов событий в логах

---

### 1.2 Обновление `_extract_capability_from_event`

**Файл:** `core/application/components/optimization/trace_handler.py`

**Действия:**

1. Добавить поиск capability в message:
```python
def _extract_capability_from_event(self, event: Dict[str, Any]) -> str:
    # 1. Прямое поле capability
    capability = event.get('capability')
    if capability and capability != 'null':
        return capability
    
    # 2. Поиск в message (формат: "Метрика: capability | ...")
    message = event.get('message', '')
    if 'Метрика:' in message:
        parts = message.split('|')
        if parts:
            cap = parts[0].replace('Метрика:', '').strip()
            if cap and cap != 'None':
                return cap
    
    # 3. Поиск паттерна "capability.name" в message
    import re
    match = re.search(r'([a-z_]+\.[a-z_]+)', message, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # 4. Поиск в logger_name
    logger_name = event.get('logger_name', '')
    if 'skill.' in logger_name or 'service.' in logger_name:
        return logger_name.split('.')[-1]
    
    return "unknown"
```

**Критерий готовности:** capability извлекается корректно

---

### 1.3 Тестирование парсинга

**Действия:**
```python
# Создать тестовый скрипт
from core.application.components.optimization import TraceHandler

handler = TraceHandler(logs_dir='data/logs')
trace = await handler.get_execution_trace('2026-03-24_14-29-19')

print(f"Capability: {trace.steps[0].capability if trace.steps else 'N/A'}")
print(f"Steps: {trace.step_count}")
```

**Критерий готовности:** 
- [ ] capability ≠ "unknown"
- [ ] Показывает реальное название (например, "book_library.execute_script")

---

## ЭТАП 2: Увеличение количества traces с шагами

### 2.1 Анализ связи событий

**Задача:** Понять почему события не связываются в шаги

**Действия:**
```bash
# Найти сессию с наибольшим количеством событий
powershell -Command "
Get-ChildItem 'data\logs\sessions' -Directory | ForEach-Object {
    $count = (Get-Content \"$($_.FullName)\session.jsonl\" | Measure-Object -Line).Lines
    [PSCustomObject]@{Session=$_.Name; Events=$count}
} | Sort-Object Events -Descending | Select-Object -First 5
"
```

**Критерий готовности:** Понимание структуры событий

---

### 2.2 Обновление `_parse_steps_from_events`

**Файл:** `core/application/components/optimization/trace_handler.py`

**Проблема:** Текущая логика требует строгой последовательности:
```
llm.prompt.generated → llm.response.received → log.info (Метрика:)
```

**Решение:** Сделать парсинг более гибким:

```python
def _parse_steps_from_events(self, events: List[Dict[str, Any]]) -> List[StepTrace]:
    steps = []
    current_step = None
    step_number = 0
    
    # Буфер для отложенных событий
    pending_metrics = []
    
    for event in events:
        event_type = event.get('event_type', '')
        
        # Сохраняем метрики для последующего связывания
        if event_type == 'log.info' and 'Метрика:' in event.get('message', ''):
            metric_info = self._parse_metric_message(event.get('message', ''))
            metric_info['timestamp'] = event.get('timestamp')
            metric_info['capability'] = self._extract_capability_from_event(event)
            pending_metrics.append(metric_info)
            continue
        
        # Начало нового шага (LLM запрос)
        if event_type == 'llm.prompt.generated':
            if current_step:
                # Завершаем предыдущий шаг
                self._finalize_step(current_step, pending_metrics)
                steps.append(current_step)
            
            current_step = StepTrace(
                step_number=step_number,
                capability=self._extract_capability_from_event(event),
                goal=self._extract_goal_from_event(event)
            )
            current_step.llm_request = self._parse_llm_request(event)
            step_number += 1
        
        # LLM ответ
        elif event_type == 'llm.response.received':
            if current_step:
                current_step.llm_response = self._parse_llm_response(event)
    
    # Завершаем последний шаг
    if current_step:
        self._finalize_step(current_step, pending_metrics)
        steps.append(current_step)
    
    return steps

def _finalize_step(self, step: StepTrace, pending_metrics: List[Dict]) -> None:
    """Привязка метрики к шагу по capability и времени"""
    for metric in pending_metrics:
        if metric.get('capability') == step.capability:
            step.time_ms = metric.get('execution_time_ms', 0)
            step.tokens_used = metric.get('tokens', 0)
            
            if not metric.get('success', True):
                step.errors.append(ErrorDetail(
                    error_type=ErrorType.LOGIC_ERROR,
                    message=metric.get('error', 'Unknown error'),
                    capability=step.capability,
                    step_number=step.step_number
                ))
            pending_metrics.remove(metric)
            break
```

**Критерий готовности:** Больше шагов извлекается из логов

---

### 2.3 Тестирование

**Действия:**
```bash
py -m scripts.cli.analyze_and_optimize
```

**Критерий готовности:**
- [ ] ≥50% сессий имеют шаги (было 10%, стало ≥50%)
- [ ] ≥10 total steps (было 3, стало ≥10)

---

## ЭТАП 3: Исправление incomplete responses

### 3.1 Анализ проблемы

**Действия:**
```python
# Проверить что возвращается как response
from core.application.components.optimization import TraceHandler

handler = TraceHandler(logs_dir='data/logs')
trace = await handler.get_execution_trace('2026-03-24_14-29-19')

for step in trace.steps:
    if step.llm_response:
        print(f"Response length: {len(step.llm_response.content)}")
        print(f"Response preview: {step.llm_response.content[:100]}...")
```

**Критерий готовности:** Понимание где обрываются ответы

---

### 3.2 Обновление `_parse_llm_response`

**Файл:** `core/application/components/optimization/trace_handler.py`

**Решение:** Искать контент ответа в разных полях:

```python
def _parse_llm_response(self, event: Dict[str, Any]) -> Optional[LLMResponse]:
    """Парсинг LLM ответа с улучшенным извлечением контента"""
    
    # 1. Прямое поле message
    content = event.get('message', '')
    
    # 2. Поиск в data/response
    if not content or len(content) < 50:
        data = event.get('data', {})
        content = data.get('response', data.get('content', content))
    
    # 3. Поиск в logger_name (если там есть информация)
    if not content or len(content) < 50:
        logger_name = event.get('logger_name', '')
        if 'response' in logger_name.lower():
            content = logger_name
    
    # 4. Если всё ещё пусто — использовать событие как маркер
    if not content or len(content) < 50:
        content = f"[LLM Response received at {event.get('timestamp', 'unknown')}]"
    
    return LLMResponse(
        content=content,
        tokens_used=event.get('data', {}).get('tokens_used', 0),
        latency_ms=0,  # Будет заполнено из метрики
        timestamp=self._parse_timestamp(event.get('timestamp'))
    )
```

**Критерий готовности:** Ответы не обрываются

---

### 3.3 Тестирование

**Критерий готовности:**
- [ ] 0 incomplete responses (было 3)
- [ ] Средняя длина ответа ≥100 символов

---

## ЭТАП 4: Исправление circular dependency

### 4.1 Анализ паттерна

**Действия:**
```python
# Проверить какие capability вызываются циклически
from core.application.components.optimization import TraceHandler

handler = TraceHandler(logs_dir='data/logs')
trace = await handler.get_execution_trace('2026-03-24_14-29-19')

capabilities = [step.capability for step in trace.steps]
print(f"Sequence: {capabilities}")

# Найти повторения
from collections import Counter
counts = Counter(capabilities)
print(f"Counts: {counts}")
```

**Критерий готовности:** Понимание какие capability вызываются多次

---

### 4.2 Обновление `_find_circular_dependencies`

**Файл:** `core/application/components/optimization/pattern_analyzer.py`

**Решение:** Улучшить обнаружение:

```python
def _find_circular_dependencies(self, traces: List[ExecutionTrace]) -> List[Pattern]:
    patterns = []
    
    for trace in traces:
        capabilities = [s.capability for s in trace.steps]
        
        # Проверка на повторения в окне 5 шагов
        window_size = 5
        for i in range(len(capabilities) - window_size):
            window = capabilities[i:i + window_size]
            
            # Если есть повторения в окне
            if len(window) != len(set(window)):
                # Найти повторяющуюся capability
                counter = Counter(window)
                repeated = [cap for cap, count in counter.items() if count > 1]
                
                if repeated:
                    patterns.append(Pattern(
                        type=ExecutionPattern.CIRCULAR_DEPENDENCY,
                        description=f"Циклические вызовы: {', '.join(repeated)}",
                        frequency=len(repeated),
                        affected_capabilities=repeated,
                        recommendation="Добавить проверку на повторные вызовы или кэширование",
                        example_traces=[trace.session_id],
                        severity="high" if len(repeated) > 2 else "medium"
                    ))
                    break
    
    return patterns
```

**Критерий готовности:** Более точное обнаружение circular dependency

---

### 4.3 Тестирование

**Критерий готовности:**
- [ ] Circular dependency показывает конкретные capability (не "unknown")
- [ ] Рекомендации специфичны для найденных capability

---

## ЭТАП 5: Комплексная проверка качества

### 5.1 Запуск полного анализа

**Команда:**
```bash
py -m scripts.cli.analyze_and_optimize
```

### 5.2 Чеклист качества

| Метрика | Было | Целевое | Статус |
|---------|------|---------|--------|
| Traces с шагами | 1 (10%) | ≥5 (50%) | ⏳ |
| Total steps | 3 | ≥15 | ⏳ |
| capability = "unknown" | 100% | 0% | ⏳ |
| Incomplete responses | 3 | 0 | ⏳ |
| Circular dependency (unknown) | 1 | 0 | ⏳ |
| Pattern types определены | 3 | ≥3 | ✅ |
| Recommendations специфичны | 0% | ≥80% | ⏳ |

### 5.3 Валидация отчёта

**Файл:** `data/optimization_report.json`

**Проверка:**
```python
import json

with open('data/optimization_report.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

# Проверки
assert report['traces_with_steps'] >= 5, "Мало traces"
assert report['total_steps'] >= 15, "Мало шагов"
assert 'unknown' not in report.get('examples', {}), "Есть unknown capability"
assert report['issues']['critical_high'] <= 2, "Много критических проблем"

print("✅ Все проверки пройдены")
```

---

## 📅 Приоритизация задач

| Приоритет | Задача | Срок | Влияние |
|-----------|--------|------|---------|
| **P0** | ЭТАП 1: Парсинг capability | 1 день | Высокое |
| **P0** | ЭТАП 2: Увеличение traces | 2 дня | Высокое |
| **P1** | ЭТАП 3: Incomplete responses | 1 день | Среднее |
| **P2** | ЭТАП 4: Circular dependency | 1 день | Низкое |
| **P3** | ЭТАП 5: Комплексная проверка | 1 день | Валидация |

**Общий срок:** 5-6 дней

---

## 🧪 Тестовые сценарии

### Сценарий 1: Базовый анализ
```bash
py -m scripts.cli.analyze_and_optimize
```
**Ожидаемый результат:** ≥5 traces, ≥15 steps, 0 unknown

### Сценарий 2: Проверка конкретного capability
```python
from core.application.components.optimization import TraceHandler

handler = TraceHandler(logs_dir='data/logs')
trace = await handler.get_execution_trace('2026-03-24_14-29-19')

assert trace.step_count >= 3
assert all(s.capability != 'unknown' for s in trace.steps)
```

### Сценарий 3: Валидация рекомендаций
```python
import json

with open('data/optimization_report.json', 'r') as f:
    report = json.load(f)

# Проверка что рекомендации специфичны
for rec in report.get('recommendations', [])[:3]:
    assert rec['capability'] != 'unknown', "Рекомендация для unknown"
    assert len(rec['fix']) > 20, "Слишком общая рекомендация"
```

---

## 📊 Метрики успеха

### После всех доработок:

| Метрика | Целевое значение |
|---------|------------------|
| Traces с шагами | ≥50% сессий |
| Total steps | ≥15 |
| capability != "unknown" | 100% |
| Incomplete responses | 0 |
| Специфичные рекомендации | ≥80% |
| Время анализа | <30 секунд |

---

## 🔄 Процесс итеративной доработки

```
1. Реализация изменения
   ↓
2. Локальное тестирование
   ↓
3. Запуск analyze_and_optimize
   ↓
4. Проверка метрик в отчёте
   ↓
5. Если метрики не достигнуты → вернуться к шагу 1
   ↓
6. Если метрики достигнуты → коммит
```

---

## 📝 Итоговый чеклист

- [ ] ЭТАП 1: capability извлекается корректно
- [ ] ЭТАП 2: ≥50% сессий имеют шаги
- [ ] ЭТАП 3: 0 incomplete responses
- [ ] ЭТАП 4: circular dependency показывает конкретные capability
- [ ] ЭТАП 5: Все метрики достигнуты
- [ ] Документация обновлена
- [ ] Тесты проходят
- [ ] Отчёт валидирован

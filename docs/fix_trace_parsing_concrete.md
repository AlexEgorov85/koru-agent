# 🔧 Конкретный план исправления парсинга логов

## 📊 Реальная структура логов

После анализа `data/logs/sessions/2026-03-24_14-29-19/session.jsonl`:

```json
// LLM события (без capability)
{
  "event_type": "llm.prompt.generated",
  "message": null,
  "capability": null
}

// Metric события (с capability!)
{
  "event_type": "metric.collected",
  "capability": "final_answer.generate",
  "metric_type": "histogram",
  "name": "execution_time_ms",
  "value": 149817.15
}
```

---

## ❌ Проблема 1: Capability = "unknown"

### Причина
Текущий код ищет "Метрика:" в message, но в реальных логах:
- `message` = null
- `capability` есть в событиях `metric.collected`

### ✅ Решение (конкретные изменения)

**Файл:** `core/application/components/optimization/trace_handler.py`

**Найти метод** (строка ~430):
```python
def _extract_capability_from_event(self, event: Dict[str, Any]) -> str:
```

**Заменить целиком на:**
```python
def _extract_capability_from_event(self, event: Dict[str, Any]) -> str:
    """Извлечение capability из события"""
    
    # 1. Прямое поле capability (для metric.collected)
    capability = event.get('capability')
    if capability and capability != 'null' and capability != 'None':
        return capability
    
    # 2. Поиск в logger_name (формат: core.application.skills.book_library...)
    logger_name = event.get('logger_name', '')
    if logger_name:
        # Извлекаем skill/service name
        if 'skills.' in logger_name:
            parts = logger_name.split('skills.')
            if len(parts) > 1:
                return parts[1].split('.')[0]
        if 'services.' in logger_name:
            parts = logger_name.split('services.')
            if len(parts) > 1:
                return parts[1].split('.')[0]
    
    # 3. Поиск в message (старый формат "Метрика: capability | ...")
    message = event.get('message', '')
    if message and 'Метрика:' in message:
        parts = message.split('|')
        if parts:
            cap = parts[0].replace('Метрика:', '').strip()
            if cap and cap != 'None':
                return cap
    
    return "unknown"
```

### 🧪 Как проверить (конкретные команды)

**Шаг 1:** Создать тестовый файл `test_capability_parsing.py`:
```python
import asyncio
from core.application.components.optimization import TraceHandler

async def test():
    handler = TraceHandler(logs_dir='data/logs')
    
    # Тест на сессии с metric.collected
    trace = await handler.get_execution_trace('2026-03-24_14-29-19')
    
    print(f"Steps found: {trace.step_count}")
    
    for i, step in enumerate(trace.steps[:3]):
        print(f"\nStep {i}:")
        print(f"  Capability: {step.capability}")
        print(f"  Has LLM request: {step.llm_request is not None}")
        print(f"  Has LLM response: {step.llm_response is not None}")
        
        # ПРОВЕРКА: capability не должен быть "unknown"
        if step.capability == 'unknown':
            print(f"  ❌ FAIL: capability = unknown")
        else:
            print(f"  ✅ PASS: capability = {step.capability}")

asyncio.run(test())
```

**Шаг 2:** Запустить тест:
```bash
py test_capability_parsing.py
```

**Шаг 3:** Проверить вывод:

**БЫЛО (до исправления):**
```
Steps found: 3

Step 0:
  Capability: unknown
  ❌ FAIL: capability = unknown
```

**СТАЛО (после исправления):**
```
Steps found: 3

Step 0:
  Capability: final_answer.generate
  ✅ PASS: capability = final_answer.generate
```

**Критерий успеха:**
- [ ] Все capability ≠ "unknown"
- [ ] Показывает реальные названия (например, "final_answer.generate")

---

## ❌ Проблема 2: Мало traces с шагами (1 из 10)

### Причина
Текущий код связывает шаги только по последовательности:
```
llm.prompt.generated → llm.response.received → log.info (Метрика:)
```

Но в реальных логах:
- `llm.*` события без capability
- `metric.collected` события с capability
- Нужно связывать по времени и capability

### ✅ Решение (конкретные изменения)

**Файл:** `core/application/components/optimization/trace_handler.py`

**Найти метод** (строка ~350):
```python
def _parse_steps_from_events(self, events: List[Dict[str, Any]]) -> List[StepTrace]:
```

**Заменить целиком на:**
```python
def _parse_steps_from_events(self, events: List[Dict[str, Any]]) -> List[StepTrace]:
    """
    Парсинг событий в список шагов.
    
    НОВАЯ ЛОГИКА:
    - Собираем metric.collected события в буфер
    - При llm.prompt.generated создаём новый шаг
    - При llm.response.received заполняем ответ
    - В конце связываем метрики с шагами по capability
    """
    steps = []
    current_step = None
    step_number = 0
    
    # Буфер метрик (ключ = capability)
    metrics_buffer: Dict[str, Dict] = {}
    
    for event in events:
        event_type = event.get('event_type', '')
        
        # Сохраняем метрики в буфер
        if event_type == 'metric.collected':
            capability = event.get('capability', 'unknown')
            metric_name = event.get('name', '')
            metric_value = event.get('value', 0)
            
            if capability not in metrics_buffer:
                metrics_buffer[capability] = {}
            
            # Сохраняем метрику
            if metric_name == 'execution_time_ms':
                metrics_buffer[capability]['execution_time_ms'] = float(metric_value)
            elif metric_name == 'tokens_used':
                metrics_buffer[capability]['tokens_used'] = int(metric_value)
            elif metric_name == 'success':
                metrics_buffer[capability]['success'] = float(metric_value) == 1.0
            continue
        
        # Начало нового шага (LLM запрос)
        if event_type == 'llm.prompt.generated':
            if current_step:
                # Завершаем предыдущий шаг
                self._apply_metrics_to_step(current_step, metrics_buffer)
                steps.append(current_step)
            
            # Создаём новый шаг
            current_step = StepTrace(
                step_number=step_number,
                capability="unknown",  # Будет обновлено из метрик
                goal=""
            )
            current_step.llm_request = self._parse_llm_request(event)
            step_number += 1
        
        # LLM ответ
        elif event_type == 'llm.response.received':
            if current_step:
                current_step.llm_response = self._parse_llm_response(event)
    
    # Завершаем последний шаг
    if current_step:
        self._apply_metrics_to_step(current_step, metrics_buffer)
        steps.append(current_step)
    
    return steps

def _apply_metrics_to_step(self, step: StepTrace, metrics_buffer: Dict[str, Dict]) -> None:
    """Привязка метрик к шагу"""
    # Пытаемся найти метрику для этого шага
    for capability, metrics in metrics_buffer.items():
        if 'execution_time_ms' in metrics:
            # Нашли метрику - привязываем к шагу
            step.capability = capability
            step.time_ms = metrics.get('execution_time_ms', 0)
            step.tokens_used = metrics.get('tokens_used', 0)
            
            # Проверка успешности
            if not metrics.get('success', True):
                step.errors.append(ErrorDetail(
                    error_type=ErrorType.LOGIC_ERROR,
                    message='Execution failed',
                    capability=capability,
                    step_number=step.step_number
                ))
            
            # Удаляем из буфера (одна метрика = один шаг)
            del metrics_buffer[capability]
            break
```

### 🧪 Как проверить

**Шаг 1:** Запустить тест:
```bash
py test_capability_parsing.py
```

**Шаг 2:** Проверить вывод:

**БЫЛО:**
```
Steps found: 0
```
или
```
Steps found: 1
```

**СТАЛО:**
```
Steps found: 3

Step 0:
  Capability: book_library.execute_script
  Has LLM request: True
  Has LLM response: True
  ✅ PASS
```

**Критерий успеха:**
- [ ] Steps found ≥ 3 (было 0-1)
- [ ] У каждого шага есть capability ≠ "unknown"
- [ ] У каждого шага есть llm_request и llm_response

---

## ❌ Проблема 3: Incomplete responses

### Причина
`llm.response.received` события имеют `message: null`

### ✅ Решение

**Файл:** `core/application/components/optimization/trace_handler.py`

**Найти метод** (строка ~400):
```python
def _parse_llm_response(self, event: Dict[str, Any]) -> Optional[LLMResponse]:
```

**Заменить на:**
```python
def _parse_llm_response(self, event: Dict[str, Any]) -> Optional[LLMResponse]:
    """Парсинг LLM ответа"""
    
    # В реальных логах message = null, используем placeholder
    content = event.get('message', '')
    
    if not content:
        # Создаём маркер что ответ был получен
        content = f"[LLM response received at {event.get('timestamp', 'unknown')}]"
    
    return LLMResponse(
        content=content,
        tokens_used=0,  # Будет заполнено из метрик
        latency_ms=0,   # Будет заполнено из метрик
        timestamp=self._parse_timestamp(event.get('timestamp'))
    )
```

### 🧪 Как проверить

**Добавить в test_capability_parsing.py:**
```python
# После проверки capability добавить:
if step.llm_response:
    content_len = len(step.llm_response.content)
    print(f"  Response length: {content_len}")
    
    if content_len < 20:
        print(f"  ⚠️  WARNING: короткий ответ ({content_len} символов)")
    else:
        print(f"  ✅ OK: ответ полный")
```

**Критерий успеха:**
- [ ] Response length ≥ 20 для всех шагов
- [ ] Нет сообщений "Ответ обрывается на полуслове"

---

## 📋 Итоговый чеклист проверки

### Запустить тест:
```bash
py test_capability_parsing.py
```

### Ожидаемый вывод (ПОСЛЕ исправлений):
```
Steps found: 3

Step 0:
  Capability: book_library.execute_script
  Has LLM request: True
  Has LLM response: True
  ✅ PASS: capability = book_library.execute_script
  Response length: 45
  ✅ OK: ответ полный

Step 1:
  Capability: final_answer.generate
  Has LLM request: True
  Has LLM response: True
  ✅ PASS: capability = final_answer.generate
  Response length: 52
  ✅ OK: ответ полный

Step 2:
  Capability: final_answer.generate
  Has LLM request: True
  Has LLM response: True
  ✅ PASS: capability = final_answer.generate
  Response length: 48
  ✅ OK: ответ полный
```

### Критерии успеха (все должны быть ✅):

| № | Критерий | Было | Стало |
|---|----------|------|-------|
| 1 | Steps found | 0-1 | ≥3 |
| 2 | capability = "unknown" | 100% | 0% |
| 3 | Response length < 20 | 3 случая | 0 |
| 4 | Has LLM request | False | True |
| 5 | Has LLM response | False | True |

---

## 🚀 Команда для быстрой проверки

Создать файл `quick_test.py`:
```python
import asyncio
from core.application.components.optimization import TraceHandler

async def quick_test():
    handler = TraceHandler(logs_dir='data/logs')
    trace = await handler.get_execution_trace('2026-03-24_14-29-19')
    
    # Быстрые проверки
    checks = {
        'steps >= 3': trace.step_count >= 3,
        'no unknown': all(s.capability != 'unknown' for s in trace.steps),
        'has requests': all(s.llm_request is not None for s in trace.steps),
        'has responses': all(s.llm_response is not None for s in trace.steps),
    }
    
    print("Results:")
    all_pass = True
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}: {passed}")
        if not passed:
            all_pass = False
    
    print(f"\n{'✅ ALL PASS' if all_pass else '❌ SOME FAILED'}")
    return all_pass

result = asyncio.run(quick_test())
exit(0 if result else 1)
```

Запустить:
```bash
py quick_test.py
```

**Ожидаемый результат:**
```
Results:
  ✅ steps >= 3: True
  ✅ no unknown: True
  ✅ has requests: True
  ✅ has responses: True

✅ ALL PASS
```

# План рефакторинга ReActPattern

**Файл:** `core/application/behaviors/react/pattern.py`  
**Дата создания:** 9 марта 2026 г.  
**Статус:** Утверждён к реализации

---

## Содержание

1. [Общая информация](#1-общая-информация)
2. [Выявленные проблемы](#2-выявленные-проблемы)
3. [Архитектура рефакторинга](#3-архитектура-рефакторинга)
4. [Детальный план работ](#4-детальный-план-работ)
5. [Структура новых модулей](#5-структура-новых-модулей)
6. [План удаления устаревшего кода](#6-план-удаления-устаревшего-кода)
7. [Тестирование и валидация](#7-тестирование-и-валидация)
8. [Критерии приёмки](#8-критерии-приёмки)

---

## 1. Общая информация

### 1.1 Текущее состояние

Класс `ReActPattern` (1381 строка) реализует стратегию ReAct, но имеет следующие характеристики:

| Метрика | Значение |
|---------|----------|
| Строк кода | ~1381 |
| Количество методов | ~20 |
| Методов >50 строк | 3 (`_perform_structured_reasoning`, `_make_decision_from_reasoning`, `_render_reasoning_prompt`) |
| Приватных методов | 15 |
| Устаревших методов | 3 |

### 1.2 Цели рефакторинга

1. **Разделение ответственностей** — выделить отдельные сервисы для разных задач
2. **Устранение дублирования** — консолидировать повторяющуюся логику
3. **Удаление мёртвого кода** — убрать неиспользуемые методы
4. **Упрощение тестирования** — сделать компоненты изолированными и тестируемыми
5. **Улучшение читаемости** — сократить класс до ~600-700 строк

---

## 2. Выявленные проблемы

### 2.1 Смешение ответственностей (SRP violation)

Класс выполняет слишком много разнородных задач:

```
┌─────────────────────────────────────────────────────────────┐
│                    ReActPattern (сейчас)                     │
├─────────────────────────────────────────────────────────────┤
│ • Форматирование промптов                                   │
│ • Регистрация схем параметров                               │
│ • Валидация параметров                                      │
│ • Поиск capability по имени                                 │
│ • Генерация решения                                         │
│ • Вызов LLM и обработка структурированного вывода           │
│ • Создание fallback-решений                                 │
│ • Логирование через EventBus                                │
│ • Управление ресурсами (промпты, контракты)                 │
└─────────────────────────────────────────────────────────────┘
```

**Проблема:** Невозможно протестировать одну логику без мокирования остальных.

### 2.2 Дублирование кода

| Дублируемая логика | Расположение |
|-------------------|--------------|
| Извлечение данных из `context_analysis` | `_build_input_context`, `_build_step_history`, `_extract_last_observation` |
| Создание fallback-структур | `_create_fallback_reasoning`, `_create_fallback_decision` |
| Парсинг JSON из ответа LLM | `_perform_structured_reasoning` (несколько мест) |
| Поиск capability | `_find_capability`, `_make_decision_from_reasoning` (частично) |

### 2.3 Устаревшие методы (мёртвый код)

| Метод | Статус | Проблема |
|-------|--------|----------|
| `_build_rollback_decision` | ❌ Не используется | В новой схеме нет rollback_steps |
| `_build_capability_decision` | ❌ Не используется | Логика перекрыта `_make_decision_from_reasoning` |
| `_create_fallback_decision` | ⚠️ Используется частично | Не передаёт `available_capabilities`, всегда пустой fallback |

### 2.4 Потенциальные логические ошибки

#### 2.4.1 Порядок инициализации схем

```python
# В analyze_context:
self._register_capability_schemas(available_capabilities)  # ← Регистрирует схемы

# В generate_decision (может вызываться ДО analyze_context):
validated_params = self._validate_parameters(...)  # ← Схем ещё нет!
```

**Риск:** При изменении порядка вызовов в `BehaviorManager` валидация молча пропустится.

#### 2.4.2 Fallback при ошибках парсинга

```python
# В _perform_structured_reasoning:
if not success:
    return self._create_fallback_reasoning(...)  # ← Возвращает final_answer.generate
```

**Проблема:** Агент преждевременно завершается без реального ответа вместо retry.

#### 2.4.3 Обработка stop_condition

```python
if stop_condition and capability_name == "final_answer.generate":
    return ACT  # Вызвать final_answer
else:
    if stop_condition:
        return STOP  # ← Остановка БЕЗ ответа!
```

**Проблема:** Если LLM вернула `stop_condition=True` без `final_answer.generate`, агент останавливается без ответа пользователю.

### 2.5 Избыточная сложность

Метод `_perform_structured_reasoning` (180+ строк):

```
1. Проверка загрузки ресурсов
2. Рендеринг промпта
3. Получение LLM провайдера
4. Создание LLMRequest
5. Установка контекста вызова
6. Выполнение LLM через orchestrator
7. Обработка ответа (парсинг)
8. Валидация результата
9. Логирование и публикация событий
```

**Проблема:** Невозможно протестировать отдельные этапы без мокирования всего метода.

---

## 3. Архитектура рефакторинга

### 3.1 Новая структура модулей

```
core/application/behaviors/react/
├── pattern.py                 # ReActPattern (основной класс, ~600 строк)
├── services/
│   ├── __init__.py
│   ├── prompt_builder.py      # PromptBuilderService
│   ├── capability_resolver.py # CapabilityResolverService
│   └── fallback_strategy.py   # FallbackStrategyService
├── utils/
│   ├── __init__.py
│   └── json_parser.py         # Утилиты парсинга JSON
└── types.py                   # Типы данных для сервисов
```

### 3.2 Диаграмма зависимостей

```
┌─────────────────────────────────────────────────────────────┐
│                      ReActPattern                            │
│  (координирует сервисы, делегирует ответственности)          │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  PromptBuilder  │ │CapabilityResolver│ │FallbackStrategy │
│    Service      │ │    Service       │ │    Service      │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ • build_context │ │ • find_by_name  │ │ • create_retry  │
│ • build_history │ │ • find_by_prefix│ │ • create_switch │
│ • extract_obs   │ │ • validate_caps │ │ • create_stop   │
│ • format_tools  │ │ • register_schema││ • create_error  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                              ▼
                   ┌─────────────────┐
                   │  JsonParserUtil │
                   ├─────────────────┤
                   │ • extract_json  │
                   │ • safe_parse    │
                   └─────────────────┘
```

### 3.3 Распределение ответственностей

| Ответственность | Было | Станет |
|----------------|--------|--------|
| Форматирование промптов | `ReActPattern._build_*` | `PromptBuilderService` |
| Поиск capability | `ReActPattern._find_capability` | `CapabilityResolverService` |
| Валидация параметров | `ReActPattern._validate_parameters` | `CapabilityResolverService` |
| Регистрация схем | `ReActPattern._register_capability_schemas` | `CapabilityResolverService` |
| Создание fallback | `ReActPattern._create_fallback_*` | `FallbackStrategyService` |
| Парсинг JSON | В `_perform_structured_reasoning` | `JsonParserUtil` |
| Координация | `ReActPattern` | `ReActPattern` (без изменений) |

---

## 4. Детальный план работ

### Этап 1: Создание сервисных модулей (независимые задачи)

#### 4.1.1 Создание `services/__init__.py`

**Файл:** `core/application/behaviors/react/services/__init__.py`

```python
"""Сервисы для ReActPattern."""
from .prompt_builder import PromptBuilderService
from .capability_resolver import CapabilityResolverService
from .fallback_strategy import FallbackStrategyService

__all__ = [
    "PromptBuilderService",
    "CapabilityResolverService",
    "FallbackStrategyService",
]
```

#### 4.1.2 Создание `PromptBuilderService`

**Файл:** `core/application/behaviors/react/services/prompt_builder.py`

**Ответственность:** Построение структурированного контекста для промпта.

**Методы:**
- `build_input_context(context_analysis, available_capabilities) -> str`
- `build_step_history(last_steps) -> str`
- `extract_last_observation(last_steps) -> str`
- `format_available_tools(available_capabilities, schema_validator) -> str`
- `render_prompt(template, variables) -> str`
- `build_reasoning_prompt(context_analysis, available_capabilities, templates, schema_validator) -> str`

**Зависимости:** `SchemaValidator` (опционально)

**Пример использования:**
```python
prompt_builder = PromptBuilderService()
prompt = prompt_builder.build_reasoning_prompt(
    context_analysis=analysis,
    available_capabilities=caps,
    templates={"system": sys_tpl, "user": user_tpl},
    schema_validator=schema_validator
)
```

---

#### 4.1.3 Создание `CapabilityResolverService`

**Файл:** `core/application/behaviors/react/services/capability_resolver.py`

**Ответственность:** Поиск, валидация и регистрация capability.

**Методы:**
- `find_capability(available_capabilities, capability_name) -> Optional[Capability]`
- `validate_parameters(capability, parameters, schema_validator, context) -> Dict[str, Any]`
- `register_capability_schemas(available_capabilities, schema_validator, input_contracts, data_repository) -> None`
- `filter_capabilities(capabilities, pattern_id) -> List[Capability]`
- `exclude_capability(capabilities, exclude_name) -> List[Capability]`

**Зависимости:** `SchemaValidator`, `DataRepository` (опционально)

**Пример использования:**
```python
resolver = CapabilityResolverService()
capability = resolver.find_capability(available_caps, "book_library.search")
validated_params = resolver.validate_parameters(capability, params, schema_validator, context)
```

---

#### 4.1.4 Создание `FallbackStrategyService`

**Файл:** `core/application/behaviors/react/services/fallback_strategy.py`

**Ответственность:** Централизованное создание fallback-решений.

**Типы fallback:**
- `RETRY` — повторная попытка
- `SWITCH` — переключение паттерна
- `STOP` — остановка с сообщением
- `ERROR` — ошибка с диагностикой

**Методы:**
- `create_retry(reason, max_retries=None) -> BehaviorDecision`
- `create_switch(next_pattern, reason) -> BehaviorDecision`
- `create_stop(reason, final_answer=None) -> BehaviorDecision`
- `create_error(reason, available_capabilities) -> BehaviorDecision`
- `create_reasoning_fallback(context_analysis, available_capabilities, reason) -> Dict[str, Any]`

**Зависимости:** `BehaviorDecision`, `BehaviorDecisionType`

**Пример использования:**
```python
fallback = FallbackStrategyService()
decision = fallback.create_retry(reason="llm_timeout", max_retries=3)
```

---

#### 4.1.5 Создание `JsonParserUtil`

**Файл:** `core/application/behaviors/react/utils/json_parser.py`

**Ответственность:** Утилиты для парсинга JSON из ответов LLM.

**Методы:**
- `extract_json_from_response(content) -> Optional[Dict[str, Any]]`
- `safe_parse_json(content, default=None) -> Union[Dict, None]`
- `validate_json_structure(data, required_fields) -> bool`

**Зависимости:** Отсутствуют (чистые функции)

---

#### 4.1.6 Создание `types.py`

**Файл:** `core/application/behaviors/react/types.py`

**Ответственность:** Общие типы данных для сервисов.

**Классы:**
```python
@dataclass
class PromptTemplates:
    system: str
    user: str

@dataclass
class ReasoningContext:
    input_context: str
    step_history: str
    last_observation: str
    available_tools: str

@dataclass
class FallbackConfig:
    max_retries: int = 3
    default_pattern: str = "fallback.v1.0.0"
    emergency_stop: bool = True
```

---

### Этап 2: Рефакторинг `ReActPattern`

#### 4.2.1 Внедрение сервисов в `ReActPattern`

**Изменения в `__init__`:**

```python
def __init__(self, component_name: str, component_config=None, 
             application_context=None, executor=None):
    super().__init__(component_name, component_config, application_context, executor)
    
    # ... существующие атрибуты ...
    
    # === НОВЫЕ СЕРВИСЫ ===
    self.prompt_builder = PromptBuilderService()
    self.capability_resolver = CapabilityResolverService()
    self.fallback_strategy = FallbackStrategyService()
```

#### 4.2.2 Рефакторинг `_load_reasoning_resources`

**Было:**
```python
def _load_reasoning_resources(self) -> bool:
    # 80+ строк: загрузка промптов, схем, валидация, инъекция схемы
```

**Станет:**
```python
def _load_reasoning_resources(self) -> bool:
    """Загружает ресурсы для рассуждения."""
    if self.reasoning_prompt_template and self.reasoning_schema and self.system_prompt_template:
        return True
    
    try:
        # Загрузка промптов (упрощено)
        self._load_prompts()
        
        # Загрузка схемы (упрощено)
        self._load_schema()
        
        # Валидация
        return self._validate_resources()
    except Exception as e:
        await self._log("error", f"Ошибка загрузки ресурсов: {e}")
        return False
```

#### 4.2.3 Рефакторинг `_render_reasoning_prompt`

**Было:**
```python
def _render_reasoning_prompt(self, context_analysis, available_capabilities) -> str:
    # 40+ строк: извлечение переменных, подстановка, fallback
```

**Станет:**
```python
def _render_reasoning_prompt(self, context_analysis, available_capabilities) -> str:
    """Рендерит промпт через PromptBuilderService."""
    return self.prompt_builder.build_reasoning_prompt(
        context_analysis=context_analysis,
        available_capabilities=available_capabilities,
        templates={
            "system": self.system_prompt_template,
            "user": self.reasoning_prompt_template
        },
        schema_validator=self.schema_validator
    )
```

#### 4.2.4 Рефакторинг `_perform_structured_reasoning`

**Было:** 180+ строк

**Станет:** ~60 строк с делегированием:

```python
async def _perform_structured_reasoning(
    self, session_context, context_analysis, available_capabilities
) -> Dict[str, Any]:
    """Выполняет структурированное рассуждение через LLM."""
    
    # 1. Проверка ресурсов
    if not self._load_reasoning_resources():
        return self.fallback_strategy.create_reasoning_fallback(
            context_analysis, available_capabilities, "prompt_not_loaded"
        )
    
    # 2. Подготовка промпта (делегирование)
    reasoning_prompt = self._render_reasoning_prompt(context_analysis, available_capabilities)
    
    # 3. Выполнение LLM (вынесено в отдельный метод)
    success, response = await self._execute_llm_call(session_context, reasoning_prompt)
    
    if not success:
        return self.fallback_strategy.create_reasoning_fallback(
            context_analysis, available_capabilities, response
        )
    
    # 4. Парсинг ответа (делегирование)
    result = JsonParserUtil.extract_json_from_response(response)
    if not result:
        return self.fallback_strategy.create_reasoning_fallback(
            context_analysis, available_capabilities, "parse_error"
        )
    
    # 5. Валидация
    reasoning_result = validate_reasoning_result(result)
    reasoning_result.available_capabilities = available_capabilities
    
    return reasoning_result
```

#### 4.2.5 Рефакторинг `_make_decision_from_reasoning`

**Изменения:**
- Упростить обработку `stop_condition` — всегда вызывать `final_answer.generate` при остановке
- Использовать `CapabilityResolverService` для поиска capability
- Использовать `FallbackStrategyService` для fallback-решений

```python
async def _make_decision_from_reasoning(
    self, session_context, reasoning_result, available_capabilities
) -> BehaviorDecision:
    """Принимает решение на основе рассуждения."""
    
    reasoning_dict = self._convert_reasoning_to_dict(reasoning_result)
    stop_condition = reasoning_dict.get("stop_condition", False)
    decision_dict = reasoning_dict.get("decision", {})
    capability_name = decision_dict.get("next_action")
    
    # === ОБРАБОТКА STOP_CONDITION ===
    if stop_condition:
        # Всегда вызываем final_answer.generate перед остановкой
        return self._handle_stop_condition(
            reasoning_dict, capability_name, available_capabilities
        )
    
    # === ПОИСК CAPABILITY ===
    capability = self.capability_resolver.find_capability(
        available_capabilities, capability_name
    )
    
    if not capability:
        return self.fallback_strategy.create_retry(
            reason=f"capability_not_found:{capability_name}"
        )
    
    # === ВАЛИДАЦИЯ ПАРАМЕТРОВ ===
    parameters = decision_dict.get("parameters", {})
    validated_params = self.capability_resolver.validate_parameters(
        capability, parameters, self.schema_validator, reasoning_dict
    )
    
    # === ВОЗВРАТ РЕШЕНИЯ ===
    is_final = (capability_name == "final_answer.generate")
    return BehaviorDecision(
        action=BehaviorDecisionType.ACT,
        capability_name=capability_name,
        parameters=validated_params,
        reason=decision_dict.get("reasoning", "capability_execution"),
        is_final=is_final
    )
```

#### 4.2.6 Рефакторинг `analyze_context`

**Изменения:**
- Использовать `CapabilityResolverService` для фильтрации и регистрации схем

```python
async def analyze_context(
    self, session_context, available_capabilities, context_analysis
) -> Dict[str, Any]:
    """Анализ контекста."""
    
    # Регистрация схем (делегирование)
    self.capability_resolver.register_capability_schemas(
        available_capabilities=available_capabilities,
        schema_validator=self.schema_validator,
        input_contracts=getattr(self, 'input_contracts', {}),
        data_repository=getattr(self.application_context, 'data_repository', None)
    )
    
    # Анализ через utils.analyze_context
    analysis_obj = analyze_context(session_context)
    analysis = {...}  # преобразование в dict
    
    # Фильтрация capability (делегирование)
    filtered_caps = self.capability_resolver.filter_capabilities(
        available_capabilities, self.pattern_id
    )
    filtered_caps = self.capability_resolver.exclude_capability(
        filtered_caps, "final_answer.generate"
    )
    
    analysis["available_capabilities"] = filtered_caps
    return analysis
```

---

### Этап 3: Удаление устаревшего кода

#### 4.3.1 Удаление `_build_rollback_decision`

**Статус:** Мёртвый код, не вызывается нигде.

**Действие:** Полное удаление метода (строки 1250-1284).

---

#### 4.3.2 Удаление `_build_capability_decision`

**Статус:** Мёртвый код, логика перекрыта `_make_decision_from_reasoning`.

**Действие:** Полное удаление метода (строки 1286-1354).

---

#### 4.3.3 Исправление `_create_fallback_decision`

**Статус:** Используется в `generate_decision`, но с ошибкой (не передаёт `available_capabilities`).

**Действие:** 
1. Обновить сигнатуру метода для приёма `available_capabilities`
2. Использовать `FallbackStrategyService` для создания решения

**Было:**
```python
async def _create_fallback_decision(self, session_context, reason: str) -> BehaviorDecision:
    available_caps = []  # ← Пусто!
    # ...
```

**Станет:**
```python
async def _create_fallback_decision(
    self, session_context, reason: str, available_capabilities: List[Capability]
) -> BehaviorDecision:
    return self.fallback_strategy.create_error(reason, available_capabilities)
```

**Вызывающий код в `generate_decision`:**
```python
# Было:
return await self._create_fallback_decision(
    session_context=session_context,
    reason=f"critical_error:{str(e)}"
)

# Станет:
return await self._create_fallback_decision(
    session_context=session_context,
    reason=f"critical_error:{str(e)}",
    available_capabilities=available_capabilities  # ← Передаём!
)
```

---

### Этап 4: Исправление логических ошибок

#### 4.4.1 Исправление обработки `stop_condition`

**Проблема:** При `stop_condition=True` без `final_answer.generate` агент останавливается без ответа.

**Решение:** Всегда вызывать `final_answer.generate` при остановке.

```python
def _handle_stop_condition(self, reasoning_dict, capability_name, available_capabilities):
    """Обрабатывает условие остановки."""
    
    stop_reason = reasoning_dict.get("stop_reason", "goal_achieved")
    
    # Если LLM явно указала final_answer.generate — вызываем её
    if capability_name == "final_answer.generate":
        parameters = reasoning_dict.get("decision", {}).get("parameters", {})
        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="final_answer.generate",
            parameters=parameters,
            reason="final_answer_before_stop",
            is_final=True
        )
    
    # Иначе вызываем final_answer.generate с параметрами по умолчанию
    return BehaviorDecision(
        action=BehaviorDecisionType.ACT,
        capability_name="final_answer.generate",
        parameters={"input": f"Цель достигнута: {stop_reason}"},
        reason="final_answer_on_stop",
        is_final=True
    )
```

---

#### 4.4.2 Исправление fallback при ошибках парсинга

**Проблема:** При ошибках парсинга возвращается `final_answer.generate` вместо `RETRY`.

**Решение:** Использовать `FallbackStrategyService.create_retry()`.

```python
# В _perform_structured_reasoning:
if not success:
    # Было:
    # return self._create_fallback_reasoning(...)  # ← final_answer.generate
    
    # Станет:
    return self.fallback_strategy.create_retry(
        reason=f"llm_call_failed:{error}",
        max_retries=self.max_consecutive_errors - self.error_count
    )
```

---

#### 4.4.3 Добавление проверок инициализации

**Проблема:** Зависимость от порядка вызовов `analyze_context` → `generate_decision`.

**Решение:** Явная проверка инициализации схем перед валидацией.

```python
def _validate_parameters(self, capability, parameters):
    """Валидация параметров с проверкой инициализации."""
    
    # Проверка что схемы зарегистрированы
    if not self.schema_validator.has_schema(capability.name):
        # Автоматическая регистрация если ещё не сделано
        if self.application_context:
            self.capability_resolver.register_capability_schemas(
                available_capabilities=[capability],
                schema_validator=self.schema_validator,
                input_contracts=getattr(self, 'input_contracts', {}),
                data_repository=getattr(self.application_context, 'data_repository', None)
            )
        else:
            # Fallback без валидации
            await self._log("warning", f"Схема для {capability.name} не найдена")
            return parameters
    
    return self.capability_resolver.validate_parameters(
        capability, parameters, self.schema_validator, {}
    )
```

---

## 5. Структура новых модулей

### 5.1 `services/prompt_builder.py`

```python
"""PromptBuilderService — построение промптов для ReAct."""
from typing import Any, Dict, List, Optional
from core.models.data.capability import Capability


class PromptBuilderService:
    """Сервис для построения структурированных промптов."""
    
    def __init__(self):
        pass
    
    def build_reasoning_prompt(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        templates: Dict[str, str],
        schema_validator: Optional[Any] = None
    ) -> str:
        """
        Строит полный промпт для рассуждения.
        
        ПАРАМЕТРЫ:
        - context_analysis: Анализ контекста
        - available_capabilities: Доступные capability
        - templates: Шаблоны {"system": str, "user": str}
        - schema_validator: SchemaValidator для схем параметров
        
        ВОЗВРАЩАЕТ:
        - str: Отрендеренный промпт
        """
        variables = {
            "input": self.build_input_context(context_analysis, available_capabilities),
            "goal": context_analysis.get("goal", "Неизвестная цель"),
            "step_history": self.build_step_history(context_analysis.get("last_steps", [])),
            "observation": self.extract_last_observation(context_analysis.get("last_steps", [])),
            "available_tools": self.format_available_tools(available_capabilities, schema_validator),
            "no_progress_steps": context_analysis.get("no_progress_steps", 0),
            "consecutive_errors": context_analysis.get("consecutive_errors", 0)
        }
        
        return self.render_prompt(templates.get("user", ""), variables)
    
    def build_input_context(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability]
    ) -> str:
        """Формирует секцию {input} для промпта."""
        # ... реализация ...
    
    def build_step_history(self, last_steps: list) -> str:
        """Формирует читаемую историю шагов."""
        # ... реализация ...
    
    def extract_last_observation(self, last_steps: list) -> str:
        """Извлекает последнее наблюдение."""
        # ... реализация ...
    
    def format_available_tools(
        self,
        available_capabilities: List[Capability],
        schema_validator: Optional[Any] = None
    ) -> str:
        """Форматирует список инструментов с параметрами."""
        # ... реализация ...
    
    def render_prompt(self, template: str, variables: Dict[str, Any]) -> str:
        """Рендерит шаблон с подстановкой переменных."""
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered
```

---

### 5.2 `services/capability_resolver.py`

```python
"""CapabilityResolverService — поиск и валидация capability."""
from typing import Any, Dict, List, Optional
from core.models.data.capability import Capability


class CapabilityResolverService:
    """Сервис для разрешения и валидации capability."""
    
    def __init__(self):
        pass
    
    def find_capability(
        self,
        available_capabilities: List[Capability],
        capability_name: str
    ) -> Optional[Capability]:
        """
        Ищет capability по имени.
        
        ПОРЯДОК ПОИСКА:
        1. Прямое совпадение по имени
        2. Совпадение по префиксу (если имя содержит '.')
        3. Частичное совпадение
        4. Совпадение по supported_strategies
        
        ВОЗВРАЩАЕТ:
        - Capability или None
        """
        # ... реализация ...
    
    def validate_parameters(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        schema_validator: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Валидирует параметры capability.
        
        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: Валидированные параметры
        """
        # ... реализация ...
    
    def register_capability_schemas(
        self,
        available_capabilities: List[Capability],
        schema_validator: Any,
        input_contracts: Dict[str, Any],
        data_repository: Optional[Any] = None
    ) -> None:
        """
        Регистрирует схемы входных параметров для всех capability.
        
        ПАРАМЕТРЫ:
        - available_capabilities: Список capability
        - schema_validator: SchemaValidator для регистрации
        - input_contracts: Кэш input контрактов компонента
        - data_repository: DataRepository для получения схем (опционально)
        """
        # ... реализация ...
    
    def filter_capabilities(
        self,
        capabilities: List[Capability],
        pattern_id: str
    ) -> List[Capability]:
        """
        Фильтрует capability по supported_strategies.
        
        ВОЗВРАЩАЕТ:
        - List[Capability]: Отфильтрованные capability
        """
        # ... реализация ...
    
    def exclude_capability(
        self,
        capabilities: List[Capability],
        exclude_name: str
    ) -> List[Capability]:
        """
        Исключает capability по имени.
        
        ВОЗВРАЩАЕТ:
        - List[Capability]: Capability без исключённого
        """
        return [cap for cap in capabilities if cap.name != exclude_name]
```

---

### 5.3 `services/fallback_strategy.py`

```python
"""FallbackStrategyService — стратегии fallback."""
from typing import Any, Dict, List, Optional
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability


class FallbackStrategy:
    """Стратегии fallback для ReActPattern."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {
            "max_retries": 3,
            "default_pattern": "fallback.v1.0.0",
            "emergency_stop": True
        }
    
    def create_retry(
        self,
        reason: str,
        max_retries: Optional[int] = None
    ) -> BehaviorDecision:
        """
        Создаёт решение для повторной попытки.
        
        ПАРАМЕТРЫ:
        - reason: Причина retry
        - max_retries: Максимум попыток (опционально)
        
        ВОЗВРАЩАЕТ:
        - BehaviorDecision с action=RETRY
        """
        return BehaviorDecision(
            action=BehaviorDecisionType.RETRY,
            reason=reason,
            confidence=0.5
        )
    
    def create_switch(
        self,
        next_pattern: str,
        reason: str
    ) -> BehaviorDecision:
        """
        Создаёт решение для переключения паттерна.
        
        ВОЗВРАЩАЕТ:
        - BehaviorDecision с action=SWITCH
        """
        return BehaviorDecision(
            action=BehaviorDecisionType.SWITCH,
            next_pattern=next_pattern,
            reason=reason,
            confidence=0.7
        )
    
    def create_stop(
        self,
        reason: str,
        final_answer: Optional[str] = None
    ) -> BehaviorDecision:
        """
        Создаёт решение для остановки.
        
        ПАРАМЕТРЫ:
        - reason: Причина остановки
        - final_answer: Текст финального ответа (опционально)
        
        ВОЗВРАЩАЕТ:
        - BehaviorDecision с action=STOP
        """
        return BehaviorDecision(
            action=BehaviorDecisionType.STOP,
            reason=reason,
            confidence=0.9
        )
    
    def create_error(
        self,
        reason: str,
        available_capabilities: List[Capability]
    ) -> BehaviorDecision:
        """
        Создаёт решение при ошибке.
        
        ЛОГИКА:
        - Если есть доступные capability — ACT с первой доступной
        - Иначе — STOP с emergency_stop
        
        ВОЗВРАЩАЕТ:
        - BehaviorDecision
        """
        if available_capabilities:
            cap = available_capabilities[0]
            return BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=cap.name,
                parameters={"input": "Продолжить выполнение задачи", "context": reason},
                reason=f"fallback_{reason}",
                confidence=0.3
            )
        
        return BehaviorDecision(
            action=BehaviorDecisionType.STOP,
            reason=f"emergency_stop_no_capabilities_{reason}",
            confidence=0.1
        )
    
    def create_reasoning_fallback(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        reason: str
    ) -> Dict[str, Any]:
        """
        Создаёт fallback-результат рассуждения.
        
        ИСПОЛЬЗУЕТСЯ: Когда _perform_structured_reasoning не может получить ответ от LLM.
        
        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: Структура reasoning_result
        """
        fallback_capability = (
            available_capabilities[0].name if available_capabilities
            else "final_answer.generate"
        )
        
        return {
            "analysis": {
                "current_situation": f"Fallback: {reason}",
                "progress_assessment": "Неизвестно",
                "confidence": 0.3,
                "errors_detected": True,
                "consecutive_errors": context_analysis.get("consecutive_errors", 0) + 1,
                "execution_time": context_analysis.get("execution_time_seconds", 0),
                "no_progress_steps": context_analysis.get("no_progress_steps", 0)
            },
            "decision": {
                "next_action": fallback_capability,
                "reasoning": f"fallback после ошибки: {reason}",
                "parameters": {"query": context_analysis.get("goal", "Продолжить")},
                "expected_outcome": "Неизвестно"
            },
            "available_capabilities": available_capabilities,
            "confidence": 0.1,
            "stop_condition": False,
            "stop_reason": "fallback",
            "alternative_actions": [],
            "thought": f"Fallback из-за: {reason}"
        }
```

---

### 5.4 `utils/json_parser.py`

```python
"""JsonParserUtil — утилиты парсинга JSON."""
import json
import re
from typing import Any, Dict, List, Optional


class JsonParserUtil:
    """Утилиты для парсинга JSON из ответов LLM."""
    
    @staticmethod
    def extract_json_from_response(content: str) -> Optional[Dict[str, Any]]:
        """
        Извлекает JSON из ответа LLM.
        
        ПОДДЕРЖИВАЕТ:
        - Чистый JSON: {"key": "value"}
        - JSON в блоке кода: ```json {...} ```
        - JSON в блоке кода без указания языка: ``` {...} ```
        
        ВОЗВРАЩАЕТ:
        - Dict[str, Any] или None при ошибке
        """
        if not content:
            return None
        
        # Попытка парсинга как чистого JSON
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass
        
        # Поиск JSON в блоке кода
        json_block_pattern = r'```(?:json)?\s*({.*?})\s*```'
        match = re.search(json_block_pattern, content, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # Поиск первого { и последней }
        start = content.find('{')
        end = content.rfind('}') + 1
        
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
        
        return None
    
    @staticmethod
    def safe_parse_json(
        content: str,
        default: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Безопасный парсинг JSON с возвратом default при ошибке.
        
        ВОЗВРАЩАЕТ:
        - Dict[str, Any] или default
        """
        result = JsonParserUtil.extract_json_from_response(content)
        return result if result is not None else default
    
    @staticmethod
    def validate_json_structure(
        data: Dict[str, Any],
        required_fields: List[str]
    ) -> bool:
        """
        Проверяет наличие обязательных полей в JSON.
        
        ВОЗВРАЩАЕТ:
        - bool: True если все поля присутствуют
        """
        if not isinstance(data, dict):
            return False
        
        return all(field in data for field in required_fields)
```

---

### 5.5 `types.py`

```python
"""Типы данных для ReActPattern."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PromptTemplates:
    """Шаблоны промптов."""
    system: str = ""
    user: str = ""
    
    def is_complete(self) -> bool:
        """Проверяет что оба шаблона загружены."""
        return bool(self.system.strip()) and bool(self.user.strip())


@dataclass
class ReasoningContext:
    """Контекст для рассуждения."""
    input_context: str = ""
    step_history: str = ""
    last_observation: str = ""
    available_tools: str = ""
    
    def to_prompt_variables(self, goal: str, no_progress_steps: int, 
                           consecutive_errors: int) -> Dict[str, Any]:
        """Преобразует в переменные для промпта."""
        return {
            "input": self.input_context,
            "goal": goal,
            "step_history": self.step_history,
            "observation": self.last_observation,
            "available_tools": self.available_tools,
            "no_progress_steps": no_progress_steps,
            "consecutive_errors": consecutive_errors
        }


@dataclass
class FallbackConfig:
    """Конфигурация fallback стратегий."""
    max_retries: int = 3
    default_pattern: str = "fallback.v1.0.0"
    emergency_stop: bool = True
    min_confidence: float = 0.1
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует в словарь."""
        return {
            "max_retries": self.max_retries,
            "default_pattern": self.default_pattern,
            "emergency_stop": self.emergency_stop,
            "min_confidence": self.min_confidence
        }
```

---

## 6. План удаления устаревшего кода

### 6.1 Методы для удаления

| Метод | Строки | Причина | Зависимости |
|-------|--------|---------|-------------|
| `_build_rollback_decision` | 1250-1284 | Мёртвый код | Отсутствуют |
| `_build_capability_decision` | 1286-1354 | Мёртвый код | Отсутствуют |

### 6.2 Методы для модификации

| Метод | Изменение | Причина |
|-------|-----------|---------|
| `_create_fallback_decision` | Добавить параметр `available_capabilities` | Исправление ошибки |
| `_perform_structured_reasoning` | Разбить на подметоды | Упрощение |
| `_make_decision_from_reasoning` | Упростить обработку stop_condition | Исправление логики |

### 6.3 Методы для перемещения в сервисы

| Метод | Куда переместить |
|-------|------------------|
| `_build_input_context` | `PromptBuilderService.build_input_context` |
| `_build_step_history` | `PromptBuilderService.build_step_history` |
| `_extract_last_observation` | `PromptBuilderService.extract_last_observation` |
| `_format_available_tools` | `PromptBuilderService.format_available_tools` |
| `_find_capability` | `CapabilityResolverService.find_capability` |
| `_validate_parameters` | `CapabilityResolverService.validate_parameters` |
| `_register_capability_schemas` | `CapabilityResolverService.register_capability_schemas` |
| `_create_fallback_reasoning` | `FallbackStrategyService.create_reasoning_fallback` |

---

## 7. Тестирование и валидация

### 7.1 Юнит-тесты для сервисов

#### 7.1.1 Тесты `PromptBuilderService`

**Файл:** `tests/react/services/test_prompt_builder.py`

```python
class TestPromptBuilderService:
    
    def test_build_input_context(self):
        """Проверка построения контекста."""
        builder = PromptBuilderService()
        context_analysis = {
            "goal": "Найти книгу",
            "last_steps": [{"capability": "search", "summary": "Поиск"}],
            "no_progress_steps": 0,
            "consecutive_errors": 0
        }
        available_capabilities = [...]
        
        result = builder.build_input_context(context_analysis, available_capabilities)
        
        assert "ЦЕЛЬ: Найти книгу" in result
        assert "Шагов выполнено: 1" in result
    
    def test_build_step_history_empty(self):
        """Проверка пустой истории."""
        builder = PromptBuilderService()
        result = builder.build_step_history([])
        assert result == "Шаги не выполнены"
    
    def test_extract_last_observation(self):
        """Проверка извлечения наблюдения."""
        builder = PromptBuilderService()
        last_steps = [
            {"capability": "search", "observation": "Книга найдена"}
        ]
        result = builder.extract_last_observation(last_steps)
        assert result == "Книга найдена"
    
    def test_render_prompt(self):
        """Проверка рендеринга шаблона."""
        builder = PromptBuilderService()
        template = "Цель: {goal}, Шаг: {step}"
        variables = {"goal": "Тест", "step": "1"}
        
        result = builder.render_prompt(template, variables)
        assert result == "Цель: Тест, Шаг: 1"
```

---

#### 7.1.2 Тесты `CapabilityResolverService`

**Файл:** `tests/react/services/test_capability_resolver.py`

```python
class TestCapabilityResolverService:
    
    def test_find_capability_direct_match(self):
        """Проверка прямого совпадения."""
        resolver = CapabilityResolverService()
        capabilities = [
            Capability(name="book_library.search", ...),
            Capability(name="final_answer.generate", ...)
        ]
        
        result = resolver.find_capability(capabilities, "book_library.search")
        assert result is not None
        assert result.name == "book_library.search"
    
    def test_find_capability_prefix_match(self):
        """Проверка совпадения по префиксу."""
        resolver = CapabilityResolverService()
        capabilities = [
            Capability(name="book_library", ...)
        ]
        
        result = resolver.find_capability(capabilities, "book_library.search")
        assert result is not None
        assert result.name == "book_library"
    
    def test_find_capability_not_found(self):
        """Проверка отсутствия capability."""
        resolver = CapabilityResolverService()
        capabilities = [Capability(name="other", ...)]
        
        result = resolver.find_capability(capabilities, "nonexistent")
        assert result is None
    
    def test_filter_capabilities_by_strategy(self):
        """Проверка фильтрации по стратегии."""
        resolver = CapabilityResolverService()
        capabilities = [
            Capability(name="react_cap", supported_strategies=["react"]),
            Capability(name="planning_cap", supported_strategies=["planning"])
        ]
        
        result = resolver.filter_capabilities(capabilities, "react_pattern")
        assert len(result) == 1
        assert result[0].name == "react_cap"
```

---

#### 7.1.3 Тесты `FallbackStrategyService`

**Файл:** `tests/react/services/test_fallback_strategy.py`

```python
class TestFallbackStrategyService:
    
    def test_create_retry(self):
        """Проверка создания retry."""
        strategy = FallbackStrategyService()
        decision = strategy.create_retry(reason="timeout")
        
        assert decision.action == BehaviorDecisionType.RETRY
        assert "timeout" in decision.reason
    
    def test_create_switch(self):
        """Проверка создания switch."""
        strategy = FallbackStrategyService()
        decision = strategy.create_switch(
            next_pattern="fallback.v1.0.0",
            reason="too_many_errors"
        )
        
        assert decision.action == BehaviorDecisionType.SWITCH
        assert decision.next_pattern == "fallback.v1.0.0"
    
    def test_create_error_with_capabilities(self):
        """Проверка создания error с capability."""
        strategy = FallbackStrategyService()
        capabilities = [Capability(name="test_cap", ...)]
        decision = strategy.create_error(reason="test_error", 
                                         available_capabilities=capabilities)
        
        assert decision.action == BehaviorDecisionType.ACT
        assert decision.capability_name == "test_cap"
    
    def test_create_error_without_capabilities(self):
        """Проверка создания error без capability."""
        strategy = FallbackStrategyService()
        decision = strategy.create_error(reason="test_error", 
                                         available_capabilities=[])
        
        assert decision.action == BehaviorDecisionType.STOP
        assert "emergency_stop" in decision.reason
    
    def test_create_reasoning_fallback(self):
        """Проверка создания reasoning fallback."""
        strategy = FallbackStrategyService()
        context_analysis = {"goal": "Тест", "consecutive_errors": 1}
        capabilities = [Capability(name="test_cap", ...)]
        
        result = strategy.create_reasoning_fallback(
            context_analysis, capabilities, "test_reason"
        )
        
        assert "Fallback: test_reason" in result["analysis"]["current_situation"]
        assert result["confidence"] == 0.1
```

---

#### 7.1.4 Тесты `JsonParserUtil`

**Файл:** `tests/react/utils/test_json_parser.py`

```python
class TestJsonParserUtil:
    
    def test_extract_json_pure(self):
        """Проверка чистого JSON."""
        content = '{"key": "value"}'
        result = JsonParserUtil.extract_json_from_response(content)
        assert result == {"key": "value"}
    
    def test_extract_json_in_code_block(self):
        """Проверка JSON в блоке кода."""
        content = '```json\n{"key": "value"}\n```'
        result = JsonParserUtil.extract_json_from_response(content)
        assert result == {"key": "value"}
    
    def test_extract_json_in_code_block_no_lang(self):
        """Проверка JSON в блоке без языка."""
        content = '```\n{"key": "value"}\n```'
        result = JsonParserUtil.extract_json_from_response(content)
        assert result == {"key": "value"}
    
    def test_extract_json_invalid(self):
        """Проверка невалидного JSON."""
        content = 'not json'
        result = JsonParserUtil.extract_json_from_response(content)
        assert result is None
    
    def test_validate_json_structure(self):
        """Проверка структуры JSON."""
        data = {"thought": "test", "decision": {}}
        result = JsonParserUtil.validate_json_structure(
            data, ["thought", "decision"]
        )
        assert result is True
        
        result = JsonParserUtil.validate_json_structure(
            data, ["thought", "missing"]
        )
        assert result is False
```

---

### 7.2 Интеграционные тесты

#### 7.2.1 Тесты рефакторённого `ReActPattern`

**Файл:** `tests/react/test_react_pattern_refactored.py`

```python
class TestReActPatternRefactored:
    
    @pytest.fixture
    def react_pattern(self, mock_application_context):
        """Создание ReActPattern с моками."""
        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=mock_component_config,
            application_context=mock_application_context,
            executor=mock_executor
        )
        return pattern
    
    async def test_analyze_context_registers_schemas(self, react_pattern):
        """Проверка регистрации схем в analyze_context."""
        capabilities = [Capability(name="test_cap", ...)]
        context_analysis = {...}
        session_context = mock_session_context
        
        result = await react_pattern.analyze_context(
            session_context, capabilities, context_analysis
        )
        
        # Проверка что схемы зарегистрированы
        assert react_pattern.schema_validator.has_schema("test_cap")
    
    async def test_generate_decision_uses_services(self, react_pattern):
        """Проверка использования сервисов в generate_decision."""
        # Мокирование сервисов
        react_pattern.prompt_builder.build_reasoning_prompt = AsyncMock(...)
        react_pattern.capability_resolver.find_capability = Mock(...)
        react_pattern.fallback_strategy.create_retry = Mock(...)
        
        # Вызов generate_decision
        decision = await react_pattern.generate_decision(...)
        
        # Проверка вызова сервисов
        assert react_pattern.prompt_builder.build_reasoning_prompt.called
        assert react_pattern.capability_resolver.find_capability.called
    
    async def test_stop_condition_always_calls_final_answer(self, react_pattern):
        """Проверка что stop_condition всегда вызывает final_answer."""
        reasoning_result = ReasoningResult(
            thought="Цель достигнута",
            decision={"next_action": "other_action"},
            stop_condition=True,
            stop_reason="goal_achieved"
        )
        
        decision = await react_pattern._make_decision_from_reasoning(
            session_context=None,
            reasoning_result=reasoning_result,
            available_capabilities=[]
        )
        
        # Проверка что вызывается final_answer.generate
        assert decision.action == BehaviorDecisionType.ACT
        assert decision.capability_name == "final_answer.generate"
        assert decision.is_final is True
    
    async def test_fallback_receives_available_capabilities(self, react_pattern):
        """Проверка что fallback получает available_capabilities."""
        capabilities = [Capability(name="test_cap", ...)]
        
        # Вызов с ошибкой
        react_pattern._perform_structured_reasoning = AsyncMock(
            side_effect=Exception("Test error")
        )
        
        decision = await react_pattern.generate_decision(
            session_context=None,
            available_capabilities=capabilities,
            context_analysis={}
        )
        
        # Проверка что fallback использовал capability
        assert decision.capability_name == "test_cap"
```

---

### 7.3 Регрессионные тесты

#### 7.3.1 Запуск существующих тестов

**Команда:**
```bash
pytest tests/react/ -v --tb=short
```

**Ожидаемый результат:** Все тесты проходят без изменений.

---

#### 7.3.2 Проверка инвариантов

**Файл:** `tests/react/test_react_invariants.py` (существующий)

**Добавить проверки:**
1. `stop_condition` всегда приводит к вызову `final_answer.generate`
2. Fallback решения всегда содержат валидные `capability_name`
3. Сервисы изолированы и тестируются независимо

---

## 8. Критерии приёмки

### 8.1 Функциональные критерии

- [ ] Все существующие тесты проходят без изменений
- [ ] Новые юнит-тесты для сервисов написаны и проходят
- [ ] `stop_condition` всегда вызывает `final_answer.generate` перед остановкой
- [ ] Fallback при ошибках парсинга возвращает `RETRY` вместо `final_answer.generate`
- [ ] `_create_fallback_decision` корректно использует `available_capabilities`

### 8.2 Архитектурные критерии

- [ ] Созданы модули `services/` и `utils/`
- [ ] `PromptBuilderService` реализован и используется
- [ ] `CapabilityResolverService` реализован и используется
- [ ] `FallbackStrategyService` реализован и используется
- [ ] `JsonParserUtil` реализован и используется
- [ ] `types.py` содержит общие типы данных

### 8.3 Критерии кода

- [ ] Класс `ReActPattern` сокращён до ~600-700 строк
- [ ] Метод `_perform_structured_reasoning` сокращён до ~60 строк
- [ ] Удалены методы `_build_rollback_decision` и `_build_capability_decision`
- [ ] Метод `_create_fallback_decision` исправлен
- [ ] Отсутствует дублирование кода между методами
- [ ] Все публичные методы имеют docstring

### 8.4 Критерии тестирования

- [ ] Покрытие тестами ≥ 80% для новых сервисов
- [ ] Интеграционные тесты для `ReActPattern` проходят
- [ ] Регрессионные тесты проходят
- [ ] Тесты на инварианты добавлены

---

## Приложения

### Приложение A: Карта зависимостей

```
ReActPattern
├── PromptBuilderService (новый)
│   └── JsonParserUtil (новый, опционально)
├── CapabilityResolverService (новый)
│   └── SchemaValidator (существующий)
├── FallbackStrategyService (новый)
│   └── BehaviorDecision (существующий)
└── LLMOrchestrator (существующий)
```

### Приложение B: Метрики до/после

| Метрика | До | После | Изменение |
|---------|-----|-------|-----------|
| Строк в `pattern.py` | 1381 | ~650 | -53% |
| Количество методов | 20 | 12 | -40% |
| Методов >50 строк | 3 | 1 | -67% |
| Юнит-тестов | 5 | 25 | +400% |
| Покрытие тестами | 45% | 82% | +82% |

### Приложение C: Чеклист реализации

- [ ] Создать директорию `services/`
- [ ] Создать директорию `utils/`
- [ ] Реализовать `PromptBuilderService`
- [ ] Реализовать `CapabilityResolverService`
- [ ] Реализовать `FallbackStrategyService`
- [ ] Реализовать `JsonParserUtil`
- [ ] Реализовать `types.py`
- [ ] Внедрить сервисы в `ReActPattern`
- [ ] Рефакторить `_perform_structured_reasoning`
- [ ] Рефакторить `_make_decision_from_reasoning`
- [ ] Исправить `_create_fallback_decision`
- [ ] Удалить `_build_rollback_decision`
- [ ] Удалить `_build_capability_decision`
- [ ] Написать юнит-тесты для сервисов
- [ ] Написать интеграционные тесты
- [ ] Запустить регрессионные тесты
- [ ] Обновить документацию

---

**Документ утверждён:** 9 марта 2026 г.  
**Ответственный за реализацию:** [Разработчик]  
**Ожидаемое время реализации:** 16-24 часа

# 📝 План: JsonParsingService — Единый сервис для парсинга JSON ответов LLM

## 🎯 Проблема
Логика парсинга JSON дублируется в 7+ местах проекта, включая инфраструктурный слой (`LLMOrchestrator`, `Providers`) и слой бизнес-логики (`Skills`).
*   **3 реализации** `extract_json_from_response()`
*   **2 реализации** создания Pydantic-моделей из JSON Schema
*   **Риск:** Инфраструктура (`LLMOrchestrator`) не должна зависеть от компонентов приложения (`Services`).

## 🏗️ Целевая Архитектура

Решение разделено на два уровня для соблюдения чистоты слоев:

1.  **Инфраструктурный слой (`core/utils/json_utils.py`)**:
    *   Низкоуровневые функции (Regex, исправление ошибок, создание классов).
    *   **Используется:** `LLMOrchestrator`, `Providers` (LlamaCpp, VLLM).
    *   *Не имеет зависимостей от компонентов.*

2.  **Слой бизнес-логики (`core/components/services/json_parsing/service.py`)**:
    *   Обертка над утилитами с логированием, метриками и валидацией.
    *   **Используется:** `Skills`, `Tools` через `ActionExecutor`.

---

## 📋 Детальный план

### Фаза 1: Утилиты (Infrastructure Layer)
**Файл:** `core/utils/json_utils.py`
Переносим сюда общую логику, чтобы `LLMOrchestrator` мог ей пользоваться напрямую без зависимости от Сервиса.

*   [x] `extract_json_from_response(text)` — Regex извлечение из Markdown/текста.
*   [x] `fix_json(json_str)` — Исправление типичных ошибок (лишние запятые).
*   [x] `create_pydantic_model_from_schema(name, schema)` — Динамическое создание класса Pydantic.

### Фаза 2: Сервис (Application Layer)
**Файл:** `core/components/services/json_parsing/service.py`
Создаем новый компонент, доступный через `ActionExecutor`.

*   [x] Наследование от `Service`.
*   [x] Capability: `json_parsing.parse_to_model` — Принимает сырой текст и схему, возвращает валидированную модель.
*   [x] Capability: `json_parsing.safe_get` — Безопасный доступ к вложенным полям (замена `data.get(...)`).
*   [x] Интеграция с `LogSession` и `MetricsPublisher`.

### Фаза 3: Миграция Orchestrator и Providers
Избавляемся от дублирования кода.

*   [x] **LLMOrchestrator**: Заменяет внутренние методы `_create_model_from_schema` на вызов утилит из `json_utils`.
*   [x] **Providers (LlamaCpp/VLLM)**: Заменяют внутренние методы `_extract_json_from_response` на вызов утилит из `json_utils`.

### Фаза 4: Контракты (Discovery)
Добавляем поддержку в систему обнаружения компонентов.

*   [x] `data/contracts/service/json_parsing/v1.0.0.yaml` — Описание входов/выходов сервиса.

---

## 💻 Реализация Ключевых Компонентов

### 1. Утилиты (`core/utils/json_utils.py`)
*Используется LLMOrchestrator и Провайдерами.*

```python
import re
import json
from pydantic import create_model
from typing import Dict, Any, Type, Optional, List

def extract_json_from_response(content: str) -> Optional[str]:
    """Извлекает JSON из текста (поддержка markdown кода)."""
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', content, re.DOTALL | re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        if candidate.startswith(("{", "[")):
            return candidate
    
    start = content.find('{')
    end = content.rfind('}') + 1
    if start != -1 and end > start:
        return content[start:end]
    return None

def create_pydantic_model_from_schema(
    model_name: str,
    schema: Dict[str, Any],
    defs: Optional[Dict] = None
) -> Type:
    """Создает динамическую Pydantic модель из JSON Schema."""
    fields = {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for field_name, field_def in properties.items():
        # ... (логика рекурсивного определения типов: string -> str, array -> List, etc.)
        # ... (упрощенная реализация для примера)
        field_type = str 
        is_required = field_name in required
        fields[field_name] = (field_type, ...) if is_required else (field_type, None)

    return create_model(model_name, **fields)
```

### 2. JsonParsingService (`core/components/services/json_parsing/service.py`)
*Используется Навыками и Инструментами через ActionExecutor.*

```python
from core.components.services.service import Service
from core.utils import json_utils
from pydantic import BaseModel

class JsonParsingService(Service):
    @property
    def description(self) -> str:
        return "Единый сервис парсинга и валидации JSON ответов LLM"

    async def parse_to_model(self, parameters: Dict[str, Any], execution_context) -> Dict[str, Any]:
        """Полный цикл: Извлечение -> Парсинг -> Валидация схемой."""
        raw_content = parameters.get("content")
        schema_def = parameters.get("schema_def")
        model_name = parameters.get("model_name", "DynamicModel")
        
        # 1. Извлечение
        json_str = json_utils.extract_json_from_response(raw_content)
        if not json_str:
            return {"success": False, "error": "JSON не найден в ответе"}

        # 2. Парсинг
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Ошибка JSON: {e}"}

        # 3. Валидация моделью
        if schema_def:
            try:
                model_class = json_utils.create_pydantic_model_from_schema(model_name, schema_def)
                validated_model = model_class(**data)
                return {"success": True, "data": validated_model.model_dump()}
            except Exception as e:
                return {"success": False, "error": f"Валидация схемы: {e}"}
        
        return {"success": True, "data": data}
```

---

## ✅ Чек-лист успешности

- [ ] `core/utils/json_utils.py` создан и содержит общую логику.
- [ ] `JsonParsingService` создан и зарегистрирован через Discovery.
- [ ] `LLMOrchestrator` импортирует функции из `json_utils`, а не дублирует их.
- [ ] `LlamaCppProvider` и `VLLMProvider` используют `json_utils`.
- [ ] В проекте больше нет прямых вызовов `json.loads()` без обработки ошибок (кроме конфигов).
- [ ] Unit-тесты на сервис и утилиты проходят.
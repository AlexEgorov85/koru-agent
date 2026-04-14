"""
LLM Planner — планирование аналитики через LLM.

ОТВЕТСТВЕННОСТЬ:
- Получение схемы данных и вопроса от пользователя
- Генерация промпта для LLM с инструкциями по созданию DSL
- Парсинг JSON DSL ответа от LLM
- Валидация DSL спецификации

НЕ ОТВЕТСТВЕННОСТЬ:
- Выполнение операций (это AnalyticsEngine)
- Прямой вызов LLM (через executor)
- Обработка сырых данных

АРХИТЕКТУРА:
- LLM получает схему данных (не все данные)
- Возвращает JSON DSL для AnalyticsEngine
- Код НЕ генерируется (только декларативные операции)

ПРИМЕР DSL:
{
    "reasoning": "Нужно отфильтровать продажи >1000 и сгруппировать по региону",
    "operations": [
        {"type": "filter", "conditions": [{"column": "amount", "operator": "gt", "value": 1000}]},
        {"type": "group_by", "columns": ["region"], "metrics": [{"column": "amount", "func": "sum", "alias": "total_sales"}]},
        {"type": "sort", "column": "total_sales", "order": "desc"}
    ]
}
"""
from typing import Dict, Any, Optional, List


class LLMPlanner:
    """
    Планировщик операций через LLM.

    АРХИТЕКТУРА:
    - Принимает схему данных и вопрос
    - Генерирует промпт для LLM
    - Парсит JSON DSL ответ
    - Валидирует спецификацию

    ВАЖНО:
    - LLM НЕ генерирует код
    - LLM выбирает только из разрешённых операций
    - Все параметры строго типизированы
    """

    # Разрешённые операции и их параметры
    ALLOWED_OPERATIONS = {
        "filter": {
            "conditions": {
                "type": "list",
                "items": {
                    "column": "string",
                    "operator": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "not_null", "is_null"],
                    "value": "any"
                }
            }
        },
        "group_by": {
            "columns": {"type": "list[string]"},
            "metrics": {
                "type": "list",
                "items": {
                    "column": "string",
                    "func": ["count", "sum", "mean", "min", "max", "median", "unique"],
                    "alias": "string"
                }
            }
        },
        "aggregate": {
            "metrics": {
                "type": "list",
                "items": {
                    "column": "string",
                    "func": ["count", "sum", "mean", "min", "max", "median", "unique"],
                    "alias": "string"
                }
            }
        },
        "sort": {
            "column": "string",
            "order": ["asc", "desc"]
        },
        "limit": {
            "n": "integer"
        },
        "select": {
            "columns": {"type": "list[string]"}
        },
        "describe": {}
    }

    @staticmethod
    def build_planner_prompt(
        data_schema: Dict[str, Any],
        question: str,
        context: Optional[str] = None
    ) -> str:
        """
        Построение промпта для LLM-планировщика.

        АРХИТЕКТУРА:
        1. Показываем схему данных (не сами данные)
        2. Задаём вопрос пользователя
        3. Даем инструкции по созданию DSL
        4. Требует JSON ответ

        ARGS:
        - data_schema: Dict — схема данных от DataProfiler
        - question: str — вопрос пользователя
        - context: str — дополнительный контекст

        RETURNS:
        - str — готовый промпт для LLM

        EXAMPLE:
        >>> prompt = LLMPlanner.build_planner_prompt(schema, "Какие продажи по регионам?")
        >>> # LLM вернёт JSON DSL
        """
        schema_str = _format_schema_for_prompt(data_schema)

        context_section = ""
        if context:
            context_section = f"\n### КОНТЕКСТ\n{context}\n"

        prompt = f"""### ЗАДАЧА
Ты — планировщик аналитики данных. Твоя задача — преобразовать вопрос пользователя в JSON DSL спецификацию для выполнения аналитических операций.

### СХЕМА ДАННЫХ
{schema_str}

### ВОПРОС ПОЛЬЗОВАТЕЛЯ
{question}
{context_section}
### ИНСТРУКЦИИ

1. **ПРОАНАЛИЗИРУЙ** вопрос и схему данных
2. **ВЫБЕРИ** необходимые операции из списка:
   - `filter`: фильтрация строк по условиям
   - `group_by`: группировка с агрегацией
   - `aggregate`: агрегация всего датасета
   - `sort`: сортировка результатов
   - `limit`: ограничение количества строк
   - `select`: выбор конкретных колонок
   - `describe`: статистическое описание данных

3. **СОЗДАЙ** JSON DSL со структурой:
```json
{{
    "reasoning": "Объясни, почему выбраны эти операции",
    "operations": [
        {{
            "type": "filter",
            "conditions": [
                {{"column": "column_name", "operator": "gt", "value": 100}}
            ]
        }},
        {{
            "type": "group_by",
            "columns": ["category"],
            "metrics": [
                {{"column": "price", "func": "sum", "alias": "total_price"}}
            ]
        }}
    ]
}}
```

4. **ПРАВИЛА**:
   - Используй ТОЛЬКО разрешённые операторы: eq, ne, gt, gte, lt, lte, in, contains, not_null, is_null
   - Используй ТОЛЬКО разрешённые метрики: count, sum, mean, min, max, median, unique
   - Все имена колонок должны точно соответствовать схеме
   - Для сортировки order: "asc" или "desc"
   - Не генерируй Python-код — только декларативный JSON DSL

### ОТВЕТ
Верни ТОЛЬКО JSON (без markdown, без комментариев):"""

        return prompt

    @staticmethod
    def validate_dsl(dsl_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидация DSL спецификации от LLM.

        ПРОВЕРКИ:
        - Наличие обязательных полей (operations)
        - Допустимые типы операций
        - Корректные имена колонок (по схеме если доступна)
        - Допустимые операторы и метрики
        - Типы параметров

        ARGS:
        - dsl_spec: Dict — DSL спецификация от LLM

        RETURNS:
        - Dict с результатом валидации:
          {"valid": True, "errors": []} или
          {"valid": False, "errors": ["..."]}

        EXAMPLE:
        >>> result = LLMPlanner.validate_dsl(dsl)
        >>> if not result["valid"]:
        ...     raise ValueError(result["errors"])
        """
        errors = []

        # Проверка структуры
        if "operations" not in dsl_spec:
            return {
                "valid": False,
                "errors": ["Отсутствует обязательное поле 'operations'"]
            }

        operations = dsl_spec["operations"]
        if not isinstance(operations, list):
            return {
                "valid": False,
                "errors": ["'operations' должен быть списком"]
            }

        if len(operations) == 0:
            return {
                "valid": False,
                "errors": ["Список operations пуст"]
            }

        # Валидация каждой операции
        for i, op in enumerate(operations):
            if "type" not in op:
                errors.append(f"Операция #{i}: отсутствует поле 'type'")
                continue

            op_type = op["type"]
            if op_type not in LLMPlanner.ALLOWED_OPERATIONS:
                errors.append(f"Операция #{i}: неподдерживаемый тип '{op_type}'. Разрешены: {list(LLMPlanner.ALLOWED_OPERATIONS.keys())}")
                continue

            # Валидация параметров операции
            schema = LLMPlanner.ALLOWED_OPERATIONS[op_type]
            LLMPlanner._validate_operation(op, schema, errors, i)

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    @staticmethod
    def _validate_operation(
        op: Dict[str, Any],
        schema: Dict[str, Any],
        errors: List[str],
        op_index: int
    ) -> None:
        """Валидация одной операции по схеме."""
        prefix = f"Операция #{op_index} ({op['type']})"

        for param_name, param_schema in schema.items():
            if param_name not in op:
                # Проверяем обязательность
                if isinstance(param_schema, dict) and param_schema.get("required", False):
                    errors.append(f"{prefix}: отсутствует обязательный параметр '{param_name}'")
                continue

            value = op[param_name]

            # Валидация типа
            if isinstance(param_schema, str):
                expected_type = param_schema
                if expected_type == "integer" and not isinstance(value, int):
                    errors.append(f"{prefix}: '{param_name}' должен быть integer, получен {type(value).__name__}")
                elif expected_type == "string" and not isinstance(value, str):
                    errors.append(f"{prefix}: '{param_name}' должен быть string, получен {type(value).__name__}")

            elif isinstance(param_schema, list):
                # enum validation
                if value not in param_schema:
                    errors.append(f"{prefix}: '{param_name}' должен быть одним из {param_schema}, получен '{value}'")

            elif isinstance(param_schema, dict):
                if param_schema.get("type") == "list":
                    if not isinstance(value, list):
                        errors.append(f"{prefix}: '{param_name}' должен быть списком")
                    elif "items" in param_schema:
                        # Валидация элементов списка
                        items_schema = param_schema["items"]
                        for j, item in enumerate(value):
                            if isinstance(items_schema, dict):
                                # Валидация dict-элементов
                                for field_name, field_type in items_schema.items():
                                    if isinstance(field_type, list):
                                        # enum validation
                                        if field_name in item and item[field_name] not in field_type:
                                            errors.append(f"{prefix}: {param_name}[{j}].{field_name} должен быть одним из {field_type}")
                                    elif field_type == "string" and field_name in item and not isinstance(item[field_name], str):
                                        errors.append(f"{prefix}: {param_name}[{j}].{field_name} должен быть string")
                                    elif field_type == "any":
                                        pass  # any type is valid
                                    elif field_type == "integer" and field_name in item and not isinstance(item[field_name], (int, float)):
                                        errors.append(f"{prefix}: {param_name}[{j}].{field_name} должен быть числом")


def _format_schema_for_prompt(schema: Dict[str, Any]) -> str:
    """
    Форматирование схемы данных для вставки в промпт.

    ARGS:
    - schema: Dict — схема от DataProfiler

    RETURNS:
    - str — читаемое представление схемы
    """
    if not schema:
        return "Схема данных отсутствует"

    if schema.get("type") == "tabular":
        profile = schema.get("profile", {})
        lines = [
            f"Тип: табличные данные",
            f"Строк: {profile.get('row_count', 0)}",
            f"Колонок: {len(profile.get('columns', []))}",
            ""
        ]

        for col in profile.get("columns", []):
            col_lines = [
                f"  - {col['name']} ({col['type']})",
            ]
            if col.get("nullable"):
                col_lines.append(f"    Пропуски: {col.get('null_count', 0)}")
            if col.get("stats"):
                stats = col["stats"]
                col_lines.append(f"    Статистика: min={stats.get('min')}, max={stats.get('max')}, mean={stats.get('mean')}")
            if col.get("sample_values"):
                samples = col["sample_values"][:3]
                col_lines.append(f"    Примеры: {samples}")
            
            lines.extend(col_lines)

        return "\n".join(lines)

    elif schema.get("type") == "text":
        profile = schema.get("profile", {})
        return (
            f"Тип: текстовые данные\n"
            f"Символов: {profile.get('char_count', 0)}\n"
            f"Слов: {profile.get('word_count', 0)}\n"
            f"Строк: {profile.get('line_count', 0)}\n"
            f"Токенов (оценка): {profile.get('estimated_tokens', 0)}\n"
            f"Есть структура: {'Да' if profile.get('has_structure') else 'Нет'}"
        )

    return str(schema)

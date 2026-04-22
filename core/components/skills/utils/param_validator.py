"""
Универсальный валидатор параметров с 3 ступенями:

ПАЙПЛАЙН:
┌─────────────────────────────────────────────────────────────┐
│  ШАГ 1: Enum ИЛИ SQL ILIKE (развилка)                    │
│  ├── type="enum" → проверка по списку allowed_values      │
│  └── type="search" → SQL ILIKE поиск в БД                │
│      Что быстрее найдёт — то и возвращаем                  │
├─────────────────────────────────────────────────────────────┤
│  ШАГ 2: Vector search (если ШАГ 1 не нашёл)              │
│  └── Семантический поиск через FAISS                       │
├─────────────────────────────────────────────────────────────┤
│  ШАГ 3: Fuzzy matching (если ШАГ 2 не нашёл)             │
│  └── Расстояние Левенштейна                               │
└─────────────────────────────────────────────────────────────┘

ВАЖНО: Валидация НЕ БЛОКИРУЕТ выполнение.
- Найдено → corrected_value
- Не найдено → warning + suggestions (продолжаем с исходным)

ИСПОЛЬЗОВАНИЕ:
```python
from core.components.skills.utils.param_validator import ParamValidator

validator = ParamValidator(executor)
result = await validator.validate(
    param_value="Пушкин",
    config={
        "table": "authors",
        "search_fields": ["first_name", "last_name"],
    }
)
# result = {"valid": True, "corrected_value": "Пушкин А.С.", "warning": None, "suggestions": []}
```

=============================================================================
КОНФИГУРАЦИЯ VECTOR SEARCH
=============================================================================

Для работы 2-й ступени валидации (Vector search) нужны FAISS индексы.

НАСТРОЙКА В INFRASTRUCTURE:

1. В infra config (data/config/defaults/dev.yaml):
```yaml
infrastructure:
  vector_providers:
    books:
      provider_type: faiss
      index_type: Flat
      dimension: 384
      source_table: Lib.books
      source_column: title
    authors:
      provider_type: faiss
      index_type: Flat
      dimension: 384
      source_table: Lib.authors
      source_column: last_name
    genres:
      provider_type: faiss
      index_type: Flat
      dimension: 384
      source_table: Lib.genres
      source_column: name
```

2. Инициализация FAISS провайдеров в InfraConfig:
```python
# Пример инициализации
faiss_provider = FaissProvider('authors', dimension=384)
infra.set_faiss_provider('authors', faiss_provider)
```

3. Создание индексов (однократно):
```python
# Загрузка данных в индекс
for author in get_all_authors():
    embedding = embedding_provider.get_embedding(author)
    faiss_provider.add(embedding)
faiss_provider.save()
```

ДОСТУПНЫЕ SOURCE (параметр source в vector_search.search):
- "books" — индекс названий книг
- "authors" — индекс авторов (фамилии)
- "genres" — индекс жанров
- "audits" — индекс аудиторских проверок
- "violations" — индекс отклонений
- Любой другой — должен быть зарегистрирован в infrastructure

ЕСЛИ ИНДЕКС НЕ СУЩЕСТВУЕТ:
- Валидация через vector search пропускается (fallback на следующую ступень)
- Логируется warning: "Vector validation failed: ..."
- Это НЕ ошибка — валидация продолжает 3-ю ступень (Fuzzy)

=============================================================================
КОНФИГУРАЦИЯ СКРИПТОВ
=============================================================================

Пример конфигурации валидации в скрипте:
```python
SCRIPTS_REGISTRY = {
    "get_books_by_author": {
        "sql": "SELECT ... WHERE author_id = %s",
        "parameters": {
            "author": {
                "type": "like",
                "required": True,
                "description": "Фамилия автора",
                "validation": {
                    "table": "authors",           # Таблица для SQL валидации
                    "search_fields": ["first_name", "last_name"],  # Поля для поиска
                    "vector_source": "authors",   # Source для vector search
                    "vector_min_score": 0.7,     # (опционально) мин. score
                    "vector_top_k": 3,           # (опционально) кол-во результатов
                }
            }
        }
    },
    "get_violations_by_status": {
        "sql": "SELECT ... WHERE status = %s",
        "parameters": {
            "status": {
                "type": "like",
                "required": True,
                "description": "Статус отклонения",
                "validation": {
                    "type": "enum",
                    "allowed_values": ["Открыто", "В работе", "Устранено", "На проверке"]
                }
            }
        }
    }
}
```

ТИПЫ ВАЛИДАЦИИ:
- type="enum": Проверка по списку allowed_values (быстро, без БД)
- type="search": SQL → Vector → Fuzzy (по умолчанию, если указан table)

ПОЛЯ КОНФИГУРАЦИИ (для type="search"):
- table: Имя таблицы в БД (без схемы)
- search_fields: Список полей для SQL ILIKE поиска
- vector_source: Имя FAISS индекса (source для vector_search.search)
- vector_min_score: (опционально) мин. score для vector matching (по умолч. 0.7)
- vector_top_k: (опционально) кол-во результатов для vector search (по умолч. 3)

ПОЛЯ КОНФИГУРАЦИИ (для type="enum"):
- allowed_values: Список допустимых значений (case-insensitive проверка)
"""

from typing import Dict, Any, List, Optional
from core.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus


def levenshtein_distance(s1: str, s2: str) -> int:
    """Расстояние Левенштейна между строками"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def fuzzy_match(value: str, candidates: List[str], max_distance: int = 2) -> Optional[str]:
    """Нечёткое совпадение значения со списком кандидатов"""
    if not value or not candidates:
        return None
    
    value_lower = value.lower().strip()
    value_words = value_lower.split()
    value_last = value_words[-1] if value_words else value_lower
    
    best_match = None
    best_distance = max_distance + 1
    
    for candidate in candidates:
        if not candidate:
            continue
        candidate_lower = candidate.lower().strip()
        candidate_words = candidate_lower.split()
        
        for word in candidate_words:
            dist = levenshtein_distance(value_lower, word)
            if dist <= max_distance and dist < best_distance:
                best_distance = dist
                best_match = candidate
                break
            
            dist_last = levenshtein_distance(value_last, word)
            if dist_last <= max_distance and dist_last < best_distance:
                best_distance = dist_last
                best_match = candidate
                break
    
    return best_match


class ParamValidator:
    """
    Универсальный валидатор параметров с 3 ступенями.
    
    АРХИТЕКТУРА:
    - executor: ActionExecutor для выполнения запросов
    - schema: имя схемы БД (по умолчанию "Lib")
    - log_callback: функция для логирования
    """

    def __init__(
        self,
        executor,
        schema: Optional[str] = None,
        log_callback=None
    ):
        self.executor = executor
        self.schema = schema  # None = без указания схемы (public)
        self._log_callback = log_callback

    async def _safe_log(self, message: str) -> None:
        """Безопасное логирование (async-safe)."""
        if self._log_callback:
            result = self._log_callback(message)
            if hasattr(result, '__await__'):
                await result
            # else: sync функция, просто вызываем

    async def validate(
        self,
        param_value: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Валидация параметра.

        ПАЙПЛАЙН (3 ступени):
        1. Enum ИЛИ SQL ILIKE — что-то одно (что быстрее найдёт)
        2. Vector search — если не найдено на шаге 1
        3. Fuzzy matching — если не найдено на шаге 2

        ВАЖНО: Валидация НЕ БЛОКИРУЕТ выполнение.
        - Найдено → corrected_value
        - Не найдено → warning + suggestions (продолжаем с исходным)

        ARGS:
        - param_value: значение для валидации
        - config: конфигурация валидации
            {
                "type": "enum" | "search",       # тип валидации
                "allowed_values": [...],          # для type="enum"
                "table": "authors",               # для type="search"
                "search_fields": [...],
                "vector_source": "authors"
            }

        RETURNS:
        - Dict с ключами: valid (всегда True), corrected_value, warning, suggestions
        """
        # =========================================================
        # ШАГ 1: Enum ИЛИ SQL ILIKE (развилка)
        # =========================================================
        validation_type = config.get("type", "search")
        table = config.get("table", "")
        search_fields = config.get("search_fields", [])

        # 1a. Enum — быстрая проверка по списку
        enum_suggestions = []
        if validation_type == "enum":
            result = await self._validate_enum(param_value, config)
            if result.get("corrected_value") is not None:
                return result
            # Сохраняем suggestions от enum на случай если ничего не найдётся
            enum_suggestions = result.get("suggestions", [])

        # 1b. SQL ILIKE — поиск точного совпадения в БД
        if table and search_fields:
            try:
                result = await self._validate_sql(param_value, table, search_fields)
                if result.get("corrected_value") is not None:
                    return result
            except Exception as e:
                await self._safe_log(f"SQL validation failed: {e}")

        # =========================================================
        # ШАГ 2: Vector search — семантический поиск
        # =========================================================
        # vector_source должен быть явно указан в config
        if "vector_source" in config:
            try:
                result = await self._validate_vector(param_value, config["vector_source"], config)
                if result.get("corrected_value") is not None:
                    return result
            except Exception as e:
                await self._safe_log(f"Vector validation failed: {e}")

        # =========================================================
        # ШАГ 3: Fuzzy matching — нечёткое совпадение
        # =========================================================
        if table and search_fields:
            try:
                result = await self._validate_fuzzy(param_value, table, search_fields)
                if result.get("corrected_value") is not None:
                    return result
            except Exception as e:
                await self._safe_log(f"Fuzzy validation failed: {e}")

        # Ничего не найдено — возвращаем suggestions от enum если были
        return {
            "valid": True,
            "corrected_value": None,
            "warning": f"'{param_value}' не найдено в БД",
            "suggestions": enum_suggestions
        }

    async def _validate_enum(
        self,
        param_value: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ступень 1: Проверка по списку допустимых значений"""
        allowed_values = config.get("allowed_values", [])
        if not allowed_values:
            return {"valid": True, "corrected_value": None, "warning": None, "suggestions": []}

        # Case-insensitive проверка
        value_lower = str(param_value).lower().strip()
        for allowed in allowed_values:
            if str(allowed).lower().strip() == value_lower:
                # Точное совпадение — используем каноническое значение
                return {
                    "valid": True,
                    "corrected_value": allowed,
                    "warning": None,
                    "suggestions": []
                }

        # Не найдено — warning, но НЕ ошибка
        return {
            "valid": True,  # НЕ блокируем!
            "corrected_value": None,
            "warning": f"'{param_value}' не в списке допустимых значений: {allowed_values}",
            "suggestions": list(allowed_values)
        }

    async def _validate_sql(
        self,
        param_value: str,
        table: str,
        search_fields: List[str]
    ) -> Dict[str, Any]:
        """Ступень 1: SQL ILIKE поиск"""
        exec_context = ExecutionContext()
        search_term = param_value.lower().strip()

        where_clauses = [f'"{field}" ILIKE %s' for field in search_fields]
        where_sql = " OR ".join(where_clauses)

        # Если схема указана — используем её, иначе — public
        table_ref = f'"{self.schema}"."{table}"' if self.schema else f'"{table}"'
        sql = f'SELECT DISTINCT "{search_fields[0]}" FROM {table_ref} WHERE {where_sql} LIMIT 5'
        params = [f"%{search_term}%"] * len(search_fields)

        result = await self.executor.execute_action(
            action_name="sql_query.execute",
            parameters={"sql": sql, "parameters": params},
            context=exec_context
        )

        if result.status == ExecutionStatus.COMPLETED and result.data:
            rows = result.data.rows if hasattr(result.data, 'rows') else []
            if rows:
                first_value = rows[0][0] if hasattr(rows[0], '__getitem__') else str(rows[0])
                return {"valid": True, "corrected_value": first_value, "warning": None, "suggestions": []}

        return {"valid": True, "corrected_value": None, "warning": None, "suggestions": []}

    async def _validate_vector(
        self,
        param_value: str,
        vector_source: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ступень 2: Vector search"""
        exec_context = ExecutionContext()

        min_score = config.get("vector_min_score", 0.7)
        top_k = config.get("vector_top_k", 3)

        result = await self.executor.execute_action(
            action_name="vector_search.search",
            parameters={
                "query": param_value,
                "top_k": top_k,
                "min_score": min_score,
                "source": vector_source
            },
            context=exec_context
        )

        if result.status == ExecutionStatus.COMPLETED and result.data:
            inner_data = result.data
            # VectorSearchTool возвращает {"results": [...], "total_found": N}
            if isinstance(inner_data, dict):
                results = inner_data.get("results", [])
            elif hasattr(inner_data, "data"):
                nested = inner_data.data
                results = nested.get("results", []) if isinstance(nested, dict) else (nested if isinstance(nested, list) else [])
            elif hasattr(inner_data, "results"):
                results = inner_data.results
            else:
                results = inner_data if isinstance(inner_data, list) else []

            if results:
                best = results[0]
                metadata = best.get("metadata", {})
                score = best.get("score", 0)

                # Определяем поле с именем по source
                if vector_source == "authors":
                    found_value = metadata.get("author", metadata.get("author_name", 
                        metadata.get("last_name", metadata.get("name", ""))))
                elif vector_source == "genres":
                    found_value = metadata.get("genre_name", metadata.get("name", ""))
                elif vector_source == "audits":
                    found_value = metadata.get("title", metadata.get("audit_title", ""))
                elif vector_source == "violations":
                    found_value = metadata.get("violation_code", metadata.get("description", ""))
                else:
                    found_value = metadata.get("name", metadata.get("title", ""))

                if score >= min_score and found_value:
                    return {"valid": True, "corrected_value": found_value, "warning": None, "suggestions": []}

        return {"valid": True, "corrected_value": None, "warning": None, "suggestions": []}

    async def _validate_fuzzy(
        self,
        param_value: str,
        table: str,
        search_fields: List[str]
    ) -> Dict[str, Any]:
        """Ступень 3: Fuzzy matching"""
        exec_context = ExecutionContext()

        field = search_fields[0]
        table_ref = f'"{self.schema}"."{table}"' if self.schema else f'"{table}"'
        sql = f'SELECT DISTINCT "{field}" FROM {table_ref} ORDER BY "{field}"'

        result = await self.executor.execute_action(
            action_name="sql_query.execute",
            parameters={"sql": sql, "parameters": []},
            context=exec_context
        )

        if result.status == ExecutionStatus.COMPLETED and result.data:
            rows = result.data.rows if hasattr(result.data, 'rows') else []
            all_values = [row[0] if hasattr(row, '__getitem__') else str(row) for row in rows]

            matched = fuzzy_match(param_value, all_values, max_distance=2)
            if matched:
                return {"valid": True, "corrected_value": matched, "warning": None, "suggestions": []}

        return {
            "valid": True,  # НЕ блокируем!
            "corrected_value": None,
            "warning": f"'{param_value}' не найдено",
            "suggestions": []
        }

    async def validate_multiple(
        self,
        params: Dict[str, Any],
        validation_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Валидация нескольких параметров.

        АРХИТЕКТУРА: Валидация НЕ БЛОКИРУЕТ выполнение.
        Все warnings собираются, но выполнение продолжается.

        ARGS:
        - params: {"param_name": value, ...}
        - validation_config: {"param_name": config, ...}

        RETURNS:
        - Dict с ключами: valid (всегда True), corrected_params, warnings, suggestions
        """
        result = {
            "valid": True,
            "corrected_params": {},
            "warnings": [],
            "suggestions": {}
        }

        for param_name, param_config in validation_config.items():
            if param_name not in params:
                continue

            param_value = params[param_name]
            if not param_value:
                continue

            validation = await self.validate(param_value, param_config)

            # Собираем warnings (НЕ блокируем!)
            warning = validation.get("warning")
            if warning:
                result["warnings"].append(f"Параметр '{param_name}': {warning}")
                result["suggestions"][param_name] = validation.get("suggestions", [])

            corrected = validation.get("corrected_value")
            if corrected and corrected != param_value:
                result["corrected_params"][param_name] = corrected
                result["warnings"].append(f"✏️ Исправлена опечатка: '{param_value}' → '{corrected}'")

        return result
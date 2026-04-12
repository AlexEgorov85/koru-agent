"""
Универсальный валидатор параметров с 3 ступенями:
1. SQL ILIKE поиск
2. Vector search
3. Fuzzy matching

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
# result = {"valid": True, "corrected_value": "Пушкин А.С.", "suggestions": []}
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

ДОСТУПНЫЕ SOURCE (параметр source в vector_books.search):
- "books" — индекс названий книг
- "authors" — индекс авторов (фамилии)
- "genres" — индекс жанров
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
        "validation": {
            "author": {
                "table": "authors",           # Таблица для SQL валидации
                "search_fields": ["first_name", "last_name"],  # Поля для поиска
                "vector_source": "authors",   # Source для vector search
                "vector_min_score": 0.7,     # (опционально) мин. score
                "vector_top_k": 3,           # (опционально) кол-во результатов
            }
        }
    }
}
```

ПОЛЯ КОНФИГУРАЦИИ:
- table: Имя таблицы в БД (без схемы)
- search_fields: Список полей для SQL ILIKE поиска
- vector_source: Имя FAISS индекса (source для vector_books.search)
- vector_min_score: (опционально) мин. score для vector matching (по умолч. 0.7)
- vector_top_k: (опционально) кол-во результатов для vector search (по умолч. 3)
"""

from typing import Dict, Any, List, Optional
from core.agent.components.action_executor import ExecutionContext
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
        self._log = log_callback or (lambda x: None)

    async def validate(
        self,
        param_value: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Валидация параметра с 3 ступенями.

        ARGS:
        - param_value: значение для валидации
        - config: конфигурация валидации
            {
                "table": "authors",      # имя таблицы
                "field": "last_name",     # основное поле (для возврата)
                "search_fields": ["first_name", "last_name"],  # поля для поиска
                "vector_source": "authors"  # (опционально) source для vector search
            }

        RETURNS:
        - Dict с ключами: valid, corrected_value, error, suggestions
        """
        table = config.get("table", "")
        search_fields = config.get("search_fields", [])
        vector_source = config.get("vector_source", table)

        if not table or not search_fields:
            return {"valid": True, "suggestions": []}

        # Ступень 1: SQL ILIKE
        try:
            result = await self._validate_sql(param_value, table, search_fields)
            if result["valid"]:
                return result
        except Exception as e:
            await self._log(f"SQL validation failed: {e}")

        # Ступень 2: Vector search
        try:
            result = await self._validate_vector(param_value, vector_source, config)
            if result["valid"]:
                return result
        except Exception as e:
            await self._log(f"Vector validation failed: {e}")

        # Ступень 3: Fuzzy matching
        try:
            return await self._validate_fuzzy(param_value, table, search_fields)
        except Exception as e:
            await self._log(f"Fuzzy validation failed: {e}")
            return {"valid": False, "error": f"'{param_value}' не найдено", "suggestions": []}

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
                return {"valid": True, "corrected_value": first_value, "suggestions": []}

        return {"valid": False, "error": f"'{param_value}' не найдено", "suggestions": []}

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
            action_name="vector_books.search",
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
            if hasattr(inner_data, 'data'):
                actual_data = inner_data.data
            else:
                actual_data = inner_data
            
            results = actual_data if isinstance(actual_data, list) else []
            if results:
                best = results[0]
                # Определяем поле с именем
                name_field = f"{vector_source[:-1]}_name" if vector_source.endswith("s") else "name"
                found_value = best.get(name_field, best.get('name', ''))
                score = best.get('score', 0)
                
                if score >= min_score:
                    return {"valid": True, "corrected_value": found_value, "suggestions": []}

        return {"valid": False, "error": "Не найдено", "suggestions": []}

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
                return {"valid": True, "corrected_value": matched, "suggestions": []}

        return {"valid": False, "error": f"'{param_value}' не найдено", "suggestions": []}

    async def validate_multiple(
        self,
        params: Dict[str, Any],
        validation_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Валидация нескольких параметров.

        ARGS:
        - params: {"param_name": value, ...}
        - validation_config: {"param_name": config, ...}

        RETURNS:
        - Dict с ключами: valid, corrected_params, warning, suggestions
        """
        result = {
            "valid": True,
            "corrected_params": {},
            "warning": None,
            "suggestions": []
        }

        for param_name, param_config in validation_config.items():
            if param_name not in params:
                continue

            param_value = params[param_name]
            if not param_value:
                continue

            validation = await self.validate(param_value, param_config)

            if not validation["valid"]:
                result["valid"] = False
                result["warning"] = f"Параметр '{param_name}': {validation.get('error', 'невалиден')}"
                result["suggestions"] = validation.get("suggestions", [])
                return result

            corrected = validation.get("corrected_value")
            if corrected and corrected != param_value:
                result["corrected_params"][param_name] = corrected
                result["warning"] = f"✏️ Исправлена опечатка: '{param_value}' → '{corrected}'"

        return result
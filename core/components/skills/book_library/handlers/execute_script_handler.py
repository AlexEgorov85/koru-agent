import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from core.agent.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus
from core.components.skills.handlers.base_handler import SkillHandler


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Вычисляет расстояние Левенштейна между двумя строками.
    
    ARGS:
    - s1: первая строка
    - s2: вторая строка
    
    RETURNS:
    - Количество операций вставки/удаления/замены для превращения s1 в s2
    """
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
    """
    Нечёткое совпадение значения со списком кандидатов.
    
    ARGS:
    - value: искомое значение (возможно с опечаткой)
    - candidates: список корректных значений (полные имена "Имя Фамилия")
    - max_distance: максимальное расстояние Левенштейна для совпадения
    
    RETURNS:
    - Наиболее близкое значение или None, если совпадение не найдено
    """
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


class ExecuteScriptHandler(SkillHandler):
    """
    Обработчик выполнения заготовленных SQL-скриптов.

    RESPONSIBILITIES:
    - Валидация и выполнение статических скриптов
    - Проверка разрешённых скриптов
    - Преобразование параметров для SQL

    CAPABILITY:
    - book_library.execute_script
    """

    capability_name = "book_library.execute_script"

    async def _execute_impl(self, capability, parameters, execution_context=None):
        """Делегирует execute() — обратная совместимость."""
        return await self.execute(parameters, execution_context)

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Выполнение статического скрипта.

        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        start_time = time.time()
        script_name = params.script_name if hasattr(params, 'script_name') else ''
        max_rows = params.max_results if hasattr(params, 'max_results') else 50
        await self.log_info(f"📖 execute_script: script_name={script_name}, params={params}")

        # 1. Проверка что скрипт существует
        allowed_scripts = self._get_allowed_scripts()
        if script_name not in allowed_scripts:
            available_scripts = list(allowed_scripts.keys())
            raise ValueError(f"Скрипт '{script_name}' не найден. Доступные: {available_scripts}")

        # 2. Валидация параметров (может вызывать дополнительные скрипты)
        validation_result = await self._validate_parameters(params, script_name)
        if validation_result.get("warning"):
            await self.log_info(f"✏️ Валидация: {validation_result['warning']}")
        if not validation_result["valid"]:
            warning = validation_result.get("warning")
            suggestions = validation_result.get("suggestions", [])
            if suggestions:
                raise ValueError(f"Параметры невалидны: {warning}. Возможно вы имели в виду: {', '.join(suggestions)}")
            else:
                raise ValueError(f"Параметры невалидны: {warning}")

        # 3. Получение конфигурации скрипта
        allowed_scripts = self._get_allowed_scripts()
        script_config = allowed_scripts[script_name]
        sql_query = script_config['sql']

        # 4. Применение автокоррекции параметров
        corrected_params = validation_result.get("corrected_params", {})
        if corrected_params:
            # Обновляем params исправленными значениями
            params = {**params, **corrected_params}
            warning = validation_result.get("warning")
            if warning:
                await self.log_info(warning)

        # 5. Подготовка параметров для SQL
        script_params = self._prepare_script_params(params, script_config, max_rows)
        sql_params_list = self._convert_to_sql_params(script_params, script_config, max_rows)

        # 5. Выполнение SQL
        rows, execution_time = await self._execute_sql(sql_query, sql_params_list)

        # 6. Формирование результата
        total_time = time.time() - start_time
        result_data = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "static",
            "script_name": script_name
        }

        # 7. Публикация метрик
        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="static",
            rows_returned=len(rows),
            script_name=script_name
        )

        # 8. Валидация через выходной контракт
        return self._validate_output(result_data)

    def _extract_params(self, params: Dict[str, Any]) -> tuple:
        """
        Извлечение параметров script_name и max_rows.

        ARGS:
        - params: входные параметры

        RETURNS:
        - tuple: (script_name, max_rows)
        """
        if isinstance(params, dict):
            script_name = params.get('script_name')
            max_rows = params.get('max_rows', 100)
        else:
            script_name = getattr(params, 'script_name', None)
            max_rows = getattr(params, 'max_rows', 100)

        if not script_name:
            raise ValueError("Требуется параметр 'script_name'")

        return script_name, max_rows

    def _get_allowed_scripts(self) -> Dict[str, Dict[str, Any]]:
        """Получение реестра разрешённых скриптов"""
        if self.skill._scripts_registry:
            return {name: config.to_dict() for name, config in self.skill._scripts_registry.items()}
        return self.skill._get_allowed_scripts()

    def _prepare_script_params(
        self,
        params: Dict[str, Any],
        script_config: Dict[str, Any],
        max_rows: int
    ) -> Dict[str, Any]:
        """
        Подготовка параметров для скрипта.

        ARGS:
        - params: входные параметры
        - script_config: конфигурация скрипта
        - max_rows: максимальное количество строк

        RETURNS:
        - dict: параметры для SQL
        """
        # Сначала извлекаем базовые параметры из входных данных
        if isinstance(params, dict):
            script_params = params.copy()
            script_params.pop('script_name', None)
        elif hasattr(params, 'model_dump'):
            script_params = params.model_dump()
            script_params.pop('script_name', None)
        elif hasattr(params, 'parameters'):
            script_params = getattr(params, 'parameters', {})
            if hasattr(script_params, 'model_dump'):
                script_params = script_params.model_dump()
        else:
            script_params = {}

        # Специальная обработка для get_books_by_year_range
        # Устанавливаем значения по умолчанию для отсутствующих или None параметров
        if script_config.get('name') == 'get_books_by_year_range':
            # Год "от" - по умолчанию 0 (все книги с начала)
            if 'year_from' not in script_params or script_params.get('year_from') is None:
                script_params['year_from'] = 0
            # Год "до" - по умолчанию 9999 (до бесконечности)
            if 'year_to' not in script_params or script_params.get('year_to') is None:
                script_params['year_to'] = 9999

        # Добавляем max_rows
        if 'max_rows' not in script_params:
            if isinstance(params, dict) and 'max_rows' in params:
                script_params['max_rows'] = params['max_rows']
            elif hasattr(params, 'max_rows'):
                max_rows_val = getattr(params, 'max_rows')
                if max_rows_val is not None:
                    script_params['max_rows'] = max_rows_val
            else:
                script_params['max_rows'] = max_rows

        # Проверка обязательных параметров
        required_params = script_config.get('required_parameters', [])
        missing_params = set(required_params) - set(script_params.keys())
        if missing_params:
            raise ValueError(f"Отсутствуют обязательные параметры: {missing_params}")

        return script_params

    def _convert_to_sql_params(
        self,
        script_params: Dict[str, Any],
        script_config: Dict[str, Any],
        max_rows: int
    ) -> List[Any]:
        """
        Преобразование именованных параметров в позиционные для PostgreSQL.

        ARGS:
        - script_params: параметры скрипта
        - script_config: конфигурация скрипта
        - max_rows: максимальное количество строк

        RETURNS:
        - list: позиционные параметры для psycopg2
        """
        required_params = script_config.get('required_parameters', [])
        optional_params = script_config.get('parameters', [])
        all_params = required_params + [p for p in optional_params if p not in required_params]

        sql_params_list = []

        for param_name in all_params:
            if param_name == 'max_rows':
                continue
            if param_name in script_params:
                param_value = script_params[param_name]
                # Для ILIKE параметров добавляем % если нет wildcard
                if param_name in ['author', 'title_pattern']:
                    if param_value and '%' not in param_value:
                        param_value = f'%{param_value}%'
                sql_params_list.append(param_value)

        sql_params_list.append(max_rows)
        return sql_params_list

    async def _validate_parameters(self, params: Dict[str, Any], script_name: str) -> Dict[str, Any]:
        """
        Валидация параметров скрипта с использованием vector search.

        Проверяет параметры типа author, genre и другие через vector DB
        для поиска похожих значений и предотвращения ошибок.

        RETURNS:
        - Dict с ключами: valid (bool), warning (str), suggestions (list), corrected_params (dict)
        """
        validation_result = {"valid": True, "warning": None, "suggestions": [], "corrected_params": {}}

        required_params = self._get_validation_params(script_name)
        if not required_params:
            return validation_result

        for param_name, param_type in required_params.items():
            if param_name not in params:
                continue

            param_value = params[param_name]
            if not param_value:
                continue

            if param_type == "author":
                result = await self._validate_author(param_value)
                if not result["valid"]:
                    validation_result["valid"] = False
                    validation_result["warning"] = f"Автор '{param_value}' не найден"
                    validation_result["suggestions"] = result.get("suggestions", [])
                    return validation_result
                # Автокоррекция опечатки
                corrected = result.get("corrected_value")
                if corrected:
                    validation_result["corrected_params"][param_name] = corrected
                    validation_result["warning"] = f"✏️ Исправлена опечатка: '{param_value}' → '{corrected}'"
            elif param_type == "genre":
                result = await self._validate_genre(param_value)
                if not result["valid"]:
                    validation_result["valid"] = False
                    validation_result["warning"] = f"Жанр '{param_value}' не найден"
                    validation_result["suggestions"] = result.get("suggestions", [])

        return validation_result

    def _get_validation_params(self, script_name: str) -> Dict[str, str]:
        """Определение какие параметры нужно валидировать для каждого скрипта"""
        validation_map = {
            "get_books_by_author": {"author": "author"},
            "count_books_by_author": {"author": "author"},
            "get_books_by_genre": {"genre": "genre"},
            "get_distinct_authors": {},
            "get_distinct_genres": {},
        }
        return validation_map.get(script_name, {})

    async def _validate_author(self, author_name: str) -> Dict[str, Any]:
        """
        Валидация автора с автокоррекцией опечаток.

        Стратегия:
        1. SQL поиск по фамилии (ILIKE) — быстрый и надёжный
        2. Векторный поиск для семантических совпадений
        3. Fuzzy matching через полный список авторов

        RETURNS:
        - Dict с ключами: valid (bool), suggestions (list), corrected_value (str|None)
        """
        try:
            exec_context = ExecutionContext()
            author_name_lower = author_name.lower().strip()
            author_words = author_name_lower.split()
            search_term = author_words[-1] if len(author_words) > 1 else author_name_lower
            await self.log_debug(f"[DEBUG _validate_author] author_name='{author_name}', search_term='{search_term}'")

            # Ступень 1: SQL LIKE поиск по имени и фамилии
            try:
                sql_params_list = [f"%{search_term}%", f"%{search_term}%"]
                await self.log_debug(f"[DEBUG _validate_author] SQL: ILIKE query with params={sql_params_list}")
                
                sql_result = await self.executor.execute_action(
                    action_name="sql_query.execute",
                    parameters={
                        "sql": '''
                            SELECT DISTINCT 
                                a.first_name || ' ' || a.last_name as full_name,
                                a.last_name,
                                a.first_name
                            FROM "Lib".books b 
                            JOIN "Lib".authors a ON b.author_id = a.id 
                            WHERE a.first_name ILIKE %s OR a.last_name ILIKE %s 
                            LIMIT 5
                        ''',
                        "parameters": sql_params_list
                    },
                    context=exec_context
                )
                await self.log_debug(f"[DEBUG _validate_author] SQL result: status={sql_result.status}, error={getattr(sql_result, 'error', getattr(sql_result, 'data', 'N/A'))}")

                if sql_result.status == ExecutionStatus.COMPLETED and sql_result.data:
                    rows = sql_result.data.rows if hasattr(sql_result.data, 'rows') else []
                    await self.log_debug(f"[DEBUG _validate_author] SQL found {len(rows)} rows")
                    if rows:
                        for row in rows:
                            if hasattr(row, '__getitem__'):
                                full_name = row[0]
                                last_name = row[1]
                                first_name = row[2]
                            else:
                                full_name = str(row)
                                last_name = ""
                                first_name = ""

                            await self.log_debug(f"[DEBUG _validate_author] Comparing: search_term='{search_term}' vs full_name='{full_name}', last_name='{last_name}', first_name='{first_name}'")
                            
                            if (last_name.lower() == search_term or 
                                first_name.lower() == search_term or
                                full_name.lower() == author_name_lower or
                                author_name_lower in full_name.lower()):
                                await self.log_debug(f"[DEBUG _validate_author] MATCH! returning valid with corrected_value='{full_name}'")
                                return {"valid": True, "suggestions": [], "corrected_value": full_name}

                        first_row = rows[0]
                        if hasattr(first_row, '__getitem__'):
                            return {"valid": True, "suggestions": [], "corrected_value": first_row[0]}
                        else:
                            return {"valid": True, "suggestions": [], "corrected_value": str(first_row)}

            except Exception as e:
                await self.log_debug(f"SQL author validation failed: {e}")

            # Ступень 2: Векторный поиск
            try:
                vector_result = await self.executor.execute_action(
                    action_name="vector_books.search",
                    parameters={
                        "query": author_name,
                        "top_k": 3,
                        "min_score": 0.5,
                        "source": "authors"
                    },
                    context=exec_context
                )

                if vector_result.status == ExecutionStatus.COMPLETED and vector_result.data:
                    inner_data = vector_result.data
                    if hasattr(inner_data, 'data'):
                        actual_data = inner_data.data
                    else:
                        actual_data = inner_data
                    results = actual_data if isinstance(actual_data, list) else []
                    if results:
                        best_result = results[0]
                        author_from_vector = best_result.get('author_name', best_result.get('name', ''))
                        score = best_result.get('score', 0)
                        await self.log_debug(f"[DEBUG _validate_author] Vector found: author='{author_from_vector}', score={score}")
                        if score >= 0.7:
                            return {"valid": True, "suggestions": [], "corrected_value": author_from_vector}

            except Exception as e:
                await self.log_debug(f"Vector author validation failed: {e}")

            # Ступень 3: Fuzzy matching через get_distinct_authors
            try:
                authors_result = await self.executor.execute_action(
                    action_name="book_library.execute_script",
                    parameters={"script_name": "get_distinct_authors", "max_rows": 100},
                    context=exec_context
                )
                await self.log_debug(f"[DEBUG _validate_author] Fuzzy step: status={authors_result.status}")
                await self.log_debug(f"[DEBUG _validate_author] authors_result.data={authors_result.data}")

                if authors_result.status == ExecutionStatus.COMPLETED and authors_result.data:
                    authors_data = authors_result.data.rows if hasattr(authors_result.data, 'rows') else []
                    
                    if not authors_data:
                        return {"valid": True, "suggestions": [], "corrected_value": author_name}
                    
                    # SQL returns: last_name as dict {'last_name': 'Name'}
                    all_authors = []
                    for row in authors_data:
                        if isinstance(row, dict) and 'last_name' in row:
                            all_authors.append(row['last_name'])
                        elif isinstance(row, (list, tuple)) and len(row) > 0:
                            all_authors.append(row[0])
                    await self.log_debug(f"[DEBUG _validate_author] Got {len(all_authors)} authors: {all_authors[:5]}")
                    await self.log_debug(f"[DEBUG _validate_author] search_term='{search_term}', author_name_lower='{author_name_lower}'")

                    for author in all_authors:
                        author_lower = author.lower()
                        # Теперь SQL возвращает только фамилию, сравниваем напрямую
                        if search_term == author_lower:
                            await self.log_debug(f"[DEBUG _validate_author] Direct MATCH: '{search_term}' == '{author_lower}'")
                            return {"valid": True, "suggestions": [], "corrected_value": author}

                    for author in all_authors:
                        author_lower = author.lower()
                        if self._fuzzy_match(author_name_lower, author_lower) > 0.8:
                            await self.log_debug(f"[DEBUG _validate_author] Fuzzy match: '{author_name_lower}' == '{author_lower}'")
                            return {"valid": True, "suggestions": [], "corrected_value": author}

            except Exception as e:
                await self.log_debug(f"Fuzzy author validation failed: {e}")

            # Если ничего не найдено
            await self.log_debug(f"[DEBUG _validate_author] Author NOT FOUND, returning valid=False")
            return {"valid": False, "suggestions": [], "corrected_value": None}

        except Exception as e:
            await self.log_error(f"Author validation error: {e}")
            return {"valid": True, "suggestions": [], "corrected_value": None}

    async def _validate_genre(self, genre: str) -> Dict[str, Any]:
        """Валидация жанра - точное совпадение"""
        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": '''
                        SELECT DISTINCT g.name 
                        FROM "Lib".books b 
                        JOIN "Lib".book_genres bg ON b.id = bg.book_id 
                        JOIN "Lib".genres g ON bg.genre_id = g.id 
                        WHERE g.name ILIKE %s 
                        LIMIT 5
                    ''',
                    "parameters": [f"%{genre}%"]
                },
                context=exec_context
            )

            if result.status == ExecutionStatus.COMPLETED and result.data:
                rows = result.data.rows if hasattr(result.data, 'rows') else []
                if rows:
                    return {"valid": True, "suggestions": []}

            suggestions = await self._get_genre_suggestions()
            return {"valid": False, "suggestions": suggestions}

        except Exception as e:
            await self.log_warning(f"Genre validation failed: {e}")
            return {"valid": True, "suggestions": []}

    async def _get_all_authors(self) -> List[str]:
        """Получение полного списка авторов для fuzzy matching"""
        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": "SELECT DISTINCT a.first_name || ' ' || a.last_name FROM \"Lib\".books b JOIN \"Lib\".authors a ON b.author_id = a.id ORDER BY a.last_name",
                    "parameters": []
                },
                context=exec_context
            )
            if result.status == ExecutionStatus.COMPLETED and result.data:
                rows = result.data.rows if hasattr(result.data, 'rows') else []
                return [row[0] if hasattr(row, '__getitem__') else str(row) for row in rows]
        except Exception as e:
            await self.log_debug(f"Failed to get all authors: {e}")
        return []

    async def _get_author_suggestions(self, author_name: str) -> List[str]:
        """Получение списка авторов для подсказок"""
        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": "SELECT DISTINCT a.first_name || ' ' || a.last_name FROM \"Lib\".books b JOIN \"Lib\".authors a ON b.author_id = a.id WHERE a.first_name ILIKE $1 OR a.last_name ILIKE $1 LIMIT 5",
                    "parameters": [f"%{author_name}%"]
                },
                context=exec_context
            )
            if result.status == ExecutionStatus.COMPLETED and result.data:
                rows = result.data.rows if hasattr(result.data, 'rows') else []
                return [row[0] if hasattr(row, '__getitem__') else str(row) for row in rows]
        except:
            pass
        return []

    async def _get_genre_suggestions(self) -> List[str]:
        """Получение списка жанров для подсказок"""
        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": 'SELECT DISTINCT g.name FROM "Lib".genres g ORDER BY g.name LIMIT 20',
                    "parameters": []
                },
                context=exec_context
            )
            if result.status == ExecutionStatus.COMPLETED and result.data:
                rows = result.data.rows if hasattr(result.data, 'rows') else []
                return [row[0] if hasattr(row, '__getitem__') else getattr(row, 'genre', '') for row in rows]
        except:
            pass
        return []

    async def _execute_sql(self, sql: str, params: List[Any]) -> tuple:
        """
        Выполнение SQL запроса.

        ARGS:
        - sql: SQL запрос
        - params: позиционные параметры

        RETURNS:
        - tuple: (rows, execution_time)
        """
        rows = []
        execution_time = 0.0

        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="sql_query_service.execute_query",
                parameters={
                    "sql_query": sql,
                    "parameters": params
                },
                context=exec_context
            )

            if result.status == ExecutionStatus.COMPLETED and result.data:
                rows = result.data.rows if hasattr(result.data, 'rows') else []
                execution_time = result.data.execution_time if hasattr(result.data, 'execution_time') else 0.0
            else:
                error_msg = result.error if hasattr(result, 'error') else "Неизвестная ошибка"
                raise RuntimeError(f"Ошибка выполнения SQL: {error_msg}")

        except Exception as e:
            await self.log_error(f"Ошибка выполнения скрипта: {e}")
            raise

        return rows, execution_time

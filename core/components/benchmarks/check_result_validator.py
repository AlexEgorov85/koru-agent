"""
CheckResultValidator - специализированный валидатор для check_result skill.

ОЦЕНИВАЕТ:
1. execute_script:
   - Правильность выбранного скрипта (script_name match)
   - Правильность параметров (expected_parameters match)
   - Наличие результатов (has_results)

2. generate_script:
   - Валидность SQL (syntax check)
   - Наличие требуемых конструкций (JOIN, GROUP BY, WHERE и т.д.)
   - Выполняемость SQL (execution success)

3. vector_search:
   - Использован ли векторный поиск
   - Релевантность результатов
   - Правильный источник (audits/violations)

ИСПОЛЬЗОВАНИЕ:
```python
validator = CheckResultValidator()
result = validator.validate(response, scenario)
```
"""
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Результат валидации одного сценария."""
    success: bool
    score: float  # 0.0 - 1.0
    checks: Dict[str, bool]  # Детализация проверок
    errors: List[str]  # Список ошибок
    metadata: Dict[str, Any]  # Дополнительные метаданные


class CheckResultValidator:
    """
    Валидатор для check_result skill.

    RESPONSIBILITIES:
    - Валидация execute_script (правильность скрипта и параметров)
    - Валидация generate_script (качество SQL)
    - Валидация vector_search (релевантность поиска)

    USAGE:
    ```python
    validator = CheckResultValidator()
    result = validator.validate(response, scenario)
    ```
    """

    def __init__(self):
        # SQL ключевые слова для анализа
        self.sql_keywords = {
            'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
            'ON', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS', 'NULL',
            'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET',
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
            'AS', 'DISTINCT', 'ALL', 'UNION', 'INTERSECT', 'EXCEPT'
        }

    def validate(
        self,
        response: Dict[str, Any],
        scenario: Any
    ) -> ValidationResult:
        """
        Комплексная валидация ответа check_result.

        ARGS:
        - response: ответ от системы (output, metadata, error)
        - scenario: BenchmarkScenario с ожидаемыми результатами

        RETURNS:
        - ValidationResult: результат валидации
        """
        # Определяем capability из сценария
        capability = scenario.metadata.get('capability', '')
        
        if 'execute_script' in capability:
            return self._validate_execute_script(response, scenario)
        elif 'generate_script' in capability:
            return self._validate_generate_script(response, scenario)
        elif 'vector_search' in capability:
            return self._validate_vector_search(response, scenario)
        else:
            # Fallback для неизвестных capabilities
            return self._validate_generic(response, scenario)

    def _validate_execute_script(
        self,
        response: Dict[str, Any],
        scenario: Any
    ) -> ValidationResult:
        """
        Валидация execute_script.

        ПРОВЕРКИ:
        1. Правильность выбранного скрипта (если указан expected_script_name)
        2. Правильность параметров (если указаны expected_parameters)
        3. Успешность выполнения (success=True)
        4. Наличие результатов (has_results)
        """
        checks = {}
        errors = []
        scores = []

        # Извлекаем метаданные сценария
        expected_script = scenario.metadata.get('expected_script_name')
        expected_params = scenario.metadata.get('expected_parameters', {})
        metadata = scenario.metadata.get('metadata', {})

        # Получаем ответ
        response_success = response.get('success', False)
        response_output = response.get('output', '')
        response_metadata = response.get('metadata', {})

        # 1. Проверка успешности выполнения
        checks['execution_success'] = response_success
        if response_success:
            scores.append(1.0)
        else:
            scores.append(0.0)
            errors.append(f"Выполнение завершилось ошибкой: {response.get('error', 'unknown')}")

        # 2. Проверка правильности скрипта
        if expected_script:
            actual_script = response_metadata.get('script_name')
            if actual_script:
                script_match = actual_script == expected_script
                checks['script_name_match'] = script_match
                if script_match:
                    scores.append(1.0)
                else:
                    scores.append(0.0)
                    errors.append(
                        f"Неправильный скрипт: ожидался '{expected_script}', "
                        f"получен '{actual_script}'"
                    )
            else:
                # Если script_name нет в ответе, пытаемся извлечь из output
                checks['script_name_match'] = False
                scores.append(0.0)
                errors.append("script_name не найден в ответе")

        # 3. Проверка параметров
        if expected_params:
            actual_params = response_metadata.get('script_parameters', {})
            param_scores = []
            
            for param_name, expected_value in expected_params.items():
                actual_value = actual_params.get(param_name)
                param_match = actual_value == expected_value
                checks[f'param_{param_name}'] = param_match
                if param_match:
                    param_scores.append(1.0)
                else:
                    param_scores.append(0.0)
                    errors.append(
                        f"Неправильный параметр '{param_name}': "
                        f"ожидалось '{expected_value}', получено '{actual_value}'"
                    )
            
            if param_scores:
                scores.append(sum(param_scores) / len(param_scores))

        # 4. Проверка наличия результатов
        validation_rules = scenario.metadata.get('validation', {})
        if validation_rules.get('must_return_list'):
            has_results = isinstance(response_output, (list, dict)) and response_output
            checks['has_results'] = bool(has_results)
            if has_results:
                scores.append(1.0)
            else:
                scores.append(0.0)
                errors.append("Результаты выполнения отсутствуют")

        # Рассчитываем итоговый score
        final_score = sum(scores) / len(scores) if scores else 0.0

        return ValidationResult(
            success=final_score >= 0.8,
            score=final_score,
            checks=checks,
            errors=errors,
            metadata={
                'capability': 'execute_script',
                'expected_script': expected_script,
                'actual_script': response_metadata.get('script_name'),
            }
        )

    def _validate_generate_script(
        self,
        response: Dict[str, Any],
        scenario: Any
    ) -> ValidationResult:
        """
        Валидация generate_script.

        ПРОВЕРКИ:
        1. Наличие SQL в ответе
        2. Валидность SQL (синтаксис)
        3. Наличие требуемых конструкций (JOIN, GROUP BY, WHERE и т.д.)
        4. Успешность выполнения
        """
        checks = {}
        errors = []
        scores = []

        # Получаем ответ
        response_success = response.get('success', False)
        response_output = response.get('output', '')
        response_metadata = response.get('metadata', {})

        # Извлекаем validation правила
        validation_rules = scenario.metadata.get('validation', {})

        # 1. Проверка успешности
        checks['execution_success'] = response_success
        if response_success:
            scores.append(1.0)
        else:
            scores.append(0.0)
            errors.append(f"Выполнение завершилось ошибкой: {response.get('error', 'unknown')}")

        # 2. Извлекаем SQL из ответа
        sql_query = self._extract_sql_from_response(response_output)
        checks['has_sql'] = bool(sql_query)
        
        if sql_query:
            scores.append(1.0)
        else:
            scores.append(0.0)
            errors.append("SQL запрос не найден в ответе")
            return ValidationResult(
                success=False,
                score=sum(scores) / len(scores) if scores else 0.0,
                checks=checks,
                errors=errors,
                metadata={'capability': 'generate_script', 'sql_found': False}
            )

        # 3. Проверка валидности SQL
        if validation_rules.get('must_be_valid_sql', False):
            is_valid, error = self._check_sql_validity(sql_query)
            checks['sql_valid'] = is_valid
            if is_valid:
                scores.append(1.0)
            else:
                scores.append(0.0)
                errors.append(f"Невалидный SQL: {error}")

        # 4. Проверка наличия требуемых конструкций
        sql_upper = sql_query.upper()
        structure_checks = {
            'must_have_from_clause': lambda: 'FROM' in sql_upper,
            'must_have_where_clause': lambda: 'WHERE' in sql_upper,
            'must_have_join': lambda: 'JOIN' in sql_upper,
            'must_use_left_join_or_not_exists': lambda: (
                'LEFT JOIN' in sql_upper or 'NOT EXISTS' in sql_upper or 'NOT IN' in sql_upper
            ),
            'must_have_group_by': lambda: 'GROUP BY' in sql_upper,
            'must_have_order_by': lambda: 'ORDER BY' in sql_upper,
            'must_have_count': lambda: 'COUNT(' in sql_upper,
            'must_have_date_filter': lambda: self._check_date_filter(sql_query),
            'must_have_deadline_filter': lambda: 'deadline' in sql_query.lower(),
            'must_have_year_filter': lambda: self._check_year_filter(sql_query),
            'uses_join_or_subquery': lambda: (
                'JOIN' in sql_upper or 'SELECT' in sql_query[sql_query.upper().find('SELECT')+6:].upper()
            ),
        }

        structure_scores = []
        for check_name, check_func in structure_checks.items():
            if validation_rules.get(check_name, False):
                result = check_func()
                checks[check_name] = result
                if result:
                    structure_scores.append(1.0)
                else:
                    structure_scores.append(0.0)
                    errors.append(f"Не найдена требуемая конструкция: {check_name}")

        if structure_scores:
            scores.append(sum(structure_scores) / len(structure_scores))

        # 5. Проверка наличия агрегации (для сложных запросов)
        if validation_rules.get('has_aggregation', False):
            has_agg = any(kw in sql_upper for kw in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(', 'GROUP BY'])
            checks['has_aggregation'] = has_agg
            if has_agg:
                scores.append(1.0)
            else:
                scores.append(0.0)
                errors.append("Агрегация не найдена в SQL")

        # Рассчитываем итоговый score
        final_score = sum(scores) / len(scores) if scores else 0.0

        return ValidationResult(
            success=final_score >= 0.8,
            score=final_score,
            checks=checks,
            errors=errors,
            metadata={
                'capability': 'generate_script',
                'sql_found': bool(sql_query),
                'sql_preview': sql_query[:200] if sql_query else None,
            }
        )

    def _validate_vector_search(
        self,
        response: Dict[str, Any],
        scenario: Any
    ) -> ValidationResult:
        """
        Валидация vector_search.

        ПРОВЕРКИ:
        1. Использован ли векторный поиск
        2. Правильный источник (audits/violations)
        3. Наличие результатов
        4. Релевантность результатов
        """
        checks = {}
        errors = []
        scores = []

        # Получаем ответ
        response_success = response.get('success', False)
        response_output = response.get('output', '')
        response_metadata = response.get('metadata', {})

        # Извлекаем validation правила
        validation_rules = scenario.metadata.get('validation', {})

        # 1. Проверка успешности
        checks['execution_success'] = response_success
        if response_success:
            scores.append(1.0)
        else:
            scores.append(0.0)
            errors.append(f"Выполнение завершилось ошибкой: {response.get('error', 'unknown')}")

        # 2. Проверка использования векторного поиска
        if validation_rules.get('must_use_vector_search', False):
            used_vector = response_metadata.get('used_vector_search', False)
            if not used_vector:
                # Проверяем по наличию score в результатах (признак vector search)
                if isinstance(response_output, dict):
                    results = response_output.get('results', [])
                    if results and 'score' in results[0]:
                        used_vector = True
            
            checks['used_vector_search'] = used_vector
            if used_vector:
                scores.append(1.0)
            else:
                scores.append(0.0)
                errors.append("Векторный поиск не использован")

        # 3. Проверка источника
        expected_source = validation_rules.get('must_have_source')
        if expected_source:
            actual_source = response_metadata.get('source', '')
            source_match = actual_source == expected_source
            
            # Если source нет в metadata, пытаемся найти в output
            if not source_match and isinstance(response_output, dict):
                actual_source = response_output.get('source', '')
                source_match = actual_source == expected_source
            
            checks['source_match'] = source_match
            if source_match:
                scores.append(1.0)
            else:
                scores.append(0.0)
                errors.append(
                    f"Неправильный источник: ожидался '{expected_source}', "
                    f"получен '{actual_source}'"
                )

        # 4. Проверка наличия результатов
        if validation_rules.get('must_return_results', False):
            has_results = False
            if isinstance(response_output, list):
                has_results = len(response_output) > 0
            elif isinstance(response_output, dict):
                results = response_output.get('results', [])
                has_results = len(results) > 0
            
            checks['has_results'] = has_results
            if has_results:
                scores.append(1.0)
            else:
                scores.append(0.0)
                errors.append("Результаты поиска отсутствуют")

        # 5. Проверка релевантности (если есть min_score в metadata)
        min_score = scenario.metadata.get('metadata', {}).get('min_score', 0.5)
        if isinstance(response_output, dict):
            results = response_output.get('results', [])
            if results:
                avg_score = sum(r.get('score', 0) for r in results) / len(results)
                checks['avg_relevance_score'] = avg_score
                if avg_score >= min_score:
                    scores.append(1.0)
                else:
                    scores.append(avg_score / min_score)
                    errors.append(
                        f"Низкая релевантность: средняя оценка {avg_score:.2f} "
                        f"< порога {min_score:.2f}"
                    )

        # Рассчитываем итоговый score
        final_score = sum(scores) / len(scores) if scores else 0.0

        return ValidationResult(
            success=final_score >= 0.8,
            score=final_score,
            checks=checks,
            errors=errors,
            metadata={
                'capability': 'vector_search',
                'source_match': checks.get('source_match', False),
            }
        )

    def _validate_generic(
        self,
        response: Dict[str, Any],
        scenario: Any
    ) -> ValidationResult:
        """Fallback валидация для неизвестных capabilities."""
        checks = {}
        errors = []
        
        response_success = response.get('success', False)
        checks['execution_success'] = response_success
        
        if response_success:
            return ValidationResult(
                success=True,
                score=1.0,
                checks=checks,
                errors=[],
                metadata={'capability': 'unknown'}
            )
        else:
            errors.append(f"Выполнение завершилось ошибкой: {response.get('error', 'unknown')}")
            return ValidationResult(
                success=False,
                score=0.0,
                checks=checks,
                errors=errors,
                metadata={'capability': 'unknown'}
            )

    # ========================================================================
    # Вспомогательные методы
    # ========================================================================

    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """
        Извлечение SQL из ответа.

        Поддерживает:
        - Чистый SQL
        - SQL в markdown блоках (```sql ... ```)
        - SQL с текстом вокруг
        """
        if not response:
            return None

        # Паттерн 1: SQL в markdown блоке
        markdown_match = re.search(r'```sql\s*\n(.*?)\n```', response, re.DOTALL)
        if markdown_match:
            return markdown_match.group(1).strip()

        # Паттерн 2: Общий markdown блок
        code_match = re.search(r'```\s*\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            if any(kw in code.upper() for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
                return code

        # Паттерн 3: Ищем SELECT ... в тексте
        select_match = re.search(r'SELECT\b.*?;', response, re.IGNORECASE | re.DOTALL)
        if select_match:
            return select_match.group(0).strip()

        # Паттерн 4: Если весь ответ похож на SQL
        response_upper = response.upper().strip()
        if any(response_upper.startswith(kw) for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
            return response.strip()

        return None

    def _check_sql_validity(self, sql: str) -> Tuple[bool, str]:
        """
        Базовая проверка валидности SQL.

        RETURNS:
        - (is_valid, error_message)
        """
        sql = sql.strip()

        # Пустой запрос
        if not sql:
            return False, 'Пустой SQL запрос'

        # Проверка на основные SQL команды
        valid_starts = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')
        sql_upper = sql.upper().strip()

        if not any(sql_upper.startswith(cmd) for cmd in valid_starts):
            return False, f'Не начинается с допустимой команды'

        # Проверка на баланс скобок
        paren_count = sql.count('(') - sql.count(')')
        if paren_count != 0:
            return False, f'Несбалансированные скобки (разница: {paren_count})'

        # Проверка на наличие SELECT ... FROM для SELECT запросов
        if sql_upper.startswith('SELECT'):
            if 'FROM' not in sql_upper:
                return False, 'Отсутствует FROM в SELECT запросе'

        return True, ''

    def _check_date_filter(self, sql: str) -> bool:
        """Проверка наличия фильтра по дате."""
        patterns = [
            r'\d{4}\s*-\s*\d{2}\s*-\s*\d{2}',  # YYYY-MM-DD
            r'CURRENT_DATE',
            r'NOW\(\)',
            r'EXTRACT\s*\(\s*YEAR',
            r'date\s*[><=]+',
            r'planned_date',
            r'actual_date',
            r'deadline',
        ]
        for pattern in patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return True
        return False

    def _check_year_filter(self, sql: str) -> bool:
        """Проверка наличия фильтра по году."""
        patterns = [
            r'year\s*[><=]+\s*\d{4}',
            r'\d{4}\s*-\s*\d{2}\s*-\s*\d{2}',
            r'EXTRACT\s*\(\s*YEAR',
            r'YEAR\s*\(',
        ]
        for pattern in patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return True
        return False

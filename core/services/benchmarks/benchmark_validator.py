#!/usr/bin/env python3
"""
Валидатор результатов бенчмарка.

КОМПОНЕНТЫ:
- SQLValidator: валидация SQL запросов
- AnswerValidator: валидация финальных ответов
- BenchmarkValidator: комплексная валидация

Использование:
    from scripts.cli.benchmark_validator import BenchmarkValidator
    
    validator = BenchmarkValidator()
    result = validator.validate_sql(sql, validation_rules)
"""
import re
from typing import Dict, List, Any, Optional, Tuple, Set


# ============================================================================
# SQL Validator
# ============================================================================

class SQLValidator:
    """
    Валидация SQL запросов.
    
    Проверки:
    - Синтаксическая валидность
    - Наличие требуемых таблиц
    - Наличие WHERE/JOIN/GROUP BY и т.д.
    - Проверка агрегатных функций
    - Проверка колонок
    """
    
    def __init__(self):
        # SQL ключевые слова для парсинга
        self.sql_keywords = {
            'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
            'ON', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS', 'NULL',
            'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET',
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
            'AS', 'DISTINCT', 'ALL', 'UNION', 'INTERSECT', 'EXCEPT'
        }
    
    def validate(
        self, 
        sql: str, 
        validation_rules: Dict[str, Any],
        expected_output: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Комплексная валидация SQL запроса.
        
        ARGS:
        - sql: SQL запрос для проверки
        - validation_rules: правила валидации из бенчмарка
        - expected_output: ожидаемый результат (для дополнительной проверки)
        
        RETURNS:
        - Dict с результатами валидации
        """
        errors = []
        checks = {}
        sql_upper = sql.upper()
        
        # 1. Проверка на валидность SQL (базовая)
        if validation_rules.get('must_be_valid_sql', False):
            is_valid, error = self._check_sql_validity(sql)
            checks['sql_valid'] = is_valid
            if not is_valid:
                errors.append(f'Невалидный SQL: {error}')
        
        # 2. Проверка таблиц
        if validation_rules.get('must_have_tables'):
            required_tables = validation_rules['must_have_tables']
            tables_found = self._extract_tables(sql)
            missing_tables = [t for t in required_tables if t.lower() not in [tf.lower() for tf in tables_found]]
            checks['has_tables'] = len(missing_tables) == 0
            checks['tables_found'] = list(tables_found)
            if missing_tables:
                errors.append(f'Нет таблиц: {missing_tables}')
        
        # 3. Проверка WHERE
        if validation_rules.get('must_have_where', False):
            has_where = 'WHERE' in sql_upper
            checks['has_where'] = has_where
            if not has_where:
                errors.append('Отсутствует WHERE')
        
        # 4. Проверка JOIN
        if validation_rules.get('must_have_join', False):
            has_join = 'JOIN' in sql_upper
            checks['has_join'] = has_join
            if not has_join:
                errors.append('Отсутствует JOIN')
        
        # 5. Проверка COUNT
        if validation_rules.get('must_have_count', False):
            has_count = 'COUNT(' in sql_upper
            checks['has_count'] = has_count
            if not has_count:
                errors.append('Отсутствует COUNT()')
        
        # 6. Проверка фильтра по году
        if validation_rules.get('must_have_year_filter', False):
            has_year_filter = self._check_year_filter(sql)
            checks['has_year_filter'] = has_year_filter
            if not has_year_filter:
                errors.append('Отсутствует фильтр по году')
        
        # 7. Проверка GROUP BY
        if validation_rules.get('must_have_group_by', False):
            has_group_by = 'GROUP BY' in sql_upper
            checks['has_group_by'] = has_group_by
            if not has_group_by:
                errors.append('Отсутствует GROUP BY')
        
        # 8. Проверка ORDER BY
        if validation_rules.get('must_have_order_by', False):
            has_order_by = 'ORDER BY' in sql_upper
            checks['has_order_by'] = has_order_by
            if not has_order_by:
                errors.append('Отсутствует ORDER BY')
        
        # 9. Проверка колонок (если есть expected_output)
        if validation_rules.get('must_return_correct_columns') and expected_output:
            required_columns = validation_rules['must_return_correct_columns']
            # Проверяем, что колонки упоминаются в SELECT
            has_columns = self._check_columns_in_select(sql, required_columns)
            checks['has_correct_columns'] = has_columns
            if not has_columns:
                errors.append(f'Не найдены требуемые колонки: {required_columns}')
        
        # 10. Проверка на наличие нескольких авторов (для сложных запросов)
        if validation_rules.get('must_have_multiple_authors', False):
            has_multiple = self._check_multiple_authors(sql)
            checks['has_multiple_authors'] = has_multiple
            if not has_multiple:
                errors.append('Запрос не поддерживает нескольких авторов')
        
        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'checks': checks,
            'sql_analyzed': sql[:200]  # Первые 200 символов для лога
        }
    
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
        
        # Проверка на опасные конструкции (для безопасности)
        dangerous_patterns = ['; DROP', '; DELETE', '; UPDATE', '--', '/*', '*/']
        for pattern in dangerous_patterns:
            if pattern.upper() in sql_upper:
                return False, f'Обнаружена опасная конструкция: {pattern}'
        
        return True, ''
    
    def _extract_tables(self, sql: str) -> Set[str]:
        """
        Извлечение имён таблиц из SQL запроса.
        """
        tables = set()
        sql_upper = sql.upper()
        
        # Паттерн: FROM table_name или JOIN table_name
        patterns = [
            r'FROM\s+([^\s,(]+)',
            r'JOIN\s+([^\s,]+)',
            r'INTO\s+([^\s,]+)',
            r'UPDATE\s+([^\s,]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                # Очистка от кавычек и схем
                table_name = match.strip('"\'`[]')
                # Удаление схемы (schema.table -> table)
                if '.' in table_name:
                    table_name = table_name.split('.')[-1]
                if table_name and table_name.upper() not in self.sql_keywords:
                    tables.add(table_name)
        
        return tables
    
    def _check_year_filter(self, sql: str) -> bool:
        """
        Проверка наличия фильтра по году.
        """
        # Паттерны для года: year > 1850, publication_date >= '1850-01-01' и т.д.
        patterns = [
            r'year\s*[><=]+\s*\d{4}',
            r'date\s*[><=]+\s*[\'"]?\d{4}',
            r'\d{4}\s*-\s*\d{2}\s*-\s*\d{2}',  # Дата в формате YYYY-MM-DD
            r'EXTRACT\s*\(\s*YEAR',
            r'YEAR\s*\(',
        ]
        
        for pattern in patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return True
        
        return False
    
    def _check_columns_in_select(self, sql: str, required_columns: List[str]) -> bool:
        """
        Проверка наличия требуемых колонок в SELECT.
        """
        # Извлекаем часть SELECT ... FROM
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return False
        
        select_part = select_match.group(1).upper()
        
        # Проверка на SELECT *
        if '*' in select_part:
            return True  # SELECT * возвращает все колонки
        
        # Проверка каждой требуемой колонки
        for col in required_columns:
            if col.upper() not in select_part:
                return False
        
        return True
    
    def _check_multiple_authors(self, sql: str) -> bool:
        """
        Проверка поддержки нескольких авторов.
        """
        # Наличие нескольких условий для авторов
        author_patterns = [
            r'author.*=.*author',  # author1 = author2
            r'AND.*author',  # AND author
            r'OR.*author',  # OR author
            r'IN\s*\([^)]+,',  # IN (val1, val2)
            r'JOIN.*author.*JOIN',  # Несколько JOIN
        ]
        
        for pattern in author_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return True
        
        return False


# ============================================================================
# Answer Validator
# ============================================================================

class AnswerValidator:
    """
    Валидация финальных ответов агента.
    
    Проверки:
    - Наличие ключевых слов
    - Язык ответа
    - Отсутствие галлюцинаций
    - Полнота ответа
    - Вежливость
    - Упоминание автора
    """
    
    def __init__(self):
        # Слова-маркеры вежливости
        self.polite_words = {
            'пожалуйста', 'к сожалению', 'увы', 'могу сообщить',
            'предлагаю', 'рекомендую', 'обратите внимание'
        }
        
        # Слова-маркеры отсутствия результатов
        self.no_result_words = {
            'ничего не найдено', 'не найдено', 'отсутствуют',
            'нет информации', 'к сожалению', 'увы', 'пусто',
            'не удалось найти', 'нет данных'
        }
    
    def validate(
        self,
        answer: str,
        validation_rules: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        expected_books: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Комплексная валидация финального ответа.
        
        ARGS:
        - answer: текст ответа агента
        - validation_rules: правила валидации из бенчмарка
        - context: контекст (SQL результат и т.д.)
        - expected_books: ожидаемые книги для сверки
        
        RETURNS:
        - Dict с результатами валидации
        """
        errors = []
        checks = {}
        answer_lower = answer.lower()
        
        # 1. Проверка keywords
        if validation_rules.get('must_contain_keywords'):
            required_keywords = validation_rules['must_contain_keywords']
            missing_keywords = self._check_keywords(answer, required_keywords)
            checks['has_keywords'] = len(missing_keywords) == 0
            checks['missing_keywords'] = missing_keywords
            if missing_keywords:
                errors.append(f'Нет keywords: {missing_keywords[:3]}')
        
        # 2. Проверка языка (русский)
        if validation_rules.get('must_be_in_russian', False):
            is_russian, cyrillic_ratio = self._check_russian_language(answer)
            checks['is_russian'] = is_russian
            checks['cyrillic_ratio'] = cyrillic_ratio
            if not is_russian:
                errors.append('Ответ не на русском языке')
        
        # 3. Проверка на галлюцинации
        if validation_rules.get('must_not_hallucinate', False) and context:
            hallucinations = self._check_hallucinations(answer, context, expected_books)
            checks['has_hallucinations'] = len(hallucinations) > 0
            checks['hallucinations'] = hallucinations
            if hallucinations:
                errors.append(f'Возможные галлюцинации: {hallucinations[:3]}')
        
        # 4. Проверка минимальной длины
        if validation_rules.get('min_length'):
            min_len = validation_rules['min_length']
            actual_len = len(answer)
            checks['length'] = actual_len
            checks['min_length_met'] = actual_len >= min_len
            if actual_len < min_len:
                errors.append(f'Ответ слишком короткий ({actual_len} < {min_len})')
        
        # 5. Проверка упоминания автора
        if validation_rules.get('must_mention_author', False):
            author_name = context.get('metadata', {}).get('author', '') if context else ''
            if not author_name:
                # Пытаемся извлечь из expected_books
                if expected_books and len(expected_books) > 0:
                    author_name = expected_books[0].get('author', '')
            
            mentions_author = self._check_author_mention(answer, author_name)
            checks['mentions_author'] = mentions_author
            if not mentions_author and author_name:
                errors.append(f'Не упомянут автор: {author_name}')
        
        # 6. Проверка отсутствия результатов (для edge cases)
        if validation_rules.get('must_indicate_no_results', False):
            indicates_no_results = self._check_no_results_indication(answer)
            checks['indicates_no_results'] = indicates_no_results
            if not indicates_no_results:
                errors.append('Не указано, что результатов нет')
        
        # 7. Проверка вежливости
        if validation_rules.get('must_be_polite', False):
            is_polite, polite_words_found = self._check_politeness(answer)
            checks['is_polite'] = is_polite
            checks['polite_words'] = list(polite_words_found)
            if not is_polite:
                errors.append('Ответ недостаточно вежливый')
        
        # 8. Проверка числа (для агрегаций)
        if validation_rules.get('must_contain_number', False):
            has_number = self._check_number_present(answer)
            checks['has_number'] = has_number
            if not has_number:
                errors.append('Не найдено числовое значение')
        
        # 9. Сверка с ожидаемыми книгами
        if expected_books:
            books_match, missing_books = self._check_books_match_detailed(answer, expected_books)
            checks['books_match'] = books_match
            checks['missing_books'] = missing_books
            if not books_match:
                errors.append(f'Не все ожидаемые книги упомянуты: не найдены {missing_books}')
        
        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'checks': checks,
            'answer_length': len(answer),
            'answer_preview': answer[:200]
        }
    
    def _check_keywords(self, answer: str, required_keywords: List[str]) -> List[str]:
        """
        Проверка наличия ключевых слов в ответе.
        
        RETURNS:
        - Список отсутствующих keywords
        """
        answer_lower = answer.lower()
        missing = []
        
        for kw in required_keywords:
            # Особая обработка для паттернов типа "4 книг"
            if kw.replace(' ', '').isdigit() or any(c.isdigit() for c in kw):
                # Числовой паттерн - ищем число
                numbers_in_kw = re.findall(r'\d+', kw)
                for num in numbers_in_kw:
                    if num not in answer:
                        missing.append(kw)
                        break
            elif kw.lower() not in answer_lower:
                missing.append(kw)
        
        return missing
    
    def _check_russian_language(self, answer: str) -> Tuple[bool, float]:
        """
        Проверка, что ответ на русском языке.
        
        RETURNS:
        - (is_russian, cyrillic_ratio)
        """
        if not answer.strip():
            return False, 0.0
        
        cyrillic_count = sum(1 for c in answer if '\u0400' <= c <= '\u04FF')
        total_chars = sum(1 for c in answer if c.isalpha())
        
        if total_chars == 0:
            return False, 0.0
        
        ratio = cyrillic_count / total_chars
        # Считаем русским, если >50% символов - кириллица
        return ratio >= 0.5, ratio
    
    def _check_hallucinations(
        self, 
        answer: str, 
        context: Dict[str, Any],
        expected_books: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Проверка на галлюцинации (выдуманные факты).
        
        Сравнивает ответ с данными из SQL результата.
        
        RETURNS:
        - Список возможных галлюцинаций
        """
        hallucinations = []
        answer_lower = answer.lower()
        
        # Получаем реальные данные из контекста
        sql_result = context.get('sql_result', {})
        rows = sql_result.get('rows', [])
        
        if not rows and not expected_books:
            return hallucinations  # Нет данных для сверки
        
        # Собираем реальные названия книг
        real_books = set()
        real_authors = set()
        
        for row in rows:
            if 'title' in row:
                real_books.add(row['title'].lower())
            if 'author' in row:
                real_authors.add(row['author'].lower())
        
        if expected_books:
            for book in expected_books:
                if 'title' in book:
                    real_books.add(book['title'].lower())
                if 'author' in book:
                    real_authors.add(book['author'].lower())
        
        # Проверяем, нет ли в ответе книг, которых нет в БД
        # Это упрощённая проверка - ищем явные несоответствия
        known_false_books = [
            'война и мир', 'anna karenina', 'гамлет',  # Примеры заведомо ложных книг
        ]
        
        for false_book in known_false_books:
            if false_book in answer_lower and false_book not in real_books:
                hallucinations.append(false_book)
        
        return hallucinations
    
    def _check_author_mention(self, answer: str, author_name: str) -> bool:
        """
        Проверка упоминания автора в ответе.
        """
        if not author_name:
            return True  # Нет автора для проверки
        
        answer_lower = answer.lower()
        author_lower = author_name.lower()
        
        # Разбиваем имя на части (фамилия, имя)
        name_parts = author_lower.split()
        
        # Проверяем полное имя
        if author_lower in answer_lower:
            return True
        
        # Проверяем фамилию (последняя часть имени)
        if len(name_parts) > 1 and name_parts[-1] in answer_lower:
            return True
        
        # Проверяем любую часть имени
        for part in name_parts:
            if len(part) > 3 and part in answer_lower:  # Избегаем слишком коротких совпадений
                return True
        
        return False
    
    def _check_no_results_indication(self, answer: str) -> bool:
        """
        Проверка, что ответ указывает на отсутствие результатов.
        """
        answer_lower = answer.lower()
        
        for phrase in self.no_result_words:
            if phrase in answer_lower:
                return True
        
        return False
    
    def _check_politeness(self, answer: str) -> Tuple[bool, Set[str]]:
        """
        Проверка вежливости ответа.
        
        RETURNS:
        - (is_polite, found_polite_words)
        """
        answer_lower = answer.lower()
        found_words = set()
        
        for word in self.polite_words:
            if word in answer_lower:
                found_words.add(word)
        
        # Считаем вежливым, если найдено хотя бы одно слово
        is_polite = len(found_words) >= 1
        
        return is_polite, found_words
    
    def _check_number_present(self, answer: str) -> bool:
        """
        Проверка наличия числового значения в ответе.
        """
        return bool(re.search(r'\d+', answer))
    
    def _normalize_russian(self, text: str) -> str:
        """Нормализация русского текста: ё -> е"""
        text = text.lower()
        text = text.replace('ё', 'е')
        text = text.replace('Ё', 'Е')
        return text

    def _check_books_match_detailed(self, answer: str, expected_books: List[Dict[str, Any]]) -> tuple[bool, List[str]]:
        """
        Проверка, что все ожидаемые книги упомянуты в ответе.
        Возвращает (match, missing_books)
        """
        answer_normalized = self._normalize_russian(answer)
        missing = []
        
        for book in expected_books:
            title = book.get('title', '')
            if title:
                title_normalized = self._normalize_russian(title)
                found = title_normalized in answer_normalized
                if not found:
                    missing.append(title)
        
        return len(missing) == 0, missing

    def _check_books_match(self, answer: str, expected_books: List[Dict[str, Any]]) -> bool:
        """
        Проверка, что все ожидаемые книги упомянуты в ответе.
        """
        match, _ = self._check_books_match_detailed(answer, expected_books)
        return match


# ============================================================================
# Benchmark Validator (Facade)
# ============================================================================

class BenchmarkValidator:
    """
    Фасад для валидации результатов бенчмарка.
    
    Объединяет SQL и Answer валидаторы.
    """
    
    def __init__(self):
        self.sql_validator = SQLValidator()
        self.answer_validator = AnswerValidator()
    
    def validate_sql_generation(
        self,
        sql: str,
        validation_rules: Dict[str, Any],
        expected_output: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Валидация SQL запроса.
        """
        return self.sql_validator.validate(sql, validation_rules, expected_output)
    
    def validate_final_answer(
        self,
        answer: str,
        validation_rules: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        expected_books: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Валидация финального ответа.
        """
        return self.answer_validator.validate(answer, validation_rules, context, expected_books)
    
    def validate_test_result(
        self,
        test_case: Dict[str, Any],
        agent_response: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Комплексная валидация результата теста.
        
        ARGS:
        - test_case: тестовый кейс из бенчмарка
        - agent_response: ответ агента
        - context: дополнительный контекст
        
        RETURNS:
        - Dict с результатами валидации
        """
        validation_rules = test_case.get('validation', {})
        expected_output = test_case.get('expected_output', {})
        
        result = {
            'test_id': test_case.get('id', 'unknown'),
            'sql_validation': None,
            'answer_validation': None,
            'overall_passed': True,
            'errors': []
        }
        
        # Валидация SQL (если есть в ответе)
        if 'sql' in agent_response:
            sql_result = self.validate_sql_generation(
                agent_response['sql'],
                validation_rules,
                expected_output
            )
            result['sql_validation'] = sql_result
            if not sql_result['passed']:
                result['overall_passed'] = False
                result['errors'].extend(sql_result['errors'])
        
        # Валидация ответа (если есть в ответе)
        if 'final_answer' in agent_response:
            # Получаем ожидаемые книги из expected_output
            expected_books = expected_output.get('books', [])
            
            answer_result = self.validate_final_answer(
                agent_response['final_answer'],
                validation_rules,
                context,
                expected_books
            )
            result['answer_validation'] = answer_result
            if not answer_result['passed']:
                result['overall_passed'] = False
                result['errors'].extend(answer_result['errors'])
        
        return result

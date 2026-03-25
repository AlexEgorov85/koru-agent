#!/usr/bin/env python3
"""
Тесты для модуля benchmark_validator.

Запуск:
    py -m pytest tests/test_cli/test_benchmark_validator.py -v
"""
import pytest
from core.benchmarks import (
    SQLValidator,
    AnswerValidator,
    BenchmarkValidator
)


# ============================================================================
# Тесты SQL Validator
# ============================================================================

class TestSQLValidator:
    """Тесты для SQLValidator"""

    def setup_method(self):
        """Инициализация перед каждым тестом"""
        self.validator = SQLValidator()

    def test_valid_select_query(self):
        """Проверка валидного SELECT запроса"""
        sql = "SELECT * FROM books WHERE author_id = 1"
        rules = {'must_be_valid_sql': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is True
        assert result['checks']['sql_valid'] is True

    def test_invalid_empty_query(self):
        """Проверка пустого запроса"""
        sql = ""
        rules = {'must_be_valid_sql': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is False
        assert 'sql_valid' in result['checks']
        assert result['checks']['sql_valid'] is False

    def test_missing_where(self):
        """Проверка отсутствия WHERE"""
        sql = "SELECT * FROM books"
        rules = {'must_have_where': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is False
        assert result['checks']['has_where'] is False
        assert 'Отсутствует WHERE' in result['errors']

    def test_has_where(self):
        """Проверка наличия WHERE"""
        sql = "SELECT * FROM books WHERE id = 1"
        rules = {'must_have_where': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is True
        assert result['checks']['has_where'] is True

    def test_missing_join(self):
        """Проверка отсутствия JOIN"""
        sql = "SELECT * FROM books WHERE author_id = 1"
        rules = {'must_have_join': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is False
        assert result['checks']['has_join'] is False

    def test_has_join(self):
        """Проверка наличия JOIN"""
        sql = """
            SELECT b.title, a.name
            FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE a.name = 'Пушкин'
        """
        rules = {'must_have_join': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is True
        assert result['checks']['has_join'] is True

    def test_missing_tables(self):
        """Проверка отсутствия требуемых таблиц"""
        sql = "SELECT * FROM books WHERE id = 1"
        rules = {'must_have_tables': ['books', 'authors']}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is False
        assert 'authors' in result['errors'][0]

    def test_has_required_tables(self):
        """Проверка наличия требуемых таблиц"""
        sql = """
            SELECT b.title, a.name
            FROM books b
            JOIN authors a ON b.author_id = a.id
        """
        rules = {'must_have_tables': ['books', 'authors']}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is True
        assert 'books' in result['checks'].get('tables_found', [])
        assert 'authors' in result['checks'].get('tables_found', [])

    def test_missing_count(self):
        """Проверка отсутствия COUNT"""
        sql = "SELECT * FROM books"
        rules = {'must_have_count': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is False
        assert result['checks']['has_count'] is False

    def test_has_count(self):
        """Проверка наличия COUNT"""
        sql = "SELECT COUNT(*) FROM books"
        rules = {'must_have_count': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is True
        assert result['checks']['has_count'] is True

    def test_year_filter_detected(self):
        """Проверка обнаружения фильтра по году"""
        sql = "SELECT * FROM books WHERE year > 1850"
        rules = {'must_have_year_filter': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is True
        assert result['checks']['has_year_filter'] is True

    def test_year_filter_date_format(self):
        """Проверка обнаружения фильтра по дате"""
        sql = "SELECT * FROM books WHERE publication_date >= '1850-01-01'"
        rules = {'must_have_year_filter': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is True
        assert result['checks']['has_year_filter'] is True

    def test_unbalanced_parentheses(self):
        """Проверка несбалансированных скобок"""
        sql = "SELECT * FROM books WHERE (id = 1"
        rules = {'must_be_valid_sql': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is False
        assert 'скобки' in result['errors'][0].lower()

    def test_dangerous_pattern_detected(self):
        """Проверка обнаружения опасной конструкции"""
        sql = "SELECT * FROM books; DROP TABLE books"
        rules = {'must_be_valid_sql': True}
        
        result = self.validator.validate(sql, rules)
        
        assert result['passed'] is False
        assert 'опасная' in result['errors'][0].lower()

    def test_select_star_returns_all_columns(self):
        """Проверка что SELECT * возвращает все колонки"""
        sql = "SELECT * FROM books"
        rules = {
            'must_return_correct_columns': True,
            'must_be_valid_sql': True
        }
        expected = {'books': [{'title': 'Test'}]}
        
        result = self.validator.validate(sql, rules, expected)
        
        assert result['passed'] is True
        assert result['checks'].get('has_correct_columns') is True


# ============================================================================
# Тесты Answer Validator
# ============================================================================

class TestAnswerValidator:
    """Тесты для AnswerValidator"""

    def setup_method(self):
        """Инициализация перед каждым тестом"""
        self.validator = AnswerValidator()

    def test_keywords_present(self):
        """Проверка наличия ключевых слов"""
        answer = "Пушкин написал: Евгений Онегин, Капитанская дочка"
        rules = {'must_contain_keywords': ['Евгений Онегин', 'Капитанская дочка']}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is True
        assert result['checks']['has_keywords'] is True

    def test_keywords_missing(self):
        """Проверка отсутствия ключевых слов"""
        answer = "Пушкин написал: Евгений Онегин"
        rules = {'must_contain_keywords': ['Евгений Онегин', 'Капитанская дочка']}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is False
        assert 'Капитанская дочка' in result['checks'].get('missing_keywords', [])

    def test_russian_language_detected(self):
        """Проверка определения русского языка"""
        answer = "Пушкин написал много книг"
        rules = {'must_be_in_russian': True}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is True
        assert result['checks']['is_russian'] is True

    def test_english_language_detected(self):
        """Проверка определения английского языка"""
        answer = "Pushkin wrote many books"
        rules = {'must_be_in_russian': True}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is False
        assert result['checks']['is_russian'] is False

    def test_min_length_met(self):
        """Проверка минимальной длины"""
        answer = "Это достаточно длинный ответ на вопрос"
        rules = {'min_length': 20}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is True
        assert result['checks']['length'] >= 20

    def test_min_length_not_met(self):
        """Проверка недостаточной длины"""
        answer = "Короткий ответ"
        rules = {'min_length': 20}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is False
        assert result['checks']['length'] < 20

    def test_author_mentioned_full_name(self):
        """Проверка упоминания полного имени автора"""
        answer = "Николай Гоголь написал Мёртвые души"
        rules = {'must_mention_author': True}
        context = {'metadata': {'author': 'Николай Гоголь'}}
        
        result = self.validator.validate(answer, rules, context)
        
        assert result['passed'] is True
        assert result['checks']['mentions_author'] is True

    def test_author_mentioned_last_name(self):
        """Проверка упоминания фамилии автора"""
        answer = "Гоголь написал Мёртвые души"
        rules = {'must_mention_author': True}
        context = {'metadata': {'author': 'Николай Гоголь'}}
        
        result = self.validator.validate(answer, rules, context)
        
        assert result['passed'] is True
        assert result['checks']['mentions_author'] is True

    def test_no_results_indicated(self):
        """Проверка указания на отсутствие результатов"""
        answer = "К сожалению, ничего не найдено по вашему запросу"
        rules = {'must_indicate_no_results': True}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is True
        assert result['checks']['indicates_no_results'] is True

    def test_politeness_detected(self):
        """Проверка обнаружения вежливости"""
        answer = "К сожалению, я не могу найти эту книгу"
        rules = {'must_be_polite': True}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is True
        assert result['checks']['is_polite'] is True

    def test_number_present(self):
        """Проверка наличия числа"""
        answer = "В библиотеке 33 книги"
        rules = {'must_contain_number': True}
        
        result = self.validator.validate(answer, rules)
        
        assert result['passed'] is True
        assert result['checks']['has_number'] is True

    def test_books_match_all_present(self):
        """Проверка соответствия всем ожидаемым книгам"""
        answer = "Пушкин написал: Евгений Онегин, Капитанская дочка, Руслан и Людмила"
        rules = {}
        expected_books = [
            {'title': 'Евгений Онегин'},
            {'title': 'Капитанская дочка'}
        ]
        
        result = self.validator.validate(answer, rules, {}, expected_books)
        
        assert result['passed'] is True
        assert result['checks']['books_match'] is True

    def test_books_match_missing(self):
        """Проверка отсутствия ожидаемой книги"""
        answer = "Пушкин написал: Евгений Онегин"
        rules = {}
        expected_books = [
            {'title': 'Евгений Онегин'},
            {'title': 'Капитанская дочка'}
        ]
        
        result = self.validator.validate(answer, rules, {}, expected_books)
        
        assert result['passed'] is False
        assert result['checks']['books_match'] is False


# ============================================================================
# Тесты Benchmark Validator (Facade)
# ============================================================================

class TestBenchmarkValidator:
    """Тесты для BenchmarkValidator"""

    def setup_method(self):
        """Инициализация перед каждым тестом"""
        self.validator = BenchmarkValidator()

    def test_validate_sql_generation_success(self):
        """Проверка успешной валидации SQL"""
        sql = """
            SELECT b.title FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE a.last_name = 'Гоголь'
        """
        rules = {
            'must_have_tables': ['books', 'authors'],
            'must_have_where': True,
            'must_have_join': True
        }
        
        result = self.validator.validate_sql_generation(sql, rules)
        
        assert result['passed'] is True

    def test_validate_final_answer_success(self):
        """Проверка успешной валидации ответа"""
        answer = "Гоголь написал: Мёртвые души, Ревизор, Тарас Бульба"
        rules = {
            'must_contain_keywords': ['Мёртвые души', 'Ревизор'],
            'must_be_in_russian': True,
            'min_length': 20
        }
        
        result = self.validator.validate_final_answer(answer, rules)
        
        assert result['passed'] is True

    def test_validate_test_result_full(self):
        """Проверка комплексной валидации теста"""
        test_case = {
            'id': 'test_1',
            'validation': {
                'must_have_where': True,
                'must_contain_keywords': ['книга'],
                'must_be_in_russian': True
            },
            'expected_output': {
                'books': [{'title': 'книга'}]
            }
        }
        agent_response = {
            'sql': 'SELECT * FROM books WHERE id = 1',
            'final_answer': 'Это книга Пушкина'
        }
        
        result = self.validator.validate_test_result(test_case, agent_response)
        
        assert result['overall_passed'] is True
        assert result['sql_validation'] is not None
        assert result['answer_validation'] is not None

    def test_validate_test_result_failure(self):
        """Проверка провала комплексной валидации"""
        test_case = {
            'id': 'test_1',
            'validation': {
                'must_have_join': True,  # Нет JOIN в SQL
                'must_contain_keywords': ['несуществующее_слово']  # Нет в ответе
            },
            'expected_output': {}
        }
        agent_response = {
            'sql': 'SELECT * FROM books WHERE id = 1',
            'final_answer': 'Простой ответ'
        }
        
        result = self.validator.validate_test_result(test_case, agent_response)
        
        assert result['overall_passed'] is False
        assert len(result['errors']) > 0


# ============================================================================
# Интеграционные тесты
# ============================================================================

class TestIntegration:
    """Интеграционные тесты для валидатора"""

    def test_full_sql_benchmark_scenario(self):
        """Тест полного сценария SQL бенчмарка"""
        validator = BenchmarkValidator()
        
        # Сценарий: поиск книг Гоголя
        test_case = {
            'id': 'sql_gogol',
            'validation': {
                'must_have_tables': ['books', 'authors'],
                'must_have_where': True,
                'must_have_join': True,
                'must_be_valid_sql': True
            },
            'expected_output': {
                'books': [
                    {'title': 'Мёртвые души'},
                    {'title': 'Ревизор'}
                ],
                'count': 4
            }
        }
        
        agent_response = {
            'sql': """
                SELECT b.title, b.isbn, b.publication_date
                FROM "Lib".books b
                JOIN "Lib".authors a ON b.author_id = a.id
                WHERE a.last_name = 'Гоголь'
                ORDER BY b.title
            """,
            'final_answer': 'Николай Гоголь написал: Мёртвые души, Ревизор, Тарас Бульба, Шинель'
        }
        
        result = validator.validate_test_result(test_case, agent_response)
        
        assert result['overall_passed'] is True
        assert result['sql_validation']['passed'] is True
        assert result['answer_validation']['passed'] is True

    def test_full_answer_benchmark_scenario(self):
        """Тест полного сценария Answer бенчмарка"""
        validator = BenchmarkValidator()
        
        # Сценарий: ответ о книгах Достоевского
        test_case = {
            'id': 'answer_dostoevsky',
            'validation': {
                'must_contain_keywords': [
                    'Бедные люди',
                    'Братья Карамазовы',
                    'Идиот',
                    '4 книг'
                ],
                'must_be_in_russian': True,
                'must_not_hallucinate': True,
                'must_mention_author': True,
                'min_length': 20
            },
            'expected_output': {
                'books': [
                    {'title': 'Бедные люди'},
                    {'title': 'Братья Карамазовы'},
                    {'title': 'Идиот'},
                    {'title': 'Преступление и наказание'}
                ]
            }
        }
        
        agent_response = {
            'final_answer': 'Фёдор Достоевский написал 4 книг: Бедные люди, Братья Карамазовы, Идиот, Преступление и наказание'
        }
        
        context = {
            'metadata': {'author': 'Фёдор Достоевский'},
            'sql_result': {'rows': [], 'count': 4}
        }
        
        result = validator.validate_test_result(test_case, agent_response, context)
        
        assert result['overall_passed'] is True
        assert result['answer_validation']['passed'] is True

    def test_edge_case_no_results(self):
        """Тест краевого случая: нет результатов"""
        validator = BenchmarkValidator()
        
        test_case = {
            'id': 'edge_no_results',
            'validation': {
                'must_indicate_no_results': True,
                'must_be_polite': True,
                'must_be_in_russian': True,
                'must_not_hallucinate': True
            },
            'expected_output': {
                'books': [],
                'count': 0
            }
        }
        
        agent_response = {
            'final_answer': 'К сожалению, ничего не найдено по вашему запросу'
        }
        
        result = validator.validate_test_result(test_case, agent_response)
        
        assert result['overall_passed'] is True

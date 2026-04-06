"""
Общая функция запуска бенчмарка — используется CLI и оптимизатором.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from core.services.benchmarks import BenchmarkValidator


def _extract_sql_from_agent(agent) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Извлечение SQL-запросов и результатов из session_context агента.

    ARGS:
    - agent: экземпляр AgentRuntime

    RETURNS:
    - (sql_queries, sql_results): список SQL-запросов и список результатов
    """
    sql_queries: List[str] = []
    sql_results: List[Dict[str, Any]] = []
    try:
        session_ctx = getattr(agent, 'session_context', None)
        if not session_ctx:
            return sql_queries, sql_results

        data_ctx = getattr(session_ctx, 'data_context', None)
        if not data_ctx:
            return sql_queries, sql_results

        for item in data_ctx.get_all_items():
            content = getattr(item, 'content', None)
            if isinstance(content, dict):
                sql = content.get('sql_query')
                if sql and isinstance(sql, str):
                    sql_queries.append(sql)
                    sql_results.append({
                        'rows': content.get('rows', []),
                        'rowcount': content.get('rowcount', 0),
                        'columns': content.get('columns', []),
                    })
    except Exception:
        pass
    return sql_queries, sql_results


def _extract_sql_from_final_answer(final_answer: str) -> Optional[str]:
    """
    Извлечение SQL из финального ответа (fallback).

    Ищет паттерн sql_query='...' в строке ответа.

    ARGS:
    - final_answer: текст финального ответа

    RETURNS:
    - str или None: найденный SQL-запрос
    """
    if not isinstance(final_answer, str):
        return None
    match = re.search(r"sql_query=['\"]([^'\"]+)['\"]", final_answer)
    if match:
        return match.group(1)
    return None


def _validate_agent_execution(
    agent,
    final_answer: str,
    test_case: Dict[str, Any],
    validator: BenchmarkValidator,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Комплексная валидация: SQL + финальный ответ.

    1. Извлекает SQL из session_context агента
    2. Валидирует SQL через SQLValidator (если в rules есть SQL-правила)
    3. Валидирует финальный ответ через AnswerValidator
    4. Комбинирует результаты

    ARGS:
    - agent: экземпляр AgentRuntime
    - final_answer: текст финального ответа
    - test_case: тест-кейс с validation rules
    - validator: BenchmarkValidator

    RETURNS:
    - (passed: bool, validation_details: dict)
    """
    validation_rules = test_case.get('validation', {})
    if not validation_rules:
        return True, None

    sql_rules = {}
    answer_rules = {}

    sql_rule_keys = {
        'must_be_valid_sql', 'must_have_tables', 'must_have_where',
        'must_have_join', 'must_have_count', 'must_have_year_filter',
        'must_have_group_by', 'must_have_order_by', 'must_return_correct_columns',
        'must_have_multiple_authors', 'must_not_have_unexpected_conditions',
        'must_have_schema',
    }
    answer_rule_keys = {
        'must_contain_keywords', 'must_be_in_russian', 'must_not_hallucinate',
        'min_length', 'must_mention_author', 'must_indicate_no_results',
        'must_be_polite', 'must_contain_number', 'must_not_falsely_report_no_results',
    }

    for key, value in validation_rules.items():
        if key in sql_rule_keys:
            sql_rules[key] = value
        elif key in answer_rule_keys:
            answer_rules[key] = value
        else:
            answer_rules[key] = value

    sql_validation = None
    answer_validation = None
    all_errors = []

    sql_queries, sql_results = _extract_sql_from_agent(agent)
    if not sql_queries and not sql_results:
        sql_from_answer = _extract_sql_from_final_answer(final_answer)
        if sql_from_answer:
            sql_queries = [sql_from_answer]
            sql_results = [{'rows': [], 'rowcount': 0, 'columns': []}]

    if sql_rules:
        if sql_queries:
            sql_rules['_metadata'] = test_case.get('metadata', {})
            for idx, sql in enumerate(sql_queries):
                sql_validation = validator.validate_sql_generation(
                    sql=sql,
                    validation_rules=sql_rules,
                    expected_output=test_case.get('expected_output', {}),
                )
                if sql_validation['passed']:
                    break
                all_errors.extend([f"SQL: {e}" for e in sql_validation.get('errors', [])])
        else:
            all_errors.append("SQL-запрос не найден в результатах агента")

    if answer_rules or not sql_rules:
        sql_ctx = sql_results[0] if sql_results else {}
        answer_validation = validator.validate_final_answer(
            answer=final_answer,
            validation_rules=answer_rules if answer_rules else validation_rules,
            context={
                'metadata': test_case.get('metadata', {}),
                'sql_result': sql_ctx,
            },
            expected_books=test_case.get('expected_output', {}).get('books', []),
        )
        if not answer_validation['passed']:
            all_errors.extend(answer_validation.get('errors', []))

    passed = len(all_errors) == 0

    combined_validation = {
        'passed': passed,
        'errors': all_errors,
        'sql_validation': sql_validation,
        'answer_validation': answer_validation,
    }

    return passed, combined_validation


async def run_agent_benchmark(
    test_cases: List[Dict[str, Any]],
    app_context,
    infra_context,
    verbose: bool = False,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Запуск полного агента на списке вопросов.

    ARGS:
    - test_cases: вопросы [{input, id, name, validation, ...}]
    - app_context: ApplicationContext (prod или sandbox)
    - infra_context: InfrastructureContext
    - verbose: подробный вывод
    - output_file: путь для сохранения результатов (None = не сохранять)

    RETURNS:
    - Dict: {success_rate, success_count, total, avg_steps, results, raw_file}
    """
    from core.agent.factory import AgentFactory
    from core.config.agent_config import AgentConfig

    def log_print(*args, **kwargs):
        print(*args, **kwargs)
        sys.stdout.flush()

    agent_factory = AgentFactory(app_context)
    validator = BenchmarkValidator()

    results = []
    success_count = 0
    total_steps = 0

    for i, tc in enumerate(test_cases, 1):
        if verbose:
            log_print(f"\n{'='*60}")
            log_print(f"ТЕСТ {i}/{len(test_cases)}: {tc.get('name', tc['input'][:50])}...")
            log_print(f"{'='*60}\n")
            log_print("🚀 Агент запущен...")
            sys.stdout.flush()
        else:
            print(f"  [{i}/{len(test_cases)}] {tc.get('name', tc['input'][:60])}...", end=" ")
            sys.stdout.flush()

        agent_config = AgentConfig(max_steps=10, temperature=0.2)
        agent = await agent_factory.create_agent(goal=tc['input'], config=agent_config)

        try:
            result = await agent.run(tc['input'])
            success = True
            final_answer = ''
            steps_count = 0

            if hasattr(result, 'data') and result.data:
                from pydantic import BaseModel
                if isinstance(result.data, BaseModel):
                    final_answer = result.data.final_answer
                    steps_count = result.data.metadata.total_steps if hasattr(result.data, 'metadata') else 0
                elif isinstance(result.data, dict):
                    final_answer = result.data.get('final_answer', '')
                    steps_count = result.metadata.get('total_steps', 0) if hasattr(result, 'metadata') else 0
                else:
                    final_answer = str(result.data)
            else:
                final_answer = str(result)

            if hasattr(result, 'error') and result.error:
                success = False

            if tc.get('validation'):
                success, validation = _validate_agent_execution(
                    agent=agent,
                    final_answer=final_answer,
                    test_case=tc,
                    validator=validator,
                )
            else:
                validation = None

            if success:
                success_count += 1
                if verbose:
                    log_print(f"\n    ✅ ВАЛИДАЦИЯ: PASS")
                    if final_answer:
                        log_print(f"\n    Ответ: {final_answer if len(final_answer) > 0 else ''}")
                else:
                    print(f"✅")
            else:
                errors = validation.get('errors', []) if validation else []
                if verbose:
                    log_print(f"\n    ❌ ВАЛИДАЦИЯ: FAIL - {', '.join(errors[:3])}")
                    if final_answer:
                        log_print(f"\n    Ответ: {final_answer if len(final_answer) > 0 else ''}")
                else:
                    print(f"❌ {errors[0] if errors else 'failed'}")

            results.append({
                'test_id': tc.get('id', f'test_{i}'),
                'input': tc['input'],
                'success': success,
                'final_answer': final_answer,
                'steps': steps_count,
                'validation': validation,
                'metadata': result.metadata if hasattr(result, 'metadata') else {},
            })
            total_steps += steps_count

        except Exception as e:
            if verbose:
                log_print(f"\n    ❌ Ошибка: {e}")
            else:
                print(f"❌ {e}")
            results.append({
                'test_id': tc.get('id', f'test_{i}'),
                'input': tc['input'],
                'success': False,
                'error': str(e),
            })

    total = len(results)
    success_rate = success_count / total if total > 0 else 0
    avg_steps = total_steps / success_count if success_count > 0 else 0

    if not verbose:
        print(f"\n📊 {success_count}/{total} ({success_rate:.1%}) | avg steps: {avg_steps:.1f}")

    benchmark_result = {
        'success_rate': success_rate,
        'success_count': success_count,
        'total': total,
        'avg_steps': avg_steps,
        'results': results,
    }

    # Сохранение в файл если указан
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        full_data = {
            'run_at': datetime.now().isoformat(),
            'test_results': results,
            'metrics': {
                'total': total,
                'successful': success_count,
                'failed': total - success_count,
                'success_rate': success_rate,
                'total_steps': total_steps,
                'avg_steps': avg_steps,
            },
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
        benchmark_result['raw_file'] = str(output_path)

    return benchmark_result

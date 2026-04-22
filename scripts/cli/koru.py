#!/usr/bin/env python3
"""
Koru — единый CLI для бенчмарков, оптимизации и управления промптами.

ИСПОЛЬЗОВАНИЕ:
    python -m scripts.cli.koru bench run --level sql
    python -m scripts.cli.koru bench run -g "Какие книги написал Пушкин?"
    python -m scripts.cli.koru bench generate
    python -m scripts.cli.koru bench compare results1.json results2.json
    python -m scripts.cli.koru bench history
    python -m scripts.cli.koru bench optimize --size 2 --mode accuracy
    python -m scripts.cli.koru prompt create --capability planning.create_plan --version v1.0.0
    python -m scripts.cli.koru prompt status
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.cli._utils import (
    init_contexts, cleanup, log_print, print_separator,
    load_benchmark, save_results, load_results,
    calculate_metrics, print_metrics, compare_metrics, show_history,
    select_test_cases,
)


# ===========================================================================
# BENCH: run
# ===========================================================================

async def cmd_bench_run(args) -> int:
    """Запуск РЕАЛЬНОГО агента на бенчмарке."""
    print_separator("ЗАПУСК РЕАЛЬНОГО АГЕНТА НА БЕНЧМАРКЕ")

    # Режим одного теста или полный бенчмарк
    if args.goal:
        log_print(f"Goal: {args.goal}")
        log_print(f"Mode: SINGLE TEST\n")
        test_cases = [{"input": args.goal, "id": "single_test", "name": "Single Test"}]
    else:
        benchmark = load_benchmark(args.benchmark)
        if not benchmark:
            return 1

        test_cases = select_test_cases(benchmark, level=args.level, limit=args.limit)

        sql_tests = benchmark["levels"].get("sql_generation", {}).get("test_cases", [])
        answer_tests = benchmark["levels"].get("final_answer", {}).get("test_cases", [])

        log_print(f"📊 Уровень: {args.level}")
        log_print(f"📊 SQL Generation: {len(sql_tests)} тестов")
        log_print(f"📊 Final Answer: {len(answer_tests)} тестов")
        log_print(f"📊 Запускаем: {len(test_cases)} тестов\n")

    # Инициализация
    log_print("🔄 Инициализация инфраструктуры...")
    app, infra = await init_contexts(profile="dev", data_dir="data")
    log_print("✅ Инфраструктура готова\n")

    from core.agent.factory import AgentFactory
    from core.config.agent_config import AgentConfig
    from core.components.benchmarks import BenchmarkValidator

    agent_factory = AgentFactory(app)
    validator = BenchmarkValidator()

    results = {
        "run_at": datetime.now().isoformat(),
        "benchmark": args.benchmark,
        "mode": "single" if args.goal else "full",
        "level": args.level,
        "test_results": [],
    }

    for i, test in enumerate(test_cases, 1):
        log_print(f"\n{'=' * 60}")
        log_print(f"ТЕСТ {i}/{len(test_cases)}: {test.get('name', test['input'][:50])}...")
        log_print(f"{'=' * 60}\n")

        agent_config = AgentConfig(max_steps=10, temperature=0.2)
        agent = await agent_factory.create_agent(goal=test["input"], config=agent_config)

        log_print("🚀 Агент запущен...\n")
        result = await agent.run(test["input"])
        await asyncio.sleep(0.1)  # Очистка буфера

        # Извлечение финального ответа
        final_answer = ""
        steps_count = 0
        success = True

        if hasattr(result, "data") and result.data:
            from pydantic import BaseModel
            if isinstance(result.data, BaseModel):
                final_answer = getattr(result.data, "final_answer", "")
                steps_count = getattr(getattr(result.data, "metadata", None), "total_steps", 0)
            elif isinstance(result.data, dict):
                final_answer = result.data.get("final_answer", "")
                steps_count = result.metadata.get("total_steps", 0) if hasattr(result, "metadata") else 0
            else:
                final_answer = str(result.data)

        if hasattr(result, "error") and result.error:
            success = False

        # Валидация
        validation_result = None
        if test.get("validation"):
            validation_result = validator.validate_final_answer(
                answer=final_answer,
                validation_rules=test.get("validation", {}),
                context={"metadata": test.get("metadata", {})},
                expected_books=test.get("expected_output", {}).get("books", []),
            )
            success = validation_result["passed"]

            if validation_result["passed"]:
                log_print(f"\n    ✅ ВАЛИДАЦИЯ: PASS")
            else:
                log_print(f"\n    ❌ ВАЛИДАЦИЯ: FAIL - {', '.join(validation_result['errors'][:3])}")

        # Вывод ответа
        if final_answer:
            print(f"\n{final_answer}")

        test_result = {
            "test_id": test.get("id", f"test_{i}"),
            "input": test["input"],
            "success": success,
            "final_answer": final_answer,
            "metadata": result.metadata if hasattr(result, "metadata") else {},
            "steps": steps_count,
            "validation": validation_result,
        }
        results["test_results"].append(test_result)

    # Метрики
    metrics = calculate_metrics(results["test_results"])

    print_separator("ИТОГОВАЯ СТАТИСТИКА")
    log_print(f"\n📊 Общие метрики:")
    log_print(f"   Всего тестов: {metrics['total']}")
    log_print(f"   ✅ Успешных: {metrics['successful']}")
    log_print(f"   ❌ Failed: {metrics['failed']}")
    log_print(f"   📈 Success Rate: {metrics['success_rate']:.1f}%")

    if metrics["successful"] > 0:
        log_print(f"\n📈 Эффективность:")
        log_print(f"   Всего шагов: {metrics['total_steps']}")
        log_print(f"   Среднее шагов на тест: {metrics['avg_steps']:.2f}")
        log_print(f"   Efficiency Score: {metrics['efficiency_score']:.1f}/100")

    log_print(f"\n{'=' * 60}")
    log_print(f"   ОБЩАЯ ОЦЕНКА: {metrics['overall_score']:.1f}/100 {metrics['emoji']} {metrics['grade']}")
    log_print(f"{'=' * 60}")

    results["metrics"] = metrics
    save_results(results, args.output)

    await cleanup(app, infra)
    return 0 if metrics["success_rate"] >= 50 else 1


# ===========================================================================
# BENCH: generate
# ===========================================================================

async def cmd_bench_generate(args) -> int:
    """Генерация бенчмарка из реальных данных БД."""
    print_separator("ГЕНЕРАЦИЯ БЕНЧМАРКА ДЛЯ ТЕСТИРОВАНИЯ АГЕНТА")
    log_print(f"Output: {args.output}\n")

    log_print("🔄 Инициализация инфраструктуры...")
    app, infra = await init_contexts(profile="dev", data_dir="data")
    log_print("✅ Инфраструктура готова\n")

    db_provider = infra.lifecycle_manager.get_resource("default_db")
    if not db_provider:
        log_print("❌ DB провайдер не найден")
        await cleanup(app, infra)
        return 1

    try:
        await db_provider.query("SELECT 1")
        log_print("✅ Подключение к БД успешно")
    except Exception as e:
        log_print(f"❌ Ошибка подключения к БД: {e}")
        await cleanup(app, infra)
        return 1

    # Генерация тестов
    print_separator("ГЕНЕРАЦИЯ ТЕСТОВЫХ КЕЙСОВ")
    sql_tests = await _generate_sql_generation_tests(db_provider)
    final_answer_tests = await _generate_final_answer_tests(db_provider)

    log_print(f"\n✅ SQL Generation тестов: {len(sql_tests)}")
    log_print(f"✅ Final Answer тестов: {len(final_answer_tests)}")

    benchmark = {
        "generated_at": datetime.now().isoformat(),
        "version": "1.0",
        "description": "Бенчмарк для тестирования агента (SQL + Final Answer)",
        "levels": {
            "sql_generation": {
                "description": "Проверка качества генерации SQL запросов",
                "test_cases": sql_tests,
            },
            "final_answer": {
                "description": "Проверка качества финального ответа",
                "test_cases": final_answer_tests,
            },
        },
        "metadata": {
            "source": "database",
            "dynamic": True,
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(benchmark, f, indent=2, ensure_ascii=False)

    log_print(f"\n💾 Бенчмарк сохранён: {output_path}")
    log_print(f"📊 Размер: {output_path.stat().st_size / 1024:.1f} KB")

    await cleanup(app, infra)
    return 0


async def _generate_sql_generation_tests(db_provider) -> List[Dict[str, Any]]:
    """Генерация тестов для SQL Generation."""
    tests = []

    authors_result = await db_provider.query('SELECT * FROM "Lib".authors ORDER BY last_name')
    authors = [
        {
            "id": row.get("id") if isinstance(row, dict) else row[0],
            "first_name": row.get("first_name") if isinstance(row, dict) else row[1],
            "last_name": row.get("last_name") if isinstance(row, dict) else row[2],
        }
        for row in authors_result.rows
    ]

    test_authors = authors[:3]
    question_templates = [
        lambda a: f"Какие книги написал {a['first_name']} {a['last_name']}?",
        lambda a: f"Найти все книги автора {a['last_name']}",
        lambda a: f"Покажи книги {a['first_name']} {a['last_name']}",
    ]

    for i, author in enumerate(test_authors):
        last_name = author["last_name"]
        first_name = author["first_name"]

        books_result = await db_provider.query(f"""
            SELECT b.id, b.title, b.isbn, b.publication_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE a.last_name = '{last_name}'
            ORDER BY b.title
        """)

        books = [
            {
                "title": row.get("title") if isinstance(row, dict) else row[1],
                "year": str(row.get("publication_date")) if isinstance(row, dict) else str(row[3]),
            }
            for row in books_result.rows
        ]

        nl_query = question_templates[i](author)
        tests.append({
            "id": f"sql_{last_name.lower().replace(' ', '_')}_{hash(nl_query) % 1000}",
            "name": f"SQL: {nl_query[:50]}",
            "input": nl_query,
            "expected_output": {"success": True, "books": books, "count": len(books)},
            "validation": {
                "must_have_tables": ["books", "authors"],
                "must_have_where": True,
                "must_have_join": True,
                "must_be_valid_sql": True,
                "must_return_correct_columns": ["title", "isbn", "publication_date"],
            },
            "metadata": {
                "author": f"{first_name} {last_name}",
                "expected_count": len(books),
                "difficulty": "easy" if len(books) <= 2 else "medium",
            },
        })

    # Агрегация
    tests.append({
        "id": "sql_aggregation_count",
        "name": "SQL: Посчитать количество книг",
        "input": "Сколько всего книг в библиотеке?",
        "expected_output": {"success": True, "query_type": "aggregation"},
        "validation": {
            "must_have_tables": ["books"],
            "must_have_count": True,
            "must_be_valid_sql": True,
        },
        "metadata": {"query_type": "aggregation", "difficulty": "easy"},
    })

    # Фильтрация по году
    tests.append({
        "id": "sql_filter_by_year",
        "name": "SQL: Книги после 1850 года",
        "input": "Найти книги изданные после 1850 года",
        "expected_output": {"success": True, "query_type": "filtered_search"},
        "validation": {
            "must_have_schema": ["Lib.books"],
            "must_have_where": True,
            "must_have_year_filter": True,
            "must_be_valid_sql": True,
            "must_not_have_unexpected_conditions": True,
            "must_not_falsely_report_no_results": True,
        },
        "metadata": {"filter": {"year_from": 1850}, "difficulty": "medium"},
    })

    # Семантический поиск
    tests.extend([
        {
            "id": "sql_semantic_captain_daughter",
            "name": "SQL: Роман о пугачёвском восстании",
            "input": "Найди книгу про пугачёвское восстание и офицера который присягнул самозванцу",
            "expected_output": {"success": True, "books": [{"title": "Капитанская дочка"}], "count": 1},
            "validation": {
                "must_have_tables": ["books"],
                "must_have_where": True,
                "must_be_valid_sql": True,
                "must_return_correct_columns": ["title", "isbn", "publication_date"],
            },
            "metadata": {"search_type": "semantic", "target_book": "Капитанская дочка", "difficulty": "hard"},
        },
        {
            "id": "sql_semantic_crime_punishment",
            "name": "SQL: Роман о преступлении студента",
            "input": "Найди роман где студент убил старуху процентщицу",
            "expected_output": {"success": True, "books": [{"title": "Преступление и наказание"}], "count": 1},
            "validation": {
                "must_have_tables": ["books"],
                "must_have_where": True,
                "must_be_valid_sql": True,
                "must_return_correct_columns": ["title", "isbn", "publication_date"],
            },
            "metadata": {"search_type": "semantic", "target_book": "Преступление и наказание", "difficulty": "hard"},
        },
    ])

    return tests


async def _generate_final_answer_tests(db_provider) -> List[Dict[str, Any]]:
    """Генерация тестов для Final Answer."""
    tests = []

    authors_result = await db_provider.query('SELECT * FROM "Lib".authors ORDER BY last_name')
    authors = [
        {
            "id": row.get("id") if isinstance(row, dict) else row[0],
            "first_name": row.get("first_name") if isinstance(row, dict) else row[1],
            "last_name": row.get("last_name") if isinstance(row, dict) else row[2],
        }
        for row in authors_result.rows
    ]

    for author in authors[:6]:
        last_name = author["last_name"]
        first_name = author["first_name"]

        books_result = await db_provider.query(f"""
            SELECT b.title, b.publication_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE a.last_name = '{last_name}'
            ORDER BY b.title
        """)

        books = [
            {
                "title": row.get("title") if isinstance(row, dict) else row[1],
                "year": str(row.get("publication_date")) if isinstance(row, dict) else str(row[3]),
            }
            for row in books_result.rows
        ]

        required_keywords = [book["title"] for book in books[:3]]
        if len(books) > 3:
            required_keywords.append(f"{len(books)} книг")

        sql_context = {
            "query": f"SELECT * FROM books WHERE author = '{last_name}'",
            "rows": books,
            "count": len(books),
        }

        tests.append({
            "id": f"answer_{last_name.lower().replace(' ', '_')}",
            "name": f"Answer: Книги {first_name} {last_name}",
            "input": f"Какие книги написал {first_name} {last_name}?",
            "context": {"sql_result": sql_context},
            "expected_output": {"success": True, "language": "ru", "format": "natural_language"},
            "validation": {
                "must_contain_keywords": required_keywords,
                "must_be_in_russian": True,
                "must_not_hallucinate": True,
                "must_mention_author": True,
                "min_length": 20,
            },
            "metadata": {
                "author": f"{first_name} {last_name}",
                "expected_books": len(books),
                "difficulty": "easy" if len(books) <= 2 else "medium",
            },
        })

    # Нет результатов
    tests.append({
        "id": "answer_no_results",
        "name": "Answer: Нет результатов",
        "input": "Какие книги написал Неизвестный Автор?",
        "context": {
            "sql_result": {"query": "SELECT * FROM books WHERE author = 'Неизвестный Автор'", "rows": [], "count": 0},
        },
        "expected_output": {"success": True, "language": "ru", "format": "natural_language"},
        "validation": {
            "must_indicate_no_results": True,
            "must_be_polite": True,
            "must_be_in_russian": True,
            "must_not_hallucinate": True,
        },
        "metadata": {"expected_books": 0, "difficulty": "easy", "edge_case": "no_results"},
    })

    # Агрегация
    tests.append({
        "id": "answer_aggregation",
        "name": "Answer: Количество книг",
        "input": "Сколько всего книг в библиотеке?",
        "context": {"sql_result": {"query": "SELECT COUNT(*) FROM books", "rows": [{"count": 33}], "count": 33}},
        "expected_output": {"success": True, "language": "ru", "format": "natural_language"},
        "validation": {
            "must_contain_number": True,
            "must_be_in_russian": True,
            "must_not_hallucinate": True,
        },
        "metadata": {"query_type": "aggregation", "difficulty": "easy"},
    })

    return tests


# ===========================================================================
# BENCH: compare
# ===========================================================================

async def cmd_bench_compare(args) -> int:
    """Сравнение двух результатов бенчмарков."""
    if len(args.results_files) < 2:
        log_print("❌ Укажите два файла результатов для сравнения")
        return 1

    r1 = load_results(args.results_files[0])
    r2 = load_results(args.results_files[1])
    if not r1 or not r2:
        return 1

    m1 = r1.get("metrics", {})
    m2 = r2.get("metrics", {})

    print_metrics(args.results_files[0], m1)
    print_metrics(args.results_files[1], m2)
    compare_metrics(m1, m2)
    return 0


# ===========================================================================
# BENCH: history
# ===========================================================================

async def cmd_bench_history(args) -> int:
    """Показать историю запусков."""
    show_history(benchmarks_dir=args.dir)
    return 0


# ===========================================================================
# BENCH: optimize
# ===========================================================================

async def cmd_bench_optimize(args) -> int:
    """Запуск оптимизации через OptimizationOrchestrator."""
    from scripts.cli._utils import load_first_n_questions, build_scenarios_from_questions

    questions = load_first_n_questions(args.benchmark_file, args.size)
    if not questions:
        log_print("❌ Нет вопросов для запуска")
        return 1

    # Определяем capability
    if args.capability:
        # Явно указанная capability
        capability = args.capability
        questions = [q for q in questions if q.get('level') in capability or capability in q.get('id', '')]
    else:
        # Берём первую найденную capability из вопросов
        capability = questions[0].get('level', 'agent_benchmark') if questions else 'agent_benchmark'

    log_print(f"📋 Загружено {len(questions)} вопросов для capability: {capability}")
    for q in questions:
        log_print(f"   • [{q['level']}] {q['name']}")
    log_print()

    # Инфраструктура
    import yaml
    from core.config.models import SystemConfig
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus

    with open("core/config/defaults/dev.yaml", "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    infra_config = SystemConfig(**raw_config)
    infra = InfrastructureContext(infra_config)
    await infra.initialize()

    event_bus = infra.event_bus
    llm_provider = infra.lifecycle_manager.get_resource("default_llm")

    log_print("✅ Инфраструктура инициализирована (настоящая LLM)\n")

    # Сценарии
    scenarios = build_scenarios_from_questions(questions, event_bus)

    # Executor callback
    async def executor_callback(input_text: str, version_id: str) -> Dict[str, Any]:
        from datetime import datetime
        start = datetime.now()
        try:
            response = await llm_provider.generate(
                prompt=input_text,
                system_prompt="Ты — помощник. Отвечай точно и по делу.",
                temperature=0.2,
                max_tokens=2048,
            )
            elapsed = (datetime.now() - start).total_seconds() * 1000
            text = response.text if hasattr(response, "text") else str(response)
            return {
                "success": True,
                "output": text,
                "execution_time_ms": elapsed,
                "tokens_used": response.tokens_used if hasattr(response, "tokens_used") else 0,
            }
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "execution_time_ms": elapsed,
                "tokens_used": 0,
            }

    # Компоненты оркестратора
    from core.services.optimization.orchestrator import (
        OptimizationOrchestrator, OrchestratorV2Config,
    )
    from core.components.benchmarks.benchmark_runner import BenchmarkRunner, BenchmarkRunConfig
    from core.services.optimization.trace_collector import TraceCollector
    from core.services.optimization.evaluator import Evaluator
    from core.services.optimization.prompt_generator import PromptGenerator
    from core.services.optimization.version_manager import VersionManager
    from core.services.optimization.safety_layer import SafetyLayer
    from core.services.optimization.pattern_analyzer import PatternAnalyzer
    from core.services.optimization.prompt_analyzer import PromptResponseAnalyzer
    from core.services.optimization.root_cause_analyzer import RootCauseAnalyzer
    from core.services.optimization.example_extractor import ExampleExtractor
    from core.components.benchmarks.benchmark_models import PromptVersion, OptimizationMode
    from core.models.data.execution_trace import ExecutionTrace, StepTrace, ErrorDetail, ErrorType
    from unittest.mock import AsyncMock

    # Fake traces
    fake_trace = ExecutionTrace(
        session_id="fake_session",
        agent_id="fake_agent",
        goal="SQL benchmark",
        steps=[
            StepTrace(
                step_number=1,
                capability="agent_benchmark",
                goal="Generate SQL for books query",
                errors=[
                    ErrorDetail(error_type=ErrorType.SYNTAX_ERROR, message="Invalid SQL syntax", capability="agent_benchmark", step_number=1),
                    ErrorDetail(error_type=ErrorType.LOGIC_ERROR, message="Query returns wrong results - missing JOIN", capability="agent_benchmark", step_number=1),
                ],
            ),
            StepTrace(
                step_number=2,
                capability="agent_benchmark",
                goal="Generate SQL for author search",
                errors=[
                    ErrorDetail(error_type=ErrorType.VALIDATION_ERROR, message="Schema violation: missing required column", capability="agent_benchmark", step_number=2),
                ],
            ),
        ],
    )

    trace_collector = AsyncMock()
    trace_collector.collect_traces = AsyncMock(return_value=[fake_trace])
    trace_collector.build_dataset = AsyncMock()

    benchmark_runner = BenchmarkRunner(
        event_bus=event_bus,
        executor_callback=executor_callback,
        config=BenchmarkRunConfig(temperature=0.2, seed=42, max_retries=1, timeout_seconds=120),
    )

    evaluator = Evaluator(event_bus=event_bus)
    prompt_generator = PromptGenerator(event_bus=event_bus)
    version_manager = VersionManager(event_bus=event_bus)
    safety_layer = SafetyLayer(event_bus=event_bus)
    pattern_analyzer = PatternAnalyzer()
    prompt_analyzer = PromptResponseAnalyzer()
    root_cause_analyzer = RootCauseAnalyzer()
    example_extractor = ExampleExtractor()

    baseline = PromptVersion(
        id="baseline_v1", parent_id=None, capability="agent_benchmark",
        prompt="Ты — помощник. Отвечай точно и по делу.", status="active",
    )
    await version_manager.register(baseline)
    await version_manager.promote(baseline.id, "agent_benchmark")

    mode_map = {
        "accuracy": OptimizationMode.ACCURACY,
        "speed": OptimizationMode.SPEED,
        "tokens": OptimizationMode.TOKENS,
        "balanced": OptimizationMode.BALANCED,
    }

    orch_config = OrchestratorV2Config(max_iterations=3, target_accuracy=0.8, min_improvement=0.05, timeout_seconds=600)
    orchestrator = OptimizationOrchestrator(
        trace_collector=trace_collector, pattern_analyzer=pattern_analyzer,
        prompt_analyzer=prompt_analyzer, root_cause_analyzer=root_cause_analyzer,
        example_extractor=example_extractor, benchmark_runner=benchmark_runner,
        evaluator=evaluator, prompt_generator=prompt_generator,
        version_manager=version_manager, safety_layer=safety_layer,
        event_bus=event_bus, config=orch_config,
    )
    orchestrator.set_executor_callback(executor_callback)

    async def load_scenarios(version, capability):
        return scenarios

    orchestrator._load_scenarios_for_version = load_scenarios

    log_print(f"🚀 Запуск оптимизации (mode={args.mode}, iterations={orch_config.max_iterations})\n")

    result = await orchestrator.optimize(capability=capability, mode=mode_map[args.mode])

    # Отчёт
    log_print("═" * 60)
    log_print("📊 РЕЗУЛЬТАТ")
    log_print("═" * 60)
    log_print(f"  Статус:        {result.status}")
    log_print(f"  From version:  {result.from_version}")
    log_print(f"  To version:    {result.to_version}")
    log_print(f"  Итерации:      {result.iterations}")
    log_print(f"  Цель:          {'✅ достигнута' if result.target_achieved else '❌ не достигнута'}")

    if result.initial_metrics:
        log_print(f"  Initial score: {result.initial_metrics.get('score', 'N/A')}")
    if result.final_metrics:
        log_print(f"  Final score:   {result.final_metrics.get('score', 'N/A')}")
    if result.improvements:
        for metric, val in result.improvements.items():
            log_print(f"  {metric}: {val:+.1f}%")
    if result.error:
        log_print(f"  Ошибка:        {result.error}")

    log_print()
    report = orchestrator.get_optimization_report(result)
    log_print(json.dumps(report, ensure_ascii=False, indent=2))

    await infra.shutdown()
    return 0


# ===========================================================================
# PROMPT: create / promote / archive / status
# ===========================================================================

def _cmd_prompt_create(args) -> int:
    """Создать новый промпт-черновик."""
    from core.models.data.prompt import Prompt, PromptStatus, PromptMetadata
    from core.models.data.prompt_serialization import PromptSerializer

    content_templates = {
        "planning": """# Планирование задачи

Вы - помощник по планированию задач. Ваша цель - помочь пользователю разбить сложную задачу на подзадачи.

## Контекст:
{{ context }}

## Задача:
{{ task }}

## Требования:
{{ requirements }}

## Результат:
""",
        "analysis": """# Анализ информации

Вы - аналитический помощник. Ваша цель - проанализировать предоставленную информацию и предоставить структурированный обзор.

## Данные для анализа:
{{ data }}

## Критерии анализа:
{{ criteria }}

## Результат анализа:
""",
        "default": """# {{ title }}

{{ description }}

## Входные данные:
{% for var in input_vars %}
- {{ var }}
{% endfor %}

## Результат:
""",
    }

    template = content_templates.get(args.template, content_templates["default"])

    metadata = PromptMetadata(
        version=args.version,
        skill=args.capability.split(".")[0] if "." in args.capability else "general",
        capability=args.capability,
        role="system",
        language="ru",
        tags=[args.template] if args.template else ["general"],
        variables=["title", "description", "input_vars"] if args.template == "default" else [],
        status=PromptStatus.DRAFT,
        quality_metrics={},
        author=args.author,
        changelog=[f"Создан {datetime.now().isoformat()}"],
    )

    prompt = Prompt(metadata=metadata, content=template)
    base_path = Path("prompts")
    file_path = PromptSerializer.to_file(prompt, base_path)

    log_print(f"✅ Промпт создан: {file_path}")
    return 0


def _cmd_prompt_promote(args) -> int:
    """Продвинуть промпт в активный статус."""

    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    prompt = registry.get_prompt_by_capability_and_version(args.capability, args.version)

    if not prompt:
        log_print(f"❌ Промпт {args.capability} версии {args.version} не найден")
        return 1

    prompt.metadata.status = PromptStatus.ACTIVE
    prompt.metadata.updated_at = datetime.now(timezone.utc)
    prompt.metadata.changelog.append(f"Продвинут в активные {datetime.now(timezone.utc).isoformat()}")

    success = registry.promote(prompt)
    if success:
        log_print(f"✅ Промпт {args.capability} версии {args.version} продвинут в активные")
    else:
        log_print(f"❌ Ошибка при продвижении промпта {args.capability} версии {args.version}")
    return 0 if success else 1


def _cmd_prompt_archive(args) -> int:
    """Архивировать промпт."""

    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    success = registry.archive(args.capability, args.version, args.reason)

    if success:
        log_print(f"✅ Промпт {args.capability} версии {args.version} архивирован")
    else:
        log_print(f"❌ Ошибка при архивации промпта {args.capability} версии {args.version}")
    return 0 if success else 1


def _cmd_prompt_status(args) -> int:
    """Показать статус всех промптов."""

    registry = PromptRegistry(Path("prompts") / "registry.yaml")

    log_print("\nАктивные промпты:")
    for capability, entry in registry.active_prompts.items():
        log_print(f"  - {capability}: {entry.version} ({entry.status.value}) - {entry.file_path}")

    log_print("\nАрхивные промпты:")
    for (capability, version), entry in registry.archived_prompts.items():
        log_print(f"  - {capability}: {version} ({entry.status.value}) - {entry.file_path}")

    return 0


# ===========================================================================
# Главный парсер
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="koru",
        description="Koru — единый CLI для бенчмарков, оптимизации и управления промптами",
    )
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # ----- bench -----
    bench_parser = subparsers.add_parser("bench", help="Бенчмарки и оптимизация")
    bench_sub = bench_parser.add_subparsers(dest="bench_command", help="Команды бенчмарков")

    # bench run
    run_parser = bench_sub.add_parser("run", help="Запуск реального агента на бенчмарке")
    run_parser.add_argument("--benchmark", "-b", type=str, default="data/benchmarks/agent_benchmark.json")
    run_parser.add_argument("--output", "-o", type=str, default="data/benchmarks/real_benchmark_results.json")
    run_parser.add_argument("--goal", "-g", type=str, default=None, help="Один тестовый вопрос")
    run_parser.add_argument("--limit", "-l", type=int, default=None, help="Максимум тестов")
    run_parser.add_argument("--level", type=str, default="all", choices=["all", "sql", "answer"])

    # bench generate
    gen_parser = bench_sub.add_parser("generate", help="Генерация бенчмарка из БД")
    gen_parser.add_argument("--output", "-o", type=str, default="data/benchmarks/agent_benchmark.json")

    # bench compare
    cmp_parser = bench_sub.add_parser("compare", help="Сравнение результатов")
    cmp_parser.add_argument("results_files", nargs=2, help="Два файла результатов")

    # bench history
    hist_parser = bench_sub.add_parser("history", help="История запусков")
    hist_parser.add_argument("--dir", type=str, default="data/benchmarks")

    # bench optimize
    opt_parser = bench_sub.add_parser("optimize", help="Оптимизация через orchestrator")
    opt_parser.add_argument("--size", type=int, default=2, help="Количество вопросов")
    opt_parser.add_argument("--mode", type=str, default="accuracy", choices=["accuracy", "speed", "tokens", "balanced"])
    opt_parser.add_argument("--benchmark-file", type=str, default="data/benchmarks/agent_benchmark.json")
    opt_parser.add_argument("--capability", type=str, default=None, help="Capability для тестирования (по умолчанию: все из бенчмарка)")

    # ----- prompt -----
    prompt_parser = subparsers.add_parser("prompt", help="Управление промптами")
    prompt_sub = prompt_parser.add_subparsers(dest="prompt_command", help="Команды промптов")

    # prompt create
    create_p = prompt_sub.add_parser("create", help="Создать новый промпт-черновик")
    create_p.add_argument("--capability", required=True)
    create_p.add_argument("--version", required=True)
    create_p.add_argument("--template", default="default", choices=["planning", "analysis", "default"])
    create_p.add_argument("--author", required=True)

    # prompt promote
    promote_p = prompt_sub.add_parser("promote", help="Продвинуть промпт в активный статус")
    promote_p.add_argument("--capability", required=True)
    promote_p.add_argument("--version", required=True)

    # prompt archive
    archive_p = prompt_sub.add_parser("archive", help="Архивировать промпт")
    archive_p.add_argument("--capability", required=True)
    archive_p.add_argument("--version", required=True)
    archive_p.add_argument("--reason", default="")

    # prompt status
    prompt_sub.add_parser("status", help="Показать статус всех промптов")

    return parser


# ===========================================================================
# Entry point
# ===========================================================================

async def async_main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # ---- bench ----
    if args.command == "bench":
        if not args.bench_command:
            parser.parse_args(["bench", "--help"])
            return 1

        if args.bench_command == "run":
            return await cmd_bench_run(args)
        elif args.bench_command == "generate":
            return await cmd_bench_generate(args)
        elif args.bench_command == "compare":
            return await cmd_bench_compare(args)
        elif args.bench_command == "history":
            return await cmd_bench_history(args)
        elif args.bench_command == "optimize":
            return await cmd_bench_optimize(args)

    # ---- prompt ----
    elif args.command == "prompt":
        if not args.prompt_command:
            parser.parse_args(["prompt", "--help"])
            return 1

        if args.prompt_command == "create":
            return _cmd_prompt_create(args)
        elif args.prompt_command == "promote":
            return _cmd_prompt_promote(args)
        elif args.prompt_command == "archive":
            return _cmd_prompt_archive(args)
        elif args.prompt_command == "status":
            return _cmd_prompt_status(args)

    return 1


def main():
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()

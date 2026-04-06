#!/usr/bin/env python3
"""
CLI скрипт для запуска оптимизации промптов на новой архитектуре.

ПЛАН РАБОТЫ:
1. Baseline — запуск бенчмарка → текущая точность
2. Анализ — какие тесты failed + session.jsonl (цепочка шагов)
3. TraceCollector — читает логи → ExecutionTrace → анализаторы → root causes
4. OptimizationOrchestrator — генерирует кандидатов (улучшенные промпты)
5. Тестирование кандидатов — sandbox ApplicationContext с новым промптом → полный агент на тех же вопросах
6. Промоушн — лучший кандидат → обновление промпта в data/prompts/
7. Финальный бенчмарк — подтверждение улучшения

ИСПОЛЬЗОВАНИЕ:
    python scripts/cli/run_optimization.py --capability vector_books.search --mode accuracy
    python scripts/cli/run_optimization.py --capability vector_books.search --benchmark-size 2 --dry-run
    python scripts/cli/run_optimization.py --session-log data/logs/.../session.jsonl --analyze-only
"""
import argparse
import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Запуск оптимизации промптов (новая архитектура)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s --capability vector_books.search --mode accuracy
  %(prog)s --capability vector_books.search --benchmark-size 2
  %(prog)s --capability vector_books.search --dry-run --verbose
  %(prog)s --session-log data/logs/.../session.jsonl --analyze-only
        """
    )

    parser.add_argument(
        '-c', '--capability',
        type=str,
        required=False,
        help='Название способности для оптимизации'
    )

    parser.add_argument(
        '--list-capabilities',
        action='store_true',
        help='Список доступных способностей'
    )

    parser.add_argument(
        '-m', '--mode',
        type=str,
        choices=['accuracy', 'speed', 'tokens', 'balanced'],
        default='accuracy',
        help='Режим оптимизации (по умолчанию: accuracy)'
    )

    parser.add_argument(
        '-t', '--target-accuracy',
        type=float,
        default=0.9,
        help='Целевая точность (по умолчанию: 0.9)'
    )

    parser.add_argument(
        '--max-iterations',
        type=int,
        default=3,
        help='Максимальное количество итераций (по умолчанию: 3)'
    )

    parser.add_argument(
        '--min-improvement',
        type=float,
        default=0.05,
        help='Минимальное улучшение для продолжения (по умолчанию: 0.05)'
    )

    parser.add_argument(
        '--benchmark-size',
        type=int,
        default=10,
        help='Количество вопросов из бенчмарка для тестирования (по умолчанию: 10)'
    )

    parser.add_argument(
        '--benchmark-level',
        type=str,
        choices=['all', 'sql', 'answer'],
        default='sql',
        help='Уровень бенчмарка (по умолчанию: sql)'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Файл для вывода результатов в JSON'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробный вывод результатов'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Тестовый запуск без реальных изменений'
    )

    parser.add_argument(
        '--session-log',
        type=str,
        help='Путь к session.jsonl для анализа'
    )

    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Только анализ лога без запуска оптимизации'
    )

    return parser.parse_args()


def list_capabilities(data_dir: Path) -> list:
    """Получение списка доступных способностей."""
    capabilities = []
    prompts_dir = data_dir / 'prompts' / 'skill'
    if prompts_dir.exists():
        for item in prompts_dir.iterdir():
            if item.is_dir() and list(item.glob('*.yaml')):
                capabilities.append(item.name)
    metrics_dir = data_dir / 'metrics'
    if metrics_dir.exists():
        for item in metrics_dir.iterdir():
            if item.is_dir() and item.name not in capabilities:
                capabilities.append(item.name)
    return sorted(set(capabilities))


def load_benchmark_questions(benchmark_file: str, level: str = 'sql', limit: int = 10) -> List[Dict[str, Any]]:
    """Загрузка вопросов из бенчмарка."""
    benchmark_path = Path(benchmark_file)
    if not benchmark_path.exists():
        return []

    with open(benchmark_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    test_cases = []
    if level in ('sql', 'all'):
        test_cases.extend(data.get('levels', {}).get('sql_generation', {}).get('test_cases', []))
    if level in ('answer', 'all'):
        test_cases.extend(data.get('levels', {}).get('final_answer', {}).get('test_cases', []))

    return test_cases[:limit]


def find_latest_session_log(logs_dir: str = "data/logs") -> Optional[Path]:
    """Поиск последнего session.jsonl."""
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        return None

    session_files = sorted(logs_path.rglob("session.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return session_files[0] if session_files else None


def load_prompts_for_capability(capability: str, data_dir: str = "data") -> List[Dict[str, Any]]:
    """Загрузка промптов для capability из data/prompts/. Приоритет: active > draft > остальные."""
    prompts = []
    prompts_dir = Path(data_dir) / 'prompts' / 'skill' / capability
    if not prompts_dir.exists():
        return prompts

    import yaml
    for prompt_file in prompts_dir.glob('*.yaml'):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data and isinstance(data, dict):
            prompts.append({
                'file': str(prompt_file),
                'capability': data.get('capability', ''),
                'version': data.get('version', ''),
                'status': data.get('status', 'draft'),
                'content': data.get('content', ''),
                'variables': data.get('variables', []),
            })

    # Сортировка: active primero, затем draft, остальные
    status_priority = {'active': 0, 'draft': 1}
    prompts.sort(key=lambda p: status_priority.get(p['status'], 2))
    return prompts


def save_prompt_to_file(prompt_content: str, capability: str, version: str, status: str = "candidate") -> str:
    """Сохранение промпта кандидата в data/prompts/."""
    import yaml

    prompts_dir = Path('data') / 'prompts' / 'skill' / capability
    prompts_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{capability}.system_{version}.yaml"
    filepath = prompts_dir / filename

    prompt_data = {
        'capability': capability,
        'component_type': 'skill',
        'version': version,
        'status': status,
        'description': f"Оптимизированный промпт {version}",
        'content': prompt_content,
        'variables': [],
        'metadata': {
            'author': 'optimization_orchestrator',
            'created': datetime.now().isoformat(),
        },
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(prompt_data, f, allow_unicode=True, default_flow_style=False)

    return str(filepath)


def analyze_session_log_for_errors(log_path: Path, failed_test_ids: List[str], verbose: bool = False) -> Dict[str, Any]:
    """
    Глубокий анализ session.jsonl — поиск цепочки шагов для failed тестов.

    ARGS:
    - log_path: путь к session.jsonl
    - failed_test_ids: ID проваленных тестов (для корреляции)
    - verbose: подробный вывод

    RETURNS:
    - Dict с анализом ошибок по шагам
    """
    if not log_path or not log_path.exists():
        return {'error': 'Log file not found'}

    errors_by_step = []
    tool_calls = []
    llm_calls = []

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event.get('event_type', event.get('type', ''))

                # Поиск ошибок в шагах
                if 'error' in event or 'exception' in event:
                    error_info = {
                        'event_type': event_type,
                        'error': event.get('error') or event.get('exception', ''),
                        'timestamp': event.get('timestamp', ''),
                        'capability': event.get('capability', ''),
                        'step': event.get('step', ''),
                    }
                    errors_by_step.append(error_info)

                # Сбор tool calls для понимания что делал агент
                if 'tool' in event_type.lower() or 'tool_call' in event_type.lower():
                    tool_calls.append({
                        'type': event_type,
                        'tool': event.get('tool_name', event.get('capability', '')),
                        'success': event.get('success', True),
                    })

                # Сбор LLM calls
                if 'llm' in event_type.lower() or 'prompt' in event_type.lower():
                    llm_calls.append({
                        'type': event_type,
                        'timestamp': event.get('timestamp', ''),
                    })

    except Exception as e:
        return {'error': f'Failed to parse log: {str(e)}'}

    analysis = {
        'log_file': str(log_path),
        'total_errors': len(errors_by_step),
        'total_tool_calls': len(tool_calls),
        'total_llm_calls': len(llm_calls),
        'errors': errors_by_step[:10],
        'failed_tool_calls': [t for t in tool_calls if not t.get('success', True)][:5],
    }

    if verbose:
        print(f"\n  📄 Лог: {log_path}")
        print(f"  Ошибок в логе: {len(errors_by_step)}")
        print(f"  Tool calls: {len(tool_calls)}")
        print(f"  LLM calls: {len(llm_calls)}")

        if errors_by_step:
            print(f"\n  Последние ошибки:")
            for err in errors_by_step[:5]:
                cap = err.get('capability', '?')
                step = err.get('step', '?')
                error_msg = str(err.get('error', ''))
                print(f"    [{cap}:{step}] {error_msg}")

        failed_tools = [t for t in tool_calls if not t.get('success', True)]
        if failed_tools:
            print(f"\n  Failed tool calls:")
            for t in failed_tools[:5]:
                print(f"    ❌ {t.get('tool', '?')}")

    return analysis


async def run_baseline_benchmark(
    test_cases: List[Dict[str, Any]],
    infra_context,
    config,
    benchmark_level: str = 'sql',
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    ЭТАП 1: Baseline бенчмарк — запуск полного агента через общий модуль.
    """
    from core.config.app_config import AppConfig
    from core.application_context.application_context import ApplicationContext
    from core.services.benchmarks.benchmark_runner_agent import run_agent_benchmark

    print("\n" + "=" * 60)
    print("ЭТАП 1: Baseline бенчмарк")
    print("=" * 60)
    print(f"Вопросов: {len(test_cases)}\n")

    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir="data",
        discovery=infra_context.resource_discovery,
    )

    prod_context = ApplicationContext(
        infrastructure_context=infra_context,
        config=app_config,
        profile="prod",
    )
    await prod_context.initialize()

    try:
        result = await run_agent_benchmark(
            test_cases=test_cases,
            app_context=prod_context,
            infra_context=infra_context,
            verbose=verbose,
            output_file='data/benchmarks/real_benchmark_results.json',
        )
        return result
    finally:
        await prod_context.shutdown()


async def create_sandbox_context(
    infra_context,
    config,
):
    """
    Создание sandbox ApplicationContext.
    Промпты загружаются из data/prompts/ при инициализации.
    """
    from core.config.app_config import AppConfig
    from core.application_context.application_context import ApplicationContext

    app_config = AppConfig.from_discovery(
        profile="sandbox",
        data_dir="data",
        discovery=infra_context.resource_discovery,
    )

    sandbox = ApplicationContext(
        infrastructure_context=infra_context,
        config=app_config,
        profile="sandbox",
        prompt_loading_config={"default": "draft"},
    )
    await sandbox.initialize()
    return sandbox


async def run_candidate_benchmark_on_sandbox(
    test_cases: List[Dict[str, Any]],
    sandbox,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Запуск бенчмарка на уже созданном sandbox контексте.
    Не создаёт новый AppConfig — переиспользует переданный sandbox.
    """
    from core.agent.factory import AgentFactory
    from core.config.agent_config import AgentConfig
    from core.services.benchmarks import BenchmarkValidator
    from core.services.benchmarks.benchmark_runner_agent import _validate_agent_execution

    print(f"  🔄 [run_candidate_benchmark] Создаю AgentFactory...")
    agent_factory = AgentFactory(sandbox)
    print(f"  🔄 [run_candidate_benchmark] AgentFactory создан")
    validator = BenchmarkValidator()

    success_count = 0
    total_steps = 0
    results = []

    for i, tc in enumerate(test_cases, 1):
        print(f"  🔄 [run_candidate_benchmark] Тест {i}/{len(test_cases)}: {tc.get('input', '')[:50]}...")
        agent_config = AgentConfig(max_steps=10, temperature=0.2)
        print(f"  🔄 [run_candidate_benchmark] Создаю агента...")
        agent = await agent_factory.create_agent(goal=tc['input'], config=agent_config)
        print(f"  🔄 [run_candidate_benchmark] Агент создан, запускаю...")

        try:
            result = await agent.run(tc['input'])
            print(f"  🔄 [run_candidate_benchmark] Агент завершил")
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

            if hasattr(result, 'error') and result.error:
                success = False

            validation = None
            if tc.get('validation'):
                success, validation = _validate_agent_execution(
                    agent=agent,
                    final_answer=final_answer,
                    test_case=tc,
                    validator=validator,
                )

            if success:
                success_count += 1
                if verbose:
                    print(f"✅")

            results.append({
                'test_id': tc.get('id', f'test_{i}'),
                'input': tc['input'],
                'success': success,
                'final_answer': final_answer,
                'steps': steps_count,
                'validation': validation,
            })
            total_steps += steps_count

        except Exception as e:
            if verbose:
                print(f"❌ {e}")
            results.append({
                'test_id': tc.get('id', f'test_{i}'),
                'input': tc['input'],
                'success': False,
                'error': str(e),
            })

    success_rate = success_count / len(test_cases) if test_cases else 0
    avg_steps = total_steps / success_count if success_count > 0 else 0

    return {
        'success_rate': success_rate,
        'success_count': success_count,
        'total': len(test_cases),
        'avg_steps': avg_steps,
        'results': results,
    }


async def run_optimization_v2(
    capability: str,
    mode: str,
    target_accuracy: float,
    max_iterations: int,
    min_improvement: float,
    benchmark_size: int = 10,
    benchmark_level: str = 'sql',
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Полный цикл оптимизации промптов.
    """
    print(f"\n{'='*60}")
    print(f"Оптимизация: {capability}")
    print(f"{'='*60}")
    print(f"Режим: {mode}")
    print(f"Целевая точность: {target_accuracy}")
    print(f"Максимум итераций: {max_iterations}")
    print(f"Бенчмарк: {benchmark_size} вопросов ({benchmark_level})")
    print(f"Dry run: {dry_run}")
    print(f"{'='*60}\n")

    infra_context = None
    sandbox_for_callback = None

    try:
        # === ИМПОРТЫ ===
        from core.config import get_config
        from core.infrastructure_context.infrastructure_context import InfrastructureContext
        from core.application_context.application_context import ApplicationContext
        from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
        from core.services.benchmarks.benchmark_models import (
            OptimizationMode, PromptVersion, MutationType,
        )

        from core.agent.components.optimization import (
            Evaluator,
            PromptGenerator,
            VersionManager,
            SafetyLayer,
            OptimizationOrchestrator,
            TraceCollector,
            PatternAnalyzer,
            PromptResponseAnalyzer,
            RootCauseAnalyzer,
            ExampleExtractor,
        )
        from core.services.benchmarks.benchmark_runner import BenchmarkRunner, BenchmarkRunConfig
        from core.agent.components.optimization.trace_collector import TraceCollectionConfig
        from core.agent.components.optimization.evaluator import EvaluationConfig
        from core.agent.components.optimization.prompt_generator import GenerationConfig
        from core.agent.components.optimization.safety_layer import SafetyConfig
        from core.agent.components.optimization.orchestrator import OrchestratorV2Config

        # === ЗАГРУЗКА КОНФИГУРАЦИИ ===
        config = get_config(profile='dev', data_dir='data')
        data_dir = Path(config.data_dir)

        # === ЭТАП 0: Загрузка вопросов бенчмарка ===
        test_cases = load_benchmark_questions(
            benchmark_file='data/benchmarks/agent_benchmark.json',
            level=benchmark_level,
            limit=benchmark_size,
        )
        if not test_cases:
            print("❌ Не найдено вопросов в бенчмарке")
            return {'status': 'failed', 'error': 'No benchmark questions found'}

        print(f"📋 Загружено {len(test_cases)} вопросов из бенчмарка\n")

        # === ИНИЦИАЛИЗАЦИЯ ИНФРАСТРУКТУРЫ ===
        print("🔄 Инициализация инфраструктуры...")
        infra_context = InfrastructureContext(config)
        await infra_context.initialize()
        print("✅ Инфраструктура готова\n")

        event_bus = infra_context.event_bus

        # === ЭТАП 1: Baseline бенчмарк ===
        baseline = await run_baseline_benchmark(
            test_cases=test_cases,
            infra_context=infra_context,
            config=config,
            benchmark_level=benchmark_level,
            verbose=verbose,
        )

        if baseline['success_rate'] >= target_accuracy:
            print(f"\n✅ Целевая точность уже достигнута: {baseline['success_rate']:.1%} >= {target_accuracy:.1%}")
            await infra_context.shutdown()
            infra_context = None
            return {
                'status': 'target_already_achieved',
                'baseline': baseline,
                'capability': capability,
            }

        # === ЭТАП 2: Анализ ошибок + session.jsonl ===
        print("\n" + "=" * 60)
        print("ЭТАП 2: Анализ ошибок")
        print("=" * 60)

        failed_tests = [r for r in baseline['results'] if not r['success']]
        failed_ids = [r.get('test_id', '') for r in failed_tests]
        print(f"Failed тестов: {len(failed_tests)}/{len(test_cases)}")

        for ft in failed_tests:
            errors = ft.get('validation', {}).get('errors', []) if ft.get('validation') else []
            error_msg = errors[0] if errors else ft.get('error', 'unknown')
            print(f"  ❌ {ft.get('test_id', '?')}: {error_msg[:80]}")

        # Глубокий анализ session.jsonl
        latest_log = find_latest_session_log("data/logs")
        if latest_log:
            print(f"\n  📄 Анализ лога: {latest_log}")
            log_analysis = analyze_session_log_for_errors(
                log_path=latest_log,
                failed_test_ids=failed_ids,
                verbose=verbose,
            )
            if log_analysis.get('total_errors', 0) > 0:
                print(f"  Найдено ошибок в логе: {log_analysis['total_errors']}")
                if log_analysis.get('failed_tool_calls'):
                    print(f"  Failed tool calls: {len(log_analysis['failed_tool_calls'])}")
        else:
            print("  ⚠️ session.jsonl не найден — анализ только по результатам валидации")
            log_analysis = {}

        # === ЭТАП 3: Сбор traces ===
        print("\n" + "=" * 60)
        print("ЭТАП 3: Сбор traces")
        print("=" * 60)

        from core.agent.components.optimization.trace_handler import TraceHandler

        trace_handler = TraceHandler(
            session_handler=infra_context.session_handler,
            logs_dir="data/logs",
        )
        trace_collector = TraceCollector(
            trace_handler=trace_handler,
            config=TraceCollectionConfig(),
        )

        traces = await trace_collector.collect_traces(capability)
        print(f"  Trace найдено: {len(traces)}")

        if not traces and latest_log:
            print(f"  Попытка чтения из последнего лога: {latest_log.parent}")
            trace_handler = TraceHandler(
                session_handler=infra_context.session_handler,
                logs_dir=str(latest_log.parent),
            )
            trace_collector = TraceCollector(
                trace_handler=trace_handler,
                config=TraceCollectionConfig(),
            )
            traces = await trace_collector.collect_traces(capability)
            print(f"  Trace из лога: {len(traces)}")

        if not traces:
            print("  ⚠️ Trace не найдены — оптимизация продолжится без анализа traces")

        # Анализ traces
        pattern_analyzer = PatternAnalyzer()
        prompt_analyzer = PromptResponseAnalyzer()
        root_cause_analyzer = RootCauseAnalyzer()
        example_extractor = ExampleExtractor()

        patterns = pattern_analyzer.analyze(traces) if traces else []
        prompt_issues = prompt_analyzer.analyze_prompts(traces) if traces else []
        response_issues = prompt_analyzer.analyze_responses(traces) if traces else []
        root_causes = root_cause_analyzer.analyze(patterns, prompt_issues, response_issues) if traces else []
        good_examples, error_examples = example_extractor.extract_few_shot_examples(
            traces, capability, num_good=3, num_bad=2
        ) if traces else ([], [])

        print(f"  Паттернов: {len(patterns)}")
        print(f"  Проблем промптов: {len(prompt_issues)}")
        print(f"  Root causes: {len(root_causes)}")
        print(f"  Примеров: {len(good_examples)} good, {len(error_examples)} bad\n")

        # === ЭТАП 4: Загрузка промптов и создание baseline версии ===
        print("=" * 60)
        print("ЭТАП 4: Загрузка промптов")
        print("=" * 60)

        prompts = load_prompts_for_capability(capability, 'data')
        print(f"  Промптов найдено: {len(prompts)}")

        for p in prompts:
            marker = " ← baseline" if p['status'] == 'active' else ""
            print(f"    {p['capability']}@{p['version']} ({p['status']}){marker}")

        # Определяем основной метод skill для оптимизации (тот что использует LLM)
        # Для book_library это search_books (dynamic, требует LLM для генерации SQL)
        # Ищем system промпт — он содержит инструкции для LLM
        system_prompts = [p for p in prompts if '.system' in p['capability'] and p['status'] == 'active']
        if not system_prompts:
            system_prompts = [p for p in prompts if '.system' in p['capability']]
        if not system_prompts:
            system_prompts = prompts  # fallback: все промпты

        # Берём первый active system промпт как baseline
        baseline_prompt = system_prompts[0] if system_prompts else None
        baseline_prompt_content = baseline_prompt['content'] if baseline_prompt else ""
        baseline_prompt_capability = baseline_prompt['capability'] if baseline_prompt else capability

        if not baseline_prompt_content:
            print(f"  ⚠️ Промпт не найден, оптимизация невозможна")
            return

        print(f"\n  📝 Базовый промпт: {baseline_prompt_capability}@{baseline_prompt['version']}")
        print(f"  📝 Длина промпта: {len(baseline_prompt_content)} символов")

        baseline_version = PromptVersion(
            id=f"{baseline_prompt_capability}_baseline",
            parent_id=None,
            capability=baseline_prompt_capability,
            prompt=baseline_prompt_content,
            status="active",
        )

        # === Создание компонентов оптимизации ===
        print("\n🔧 Создание компонентов оптимизации...\n")

        # Базовый sandbox для получения baseline
        base_sandbox = await create_sandbox_context(
            infra_context=infra_context,
            config=config,
        )
        print(f"  📦 Sandbox контекст создан (profile={base_sandbox.profile})")
        print(f"  🎯 Оптимизируемый метод: {baseline_prompt_capability}")

        benchmark_config = BenchmarkRunConfig(
            temperature=0.0,
            seed=42,
            max_retries=1,
            timeout_seconds=120,
        )

        async def executor_callback(input_text: str, version_id: str) -> dict:
            """
            executor_callback — для каждого кандидата создаём новый контекст.
            """
            start = datetime.now()
            try:
                print(f"  🔄 [executor_callback] Начало для {version_id}")
                candidate = await version_manager.get_version(
                    capability=baseline_prompt_capability,
                    version_id=version_id,
                )
                if not candidate:
                    return {
                        'success': False,
                        'output': None,
                        'error': f'Version {version_id} not found',
                        'execution_time_ms': 0,
                        'tokens_used': 0,
                    }
                print(f"  🔄 [executor_callback] Найден кандидат, создаю контекст...")

                # Создаём новый контекст с промптом кандидата
                sandbox_for_test = await base_sandbox.clone_with_prompt_content_override(
                    capability=baseline_prompt_capability,
                    prompt_content=candidate.prompt,
                )
                print(f"  📦 Новый контекст создан для версии {version_id}")

                # Запускаем один вопрос на новом контексте
                print(f"  🔄 [executor_callback] Запускаю benchmark...")
                result = await run_candidate_benchmark_on_sandbox(
                    test_cases=[{'input': input_text, 'id': version_id, 'validation': None}],
                    sandbox=sandbox_for_test,
                    verbose=False,
                )
                print(f"  🔄 [executor_callback] Benchmark завершён")

                # Очищаем контекст
                print(f"  🔄 [executor_callback] Очищаю контекст...")
                await sandbox_for_test.shutdown()

                elapsed = (datetime.now() - start).total_seconds() * 1000
                return {
                    'success': result['success_count'] > 0,
                    'output': result['results'][0].get('final_answer', '') if result.get('results') else '',
                    'execution_time_ms': elapsed,
                    'tokens_used': 0,
                    'candidate_prompt_length': len(candidate.prompt),
                }

            except Exception as e:
                elapsed = (datetime.now() - start).total_seconds() * 1000
                import traceback
                print(f"  ❌ executor_callback exception: {e}")
                print(f"  Traceback: {traceback.format_exc()}")
                return {
                    'success': False,
                    'output': None,
                    'error': str(e),
                    'execution_time_ms': elapsed,
                    'tokens_used': 0,
                }

        benchmark_runner = BenchmarkRunner(
            event_bus=event_bus,
            executor_callback=executor_callback,
            config=benchmark_config,
        )
        print("  ✅ BenchmarkRunner (реальный агент, кэшированный sandbox)")

        evaluation_config = EvaluationConfig(
            success_rate_weight=0.4,
            execution_success_weight=0.3,
            sql_validity_weight=0.2,
            latency_weight=0.1,
            min_success_rate=0.8,
            max_latency_ms=5000.0,
        )
        evaluator = Evaluator(event_bus=event_bus, config=evaluation_config)
        print("  ✅ Evaluator")

        generation_config = GenerationConfig(
            temperature=0.7,
            max_tokens=4000,
            top_p=0.9,
            diversity_threshold=0.3,
            max_candidates=3,
        )
        prompt_generator = PromptGenerator(event_bus=event_bus, config=generation_config)
        print("  ✅ PromptGenerator")

        version_manager = VersionManager(event_bus=event_bus)
        await version_manager.register(baseline_version)
        await version_manager.promote(baseline_version.id, baseline_prompt_capability)
        print(f"  ✅ VersionManager (baseline зарегистрирован: {baseline_prompt_capability})")

        safety_config = SafetyConfig(
            max_success_rate_degradation=0.5,
            max_error_rate_increase=0.5,
            max_latency_increase_factor=2.0,
            min_acceptable_score=0.3,
            check_sql_injection=True,
            check_empty_result=True,
        )
        safety_layer = SafetyLayer(event_bus=event_bus, config=safety_config)
        print("  ✅ SafetyLayer")

        # === ЭТАП 5-6: Оптимизация ===
        print("\n" + "=" * 60)
        print("ЭТАП 5-6: Оптимизация и тестирование кандидатов")
        print("=" * 60)

        orchestrator_config = OrchestratorV2Config(
            max_iterations=max_iterations,
            target_accuracy=target_accuracy,
            min_improvement=min_improvement,
            timeout_seconds=600,
            max_examples=5,
            max_error_examples=3,
            benchmark_size=benchmark_size,
            baseline_results=baseline,
        )

        orchestrator = OptimizationOrchestrator(
            trace_collector=trace_collector,
            pattern_analyzer=pattern_analyzer,
            prompt_analyzer=prompt_analyzer,
            root_cause_analyzer=root_cause_analyzer,
            example_extractor=example_extractor,
            benchmark_runner=benchmark_runner,
            evaluator=evaluator,
            prompt_generator=prompt_generator,
            version_manager=version_manager,
            safety_layer=safety_layer,
            event_bus=event_bus,
            config=orchestrator_config,
        )
        orchestrator.set_executor_callback(executor_callback)

        mode_map = {
            'accuracy': OptimizationMode.ACCURACY,
            'speed': OptimizationMode.SPEED,
            'tokens': OptimizationMode.TOKENS,
            'balanced': OptimizationMode.BALANCED,
        }
        optimization_mode = mode_map.get(mode, OptimizationMode.ACCURACY)

        if dry_run:
            print("⚠️  DRY RUN: Тестовый запуск без реальных изменений\n")
            result = {
                'capability': capability,
                'mode': mode,
                'timestamp': datetime.now().isoformat(),
                'status': 'dry_run',
                'baseline': baseline,
                'traces_count': len(traces),
                'patterns_count': len(patterns),
                'root_causes_count': len(root_causes),
                'log_analysis': log_analysis,
            }
        else:
            # Используем конкретный метод (не общую capability) для оптимизации
            opt_capability = baseline_prompt_capability if baseline_prompt_capability else capability
            print(f"  🎯 Запуск оптимизации для: {opt_capability}")
            opt_result = await orchestrator.optimize(
                capability=opt_capability,
                mode=optimization_mode,
            )

            if opt_result is None:
                print("❌ Оптимизация не была запущена")
                return {
                    'capability': capability,
                    'mode': mode,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'not_started',
                }

            result = {
                'capability': capability,
                'mode': mode,
                'timestamp': opt_result.timestamp.isoformat() if hasattr(opt_result, 'timestamp') else datetime.now().isoformat(),
                'status': opt_result.status if hasattr(opt_result, 'status') else 'completed',
                'baseline': baseline,
                'from_version': opt_result.from_version if hasattr(opt_result, 'from_version') else 'unknown',
                'to_version': opt_result.to_version if hasattr(opt_result, 'to_version') else 'unknown',
                'iterations': opt_result.iterations if hasattr(opt_result, 'iterations') else 0,
                'target_achieved': opt_result.target_achieved if hasattr(opt_result, 'target_achieved') else False,
                'initial_metrics': opt_result.initial_metrics if hasattr(opt_result, 'initial_metrics') else {},
                'final_metrics': opt_result.final_metrics if hasattr(opt_result, 'final_metrics') else {},
                'improvements': opt_result.improvements if hasattr(opt_result, 'improvements') else {},
                'error': opt_result.error if hasattr(opt_result, 'error') else None,
            }

            # === ЭТАП 7: Финальный бенчмарк ===
            if opt_result.to_version and opt_result.to_version != opt_result.from_version:
                print("\n" + "=" * 60)
                print("ЭТАП 7: Финальный бенчмарк (подтверждение)")
                print("=" * 60)

                new_version = await version_manager.get_version(opt_result.to_version)
                if new_version:
                    # Сохраняем промпт кандидата в файл
                    saved_path = save_prompt_to_file(
                        prompt_content=new_version.prompt,
                        capability=capability,
                        version=new_version.id,
                        status="candidate",
                    )
                    print(f"  💾 Промпт сохранён: {saved_path}")

                    # Создаём отдельный sandbox для финального бенчмарка
                    final_sandbox = await create_sandbox_context(
                        infra_context=infra_context,
                        prompt_overrides={capability: new_version.prompt},
                        config=config,
                    )

                    try:
                        final_result = await run_candidate_benchmark_on_sandbox(
                            test_cases=test_cases,
                            sandbox=final_sandbox,
                            verbose=verbose,
                        )

                        result['final_benchmark'] = final_result
                        result['baseline_accuracy'] = baseline['success_rate']
                        result['final_accuracy'] = final_result['success_rate']
                        result['improvement'] = final_result['success_rate'] - baseline['success_rate']
                        result['saved_prompt_path'] = saved_path

                        print(f"\n📊 Сравнение:")
                        print(f"  Baseline:  {baseline['success_rate']:.1%} ({baseline['success_count']}/{baseline['total']})")
                        print(f"  Final:     {final_result['success_rate']:.1%} ({final_result['success_count']}/{final_result['total']})")
                        improvement = final_result['success_rate'] - baseline['success_rate']
                        sign = '+' if improvement >= 0 else ''
                        print(f"  Изменение: {sign}{improvement:.1%}")

                    finally:
                        await final_sandbox.shutdown()

        # === Вывод результатов ===
        print(f"\n{'='*60}")
        print(f"Результаты оптимизации")
        print(f"{'='*60}")

        status = result.get('status', 'unknown')
        if status == 'dry_run':
            print(f"Статус: 🔹 Dry run")
            print(f"Baseline: {baseline['success_rate']:.1%}")
            print(f"Trace: {result.get('traces_count', 0)}")
            print(f"Root causes: {result.get('root_causes_count', 0)}")
        else:
            target = '✅' if result.get('target_achieved') else '⚠️'
            print(f"Статус: {target} {status}")
            print(f"Baseline: {baseline['success_rate']:.1%}")
            if result.get('final_accuracy') is not None:
                print(f"Final:    {result['final_accuracy']:.1%}")
                sign = '+' if result.get('improvement', 0) >= 0 else ''
                print(f"Change:   {sign}{result.get('improvement', 0):.1%}")
            if result.get('saved_prompt_path'):
                print(f"Prompt:   {result['saved_prompt_path']}")

        print(f"\n{'='*60}\n")

        if verbose:
            print("Полные результаты:")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        return result

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return {
            'capability': capability,
            'mode': mode,
            'timestamp': datetime.now().isoformat(),
            'status': 'failed',
            'error': str(e),
        }

    finally:
        # Гарантированный cleanup
        if sandbox_for_callback:
            try:
                await sandbox_for_callback.shutdown()
            except Exception:
                pass
        if infra_context:
            try:
                await infra_context.shutdown()
            except Exception:
                pass


async def analyze_session_log(log_path: str, verbose: bool = False):
    """Анализ лога сессии."""
    print("\n" + "=" * 60)
    print("Session Log Analyzer")
    print("=" * 60)

    try:
        from core.agent.components.optimization.session_log_parser import SessionLogParser
        from core.agent.components.optimization.prompt_analyzer import analyze_prompts_from_session

        parser = SessionLogParser()
        session = parser.parse_file(Path(log_path))
        session_report = parser.generate_analysis_report(session)
        prompt_report = await analyze_prompts_from_session(session_report)

        print(f"\nPath: {log_path}")
        print(f"Duration: {session_report['summary']['duration_seconds']:.1f}s")
        print(f"LLM calls: {session_report['summary']['total_llm_calls']}")
        print(f"Actions: {session_report['summary']['total_actions']}")
        print(f"Failed: {session_report['summary']['actions_with_errors']}")

        if session_report.get('failed_actions'):
            print(f"\nErrors ({len(session_report['failed_actions'])}):")
            for err in session_report['failed_actions'][:5]:
                print(f"  - [{err.get('action', '?')}] {err.get('error', 'N/A')[:80]}")

        if prompt_report.get('issues'):
            print(f"\nPrompt issues ({len(prompt_report['issues'])}):")
            for issue in prompt_report['issues']:
                print(f"  [{issue['severity'].upper()}] {issue['type']}: {issue['description'][:80]}")

        return {'session': session_report, 'prompts': prompt_report}

    except Exception as e:
        print(f"\n❌ Analysis error: {e}")
        return {'status': 'failed', 'error': str(e)}


async def main():
    """Основная функция"""
    args = parse_args()

    print("\n" + "=" * 60)
    print("Optimization CLI")
    print("=" * 60)

    try:
        from core.config import get_config
        config = get_config(profile='dev', data_dir='data')
        data_dir = Path(config.data_dir)
    except Exception:
        data_dir = Path('data')

    # Анализ лога
    if args.session_log:
        result = await analyze_session_log(args.session_log, args.verbose)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Сохранено в {args.output}")
        if args.analyze_only or not args.capability:
            sys.exit(0)

    # Список способностей
    if args.list_capabilities:
        capabilities = list_capabilities(data_dir)
        print(f"\nДоступные способности ({len(capabilities)}):")
        for cap in capabilities:
            print(f"  - {cap}")
        sys.exit(0)

    if not args.capability:
        print("❌ Укажите --capability, --list-capabilities или --session-log")
        sys.exit(1)

    try:
        result = await run_optimization_v2(
            capability=args.capability,
            mode=args.mode,
            target_accuracy=args.target_accuracy,
            max_iterations=args.max_iterations,
            min_improvement=args.min_improvement,
            benchmark_size=args.benchmark_size,
            benchmark_level=args.benchmark_level,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n✅ Сохранено в {args.output}")

        if result.get('status') == 'failed':
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())

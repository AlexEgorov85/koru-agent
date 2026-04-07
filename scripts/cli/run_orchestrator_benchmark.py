#!/usr/bin/env python3
"""
Быстрый запуск OptimizationOrchestrator на первых N вопросах бенчмарка.
Использует НАСТОЯЩУЮ LLM из dev.yaml (llama_cpp).

ИСПОЛЬЗОВАНИЕ:
    python scripts/cli/run_orchestrator_benchmark.py --size 2 --mode accuracy
    python scripts/cli/run_orchestrator_benchmark.py --size 2 --mode speed --verbose
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

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Запуск оркестратора на бенчмарке')
    parser.add_argument('--size', type=int, default=2, help='Количество вопросов из бенчмарка')
    parser.add_argument('--mode', type=str, default='accuracy',
                        choices=['accuracy', 'speed', 'tokens', 'balanced'])
    parser.add_argument('--benchmark-file', type=str, default='data/benchmarks/agent_benchmark.json')
    parser.add_argument('--verbose', action='store_true')
    return parser.parse_args()


def load_first_n_questions(benchmark_file: str, n: int) -> List[Dict[str, Any]]:
    benchmark_path = Path(benchmark_file)
    if not benchmark_path.exists():
        print(f"❌ Бенчмарк не найден: {benchmark_file}")
        return []

    with open(benchmark_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    questions = []
    for level_name, level_data in data.get('levels', {}).items():
        for tc in level_data.get('test_cases', []):
            if len(questions) >= n:
                return questions
            questions.append({
                'id': tc.get('id', f'{level_name}_{len(questions)}'),
                'name': tc.get('name', ''),
                'input': tc.get('input', ''),
                'expected_output': tc.get('expected_output', {}),
                'level': level_name,
            })
    return questions


def build_scenarios_from_questions(questions: List[Dict[str, Any]], event_bus):
    from core.components.services.benchmarks.benchmark_models import (
        BenchmarkScenario, ExpectedOutput, EvaluationCriterion, EvaluationType,
    )

    scenarios = []
    for q in questions:
        expected = ExpectedOutput(
            content=q['expected_output'],
            criteria=[
                EvaluationCriterion(
                    name='accuracy',
                    evaluation_type=EvaluationType.SEMANTIC,
                    weight=1.0,
                    threshold=0.8,
                )
            ],
        )
        scenario = BenchmarkScenario(
            id=q['id'],
            name=q['name'],
            description=f"Бенчмарк: {q['level']}",
            goal=q['input'],
            expected_output=expected,
            criteria=[
                EvaluationCriterion(
                    name='accuracy',
                    evaluation_type=EvaluationType.SEMANTIC,
                    weight=1.0,
                    threshold=0.8,
                )
            ],
            timeout_seconds=60,
            metadata={'level': q['level']},
        )
        scenarios.append(scenario)
    return scenarios


async def main():
    args = parse_args()

    questions = load_first_n_questions(args.benchmark_file, args.size)
    if not questions:
        print("❌ Нет вопросов для запуска")
        return

    print(f"📋 Загружено {len(questions)} вопросов:")
    for q in questions:
        print(f"   • [{q['level']}] {q['name']}")
    print()

    # === Инфраструктура без discovery (обход сломанных промптов) ===
    import yaml
    from core.config.models import SystemConfig
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType

    with open('core/config/defaults/dev.yaml', 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)

    infra_config = SystemConfig(**raw_config)
    infra_context = InfrastructureContext(infra_config)
    await infra_context.initialize()

    event_bus = infra_context.event_bus
    llm_provider = infra_context.lifecycle_manager.get_resource('default_llm')

    print("✅ Инфраструктура инициализирована (настоящая LLM)")
    print()

    # === Сценарии бенчмарка ===
    scenarios = build_scenarios_from_questions(questions, event_bus)

    # === Executor callback (реальная LLM) ===
    async def executor_callback(input_text: str, version_id: str) -> Dict[str, Any]:
        start = datetime.now()
        try:
            response = await llm_provider.generate(
                prompt=input_text,
                system_prompt="Ты — помощник. Отвечай точно и по делу.",
                temperature=0.2,
                max_tokens=2048,
            )
            elapsed = (datetime.now() - start).total_seconds() * 1000
            text = response.text if hasattr(response, 'text') else str(response)
            return {
                'success': True,
                'output': text,
                'execution_time_ms': elapsed,
                'tokens_used': response.tokens_used if hasattr(response, 'tokens_used') else 0,
            }
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            return {
                'success': False,
                'output': None,
                'error': str(e),
                'execution_time_ms': elapsed,
                'tokens_used': 0,
            }

    # === Компоненты оркестратора ===
    from core.agent.components.optimization.orchestrator import (
        OptimizationOrchestrator, OrchestratorV2Config,
    )
    from core.agent.components.optimization.trace_collector import TraceCollector
    from core.components.services.benchmarks.benchmark_runner import BenchmarkRunner, BenchmarkRunConfig
    from core.agent.components.optimization.evaluator import Evaluator
    from core.agent.components.optimization.prompt_generator import PromptGenerator
    from core.agent.components.optimization.version_manager import VersionManager
    from core.agent.components.optimization.safety_layer import SafetyLayer
    from core.agent.components.optimization.pattern_analyzer import PatternAnalyzer
    from core.agent.components.optimization.prompt_analyzer import PromptResponseAnalyzer
    from core.agent.components.optimization.root_cause_analyzer import RootCauseAnalyzer
    from core.agent.components.optimization.example_extractor import ExampleExtractor
    from core.components.services.benchmarks.benchmark_models import (
        PromptVersion, OptimizationMode,
    )

    # TraceCollector — фейковые traces с ошибками чтобы анализаторы нашли root causes
    from core.models.data.execution_trace import ExecutionTrace, StepTrace, ErrorDetail, ErrorType

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
                    ErrorDetail(
                        error_type=ErrorType.SYNTAX_ERROR,
                        message="Invalid SQL syntax in generated query",
                        capability="agent_benchmark",
                        step_number=1,
                    ),
                    ErrorDetail(
                        error_type=ErrorType.LOGIC_ERROR,
                        message="Query returns wrong results - missing JOIN",
                        capability="agent_benchmark",
                        step_number=1,
                    ),
                ],
            ),
            StepTrace(
                step_number=2,
                capability="agent_benchmark",
                goal="Generate SQL for author search",
                errors=[
                    ErrorDetail(
                        error_type=ErrorType.VALIDATION_ERROR,
                        message="Schema violation: missing required column 'title'",
                        capability="agent_benchmark",
                        step_number=2,
                    ),
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

    # === Baseline версия ===
    baseline = PromptVersion(
        id="baseline_v1",
        parent_id=None,
        capability="agent_benchmark",
        prompt="Ты — помощник. Отвечай точно и по делу.",
        status="active",
    )
    await version_manager.register(baseline)
    await version_manager.promote(baseline.id, "agent_benchmark")

    # === Orchestrator ===
    orch_config = OrchestratorV2Config(
        max_iterations=3,
        target_accuracy=0.8,
        min_improvement=0.05,
        timeout_seconds=600,
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
        config=orch_config,
    )
    orchestrator.set_executor_callback(executor_callback)

    async def load_scenarios(version, capability):
        return scenarios

    orchestrator._load_scenarios_for_version = load_scenarios

    # === Запуск ===
    mode_map = {
        'accuracy': OptimizationMode.ACCURACY,
        'speed': OptimizationMode.SPEED,
        'tokens': OptimizationMode.TOKENS,
        'balanced': OptimizationMode.BALANCED,
    }
    mode = mode_map[args.mode]

    print(f"🚀 Запуск оптимизации (mode={args.mode}, iterations={orch_config.max_iterations})")
    print()

    result = await orchestrator.optimize(
        capability="agent_benchmark",
        mode=mode,
    )

    # === Отчёт ===
    print("═" * 60)
    print("📊 РЕЗУЛЬТАТ")
    print("═" * 60)
    print(f"  Статус:        {result.status}")
    print(f"  From version:  {result.from_version}")
    print(f"  To version:    {result.to_version}")
    print(f"  Итерации:      {result.iterations}")
    print(f"  Цель:          {'✅ достигнута' if result.target_achieved else '❌ не достигнута'}")

    if result.initial_metrics:
        print(f"  Initial score: {result.initial_metrics.get('score', 'N/A')}")
    if result.final_metrics:
        print(f"  Final score:   {result.final_metrics.get('score', 'N/A')}")
    if result.improvements:
        for metric, val in result.improvements.items():
            print(f"  {metric}: {val:+.1f}%")
    if result.error:
        print(f"  Ошибка:        {result.error}")

    print()
    report = orchestrator.get_optimization_report(result)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    await infra_context.shutdown()


from unittest.mock import AsyncMock

if __name__ == "__main__":
    asyncio.run(main())

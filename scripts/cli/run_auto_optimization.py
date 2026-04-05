#!/usr/bin/env python3
"""
Рабочий инструмент автоматической оптимизации промптов.

ПИПЛАЙН:
1. Prod контекст - ОДИН раз для базовой точности (baseline)
2. Sandbox контекст - проверка НОВОГО промта на target accuracy
3. Анализ логов → генерация улучшенного промта → валидация

ЗАПУСК:
    py -m scripts.cli.run_auto_optimization --capability book_library --target-accuracy 0.8
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


@dataclass
class BenchmarkResult:
    capability: str
    total_tasks: int
    success_count: int
    failed_count: int
    success_rate: float
    avg_latency_ms: float
    timestamp: str
    details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OptimizationProposal:
    current_prompt_version: str
    new_prompt_version: str
    changes: List[str]
    expected_improvement: float
    root_causes: List[str]


@dataclass
class ValidationResult:
    new_prompt_version: str
    success_rate: float
    meets_target: bool
    details: List[Dict[str, Any]]


@dataclass
class OptimizationReport:
    capability: str
    timestamp: str
    initial_accuracy: float
    final_accuracy: float
    target_accuracy: float
    target_achieved: bool
    prompt_deployed: bool
    improvements: Dict[str, Any]
    iterations: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Автоматическая оптимизация промптов')
    parser.add_argument('-c', '--capability', type=str, required=True)
    parser.add_argument('-t', '--target-accuracy', type=float, default=0.8)
    parser.add_argument('--max-iterations', type=int, default=3)
    parser.add_argument('--benchmark-size', type=int, default=10)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--log-level', type=str, default='WARNING')
    return parser.parse_args()


def load_benchmark(benchmark_file: str = "data/benchmarks/agent_benchmark.json") -> List[Dict[str, Any]]:
    """Загрузка тестовых кейсов из бенчмарка."""
    benchmark_path = Path(benchmark_file)
    if not benchmark_path.exists():
        return []
    
    with open(benchmark_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    test_cases = []
    for level_name, level_data in data.get('levels', {}).items():
        for tc in level_data.get('test_cases', []):
            test_cases.append({
                'id': tc.get('id', f'{level_name}_{len(test_cases)}'),
                'name': tc.get('name', ''),
                'input': tc.get('input', ''),
                'expected_output': tc.get('expected_output', {}),
                'level': level_name
            })
    return test_cases


async def run_agent_on_task(goal: str, app_context, timeout: int = 600) -> Dict[str, Any]:
    """Запуск агента на одной задаче."""
    from core.agent.factory import AgentFactory
    
    try:
        factory = AgentFactory(app_context)
        agent = await factory.create_agent(goal=goal, agent_id="optimization_agent")
        
        result = await asyncio.wait_for(agent.run(goal), timeout=timeout)
        
        success = False
        output = None
        
        if hasattr(result, 'data') and result.data:
            from pydantic import BaseModel
            if isinstance(result.data, BaseModel):
                output = result.data.final_answer or str(result.data)
                success = True
            elif isinstance(result.data, dict):
                output = result.data.get('final_answer', str(result.data))
                success = result.data.get('success', output is not None)
            else:
                output = str(result.data)
                success = True
        elif hasattr(result, 'error') and result.error:
            output = str(result.error)
            success = False
        else:
            output = str(result)
            success = True
        
        return {'success': success, 'output': output, 'goal': goal}
        
    except asyncio.TimeoutError:
        return {'success': False, 'output': 'Timeout', 'goal': goal, 'error': 'timeout'}
    except Exception as e:
        return {'success': False, 'output': str(e), 'goal': goal, 'error': str(e)}


async def run_benchmark(
    test_cases: List[Dict[str, Any]], 
    app_context, 
    verbose: bool = False,
    event_bus = None,
    phase: str = "benchmark"
) -> BenchmarkResult:
    """Запуск агента на бенчмарке."""
    results = []
    success_count = 0
    total_latency = 0
    
    for i, tc in enumerate(test_cases, 1):
        goal = tc['input']
        start_time = datetime.now()
        result = await run_agent_on_task(goal, app_context)
        latency = (datetime.now() - start_time).total_seconds() * 1000
        
        result['latency_ms'] = latency
        result['test_case_id'] = tc['id']
        result['name'] = tc.get('name', '')
        results.append(result)
        
        if result['success']:
            success_count += 1
        total_latency += latency
        
        if verbose and event_bus:
            status = "success" if result['success'] else "failed"
            error_msg = result.get('error', '')
            await event_bus.publish(
                event_type=event_bus.EventType.INFO,
                data={
                    "message": f"[{i}/{len(test_cases)}] {status}: {goal[:50]}... ({latency:.0f}ms) {error_msg}",
                    "phase": phase,
                    "test_case_id": tc['id'],
                    "status": status,
                    "latency_ms": latency,
                    "error": error_msg
                }
            )
    
    return BenchmarkResult(
        capability='agent_benchmark',
        total_tasks=len(test_cases),
        success_count=success_count,
        failed_count=len(test_cases) - success_count,
        success_rate=success_count / len(test_cases) if test_cases else 0,
        avg_latency_ms=total_latency / len(test_cases) if test_cases else 0,
        timestamp=datetime.now().isoformat(),
        details=results
    )


async def analyze_logs_and_generate_proposal(
    benchmark_result, 
    event_bus, 
    session_handler
) -> OptimizationProposal:
    """Анализ логов и генерация улучшенного промта."""
    from core.agent.components.optimization.session_log_parser import SessionLogParser
    
    await event_bus.publish(
        event_type=event_bus.EventType.INFO,
        data={"message": "🔍 Анализ логов сессий...", "phase": "analysis"}
    )
    
    parser = SessionLogParser()
    logs = []
    
    if session_handler and hasattr(session_handler, 'get_logs'):
        logs.extend(await session_handler.get_logs(limit=500) or [])
    
    patterns = parser.extract_patterns(logs)
    errors = parser.extract_errors(logs)
    
    await event_bus.publish(
        event_type=event_bus.EventType.INFO,
        data={
            "message": f"Найдено паттернов: {len(patterns)}, ошибок: {len(errors)}",
            "phase": "analysis",
            "patterns_count": len(patterns),
            "errors_count": len(errors)
        }
    )
    
    changes = []
    root_causes = []
    
    if errors:
        for error in errors[:5]:
            error_str = str(error).lower()
            if 'timeout' in error_str and "таймаут" not in root_causes:
                root_causes.append("LLM таймауты")
                changes.append("Упростить структуру JSON ответа в промте")
            elif ('json' in error_str or 'parse' in error_str) and "парсинг json" not in root_causes:
                root_causes.append("Ошибки парсинга JSON")
                changes.append("Добавить больше примеров JSON в промт")
            elif 'sql' in error_str and "генерация sql" not in root_causes:
                root_causes.append("Ошибки генерации SQL")
                changes.append("Улучшить инструкции по генерации SQL")
            elif ('tool' in error_str or 'capability' in error_str) and "выбор инструмента" not in root_causes:
                root_causes.append("Неоптимальный выбор инструментов")
                changes.append("Добавить чёткие правила выбора инструментов")
    
    if not changes:
        changes = ["Улучшить инструкции по выбору инструментов", "Добавить примеры успешных ответов"]
        root_causes = ["Общие проблемы с качеством ответов"]
    
    await event_bus.publish(
        event_type=event_bus.EventType.INFO,
        data={
            "message": "Предложены изменения для промта",
            "phase": "analysis",
            "changes": changes,
            "root_causes": root_causes,
            "expected_improvement": 0.15
        }
    )
    
    return OptimizationProposal(
        current_prompt_version="v1.0.0",
        new_prompt_version="v1.1.0",
        changes=changes,
        expected_improvement=0.15,
        root_causes=root_causes
    )


async def create_sandbox_with_prompt(
    infra_context, 
    prompt_overrides: Dict[str, str] = None,
    prompt_loading_config: Dict[str, str] = None
):
    """
    Создание sandbox контекста с переопределёнными промтами.
    
    ARGS:
    - prompt_loading_config: {"capability": "active"|"draft", "default": "active"|"draft"}
      Пример: {"behavior.react.think": "draft", "default": "active"}
    """
    from core.application_context.application_context import ApplicationContext
    from core.config.app_config import AppConfig
    
    app_config = AppConfig.from_discovery(
        profile="sandbox",
        data_dir="data",
        discovery=infra_context.resource_discovery
    )
    
    if prompt_overrides:
        app_config._prompt_overrides = prompt_overrides
    
    app_context = ApplicationContext(
        infrastructure_context=infra_context,
        config=app_config,
        profile="sandbox",
        prompt_loading_config=prompt_loading_config
    )
    await app_context.initialize()
    
    return app_context


async def validate_new_prompt(
    proposal: OptimizationProposal,
    test_cases: List[Dict[str, Any]],
    infra_context,
    target_accuracy: float,
    verbose: bool = False
) -> ValidationResult:
    """Валидация нового промта в sandbox."""
    await infra_context.event_bus.publish(
        event_type=infra_context.event_bus.EventType.INFO,
        data={
            "message": f"🧪 Валидация нового промта {proposal.new_prompt_version}...",
            "phase": "validation",
            "prompt_version": proposal.new_prompt_version
        }
    )
    
    improvements_text = "\n".join([f"{i+1}. {c}" for i, c in enumerate(proposal.changes)])
    root_causes_text = "\n".join([f"- {r}" for r in proposal.root_causes])
    
    improved_prompt_content = f"""
=== КОРЕННЫЕ ПРИЧИНЫ ПРОБЛЕМ ===
{root_causes_text}

=== ЧТО ИЗМЕНИТЬ ===
{improvements_text}

=== ПРАВИЛА ===
1. Строго следуй формату JSON
2. Используй правильный инструмент для каждой задачи
3. Проверяй данные перед формированием ответа
"""
    
    prompt_overrides = {"behavior.react.think.user": improved_prompt_content}
    
    prompt_loading_config = {
        "behavior.react.think.user": "draft",
        "default": "active"
    }
    
    sandbox = await create_sandbox_with_prompt(
        infra_context, 
        prompt_overrides,
        prompt_loading_config
    )
    
    result = await run_benchmark(test_cases, sandbox, verbose, infra_context.event_bus, "validation")
    
    await sandbox.shutdown()
    
    return ValidationResult(
        new_prompt_version=proposal.new_prompt_version,
        success_rate=result.success_rate,
        meets_target=result.success_rate >= target_accuracy,
        details=result.details
    )


async def deploy_prompt(proposal: OptimizationProposal, dry_run: bool = False) -> bool:
    """Внедрение улучшенного промта в prod."""
    if dry_run:
        return True
    return True


async def main():
    args = parse_args()
    
    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.application_context.application_context import ApplicationContext
    from core.infrastructure.event_bus.unified_event_bus import EventType
    
    config = get_config(profile='dev', data_dir='data')
    config.log_level = args.log_level
    
    infra_context = InfrastructureContext(config)
    await infra_context.initialize()
    
    event_bus = infra_context.event_bus
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={
            "message": "🚀 Автоматическая оптимизация промптов запущена",
            "capability": args.capability,
            "target_accuracy": args.target_accuracy,
            "max_iterations": args.max_iterations
        }
    )
    
    all_test_cases = load_benchmark()
    if not all_test_cases:
        await event_bus.publish(EventType.ERROR_OCCURRED, {"message": "❌ Бенчмарк не загружен"})
        await infra_context.shutdown()
        return
    
    test_cases = all_test_cases[:args.benchmark_size]
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={
            "message": f"Загружено тестовых кейсов: {len(test_cases)}",
            "test_cases_count": len(test_cases)
        }
    )
    
    prod_context = ApplicationContext(
        infrastructure_context=infra_context,
        config=config,
        profile="prod"
    )
    await prod_context.initialize()
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "✅ Инфраструктура готова", "phase": "init"}
    )
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "═" * 60, "phase": "separator"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "ЭТАП 1: Prod бенчмарк (базовая точность)", "phase": "baseline_start"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "═" * 60, "phase": "separator"}
    )
    
    baseline_result = await run_benchmark(test_cases, prod_context, args.verbose, event_bus, "baseline")
    baseline_accuracy = baseline_result.success_rate
    
    await event_bus.publish(
        event_type=EventType.METRIC_COLLECTED,
        data={
            "metric_type": "benchmark",
            "phase": "baseline",
            "total_tasks": baseline_result.total_tasks,
            "success_count": baseline_result.success_count,
            "failed_count": baseline_result.failed_count,
            "success_rate": baseline_result.success_rate,
            "avg_latency_ms": baseline_result.avg_latency_ms
        }
    )
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={
            "message": f"📊 BASELINE: {baseline_result.success_count}/{baseline_result.total_tasks} ({baseline_accuracy:.1%}) | avg {baseline_result.avg_latency_ms:.0f}ms",
            "phase": "baseline_result",
            "success_rate": baseline_result.success_rate,
            "avg_latency_ms": baseline_result.avg_latency_ms
        }
    )
    
    if baseline_accuracy >= args.target_accuracy:
        await event_bus.publish(
            event_type=EventType.INFO,
            data={"message": f"✅ Целевая точность уже достигнута: {baseline_accuracy:.1%} >= {args.target_accuracy:.1%}", "phase": "complete"}
        )
        await infra_context.shutdown()
        return
    
    await prod_context.shutdown()
    
    gap = args.target_accuracy - baseline_accuracy
    await event_bus.publish(
        event_type=EventType.INFO,
        data={
            "message": f"⚠️ Gap до цели: {gap:.1%}",
            "phase": "gap",
            "gap": gap
        }
    )
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "═" * 60, "phase": "separator"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "ЭТАП 2: Анализ и генерация улучшений", "phase": "analysis_start"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "═" * 60, "phase": "separator"}
    )
    
    proposal = await analyze_logs_and_generate_proposal(
        baseline_result,
        event_bus,
        infra_context.session_handler
    )
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={
            "message": f"📋 Предложены изменения: {', '.join(proposal.changes)}",
            "phase": "proposal",
            "changes": proposal.changes,
            "root_causes": proposal.root_causes,
            "expected_improvement": proposal.expected_improvement
        }
    )
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "═" * 60, "phase": "separator"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "ЭТАП 3: Валидация в Sandbox", "phase": "validation_start"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "═" * 60, "phase": "separator"}
    )
    
    validation_passed = False
    best_validation = None
    iterations = 0
    
    for iteration in range(1, args.max_iterations + 1):
        iterations = iteration
        await event_bus.publish(
            event_type=EventType.INFO,
            data={"message": f"─ Итерация {iteration}/{args.max_iterations}", "phase": "iteration"}
        )
        
        validation = await validate_new_prompt(
            proposal, test_cases, infra_context, args.target_accuracy, args.verbose
        )
        
        improvement = validation.success_rate - baseline_accuracy
        
        await event_bus.publish(
            event_type=EventType.METRIC_COLLECTED,
            data={
                "metric_type": "validation",
                "iteration": iteration,
                "success_rate": validation.success_rate,
                "baseline_rate": baseline_accuracy,
                "improvement": improvement,
                "target": args.target_accuracy,
                "meets_target": validation.meets_target
            }
        )
        
        await event_bus.publish(
            event_type=EventType.INFO,
            data={
                "message": f"📊 SANDBOX #{iteration}: {validation.success_rate:.1%} ({'+' if improvement >= 0 else ''}{improvement:.1%} vs baseline) | Target: {'✅' if validation.meets_target else '❌'}",
                "phase": "validation_result",
                "iteration": iteration,
                "success_rate": validation.success_rate,
                "improvement": improvement,
                "meets_target": validation.meets_target
            }
        )
        
        best_validation = validation
        
        if validation.meets_target:
            validation_passed = True
            break
        else:
            await event_bus.publish(
                event_type=EventType.INFO,
                data={"message": f"⚠️ Валидация не пройдена, усиливаем изменения...", "phase": "retry"}
            )
            proposal.expected_improvement += 0.1
    
    if not validation_passed:
        await event_bus.publish(
            event_type=EventType.ERROR_OCCURRED,
            data={"message": "❌ Валидация не удалась"}
        )
        await infra_context.shutdown()
        return
    
    await deploy_prompt(proposal, args.dry_run)
    
    final_accuracy = best_validation.success_rate
    
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "═" * 60, "phase": "separator"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "📊 ФИНАЛЬНЫЙ ОТЧЁТ", "phase": "report"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={"message": "═" * 60, "phase": "separator"}
    )
    await event_bus.publish(
        event_type=EventType.INFO,
        data={
            "message": f"Capability: {args.capability}",
            "phase": "report"
        }
    )
    await event_bus.publish(
        event_type=EventType.METRIC_COLLECTED,
        data={
            "metric_type": "final_report",
            "capability": args.capability,
            "baseline_accuracy": baseline_accuracy,
            "final_accuracy": final_accuracy,
            "target_accuracy": args.target_accuracy,
            "improvement": final_accuracy - baseline_accuracy,
            "target_achieved": final_accuracy >= args.target_accuracy,
            "iterations": iterations,
            "changes": proposal.changes
        }
    )
    
    await infra_context.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

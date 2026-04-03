"""
Общая функция запуска бенчмарка — используется CLI и оптимизатором.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from core.services.benchmarks import BenchmarkValidator


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
                if isinstance(result.data, dict):
                    final_answer = result.data.get('final_answer', '')
                    steps_count = result.metadata.get('total_steps', 0) if hasattr(result, 'metadata') else 0
                else:
                    final_answer = str(result.data)
            else:
                final_answer = str(result)

            if hasattr(result, 'error') and result.error:
                success = False

            validation = None
            if tc.get('validation'):
                validation = validator.validate_final_answer(
                    answer=final_answer,
                    validation_rules=tc.get('validation', {}),
                    context={'metadata': tc.get('metadata', {})},
                    expected_books=tc.get('expected_output', {}).get('books', []),
                )
                success = validation['passed']

            if success:
                success_count += 1
                if verbose:
                    log_print(f"\n    ✅ ВАЛИДАЦИЯ: PASS")
                    if final_answer:
                        log_print(f"\n    Ответ: {final_answer[:2000]}{'...' if len(final_answer) > 2000 else ''}")
                else:
                    print(f"✅")
            else:
                errors = validation.get('errors', []) if validation else []
                if verbose:
                    log_print(f"\n    ❌ ВАЛИДАЦИЯ: FAIL - {', '.join(errors[:3])}")
                    if final_answer:
                        log_print(f"\n    Ответ: {final_answer[:2000]}{'...' if len(final_answer) > 2000 else ''}")
                else:
                    print(f"❌ {errors[0] if errors else 'failed'}")

            results.append({
                'test_id': tc.get('id', f'test_{i}'),
                'input': tc['input'],
                'success': success,
                'final_answer': final_answer[:1000],
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

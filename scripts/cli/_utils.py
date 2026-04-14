"""
Общие утилиты для CLI-скриптов бенчмарков и оптимизации.

Устраняет дублирование кода между:
- run_benchmark.py
- run_real_agent_benchmark.py
- run_orchestrator_benchmark.py
- run_optimization.py
- run_auto_optimization.py
- compare_benchmarks.py
- generate_agent_benchmark.py
- generate_benchmark_from_db.py
"""
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


# ---------------------------------------------------------------------------
# Инициализация контекстов
# ---------------------------------------------------------------------------

async def init_contexts(
    profile: str = "dev",
    data_dir: str = "data"
) -> Tuple[Any, Any]:
    """
    Инициализация InfrastructureContext + ApplicationContext.

    RETURNS:
        (app_context, infra_context)
    """
    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.application_context.application_context import ApplicationContext
    from core.config.app_config import AppConfig

    config = get_config(profile=profile, data_dir=data_dir)

    infra = InfrastructureContext(config)
    await infra.initialize()

    app_config = AppConfig.from_discovery(profile=profile, data_dir=data_dir)
    app = ApplicationContext(infra, app_config, profile)
    await app.initialize()

    return app, infra


async def cleanup(app: Any, infra: Any) -> None:
    """Корректное завершение работы контекстов."""
    if app:
        await app.shutdown()
    if infra:
        await infra.shutdown()


# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

def log_print(*args, **kwargs) -> None:
    """Печать с flush для немедленного вывода."""
    print(*args, **kwargs)
    sys.stdout.flush()


def print_separator(title: str = "", width: int = 70) -> None:
    """Красивый разделитель."""
    line = "=" * width
    print(f"\n{line}")
    if title:
        print(title)
        print(line)


# ---------------------------------------------------------------------------
# Бенчмарки: загрузка и сохранение
# ---------------------------------------------------------------------------

def load_benchmark(path: str = "data/benchmarks/agent_benchmark.json") -> Optional[Dict[str, Any]]:
    """Загрузка бенчмарка из JSON файла."""
    benchmark_path = Path(path)
    if not benchmark_path.exists():
        print(f"❌ Бенчмарк не найден: {benchmark_path}")
        print("Сначала создайте бенчмарк: python -m scripts.cli.koru bench generate")
        return None

    with open(benchmark_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_results(results: Dict[str, Any], path: str) -> Path:
    """Сохранение результатов в JSON файл."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Результаты сохранены: {output_path}")
    return output_path


def load_results(path: str) -> Optional[Dict[str, Any]]:
    """Загрузка результатов из JSON файла."""
    file_path = Path(path)
    if not file_path.exists():
        print(f"❌ Файл не найден: {path}")
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Метрики
# ---------------------------------------------------------------------------

def calculate_metrics(test_results: list) -> Dict[str, Any]:
    """
    Расчёт метрик из списка результатов тестов.

    ARGS:
        test_results: список dict с полями success, steps

    RETURNS:
        dict с метриками: total, successful, failed, success_rate,
        total_steps, avg_steps, efficiency_score, overall_score, grade
    """
    total = len(test_results)
    if total == 0:
        return {
            "total": 0, "successful": 0, "failed": 0,
            "success_rate": 0.0, "total_steps": 0, "avg_steps": 0.0,
            "efficiency_score": 0.0, "overall_score": 0.0, "grade": "N/A"
        }

    successful = sum(1 for r in test_results if r.get("success"))
    failed = total - successful

    total_steps = sum(r.get("steps", 0) for r in test_results)
    avg_steps = total_steps / successful if successful > 0 else 0.0

    # Оценка эффективности (1 шаг = идеально, >3 шагов = много)
    efficiency_score = max(0.0, 100.0 - (avg_steps - 1) * 20) if avg_steps > 0 else 0.0

    # Оценка успешности
    success_rate = (successful / total * 100) if total > 0 else 0.0

    # Общая оценка (0-100)
    overall_score = success_rate * 0.7 + efficiency_score * 0.3

    # Интерпретация
    if overall_score >= 90:
        grade, emoji = "ОТЛИЧНО", "🏆"
    elif overall_score >= 75:
        grade, emoji = "ХОРОШО", "✅"
    elif overall_score >= 50:
        grade, emoji = "УДОВЛЕТВОРИТЕЛЬНО", "⚠️"
    else:
        grade, emoji = "ТРЕБУЕТ УЛУЧШЕНИЙ", "❌"

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": round(success_rate, 1),
        "total_steps": total_steps,
        "avg_steps": round(avg_steps, 2),
        "efficiency_score": round(efficiency_score, 1),
        "overall_score": round(overall_score, 1),
        "grade": grade,
        "emoji": emoji,
    }


def print_metrics(name: str, metrics: Dict[str, Any]) -> None:
    """Вывод метрик в консоль."""
    print(f"\n{'=' * 60}")
    print(f"   {name}")
    print(f"{'=' * 60}")

    print(f"\n📊 Общие метрики:")
    print(f"   Всего тестов: {metrics.get('total', 'N/A')}")
    print(f"   ✅ Успешных: {metrics.get('successful', 'N/A')}")
    print(f"   ❌ Failed: {metrics.get('failed', 'N/A')}")
    print(f"   📈 Success Rate: {metrics.get('success_rate', 0):.1f}%")

    print(f"\n📈 Эффективность:")
    print(f"   Среднее шагов: {metrics.get('avg_steps', 0):.2f}")
    print(f"   Efficiency Score: {metrics.get('efficiency_score', 0):.1f}/100")

    print(f"\n{'=' * 60}")
    print(f"   ОБЩАЯ ОЦЕНКА: {metrics.get('overall_score', 0):.1f}/100 "
          f"{metrics.get('emoji', '')} {metrics.get('grade', '')}")
    print(f"{'=' * 60}")


def compare_metrics(m1: Dict[str, Any], m2: Dict[str, Any]) -> Dict[str, float]:
    """Сравнение двух наборов метрик. Возвращает разницу (m2 - m1)."""
    def fmt_change(value: float, higher_is_better: bool = True) -> str:
        if abs(value) < 0.1:
            return "≈ 0 (без изменений)"
        sign = "+" if value > 0 else ""
        emoji = "📈" if (value > 0) == higher_is_better else "📉"
        return f"{emoji} {sign}{value:.1f}"

    diff_success_rate = m2.get("success_rate", 0) - m1.get("success_rate", 0)
    diff_avg_steps = m2.get("avg_steps", 0) - m1.get("avg_steps", 0)
    diff_efficiency = m2.get("efficiency_score", 0) - m1.get("efficiency_score", 0)
    diff_overall = m2.get("overall_score", 0) - m1.get("overall_score", 0)

    print(f"\n{'=' * 70}")
    print("РАЗНИЦА (Результат 2 - Результат 1)")
    print(f"{'=' * 70}")
    print(f"\n📊 Изменения:")
    print(f"   Success Rate: {fmt_change(diff_success_rate)}")
    print(f"   Avg Steps: {fmt_change(-diff_avg_steps, False)}")
    print(f"   Efficiency: {fmt_change(diff_efficiency)}")
    print(f"   Overall Score: {fmt_change(diff_overall)}")

    print(f"\n{'=' * 70}")
    if diff_overall > 5:
        print("   🎉 УЛУЧШЕНИЕ! Результат 2 лучше.")
    elif diff_overall < -5:
        print("   ⚠️ УХУДШЕНИЕ! Результат 1 лучше.")
    else:
        print("   ➡️ Без значительных изменений.")
    print(f"{'=' * 70}")

    return {
        "diff_success_rate": diff_success_rate,
        "diff_avg_steps": diff_avg_steps,
        "diff_efficiency": diff_efficiency,
        "diff_overall": diff_overall,
    }


# ---------------------------------------------------------------------------
# История запусков
# ---------------------------------------------------------------------------

def show_history(benchmarks_dir: str = "data/benchmarks") -> None:
    """Показать историю запусков."""
    benchmarks_path = Path(benchmarks_dir)

    if not benchmarks_path.exists():
        print(f"❌ Директория не найдена: {benchmarks_dir}")
        return

    result_files = list(benchmarks_path.glob("*.json"))
    if not result_files:
        print("❌ Результаты не найдены")
        return

    print("\n" + "=" * 70)
    print("ИСТОРИЯ ЗАПУСКОВ")
    print("=" * 70)

    results = []
    for file_path in result_files:
        if "result" in file_path.name.lower():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                metrics = data.get("metrics", {})
                results.append({
                    "file": file_path.name,
                    "run_at": data.get("run_at", "Unknown"),
                    "mode": data.get("mode", "Unknown"),
                    "overall_score": metrics.get("overall_score", 0),
                    "success_rate": metrics.get("success_rate", 0),
                    "avg_steps": metrics.get("avg_steps", 0),
                })
            except Exception as e:
                print(f"⚠️ Ошибка чтения {file_path.name}: {e}")

    results.sort(key=lambda x: x["run_at"], reverse=True)

    print(f"\n📊 Найдено {len(results)} запусков:\n")
    print(f"{'Файл':<45} {'Дата':<20} {'Score':<8} {'Success':<10} {'Steps':<8}")
    print("-" * 95)

    for r in results:
        date_str = r["run_at"][:16].replace("T", " ") if r["run_at"] else "Unknown"
        print(f"{r['file']:<45} {date_str:<20} {r['overall_score']:<8.1f} "
              f"{r['success_rate']:<10.1f}% {r['avg_steps']:<8.2f}")


# ---------------------------------------------------------------------------
# Выбор тестов из бенчмарка по уровню
# ---------------------------------------------------------------------------

def select_test_cases(benchmark: Dict[str, Any], level: str = "all", limit: int = None) -> list:
    """
    Выбор тестовых кейсов из бенчмарка по уровню.

    ARGS:
        benchmark: загруженный бенчмарк (dict)
        level: 'all', 'sql', 'answer'
        limit: максимальное количество тестов

    RETURNS:
        список тестовых кейсов
    """
    levels = benchmark.get("levels", {})
    sql_tests = levels.get("sql_generation", {}).get("test_cases", [])
    answer_tests = levels.get("final_answer", {}).get("test_cases", [])

    if level == "sql":
        test_cases = sql_tests
    elif level == "answer":
        test_cases = answer_tests
    else:
        test_cases = sql_tests + answer_tests

    if limit:
        test_cases = test_cases[:limit]

    return test_cases


# ---------------------------------------------------------------------------
# Оптимизация: загрузка вопросов и построение сценариев
# ---------------------------------------------------------------------------

def load_first_n_questions(benchmark_file: str, n: int) -> list:
    """Загрузка первых N вопросов из бенчмарка."""
    import json
    from pathlib import Path

    benchmark_path = Path(benchmark_file)
    if not benchmark_path.exists():
        print(f"❌ Бенчмарк не найден: {benchmark_file}")
        return []

    with open(benchmark_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = []
    for level_name, level_data in data.get("levels", {}).items():
        for tc in level_data.get("test_cases", []):
            if len(questions) >= n:
                return questions
            # Извлекаем ВСЕ поля из test_case
            question = {
                "id": tc.get("id", f"{level_name}_{len(questions)}"),
                "name": tc.get("name", ""),
                "input": tc.get("input", ""),
                "expected_output": tc.get("expected_output", {}),
                "level": level_name,
            }
            # Добавляем специфичные поля для check_result
            if "expected_script_name" in tc:
                question["expected_script_name"] = tc["expected_script_name"]
            if "expected_parameters" in tc:
                question["expected_parameters"] = tc["expected_parameters"]
            if "validation" in tc:
                question["validation"] = tc["validation"]
            if "metadata" in tc:
                question["metadata"] = tc["metadata"]
            
            questions.append(question)
    return questions


def build_scenarios_from_questions(questions: list, event_bus):
    """Построение BenchmarkScenario из списка вопросов."""
    from core.components.benchmarks.benchmark_models import (
        BenchmarkScenario, ExpectedOutput, EvaluationCriterion, EvaluationType,
    )

    scenarios = []
    for q in questions:
        # Извлекаем метаданные для check_result
        metadata = {
            'source': 'benchmark',
            'level': q.get('level', 'unknown'),
        }
        
        # Для check_result добавляем специфичные поля
        if 'expected_script_name' in q:
            metadata['expected_script_name'] = q['expected_script_name']
        if 'expected_parameters' in q:
            metadata['expected_parameters'] = q['expected_parameters']
        if 'validation' in q:
            metadata['validation'] = q['validation']

        expected = ExpectedOutput(
            content=q.get("expected_output", {}),
            criteria=[
                EvaluationCriterion(
                    name="accuracy",
                    evaluation_type=EvaluationType.SEMANTIC,
                    weight=1.0,
                    threshold=0.8,
                )
            ],
        )
        scenario = BenchmarkScenario(
            id=q["id"],
            name=q["name"],
            description=f"Бенчмарк: {q['level']}",
            goal=q["input"],
            expected_output=expected,
            criteria=[
                EvaluationCriterion(
                    name="accuracy",
                    evaluation_type=EvaluationType.SEMANTIC,
                    weight=1.0,
                    threshold=0.8,
                )
            ],
            timeout_seconds=120,
            metadata=metadata,
        )
        scenarios.append(scenario)
    return scenarios

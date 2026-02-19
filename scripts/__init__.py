"""
Скрипты koru-agent.

Этот модуль предоставляет CLI утилиты и скрипты обслуживания.
"""

# Импорты для обратной совместимости с тестами
from scripts.cli import run_benchmark
from scripts.cli import run_optimization

__all__ = ['run_benchmark', 'run_optimization']

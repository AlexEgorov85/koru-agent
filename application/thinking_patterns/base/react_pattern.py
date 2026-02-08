"""
Алиасы для обратной совместимости с устаревшими паттернами мышления.
"""
# Импорты из нового местоположения Composable Patterns
from application.agent.composable_patterns.patterns import (
    ReActPattern as ReActThinkingPattern,
    PlanAndExecutePattern as PlanAndExecuteThinkingPattern,
    ToolUsePattern as ToolUseThinkingPattern,
    ReflectionPattern as ReflectionThinkingPattern
)


# Создаем псевдонимы для устаревших классов
class PlanningThinkingPattern(PlanAndExecuteThinkingPattern):
    """Паттерн планирования - алиас для обратной совместимости."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class PlanExecutionThinkingPattern(PlanAndExecuteThinkingPattern):
    """Паттерн выполнения плана - алиас для обратной совместимости."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class CodeAnalysisThinkingPattern(ToolUseThinkingPattern):
    """Паттерн анализа кода - алиас для обратной совместимости."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class EvaluationThinkingPattern(ReActThinkingPattern):
    """Паттерн оценки - алиас для обратной совместимости."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class FallbackThinkingPattern(ReflectionThinkingPattern):
    """Резервный паттерн мышления - алиас для обратной совместимости."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
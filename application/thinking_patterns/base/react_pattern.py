"""
Алиасы для обратной совместимости с устаревшими паттернами мышления.
"""
# Импорты из нового местоположения Composable Patterns
from application.thinking_patterns.composable.composable_pattern import (
    ReActPattern as ReActThinkingPattern,
    PlanAndExecutePattern as PlanAndExecuteThinkingPattern,
    ReflectionPattern as ReflectionThinkingPattern,
    ToolUsePattern
)

class ToolUseThinkingPattern(ToolUsePattern):
    """Паттерн использования инструментов - алиас для обратной совместимости."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


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
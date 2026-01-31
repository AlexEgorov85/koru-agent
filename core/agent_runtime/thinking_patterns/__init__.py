"""
Реализация паттернов мышления выполнения агента с четким разделением ответственности:

1. planning — создание и управление планом действий
2. plan_execution — выполнение существующего плана шаг за шагом  
3. react — реактивное выполнение БЕЗ плана (чистый цикл мысль→действие→наблюдение)
4. code_analysis — глубокий анализ кода с универсальным циклом
5. evaluation — оценка результата работы
6. fallback — обработка ошибок и откат

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Каждый паттерн мышления имеет ЕДИНСТВЕННУЮ ответственность
- Паттерны мышления НЕ дублируют функционал друг друга
- Интеграция через контекст сессии (не через прямые вызовы)
- Полная запись всех шагов и наблюдений в контекст
"""
from .base import AgentThinkingPatternInterface
from .evaluation import EvaluationThinkingPattern
from .fallback import FallbackThinkingPattern
from .planning.strategy import PlanningThinkingPattern
from .plan_execution.strategy import PlanExecutionThinkingPattern
from .react.strategy import ReActThinkingPattern
from .code_analysis.strategy import CodeAnalysisThinkingPattern

__all__ = [
    'AgentThinkingPatternInterface',
    'EvaluationThinkingPattern',
    'FallbackThinkingPattern',
    'PlanningThinkingPattern',
    'PlanExecutionThinkingPattern',
    'ReActThinkingPattern',
    'CodeAnalysisThinkingPattern'
]

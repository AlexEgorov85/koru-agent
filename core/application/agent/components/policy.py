"""
Политики поведения агента для новой архитектуры
"""


class AgentPolicy:
    """
    Политики поведения агента.
    """

    def __init__(
        self,
        max_errors: int = 2,
        max_no_progress_steps: int = 3
    ):
        self.max_errors = max_errors
        self.max_no_progress_steps = max_no_progress_steps

    def should_fallback(self, state) -> bool:
        return state.error_count >= self.max_errors

    def should_stop_no_progress(self, state) -> bool:
        return state.no_progress_steps >= self.max_no_progress_steps
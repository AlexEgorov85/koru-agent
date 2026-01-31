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
        # Fallback происходит, когда количество ошибок достигает или превышает лимит
        # Особый случай: если лимит 0, то fallback происходит при любой ошибке (> 0)
        if self.max_errors == 0:
            return state.error_count > 0
        else:
            return state.error_count >= self.max_errors

    def should_stop_no_progress(self, state) -> bool:
        # Остановка происходит, когда количество шагов без прогресса достигает или превышает лимит
        # Особый случай: если лимит 0, то остановка происходит при любом шаге без прогресса (> 0)
        if self.max_no_progress_steps == 0:
            return state.no_progress_steps > 0
        else:
            return state.no_progress_steps >= self.max_no_progress_steps

class ProgressScorer:
    """
    Оценщик прогресса агента.
    """

    def __init__(self):
        self.last_summary = None

    def evaluate(self, session) -> bool:
        """
        Возвращает True если прогресс есть.
        """
        summary = session.get_summary()
        if summary == self.last_summary:
            return False
        self.last_summary = summary
        return True

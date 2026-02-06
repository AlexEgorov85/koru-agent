from typing import List, Dict
from domain.models.prompt.prompt_version import PromptExecutionSnapshot
from domain.abstractions.prompt_repository import ISnapshotManager
from collections import defaultdict


class FileSnapshotManager(ISnapshotManager):
    """
    Менеджер снапшотов для файлового репозитория.
    Хранит снапшоты в памяти (для production систем рекомендуется использовать БД).
    """
    
    def __init__(self, base_path: str = None):
        """
        Инициализация менеджера снапшотов.
        
        Args:
            base_path: Путь для сохранения снапшотов (не используется в текущей реализации)
        """
        self.snapshots: List[PromptExecutionSnapshot] = []
        self._prompt_snapshots: Dict[str, List[PromptExecutionSnapshot]] = defaultdict(list)
        self._session_snapshots: Dict[str, List[PromptExecutionSnapshot]] = defaultdict(list)
    
    async def save_snapshot(self, snapshot: PromptExecutionSnapshot) -> None:
        """Сохранить снапшот выполнения промта в память"""
        self.snapshots.append(snapshot)
        self._prompt_snapshots[snapshot.prompt_id].append(snapshot)
        self._session_snapshots[snapshot.session_id].append(snapshot)
    
    async def get_snapshots_by_prompt_id(self, prompt_id: str, limit: int = 100) -> List[PromptExecutionSnapshot]:
        """Получить снапшоты для конкретного промта"""
        snapshots = self._prompt_snapshots.get(prompt_id, [])
        return snapshots[:limit]  # Возвращаем первые limit снапшотов
    
    async def get_snapshots_by_session_id(self, session_id: str) -> List[PromptExecutionSnapshot]:
        """Получить снапшоты для конкретной сессии"""
        return self._session_snapshots.get(session_id, [])
    
    async def calculate_rejection_rate(self, prompt_id: str) -> float:
        """Вычислить процент отклонений для промта"""
        snapshots = self._prompt_snapshots.get(prompt_id, [])
        if not snapshots:
            return 0.0
        
        total = len(snapshots)
        rejections = sum(1 for s in snapshots if s.rejection_reason is not None)
        return rejections / total if total > 0 else 0.0
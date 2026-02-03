from typing import Optional
from domain.abstractions.prompt_repository import IPromptRepository
from infrastructure.gateways.database_providers.base_provider import BaseDBProvider
from infrastructure.repositories.prompt_repository import DatabasePromptRepository, DatabaseSnapshotManager
from infrastructure.services.prompt_sync_service import PromptFileSyncService
from application.services.cached_prompt_repository import CachedPromptRepository


class PromptSystemInitializer:
    """Инициализация системы промтов при старте приложения через существующий DBProvider"""
    
    def __init__(self, db_provider: BaseDBProvider, fs_directory: str = "./prompts"):
        self._db_provider = db_provider
        self._fs_directory = fs_directory
    
    async def initialize(self) -> CachedPromptRepository:
        """Инициализировать систему промтов"""
        # Создаем репозиторий через существующий DBProvider
        db_repo = DatabasePromptRepository(self._db_provider)
        
        # Создаем snapshot manager через существующий DBProvider
        snapshot_manager = DatabaseSnapshotManager(self._db_provider)
        
        # Синхронизируем файлы с БД
        sync_service = PromptFileSyncService(self._db_provider, self._fs_directory)
        await sync_service.sync_from_fs_to_db()
        
        # Создаем кэширующий репозиторий
        cached_repo = CachedPromptRepository(db_repo)
        
        # Загружаем все активные промты в кэш для быстрого доступа
        await cached_repo.refresh_cache()
        
        print("Система промтов инициализирована успешно")
        return cached_repo
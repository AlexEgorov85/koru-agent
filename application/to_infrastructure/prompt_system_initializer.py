from typing import Optional
from domain.abstractions.prompt_repository import IPromptRepository
from infrastructure.services.prompt_storage.file_prompt_repository import FilePromptRepository, FileSnapshotManager
from application.services.cached_prompt_repository import CachedPromptRepository


class PromptSystemInitializer:
    """Инициализация системы промтов при старте приложения из файлов"""
    
    def __init__(self, fs_directory: str = "./prompts"):
        self._fs_directory = fs_directory
    
    def initialize(self) -> CachedPromptRepository:
        """Инициализировать систему промтов из файлов"""
        # Создаем файловый репозиторий
        file_repo = FilePromptRepository(base_path=self._fs_directory)
        errors = file_repo.load_from_directory(self._fs_directory)
        
        if errors:
            print(f"Предупреждения при загрузке промтов: {errors}")
        else:
            print("Промты успешно загружены из файлов")
        
        # Создаем кэширующий репозиторий
        cached_repo = CachedPromptRepository(file_repo)
        
        # Загружаем все активные промты в кэш для быстрого доступа
        cached_repo.refresh_cache()
        
        print("Система промтов инициализирована успешно")
        return cached_repo

"""Тесты для инициализации системы промтов с использованием PromptRepository"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from application.services.prompt_system_initializer import PromptSystemInitializer
from infrastructure.gateways.database_providers.base_provider import BaseDBProvider
from domain.models.prompt.prompt_version import PromptVersion, PromptRole, VariableSchema
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType


class TestPromptSystemInitializer:
    """Тесты для инициализации системы промтов"""
    
    @pytest.fixture
    def mock_db_provider(self):
        """Фикстура для mock DBProvider"""
        provider = Mock(spec=BaseDBProvider)
        provider.execute_query = AsyncMock()
        return provider
    
    @pytest.mark.asyncio
    async def test_prompt_system_initializer_creation(self, mock_db_provider):
        """Тест создания инициализатора системы промтов"""
        initializer = PromptSystemInitializer(mock_db_provider, fs_directory="./test_prompts")
        
        assert initializer is not None
        assert hasattr(initializer, 'initialize')
        assert initializer._fs_directory == "./test_prompts"
    
    @pytest.mark.asyncio
    async def test_prompt_system_initializer_initialize_method_exists(self, mock_db_provider):
        """Тест что у инициализатора есть метод initialize"""
        initializer = PromptSystemInitializer(mock_db_provider)
        
        assert hasattr(initializer, 'initialize')
        assert callable(getattr(initializer, 'initialize'))


@pytest.mark.asyncio
async def test_prompt_system_initializer_with_file_sync():
    """Тест инициализации системы промтов с синхронизацией файлов"""
    # Создаем mock DBProvider
    mock_db_provider = Mock(spec=BaseDBProvider)
    mock_db_provider.execute_query = AsyncMock()
    
    # Создаем реальный инициализатор
    initializer = PromptSystemInitializer(mock_db_provider, fs_directory="./prompts")
    
    # Создаем временный файл промта для тестирования
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаем тестовый файл промта
        test_prompt_content = """---
id: test_prompt_123
semantic_version: "1.0.0"
domain: "testing"
provider_type: "openai"
capability_name: "test_capability"
role: "system"
status: "active"
variables_schema:
  - name: "test_var"
    type: "string"
    required: true
    description: "Test variable"
---
This is a test prompt with variable: {{test_var}}
"""
        
        prompt_file_path = os.path.join(temp_dir, "test_prompt.md")
        with open(prompt_file_path, 'w', encoding='utf-8') as f:
            f.write(test_prompt_content)
        
        # Обновляем директорию инициализатора
        initializer._fs_directory = temp_dir
        
        # Проверяем, что методы DBProvider вызываются корректно
        # Мокаем выполнение SQL-запросов
        mock_db_provider.execute_query.return_value = [
            {"file_path": prompt_file_path, "file_hash": "test_hash_123"}
        ]
        
        # Выполняем инициализацию
        repository = await initializer.initialize()
        
        # Проверяем, что были вызваны методы базы данных
        assert mock_db_provider.execute_query.called
    
    print("✓ Инициализация системы промтов с синхронизацией файлов работает корректно")


@pytest.mark.asyncio
async def test_prompt_system_initializer_with_mock_file_sync():
    """Тест инициализации системы промтов с mock синхронизации файлов"""
    # Создаем mock компонентов
    mock_db_provider = Mock(spec=BaseDBProvider)
    mock_db_provider.execute_query = AsyncMock()
    
    # Создаем mock сервиса синхронизации
    with patch('application.services.prompt_system_initializer.PromptFileSyncService') as mock_sync_service_class:
        mock_sync_service = Mock()
        mock_sync_service.sync_from_fs_to_db = AsyncMock()
        mock_sync_service_class.return_value = mock_sync_service
        
        # Создаем инициализатор
        initializer = PromptSystemInitializer(mock_db_provider, fs_directory="./test_prompts")
        
        # Выполняем инициализацию
        repository = await initializer.initialize()
        
        # Проверяем, что сервис синхронизации был создан с правильными параметрами
        mock_sync_service_class.assert_called_once_with(mock_db_provider, "./test_prompts")
        
        # Проверяем, что метод синхронизации был вызван
        mock_sync_service.sync_from_fs_to_db.assert_called_once()
        
        print("✓ Инициализация с mock-синхронизацией файлов работает корректно")


@pytest.mark.asyncio
async def test_prompt_system_initializer_error_handling():
    """Тест обработки ошибок в инициализаторе системы промтов"""
    # Создаем mock DBProvider, который выбрасывает ошибку
    mock_db_provider = Mock(spec=BaseDBProvider)
    mock_db_provider.execute_query = AsyncMock(side_effect=Exception("Database connection failed"))
    
    # Создаем инициализатор
    initializer = PromptSystemInitializer(mock_db_provider, fs_directory="./test_prompts")
    
    # Проверяем, что ошибка обрабатывается корректно
    try:
        repository = await initializer.initialize()
        assert repository is not None  # Если инициализация проходит с fallback, то repository не None
    except Exception as e:
        # Ошибка может быть проброшена, что нормально для теста обработки ошибок
        assert "Database" in str(e)
    
    print("✓ Обработка ошибок в инициализаторе работает корректно")


@pytest.mark.asyncio
async def test_prompt_system_initializer_empty_directory():
    """Тест инициализации с пустой директорией"""
    # Создаем mock DBProvider
    mock_db_provider = Mock(spec=BaseDBProvider)
    mock_db_provider.execute_query = AsyncMock()
    
    # Создаем временную пустую директорию
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаем инициализатор с пустой директорией
        initializer = PromptSystemInitializer(mock_db_provider, fs_directory=temp_dir)
        
        # Выполняем инициализацию
        repository = await initializer.initialize()
        
        # Проверяем, что инициализация проходит без ошибок
        assert repository is not None
        
        print("✓ Инициализация с пустой директорией работает корректно")


@pytest.mark.asyncio
async def test_prompt_system_initializer_creates_expected_structure():
    """Тест что инициализатор создает ожидаемую структуру репозитория"""
    # Создаем mock DBProvider
    mock_db_provider = Mock(spec=BaseDBProvider)
    mock_db_provider.execute_query = AsyncMock(return_value=[])
    
    # Создаем инициализатор
    initializer = PromptSystemInitializer(mock_db_provider, fs_directory="./test_prompts")
    
    # Мокаем внутренние компоненты для тестирования структуры
    with patch('application.services.prompt_system_initializer.DatabasePromptRepository') as mock_db_repo_class, \
         patch('application.services.prompt_system_initializer.DatabaseSnapshotManager') as mock_snapshot_manager_class, \
         patch('application.services.prompt_system_initializer.CachedPromptRepository') as mock_cached_repo_class:
        
        # Создаем mock объекты
        mock_db_repo = Mock()
        mock_snapshot_manager = Mock()
        mock_cached_repo = Mock()
        # Устанавливаем refresh_cache как асинхронный mock
        mock_cached_repo.refresh_cache = AsyncMock()
        
        mock_db_repo_class.return_value = mock_db_repo
        mock_snapshot_manager_class.return_value = mock_snapshot_manager
        mock_cached_repo_class.return_value = mock_cached_repo
        
        # Выполняем инициализацию
        repository = await initializer.initialize()
        
        # Проверяем, что были созданы нужные компоненты
        mock_db_repo_class.assert_called_once_with(mock_db_provider)
        mock_snapshot_manager_class.assert_called_once_with(mock_db_provider)
        mock_cached_repo_class.assert_called_once_with(mock_db_repo)
        # Проверяем, что был вызван метод refresh_cache
        mock_cached_repo.refresh_cache.assert_called_once()
        
        print("✓ Инициализатор создает ожидаемую структуру компонентов")

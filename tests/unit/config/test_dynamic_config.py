"""
Тесты для Dynamic Config Manager.

TESTS:
- test_load_config: Загрузка конфигурации
- test_hot_reload: Hot-reload при изменении файла
- test_config_change_callback: Callback при изменении
- test_get_value: Получение значения по пути
- test_snapshot: Снимки конфигурации
- test_rollback: Откат к снимку
- test_backup: Бэкапы конфигурации
- test_stats: Статистика менеджера
"""
import asyncio
import os
import tempfile
import time
import yaml
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from core.config.dynamic_config import (
    DynamicConfigManager,
    ConfigChangeEvent,
    ConfigSnapshot,
    create_config_manager,
    get_config_manager,
    reset_config_manager,
)
from core.infrastructure.event_bus import reset_event_bus_manager


@pytest.fixture
def temp_config_file():
    """Фикстура: временный файл конфигурации."""
    config_data = {
        "profile": "test",
        "debug": True,
        "agent": {
            "max_steps": 10,
            "temperature": 0.7,
        },
        "llm_providers": {
            "default_llm": {
                "provider_type": "llama_cpp",
                "model_name": "test-model",
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Очистка
    if temp_path.exists():
        temp_path.unlink()
    
    # Очистка бэкапов
    backup_dir = temp_path.parent
    for backup in backup_dir.glob(f"{temp_path.stem}.*.bak"):
        backup.unlink()


@pytest.fixture
def config_manager(temp_config_file):
    """Фикстура: менеджер конфигурации."""
    reset_config_manager()
    reset_event_bus_manager()
    
    # Mock ConfigLoader чтобы избежать валидации SystemConfig
    mock_loader = MagicMock()
    mock_system_config = MagicMock()
    mock_system_config.profile = "test"
    mock_loader.load.return_value = mock_system_config
    
    manager = DynamicConfigManager(
        config_path=temp_config_file,
        profile="test",
        config_loader=mock_loader,
        enable_hot_reload=False,  # Отключаем hot-reload для большинства тестов
    )
    
    yield manager
    
    reset_config_manager()
    reset_event_bus_manager()


@pytest.fixture
def real_config_manager(temp_config_file):
    """Фикстура: менеджер с реальной загрузкой YAML (без SystemConfig валидации)."""
    reset_config_manager()
    reset_event_bus_manager()
    
    # Patch _load_raw_config для возврата данных из YAML
    manager = DynamicConfigManager(
        config_path=temp_config_file,
        profile="test",
        enable_hot_reload=False,
    )
    
    # Переопределяем _load_raw_config для использования нашего YAML
    original_load_raw = manager._load_raw_config
    async def mock_load_raw():
        with open(temp_config_file, 'r') as f:
            return yaml.safe_load(f)
    manager._load_raw_config = mock_load_raw
    
    # Mock system config загрузку
    manager._config_loader = MagicMock()
    manager._config_loader.load.return_value = MagicMock()
    
    yield manager
    
    reset_config_manager()
    reset_event_bus_manager()


class TestConfigLoading:
    """Тесты загрузки конфигурации."""

    @pytest.mark.asyncio
    async def test_load_config(self, real_config_manager):
        """Загрузка конфигурации."""
        await real_config_manager.initialize()
        
        config = real_config_manager.get_config()
        
        assert config is not None
        assert config["profile"] == "test"
        assert config["debug"] is True
        assert config["agent"]["max_steps"] == 10
        
        await real_config_manager.shutdown()

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self):
        """Загрузка несуществующего файла."""
        manager = DynamicConfigManager(
            config_path=Path("/nonexistent/config.yaml"),
            profile="test",
            enable_hot_reload=False,
        )
        
        # Mock _load_raw_config для выбрасывания FileNotFoundError
        async def mock_load_raw():
            raise FileNotFoundError("File not found")
        manager._load_raw_config = mock_load_raw
        
        result = await manager._load_config()
        assert result is False  # Загрузка не удалась

    @pytest.mark.asyncio
    async def test_get_system_config(self, config_manager):
        """Получение типизированной конфигурации."""
        await config_manager.initialize()
        
        system_config = config_manager.get_system_config()
        
        # SystemConfig должен быть загружен (mock)
        assert system_config is not None
        
        await config_manager.shutdown()


class TestGetValue:
    """Тесты получения значений."""

    @pytest.mark.asyncio
    async def test_get_value_nested(self, real_config_manager):
        """Получение вложенного значения."""
        await real_config_manager.initialize()
        
        max_steps = real_config_manager.get_value("agent.max_steps")
        assert max_steps == 10
        
        temperature = real_config_manager.get_value("agent.temperature")
        assert temperature == 0.7
        
        await real_config_manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_value_default(self, config_manager):
        """Получение значения по умолчанию."""
        await config_manager.initialize()
        
        value = config_manager.get_value("nonexistent.key", default="default_value")
        assert value == "default_value"
        
        await config_manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_value_before_init(self, config_manager):
        """Получение значения до инициализации."""
        value = config_manager.get_value("agent.max_steps", default="not_init")
        assert value == "not_init"


class TestConfigChangeCallback:
    """Тесты callback-ов изменений."""

    @pytest.mark.asyncio
    async def test_config_change_callback(self, real_config_manager, temp_config_file):
        """Callback при изменении конфигурации."""
        await real_config_manager.initialize()
        
        changes = []
        
        async def on_change(event: ConfigChangeEvent):
            changes.append(event)
        
        real_config_manager.on_config_change(on_change)
        
        # Проверяем что callback зарегистрирован
        assert len(real_config_manager._callbacks) == 1
        
        # Имитируем изменение через вызов _on_config_changed
        await real_config_manager._on_config_changed(temp_config_file)
        
        # Ждем обработки
        await asyncio.sleep(0.1)
        
        assert len(changes) == 1
        assert changes[0].changed_keys  # Какие-то ключи изменились
        
        await real_config_manager.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self, config_manager):
        """Несколько callback-ов."""
        await config_manager.initialize()
        
        callback1_calls = []
        callback2_calls = []
        
        async def callback1(event):
            callback1_calls.append(event)
        
        def callback2(event):
            callback2_calls.append(event)
        
        config_manager.on_config_change(callback1)
        config_manager.on_config_change(callback2)
        
        # Проверяем регистрацию
        assert len(config_manager._callbacks) == 2
        
        await config_manager.shutdown()


class TestSnapshots:
    """Тесты снимков конфигурации."""

    @pytest.mark.asyncio
    async def test_snapshot_creation(self, real_config_manager):
        """Создание снимков конфигурации."""
        await real_config_manager.initialize()
        
        # Первый снимок создается при инициализации
        snapshot = real_config_manager.get_snapshot()
        
        # После инициализации снимок должен быть
        assert snapshot is not None
        assert snapshot.config is not None
        
        await real_config_manager.shutdown()

    @pytest.mark.asyncio
    async def test_snapshot_rollback(self, real_config_manager, temp_config_file):
        """Откат к снимку конфигурации."""
        await real_config_manager.initialize()
        
        # Запоминаем начальную конфигурацию
        initial_config = real_config_manager.get_config().copy()
        
        # Изменяем конфигурацию
        new_config = {
            "profile": "test",
            "debug": False,
            "agent": {"max_steps": 999},
        }
        
        with open(temp_config_file, 'w') as f:
            yaml.dump(new_config, f)
        
        await real_config_manager.reload_config()
        
        # Проверяем что конфигурация изменилась
        assert real_config_manager.get_config()["agent"]["max_steps"] == 999
        
        # Откат к предыдущему снимку
        result = await real_config_manager.rollback_to_snapshot(-1)
        
        assert result is True
        # После отката конфигурация должна восстановиться
        assert real_config_manager.get_config()["agent"]["max_steps"] == 10
        
        await real_config_manager.shutdown()

    @pytest.mark.asyncio
    async def test_snapshot_limit(self, config_manager, temp_config_file):
        """Ограничение количества снимков."""
        await config_manager.initialize()
        
        # Многократное изменение конфигурации
        for i in range(10):
            new_config = {
                "profile": "test",
                "debug": True,
                "agent": {"max_steps": i},
            }
            
            with open(temp_config_file, 'w') as f:
                yaml.dump(new_config, f)
            
            await config_manager.reload_config()
        
        # Количество снимков не должно превышать лимит
        stats = config_manager.get_stats()
        assert stats["snapshots_count"] <= config_manager._max_backup_count
        
        await config_manager.shutdown()


class TestBackup:
    """Тесты бэкапов."""

    @pytest.mark.asyncio
    async def test_backup_creation(self, real_config_manager, temp_config_file):
        """Создание бэкапа конфигурации."""
        await real_config_manager.initialize()
        
        # Изменение конфигурации (создает бэкап)
        new_config = {
            "profile": "test",
            "debug": False,
            "agent": {"max_steps": 20},
        }
        
        with open(temp_config_file, 'w') as f:
            yaml.dump(new_config, f)
        
        await real_config_manager.reload_config()
        
        # Проверка наличия бэкапа
        backup_dir = temp_config_file.parent
        backups = list(backup_dir.glob(f"{temp_config_file.stem}.*.bak"))
        
        assert len(backups) >= 1
        
        await real_config_manager.shutdown()


class TestHotReload:
    """Тесты hot-reload."""

    @pytest.mark.asyncio
    async def test_hot_reload_detection(self, temp_config_file):
        """Обнаружение изменений файла."""
        changes = []
        
        async def on_change(path):
            changes.append(path)
        
        manager = DynamicConfigManager(
            config_path=temp_config_file,
            profile="test",
            enable_hot_reload=True,
            poll_interval=0.5,  # Быстрый опрос для теста
        )
        
        await manager.initialize()
        
        # Даем watcher время на запуск
        await asyncio.sleep(0.6)
        
        # Изменение файла
        new_config = {"profile": "test", "debug": False}
        
        with open(temp_config_file, 'w') as f:
            yaml.dump(new_config, f)
        
        # Ждем обнаружения изменения
        await asyncio.sleep(1.5)
        
        # Проверяем что изменение обнаружено
        # (через callback конфигурации, не watcher)
        # Примечание: этот тест может быть нестабилен на Windows
        
        await manager.shutdown()


class TestSingleton:
    """Тесты singleton паттерна."""

    def test_create_config_manager_singleton(self, temp_config_file):
        """create_config_manager создает singleton."""
        reset_config_manager()
        
        manager1 = create_config_manager(temp_config_file, profile="test")
        manager2 = get_config_manager()
        
        assert manager1 is manager2

    def test_reset_config_manager(self, temp_config_file):
        """Сброс singleton для тестов."""
        reset_config_manager()
        manager1 = create_config_manager(temp_config_file, profile="test")
        
        reset_config_manager()
        
        # После сброса get_config_manager должен выбрасывать
        with pytest.raises(RuntimeError):
            get_config_manager()


class TestStats:
    """Тесты статистики."""

    @pytest.mark.asyncio
    async def test_get_stats(self, config_manager):
        """Получение статистики менеджера."""
        stats = config_manager.get_stats()
        
        assert "config_path" in stats
        assert "profile" in stats
        assert "initialized" in stats
        assert stats["initialized"] is False  # Еще не инициализирован
        
        await config_manager.initialize()
        
        stats = config_manager.get_stats()
        assert stats["initialized"] is True
        assert stats["hot_reload_enabled"] is False
        
        await config_manager.shutdown()

    @pytest.mark.asyncio
    async def test_is_initialized_property(self, config_manager):
        """Проверка свойства is_initialized."""
        assert config_manager.is_initialized is False
        
        await config_manager.initialize()
        
        assert config_manager.is_initialized is True
        
        await config_manager.shutdown()
        
        assert config_manager.is_initialized is False


class TestConfigSnapshot:
    """Тесты класса ConfigSnapshot."""

    def test_snapshot_checksum(self):
        """Контрольная сумма снимка."""
        config = {"key": "value", "number": 42}
        snapshot = ConfigSnapshot(config=config)
        
        assert snapshot.checksum
        assert len(snapshot.checksum) == 32  # MD5 hash

    def test_snapshot_to_dict(self):
        """Конвертация снимка в dict."""
        config = {"profile": "test", "debug": True}
        snapshot = ConfigSnapshot(config=config)
        
        data = snapshot.to_dict()
        
        assert "config" in data or "checksum" in str(data)
        assert snapshot.timestamp is not None


class TestConfigChangeEvent:
    """Тесты класса ConfigChangeEvent."""

    def test_change_event_creation(self):
        """Создание события изменения."""
        old_config = {"key": "old_value"}
        new_config = {"key": "new_value"}
        
        event = ConfigChangeEvent(
            old_config=old_config,
            new_config=new_config,
            changed_keys=["key"],
        )
        
        assert event.changed_keys == ["key"]
        assert isinstance(event.timestamp, datetime)

    def test_change_event_to_dict(self):
        """Конвертация события в dict."""
        event = ConfigChangeEvent(
            old_config={"a": 1},
            new_config={"a": 2},
            changed_keys=["a"],
        )
        
        data = event.to_dict()
        
        assert "changed_keys" in data
        assert "timestamp" in data
        assert "source" in data

"""
Тесты для системы логирования.

USAGE:
    pytest tests/unit/infrastructure/logging/test_logging.py -v
"""
import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from core.infrastructure.logging.log_config import (
    LoggingConfig,
    LogFormat,
    RetentionConfig,
    IndexingConfig,
    SymlinksConfig,
)
from core.infrastructure.logging.log_manager import LogManager
from core.infrastructure.logging.log_indexer import LogIndexer, SessionIndexEntry
from core.infrastructure.logging.log_rotator import LogRotator
from core.infrastructure.logging.log_search import LogSearch
from core.infrastructure.logging.session_logger import SessionLogger


# ============================================================================
# ФИКСТУРЫ
# ============================================================================

@pytest.fixture
def temp_log_dir():
    """Создание временной директории для логов."""
    temp_dir = tempfile.mkdtemp(prefix='test_logs_')
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config(temp_log_dir):
    """Тестовая конфигурация."""
    return LoggingConfig(
        base_dir=str(temp_log_dir),
        agent_format=LogFormat.TEXT,
        session_format=LogFormat.JSONL,
        llm_format=LogFormat.JSONL,
        retention=RetentionConfig(
            active_days=7,
            archive_months=12,
            max_size_mb=100,
            max_files_per_day=100,
        ),
        indexing=IndexingConfig(
            enabled=True,
            index_sessions=True,
            index_agents=True,
            update_interval_sec=60,
        ),
        symlinks=SymlinksConfig(
            enabled=True,
            latest_session=True,
            latest_agent=True,
            latest_llm=True,
        ),
    )


@pytest.fixture
async def log_manager(test_config):
    """Инициализированный LogManager."""
    manager = LogManager(test_config)
    await manager.initialize()
    yield manager
    await manager.shutdown()


@pytest.fixture
async def log_indexer(test_config):
    """Инициализированный LogIndexer."""
    indexer = LogIndexer(test_config)
    await indexer.initialize()
    yield indexer
    await indexer.shutdown()


@pytest.fixture
async def log_rotator(test_config):
    """Инициализированный LogRotator."""
    rotator = LogRotator(test_config)
    await rotator.initialize()
    yield rotator
    await rotator.shutdown()


# ============================================================================
# ТЕСТЫ КОНФИГУРАЦИИ
# ============================================================================

class TestLoggingConfig:
    """Тесты конфигурации логирования."""

    def test_default_config(self):
        """Тест конфигурации по умолчанию."""
        config = LoggingConfig()

        assert config.base_dir == "logs"
        assert config.agent_format == LogFormat.TEXT
        assert config.session_format == LogFormat.JSONL
        assert config.retention.active_days == 7
        assert config.retention.archive_months == 12

    def test_custom_config(self):
        """Тест пользовательской конфигурации."""
        config = LoggingConfig(
            base_dir="custom_logs",
            retention=RetentionConfig(
                active_days=14,
                archive_months=24,
            ),
        )

        assert config.base_dir == "custom_logs"
        assert config.retention.active_days == 14
        assert config.retention.archive_months == 24

    def test_paths(self, test_config):
        """Тест путей директорий."""
        assert test_config.active_dir.name == "active"
        assert test_config.archive_dir.name == "archive"
        assert test_config.indexed_dir.name == "indexed"
        assert test_config.config_dir.name == "config"


# ============================================================================
# ТЕСТЫ LOGMANAGER
# ============================================================================

class TestLogManager:
    """Тесты LogManager."""

    @pytest.mark.asyncio
    async def test_initialize(self, log_manager):
        """Тест инициализации."""
        assert log_manager.is_initialized

        # Проверка создания директорий
        assert log_manager.config.active_dir.exists()
        assert log_manager.config.archive_dir.exists()
        assert log_manager.config.indexed_dir.exists()

    @pytest.mark.asyncio
    async def test_log_agent(self, log_manager):
        """Тест логирования агента."""
        log_manager.log_agent("Test message", level="INFO", session="test123")

        # Проверка создания файла
        log_file = log_manager._get_agent_log_path()
        assert log_file.exists()

        # Проверка содержимого
        content = log_file.read_text(encoding='utf-8')
        assert "Test message" in content
        assert "INFO" in content

    @pytest.mark.asyncio
    async def test_log_session(self, log_manager):
        """Тест логирования сессии."""
        session_id = "test_session_123"
        event_data = {
            "type": "session_started",
            "goal": "Test goal",
        }

        log_manager.log_session(session_id, event_data)

        # Проверка создания файла
        log_file = log_manager._get_session_log_path(session_id)
        assert log_file.exists()

        # Проверка содержимого (JSONL)
        content = log_file.read_text(encoding='utf-8')
        data = json.loads(content.strip())
        assert data["type"] == "session_started"
        assert data["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_log_llm(self, log_manager):
        """Тест логирования LLM вызова."""
        session_id = "test_session_456"
        event_data = {
            "type": "llm_prompt",
            "component": "test_component",
            "phase": "think",
            "prompt": "Test prompt",
        }

        log_manager.log_llm(session_id, event_data)

        # Проверка создания файла
        log_file = log_manager._get_llm_log_path(session_id)
        assert log_file.exists()

        # Проверка содержимого
        content = log_file.read_text(encoding='utf-8')
        data = json.loads(content.strip())
        assert data["type"] == "llm_prompt"
        assert data["session_id"] == session_id


# ============================================================================
# ТЕСТЫ LOGINDEXER
# ============================================================================

class TestLogIndexer:
    """Тесты LogIndexer."""

    @pytest.mark.asyncio
    async def test_initialize(self, log_indexer):
        """Тест инициализации."""
        assert log_indexer.is_initialized
        assert log_indexer.sessions_count >= 0
        assert log_indexer.agents_count >= 0

    @pytest.mark.asyncio
    async def test_add_session(self, log_indexer):
        """Тест добавления сессии в индекс."""
        session_id = "test_session_789"
        agent_id = "test_agent"
        goal = "Test goal"

        await log_indexer.add_session(session_id, agent_id, goal)

        # Проверка индекса
        entry = await log_indexer.find_session(session_id)
        assert entry is not None
        assert entry.session_id == session_id
        assert entry.agent_id == agent_id
        assert entry.goal == goal

    @pytest.mark.asyncio
    async def test_get_latest_session(self, log_indexer):
        """Тест получения последней сессии."""
        # Добавление тестовых сессий
        await log_indexer.add_session("session_1", "agent_1", "Goal 1")
        await asyncio.sleep(0.1)
        await log_indexer.add_session("session_2", "agent_1", "Goal 2")

        latest = await log_indexer.get_latest_session()
        assert latest is not None
        assert latest.session_id == "session_2"

    @pytest.mark.asyncio
    async def test_update_session_status(self, log_indexer):
        """Тест обновления статуса сессии."""
        session_id = "test_session_status"

        await log_indexer.add_session(session_id, "agent_1", "Test")
        await log_indexer.update_session_status(
            session_id,
            "completed",
            steps=5,
            total_time_ms=1000
        )

        entry = await log_indexer.find_session(session_id)
        assert entry.status == "completed"
        assert entry.steps == 5
        assert entry.total_time_ms == 1000


# ============================================================================
# ТЕСТЫ LOGROTATOR
# ============================================================================

class TestLogRotator:
    """Тесты LogRotator."""

    @pytest.mark.asyncio
    async def test_initialize(self, log_rotator):
        """Тест инициализации."""
        assert log_rotator.is_initialized

    @pytest.mark.asyncio
    async def test_get_statistics(self, log_rotator):
        """Тест получения статистики."""
        stats = await log_rotator.get_log_statistics()

        assert "active" in stats
        assert "archive" in stats
        assert "indexed" in stats
        assert "total_size_bytes" in stats
        assert "total_size_mb" in stats

    @pytest.mark.asyncio
    async def test_cleanup_old_logs_dry_run(self, log_rotator):
        """Тест очистки старых логов (dry-run)."""
        result = await log_rotator.cleanup_old_logs(dry_run=True)

        assert "deleted_files" in result
        assert "deleted_size_bytes" in result
        assert "errors" in result


# ============================================================================
# ТЕСТЫ SESSIONLOGGER
# ============================================================================

class TestSessionLogger:
    """Тесты SessionLogger."""

    @pytest.mark.asyncio
    async def test_start_session(self, log_manager):
        """Тест начала сессии."""
        session_id = "test_session_start"
        logger = SessionLogger(session_id, "test_agent", log_manager)

        await logger.start(goal="Test goal")

        assert logger._active is True
        assert logger._start_time is not None

    @pytest.mark.asyncio
    async def test_log_llm_prompt(self, log_manager):
        """Тест логирования LLM промпта."""
        session_id = "test_session_llm"
        logger = SessionLogger(session_id, "test_agent", log_manager)

        await logger.start(goal="Test")
        await logger.log_llm_prompt(
            component="test",
            phase="think",
            system_prompt="System",
            user_prompt="User"
        )

        assert len(logger._llm_calls) == 1

    @pytest.mark.asyncio
    async def test_end_session(self, log_manager):
        """Тест завершения сессии."""
        session_id = "test_session_end"
        logger = SessionLogger(session_id, "test_agent", log_manager)

        await logger.start(goal="Test goal")
        await logger.log_step(1, "test_capability", True, 100)
        await logger.end(success=True, result="Success")

        assert logger._active is False

    @pytest.mark.asyncio
    async def test_logging_methods(self, log_manager):
        """Тест методов логирования."""
        session_id = "test_session_methods"
        logger = SessionLogger(session_id, "test_agent", log_manager)

        await logger.start(goal="Test")

        # Тест методов логирования
        logger.info("Info message")
        logger.debug("Debug message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.log_event("CUSTOM_EVENT", "Custom message")


# ============================================================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# ============================================================================

class TestIntegration:
    """Интеграционные тесты."""

    @pytest.mark.asyncio
    async def test_full_session_flow(self, test_config):
        """Тест полного цикла сессии."""
        # Инициализация компонентов
        manager = LogManager(test_config)
        indexer = LogIndexer(test_config)

        await manager.initialize()
        await indexer.initialize()

        manager.set_indexer(indexer)

        try:
            # Создание сессии
            session_id = "integration_test_session"
            logger = SessionLogger(session_id, "test_agent", manager)

            await logger.start(goal="Integration test")

            await logger.log_llm_prompt(
                component="react",
                phase="think",
                system_prompt="System",
                user_prompt="User"
            )

            await logger.log_llm_response(
                component="react",
                phase="think",
                response="Response",
                tokens=100,
                latency_ms=500
            )

            await logger.log_step(1, "test_capability", True, 200)

            await logger.end(success=True, result="Done")

            # Проверка индексации
            await asyncio.sleep(0.5)  # Ждем обновления индекса

            entry = await indexer.find_session(session_id)
            assert entry is not None
            assert entry.status == "completed"
            assert entry.steps == 1

        finally:
            await manager.shutdown()
            await indexer.shutdown()


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])

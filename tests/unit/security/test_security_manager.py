"""
Тесты для Security Manager.

TESTS:
- test_security_manager_creation: Создание менеджера
- test_sql_validator: Валидатор SQL
- test_file_validator: Валидатор файлов
- test_validate_and_audit: Валидация с аудитом
- test_audit_log: Лог аудита
- test_stats: Статистика
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.security import (
    SecurityManager,
    SecurityValidator,
    SQLSecurityValidator,
    FileSecurityValidator,
    SecurityResourceType,
    SecurityError,
    get_security_manager,
    create_security_manager,
    reset_security_manager,
)
from core.infrastructure.event_bus import reset_event_bus_manager


@pytest.fixture
def security_manager():
    """Фикстура: менеджер безопасности."""
    reset_security_manager()
    reset_event_bus_manager()
    manager = SecurityManager()
    yield manager
    reset_security_manager()
    reset_event_bus_manager()


class TestSecurityManagerCreation:
    """Тесты создания менеджера."""

    def test_create_security_manager(self):
        """Создание менеджера безопасности."""
        manager = SecurityManager()
        
        assert manager is not None
        assert len(manager._validators) >= 2  # SQL и File по умолчанию

    def test_get_security_manager_singleton(self):
        """get_security_manager возвращает singleton."""
        reset_security_manager()
        
        manager1 = get_security_manager()
        manager2 = get_security_manager()
        
        assert manager1 is manager2

    def test_reset_security_manager(self):
        """Сброс singleton."""
        reset_security_manager()
        manager1 = get_security_manager()
        
        reset_security_manager()
        manager2 = get_security_manager()
        
        assert manager1 is not manager2


class TestSQLValidator:
    """Тесты SQL валидатора."""

    @pytest.mark.asyncio
    async def test_valid_sql(self, security_manager):
        """Валидация корректного SQL."""
        result = await security_manager.validate(
            resource_type=SecurityResourceType.SQL,
            operation="execute_query",
            data={"sql": "SELECT * FROM users WHERE id = 1"}
        )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_drop_table_forbidden(self, security_manager):
        """Запрет DROP TABLE."""
        with pytest.raises(SecurityError) as exc_info:
            await security_manager.validate(
                resource_type=SecurityResourceType.SQL,
                operation="execute_query",
                data={"sql": "DROP TABLE users"}
            )
        
        assert "Forbidden SQL pattern" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_delete_from_forbidden(self, security_manager):
        """Запрет DELETE FROM."""
        with pytest.raises(SecurityError):
            await security_manager.validate(
                resource_type=SecurityResourceType.SQL,
                operation="execute_query",
                data={"sql": "DELETE FROM users WHERE id = 1"}
            )

    @pytest.mark.asyncio
    async def test_truncate_forbidden(self, security_manager):
        """Запрет TRUNCATE."""
        with pytest.raises(SecurityError):
            await security_manager.validate(
                resource_type=SecurityResourceType.SQL,
                operation="execute_query",
                data={"sql": "TRUNCATE TABLE users"}
            )

    @pytest.mark.asyncio
    async def test_alter_table_forbidden(self, security_manager):
        """Запрет ALTER TABLE."""
        with pytest.raises(SecurityError):
            await security_manager.validate(
                resource_type=SecurityResourceType.SQL,
                operation="execute_query",
                data={"sql": "ALTER TABLE users ADD COLUMN email VARCHAR(255)"}
            )

    @pytest.mark.asyncio
    async def test_sql_injection_detection(self, security_manager):
        """Обнаружение SQL injection."""
        # UNION SELECT injection
        with pytest.raises(SecurityError):
            await security_manager.validate(
                resource_type=SecurityResourceType.SQL,
                operation="execute_query",
                data={"sql": "SELECT * FROM users UNION SELECT * FROM passwords"}
            )

    @pytest.mark.asyncio
    async def test_non_query_operation(self, security_manager):
        """Валидация не-query операции."""
        result = await security_manager.validate(
            resource_type=SecurityResourceType.SQL,
            operation="describe_table",
            data={"table": "users"}
        )
        
        assert result is True


class TestFileValidator:
    """Тесты файлового валидатора."""

    @pytest.mark.asyncio
    async def test_valid_file_path(self, security_manager):
        """Валидация корректного пути."""
        result = await security_manager.validate(
            resource_type=SecurityResourceType.FILE,
            operation="read",
            data={"path": "data/file.txt"}
        )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_path_traversal_detection(self, security_manager):
        """Обнаружение path traversal."""
        with pytest.raises(SecurityError) as exc_info:
            await security_manager.validate(
                resource_type=SecurityResourceType.FILE,
                operation="read",
                data={"path": "../../../etc/passwd"}
            )
        
        assert "Path traversal" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_absolute_path_traversal(self, security_manager):
        """Path traversal с абсолютным путём."""
        with pytest.raises(SecurityError):
            await security_manager.validate(
                resource_type=SecurityResourceType.FILE,
                operation="read",
                data={"path": "/etc/passwd"}
            )

    @pytest.mark.asyncio
    async def test_allowed_extensions(self):
        """Проверка разрешённых расширений."""
        validator = FileSecurityValidator(
            allowed_extensions=['.txt', '.pdf']
        )
        
        # Разрешённое расширение
        result = await validator.validate(
            "read",
            {"path": "file.txt"}
        )
        assert result is True
        
        # Запрещённое расширение
        with pytest.raises(SecurityError):
            await validator.validate(
                "read",
                {"path": "file.exe"}
            )


class TestValidateAndAudit:
    """Тесты валидации с аудитом."""

    @pytest.mark.asyncio
    async def test_validate_and_audit_success(self, security_manager):
        """Успешная валидация с аудитом."""
        result = await security_manager.validate_and_audit(
            resource_type=SecurityResourceType.SQL,
            operation="execute_query",
            data={"sql": "SELECT * FROM users"},
            user_id="test_user",
            resource_name="users_table"
        )
        
        assert result is True
        
        # Проверка что аудит записан
        audit_log = security_manager.get_audit_log()
        assert len(audit_log) >= 1
        assert audit_log[-1]["user_id"] == "test_user"
        assert audit_log[-1]["success"] is True

    @pytest.mark.asyncio
    async def test_validate_and_audit_failure(self, security_manager):
        """Неуспешная валидация с аудитом."""
        with pytest.raises(SecurityError):
            await security_manager.validate_and_audit(
                resource_type=SecurityResourceType.SQL,
                operation="execute_query",
                data={"sql": "DROP TABLE users"},
                user_id="test_user",
                resource_name="users_table"
            )
        
        # Проверка что аудит записан
        audit_log = security_manager.get_audit_log()
        assert len(audit_log) >= 1
        assert audit_log[-1]["user_id"] == "test_user"
        assert audit_log[-1]["success"] is False


class TestAuditLog:
    """Тесты лога аудита."""

    @pytest.mark.asyncio
    async def test_audit_manual(self, security_manager):
        """Ручной аудит."""
        await security_manager.audit(
            action="read",
            user_id="user123",
            resource="file.txt",
            success=True,
            resource_type="file"
        )
        
        audit_log = security_manager.get_audit_log()
        
        assert len(audit_log) == 1
        assert audit_log[0]["action"] == "read"
        assert audit_log[0]["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_audit_log_limit(self, security_manager):
        """Ограничение размера лога."""
        security_manager._max_audit_log_size = 10
        
        for i in range(20):
            await security_manager.audit(
                action="test",
                user_id=f"user{i}",
                resource="resource",
                success=True
            )
        
        audit_log = security_manager.get_audit_log()
        
        assert len(audit_log) == 10
        # Последние записи
        assert audit_log[0]["user_id"] == "user10"

    @pytest.mark.asyncio
    async def test_get_audit_log_limit(self, security_manager):
        """Получение ограниченного лога."""
        for i in range(50):
            await security_manager.audit(
                action="test",
                user_id="user",
                resource="resource",
                success=True
            )
        
        # Получение только 10 записей
        audit_log = security_manager.get_audit_log(limit=10)
        
        assert len(audit_log) == 10


class TestSecurityStats:
    """Тесты статистики."""

    @pytest.mark.asyncio
    async def test_get_stats(self, security_manager):
        """Получение статистики."""
        # Добавляем события
        await security_manager.audit("read", "user1", "res1", True)
        await security_manager.audit("read", "user1", "res2", True)
        await security_manager.audit("write", "user2", "res3", False)
        
        stats = security_manager.get_stats()
        
        assert stats["total_events"] == 3
        assert stats["success_events"] == 2
        assert stats["failed_events"] == 1
        assert "read" in stats["by_action"]
        assert "user1" in stats["by_user"]

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, security_manager):
        """Статистика без событий."""
        stats = security_manager.get_stats()
        
        assert stats["total_events"] == 0
        assert stats["success_rate"] == 100


class TestCustomValidator:
    """Тесты кастомных валидаторов."""

    @pytest.mark.asyncio
    async def test_register_custom_validator(self, security_manager):
        """Регистрация кастомного валидатора."""
        class CustomValidator(SecurityValidator):
            async def validate(self, operation, data):
                if operation == "forbidden":
                    raise SecurityError("Operation forbidden")
                return True
        
        validator = CustomValidator(SecurityResourceType.API)
        security_manager.register_validator(SecurityResourceType.API, validator)
        
        # Разрешённая операция
        result = await security_manager.validate(
            SecurityResourceType.API,
            "allowed",
            {}
        )
        assert result is True
        
        # Запрещённая операция
        with pytest.raises(SecurityError):
            await security_manager.validate(
                SecurityResourceType.API,
                "forbidden",
                {}
            )

    @pytest.mark.asyncio
    async def test_get_validator(self, security_manager):
        """Получение валидатора."""
        validator = security_manager.get_validator(SecurityResourceType.SQL)
        
        assert validator is not None
        assert isinstance(validator, SQLSecurityValidator)

    @pytest.mark.asyncio
    async def test_get_unknown_validator(self, security_manager):
        """Получение неизвестного валидатора."""
        validator = security_manager.get_validator(SecurityResourceType.DATABASE)
        
        assert validator is None


class TestSingleton:
    """Тесты singleton паттерна."""

    def test_create_security_manager_singleton(self):
        """create_security_manager создает singleton."""
        reset_security_manager()
        
        manager1 = create_security_manager()
        manager2 = get_security_manager()
        
        assert manager1 is manager2

    def test_reset_security_manager(self):
        """Сброс singleton."""
        reset_security_manager()
        manager1 = create_security_manager()
        
        reset_security_manager()
        
        with pytest.raises(AssertionError):
            assert manager1 is get_security_manager()

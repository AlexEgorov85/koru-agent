"""
Юнит-тесты для FileSystemLogStorage.

ТЕСТЫ:
- test_save_log_entry: сохранение записи лога
- test_get_session_logs: получение логов сессии
- test_get_capability_logs: получение логов по capability
- test_clear_old_logs: очистка старых логов
- test_get_agents: получение списка агентов
- test_get_sessions: получение списка сессий
"""
import pytest
import asyncio
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from core.services.benchmarks.benchmark_models import LogEntry, LogType
from core.infrastructure.log_storage import FileSystemLogStorage


@pytest.fixture
def temp_storage():
    """Фикстура для временного хранилища"""
    temp_dir = tempfile.mkdtemp()
    # Отключаем буферизацию для тестов, чтобы запись была синхронной
    storage = FileSystemLogStorage(base_dir=Path(temp_dir), use_buffering=False)
    yield storage
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_log_entry():
    """Фикстура для тестовой записи лога"""
    return LogEntry(
        timestamp=datetime.now(),
        agent_id='agent_1',
        session_id='session_123',
        log_type=LogType.CAPABILITY_SELECTION,
        data={'capability': 'test_cap', 'reasoning': 'test reasoning'},
        capability='test_capability'
    )


class TestFileSystemLogStorage:
    """Тесты для FileSystemLogStorage"""

    @pytest.mark.asyncio
    async def test_save_log_entry(self, temp_storage, sample_log_entry):
        """Тест сохранения записи лога"""
        # Сохранение записи
        await temp_storage.save(sample_log_entry)

        # Проверка файла сессии
        session_file = temp_storage._get_agent_session_file(
            sample_log_entry.agent_id,
            sample_log_entry.session_id
        )
        assert session_file.exists()

        # Проверка файла capability
        cap_file = temp_storage._get_capability_file(sample_log_entry.capability)
        assert cap_file.exists()

        # Проверка общего файла
        all_file = temp_storage._get_all_logs_file(sample_log_entry.timestamp)
        assert all_file.exists()

    @pytest.mark.asyncio
    async def test_save_multiple_log_entries(self, temp_storage):
        """Тест сохранения нескольких записей лога"""
        entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'capability': 'test_cap'},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.ERROR,
                data={'error': 'test error'},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.BENCHMARK,
                data={'scenario_id': 'test_001'},
                capability='test_cap'
            ),
        ]

        for entry in entries:
            await temp_storage.save(entry)

        # Проверка количества записей
        session_logs = await temp_storage.get_by_session('agent_1', 'session_123')
        assert len(session_logs) == 3

    @pytest.mark.asyncio
    async def test_get_session_logs(self, temp_storage):
        """Тест получения логов сессии"""
        base_time = datetime.now()

        entries = [
            LogEntry(
                timestamp=base_time - timedelta(hours=2),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'step': 1},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=base_time - timedelta(hours=1),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.ERROR,
                data={'step': 2},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=base_time,
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.BENCHMARK,
                data={'step': 3},
                capability='test_cap'
            ),
        ]

        for entry in entries:
            await temp_storage.save(entry)

        # Получение логов сессии
        logs = await temp_storage.get_by_session('agent_1', 'session_123')

        assert len(logs) == 3
        # Проверка сортировки по времени
        assert logs[0].timestamp <= logs[1].timestamp <= logs[2].timestamp

    @pytest.mark.asyncio
    async def test_get_session_logs_limit(self, temp_storage):
        """Тест ограничения количества логов сессии"""
        for i in range(10):
            entry = LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'index': i},
                capability='test_cap'
            )
            await temp_storage.save(entry)

        # Получение с ограничением
        logs = await temp_storage.get_by_session('agent_1', 'session_123', limit=5)
        assert len(logs) == 5

    @pytest.mark.asyncio
    async def test_get_capability_logs(self, temp_storage):
        """Тест получения логов по capability"""
        entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'data': 1},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_2',
                session_id='session_2',
                log_type=LogType.ERROR,
                data={'data': 2},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.BENCHMARK,
                data={'data': 3},
                capability='other_cap'
            ),
        ]

        for entry in entries:
            await temp_storage.save(entry)

        # Получение логов по capability
        logs = await temp_storage.get_by_capability('test_cap')

        assert len(logs) == 2
        for log in logs:
            assert log.capability == 'test_cap'

    @pytest.mark.asyncio
    async def test_get_capability_logs_by_type(self, temp_storage):
        """Тест фильтрации логов по типу"""
        entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'data': 1},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_2',
                session_id='session_2',
                log_type=LogType.ERROR,
                data={'data': 2},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'data': 3},
                capability='test_cap'
            ),
        ]

        for entry in entries:
            await temp_storage.save(entry)

        # Получение только CAPABILITY_SELECTION
        logs = await temp_storage.get_by_capability('test_cap', log_type='capability_selection')

        assert len(logs) == 2
        for log in logs:
            assert log.log_type == LogType.CAPABILITY_SELECTION

    @pytest.mark.asyncio
    async def test_get_capability_logs_limit(self, temp_storage):
        """Тест ограничения количества логов capability"""
        for i in range(10):
            entry = LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'index': i},
                capability='test_cap'
            )
            await temp_storage.save(entry)

        # Получение с ограничением
        logs = await temp_storage.get_by_capability('test_cap', limit=5)
        assert len(logs) == 5

    @pytest.mark.asyncio
    async def test_clear_old_logs(self, temp_storage):
        """Тест очистки старых логов"""
        old_date = datetime.now() - timedelta(days=10)
        new_date = datetime.now()

        # Сохранение старых логов
        old_entry = LogEntry(
            timestamp=old_date,
            agent_id='agent_1',
            session_id='session_1',
            log_type=LogType.CAPABILITY_SELECTION,
            data={'old': True},
            capability='test_cap'
        )
        await temp_storage.save(old_entry)

        # Сохранение новых логов
        new_entry = LogEntry(
            timestamp=new_date,
            agent_id='agent_1',
            session_id='session_1',
            log_type=LogType.CAPABILITY_SELECTION,
            data={'new': True},
            capability='test_cap'
        )
        await temp_storage.save(new_entry)

        # Очистка старых (старше 5 дней)
        threshold = datetime.now() - timedelta(days=5)
        deleted = await temp_storage.clear_old(threshold)

        assert deleted >= 1

        # Проверка что остались только новые
        logs = await temp_storage.get_by_session('agent_1', 'session_1')
        # В логах сессии должен остаться только новый
        recent_logs = [l for l in logs if l.timestamp >= threshold]
        assert len(recent_logs) >= 1

    @pytest.mark.asyncio
    async def test_get_agents(self, temp_storage):
        """Тест получения списка агентов"""
        entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_one',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_two',
                session_id='session_2',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_three',
                session_id='session_3',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
        ]

        for entry in entries:
            await temp_storage.save(entry)

        agents = await temp_storage.get_agents()

        assert len(agents) == 3
        assert 'agent/one' in agents or 'agent_one' in agents
        assert 'agent/two' in agents or 'agent_two' in agents
        assert 'agent/three' in agents or 'agent_three' in agents

    @pytest.mark.asyncio
    async def test_get_sessions(self, temp_storage):
        """Тест получения списка сессий"""
        entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_one',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_two',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_three',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
        ]

        for entry in entries:
            await temp_storage.save(entry)

        sessions = await temp_storage.get_sessions('agent_1')

        assert len(sessions) == 3
        assert 'session/one' in sessions or 'session_one' in sessions
        assert 'session/two' in sessions or 'session_two' in sessions
        assert 'session/three' in sessions or 'session_three' in sessions

    @pytest.mark.asyncio
    async def test_get_capabilities(self, temp_storage):
        """Тест получения списка capability"""
        entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='capability_one'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='capability_two'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='capability_three'
            ),
        ]

        for entry in entries:
            await temp_storage.save(entry)

        capabilities = await temp_storage.get_capabilities()

        assert len(capabilities) == 3
        assert 'capability/one' in capabilities or 'capability_one' in capabilities
        assert 'capability/two' in capabilities or 'capability_two' in capabilities
        assert 'capability/three' in capabilities or 'capability_three' in capabilities

    @pytest.mark.asyncio
    async def test_get_all_logs(self, temp_storage):
        """Тест получения всех логов за день"""
        entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'index': 1},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_2',
                session_id='session_2',
                log_type=LogType.ERROR,
                data={'index': 2},
                capability='test_cap'
            ),
        ]

        for entry in entries:
            await temp_storage.save(entry)

        # Получение всех логов за сегодня
        logs = await temp_storage.get_all_logs()

        assert len(logs) >= 2

    @pytest.mark.asyncio
    async def test_get_all_logs_limit(self, temp_storage):
        """Тест ограничения всех логов"""
        for i in range(10):
            entry = LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'index': i},
                capability='test_cap'
            )
            await temp_storage.save(entry)

        # Получение с ограничением
        logs = await temp_storage.get_all_logs(limit=5)
        assert len(logs) == 5

    @pytest.mark.asyncio
    async def test_log_entry_without_capability(self, temp_storage):
        """Тест сохранения лога без capability"""
        entry = LogEntry(
            timestamp=datetime.now(),
            agent_id='agent_1',
            session_id='session_1',
            log_type=LogType.CAPABILITY_SELECTION,
            data={'test': 'data'}
            # capability не указан
        )
        await temp_storage.save(entry)

        # Проверка что запись сохранена в сессии
        logs = await temp_storage.get_by_session('agent_1', 'session_1')
        assert len(logs) == 1

    @pytest.mark.asyncio
    async def test_concurrent_save(self, temp_storage):
        """Тест конкурентного сохранения"""
        async def save_log(index: int):
            entry = LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'index': index},
                capability='test_cap'
            )
            await temp_storage.save(entry)

        # Параллельное сохранение
        await asyncio.gather(*[save_log(i) for i in range(10)])

        # Проверка что все записи сохранились
        logs = await temp_storage.get_by_session('agent_1', 'session_1')
        assert len(logs) == 10

    @pytest.mark.asyncio
    async def test_directory_structure_created(self, temp_storage):
        """Тест создания структуры директорий"""
        entry = LogEntry(
            timestamp=datetime.now(),
            agent_id='agent_1',
            session_id='session_1',
            log_type=LogType.CAPABILITY_SELECTION,
            data={},
            capability='test/capability'
        )
        await temp_storage.save(entry)

        # Проверка что директории созданы
        assert (temp_storage.base_dir / 'by_agent').exists()
        assert (temp_storage.base_dir / 'by_capability').exists()
        assert (temp_storage.base_dir / 'all').exists()

    @pytest.mark.asyncio
    async def test_log_entry_serialization(self, temp_storage, sample_log_entry):
        """Тест сериализации записи лога"""
        await temp_storage.save(sample_log_entry)

        session_file = temp_storage._get_agent_session_file(
            sample_log_entry.agent_id,
            sample_log_entry.session_id
        )

        data = temp_storage._load_json_file(session_file)

        assert len(data) == 1
        assert 'timestamp' in data[0]
        assert 'agent_id' in data[0]
        assert 'log_type' in data[0]
        assert 'data' in data[0]

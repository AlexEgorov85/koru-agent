"""
Тесты для моделей системы обучения.

TESTS:
- test_execution_context_snapshot: тесты контекста выполнения
- test_log_entry_extended: тесты расширенного LogEntry
"""
import pytest
from datetime import datetime
from core.models.data.execution import ExecutionContextSnapshot
from core.components.services.benchmarks.benchmark_models import LogEntry, LogType


class TestExecutionContextSnapshot:
    """Тесты для ExecutionContextSnapshot"""

    def test_create_snapshot(self):
        """Тест создания снимка контекста"""
        snapshot = ExecutionContextSnapshot(
            agent_id='test_agent',
            session_id='test_session',
            step_number=1,
            selected_capability='planning.create_plan',
            reasoning='Test reasoning',
            success=True
        )

        assert snapshot.agent_id == 'test_agent'
        assert snapshot.session_id == 'test_session'
        assert snapshot.step_number == 1
        assert snapshot.selected_capability == 'planning.create_plan'
        assert snapshot.reasoning == 'Test reasoning'
        assert snapshot.success is True
        assert snapshot.step_quality_score is None

    def test_snapshot_to_dict(self):
        """Тест сериализации в словарь"""
        snapshot = ExecutionContextSnapshot(
            agent_id='test_agent',
            session_id='test_session',
            step_number=5,
            available_capabilities=['cap1', 'cap2'],
            selected_capability='planning.create_plan',
            behavior_pattern='react',
            reasoning='Test reasoning',
            input_parameters={'param1': 'value1'},
            output_result={'result': 'success'},
            execution_time_ms=150.5,
            tokens_used=250,
            success=True,
            prompt_version='v1.0',
            contract_version='v2.0',
            step_quality_score=0.85
        )

        data = snapshot.to_dict()

        assert data['agent_id'] == 'test_agent'
        assert data['session_id'] == 'test_session'
        assert data['step_number'] == 5
        assert data['available_capabilities'] == ['cap1', 'cap2']
        assert data['selected_capability'] == 'planning.create_plan'
        assert data['reasoning'] == 'Test reasoning'
        assert data['execution_time_ms'] == 150.5
        assert data['tokens_used'] == 250
        assert data['step_quality_score'] == 0.85
        assert 'timestamp' in data

    def test_snapshot_from_dict(self):
        """Тест десериализации из словаря"""
        data = {
            'agent_id': 'test_agent',
            'session_id': 'test_session',
            'step_number': 3,
            'timestamp': '2026-02-27T10:00:00',
            'available_capabilities': ['cap1'],
            'selected_capability': 'planning.create_plan',
            'behavior_pattern': 'react',
            'reasoning': 'Test',
            'input_parameters': {},
            'output_result': None,
            'execution_time_ms': 100.0,
            'tokens_used': 150,
            'success': True,
            'prompt_version': 'v1.0',
            'contract_version': 'v2.0',
            'step_quality_score': 0.9
        }

        snapshot = ExecutionContextSnapshot.from_dict(data)

        assert snapshot.agent_id == 'test_agent'
        assert snapshot.step_number == 3
        assert snapshot.step_quality_score == 0.9
        assert snapshot.timestamp == datetime(2026, 2, 27, 10, 0, 0)

    def test_snapshot_default_values(self):
        """Тест значений по умолчанию"""
        snapshot = ExecutionContextSnapshot(
            agent_id='agent',
            session_id='session',
            step_number=1
        )

        assert snapshot.available_capabilities == []
        assert snapshot.selected_capability == ''
        assert snapshot.reasoning == ''
        assert snapshot.input_parameters == {}
        assert snapshot.output_result is None
        assert snapshot.execution_time_ms == 0.0
        assert snapshot.tokens_used == 0
        assert snapshot.success is True
        assert snapshot.prompt_version == ''
        assert snapshot.contract_version == ''
        assert snapshot.step_quality_score is None


class TestLogEntryExtended:
    """Тесты для расширенного LogEntry"""

    def test_log_entry_with_new_fields(self):
        """Тест LogEntry с новыми полями"""
        entry = LogEntry(
            timestamp=datetime.now(),
            agent_id='test_agent',
            session_id='test_session',
            log_type=LogType.CAPABILITY_SELECTION,
            data={
                'capability': 'planning.create_plan',
                'reasoning': 'Test reasoning'
            },
            execution_context={'step': 1},
            step_quality_score=0.85,
            benchmark_scenario_id='scenario_001'
        )

        assert entry.execution_context == {'step': 1}
        assert entry.step_quality_score == 0.85
        assert entry.benchmark_scenario_id == 'scenario_001'

    def test_log_entry_to_dict_with_new_fields(self):
        """Тест сериализации с новыми полями"""
        entry = LogEntry(
            timestamp=datetime(2026, 2, 27, 10, 0, 0),
            agent_id='test_agent',
            session_id='test_session',
            log_type=LogType.CAPABILITY_SELECTION,
            data={'capability': 'test'},
            execution_context={'key': 'value'},
            step_quality_score=0.9,
            benchmark_scenario_id='scenario_001'
        )

        data = entry.to_dict()

        assert data['execution_context'] == {'key': 'value'}
        assert data['step_quality_score'] == 0.9
        assert data['benchmark_scenario_id'] == 'scenario_001'

    def test_log_entry_from_dict_with_new_fields(self):
        """Тест десериализации с новыми полями"""
        data = {
            'timestamp': '2026-02-27T10:00:00',
            'agent_id': 'test_agent',
            'session_id': 'test_session',
            'log_type': 'capability_selection',
            'data': {'capability': 'test'},
            'execution_context': {'step': 1},
            'step_quality_score': 0.75,
            'benchmark_scenario_id': 'scenario_002'
        }

        entry = LogEntry.from_dict(data)

        assert entry.execution_context == {'step': 1}
        assert entry.step_quality_score == 0.75
        assert entry.benchmark_scenario_id == 'scenario_002'

    def test_log_entry_default_none_values(self):
        """Тест значений None по умолчанию"""
        entry = LogEntry(
            timestamp=datetime.now(),
            agent_id='agent',
            session_id='session',
            log_type=LogType.ERROR,
            data={'error': 'test'}
        )

        assert entry.execution_context is None
        assert entry.step_quality_score is None
        assert entry.benchmark_scenario_id is None

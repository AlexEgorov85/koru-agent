"""
Тесты для CLI скрипта run_benchmark.py.

ТЕСТЫ:
- test_parse_args_basic: парсинг базовых аргументов
- test_parse_args_compare: парсинг аргументов сравнения
- test_parse_args_output: парсинг аргумента output
- test_run_single_benchmark_mock: тест одиночного бенчмарка с моками
- test_run_comparison_mock: тест сравнения версий с моками
"""
import pytest
import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestParseArgs:
    """Тесты парсинга аргументов"""

    def test_parse_args_basic(self):
        """Тест парсинга базовых аргументов"""
        from scripts.cli.run_benchmark import parse_args

        test_args = ['run_benchmark.py', '-c', 'test.capability', '-v', 'v1.0.0']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.capability == 'test.capability'
        assert args.version == 'v1.0.0'
        assert args.compare is None
        assert args.output is None
        assert args.verbose is False

    def test_parse_args_compare(self):
        """Тест парсинга аргументов сравнения"""
        from scripts.cli.run_benchmark import parse_args

        test_args = ['run_benchmark.py', '-c', 'test.capability', '--compare', 'v1.0.0', 'v2.0.0']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.capability == 'test.capability'
        assert args.version is None
        assert args.compare == ['v1.0.0', 'v2.0.0']

    def test_parse_args_output(self):
        """Тест парсинга аргумента output"""
        from scripts.cli.run_benchmark import parse_args

        test_args = ['run_benchmark.py', '-c', 'test.capability', '-v', 'v1.0.0', '-o', 'results.json']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.capability == 'test.capability'
        assert args.version == 'v1.0.0'
        assert args.output == 'results.json'

    def test_parse_args_verbose(self):
        """Тест парсинга аргумента verbose"""
        from scripts.cli.run_benchmark import parse_args

        test_args = ['run_benchmark.py', '-c', 'test.capability', '-v', 'v1.0.0', '--verbose']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.verbose is True

    def test_parse_args_missing_capability(self):
        """Тест отсутствия обязательного аргумента capability"""
        from scripts.cli.run_benchmark import parse_args

        test_args = ['run_benchmark.py', '-v', 'v1.0.0']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                parse_args()


class TestRunSingleBenchmark:
    """Тесты run_single_benchmark"""

    @pytest.mark.asyncio
    async def test_run_single_benchmark_mock(self):
        """Тест одиночного бенчмарка с моками"""
        from scripts.cli.run_benchmark import run_single_benchmark

        # Мокаем зависимости (импорты внутри функции)
        with patch('core.config.app_config.AppConfig') as mock_config, \
             patch('core.infrastructure_context.infrastructure_context.InfrastructureContext') as mock_infra, \
             patch('core.application_context.application_context.ApplicationContext') as mock_app, \
             patch('core.services.benchmark_service.BenchmarkService') as mock_bench_service, \
             patch('core.services.accuracy_evaluator.AccuracyEvaluatorService') as mock_eval, \
             patch('core.infrastructure.metrics_storage.FileSystemMetricsStorage') as mock_storage, \
             patch('core.infrastructure.event_bus.event_bus.get_event_bus') as mock_bus:

            # Настройка моков
            mock_config.load_from_file.return_value = MagicMock()
            mock_infra.return_value.initialize = AsyncMock()
            mock_infra.return_value.metrics_collector = MagicMock()
            mock_app.return_value.initialize = AsyncMock()

            mock_benchmark_service = MagicMock()
            mock_benchmark_service.run_benchmark = AsyncMock(return_value=MagicMock(
                scenario_id='test_001',
                success=True,
                overall_score=0.85,
                execution_time_ms=150.0,
                tokens_used=500,
                error=None
            ))
            mock_bench_service.return_value = mock_benchmark_service

            # Запуск бенчмарка
            result = await run_single_benchmark('test.capability', 'v1.0.0', verbose=False)

            # Проверка результатов
            assert result['capability'] == 'test.capability'
            assert result['version'] == 'v1.0.0'
            assert 'timestamp' in result
            assert result['total_scenarios'] >= 0
            assert 'success_rate' in result

    @pytest.mark.asyncio
    async def test_run_single_benchmark_error(self):
        """Тест ошибки бенчмарка"""
        from scripts.cli.run_benchmark import run_single_benchmark

        with patch('core.config.app_config.AppConfig') as mock_config:
            mock_config.load_from_file.side_effect = Exception("Config not found")

            result = await run_single_benchmark('test.capability', 'v1.0.0', verbose=False)

            assert 'error' in result
            assert result['capability'] == 'test.capability'


class TestRunComparison:
    """Тесты run_comparison"""

    @pytest.mark.asyncio
    async def test_run_comparison_mock(self):
        """Тест сравнения версий с моками"""
        from scripts.cli.run_benchmark import run_comparison

        with patch('scripts.run_benchmark.run_single_benchmark') as mock_run:
            # Мокаем результаты для обеих версий
            mock_run.side_effect = [
                {
                    'capability': 'test.capability',
                    'version': 'v1.0.0',
                    'success_rate': 0.7,
                    'average_score': 0.75,
                    'average_execution_time_ms': 200.0
                },
                {
                    'capability': 'test.capability',
                    'version': 'v2.0.0',
                    'success_rate': 0.9,
                    'average_score': 0.85,
                    'average_execution_time_ms': 180.0
                }
            ]

            result = await run_comparison('test.capability', 'v1.0.0', 'v2.0.0', verbose=False)

            # Проверка результатов
            assert result['capability'] == 'test.capability'
            assert result['version_a'] == 'v1.0.0'
            assert result['version_b'] == 'v2.0.0'
            assert 'metrics_a' in result
            assert 'metrics_b' in result
            assert 'improvements' in result
            assert result['improvements']['winner'] == 'v2.0.0'  # v2.0.0 лучше

    @pytest.mark.asyncio
    async def test_run_comparison_no_improvement(self):
        """Тест сравнения без улучшения"""
        from scripts.cli.run_benchmark import run_comparison

        with patch('scripts.run_benchmark.run_single_benchmark') as mock_run:
            # Мокаем результаты - v2 хуже v1
            mock_run.side_effect = [
                {
                    'capability': 'test.capability',
                    'version': 'v1.0.0',
                    'success_rate': 0.9,
                    'average_score': 0.9,
                    'average_execution_time_ms': 150.0
                },
                {
                    'capability': 'test.capability',
                    'version': 'v2.0.0',
                    'success_rate': 0.7,
                    'average_score': 0.75,
                    'average_execution_time_ms': 200.0
                }
            ]

            result = await run_comparison('test.capability', 'v1.0.0', 'v2.0.0', verbose=False)

            assert result['improvements']['winner'] == 'v1.0.0'  # v1.0.0 лучше
            assert result['improvements']['score_change_percent'] < 0


class TestMain:
    """Тесты main функции"""

    @pytest.mark.asyncio
    async def test_main_single_benchmark(self):
        """Тест main для одиночного бенчмарка"""
        from scripts.cli.run_benchmark import main

        test_args = [
            'run_benchmark.py',
            '-c', 'test.capability',
            '-v', 'v1.0.0'
        ]

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_benchmark.run_single_benchmark') as mock_run:

            mock_run.return_value = {
                'capability': 'test.capability',
                'version': 'v1.0.0',
                'success_rate': 0.8,
                'scenarios': [{}]  # Есть сценарии = успех
            }

            # main() не вызовет sys.exit(0) явно, но завершится успешно
            # Проверяем что функция выполняется без ошибок
            try:
                await main()
            except SystemExit as e:
                # Exit code 0 при успехе
                assert e.code == 0

    @pytest.mark.asyncio
    async def test_main_comparison(self):
        """Тест main для сравнения версий"""
        from scripts.cli.run_benchmark import main

        test_args = [
            'run_benchmark.py',
            '-c', 'test.capability',
            '--compare', 'v1.0.0', 'v2.0.0'
        ]

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_benchmark.run_comparison') as mock_run:

            mock_run.return_value = {
                'capability': 'test.capability',
                'version_a': 'v1.0.0',
                'version_b': 'v2.0.0',
                'improvements': {'winner': 'v2.0.0'}
            }

            try:
                await main()
            except SystemExit as e:
                assert e.code == 0

    @pytest.mark.asyncio
    async def test_main_missing_version(self):
        """Тест main без указания версии"""
        from scripts.cli.run_benchmark import main

        test_args = ['run_benchmark.py', '-c', 'test.capability']

        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exit_info:
                await main()

            # Exit code 2 (argparse error) при ошибке
            assert exit_info.value.code != 0

    @pytest.mark.asyncio
    async def test_main_with_output(self, tmp_path):
        """Тест main с сохранением в файл"""
        from scripts.cli.run_benchmark import main

        output_file = tmp_path / 'results.json'

        test_args = [
            'run_benchmark.py',
            '-c', 'test.capability',
            '-v', 'v1.0.0',
            '-o', str(output_file)
        ]

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_benchmark.run_single_benchmark') as mock_run:

            mock_run.return_value = {
                'capability': 'test.capability',
                'version': 'v1.0.0',
                'success_rate': 0.8,
                'scenarios': [{}]
            }

            try:
                await main()
            except SystemExit:
                pass  # Ожидаем exit при успехе

            # Проверка что файл создан
            assert output_file.exists()

            # Проверка содержимого
            with open(output_file, 'r') as f:
                data = json.load(f)

            assert data['capability'] == 'test.capability'
            assert data['version'] == 'v1.0.0'

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self):
        """Тест прерывания пользователем"""
        from scripts.cli.run_benchmark import main

        test_args = ['run_benchmark.py', '-c', 'test.capability', '-v', 'v1.0.0']

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_benchmark.run_single_benchmark') as mock_run:

            mock_run.side_effect = KeyboardInterrupt()

            with pytest.raises(SystemExit) as exit_info:
                await main()

            # Exit code 130 при Ctrl+C
            assert exit_info.value.code == 130

    @pytest.mark.asyncio
    async def test_main_low_success_rate(self):
        """Тест main с низким success rate"""
        from scripts.cli.run_benchmark import main

        test_args = ['run_benchmark.py', '-c', 'test.capability', '-v', 'v1.0.0']

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_benchmark.run_single_benchmark') as mock_run:

            mock_run.return_value = {
                'capability': 'test.capability',
                'version': 'v1.0.0',
                'success_rate': 0.3,  # < 0.5
                'scenarios': []
            }

            with pytest.raises(SystemExit) as exit_info:
                await main()

            # Exit code 1 при низком success rate
            assert exit_info.value.code == 1

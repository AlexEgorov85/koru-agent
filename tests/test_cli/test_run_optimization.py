"""
Тесты для CLI скрипта run_optimization.py.

ТЕСТЫ:
- test_parse_args_basic: парсинг базовых аргументов
- test_parse_args_mode: парсинг режима оптимизации
- test_run_optimization_mock: тест оптимизации с моками
- test_main: тест main функции
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
        from scripts.cli.run_optimization import parse_args

        test_args = ['run_optimization.py', '-c', 'test.capability']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.capability == 'test.capability'
        assert args.mode == 'accuracy'  # default
        assert args.target_accuracy == 0.9  # default
        assert args.max_iterations == 5  # default

    def test_parse_args_mode(self):
        """Тест парсинга режима оптимизации"""
        from scripts.cli.run_optimization import parse_args

        test_args = ['run_optimization.py', '-c', 'test.capability', '-m', 'balanced']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.mode == 'balanced'

    def test_parse_args_invalid_mode(self):
        """Тест невалидного режима"""
        from scripts.cli.run_optimization import parse_args

        test_args = ['run_optimization.py', '-c', 'test.capability', '-m', 'invalid']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                parse_args()

    def test_parse_args_target_accuracy(self):
        """Тест парсинга целевой точности"""
        from scripts.cli.run_optimization import parse_args

        test_args = ['run_optimization.py', '-c', 'test.capability', '-t', '0.95']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.target_accuracy == 0.95

    def test_parse_args_max_iterations(self):
        """Тест парсинга количества итераций"""
        from scripts.cli.run_optimization import parse_args

        test_args = ['run_optimization.py', '-c', 'test.capability', '--max-iterations', '10']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.max_iterations == 10

    def test_parse_args_output(self):
        """Тест парсинга output файла"""
        from scripts.cli.run_optimization import parse_args

        test_args = ['run_optimization.py', '-c', 'test.capability', '-o', 'results.json']
        with patch.object(sys, 'argv', test_args):
            args = parse_args()

        assert args.output == 'results.json'


class TestRunOptimization:
    """Тесты run_optimization"""

    @pytest.mark.asyncio
    async def test_run_optimization_mock(self):
        """Тест оптимизации с моками"""
        from scripts.cli.run_optimization import run_optimization
        from core.benchmarks.benchmark_models import OptimizationResult, OptimizationMode

        # Создаём мок результата
        mock_result = OptimizationResult(
            capability='test.capability',
            from_version='v1.0.0',
            to_version='v2.0.0',
            mode=OptimizationMode.ACCURACY,
            iterations=3,
            initial_metrics={'accuracy': 0.7},
            final_metrics={'accuracy': 0.85},
            improvements={'accuracy': 21.4},
            target_achieved=True,
            recommendations=['Improve input validation']
        )

        with patch('core.config.app_config.AppConfig') as mock_config, \
             patch('core.infrastructure.context.infrastructure_context.InfrastructureContext') as mock_infra, \
             patch('core.application.context.application_context.ApplicationContext') as mock_app, \
             patch('core.application.services.optimization_service.OptimizationService') as mock_opt_service, \
             patch('core.application.services.benchmark_service.BenchmarkService') as mock_bench, \
             patch('core.application.services.accuracy_evaluator.AccuracyEvaluatorService') as mock_eval, \
             patch('core.application.services.prompt_contract_generator.PromptContractGenerator') as mock_gen, \
             patch('core.infrastructure.metrics_storage.FileSystemMetricsStorage') as mock_storage, \
             patch('core.infrastructure.event_bus.event_bus.get_event_bus') as mock_bus:

            # Настройка моков
            mock_config.load_from_file.return_value = MagicMock()
            mock_infra.return_value.initialize = AsyncMock()
            mock_infra.return_value.metrics_collector = MagicMock()
            mock_infra.return_value.log_collector = MagicMock()
            mock_app.return_value.initialize = AsyncMock()

            mock_optimization_service = MagicMock()
            mock_optimization_service.start_optimization_cycle = AsyncMock(
                return_value=mock_result
            )
            mock_opt_service.return_value = mock_optimization_service

            # Запуск оптимизации
            result = await run_optimization(
                capability='test.capability',
                mode='accuracy',
                target_accuracy=0.9,
                max_iterations=5,
                verbose=False
            )

            # Проверка результатов
            assert result['capability'] == 'test.capability'
            assert result['mode'] == 'accuracy'
            assert result['status'] == 'completed'
            assert result['from_version'] == 'v1.0.0'
            assert result['to_version'] == 'v2.0.0'
            assert result['iterations'] == 3
            assert result['target_achieved'] is True

    @pytest.mark.asyncio
    async def test_run_optimization_not_started(self):
        """Тест когда оптимизация не запущена"""
        from scripts.cli.run_optimization import run_optimization

        with patch('core.config.app_config.AppConfig') as mock_config, \
             patch('core.infrastructure.context.infrastructure_context.InfrastructureContext') as mock_infra, \
             patch('core.application.context.application_context.ApplicationContext') as mock_app, \
             patch('core.application.services.optimization_service.OptimizationService') as mock_opt_service:

            mock_config.load_from_file.return_value = MagicMock()
            mock_infra.return_value.initialize = AsyncMock()
            mock_app.return_value.initialize = AsyncMock()

            mock_optimization_service = MagicMock()
            mock_optimization_service.start_optimization_cycle = AsyncMock(return_value=None)
            mock_opt_service.return_value = mock_optimization_service

            result = await run_optimization('test.capability', 'accuracy', 0.9, 5)

            assert result['status'] == 'not_started'

    @pytest.mark.asyncio
    async def test_run_optimization_error(self):
        """Тест ошибки оптимизации"""
        from scripts.cli.run_optimization import run_optimization

        with patch('core.config.app_config.AppConfig') as mock_config:
            mock_config.load_from_file.side_effect = Exception("Config error")

            result = await run_optimization('test.capability', 'accuracy', 0.9, 5, verbose=False)

            assert result['status'] == 'failed'
            assert 'error' in result


class TestMain:
    """Тесты main функции"""

    @pytest.mark.asyncio
    async def test_main_success(self):
        """Тест успешной оптимизации"""
        from scripts.cli.run_optimization import main

        test_args = ['run_optimization.py', '-c', 'test.capability']

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_optimization.run_optimization') as mock_run:

            mock_run.return_value = {
                'capability': 'test.capability',
                'mode': 'accuracy',
                'status': 'completed',
                'target_achieved': True
            }

            try:
                await main()
            except SystemExit as e:
                assert e.code == 0

    @pytest.mark.asyncio
    async def test_main_not_started(self):
        """Тест когда оптимизация не запущена"""
        from scripts.cli.run_optimization import main

        test_args = ['run_optimization.py', '-c', 'test.capability']

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_optimization.run_optimization') as mock_run:

            mock_run.return_value = {
                'capability': 'test.capability',
                'mode': 'accuracy',
                'status': 'not_started'
            }

            with pytest.raises(SystemExit) as exit_info:
                await main()

            # Exit code 2 для not_started
            assert exit_info.value.code == 2

    @pytest.mark.asyncio
    async def test_main_failed(self):
        """Тест неудачной оптимизации"""
        from scripts.cli.run_optimization import main

        test_args = ['run_optimization.py', '-c', 'test.capability']

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_optimization.run_optimization') as mock_run:

            mock_run.return_value = {
                'capability': 'test.capability',
                'mode': 'accuracy',
                'status': 'failed',
                'error': 'Test error'
            }

            with pytest.raises(SystemExit) as exit_info:
                await main()

            # Exit code 1 для failed
            assert exit_info.value.code == 1

    @pytest.mark.asyncio
    async def test_main_with_output(self, tmp_path):
        """Тест main с сохранением в файл"""
        from scripts.cli.run_optimization import main

        output_file = tmp_path / 'optimization_results.json'

        test_args = [
            'run_optimization.py',
            '-c', 'test.capability',
            '-o', str(output_file)
        ]

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_optimization.run_optimization') as mock_run:

            mock_run.return_value = {
                'capability': 'test.capability',
                'mode': 'accuracy',
                'status': 'completed',
                'target_achieved': True
            }

            try:
                await main()
            except SystemExit:
                pass

            # Проверка что файл создан
            assert output_file.exists()

            # Проверка содержимого
            with open(output_file, 'r') as f:
                data = json.load(f)

            assert data['capability'] == 'test.capability'
            assert data['status'] == 'completed'

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self):
        """Тест прерывания пользователем"""
        from scripts.cli.run_optimization import main

        test_args = ['run_optimization.py', '-c', 'test.capability']

        with patch.object(sys, 'argv', test_args), \
             patch('scripts.run_optimization.run_optimization') as mock_run:

            mock_run.side_effect = KeyboardInterrupt()

            with pytest.raises(SystemExit) as exit_info:
                await main()

            assert exit_info.value.code == 130

    @pytest.mark.asyncio
    async def test_main_missing_capability(self):
        """Тест без указания capability"""
        from scripts.cli.run_optimization import parse_args

        test_args = ['run_optimization.py']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                parse_args()

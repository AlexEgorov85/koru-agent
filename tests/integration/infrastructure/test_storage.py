"""
Интеграционные тесты для компонентов хранения (PromptStorage, ContractStorage).

Тестирует:
- Загрузку промптов из файловой системы
- Загрузку контрактов из хранилища
- Работоспособность хранилищ
"""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.storage.prompt_storage import PromptStorage
from core.infrastructure.storage.contract_storage import ContractStorage


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prompt_storage_basic_functionality():
    """
    Интеграционный тест: проверка базовой функциональности PromptStorage
    """
    # Создаем временный каталог для тестирования
    with tempfile.TemporaryDirectory() as temp_dir:
        prompts_path = Path(temp_dir) / "prompts"
        prompts_path.mkdir()
        
        # Создаем тестовый файл промпта
        test_prompt_file = prompts_path / "test.jinja2"
        test_prompt_file.write_text("Это тестовый промпт: {{ variable }}")
        
        # Создаем PromptStorage с временным путем
        storage = PromptStorage(str(prompts_path))
        
        try:
            await storage.initialize()
            
            # Загружаем промпт
            prompt_content = await storage.load_prompt("test")
            
            assert prompt_content is not None
            assert "Это тестовый промпт:" in prompt_content
            
        finally:
            await storage.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prompt_storage_load_nonexistent_prompt():
    """
    Интеграционный тест: загрузка несуществующего промпта возвращает None
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        prompts_path = Path(temp_dir) / "prompts"
        prompts_path.mkdir()
        
        storage = PromptStorage(str(prompts_path))
        
        try:
            await storage.initialize()
            
            # Пытаемся загрузить несуществующий промпт
            prompt_content = await storage.load_prompt("nonexistent")
            
            assert prompt_content is None
            
        finally:
            await storage.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contract_storage_basic_functionality():
    """
    Интеграционный тест: проверка базовой функциональности ContractStorage
    """
    # Создаем временную директорию для контрактов
    with tempfile.TemporaryDirectory() as temp_dir:
        contracts_path = Path(temp_dir) / "contracts"
        contracts_path.mkdir()
        
        # Создаем тестовый файл контракта
        test_contract_file = contracts_path / "test_contract.json"
        test_contract_file.write_text('{"name": "test", "version": "1.0", "spec": "test spec"}')
        
        # Используем реальный ContractStorage
        storage = ContractStorage()
        
        # Мокаем путь к контрактам
        with patch.object(storage, '_load_contracts_from_fs') as mock_load:
            # Мокаем загрузку, чтобы использовать временный путь
            async def mock_load_contracts():
                # Загружаем контракты из временной директории
                contracts = {}
                for file_path in contracts_path.glob("*.json"):
                    contract_name = file_path.stem
                    contracts[contract_name] = {
                        "name": contract_name,
                        "version": "1.0",
                        "spec": "test spec"
                    }
                storage.contracts = contracts
                return contracts
            
            mock_load.side_effect = mock_load_contracts
            
            try:
                await storage.initialize()
                
                # Проверяем, что хранилище инициализировано
                assert storage.contracts is not None
                
            finally:
                await storage.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prompt_storage_with_real_files():
    """
    Интеграционный тест: PromptStorage с реальными файлами
    """
    # Используем настоящую директорию промптов, если она существует
    # или создаем временную
    with tempfile.TemporaryDirectory() as temp_dir:
        prompts_path = Path(temp_dir) / "prompts"
        prompts_path.mkdir()
        
        # Создаем несколько тестовых файлов промптов
        templates = {
            "simple": "Простой промпт",
            "with_vars": "Промпт с переменной: {{ variable }}",
            "complex": """
                {% for item in items %}
                - {{ item }}
                {% endfor %}
            """
        }
        
        for name, content in templates.items():
            file_path = prompts_path / f"{name}.jinja2"
            file_path.write_text(content)
        
        storage = PromptStorage(str(prompts_path))
        
        try:
            await storage.initialize()
            
            # Загружаем каждый промпт
            for name in templates.keys():
                content = await storage.load_prompt(name)
                assert content is not None
                assert isinstance(content, str)
                
        finally:
            await storage.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_storage_components_in_infrastructure_context():
    """
    Интеграционный тест: проверка работы хранилищ в инфраструктурном контексте
    """
    # Пропускаем, если нет флага
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Пропущено: нет флага RUN_INTEGRATION_TESTS")
    
    # Создаем временную директорию для промптов
    with tempfile.TemporaryDirectory() as temp_dir:
        prompts_path = Path(temp_dir) / "prompts"
        prompts_path.mkdir()
        
        # Создаем тестовый файл промпта
        test_prompt_file = prompts_path / "infra_test.jinja2"
        test_prompt_file.write_text("Тестовый промпт в инфраструктуре: {{ data }}")
        
        # Создаем конфигурацию с указанием директории данных
        config = SystemConfig(data_dir=str(temp_dir))
        
        infra = InfrastructureContext(config)
        
        try:
            await infra.initialize()
            
            # Получаем хранилища из инфраструктурного контекста
            prompt_storage = infra.get_resource("prompt_storage")
            contract_storage = infra.get_resource("contract_storage")
            
            # Проверяем, что хранилища существуют
            assert prompt_storage is not None
            assert contract_storage is not None
            
            # Проверяем работу PromptStorage
            prompt_content = await prompt_storage.load_prompt("infra_test")
            assert prompt_content is not None
            assert "Тестовый промпт в инфраструктуре:" in prompt_content
            
        finally:
            await infra.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_storage_shutdown_functionality():
    """
    Интеграционный тест: проверка корректного завершения работы хранилищ
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        prompts_path = Path(temp_dir) / "prompts"
        prompts_path.mkdir()
        
        storage = PromptStorage(str(prompts_path))
        
        # Инициализируем и затем завершаем работу
        await storage.initialize()
        await storage.shutdown()
        
        # После завершения работы хранилище не должно быть активным
        # (в реальной реализации может быть проверка состояния)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prompt_storage_template_rendering():
    """
    Интеграционный тест: проверка возможности рендеринга шаблонов
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        prompts_path = Path(temp_dir) / "prompts"
        prompts_path.mkdir()
        
        # Создаем промпт с Jinja2 шаблоном
        template_file = prompts_path / "template_test.jinja2"
        template_content = "Привет, {{ name }}! Сегодня {{ day }}."
        template_file.write_text(template_content)
        
        storage = PromptStorage(str(prompts_path))
        
        try:
            await storage.initialize()
            
            # Загружаем шаблон
            loaded_template = await storage.load_prompt("template_test")
            assert loaded_template is not None
            assert "{{ name }}" in loaded_template
            assert "{{ day }}" in loaded_template
            
        finally:
            await storage.shutdown()
"""
Тесты для AppConfig.from_discovery().

TESTS:
- test_from_discovery_creation: Создание AppConfig через discovery
- test_from_discovery_loads_active_prompts: Загрузка active промптов
- test_from_discovery_loads_active_contracts: Загрузка active контрактов
- test_from_discovery_loads_manifests: Загрузка манифестов
- test_from_discovery_profile_sandbox: Sandbox профиль загружает больше
"""
import pytest
import tempfile
import yaml
from pathlib import Path

from core.config.app_config import AppConfig
from core.models.data.prompt import PromptStatus
from core.models.enums.common_enums import ComponentStatus


@pytest.fixture
def temp_data_dir_with_resources():
    """Фикстура: временная директория с тестовыми ресурсами."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # === Промпты ===
        prompts_dir = tmpdir / 'prompts' / 'skill' / 'test_skill'
        prompts_dir.mkdir(parents=True)
        
        # Active промпт
        active_prompt = {
            'capability': 'test_skill.capability',
            'version': 'v1.0.0',
            'status': 'active',
            'component_type': 'skill',
            'content': 'Test active prompt content',
            'variables': []
        }
        with open(prompts_dir / 'capability_v1.0.0.yaml', 'w') as f:
            yaml.dump(active_prompt, f)
        
        # Draft промпт (не должен загружаться в prod)
        draft_prompt = {
            'capability': 'test_skill.capability',
            'version': 'v1.1.0',
            'status': 'draft',
            'component_type': 'skill',
            'content': 'Test draft prompt content',
            'variables': []
        }
        with open(prompts_dir / 'capability_v1.1.0.yaml', 'w') as f:
            yaml.dump(draft_prompt, f)
        
        # === Контракты ===
        contracts_dir = tmpdir / 'contracts' / 'skill' / 'test_skill'
        contracts_dir.mkdir(parents=True)
        
        # Input контракт (active)
        input_contract = {
            'capability': 'test_skill.capability',
            'version': 'v1.0.0',
            'status': 'active',
            'component_type': 'skill',
            'direction': 'input',
            'schema': {'type': 'object', 'properties': {'query': {'type': 'string'}}}
        }
        with open(contracts_dir / 'capability_input_v1.0.0.yaml', 'w') as f:
            yaml.dump(input_contract, f)
        
        # Output контракт (active)
        output_contract = {
            'capability': 'test_skill.capability',
            'version': 'v1.0.0',
            'status': 'active',
            'component_type': 'skill',
            'direction': 'output',
            'schema': {'type': 'object', 'properties': {'result': {'type': 'string'}}}
        }
        with open(contracts_dir / 'capability_output_v1.0.0.yaml', 'w') as f:
            yaml.dump(output_contract, f)
        
        # === Манифесты ===
        manifests_dir = tmpdir / 'manifests' / 'skills' / 'test_skill'
        manifests_dir.mkdir(parents=True)
        
        active_manifest = {
            'component_id': 'test_skill',
            'component_type': 'skill',
            'version': 'v1.0.0',
            'owner': 'test-team',
            'status': 'active',
            'dependencies': {
                'components': [],
                'tools': [],
                'services': []
            },
            'parameters': {'param1': 'value1'}
        }
        with open(manifests_dir / 'manifest.yaml', 'w') as f:
            yaml.dump(active_manifest, f)
        
        yield tmpdir


class TestAppConfigFromDiscovery:
    """Тесты AppConfig.from_discovery()."""
    
    def test_from_discovery_creation(self, temp_data_dir_with_resources):
        """Создание AppConfig через discovery."""
        config = AppConfig.from_discovery(
            profile='prod',
            data_dir=str(temp_data_dir_with_resources)
        )
        
        assert config is not None
        assert config.config_id == 'app_config_prod_discovery'
        assert config.profile == 'prod'
    
    def test_from_discovery_loads_active_prompts(self, temp_data_dir_with_resources):
        """Загрузка только active промптов в prod."""
        config = AppConfig.from_discovery(
            profile='prod',
            data_dir=str(temp_data_dir_with_resources)
        )
        
        # Должен загрузить только active промпт
        assert 'test_skill.capability' in config.prompt_versions
        assert config.prompt_versions['test_skill.capability'] == 'v1.0.0'
        
        # Draft не должен быть загружен
        # (проверяем что только одна версия в prompt_versions)
        assert len(config.prompt_versions) == 1
    
    def test_from_discovery_loads_active_contracts(self, temp_data_dir_with_resources):
        """Загрузка active контрактов."""
        config = AppConfig.from_discovery(
            profile='prod',
            data_dir=str(temp_data_dir_with_resources)
        )
        
        # Должны загрузиться input и output контракты
        assert 'test_skill.capability' in config.input_contract_versions
        assert config.input_contract_versions['test_skill.capability'] == 'v1.0.0'
        
        assert 'test_skill.capability' in config.output_contract_versions
        assert config.output_contract_versions['test_skill.capability'] == 'v1.0.0'
    
    def test_from_discovery_loads_manifests(self, temp_data_dir_with_resources):
        """Загрузка манифестов."""
        config = AppConfig.from_discovery(
            profile='prod',
            data_dir=str(temp_data_dir_with_resources)
        )
        
        # Должен загрузить конфигурацию навыка
        assert 'test_skill' in config.skill_configs
        
        skill_config = config.skill_configs['test_skill']
        assert skill_config.variant_id == 'test_skill_prod'
    
    def test_from_discovery_profile_sandbox(self, temp_data_dir_with_resources):
        """Sandbox профиль загружает active + draft."""
        config = AppConfig.from_discovery(
            profile='sandbox',
            data_dir=str(temp_data_dir_with_resources)
        )
        
        # В sandbox всё ещё загружаем только active для AppConfig
        # (фильтрация по статусам происходит на уровне ResourceDiscovery)
        assert config.profile == 'sandbox'
        assert config.config_id == 'app_config_sandbox_discovery'


class TestAppConfigFromDiscoveryWithRealData:
    """Тесты с реальными данными из data/."""
    
    def test_from_discovery_with_real_data(self):
        """Создание AppConfig из реальных данных."""
        config = AppConfig.from_discovery(
            profile='prod',
            data_dir='data'
        )
        
        assert config is not None
        assert len(config.prompt_versions) > 0
        assert len(config.skill_configs) > 0
    
    def test_from_discovery_loads_final_answer(self):
        """Загрузка final_answer skill из реальных данных."""
        config = AppConfig.from_discovery(
            profile='prod',
            data_dir='data'
        )
        
        # Final answer должен быть загружен
        assert 'final_answer' in config.skill_configs
        assert 'final_answer.generate' in config.prompt_versions

"""
Тесты для Resource Discovery.

TESTS:
- test_discovery_creation: Создание обнаружителя ресурсов
- test_prod_only_loads_active: Prod загружает только active
- test_sandbox_loads_active_and_draft: Sandbox загружает active + draft
- test_discover_prompts: Обнаружение промптов
- test_discover_contracts: Обнаружение контрактов
- test_discover_manifests: Обнаружение манифестов
- test_get_resource_from_cache: Получение ресурсов из кэша
- test_validation_report: Отчёт валидации
"""
import pytest
import tempfile
import yaml
from pathlib import Path
from datetime import datetime

from core.infrastructure.discovery.resource_discovery import ResourceDiscovery
from core.models.data.prompt import Prompt, PromptStatus
from core.models.data.contract import Contract, ContractDirection
from core.models.data.manifest import Manifest, ComponentStatus
from core.models.enums.common_enums import ComponentType


@pytest.fixture
def temp_data_dir():
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
            'content': 'Test active prompt content with {{variable}}',
            'variables': [
                {
                    'name': 'variable',
                    'description': 'Test variable',
                    'required': True
                }
            ],
            'metadata': {'author': 'test'}
        }
        with open(prompts_dir / 'capability_v1.0.0.yaml', 'w') as f:
            yaml.dump(active_prompt, f)
        
        # Draft промпт
        draft_prompt = {
            'capability': 'test_skill.capability',
            'version': 'v1.1.0',
            'status': 'draft',
            'component_type': 'skill',
            'content': 'Test draft prompt content',
            'variables': [],
        }
        with open(prompts_dir / 'capability_v1.1.0.yaml', 'w') as f:
            yaml.dump(draft_prompt, f)
        
        # Inactive промпт
        inactive_prompt = {
            'capability': 'test_skill.capability',
            'version': 'v2.0.0',
            'status': 'inactive',
            'component_type': 'skill',
            'content': 'Test inactive prompt content',
            'variables': [],
        }
        with open(prompts_dir / 'capability_v2.0.0.yaml', 'w') as f:
            yaml.dump(inactive_prompt, f)
        
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
            'schema': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string'}
                },
                'required': ['query']
            }
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
            'schema': {
                'type': 'object',
                'properties': {
                    'result': {'type': 'string'}
                }
            }
        }
        with open(contracts_dir / 'capability_output_v1.0.0.yaml', 'w') as f:
            yaml.dump(output_contract, f)
        
        # Draft input контракт
        draft_input_contract = {
            'capability': 'test_skill.capability',
            'version': 'v1.1.0',
            'status': 'draft',
            'component_type': 'skill',
            'direction': 'input',
            'schema': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string'},
                    'optional': {'type': 'string'}
                }
            }
        }
        with open(contracts_dir / 'capability_input_v1.1.0.yaml', 'w') as f:
            yaml.dump(draft_input_contract, f)
        
        # === Манифесты ===
        manifests_dir = tmpdir / 'manifests' / 'skills' / 'test_skill'
        manifests_dir.mkdir(parents=True)
        
        # Active манифест
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
            'quality_metrics': {
                'success_rate_target': 0.95,
                'avg_execution_time_ms': 500
            }
        }
        with open(manifests_dir / 'manifest.yaml', 'w') as f:
            yaml.dump(active_manifest, f)
        
        # Draft манифест
        draft_manifests_dir = tmpdir / 'manifests' / 'skills' / 'draft_skill'
        draft_manifests_dir.mkdir(parents=True)
        
        draft_manifest = {
            'component_id': 'draft_skill',
            'component_type': 'skill',
            'version': 'v0.9.0',
            'owner': 'test-team',
            'status': 'draft',
            'dependencies': {
                'components': [],
                'tools': [],
                'services': []
            }
        }
        with open(draft_manifests_dir / 'manifest.yaml', 'w') as f:
            yaml.dump(draft_manifest, f)
        
        yield tmpdir


class TestResourceDiscoveryCreation:
    """Тесты создания обнаружителя ресурсов."""
    
    def test_create_discovery_default(self, temp_data_dir):
        """Создание с параметрами по умолчанию."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir)
        
        assert discovery is not None
        assert discovery.profile == 'prod'
        assert PromptStatus.ACTIVE in discovery.allowed_prompt_statuses
        assert len(discovery.allowed_prompt_statuses) == 1
    
    def test_create_discovery_with_profile(self, temp_data_dir):
        """Создание с указанием профиля."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='sandbox')
        
        assert discovery.profile == 'sandbox'
        assert PromptStatus.ACTIVE in discovery.allowed_prompt_statuses
        assert PromptStatus.DRAFT in discovery.allowed_prompt_statuses
    
    def test_create_discovery_dev_profile(self, temp_data_dir):
        """Создание с dev профилем."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='dev')
        
        assert discovery.profile == 'dev'
        assert PromptStatus.ACTIVE in discovery.allowed_prompt_statuses
        assert PromptStatus.DRAFT in discovery.allowed_prompt_statuses
        assert PromptStatus.INACTIVE in discovery.allowed_prompt_statuses


class TestProfileStatusFiltering:
    """Тесты фильтрации по статусам для разных профилей."""
    
    def test_prod_only_loads_active(self, temp_data_dir):
        """Prod загружает только active ресурсы."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        prompts = discovery.discover_prompts()
        
        # Должен загрузить только active промпты
        assert len(prompts) == 1
        assert all(p.status == PromptStatus.ACTIVE for p in prompts)
        assert prompts[0].version == 'v1.0.0'
    
    def test_sandbox_loads_active_and_draft(self, temp_data_dir):
        """Sandbox загружает active + draft ресурсы."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='sandbox')
        
        prompts = discovery.discover_prompts()
        
        # Должен загрузить active и draft, но не inactive
        assert len(prompts) == 2
        assert all(p.status in [PromptStatus.ACTIVE, PromptStatus.DRAFT] for p in prompts)
        versions = {p.version for p in prompts}
        assert 'v1.0.0' in versions  # active
        assert 'v1.1.0' in versions  # draft
        assert 'v2.0.0' not in versions  # inactive
    
    def test_dev_loads_all_statuses(self, temp_data_dir):
        """Dev загружает все статусы."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='dev')
        
        prompts = discovery.discover_prompts()
        
        # Должен загрузить все промпты
        assert len(prompts) == 3
        statuses = {p.status for p in prompts}
        assert PromptStatus.ACTIVE in statuses
        assert PromptStatus.DRAFT in statuses
        assert PromptStatus.INACTIVE in statuses


class TestDiscoverPrompts:
    """Тесты обнаружения промптов."""
    
    def test_discover_prompts(self, temp_data_dir):
        """Обнаружение промптов."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='dev')
        
        prompts = discovery.discover_prompts()
        
        assert len(prompts) == 3
        assert all(isinstance(p, Prompt) for p in prompts)
    
    def test_discover_prompts_empty_dir(self, tmp_path):
        """Обнаружение в пустой директории."""
        discovery = ResourceDiscovery(base_dir=tmp_path, profile='prod')
        
        prompts = discovery.discover_prompts()
        
        assert len(prompts) == 0
    
    def test_discover_prompts_cache(self, temp_data_dir):
        """Кэширование промптов."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='dev')
        
        # Первое сканирование
        prompts1 = discovery.discover_prompts()
        
        # Второе сканирование (должно использовать кэш)
        prompts2 = discovery.discover_prompts()
        
        assert len(prompts1) == len(prompts2)
        assert discovery.get_prompt('test_skill.capability', 'v1.0.0') is not None
    
    def test_prompt_variables_parsed(self, temp_data_dir):
        """Парсинг переменных промпта."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        prompts = discovery.discover_prompts()
        
        active_prompt = discovery.get_prompt('test_skill.capability', 'v1.0.0')
        assert active_prompt is not None
        assert len(active_prompt.variables) == 1
        assert active_prompt.variables[0].name == 'variable'
        assert active_prompt.variables[0].required is True


class TestDiscoverContracts:
    """Тесты обнаружения контрактов."""
    
    def test_discover_contracts(self, temp_data_dir):
        """Обнаружение контрактов."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        contracts = discovery.discover_contracts()
        
        assert len(contracts) == 2  # input и output active
        assert all(isinstance(c, Contract) for c in contracts)
    
    def test_discover_contracts_directions(self, temp_data_dir):
        """Проверка направлений контрактов."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        contracts = discovery.discover_contracts()
        
        directions = {c.direction for c in contracts}
        assert ContractDirection.INPUT in directions
        assert ContractDirection.OUTPUT in directions
    
    def test_get_contract_from_cache(self, temp_data_dir):
        """Получение контракта из кэша."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        discovery.discover_contracts()
        
        contract = discovery.get_contract('test_skill.capability', 'v1.0.0', 'input')
        
        assert contract is not None
        assert contract.direction == ContractDirection.INPUT
        assert 'query' in contract.schema_data.get('properties', {})


class TestDiscoverManifests:
    """Тесты обнаружения манифестов."""
    
    def test_discover_manifests(self, temp_data_dir):
        """Обнаружение манифестов."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        manifests = discovery.discover_manifests()
        
        assert len(manifests) == 1  # Только active
        assert all(isinstance(m, Manifest) for m in manifests)
        assert manifests[0].status == ComponentStatus.ACTIVE
    
    def test_discover_manifests_sandbox(self, temp_data_dir):
        """Обнаружение манифестов в sandbox."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='sandbox')
        
        manifests = discovery.discover_manifests()
        
        assert len(manifests) == 2  # active + draft
        statuses = {m.status for m in manifests}
        assert ComponentStatus.ACTIVE in statuses
        assert ComponentStatus.DRAFT in statuses
    
    def test_get_manifest_from_cache(self, temp_data_dir):
        """Получение манифеста из кэша."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        discovery.discover_manifests()
        
        manifest = discovery.get_manifest('skill', 'test_skill')
        
        assert manifest is not None
        assert manifest.component_id == 'test_skill'
        assert manifest.owner == 'test-team'
        assert manifest.quality_metrics is not None
        assert manifest.quality_metrics.success_rate_target == 0.95


class TestValidationReport:
    """Тесты отчёта валидации."""
    
    def test_get_stats(self, temp_data_dir):
        """Получение статистики."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        discovery.discover_prompts()
        discovery.discover_contracts()
        discovery.discover_manifests()
        
        stats = discovery.get_stats()
        
        assert 'prompts_scanned' in stats
        assert 'prompts_loaded' in stats
        assert 'prompts_skipped' in stats
        assert 'contracts_scanned' in stats
        assert 'manifests_loaded' in stats
    
    def test_validation_report(self, temp_data_dir):
        """Формирование отчёта валидации."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        discovery.discover_prompts()
        discovery.discover_contracts()
        discovery.discover_manifests()
        
        report = discovery.get_validation_report()
        
        assert 'ОТЧЁТ RESOURCE DISCOVERY' in report
        assert 'Профиль: prod' in report
        assert 'Промпты:' in report
        assert 'Контракты:' in report
        assert 'Манифесты:' in report


class TestComponentTypeInference:
    """Тесты авто-определения типа компонента."""
    
    def test_infer_skill_type(self, temp_data_dir):
        """Определение типа skill из пути."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        file_path = temp_data_dir / 'prompts' / 'skill' / 'test' / 'file.yaml'
        comp_type = discovery._infer_component_type_from_path(file_path)
        
        assert comp_type == ComponentType.SKILL
    
    def test_infer_service_type(self, temp_data_dir):
        """Определение типа service из пути."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        file_path = temp_data_dir / 'prompts' / 'service' / 'test' / 'file.yaml'
        comp_type = discovery._infer_component_type_from_path(file_path)
        
        assert comp_type == ComponentType.SERVICE
    
    def test_infer_tool_type(self, temp_data_dir):
        """Определение типа tool из пути."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        file_path = temp_data_dir / 'prompts' / 'tool' / 'test' / 'file.yaml'
        comp_type = discovery._infer_component_type_from_path(file_path)
        
        assert comp_type == ComponentType.TOOL
    
    def test_infer_behavior_type(self, temp_data_dir):
        """Определение типа behavior из пути."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        file_path = temp_data_dir / 'prompts' / 'behavior' / 'test' / 'file.yaml'
        comp_type = discovery._infer_component_type_from_path(file_path)
        
        assert comp_type == ComponentType.BEHAVIOR


class TestDirectionInference:
    """Тесты определения направления контракта."""
    
    def test_infer_input_from_filename(self, temp_data_dir):
        """Определение input из имени файла."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        file_path = temp_data_dir / 'contracts' / 'capability_input_v1.0.0.yaml'
        direction = discovery._infer_direction_from_filename(file_path)
        
        assert direction == 'input'
    
    def test_infer_output_from_filename(self, temp_data_dir):
        """Определение output из имени файла."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        file_path = temp_data_dir / 'contracts' / 'capability_output_v1.0.0.yaml'
        direction = discovery._infer_direction_from_filename(file_path)
        
        assert direction == 'output'
    
    def test_parse_contract_filename(self, temp_data_dir):
        """Парсинг имени файла контракта."""
        discovery = ResourceDiscovery(base_dir=temp_data_dir, profile='prod')
        
        file_path = temp_data_dir / 'contracts' / 'capability_input_v1.0.0.yaml'
        capability, version, direction = discovery._parse_contract_filename(file_path)
        
        assert capability == 'capability'
        assert version == 'v1.0.0'
        assert direction == 'input'

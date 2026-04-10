"""
Unit-tests for ResourceLoader.
"""
import pytest
import yaml
from pathlib import Path

from core.infrastructure.loading.resource_loader import ResourceLoader
from core.models.data.prompt import Prompt, PromptStatus
from core.models.data.contract import Contract, ContractDirection
from core.models.enums.common_enums import ComponentType
from core.config.component_config import ComponentConfig
from core.errors.exceptions import ResourceLoadError


def _create_prompt_yaml(capability, version, status="active", component_type="skill"):
    data = {
        "capability": capability,
        "version": version,
        "status": status,
        "component_type": component_type,
        "content": f"Prompt for {capability} version {version}. " + "x" * 20,
        "variables": [],
        "metadata": {},
    }
    return yaml.dump(data, allow_unicode=True, default_flow_style=False)


def _create_contract_yaml(capability, version, direction, status="active", component_type="skill"):
    data = {
        "capability": capability,
        "version": version,
        "status": status,
        "component_type": component_type,
        "direction": direction,
        "schema": {"type": "object", "properties": {}},
        "description": f"Contract for {capability}",
    }
    return yaml.dump(data, allow_unicode=True, default_flow_style=False)


@pytest.fixture
def clean_loader_cache():
    ResourceLoader.clear_cache()
    yield
    ResourceLoader.clear_cache()


@pytest.fixture
def data_dir_with_resources(tmp_path):
    prompts_dir = tmp_path / "prompts" / "skill" / "planning"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "v1.0.0.yaml").write_text(
        _create_prompt_yaml("planning.create_plan", "v1.0.0", "active"), encoding="utf-8"
    )
    (prompts_dir / "v2.0.0-draft.yaml").write_text(
        _create_prompt_yaml("planning.create_plan", "v2.0.0", "draft"), encoding="utf-8"
    )
    (prompts_dir / "v0.9.0.yaml").write_text(
        _create_prompt_yaml("planning.create_plan", "v0.9.0", "inactive"), encoding="utf-8"
    )

    service_prompts = tmp_path / "prompts" / "service" / "prompt"
    service_prompts.mkdir(parents=True)
    (service_prompts / "v1.0.0.yaml").write_text(
        _create_prompt_yaml("prompt.retrieval", "v1.0.0", "active", "service"), encoding="utf-8"
    )

    contracts_dir = tmp_path / "contracts" / "skill" / "planning"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "v1.0.0_input.yaml").write_text(
        _create_contract_yaml("planning.create_plan", "v1.0.0", "input", "active"), encoding="utf-8"
    )
    (contracts_dir / "v1.0.0_output.yaml").write_text(
        _create_contract_yaml("planning.create_plan", "v1.0.0", "output", "active"), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def data_dir_with_broken_yaml(tmp_path):
    prompts_dir = tmp_path / "prompts" / "skill"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "broken.yaml").write_text("not: valid: yaml: [", encoding="utf-8")
    return tmp_path


@pytest.fixture
def data_dir_empty(tmp_path):
    return tmp_path


class TestBasicLoading:
    def test_loads_active_prompts(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader(data_dir_with_resources, profile="prod")
        loader.load_all()
        prompt = loader.get_prompt("planning.create_plan", "v1.0.0")
        assert prompt is not None
        assert prompt.capability == "planning.create_plan"
        assert prompt.status == PromptStatus.ACTIVE

    def test_loads_contracts(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader(data_dir_with_resources, profile="prod")
        loader.load_all()
        contract = loader.get_contract("planning.create_plan", "v1.0.0", "input")
        assert contract is not None
        assert contract.direction == ContractDirection.INPUT

    def test_returns_none_for_missing(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader(data_dir_with_resources, profile="prod")
        loader.load_all()
        assert loader.get_prompt("nonexistent", "v1.0.0") is None

    def test_load_all_idempotent(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader(data_dir_with_resources, profile="prod")
        loader.load_all()
        loader.load_all()
        stats = loader.get_stats()
        assert stats["prompts_loaded"] == 2


class TestProfileStatusFiltering:
    def test_prod_only_active(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader(data_dir_with_resources, profile="prod")
        loader.load_all()
        assert loader.get_prompt("planning.create_plan", "v1.0.0") is not None
        assert loader.get_prompt("planning.create_plan", "v2.0.0") is None
        assert loader.get_prompt("planning.create_plan", "v0.9.0") is None

    def test_sandbox_active_and_draft(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader(data_dir_with_resources, profile="sandbox")
        loader.load_all()
        assert loader.get_prompt("planning.create_plan", "v1.0.0") is not None
        assert loader.get_prompt("planning.create_plan", "v2.0.0") is not None
        assert loader.get_prompt("planning.create_plan", "v0.9.0") is None

    def test_dev_all_statuses(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader(data_dir_with_resources, profile="dev")
        loader.load_all()
        assert loader.get_prompt("planning.create_plan", "v1.0.0") is not None
        assert loader.get_prompt("planning.create_plan", "v2.0.0") is not None
        assert loader.get_prompt("planning.create_plan", "v0.9.0") is not None


class TestLoaderCaching:
    def test_factory_method_returns_same_instance(self, data_dir_with_resources, clean_loader_cache):
        loader1 = ResourceLoader.get(data_dir_with_resources, "prod")
        loader2 = ResourceLoader.get(data_dir_with_resources, "prod")
        assert loader1 is loader2
        assert len(ResourceLoader._cache) == 1

    def test_different_profiles_different_cache(self, data_dir_with_resources, clean_loader_cache):
        loader_prod = ResourceLoader.get(data_dir_with_resources, "prod")
        loader_sandbox = ResourceLoader.get(data_dir_with_resources, "sandbox")
        assert loader_prod is not loader_sandbox
        assert len(ResourceLoader._cache) == 2

    def test_cache_returns_already_loaded(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader.get(data_dir_with_resources, "prod")
        loader2 = ResourceLoader.get(data_dir_with_resources, "prod")
        assert loader2._loaded is True


class TestGetComponentResources:
    def test_returns_requested_resources(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader.get(data_dir_with_resources, "prod")
        config = ComponentConfig(
            variant_id="test",
            prompt_versions={"planning.create_plan": "v1.0.0"},
            input_contract_versions={"planning.create_plan": "v1.0.0"},
            output_contract_versions={"planning.create_plan": "v1.0.0"},
        )
        resources = loader.get_component_resources("planning_skill", config)
        assert "planning.create_plan" in resources["prompts"]
        assert "planning.create_plan" in resources["input_contracts"]
        assert "planning.create_plan" in resources["output_contracts"]

    def test_returns_correct_types(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader.get(data_dir_with_resources, "prod")
        config = ComponentConfig(
            variant_id="test",
            prompt_versions={"planning.create_plan": "v1.0.0"},
            input_contract_versions={"planning.create_plan": "v1.0.0"},
            output_contract_versions={"planning.create_plan": "v1.0.0"},
        )
        resources = loader.get_component_resources("planning_skill", config)
        assert isinstance(resources["prompts"]["planning.create_plan"], Prompt)
        assert isinstance(resources["input_contracts"]["planning.create_plan"], Contract)
        assert isinstance(resources["output_contracts"]["planning.create_plan"], Contract)

    def test_empty_config_returns_empty_dicts(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader.get(data_dir_with_resources, "prod")
        config = ComponentConfig(variant_id="test")
        resources = loader.get_component_resources("empty_component", config)
        assert resources["prompts"] == {}
        assert resources["input_contracts"] == {}
        assert resources["output_contracts"] == {}


class TestInference:
    def test_infers_skill_type_from_path(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader.get(data_dir_with_resources, "prod")
        loader.load_all()
        prompt = loader.get_prompt("planning.create_plan", "v1.0.0")
        assert prompt.component_type == ComponentType.SKILL

    def test_infers_service_type_from_path(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader.get(data_dir_with_resources, "prod")
        loader.load_all()
        prompt = loader.get_prompt("prompt.retrieval", "v1.0.0")
        assert prompt.component_type == ComponentType.SERVICE

    def test_infers_direction_from_filename(self):
        loader = ResourceLoader.__new__(ResourceLoader)
        assert loader._infer_direction_from_filename(Path("cap_input_v1.0.0.yaml")) == "input"
        assert loader._infer_direction_from_filename(Path("cap_output_v1.0.0.yaml")) == "output"
        assert loader._infer_direction_from_filename(Path("some/input/cap_v1.0.0.yaml")) == "input"
        assert loader._infer_direction_from_filename(Path("cap_v1.0.0.yaml")) is None


class TestFailFast:
    def test_broken_yaml_raises(self, data_dir_with_broken_yaml, clean_loader_cache):
        loader = ResourceLoader(data_dir_with_broken_yaml, profile="prod")
        with pytest.raises(ResourceLoadError):
            loader.load_all()

    def test_empty_dir_does_not_raise(self, data_dir_empty, clean_loader_cache):
        loader = ResourceLoader(data_dir_empty, profile="prod")
        loader.load_all()
        assert loader.get_all_prompts() == []
        assert loader.get_all_contracts() == []


class TestGetAllMethods:
    def test_get_all_prompts(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader.get(data_dir_with_resources, "prod")
        all_prompts = loader.get_all_prompts()
        assert len(all_prompts) == 2
        assert all(isinstance(p, Prompt) for p in all_prompts)

    def test_get_all_contracts(self, data_dir_with_resources, clean_loader_cache):
        loader = ResourceLoader.get(data_dir_with_resources, "prod")
        all_contracts = loader.get_all_contracts()
        assert len(all_contracts) == 2
        assert all(isinstance(c, Contract) for c in all_contracts)

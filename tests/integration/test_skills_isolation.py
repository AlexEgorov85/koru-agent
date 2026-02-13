"""
Тест для проверки изоляции навыков с новой архитектурой.
"""
import asyncio
from core.application.context.application_context import ApplicationContext
from core.config.models import AgentConfig, SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.skills.base_skill import BaseSkill
from core.models.capability import Capability
from core.config.component_config import ComponentConfig


class TestSkill(BaseSkill):
    """Тестовый навык для проверки изоляции."""
    
    def __init__(self, name: str, application_context, component_config=None):
        super().__init__(name=name, application_context=application_context, component_config=component_config)
    
    def get_capabilities(self):
        return [
            Capability(
                name="test.skill_action",
                description="Тестовое действие",
                skill_name=self.name,
                meta={
                    "contract_version": "v1.0.0",
                    "prompt_version": "v1.0.0"
                }
            )
        ]
    
    async def execute(self, capability, parameters, context):
        # Просто возвращаем параметры для тестирования
        return {"result": "executed", "params": parameters}


async def test_skills_isolation():
    """Тест изоляции навыков."""
    # Создаём системную конфигурацию
    system_config = SystemConfig()
    
    # Создаём инфраструктурный контекст
    infrastructure_context = InfrastructureContext(config=system_config)
    await infrastructure_context.initialize()
    
    # Создаём 2 прикладных контекста с РАЗНЫМИ версиями
    config1 = AgentConfig(
        agent_id="test_agent_1",
        prompt_versions={"test.skill_action": "v1.0.0"},
        input_contract_versions={"test.skill_action": "v1.0.0"},
        output_contract_versions={"test.skill_action": "v1.0.0"}
    )
    ctx1 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=config1
    )
    await ctx1.initialize()
    
    config2 = AgentConfig(
        agent_id="test_agent_2", 
        prompt_versions={"test.skill_action": "v2.0.0"},
        input_contract_versions={"test.skill_action": "v2.0.0"},
        output_contract_versions={"test.skill_action": "v2.0.0"}
    )
    ctx2 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=config2
    )
    await ctx2.initialize()
    
    # Создаем компонентные конфигурации для навыков
    component_config1 = ComponentConfig(
        variant_id="test_skill_v1",
        prompt_versions={"test.skill_action": "v1.0.0"},
        input_contract_versions={"test.skill_action": "v1.0.0"},
        output_contract_versions={"test.skill_action": "v1.0.0"}
    )
    
    component_config2 = ComponentConfig(
        variant_id="test_skill_v2",
        prompt_versions={"test.skill_action": "v2.0.0"},
        input_contract_versions={"test.skill_action": "v2.0.0"},
        output_contract_versions={"test.skill_action": "v2.0.0"}
    )
    
    # Создаем навыки с разными конфигурациями
    skill1 = TestSkill(name="test_skill_1", application_context=ctx1, component_config=component_config1)
    await skill1.initialize()
    
    skill2 = TestSkill(name="test_skill_2", application_context=ctx2, component_config=component_config2)
    await skill2.initialize()
    
    # Проверяем, что у навыков изолированные кэши
    print(f"Skill1 cached prompts: {list(skill1._cached_prompts.keys())}")
    print(f"Skill2 cached prompts: {list(skill2._cached_prompts.keys())}")
    
    # Проверяем, что кэши разные объекты
    cache1_prompts_id = id(skill1._cached_prompts)
    cache2_prompts_id = id(skill2._cached_prompts)
    cache1_input_contracts_id = id(skill1._cached_input_contracts)
    cache2_input_contracts_id = id(skill2._cached_input_contracts)
    
    print(f"Prompt caches are different: {cache1_prompts_id != cache2_prompts_id}")
    print(f"Input contract caches are different: {cache1_input_contracts_id != cache2_input_contracts_id}")
    
    # Проверяем, что навыки изолированы
    isolation_ok = (
        cache1_prompts_id != cache2_prompts_id and
        cache1_input_contracts_id != cache2_input_contracts_id
    )
    
    print(f"Skills isolation OK: {isolation_ok}")
    
    return isolation_ok


if __name__ == "__main__":
    asyncio.run(test_skills_isolation())
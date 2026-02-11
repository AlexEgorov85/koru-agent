"""
Простой тест для проверки архитектуры кэширования
"""
import asyncio
from unittest.mock import Mock, AsyncMock

from core.config.agent_config import AgentConfig
from core.skills.base_skill import BaseSkill
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus


class MockPromptService:
    """Мок-сервис для промптов"""
    async def get_prompt(self, capability_name: str, version: str = None, **kwargs):
        result = f"Mocked prompt for {capability_name} v{version or 'latest'}"
        print(f"get_prompt called with: {capability_name}, {version} -> {result}")
        return result
    
    def scan_active_prompts(self):
        return {
            "test.capability": {"version": "v1.0", "status": "active"},
            "another.capability": {"version": "v2.0", "status": "active"}
        }


class MockSystemContext:
    """Мок-системный контекст"""
    def __init__(self):
        self.logger = Mock()
        self.resources = {
            "prompt_service": MockPromptService(),
            "contract_service": None
        }
    
    def get_resource(self, resource_name: str):
        return self.resources.get(resource_name)


class TestSkill(BaseSkill):
    """Тестовый навык для проверки кэширования"""
    
    def get_capabilities(self):
        return [
            Capability(
                name="test.capability",
                description="Test capability",
                parameters_schema={"type": "object", "properties": {}},
                skill_name="TestSkill"
            )
        ]
    
    async def execute(self, capability, parameters, context):
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"test": "result"},
            observation_item_id="test_id",
            summary="Test execution completed",
            error=None
        )


async def debug_test():
    print("=== Отладочный тест ===")
    
    system_context = MockSystemContext()
    skill = TestSkill(name="test_skill", system_context=system_context)
    
    # Проверим, что возвращает get_capability_names
    cap_names = skill.get_capability_names()
    print(f"get_capability_names() вернул: {cap_names}")
    
    # Создаем конфигурацию с тестовыми версиями
    agent_config = AgentConfig(
        prompt_versions={"test.capability": "v1.0"}
    )
    
    print(f"agent_config.prompt_versions: {agent_config.prompt_versions}")
    
    # Инициализируем навык
    print("Вызываем skill.initialize...")
    success = await skill.initialize(agent_config)
    print(f"skill.initialize вернул: {success}")
    
    print(f"Кэш промптов после инициализации: {skill._cached_prompts}")
    
    # Проверяем, что промпт закэширован
    print("Получаем промпт из кэша...")
    cached_prompt = skill.get_prompt("test.capability")
    print(f"skill.get_prompt('test.capability') вернул: {cached_prompt}")
    
    # Проверим, соответствует ли он ожидаемому значению
    expected = "Mocked prompt for test.capability v1.0"
    print(f"Ожидаем: {expected}")
    print(f"Соответствует: {cached_prompt == expected}")


if __name__ == "__main__":
    asyncio.run(debug_test())
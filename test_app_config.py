import asyncio
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.config import get_config

async def main():
    config = get_config('prod', 'data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app = AppConfig.from_discovery('prod', 'data', infra.resource_discovery)
    
    print('=== SERVICE CONFIGS ===')
    for name, cfg in app.service_configs.items():
        print(f'  {name}: prompt_versions={getattr(cfg, "prompt_versions", "N/A")}')
    
    print('=== SKILL CONFIGS ===')
    for name, cfg in app.skill_configs.items():
        print(f'  {name}: prompt_versions={getattr(cfg, "prompt_versions", "N/A")}')
    
    print('=== TOOL CONFIGS ===')
    for name, cfg in app.tool_configs.items():
        print(f'  {name}: prompt_versions={getattr(cfg, "prompt_versions", "N/A")}')
    
    await infra.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
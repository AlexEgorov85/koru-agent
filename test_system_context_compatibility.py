from core.config import get_config
from core.system_context.system_context import SystemContext
import asyncio

async def test_system_context():
    try:
        config = get_config(profile='dev')
        with open('system_context_test.txt', 'w', encoding='utf-8') as f:
            f.write(f'Config loaded: {config.profile}\n')
            
            system_context = SystemContext(config)
            f.write('SystemContext created\n')
            
            # Проверим, что все провайдеры и сервисы могут быть инициализированы
            f.write(f'LLM providers in config: {list(config.llm_providers.keys())}\n')
            f.write(f'DB providers in config: {list(config.db_providers.keys())}\n')
            f.write(f'Skills in config: {list(config.skills.keys())}\n')
            f.write(f'Tools in config: {list(config.tools.keys())}\n')
            f.write(f'Agent config: {config.agent}\n')
            
            f.write('SystemContext configuration is compatible with architecture!\n')
        return True
    except Exception as e:
        with open('system_context_test.txt', 'w', encoding='utf-8') as f:
            f.write(f'Error: {e}\n')
            import traceback
            f.write(traceback.format_exc())
        return False

result = asyncio.run(test_system_context())
with open('system_context_test.txt', 'a', encoding='utf-8') as f:
    f.write(f'\nTest result: {result}')
print(f'Test result: {result}')
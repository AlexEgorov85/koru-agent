from core.config import get_config

try:
    config = get_config(profile='dev')
    with open('agent_config_test.txt', 'w', encoding='utf-8') as f:
        f.write('Config loaded successfully\n')
        f.write(f'Has agent_config: {hasattr(config, "agent_config")}\n')
        if hasattr(config, 'agent_config'):
            f.write(f'Agent config: {config.agent_config}\n')
            f.write(f'Agent config type: {type(config.agent_config)}\n')
        else:
            f.write('No agent_config attribute found\n')
            # Попробуем получить все атрибуты
            attrs = [attr for attr in dir(config) if not attr.startswith("_")]
            f.write(f'Config attributes: {attrs}\n')
    print("Agent config test completed")
except Exception as e:
    with open('agent_config_test.txt', 'w', encoding='utf-8') as f:
        f.write(f'Error: {e}\n')
        import traceback
        f.write(traceback.format_exc())
    print(f"Error: {e}")
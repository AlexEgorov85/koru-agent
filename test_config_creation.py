import yaml
from core.config.models import SystemConfig

config_dict = {
    'profile': 'dev',
    'debug': True,
    'log_level': 'DEBUG',
    'log_dir': 'logs/dev',
    'data_dir': 'data/dev',
    'llm_providers': {
        'default_llm': {
            'type_provider': 'llama_cpp',
            'model_name': 'qwen-4b',
            'enabled': True,
            'fallback_providers': [],
            'parameters': {
                'model_path': './models/test-model.gguf',
                'n_ctx': 2048,
                'n_gpu_layers': 0,
                'temperature': 0.2
            }
        }
    },
    'db_providers': {
        'default_db': {
            'type_provider': 'postgres',
            'enabled': True,
            'parameters': {
                'host': 'localhost',
                'port': 5432,
                'database': 'agent_dev',
                'username': 'postgres',
                'password': 'password'
            }
        }
    },
    'skills': {
        'planning': {
            'enabled': True,
            'parameters': {},
            'priority': 1
        },
        'book_library': {
            'enabled': True,
            'parameters': {
                'max_books_per_search': 10
            },
            'priority': 1
        }
    },
    'tools': {
        'SQLTool': {
            'enabled': True,
            'parameters': {},
            'dependencies': ['default_db']
        }
    },
    'agent': {
        'max_steps': 10,
        'temperature': 0.2,
        'default_strategy': 'react'
    },
    'security': {
        'secrets_path': None
    }
}

try:
    config = SystemConfig(**config_dict)
    with open('config_test_result.txt', 'w', encoding='utf-8') as f:
        f.write('Configuration loaded successfully!\n')
        f.write(f'Profile: {config.profile}\n')
        f.write(f'Debug: {config.debug}\n')
        f.write(f'LLM Providers: {list(config.llm_providers.keys())}\n')
        if 'default_llm' in config.llm_providers:
            llm = config.llm_providers['default_llm']
            f.write(f'LLM Model: {llm.model_name}\n')
            f.write(f'LLM Enabled: {llm.enabled}\n')
            f.write(f'LLM Parameters: {llm.parameters}\n')
        f.write(f'DB Providers: {list(config.db_providers.keys())}\n')
        f.write(f'Skills: {list(config.skills.keys())}\n')
        f.write(f'Tools: {list(config.tools.keys())}\n')
        f.write(f'Agent config: {config.agent}\n')
    print("SUCCESS: Configuration validated!")
except Exception as e:
    with open('config_test_result.txt', 'w', encoding='utf-8') as f:
        f.write(f'Error creating config: {e}\n')
        import traceback
        f.write(traceback.format_exc())
    print(f"ERROR: {e}")
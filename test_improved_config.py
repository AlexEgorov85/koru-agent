from core.config import get_config

try:
    config = get_config(profile='dev')
    with open('improved_config_result.txt', 'w', encoding='utf-8') as f:
        f.write('SUCCESS: Config loaded!\n')
        f.write(f'Profile: {config.profile}\n')
        f.write(f'Debug: {config.debug}\n')
        f.write(f'Log level: {config.log_level}\n')
        f.write(f'LLM providers: {list(config.llm_providers.keys())}\n')
        if 'default_llm' in config.llm_providers:
            llm = config.llm_providers['default_llm']
            f.write(f'LLM model: {llm.model_name}\n')
            f.write(f'LLM enabled: {llm.enabled}\n')
            f.write(f'LLM params: {llm.parameters}\n')
        f.write(f'DB providers: {list(config.db_providers.keys())}\n')
        if 'default_db' in config.db_providers:
            db = config.db_providers['default_db']
            f.write(f'DB enabled: {db.enabled}\n')
            f.write(f'DB params: {db.parameters}\n')
        f.write(f'Skills: {list(config.skills.keys())}\n')
        if 'planning' in config.skills:
            skill = config.skills['planning']
            f.write(f'Planning skill enabled: {skill.enabled}\n')
            f.write(f'Planning skill priority: {skill.priority}\n')
        f.write(f'Tools: {list(config.tools.keys())}\n')
        f.write(f'Agent config: {config.agent}\n')
        f.write(f'Security path: {config.security.secrets_path}\n')
    print("SUCCESS: Improved config validated!")
except Exception as e:
    with open('improved_config_result.txt', 'w', encoding='utf-8') as f:
        f.write(f'ERROR: {e}\n')
        import traceback
        f.write(traceback.format_exc())
    print(f"ERROR: {e}")
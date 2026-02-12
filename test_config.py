import logging
logging.basicConfig(level=logging.DEBUG)

from core.config.config_loader import ConfigLoader

print("Testing direct config loading...")

try:
    loader = ConfigLoader(profile='dev')
    print(f"Config dir: {loader.config_dir}")
    print(f"Profile: {loader.profile}")
    
    # Попробуем загрузить базовую конфигурацию
    base_config = loader._load_base_config()
    print(f"Base config loaded: {bool(base_config)}")
    
    # Попробуем загрузить профильную конфигурацию
    profile_config = loader._load_profile_config()
    print(f"Profile config loaded: {bool(profile_config)}")
    print(f"Profile config content: {profile_config}")
    
    # Загрузим полную конфигурацию
    config = loader.load()
    print(f"Final config profile: {config.profile}")
    print(f"Final config debug: {config.debug}")
    print(f"LLM providers: {list(config.llm_providers.keys())}")
    
except Exception as e:
    print(f"Exception occurred: {e}")
    import traceback
    traceback.print_exc()
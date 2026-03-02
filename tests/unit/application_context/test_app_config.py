import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.app_config import AppConfig

# Тестируем загрузку AppConfig через авто-обнаружение
try:
    app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
    print(f"AppConfig успешно загружен через discovery")
    print(f"Profile: {app_config.profile}")
    print(f"Config ID: {app_config.config_id}")
    print(f"Prompt versions: {app_config.prompt_versions}")
    print(f"Input contract versions: {app_config.input_contract_versions}")
    print(f"Output contract versions: {app_config.output_contract_versions}")
    print(f"Side effects enabled: {app_config.side_effects_enabled}")
    print(f"Skills loaded: {list(app_config.skill_configs.keys())}")
except Exception as e:
    print(f"Ошибка при загрузке AppConfig через discovery: {e}")
    import traceback
    traceback.print_exc()

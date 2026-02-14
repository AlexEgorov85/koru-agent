import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.app_config import AppConfig

# Тестируем загрузку AppConfig из реестра
try:
    app_config = AppConfig.from_registry(profile="prod")
    print(f"AppConfig успешно загружен из реестра")
    print(f"Profile: {app_config.profile}")
    print(f"Prompt versions: {app_config.prompt_versions}")
    print(f"Input contract versions: {app_config.input_contract_versions}")
    print(f"Output contract versions: {app_config.output_contract_versions}")
    print(f"Side effects enabled: {app_config.side_effects_enabled}")
except Exception as e:
    print(f"Ошибка при загрузке AppConfig из реестра: {e}")
    import traceback
    traceback.print_exc()
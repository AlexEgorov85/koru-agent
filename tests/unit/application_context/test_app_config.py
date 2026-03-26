import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.app_config import AppConfig

# Тестируем загрузку AppConfig через авто-обнаружение
try:
    app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
except Exception as e:
    import traceback
    traceback.print_exc()

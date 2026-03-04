from core.config.app_config import AppConfig
from pathlib import Path

cfg = AppConfig.from_discovery(profile='prod', data_dir='data')

with open('test_appconfig.txt', 'w', encoding='utf-8') as f:
    f.write('tool_configs:\n')
    for name, config in cfg.tool_configs.items():
        f.write(f'  {name}: input={config.input_contract_versions}, output={config.output_contract_versions}\n')
    
    f.write('\nskill_configs:\n')
    for name, config in cfg.skill_configs.items():
        f.write(f'  {name}: input={config.input_contract_versions}, output={config.output_contract_versions}\n')

from core.config.app_config import AppConfig

cfg = AppConfig.from_discovery(profile='prod', data_dir='data')

with open('test_behavior.txt', 'w', encoding='utf-8') as f:
    f.write('behavior_configs:\n')
    for name, config in cfg.behavior_configs.items():
        f.write(f'  {name}: input={config.input_contract_versions}, output={config.output_contract_versions}\n')

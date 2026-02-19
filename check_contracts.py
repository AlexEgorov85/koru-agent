from core.config.app_config import AppConfig
app_config = AppConfig.from_registry(profile='prod')
print('input_contract_versions:', app_config.input_contract_versions, flush=True)
print('output_contract_versions:', app_config.output_contract_versions, flush=True)

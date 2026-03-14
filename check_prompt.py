from core.infrastructure.discovery.resource_discovery import ResourceDiscovery

d = ResourceDiscovery('data', 'dev')
p = d._parse_prompt_file(r'data\prompts\service\sql_generation\sql_generation.generate_query.system_v1.0.0.yaml')
print(f'✅ Промпт загружен: {p.capability}')
print(f'📝 Переменные: {[v.name for v in p.variables]}')

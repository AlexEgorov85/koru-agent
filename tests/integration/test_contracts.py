from core.infrastructure.discovery.resource_discovery import ResourceDiscovery
from pathlib import Path

discovery = ResourceDiscovery(base_dir=Path('data'), profile='prod')
contracts = discovery.discover_contracts()

with open('test_output.txt', 'w', encoding='utf-8') as f:
    f.write(f'Всего контрактов: {len(contracts)}\n')
    for c in contracts:
        f.write(f'  {c.capability}@{c.version} ({c.component_type.value}) - {c.direction.value}\n')

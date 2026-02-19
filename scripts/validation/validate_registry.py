import yaml
with open('registry.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
print('[SUCCESS] Registry.yaml is valid YAML')
print(f'Profile: {data.get("profile", "unknown")}')
print(f'Services: {len(data.get("services", {}))}')
print(f'Skills: {len(data.get("skills", {}))}')
print(f'Tools: {len(data.get("tools", {}))}')
print(f'Behaviors: {len(data.get("behaviors", {}))}')
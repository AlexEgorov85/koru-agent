import yaml

with open('c:/Users/Р В РЎвЂ™Р В Р’В»Р В Р’ВµР В РЎвЂќР РЋР С“Р В Р’ВµР В РІвЂћвЂ“/Documents/WORK/Agent_v5/registry.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Check if 'behavior' key exists in capability_types
if 'capability_types' in data and 'behavior' in data['capability_types']:
    print(f'behavior capability type found: {data["capability_types"]["behavior"]}')
else:
    print('behavior capability type NOT FOUND')
    print('Available capability types:')
    for k, v in data.get('capability_types', {}).items():
        print(f'  {k}: {v}')
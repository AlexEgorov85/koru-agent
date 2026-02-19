import yaml

# Test if the registry file can be parsed correctly
with open('c:/Users/Алексей/Documents/WORK/Agent_v5/registry.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

print("Registry loaded successfully")
print("capability_types section:")
if 'capability_types' in data:
    print(f"  Found {len(data['capability_types'])} capability types")
    for cap, typ in data['capability_types'].items():
        if 'behavior' in cap:
            print(f"  {cap}: {typ}")
else:
    print("  No capability_types section found")
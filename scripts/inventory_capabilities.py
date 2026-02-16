#!/usr/bin/env python3
"""
Inventory script to identify all existing capabilities in the system.
"""
import yaml
from pathlib import Path
import os

# Temporarily disable qwenignore for data directory
os.environ['QWENIGNORE_DISABLED'] = '1'

def main():
    print("=== Inventory of Existing Capabilities ===\n")
    
    # Load registry.yaml
    registry_path = Path("registry.yaml")
    if not registry_path.exists():
        print(f"ERROR: {registry_path} not found")
        return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = yaml.safe_load(f)
    
    capabilities = set()
    
    # From active prompts
    for cap in registry.get("active_prompts", {}).keys():
        capabilities.add(cap)
    
    # From active contracts
    for cap_dir in registry.get("active_contracts", {}).keys():
        cap = cap_dir.rsplit(".", 1)[0]  # "planning.create_plan.input" → "planning.create_plan"
        capabilities.add(cap)
    
    # From component configurations
    for section in ['services', 'skills', 'tools', 'strategies', 'behaviors']:
        if section in registry:
            for comp_name, comp_config in registry[section].items():
                # Check for prompt versions
                if 'prompt_versions' in comp_config:
                    for cap in comp_config['prompt_versions'].keys():
                        capabilities.add(cap)
                
                # Check for input contract versions
                if 'input_contract_versions' in comp_config:
                    for cap_dir in comp_config['input_contract_versions'].keys():
                        cap = cap_dir.rsplit(".", 1)[0]
                        capabilities.add(cap)
                
                # Check for output contract versions
                if 'output_contract_versions' in comp_config:
                    for cap_dir in comp_config['output_contract_versions'].keys():
                        cap = cap_dir.rsplit(".", 1)[0]
                        capabilities.add(cap)
    
    # Scan data/prompts directory for additional capabilities
    data_dir = Path("data") if Path("data").exists() else Path(".")
    prompts_dir = data_dir / "prompts"
    
    if prompts_dir.exists():
        for file in prompts_dir.rglob("*.yaml"):
            if file.is_file():
                stem = file.stem
                # Extract capability from filename like "planning.create_plan_v1.0.0.yaml"
                parts = stem.split('_v')
                if len(parts) >= 2:
                    cap = parts[0]  # "planning.create_plan_v1.0.0" → "planning.create_plan"
                    capabilities.add(cap)
    
    print("Found capabilities:")
    for cap in sorted(capabilities):
        print(f"  - {cap}")
    
    print(f"\nTotal capabilities found: {len(capabilities)}")
    
    # Also save to a file for reference
    with open("capability_inventory.txt", "w", encoding="utf-8") as f:
        f.write("Capability Inventory\n")
        f.write("=" * 20 + "\n")
        for cap in sorted(capabilities):
            f.write(f"- {cap}\n")
    
    print("\nInventory saved to capability_inventory.txt")

if __name__ == "__main__":
    main()
"""
Скрипт для обновления registry.yaml с новыми .user/.system промптами.
"""
import yaml
from pathlib import Path

REGISTRY_FILE = Path("data/registry.yaml")
PROMPTS_DIR = Path("data/prompts")


def discover_prompts():
    """Сканирует промпты и возвращает словарь {capability: version}."""
    prompts = {}
    for f in PROMPTS_DIR.rglob("*.yaml"):
        # Пропускаем system промпты - они добавляются отдельно
        if ".system_" in f.stem:
            continue
        
        # Извлекаем capability и version
        parts = f.stem.split("_v")
        if len(parts) != 2:
            continue
        
        capability = parts[0].replace(".user", "")  # Убираем .user
        version = f"v{parts[1]}"
        prompts[capability] = version
    
    return prompts


def update_registry():
    """Обновляет registry.yaml с новыми промптами."""
    # Загружаем registry
    with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
        registry = yaml.safe_load(f)
    
    # Обновляем каждый компонент
    for comp_type in ['behaviors', 'skills', 'services', 'tools']:
        if comp_type not in registry:
            continue
        
        components = registry[comp_type]
        for comp_name, comp_config in components.items():
            if 'prompt_versions' not in comp_config:
                continue
            
            old_versions = comp_config['prompt_versions']
            new_versions = {}
            
            # Для каждого capability добавляем .user и .system
            for cap, ver in old_versions.items():
                # Добавляем user версию
                user_cap = f"{cap}.user"
                new_versions[user_cap] = ver
                
                # Добавляем system версию если существует
                system_cap = f"{cap}.system"
                # Проверяем существует ли system промпт
                system_file = PROMPTS_DIR / comp_type.replace('s', '') / comp_name / f"{cap}.system_v1.0.0.yaml"
                if not system_file.exists():
                    # Пробуем другие пути
                    for base_dir in PROMPTS_DIR.rglob(f"{cap}.system_v1.0.0.yaml"):
                        system_file = base_dir
                        break
                
                if system_file.exists():
                    new_versions[system_cap] = ver
            
            comp_config['prompt_versions'] = new_versions
            print(f"[OK] {comp_name}: {len(old_versions)} -> {len(new_versions)} prompts")
    
    # Сохраняем registry
    with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(registry, f, allow_unicode=True, default_flow_style=False)
    
    print("\nRegistry updated!")


if __name__ == "__main__":
    update_registry()

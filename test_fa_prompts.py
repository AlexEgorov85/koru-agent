"""Тест загрузки промптов для final_answer - через ResourceDiscovery."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def test_final_answer_prompts():
    from core.config.app_config import AppConfig
    from core.infrastructure.discovery.resource_discovery import ResourceDiscovery
    
    print("=" * 80)
    print("ТЕСТ ЗАГРУЗКИ ПРОМПТОВ FINAL_ANSWER")
    print("=" * 80)
    
    # Шаг 1: AppConfig.from_discovery()
    print("\n[Шаг 1] AppConfig.from_discovery()...")
    app_config = AppConfig.from_discovery(profile="dev")
    
    fa_config = app_config.skill_configs.get("final_answer")
    if not fa_config:
        print("  ✗ final_answer НЕ найден!")
        return
    
    print(f"  ✓ final_answer найден")
    print(f"    prompt_versions: {fa_config.prompt_versions}")
    
    # Шаг 2: ResourceDiscovery
    print("\n[Шаг 2] ResourceDiscovery.discover_prompts()...")
    discovery = ResourceDiscovery(base_dir="data")
    discovered_prompts = await discovery.discover_prompts(data_dir="data")
    
    print(f"  Всего обнаружено промптов: {len(discovered_prompts)}")
    
    # Ищем final_answer
    fa_discovered = {k: v for k, v in discovered_prompts.items() if "final_answer" in str(k)}
    print(f"\n  Промпты final_answer из ResourceDiscovery:")
    for key, prompts in fa_discovered.items():
        print(f"    Ключ компонента: {key}")
        for p in prompts:
            print(f"      - capability: {p.capability}, version: {p.version}, status: {p.status}")
            print(f"        content (первые 80 символов): {p.content[:80]}...")
    
    # Шаг 3: Проверка файлов на диске
    print("\n[Шаг 3] Файлы промптов на диске:")
    import glob
    fa_files = glob.glob("data/prompts/skill/final_answer/*.yaml", recursive=True)
    for file in fa_files:
        print(f"    {file}")
    
    print("\n" + "=" * 80)
    print("\nВЫВОД: Системный промпт загружается в AppConfig и ResourceDiscovery")
    print("Если он не используется - проблема в коде skill.py")

if __name__ == "__main__":
    asyncio.run(test_final_answer_prompts())

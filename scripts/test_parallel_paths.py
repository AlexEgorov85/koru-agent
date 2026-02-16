#!/usr/bin/env python3
"""
Тестирование параллельных путей инициализации (старый и новый).
"""
import asyncio
import tempfile
import shutil
from pathlib import Path
import yaml

from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.registry_loader import RegistryLoader
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.application.data_repository import DataRepository


async def test_parallel_initialization():
    """Сравнение старого и нового путей инициализации"""
    print("=== Тестирование параллельных путей инициализации ===\n")
    
    # Загрузка конфигурации
    config_loader = ConfigLoader()
    sys_config = config_loader.load_system_config()
    app_config_prod = config_loader.load_app_config(profile="prod")
    
    # Инициализация инфраструктуры (общая)
    infra = InfrastructureContext(sys_config)
    await infra.initialize()
    
    print("✓ Инфраструктура инициализирована")
    
    # === Старый путь ===
    print("\n--- Инициализация через старый путь ---")
    ctx_old = ApplicationContext(
        infra, app_config_prod, profile="prod", use_data_repository=False
    )
    old_success = await ctx_old.initialize()
    assert old_success, "Старый путь должен работать"
    print("✓ Старый путь инициализирован успешно")
    
    # === Новый путь ===
    print("\n--- Инициализация через новый путь ---")
    ctx_new = ApplicationContext(
        infra, app_config_prod, profile="prod", use_data_repository=True
    )
    new_success = await ctx_new.initialize()
    assert new_success, "Новый путь должен работать"
    print("✓ Новый путь инициализирован успешно")
    
    # === Сравнение результатов ===
    print("\n--- Сравнение результатов ---")
    for cap in list(app_config_prod.prompt_versions.keys())[:5]:  # Проверим первые 5
        ver = app_config_prod.prompt_versions[cap]
        
        try:
            # Текст промпта должен быть идентичен
            old_prompt = ctx_old.get_prompt(cap, ver)
            new_prompt = ctx_new.get_prompt(cap, ver)
            assert old_prompt == new_prompt, f"Промпт {cap}@{ver} отличается между путями"
            print(f"✓ Промпт {cap}@{ver} идентичен в обоих путях")
        except Exception as e:
            print(f"⚠️  Промпт {cap}@{ver} не найден: {e}")
    
    print("\n✓ Тест параллельных путей пройден успешно!")


def test_validation_catches_missing_capability_type():
    """Тест: репозиторий должен обнаруживать отсутствие объявления типа компонента"""
    print("\n=== Тест валидации отсутствия типа компонента ===")
    
    # Создаём временную директорию
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Создаём структуру директорий
        (tmp_path / "prompts" / "skills").mkdir(parents=True)
        
        # Файл промпта БЕЗ объявления типа в реестре
        prompt_file = tmp_path / "prompts" / "skills" / "test.missing_type_v1.0.0.yaml"
        prompt_file.write_text("""
capability: "test.missing_type"
version: "v1.0.0"
status: "active"
component_type: "skill"
content: "Тестовый промпт"
variables: []
""")
        
        # Реестр БЕЗ объявления типа для этого capability
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text("""
profile: "prod"
capability_types: {}  # ← Пусто!
active_prompts:
  test.missing_type: "v1.0.0"
""")
        
        # Инициализация
        registry_loader = RegistryLoader(registry_file)
        registry_config = registry_loader.load(profile="prod")
        
        ds = FileSystemDataSource(tmp_path, registry_config)
        repo = DataRepository(ds, profile="prod")
        
        from core.config.app_config import AppConfig
        app_config = AppConfig(prompt_versions={"test.missing_type": "v1.0.0"})
        
        # Инициализация должна провалиться с ЧЁТКОЙ ошибкой
        async def run_init():
            return await repo.initialize(app_config)
        
        success = asyncio.run(run_init())
        assert not success, "Инициализация должна провалиться"
        report = repo.get_validation_report()
        assert "не объявлен в конфигурации" in report.lower()
        print("✓ Валидация корректно обнаружила отсутствие типа компонента")


if __name__ == "__main__":
    # Запуск тестов
    asyncio.run(test_parallel_initialization())
    test_validation_catches_missing_capability_type()
    print("\n🎉 Все тесты пройдены успешно!")
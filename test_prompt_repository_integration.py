#!/usr/bin/env python3
"""
Тест интеграции промтов с репозиторием
"""
import asyncio
from application.services.prompt_initializer import PromptInitializer
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository


async def test_prompt_repository_integration():
    """Тест интеграции промтов с репозиторием"""
    print("Тест интеграции промтов с репозиторием...")
    
    # Создаем репозиторий
    repository = InMemoryPromptRepository()
    
    # Создаем инициализатор
    initializer = PromptInitializer(repository)
    
    # Инициализируем промты
    await initializer.initialize_prompts()
    
    # Проверяем, что все промты были добавлены
    print("\nПроверка наличия промтов в репозитории:")
    
    # Проверяем промт для принятия решений LLM
    llm_decision_versions = []
    for version_id, version in repository._versions.items():
        if "llm_decision" in version.capability_name:
            llm_decision_versions.append(version)
            print(f"  - Найден промт для llm_decision: {version.id}, статус: {version.status}")
    
    assert len(llm_decision_versions) > 0, "Промт для llm_decision не найден"
    
    # Проверяем промты планирования
    planning_versions = []
    for version_id, version in repository._versions.items():
        if "planning." in version.capability_name:
            planning_versions.append(version)
            print(f"  - Найден промт для планирования: {version.capability_name}, статус: {version.status}")
    
    assert len(planning_versions) == 3, f"Ожидается 3 промта планирования, найдено: {len(planning_versions)}"
    
    # Проверяем, что все промты активны
    active_versions = [v for v in repository._versions.values() if v.status == "active"]
    print(f"\nНайдено активных версий: {len(active_versions)}")
    
    # Проверяем, что у всех промтов есть переменные шаблонов
    for version in repository._versions.values():
        print(f"  - Промт {version.capability_name} имеет переменные: {version.template_variables}")
        assert isinstance(version.template_variables, list), f"Переменные шаблона должны быть списком для {version.capability_name}"
    
    print("\nВсе тесты интеграции промтов с репозиторием пройдены!")


if __name__ == "__main__":
    asyncio.run(test_prompt_repository_integration())
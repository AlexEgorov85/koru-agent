from domain.models.prompt.prompt_version import PromptVersion, PromptRole
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from application.services.file_prompt_repository import FilePromptRepository


class PromptInitializer:
    """Инициализация промтов в репозитории"""
    
    def __init__(self, prompt_repository):
        self._repository = prompt_repository
    
    async def initialize_prompts(self):
        """Инициализация всех промтов в системе через загрузку из файлов"""
        print("Инициализация промтов через загрузку из файлов...")
        
        # Загружаем промты из файлов
        file_repo = FilePromptRepository(base_path="prompts")
        errors = file_repo.load_from_directory("prompts")
        if errors:
            print(f"Ошибки при загрузке промтов из файлов: {len(errors)}")
            for error in errors:
                print(f"  - {error}")
        else:
            print("Все промты успешно загружены из файлов")
        
        # Копируем все загруженные промты в целевой репозиторий
        # Сначала загружаем все промты в память, затем копируем их в целевой репозиторий
        all_versions = []
        for version in file_repo._version_lookup.values():
            all_versions.append(version)
        
        print(f"Найдено {len(all_versions)} версий промтов для инициализации")
        
        for version in all_versions:
            try:
                # Проверяем, поддерживает ли репозиторий сохранение версий
                if hasattr(self._repository, 'save_version'):
                    await self._repository.save_version(version)
                    print(f"  - Сохранена версия: {version.id} ({version.capability_name})")
            except Exception as e:
                print(f"  - Ошибка при сохранении версии {version.id}: {str(e)}")
        
        print("Инициализация промтов завершена!")
    
    def _extract_template_variables(self, content: str) -> list:
        """Извлечение переменных шаблона из содержимого промта"""
        import re
        # Ищем все переменные в формате {variable_name}
        pattern = r'\{([^}]+)\}'
        matches = re.findall(pattern, content)
        # Убираем дубликаты и возвращаем список
        return list(set([match.strip() for match in matches if match.strip()]))

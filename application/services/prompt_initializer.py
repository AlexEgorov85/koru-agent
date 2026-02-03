from domain.models.prompt.prompt_version import PromptVersion, PromptRole
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType


class PromptInitializer:
    """Инициализация промтов в репозитории"""
    
    def __init__(self, prompt_repository):
        self._repository = prompt_repository
    
    async def initialize_prompts(self):
        """Инициализация всех промтов в системе через синхронизацию из файлов"""
        # Теперь все промты синхронизируются из файлов через PromptFileSyncService
        # Этот метод остается для обратной совместимости и может использоваться
        # для инициализации любых других данных, если потребуется
        print("Инициализация промтов через синхронизацию из файлов")
        
        # Проверим, что репозиторий поддерживает синхронизацию из файлов
        # (через PromptFileSyncService, который вызывается отдельно)
        print("Промты будут синхронизированы из файлов в директории ./prompts")
        
        print("Инициализация завершена. Все промты синхронизируются из файлов.")
    
    def _extract_template_variables(self, content: str) -> list:
        """Извлечение переменных шаблона из содержимого промта"""
        import re
        # Ищем все переменные в формате {variable_name}
        pattern = r'\{([^}]+)\}'
        matches = re.findall(pattern, content)
        # Убираем дубликаты и возвращаем список
        return list(set([match.strip() for match in matches if match.strip()]))

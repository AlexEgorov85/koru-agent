import os
import yaml
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from domain.models.domain_type import DomainType
from domain.models.prompt.prompt_version import PromptVersion, VariableSchema
import logging

from domain.models.provider_type import LLMProviderType

class PromptLoadingError(Exception):
    """Исключение для ошибок загрузки промтов"""
    pass

class PromptLoader:
    """
    Загрузчик промтов из файловой системы.
    
    Поддерживает структуру:
    prompts/
    ├── {domain}/
    │   └── {capability}/
    │       ├── {role}/
    │       │   └── v{version}.md
    │       └── _index.yaml
    """
    
    def __init__(self, base_path: str = "prompts"):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        
    def load_all_prompts(self) -> Tuple[List[PromptVersion], List[str]]:
        """
        Загружает все промты из файловой системы.
        Поддерживает структуру: prompts/{domain}/{capability}/{role}/v{version}.md
        
        Returns:
            Tuple[List[PromptVersion], List[str]]: Кортеж из списка загруженных промтов и списка ошибок
        """
        if not self.base_path.exists():
            return [], [f"Директория {self.base_path} не существует"]
            
        prompt_versions = []
        errors = []
        
        # Рекурсивно пройтись по всем поддиректориям
        for domain_dir in self.base_path.iterdir():
            if not domain_dir.is_dir():
                continue
                
            for capability_dir in domain_dir.iterdir():
                if not capability_dir.is_dir():
                    continue
                    
                # Проверим, есть ли подкаталоги ролей (system, user, assistant, tool)
                role_dirs = [
                    subdir for subdir in capability_dir.iterdir() 
                    if subdir.is_dir() and subdir.name in ["system", "user", "assistant", "tool"]
                ]
                
                if role_dirs:
                    # Новая структура: capability_dir содержит подкаталоги ролей
                    for role_dir in role_dirs:
                        # Загрузить все версии из этого подкаталога роли
                        versions, version_errors = self._load_capability_versions_from_role_dir(
                            domain_dir.name, capability_dir.name, role_dir
                        )
                        prompt_versions.extend(versions)
                        errors.extend(version_errors)
                else:
                    # Старая структура: все файлы версий находятся прямо в capability_dir
                    versions, version_errors = self._load_capability_versions_from_dir(
                        domain_dir.name, capability_dir
                    )
                    prompt_versions.extend(versions)
                    errors.extend(version_errors)
                
        return prompt_versions, errors
    
    def _load_capability_versions_from_role_dir(
        self, 
        domain: str, 
        capability: str, 
        role_dir: Path
    ) -> Tuple[List[PromptVersion], List[str]]:
        """Загружает все версии для одной capability из подкаталога роли"""
        versions = []
        errors = []
        
        for file_path in role_dir.glob("v*.md"):
            try:
                version = self._load_prompt_version(domain, capability, role_dir.name, file_path)
                if version:
                    versions.append(version)
            except Exception as e:
                errors.append(f"Ошибка загрузки промта из {file_path}: {str(e)}")
                
        return versions, errors
    
    def _load_capability_versions_from_dir(
        self, 
        domain: str, 
        capability_dir: Path
    ) -> Tuple[List[PromptVersion], List[str]]:
        """Загружает все версии для одной capability из директории"""
        # Извлекаем capability_name из имени директории
        capability = capability_dir.name
        versions = []
        errors = []
        
        for file_path in capability_dir.glob("v*.md"):
            try:
                version = self._load_prompt_version_from_legacy_path(domain, capability, file_path)
                if version:
                    versions.append(version)
            except Exception as e:
                errors.append(f"Ошибка загрузки промта из {file_path}: {str(e)}")
                
        return versions, errors
    
    def _load_prompt_version(
        self, 
        domain: str, 
        capability: str, 
        role: str, 
        file_path: Path
    ) -> Optional[PromptVersion]:
        """Загружает одну версию промта из файла в новой структуре (с ролью в пути)"""
        content = file_path.read_text(encoding='utf-8')
        
        # Извлечь frontmatter (метаданные) из Markdown файла
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if not frontmatter_match:
            raise PromptLoadingError(f"Файл {file_path} не содержит корректного frontmatter")
        
        yaml_str, prompt_content = frontmatter_match.groups()
        
        try:
            metadata = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            raise PromptLoadingError(f"Ошибка парсинга YAML в {file_path}: {str(e)}")
        
        if not isinstance(metadata, dict):
            raise PromptLoadingError(f"Frontmatter в {file_path} должен быть словарем")
        
        # Извлечь номер версии из имени файла
        version_match = re.search(r'v(\d+\.\d+\.\d+)', file_path.name)
        if not version_match:
            raise PromptLoadingError(f"Имя файла {file_path} не содержит корректной версии vX.Y.Z")
        
        semantic_version = version_match.group(1)
        
        # Генерируем ID на основе домена, capability, роли и версии
        id_parts = [domain, capability, role, semantic_version.replace('.', '_')]
        version_id = "_".join(id_parts)
        
        # Обработать переменные
        variables_schema = []
        if 'variables' in metadata:
            for var_data in metadata['variables']:
                variable = VariableSchema(
                    name=var_data['name'],
                    type=var_data.get('type', 'string'),
                    required=var_data.get('required', False),
                    description=var_data.get('description', '')
                )
                variables_schema.append(variable)
        
        # Создать объект PromptVersion
        from datetime import datetime
        from domain.models.prompt.prompt_version import PromptUsageMetrics, PromptStatus, PromptRole
        prompt_version = PromptVersion(
            id=version_id,
            semantic_version=semantic_version,
            domain=DomainType(domain),
            provider_type=LLMProviderType(metadata.get('provider', 'openai')),
            capability_name=capability,
            role=PromptRole(role),  # Роль теперь из пути к файлу
            content=prompt_content.strip(),
            max_size_bytes=500_000,  # значение по умолчанию
            variables_schema=variables_schema,
            expected_response_schema=metadata.get('expected_response', {}),
            status=PromptStatus(metadata.get('status', 'draft')),
            created_at=datetime.utcnow(),  # устанавливаем текущее время
            activation_date=None,
            deprecation_date=None,
            archived_date=None,
            parent_version_id=None,
            version_notes="",
            usage_metrics=PromptUsageMetrics()  # создаем пустой объект метрик
        )
        
        return prompt_version
    
    def _load_prompt_version_from_legacy_path(
        self, 
        domain: str, 
        capability: str, 
        file_path: Path
    ) -> Optional[PromptVersion]:
        """Загружает одну версию промта из файла в старой структуре (без роли в пути)"""
        content = file_path.read_text(encoding='utf-8')
        
        # Извлечь frontmatter (метаданные) из Markdown файла
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if not frontmatter_match:
            raise PromptLoadingError(f"Файл {file_path} не содержит корректного frontmatter")
        
        yaml_str, prompt_content = frontmatter_match.groups()
        
        try:
            metadata = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            raise PromptLoadingError(f"Ошибка парсинга YAML в {file_path}: {str(e)}")
        
        if not isinstance(metadata, dict):
            raise PromptLoadingError(f"Frontmatter в {file_path} должен быть словарем")
        
        # Извлечь номер версии из имени файла
        version_match = re.search(r'v(\d+\.\d+\.\d+)', file_path.name)
        if not version_match:
            raise PromptLoadingError(f"Имя файла {file_path} не содержит корректной версии vX.Y.Z")
        
        semantic_version = version_match.group(1)
        
        # Генерируем ID на основе домена, capability и версии
        id_parts = [domain, capability, semantic_version.replace('.', '_')]
        version_id = "_".join(id_parts)
        
        # Обработать переменные
        variables_schema = []
        if 'variables' in metadata:
            for var_data in metadata['variables']:
                variable = VariableSchema(
                    name=var_data['name'],
                    type=var_data.get('type', 'string'),
                    required=var_data.get('required', False),
                    description=var_data.get('description', '')
                )
                variables_schema.append(variable)
        
        # Создать объект PromptVersion
        from datetime import datetime
        from domain.models.prompt.prompt_version import PromptUsageMetrics, PromptStatus, PromptRole
        prompt_version = PromptVersion(
            id=version_id,
            semantic_version=semantic_version,
            domain=DomainType(domain),
            provider_type=LLMProviderType(metadata.get('provider', 'openai')),
            capability_name=capability,
            role=PromptRole(metadata.get('role', 'system')),  # Роль из метаданных
            content=prompt_content.strip(),
            max_size_bytes=500_000,  # значение по умолчанию
            variables_schema=variables_schema,
            expected_response_schema=metadata.get('expected_response', {}),
            status=PromptStatus(metadata.get('status', 'draft')),
            created_at=datetime.utcnow(),  # устанавливаем текущее время
            activation_date=None,
            deprecation_date=None,
            archived_date=None,
            parent_version_id=None,
            version_notes="",
            usage_metrics=PromptUsageMetrics()  # создаем пустой объект метрик
        )
        
        return prompt_version
    
    def validate_structure(self) -> List[str]:
        """
        Проверяет корректность структуры директорий и файлов.
        
        Returns:
            List[str]: Список ошибок валидации
        """
        errors = []
        
        if not self.base_path.exists():
            errors.append(f"Директория {self.base_path} не существует")
            return errors
        
        for domain_dir in self.base_path.iterdir():
            if not domain_dir.is_dir():
                continue
            
            for capability_dir in domain_dir.iterdir():
                if not capability_dir.is_dir():
                    continue
                
                # Проверить, есть ли хотя бы один файл версии
                # Сначала проверим структуру с подкаталогами ролей
                role_dirs = [
                    subdir for subdir in capability_dir.iterdir() 
                    if subdir.is_dir() and subdir.name in ["system", "user", "assistant", "tool"]
                ]
                
                if role_dirs:
                    # В новой структуре должны быть подкаталоги ролей
                    for role_dir in role_dirs:
                        version_files = list(role_dir.glob("v*.md"))
                        if not version_files:
                            errors.append(f"В директории {role_dir} отсутствуют файлы версий (vX.Y.Z.md)")
                        
                        # Проверить формат имен файлов версий
                        for file_path in version_files:
                            if not re.match(r'v\d+\.\d+\.\d+\.md$', file_path.name):
                                errors.append(f"Некорректный формат имени файла версии: {file_path.name}, ожидается vX.Y.Z.md")
                else:
                    # В старой структуре файлы версий должны быть прямо в capability_dir
                    version_files = list(capability_dir.glob("v*.md"))
                    if not version_files:
                        errors.append(f"В директории {capability_dir} отсутствуют файлы версий (vX.Y.Z.md)")
                    
                    # Проверить формат имен файлов версий
                    for file_path in version_files:
                        if not re.match(r'v\d+\.\d+\.\d+\.md$', file_path.name):
                            errors.append(f"Некорректный формат имени файла версии: {file_path.name}, ожидается vX.Y.Z.md")
        
        return errors
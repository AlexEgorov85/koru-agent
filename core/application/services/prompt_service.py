import os
import yaml
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import asyncio
from jinja2 import Template, UndefinedError
from core.application.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.models.prompt import Prompt, PromptStatus, PromptMetadata
from core.models.prompt_serialization import PromptSerializer
from core.infrastructure.registry.prompt_registry import PromptRegistry


class PromptNotFoundError(Exception):
    """Raised when a prompt is not found"""
    pass


class MissingVariablesError(Exception):
    """Raised when required variables are missing for rendering"""
    pass


class VersionNotFoundError(Exception):
    """Raised when a specific version of a prompt is not found"""
    pass


class PromptServiceInput(ServiceInput):
    """Входные данные для Promptservices."""
    def __init__(self, capability_name: str, variables: Dict[str, Any] = None, version: Optional[str] = None):
        self.capability_name = capability_name
        self.variables = variables or {}
        self.version = version


class PromptServiceOutput(ServiceOutput):
    """Выходные данные для Promptservices."""
    def __init__(self, rendered_prompt: str, metadata: Dict[str, Any] = None):
        self.rendered_prompt = rendered_prompt
        self.metadata = metadata or {}


class PromptService(BaseService):
    """
    Service for managing prompts with versioning, rendering, and indexing.
    Updated to support object model and registry.
    """

    @property
    def description(self) -> str:
        return "Сервис управления промптами с версионированием, рендерингом и индексацией (обновленная версия)"

    def __init__(self, prompts_dir: str = "prompts", default_version: Optional[str] = None, name: str = "prompt_service", application_context=None, component_config=None):
        from core.config.component_config import ComponentConfig
        # Создаем минимальный ComponentConfig, если не передан
        if component_config is None:
            component_config = ComponentConfig(
                variant_id="prompt_service_default",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={}
            )
        super().__init__(name=name, application_context=application_context, component_config=component_config)
        self.prompts_dir = Path(prompts_dir)
        self.default_version = default_version
        self._index = {}
        self._metadata = {}
        # Не создаем registry в __init__ - делаем это в initialize()
        self.registry = None
        self._prompt_objects: Dict[str, Dict[str, Prompt]] = {}  # capability → version → object

    async def initialize(self) -> bool:
        """
        Index all prompts at startup and load prompt objects.
        """
        try:
            # Создаем registry при инициализации, а не в __init__
            self.registry = PromptRegistry(Path(self.prompts_dir) / "registry.yaml")
            await self._build_index()
            await self._load_prompt_objects()
            
            # Вызываем родительскую инициализацию для правильной установки флага _initialized
            parent_result = await super().initialize()
            return parent_result
        except Exception as e:
            self.logger.error(f"Failed to initialize PromptService: {str(e)}")
            return False

    async def preload_prompts(self, component_config) -> bool:
        """
        Предзагрузка всех промптов, указанных в конфигурации компонента.

        ARGS:
        - component_config: конфигурация компонента с указанием версий промптов

        RETURNS:
        - bool: True если все промпты успешно загружены
        """
        if not hasattr(component_config, 'prompt_versions'):
            self.logger.info("Нет конфигурации промптов для предзагрузки")
            return True

        success = True
        for capability_name, version in component_config.prompt_versions.items():
            try:
                # Загружаем промпт и помещаем его в кэш
                prompt_obj = await self.get_prompt_object(capability_name, version)

                # Помещаем в кэш для быстрого доступа
                if capability_name not in self._prompt_objects:
                    self._prompt_objects[capability_name] = {}

                self._prompt_objects[capability_name][version] = prompt_obj

                self.logger.debug(f"Предзагружен промпт {capability_name} версии {version}")

            except Exception as e:
                self.logger.error(f"Ошибка предзагрузки промпта {capability_name} версии {version}: {e}")
                success = False

        return success

    def get_prompt_from_cache(self, capability_name: str, version: Optional[str] = None) -> Optional[str]:
        """
        Получение промпта ТОЛЬКО из кэша (без обращения к файловой системе).
        
        ARGS:
        - capability_name: имя capability
        - version: версия промпта (если None, используется активная)
        
        RETURNS:
        - str: текст промпта или None если не найден в кэше
        """
        if capability_name in self._prompt_objects:
            if version:
                if version in self._prompt_objects[capability_name]:
                    return self._prompt_objects[capability_name][version].content
            else:
                # Пытаемся получить активную версию через реестр
                active_prompt = self.registry.get_active_prompt(capability_name)
                if active_prompt:
                    return active_prompt.content
                    
                # Если нет в реестре, возвращаем последнюю из кэша
                if self._prompt_objects[capability_name]:
                    latest_version = max(
                        self._prompt_objects[capability_name].keys(),
                        key=lambda v: self._parse_version(v)
                    )
                    return self._prompt_objects[capability_name][latest_version].content
                    
        return None

    async def _build_index(self):
        """
        Build index of all available prompts by scanning the prompts directory.
        """
        self._index = {}
        self._metadata = {}

        # Load metadata
        metadata_file = self.prompts_dir / "metadata.yaml"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                self._metadata = yaml.safe_load(f)

        # Walk through all prompt files
        for file_path in self.prompts_dir.rglob("*.yaml"):
            if file_path.name == "metadata.yaml":
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    prompt_data = yaml.safe_load(f)

                # Extract version from filename (e.g., create_plan_v1.0.0.yaml -> v1.0.0)
                filename = file_path.stem
                version = self._extract_version_from_filename(filename)

                if not prompt_data or 'capability' not in prompt_data:
                    self.logger.warning(f"Invalid prompt file {file_path}: missing capability")
                    continue

                capability = prompt_data['capability']

                # Initialize index entry if not exists
                if capability not in self._index:
                    self._index[capability] = {}

                if version not in self._index[capability]:
                    self._index[capability][version] = {}

                # Store prompt info
                self._index[capability][version] = {
                    'path': file_path,
                    'data': prompt_data,
                    'skill': prompt_data.get('skill'),
                        'role': prompt_data.get('role'),
                    'language': prompt_data.get('language', 'ru'),
                    'variables': prompt_data.get('variables', []),
                    'content': prompt_data.get('content', ''),
                    'version': prompt_data.get('version')
                }

            except Exception as e:
                self.logger.error(f"Error processing prompt file {file_path}: {str(e)}")

        self.logger.info(f"Indexed {len(self._index)} capabilities with {sum(len(versions) for versions in self._index.values())} total versions")

    async def _load_prompt_objects(self):
        """
        Load prompt objects from files into memory for faster access.
        """
        self._prompt_objects = {}
        
        # Load from registry
        for capability, entry in self.registry.active_prompts.items():
            try:
                prompt = self.registry.get_active_prompt(capability)
                if prompt:
                    if capability not in self._prompt_objects:
                        self._prompt_objects[capability] = {}
                    
                    # Store by version
                    self._prompt_objects[capability][prompt.metadata.version] = prompt
            except Exception as e:
                self.logger.error(f"Error loading prompt object for capability {capability}: {str(e)}")

    async def execute(self, input_data: 'PromptServiceInput') -> 'PromptServiceOutput':
        """
        Выполнение сервиса - рендеринг промпта с подстановкой переменных.
        """
        try:
            rendered_prompt = await self.render(
                capability_name=input_data.capability_name,
                variables=input_data.variables,
                version=input_data.version
            )

            metadata = {
                'capability_name': input_data.capability_name,
                'version': input_data.version
            }

            return PromptServiceOutput(rendered_prompt=rendered_prompt, metadata=metadata)
        except Exception as e:
            self.logger.error(f"Error executing PromptService: {str(e)}")
            raise

    async def shutdown(self) -> None:
        """
        Завершение работы сервиса.
        """
        self.logger.info("Shutting down PromptService")
        # Здесь можно добавить любую очистку ресурсов при необходимости
        pass

    def _extract_version_from_filename(self, filename: str) -> str:
        """
        Extract version from filename like 'create_plan_v1.0.0' -> 'v1.0.0'
        """
        parts = filename.split('_')
        for i in range(len(parts)):
            if parts[i].lower().startswith('v') and len(parts[i]) > 1:
                # Check if it looks like a version (starts with v and has numbers/dots)
                version_part = parts[i]
                if version_part[1:].replace('.', '').isdigit():
                    return version_part

        # Default to 'latest' if no version found in filename
        return 'latest'

    # НОВЫЕ МЕТОДЫ:
    async def get_prompt_object(self, capability: str, version: Optional[str] = None) -> Prompt:
        """Возвращает объект промпта (не строку!)"""
        if capability in self._prompt_objects:
            if version:
                # Ищем конкретную версию
                if version in self._prompt_objects[capability]:
                    return self._prompt_objects[capability][version]
                else:
                    # Проверяем в реестре
                    prompt = self.registry.get_prompt_by_capability_and_version(capability, version)
                    if prompt:
                        return prompt
                    else:
                        raise VersionNotFoundError(f"Version '{version}' for capability '{capability}' not found")
            else:
                # Возвращаем активную версию
                prompt = self.registry.get_active_prompt(capability)
                if prompt:
                    return prompt
                else:
                    # Если нет в реестре, возвращаем последнюю из загруженных
                    if self._prompt_objects[capability]:
                        # Возвращаем самую новую версию
                        latest_version = max(
                            self._prompt_objects[capability].keys(),
                            key=lambda v: self._parse_version(v)
                        )
                        return self._prompt_objects[capability][latest_version]
        
        # Если не нашли в новых структурах, используем старую логику
        content = await self.get_prompt(capability, version=version)
        
        # Создаем временный объект Prompt из старого формата
        # Извлекаем метаданные из индекса
        if capability in self._index:
            if version and version in self._index[capability]:
                prompt_info = self._index[capability][version]
            else:
                # Используем последнюю версию
                available_versions = list(self._index[capability].keys())
                latest_version = self._find_latest_version(available_versions)
                prompt_info = self._index[capability][latest_version]
            
            # Создаем метаданные
            metadata = {
                'version': version or latest_version,
                'skill': prompt_info.get('skill', 'unknown'),
                'capability': capability,
                'role': prompt_info.get('role', 'system'),
                'language': prompt_info.get('language', 'ru'),
                'tags': prompt_info['data'].get('tags', []),
                'variables': prompt_info.get('variables', []),
                'status': PromptStatus.ACTIVE,  # по умолчанию
                'author': 'migration',  # по умолчанию
            }
            
            return Prompt(
                metadata=PromptMetadata(**metadata),
                content=content
            )
        
        raise PromptNotFoundError(f"Prompt with capability '{capability}' not found")

    async def create_prompt(self, capability: str, version: str, content: str, **metadata) -> Prompt:
        """Создает новый промпт-черновик и сохраняет в файл"""
        # Создаем метаданные
        prompt_metadata = {
            'version': version,
            'skill': metadata.get('skill', 'unknown'),
            'capability': capability,
            'role': metadata.get('role', 'system'),
            'language': metadata.get('language', 'ru'),
            'tags': metadata.get('tags', []),
            'variables': metadata.get('variables', []),
            'status': PromptStatus.DRAFT,
            'author': metadata.get('author', 'system'),
            'changelog': [f"Создан {metadata.get('created_at', 'now')}"]
        }
        
        # Создаем объект Prompt
        prompt = Prompt(
            metadata=PromptMetadata(**prompt_metadata),
            content=content
        )
        
        # Сохраняем в файл
        base_path = Path(self.prompts_dir)
        file_path = PromptSerializer.to_file(prompt, base_path / "skills")
        
        # Обновляем индекс
        await self.reload()
        
        return prompt

    async def promote_prompt(self, capability: str, version: str) -> bool:
        """Промоутит промпт в активный статус"""
        # Получаем промпт из реестра или из файлов
        prompt = self.registry.get_prompt_by_capability_and_version(capability, version)
        
        if not prompt:
            # Пытаемся загрузить из файлов
            if capability in self._prompt_objects and version in self._prompt_objects[capability]:
                prompt = self._prompt_objects[capability][version]
            else:
                # Пытаемся найти в индексе
                if capability in self._index and version in self._index[capability]:
                    prompt_info = self._index[capability][version]
                    content = prompt_info['content']
                    prompt_data = prompt_info['data']
                    
                    # Создаем объект Prompt из старого формата
                    metadata = {
                        'version': version,
                        'skill': prompt_data.get('skill', 'unknown'),
                        'capability': capability,
                                'role': prompt_data.get('role', 'system'),
                        'language': prompt_data.get('language', 'ru'),
                        'tags': prompt_data.get('tags', []),
                        'variables': prompt_data.get('variables', []),
                        'status': PromptStatus.DRAFT,  # по умолчанию
                        'author': prompt_data.get('author', 'migration'),
                        'changelog': prompt_data.get('changelog', [])
                    }
                    
                    prompt = Prompt(
                        metadata=PromptMetadata(**metadata),
                        content=content
                    )
        
        if prompt:
            # Обновляем статус на ACTIVE
            prompt.metadata.status = PromptStatus.ACTIVE
            prompt.metadata.updated_at = datetime.now(timezone.utc)
            
            # Сохраняем обновленный промпт
            base_path = Path(self.prompts_dir) / "skills"
            file_path = PromptSerializer.to_file(prompt, base_path)
            
            # Обновляем реестр
            success = self.registry.promote(prompt)
            
            # Обновляем индекс
            await self.reload()
            
            return success
        
        return False

    # СОХРАНЕНИЕ ОБРАТНОЙ СОВМЕСТИМОСТИ:
    async def get_prompt(
        self,
        capability_name: str,
        version: Optional[str] = None
    ) -> str:
        """
        Старый метод — возвращает строку (обертка над новым API)
        """
        try:
            prompt_obj = await self.get_prompt_object(capability_name, version)
            
            
            return prompt_obj.content
        except (PromptNotFoundError, VersionNotFoundError):
            # Если не нашли в новой системе, используем старую логику
            if capability_name not in self._index:
                raise PromptNotFoundError(f"Capability '{capability_name}' not found")

            # Determine version to use
            if version is None:
                # Use default version from metadata if available, otherwise latest
                if self._metadata and 'current_version' in self._metadata:
                    version = self._metadata['current_version']
                else:
                    # Find the latest version
                    available_versions = list(self._index[capability_name].keys())
                    version = self._find_latest_version(available_versions)

            # Check if the specific version exists
            if version not in self._index[capability_name]:
                # Try to find compatible version if exact version not found
                available_versions = list(self._index[capability_name].keys())
                version = self._find_compatible_version(version, available_versions)

                if version is None:
                    raise VersionNotFoundError(f"Version '{version}' for capability '{capability_name}' not found")

            # Get the prompt data
            prompt_info = self._index[capability_name][version]


            return prompt_info['content']

    def _find_latest_version(self, versions: List[str]) -> str:
        """
        Find the latest version from a list of versions.
        """
        if not versions:
            return 'latest'

        # Сортируем версии с использованием парсера версий
        return max(versions, key=self._parse_version, default='latest')

    def _parse_version(self, version: str) -> tuple:
        """
        Parse version string into comparable tuple
        """
        # Убираем префикс 'v' если он есть
        clean_version = version.lstrip('v')
        # Разбиваем на компоненты и конвертируем в числа
        try:
            parts = [int(part) for part in clean_version.split('.')]
            # Дополняем до 3 компонентов (major.minor.patch)
            while len(parts) < 3:
                parts.append(0)
            return tuple(parts)
        except ValueError:
            # Если не удается распарсить, возвращаем кортеж строк
            return tuple(clean_version.split('.'))

    def _find_compatible_version(self, requested_version: str, available_versions: List[str]) -> Optional[str]:
        """
        Find a compatible version based on semantic versioning rules.
        """
        # Для простоты возвращаем последнюю доступную версию
        if available_versions:
            return self._find_latest_version(available_versions)
        return None

    def scan_active_prompts(self):
        """
        Сканирует и возвращает активные промпты для использования в auto_resolve.
        """
        active_prompts = {}
        for capability, entry in self.registry.active_prompts.items():
            active_prompts[capability] = {
                "version": entry.version,
                "status": entry.status.value if hasattr(entry.status, 'value') else str(entry.status)
            }
        return active_prompts

    async def render(
        self,
        capability_name: str,
        variables: Dict[str, Any],
        version: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Старый метод — работает без изменений через объектную модель
        """
        # Get the raw prompt
        raw_prompt = await self.get_prompt(capability_name, version)

        # Get required variables for validation
        if capability_name in self._index:
            if version is None:
                # Use default version to get variables
                if self._metadata and 'current_version' in self._metadata:
                    version = self._metadata['current_version']
                else:
                    available_versions = list(self._index[capability_name].keys())
                    version = self._find_latest_version(available_versions)

            if version in self._index[capability_name]:
                required_vars = self._index[capability_name][version]['variables']
            else:
                required_vars = []
        else:
            required_vars = []

        # Validate required variables
        missing_vars = [var for var in required_vars if var not in variables]
        if missing_vars:
            raise MissingVariablesError(f"Missing required variables: {missing_vars}")

        # Check for unexpected variables (optional)
        if hasattr(self, '_strict_rendering') and self._strict_rendering:
            all_available_vars = set(required_vars + list(kwargs.keys()))
            unexpected_vars = [var for var in variables.keys() if var not in all_available_vars]
            if unexpected_vars:
                self.logger.warning(f"Unexpected variables in render call: {unexpected_vars}")

        # Combine variables and kwargs
        all_vars = {**variables, **kwargs}

        try:
            from jinja2 import StrictUndefined
            template = Template(raw_prompt, undefined=StrictUndefined)
            rendered_prompt = template.render(**all_vars)
            return rendered_prompt
        except UndefinedError as e:
            raise MissingVariablesError(f"Template rendering failed: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Prompt rendering failed: {str(e)}")

    async def list_prompts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        List prompts with optional filtering.
        """
        if filters is None:
            filters = {}

        result = []

        for capability, versions in self._index.items():
            for version, prompt_info in versions.items():
                # Apply filters
                if 'skill' in filters and prompt_info['skill'] != filters['skill']:
                    continue
                    continue
                if 'tags' in filters:
                    prompt_tags = prompt_info['data'].get('tags', [])
                    if not any(tag in prompt_tags for tag in filters['tags']):
                        continue

                result.append({
                    'capability': capability,
                    'version': version,
                    'skill': prompt_info['skill'],
                        'role': prompt_info['role'],
                    'language': prompt_info['language'],
                    'tags': prompt_info['data'].get('tags', []),
                    'path': str(prompt_info['path'])
                })

        return result

    async def reload(self) -> bool:
        """
        Hot reload prompts without stopping the system.
        """
        try:
            old_index_size = sum(len(versions) for versions in self._index.values())
            await self._build_index()
            await self._load_prompt_objects()
            new_index_size = sum(len(versions) for versions in self._index.values())

            self.logger.info(f"Reloaded prompts: {old_index_size} -> {new_index_size} versions")

            # TODO: Publish PROMPT_RELOADED event via EventBus if available

            return True
        except Exception as e:
            self.logger.error(f"Failed to reload prompts: {str(e)}")
            return False

    async def check_version_exists(self, capability: str, version: str) -> bool:
        """
        Проверяет, существует ли конкретная версия промпта для указанной capability.
        
        :param capability: имя capability
        :param version: версия промпта
        :return: True если версия существует, иначе False
        """
        # Проверяем в кэше объектов
        if capability in self._prompt_objects:
            if version in self._prompt_objects[capability]:
                return True
        
        # Проверяем в индексе
        if capability in self._index:
            if version in self._index[capability]:
                return True
        
        # Проверяем в реестре
        if self.registry:
            prompt = self.registry.get_prompt_by_capability_and_version(capability, version)
            if prompt:
                return True
        
        return False
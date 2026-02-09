import os
import yaml
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
from jinja2 import Template, UndefinedError
from core.infrastructure.service.base_service import BaseService, ServiceInput, ServiceOutput


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
    """Входные данные для PromptService."""
    def __init__(self, capability_name: str, variables: Dict[str, Any] = None, strategy: Optional[str] = None, version: Optional[str] = None):
        self.capability_name = capability_name
        self.variables = variables or {}
        self.strategy = strategy
        self.version = version


class PromptServiceOutput(ServiceOutput):
    """Выходные данные для PromptService."""
    def __init__(self, rendered_prompt: str, metadata: Dict[str, Any] = None):
        self.rendered_prompt = rendered_prompt
        self.metadata = metadata or {}


class PromptService(BaseService):
    """
    Service for managing prompts with versioning, rendering, and indexing.
    """

    @property
    def description(self) -> str:
        return "Сервис управления промптами с версионированием, рендерингом и индексацией"
    
    def __init__(self, prompts_dir: str = "prompts", default_version: Optional[str] = None, system_context=None, name: Optional[str] = None):
        super().__init__(system_context=system_context, name=name)
        self.prompts_dir = Path(prompts_dir)
        self.default_version = default_version
        self._index = {}
        self._metadata = {}
        
    async def initialize(self) -> bool:
        """
        Index all prompts at startup.
        """
        try:
            await self._build_index()
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize PromptService: {str(e)}")
            return False
    
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
                
                # Extract version from filename (e.g., create_plan_v1.2.0.yaml -> v1.2.0)
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
                    'strategy': prompt_data.get('strategy'),
                    'role': prompt_data.get('role'),
                    'language': prompt_data.get('language', 'ru'),
                    'variables': prompt_data.get('variables', []),
                    'content': prompt_data.get('content', ''),
                    'version': prompt_data.get('version')
                }
                
            except Exception as e:
                self.logger.error(f"Error processing prompt file {file_path}: {str(e)}")
        
        self.logger.info(f"Indexed {len(self._index)} capabilities with {sum(len(versions) for versions in self._index.values())} total versions")

    async def execute(self, input_data: 'PromptServiceInput') -> 'PromptServiceOutput':
        """
        Выполнение сервиса - рендеринг промпта с подстановкой переменных.
        """
        try:
            rendered_prompt = await self.render(
                capability_name=input_data.capability_name,
                variables=input_data.variables,
                strategy=input_data.strategy,
                version=input_data.version
            )
            
            metadata = {
                'capability_name': input_data.capability_name,
                'strategy': input_data.strategy,
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
        Extract version from filename like 'create_plan_v1.2.0' -> 'v1.2.0'
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
    
    async def get_prompt(
        self,
        capability_name: str,
        strategy: Optional[str] = None,
        version: Optional[str] = None
    ) -> str:
        """
        Get a prompt with version and strategy resolution.
        """
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
        
        # Apply strategy filtering if needed
        if strategy and prompt_info['strategy'] and prompt_info['strategy'] != strategy:
            raise PromptNotFoundError(f"Capability '{capability_name}' not available for strategy '{strategy}'")
        
        return prompt_info['content']
    
    def _find_latest_version(self, versions: List[str]) -> str:
        """
        Find the latest version from a list of versions.
        """
        # Simple approach: sort by version string and pick the last one
        # More sophisticated version comparison could be added later
        if not versions:
            return 'latest'
        
        # Sort versions - for now just pick the highest string
        # In the future, implement semantic versioning comparison
        return sorted(versions, reverse=True)[0]
    
    def _find_compatible_version(self, requested_version: str, available_versions: List[str]) -> Optional[str]:
        """
        Find a compatible version based on semantic versioning rules.
        """
        # For now, just return the latest available version
        # In the future, implement proper semver compatibility logic
        if available_versions:
            return self._find_latest_version(available_versions)
        return None
    
    async def render(
        self,
        capability_name: str,
        variables: Dict[str, Any],
        strategy: Optional[str] = None,
        version: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Render a prompt with variable substitution and validation.
        """
        # Get the raw prompt
        raw_prompt = await self.get_prompt(capability_name, strategy, version)
        
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
            template = Template(raw_prompt, undefined=UndefinedError)
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
                if 'strategy' in filters and prompt_info['strategy'] != filters['strategy']:
                    continue
                if 'tags' in filters:
                    prompt_tags = prompt_info['data'].get('tags', [])
                    if not any(tag in prompt_tags for tag in filters['tags']):
                        continue
                
                result.append({
                    'capability': capability,
                    'version': version,
                    'skill': prompt_info['skill'],
                    'strategy': prompt_info['strategy'],
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
            new_index_size = sum(len(versions) for versions in self._index.values())
            
            self.logger.info(f"Reloaded prompts: {old_index_size} -> {new_index_size} versions")
            
            # TODO: Publish PROMPT_RELOADED event via EventBus if available
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to reload prompts: {str(e)}")
            return False
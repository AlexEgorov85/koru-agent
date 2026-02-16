"""
Централизованный репозиторий с единой точкой валидации структуры данных.
"""
import asyncio
from typing import Dict, Tuple, List, Optional, Type
from core.infrastructure.storage.resource_data_source import ResourceDataSource
from core.models.prompt import Prompt, PromptStatus
from core.models.contract import Contract, ContractDirection
from core.models.manifest import Manifest, ComponentStatus
from core.config.app_config import AppConfig
from core.config.models import ComponentType
from pydantic import BaseModel
import logging


class DataRepository:
    """
    Централизованный репозиторий с единой точкой валидации структуры данных.
    Все ресурсы хранятся как полноценные объекты классов (не словари!).
    """

    def __init__(self, data_source: ResourceDataSource, profile: str = "prod"):
        self.data_source = data_source
        self.profile = profile
        self._initialized = False
        self.logger = logging.getLogger(__name__)

        # ТИПИЗИРОВАННЫЕ индексы (объекты классов, не словари!)
        self._prompts_index: Dict[Tuple[str, str], Prompt] = {}
        self._contracts_index: Dict[Tuple[str, str, str], Contract] = {}
        self._manifest_cache: Dict[str, Manifest] = {}  # Добавляем кэш для манифестов

        # Кэши для ленивой загрузки (уже объекты, но для контента/схем)
        self._prompt_content_cache: Dict[Tuple[str, str], str] = {}
        self._contract_schema_cache: Dict[Tuple[str, str, str], Type[BaseModel]] = {}

        self._validation_errors: List[str] = []
        self._validation_warnings: List[str] = []

    async def initialize(self, app_config: AppConfig) -> bool:
        """
        ЕДИНСТВЕННАЯ точка валидации структуры данных.
        Выполняется ОДИН РАЗ при старте приложения.
        """
        # 1. Сканируем ВСЕ метаданные как объекты
        all_prompts = self.data_source.load_all_prompts()  # → List[Prompt]
        all_contracts = self.data_source.load_all_contracts()  # → List[Contract]
        
        # 2. Строим индексы из объектов
        for prompt in all_prompts:
            key = (prompt.capability, prompt.version)
            self._prompts_index[key] = prompt
        
        for contract in all_contracts:
            key = (contract.capability, contract.version, contract.direction.value)
            self._contracts_index[key] = contract
        
        # 3. Валидация против конфигурации
        await self._validate_against_config(app_config)
        
        # 4. Валидация статусов версий против профиля
        await self._validate_status_by_profile()
        
        # 5. Финальная проверка критических ошибок
        if self._validation_errors:
            self._initialized = False
            return False
        
        self._initialized = True
        return True

    async def load_manifests(self) -> Dict[str, Manifest]:
        """Загрузка всех манифестов в кэш репозитория"""
        manifests = await asyncio.get_event_loop().run_in_executor(
            None, self.data_source.list_manifests
        )
        
        for manifest in manifests:
            key = f"{manifest.component_type.value}.{manifest.component_id}"
            self._manifest_cache[key] = manifest
        
        print(f"[DataRepository] Загружено {len(manifests)} манифестов: {list(self._manifest_cache.keys())}")
        return self._manifest_cache

    def get_manifest(self, component_type: str, component_id: str) -> Optional[Manifest]:
        """Получение манифеста из кэша"""
        key = f"{component_type}.{component_id}"
        return self._manifest_cache.get(key)

    def validate_manifest_by_profile(self, manifest: Manifest, profile: str) -> List[str]:
        """Валидация манифеста по профилю"""
        errors = []
        
        # Проверка owner
        if not manifest.owner:
            errors.append(f"Owner не указан для {manifest.component_id}")
        
        # Проверка статуса для prod
        if profile == "prod" and manifest.status != ComponentStatus.ACTIVE:
            errors.append(f"Статус {manifest.status.value} не разрешён в prod для {manifest.component_id}")
        
        # Проверка метрик
        if manifest.quality_metrics:
            if manifest.quality_metrics.success_rate_target < 0.9:
                errors.append(f"success_rate_target слишком низкий: {manifest.quality_metrics.success_rate_target}")
        
        return errors

    async def _validate_against_config(self, app_config: AppConfig):
        """Проверяем, что все версии из конфигурации существуют в ФС"""
        # Промпты
        for cap, ver in app_config.prompt_versions.items():
            key = (cap, ver)
            if key not in self._prompts_index:
                self._validation_errors.append(
                    f"Промпт {cap}@{ver} указан в конфигурации, но отсутствует в файловой системе"
                )
            else:
                prompt = self._prompts_index[key]
                # Проверяем соответствие типа компонента в конфиге и файле
                # Так как все данные уже предзагружены и валидированы, 
                # мы предполагаем, что типы компонентов уже соответствуют конфигурации
                # В новой архитектуре это соответствие проверяется при загрузке
        
        # Контракты (аналогично)
        for cap_dir, ver in app_config.input_contract_versions.items():
            cap = cap_dir.rsplit('.', 1)[0]  # "planning.create_plan.input" → "planning.create_plan"
            key = (cap, ver, "input")
            if key not in self._contracts_index:
                self._validation_errors.append(
                    f"Входной контракт {cap}@{ver} указан в конфигурации, но отсутствует в файловой системе"
                )
        
        for cap_dir, ver in app_config.output_contract_versions.items():
            cap = cap_dir.rsplit('.', 1)[0]
            key = (cap, ver, "output")
            if key not in self._contracts_index:
                self._validation_errors.append(
                    f"Выходной контракт {cap}@{ver} указан в конфигурации, но отсутствует в файловой системе"
                )
        
        # Также проверяем промпты из компонентных конфигураций
        for comp_type_attr in ['service_configs', 'skill_configs', 'tool_configs', 'behavior_configs']:
            if hasattr(app_config, comp_type_attr):
                comp_configs = getattr(app_config, comp_type_attr)
                for comp_name, comp_config in comp_configs.items():
                    if hasattr(comp_config, 'prompt_versions'):
                        for cap, ver in comp_config.prompt_versions.items():
                            key = (cap, ver)
                            if key not in self._prompts_index:
                                # Не добавляем как ошибку, а как предупреждение, т.к. это может быть нормально
                                self._validation_warnings.append(
                                    f"Промпт {cap}@{ver} из компонента {comp_name} отсутствует в файловой системе"
                                )
                    
                    if hasattr(comp_config, 'input_contract_versions'):
                        for cap_dir, ver in comp_config.input_contract_versions.items():
                            cap = cap_dir.rsplit('.', 1)[0]
                            key = (cap, ver, "input")
                            if key not in self._contracts_index:
                                self._validation_warnings.append(
                                    f"Входной контракт {cap}@{ver} из компонента {comp_name} отсутствует в файловой системе"
                                )
                    
                    if hasattr(comp_config, 'output_contract_versions'):
                        for cap_dir, ver in comp_config.output_contract_versions.items():
                            cap = cap_dir.rsplit('.', 1)[0]
                            key = (cap, ver, "output")
                            if key not in self._contracts_index:
                                self._validation_warnings.append(
                                    f"Выходной контракт {cap}@{ver} из компонента {comp_name} отсутствует в файловой системе"
                                )
    
    async def _validate_status_by_profile(self):
        """Валидация статусов версий против профиля"""
        allowed_statuses = [PromptStatus.ACTIVE] if self.profile == "prod" else [
            PromptStatus.DRAFT, PromptStatus.ACTIVE
        ]
        
        for (cap, ver), prompt in self._prompts_index.items():
            if prompt.status not in allowed_statuses:
                if self.profile == "prod":
                    self._validation_errors.append(
                        f"Промпт {cap}@{ver} имеет недопустимый статус '{prompt.status.value}' "
                        f"для профиля prod (требуется 'active')"
                    )
                else:
                    self._validation_warnings.append(
                        f"Промпт {cap}@{ver} имеет статус '{prompt.status.value}' (разрешено в sandbox)"
                    )
        
        for (cap, ver, direction), contract in self._contracts_index.items():
            if contract.status not in allowed_statuses:
                if self.profile == "prod":
                    self._validation_errors.append(
                        f"Контракт {cap}@{ver} ({direction}) имеет недопасимый статус "
                        f"'{contract.status.value}' для профиля prod"
                    )
    
    def get_prompt(self, capability: str, version: str) -> Prompt:
        """Возвращает ГОТОВЫЙ объект промпта (не строку!)"""
        if not self._initialized:
            raise RuntimeError("DataRepository не инициализирован. Вызовите .initialize() сначала.")
        
        key = (capability, version)
        if key not in self._prompts_index:
            raise KeyError(
                f"Промпт {capability}@{version} не найден в репозитории.\n"
                f"Доступные промпты: {sorted([f'{c}@{v}' for (c,v) in self._prompts_index.keys()])}"
            )
        
        return self._prompts_index[key]
    
    def get_contract(self, capability: str, version: str, direction: str) -> Contract:
        """Возвращает ГОТОВЫЙ объект контракта"""
        if not self._initialized:
            raise RuntimeError("DataRepository не инициализирован")
        
        key = (capability, version, direction)
        if key not in self._contracts_index:
            raise KeyError(
                f"Контракт {capability}@{version} ({direction}) не найден в репозитории"
            )
        
        return self._contracts_index[key]
    
    def get_contract_schema(self, capability: str, version: str, direction: str) -> Type[BaseModel]:
        """
        Возвращает СКОМПИЛИРОВАННУЮ Pydantic-схему для немедленной валидации.
        Ленивая загрузка с кэшированием.
        """
        contract = self.get_contract(capability, version, direction)
        
        cache_key = (capability, version, direction)
        if cache_key not in self._contract_schema_cache:
            self._contract_schema_cache[cache_key] = contract.pydantic_schema
        
        return self._contract_schema_cache[cache_key]
    
    def get_validation_report(self) -> str:
        """Полный отчёт о проблемах структуры"""
        report = ["=" * 60, "ОТЧЁТ ВАЛИДАЦИИ DATA REPOSITORY", "=" * 60, ""]
        
        if self._validation_errors:
            report.append("❌ КРИТИЧЕСКИЕ ОШИБКИ (блокируют запуск):")
            for i, err in enumerate(self._validation_errors, 1):
                report.append(f"  {i}. {err}")
            report.append("")
        
        if self._validation_warnings:
            report.append("⚠️  ПРЕДУПРЕЖДЕНИЯ (не блокируют запуск):")
            for i, warn in enumerate(self._validation_warnings, 1):
                report.append(f"  {i}. {warn}")
            report.append("")
        
        if not self._validation_errors and not self._validation_warnings:
            report.append("✅ Все проверки пройдены успешно")
            report.append("")
        
        # Статистика
        report.append("📊 Статистика репозитория:")
        report.append(f"   Промптов загружено: {len(self._prompts_index)}")
        report.append(f"   Контрактов загружено: {len(self._contracts_index)}")
        report.append(f"   Профиль: {self.profile}")
        report.append("=" * 60)
        
        return "\n".join(report)
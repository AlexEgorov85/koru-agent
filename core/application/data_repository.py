"""
Централизованный репозиторий с единой точкой валидации структуры данных.
"""
from typing import Dict, Tuple, List, Optional, Type
from core.infrastructure.storage.data_source import IDataSource
from core.models.prompt import Prompt, PromptStatus
from core.models.contract import Contract, ContractDirection
from core.config.app_config import AppConfig
from core.config.models import ComponentType
from pydantic import BaseModel


class DataRepository:
    """
    Централизованный репозиторий с единой точкой валидации структуры данных.
    Все ресурсы хранятся как полноценные объекты классов (не словари!).
    """
    
    def __init__(self, data_source: IDataSource, profile: str = "prod"):
        self.data_source = data_source
        self.profile = profile
        self._initialized = False
        
        # ТИПИЗИРОВАННЫЕ индексы (объекты классов, не словари!)
        self._prompts_index: Dict[Tuple[str, str], Prompt] = {}
        self._contracts_index: Dict[Tuple[str, str, str], Contract] = {}
        
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
        all_prompts = await self.data_source.list_prompts()  # → List[Prompt]
        all_contracts = await self.data_source.list_contracts()  # → List[Contract]
        
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
                try:
                    expected_type = self.data_source._get_component_type(cap)  # ← Явное получение из конфига
                    if prompt.component_type != expected_type:
                        self._validation_errors.append(
                            f"Несоответствие типа компонента для {cap}@{ver}: "
                            f"в файле '{prompt.component_type.value}', в конфигурации '{expected_type.value}'"
                        )
                except Exception as e:
                    self._validation_errors.append(
                        f"Ошибка получения типа компонента для {cap}: {str(e)}"
                    )
        
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
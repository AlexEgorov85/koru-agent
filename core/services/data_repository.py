"""
Централизованный репозиторий с единой точкой валидации структуры данных.
"""
import asyncio
from typing import Dict, Tuple, List, Optional, Type
from core.infrastructure.storage.resource_data_source import ResourceDataSource
from core.models.data.prompt import Prompt, PromptStatus
from core.models.data.contract import Contract, ContractDirection
from core.config.app_config import AppConfig
from core.models.enums.common_enums import ComponentType
from pydantic import BaseModel
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()


class DataRepository:
    """
    Централизованный репозиторий с единой точкой валидации структуры данных.
    Все ресурсы хранятся как полноценные объекты классов (не словари!).
    """

    def __init__(self, data_source: ResourceDataSource, profile: str = "prod", event_bus=None):
        self.data_source = data_source
        self.profile = profile
        self._initialized = False
        
        # Инициализация логгера
        if event_bus is not None:
            self.logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="DataRepository")
            self._use_event_logging = True
        else:
            # Dummy-логгер для обратной совместимости
            class DummyLogger:
                def info(self, msg, *a, **k): pass
                def debug(self, msg, *a, **k): pass
                def warning(self, msg, *a, **k): pass
                def error(self, msg, *a, **k): pass
                def exception(self, msg, *a, **k): pass
            self.logger = DummyLogger()
            self._use_event_logging = False

        # ТИПИЗИРОВАННЫЕ индексы (объекты классов, не словари!)
        self._prompts_index: Dict[Tuple[str, str], Prompt] = {}
        self._contracts_index: Dict[Tuple[str, str, str], Contract] = {}

        # Кэши для ленивой загрузки (уже объекты, но для контента/схем)
        self.prompt_cache: Dict[Tuple[str, str], str] = {}
        self.contract_schema_cache: Dict[Tuple[str, str, str], Type[BaseModel]] = {}

        self._validation_errors: List[str] = []
        self._validation_warnings: List[str] = []

    def _log_info(self, message: str, *args, **kwargs):
        """Информационное сообщение."""
        if self._use_event_logging:
            self.logger.info(message, *args, **kwargs)
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        else:
            self.logger.info(message, *args, **kwargs)
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    def _log_warning(self, message: str, *args, **kwargs):
        """Предупреждение."""
        if self._use_event_logging:
            self.logger.warning(message, *args, **kwargs)
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        else:
            self.logger.warning(message, *args, **kwargs)
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    def _log_error(self, message: str, *args, **kwargs):
        """Ошибка."""
        if self._use_event_logging:
            self.logger.error(message, *args, **kwargs)
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        else:
            self.logger.error(message, *args, **kwargs)
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

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

    async def _validate_against_config(self, app_config: AppConfig):
        """Проверяем, что все версии из конфигурации существуют в ФС"""
        # Промпты (исключаем .system промпты — они используются отдельно)
        for cap, ver in app_config.prompt_versions.items():
            if cap.endswith('.system'):
                continue  # Пропускаем system промпты
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
        # Ключи в input_contract_versions/output_contract_versions имеют вид "final_answer.generate"
        # и должны совпадать с capability в контрактах
        for cap, ver in app_config.input_contract_versions.items():
            key = (cap, ver, "input")
            if key not in self._contracts_index:
                self._validation_errors.append(
                    f"Входной контракт {cap}@{ver} указан в конфигурации, но отсутствует в файловой системе"
                )

        for cap, ver in app_config.output_contract_versions.items():
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
                            # Исключаем .system промпты — они используются отдельно
                            if cap.endswith('.system'):
                                continue
                            key = (cap, ver)
                            if key not in self._prompts_index:
                                # Не добавляем как ошибку, а как предупреждение, т.к. это может быть нормально
                                self._validation_warnings.append(
                                    f"Промпт {cap}@{ver} из компонента {comp_name} отсутствует в файловой системе"
                                )
                    
                    if hasattr(comp_config, 'input_contract_versions'):
                        for cap, ver in comp_config.input_contract_versions.items():
                            key = (cap, ver, "input")
                            if key not in self._contracts_index:
                                self._validation_warnings.append(
                                    f"Входной контракт {cap}@{ver} из компонента {comp_name} отсутствует в файловой системе"
                                )

                    if hasattr(comp_config, 'output_contract_versions'):
                        for cap, ver in comp_config.output_contract_versions.items():
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
        if cache_key not in self.contract_schema_cache:
            self.contract_schema_cache[cache_key] = contract.pydantic_schema

        return self.contract_schema_cache[cache_key]
    
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

    # ========================================================================
    # Методы для Benchmark/Learning системы (Этап 7)
    # ========================================================================

    def get_prompt_versions(self, capability: str) -> List[Prompt]:
        """
        Получение всех версий промпта для capability.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[Prompt]: список версий промпта, отсортированных по версии
        """
        versions = []
        for (cap, ver), prompt in self._prompts_index.items():
            if cap == capability:
                versions.append(prompt)

        # Сортировка по версии (простая строковая сортировка)
        return sorted(versions, key=lambda p: p.version)

    def get_contract_versions(self, capability: str, direction: str) -> List[Contract]:
        """
        Получение всех версий контракта для capability.

        ARGS:
        - capability: название способности
        - direction: направление (input/output)

        RETURNS:
        - List[Contract]: список версий контракта
        """
        versions = []
        for (cap, ver, dir_), contract in self._contracts_index.items():
            if cap == capability and dir_ == direction:
                versions.append(contract)

        return sorted(versions, key=lambda c: c.version)

    def get_active_version(self, capability: str) -> Optional[str]:
        """
        Получение активной версии промпта для capability.

        ARGS:
        - capability: название способности

        RETURNS:
        - Optional[str]: версия или None если не найдена
        """
        for (cap, ver), prompt in self._prompts_index.items():
            if cap == capability and prompt.status == PromptStatus.ACTIVE:
                return ver
        return None

    def get_draft_versions(self, capability: str) -> List[str]:
        """
        Получение draft версий промпта для capability.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[str]: список draft версий
        """
        drafts = []
        for (cap, ver), prompt in self._prompts_index.items():
            if cap == capability and prompt.status == PromptStatus.DRAFT:
                drafts.append(ver)
        return drafts

    def update_prompt_status(
        self,
        capability: str,
        version: str,
        new_status: PromptStatus
    ) -> bool:
        """
        Обновление статуса промпта.

        ARGS:
        - capability: название способности
        - version: версия промпта
        - new_status: новый статус

        RETURNS:
        - bool: успешно ли обновлено
        """
        key = (capability, version)
        if key not in self._prompts_index:
            self._log_warning(f"Промпт {capability}@{version} не найден")
            return False

        prompt = self._prompts_index[key]
        old_status = prompt.status

        # Prompt - frozen модель, создаём новую копию с обновлённым статусом
        try:
            new_prompt = prompt.model_copy(update={'status': new_status})
            self._prompts_index[key] = new_prompt
            self._log_info(f"Статус промпта {capability}@{version} изменён: {old_status.value} → {new_status.value}")
            return True
        except Exception as e:
            self._log_error(f"Ошибка обновления статуса промпта {capability}@{version}: {e}")
            return False

    def update_contract_status(
        self,
        capability: str,
        version: str,
        direction: str,
        new_status: PromptStatus
    ) -> bool:
        """
        Обновление статуса контракта.

        ARGS:
        - capability: название способности
        - version: версия контракта
        - direction: направление (input/output)
        - new_status: новый статус (active/draft)

        RETURNS:
        - bool: успешно ли обновлено
        """
        key = (capability, version, direction)
        if key not in self._contracts_index:
            self._log_warning(f"Контракт {capability}@{version} ({direction}) не найден")
            return False

        contract = self._contracts_index[key]
        old_status = contract.status

        # Contract - frozen модель, создаём новую копию с обновлённым статусом
        try:
            new_contract = contract.model_copy(update={'status': new_status})
            self._contracts_index[key] = new_contract
            self._log_info(f"Статус контракта {capability}@{version} ({direction}) изменён: {old_status.value} → {new_status.value}")
            return True
        except Exception as e:
            self._log_error(f"Ошибка обновления статуса контракта {capability}@{version} ({direction}): {e}")
            return False

    def add_prompt(self, prompt: Prompt) -> bool:
        """
        Добавление нового промпта в репозиторий.

        ARGS:
        - prompt: объект промпта для добавления

        RETURNS:
        - bool: успешно ли добавлено
        """
        key = (prompt.capability, prompt.version)
        if key in self._prompts_index:
            self._log_warning(f"Промпт {prompt.capability}@{prompt.version} уже существует")
            return False

        self._prompts_index[key] = prompt
        self._log_info(f"Добавлен промпт {prompt.capability}@{prompt.version}")
        return True

    def add_contract(self, contract: Contract) -> bool:
        """
        Добавление нового контракта в репозиторий.

        ARGS:
        - contract: объект контракта для добавления

        RETURNS:
        - bool: успешно ли добавлено
        """
        key = (contract.capability, contract.version, contract.direction.value)
        if key in self._contracts_index:
            self._log_warning(f"Контракт {contract.capability}@{contract.version} ({contract.direction.value}) уже существует")
            return False

        self._contracts_index[key] = contract
        self._log_info(f"Добавлен контракт {contract.capability}@{contract.version} ({contract.direction.value})")
        return True

    async def shutdown(self):
        """
        Завершение работы DataRepository.
        Очищает кэши и индексы.
        """
        self._log_info_sync("Завершение работы DataRepository...")
        self._prompts_index.clear()
        self._contracts_index.clear()
        self.prompt_cache.clear()
        self.contract_schema_cache.clear()
        self._validation_errors.clear()
        self._validation_warnings.clear()
        self._initialized = False
        self._log_info_sync("DataRepository завершён")

    def _log_info_sync(self, message: str, *args, **kwargs):
        """Синхронное информационное сообщение."""
        if self._use_event_logging:
            self.logger.info_sync(message, *args, **kwargs)
        else:
            self.logger.info(message, *args, **kwargs)              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

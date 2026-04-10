"""
Единый загрузчик ресурсов.

Заменяет:
- ResourceDiscovery (сканирование + кэш)
- FileSystemDataSource (загрузка из ФС)
- DataRepository (валидация + индекс)
- ResourcePreloader (предзагрузка для компонентов)

АРХИТЕКТУРА:
- Один проход по ФС при load_all()
- Кэширование на уровне класса (фабричный метод get())
- Fail-fast при битом YAML
- Фильтрация по статусу профиля
"""
import logging
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from core.models.data.prompt import Prompt, PromptStatus, PromptVariable
from core.models.data.contract import Contract, ContractDirection
from core.models.enums.common_enums import ComponentType
from core.errors.exceptions import ResourceLoadError
from core.infrastructure.logging.event_types import LogEventType
from core.config.component_config import ComponentConfig


logger = logging.getLogger(__name__)


class ResourceLoader:
    """
    Единый загрузчик ресурсов.

    FEATURES:
    - Фабричный метод get() с кэшированием — гарантирует ОДНО сканирование ФС
    - Профильная фильтрация статусов (prod/sandbox/dev)
    - Fail-fast при битом YAML или отсутствующих обязательных полях
    - Инференция component_type и direction из пути/имени файла

    USAGE:
    ```python
    # Через фабричный метод (рекомендуется):
    loader = ResourceLoader.get(data_dir=Path("data"), profile="prod")

    # Прямое создание:
    loader = ResourceLoader(data_dir=Path("data"), profile="prod")
    loader.load_all()

    # Получение ресурсов:
    prompt = loader.get_prompt("planning.create_plan", "v1.0.0")
    contract = loader.get_contract("planning.create_plan", "v1.0.0", "input")
    resources = loader.get_component_resources("planning_skill", component_config)
    ```
    """

    # Маппинг профилей на разрешённые статусы
    PROFILE_STATUSES: Dict[str, set] = {
        "prod": {PromptStatus.ACTIVE},
        "sandbox": {PromptStatus.ACTIVE, PromptStatus.DRAFT},
        "dev": {PromptStatus.ACTIVE, PromptStatus.DRAFT, PromptStatus.INACTIVE},
    }

    # Кэш на уровне класса (Риск 1: двойное сканирование)
    _cache: Dict[Tuple[Path, str], "ResourceLoader"] = {}

    @classmethod
    def get(cls, data_dir: Path, profile: str = "prod") -> "ResourceLoader":
        """
        Фабричный метод с кэшированием.

        Гарантирует ОДНО сканирование ФС на (data_dir, profile).

        ARGS:
        - data_dir: Базовая директория данных
        - profile: Профиль работы (prod/sandbox/dev)

        RETURNS:
        - ResourceLoader: Загруженный и готовый к использованию
        """
        key = (data_dir.resolve(), profile)
        if key not in cls._cache:
            loader = cls(data_dir, profile)
            loader.load_all()
            cls._cache[key] = loader
        return cls._cache[key]

    @classmethod
    def clear_cache(cls) -> None:
        """Очистка кэша (для тестов)."""
        cls._cache.clear()

    def __init__(self, data_dir: Path, profile: str = "prod"):
        """
        Инициализация загрузчика.

        ARGS:
        - data_dir: Базовая директория данных
        - profile: Профиль работы (prod/sandbox/dev)
        """
        self.data_dir = data_dir.resolve()
        self.profile = profile
        self.allowed_statuses = self.PROFILE_STATUSES.get(
            profile, self.PROFILE_STATUSES["prod"]
        )

        # Кэши загруженных ресурсов
        self._prompts: Dict[Tuple[str, str], Prompt] = {}        # (cap, ver) -> Prompt
        self._contracts: Dict[Tuple[str, str, str], Contract] = {}  # (cap, ver, dir) -> Contract
        self._loaded = False

        # Статистика
        self._stats = {
            "prompts_scanned": 0,
            "prompts_loaded": 0,
            "prompts_skipped": 0,
            "contracts_scanned": 0,
            "contracts_loaded": 0,
            "contracts_skipped": 0,
        }

    def load_all(self) -> None:
        """
        Однократное сканирование, парсинг и кэширование.

        Безопасно для повторного вызова — ничего не делает если уже загружено.
        Fail-fast при битом YAML — выбрасывает ResourceLoadError.
        """
        if self._loaded:
            logger.debug("ResourceLoader уже загружен, повторный вызов пропущен")
            return

        logger.info(
            "Начало загрузки ресурсов...",
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )

        self._scan_dir(
            self.data_dir / "prompts",
            is_contract=False
        )
        self._scan_dir(
            self.data_dir / "contracts",
            is_contract=True
        )
        self._loaded = True

        logger.info(
            f"✅ Загружено ресурсов: "
            f"промптов={self._stats['prompts_loaded']}, "
            f"контрактов={self._stats['contracts_loaded']} "
            f"(профиль={self.profile})",
            extra={"event_type": LogEventType.SYSTEM_READY}
        )

    def get_prompt(self, capability: str, version: str) -> Optional[Prompt]:
        """
        Получить промпт из кэша.

        ARGS:
        - capability: Имя capability (например, 'planning.create_plan')
        - version: Версия (например, 'v1.0.0')

        RETURNS:
        - Optional[Prompt]: Объект промпта или None
        """
        return self._prompts.get((capability, version))

    def get_contract(
        self,
        capability: str,
        version: str,
        direction: str
    ) -> Optional[Contract]:
        """
        Получить контракт из кэша.

        ARGS:
        - capability: Имя capability
        - version: Версия
        - direction: Направление (input/output)

        RETURNS:
        - Optional[Contract]: Объект контракта или None
        """
        return self._contracts.get((capability, version, direction))

    def get_all_prompts(self) -> List[Prompt]:
        """Все промпты из кэша (для AppConfig.from_discovery)."""
        return list(self._prompts.values())

    def get_all_contracts(self) -> List[Contract]:
        """Все контракты из кэша (для AppConfig.from_discovery)."""
        return list(self._contracts.values())

    def get_component_resources(
        self,
        component_name: str,
        config: ComponentConfig
    ) -> Dict[str, Any]:
        """
        Возвращает ресурсы, запрошенные компонентом.

        Выбирает промпты и контракты на основе версий, указанных в ComponentConfig.

        ARGS:
        - component_name: Имя компонента (для логирования)
        - config: ComponentConfig с версиями ресурсов

        RETURNS:
        - Dict с ресурсами:
          - "prompts": Dict[str, Prompt]
          - "input_contracts": Dict[str, Contract]
          - "output_contracts": Dict[str, Contract]
        """
        prompts: Dict[str, Prompt] = {}
        input_contracts: Dict[str, Contract] = {}
        output_contracts: Dict[str, Contract] = {}

        # Промпты
        for cap, ver in config.prompt_versions.items():
            prompt = self.get_prompt(cap, ver)
            if prompt:
                prompts[cap] = prompt
            else:
                logger.warning(
                    f"Промпт '{cap}@{ver}' не найден для компонента '{component_name}'",
                    extra={"event_type": LogEventType.WARNING}
                )

        # Input контракты
        for cap, ver in config.input_contract_versions.items():
            contract = self.get_contract(cap, ver, "input")
            if contract:
                input_contracts[cap] = contract
            else:
                logger.warning(
                    f"Входной контракт '{cap}@{ver}' не найден для компонента '{component_name}'",
                    extra={"event_type": LogEventType.WARNING}
                )

        # Output контракты
        for cap, ver in config.output_contract_versions.items():
            contract = self.get_contract(cap, ver, "output")
            if contract:
                output_contracts[cap] = contract
            else:
                logger.warning(
                    f"Выходной контракт '{cap}@{ver}' не найден для компонента '{component_name}'",
                    extra={"event_type": LogEventType.WARNING}
                )

        logger.debug(
            f"Ресурсы для '{component_name}': "
            f"prompts={len(prompts)}, input={len(input_contracts)}, output={len(output_contracts)}"
        )

        return {
            "prompts": prompts,
            "input_contracts": input_contracts,
            "output_contracts": output_contracts,
        }

    def get_stats(self) -> Dict[str, int]:
        """Получение статистики сканирования."""
        return self._stats.copy()

    # =========================================================================
    # Внутренние методы
    # =========================================================================

    def _scan_dir(self, base_dir: Path, is_contract: bool) -> None:
        """
        Сканирование директории с YAML файлами.

        ARGS:
        - base_dir: Директория для сканирования
        - is_contract: True если сканируем контракты, False если промпты
        """
        if not base_dir.exists():
            logger.warning(
                f"Директория не найдена: {base_dir}",
                extra={"event_type": LogEventType.WARNING}
            )
            return

        yaml_files = list(base_dir.rglob("*.yaml")) + list(base_dir.rglob("*.yml"))

        resource_type = "контрактов" if is_contract else "промптов"
        logger.debug(
            f"Сканирование {resource_type}: найдено {len(yaml_files)} файлов в {base_dir}"
        )

        for file_path in yaml_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f)

                if not isinstance(raw, dict):
                    raise ResourceLoadError(
                        f"Файл {file_path} не содержит словарь. Проверьте корректность YAML.",
                        resource_path=str(file_path)
                    )

                if is_contract:
                    self._parse_and_cache_contract(raw, file_path)
                else:
                    self._parse_and_cache_prompt(raw, file_path)

            except ResourceLoadError:
                raise
            except Exception as e:
                raise ResourceLoadError(
                    f"Ошибка загрузки ресурса {file_path}: {e}",
                    resource_path=str(file_path)
                )

    def _parse_and_cache_prompt(self, raw: Dict[str, Any], file_path: Path) -> None:
        """Парсинг и кэширование одного промпта."""
        status_str = raw.get("status", "draft")

        # Фильтрация по статусу
        try:
            status = PromptStatus(status_str)
        except ValueError:
            raise ResourceLoadError(
                f"Неизвестный статус '{status_str}' в {file_path}",
                resource_path=str(file_path)
            )

        if status not in self.allowed_statuses:
            self._stats["prompts_skipped"] += 1
            return

        # Обязательные поля
        capability = raw.get("capability")
        version = raw.get("version")
        if not capability or not version:
            raise ResourceLoadError(
                f"Файл {file_path} не содержит capability или version. "
                f"Это обязательные поля для промпта.",
                resource_path=str(file_path)
            )

        content = raw.get("content", "")
        variables_data = raw.get("variables", [])
        metadata = raw.get("metadata", {})

        # Парсинг переменных
        parsed_variables = []
        for var in variables_data:
            if isinstance(var, dict):
                try:
                    parsed_variables.append(PromptVariable(**var))
                except Exception as e:
                    raise ResourceLoadError(
                        f"Ошибка парсинга переменной в {file_path}: {e}",
                        resource_path=str(file_path)
                    )

        # Инференция component_type
        component_type_str = raw.get("component_type")
        if component_type_str:
            try:
                comp_type = ComponentType(component_type_str)
            except ValueError:
                raise ResourceLoadError(
                    f"Неизвестный тип компонента '{component_type_str}' в {file_path}",
                    resource_path=str(file_path)
                )
        else:
            comp_type = self._infer_component_type_from_path(file_path)

        prompt = Prompt(
            capability=capability,
            version=version,
            status=status,
            component_type=comp_type,
            content=content,
            variables=parsed_variables,
            metadata=metadata,
        )

        key = (capability, version)
        self._prompts[key] = prompt
        self._stats["prompts_loaded"] += 1

    def _parse_and_cache_contract(self, raw: Dict[str, Any], file_path: Path) -> None:
        """Парсинг и кэширование одного контракта."""
        status_str = raw.get("status", "draft")

        # Фильтрация по статусу
        try:
            status = PromptStatus(status_str)
        except ValueError:
            raise ResourceLoadError(
                f"Неизвестный статус '{status_str}' в {file_path}",
                resource_path=str(file_path)
            )

        if status not in self.allowed_statuses:
            self._stats["contracts_skipped"] += 1
            return

        # Обязательные поля
        capability = raw.get("capability")
        version = raw.get("version")
        direction_str = raw.get("direction")

        # Если capability/version/direction не указаны — пробуем из имени файла
        if not capability or not version:
            cap, ver, dir_from_name = self._parse_contract_filename(file_path)
            capability = capability or cap
            version = version or ver
            direction_str = direction_str or dir_from_name

        if not capability or not version:
            raise ResourceLoadError(
                f"Не удалось определить capability/version для {file_path}. "
                f"Укажите их в файле или используйте формат имени "
                f"{{capability}}_{{direction}}_{{version}}.yaml",
                resource_path=str(file_path)
            )

        # Направление по умолчанию
        if not direction_str:
            direction_str = self._infer_direction_from_filename(file_path)

        if not direction_str:
            raise ResourceLoadError(
                f"Не удалось определить направление контракта для {file_path}. "
                f"Используйте формат имени файла "
                f"{{capability}}_{{direction}}_{{version}}.yaml "
                f"или укажите direction: input|output в файле.",
                resource_path=str(file_path)
            )

        try:
            direction = ContractDirection(direction_str)
        except ValueError:
            raise ResourceLoadError(
                f"Неизвестное направление '{direction_str}' в {file_path}",
                resource_path=str(file_path)
            )

        schema_data = raw.get("schema", raw.get("schema_data", {}))
        description = raw.get("description", "")

        # Инференция component_type
        component_type_str = raw.get("component_type")
        if component_type_str:
            try:
                comp_type = ComponentType(component_type_str)
            except ValueError:
                raise ResourceLoadError(
                    f"Неизвестный тип компонента '{component_type_str}' в {file_path}",
                    resource_path=str(file_path)
                )
        else:
            comp_type = self._infer_component_type_from_path(file_path)

        contract = Contract(
            capability=capability,
            version=version,
            status=status,
            component_type=comp_type,
            direction=direction,
            schema_data=schema_data if schema_data else {"type": "object", "properties": {}},
            description=description,
        )

        key = (capability, version, direction.value)
        self._contracts[key] = contract
        self._stats["contracts_loaded"] += 1

    def _infer_component_type_from_path(self, file_path: Path) -> ComponentType:
        """Авто-определение типа компонента по пути к файлу."""
        path_str = str(file_path).lower()

        if "/skill/" in path_str or "\\skill\\" in path_str:
            return ComponentType.SKILL
        elif "/service/" in path_str or "\\service\\" in path_str:
            return ComponentType.SERVICE
        elif "/tool/" in path_str or "\\tool\\" in path_str:
            return ComponentType.TOOL
        elif "/behavior/" in path_str or "\\behavior\\" in path_str:
            return ComponentType.BEHAVIOR
        else:
            return ComponentType.SKILL

    def _infer_direction_from_filename(self, file_path: Path) -> Optional[str]:
        """Определение направления контракта из имени файла."""
        filename = file_path.stem.lower()

        if "_input" in filename or filename.startswith("input_"):
            return "input"
        elif "_output" in filename or filename.startswith("output_"):
            return "output"

        # Проверяем родительскую директорию
        parent_name = file_path.parent.name.lower()
        if "input" in parent_name:
            return "input"
        elif "output" in parent_name:
            return "output"

        return None

    def _parse_contract_filename(
        self, file_path: Path
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Парсинг capability, version, direction из имени файла контракта.

        Форматы:
        - {capability}_{direction}_{version}.yaml
        - {direction}_{version}.yaml
        """
        filename = file_path.stem

        # Паттерн для версии: v1.0.0
        version_match = re.search(r"_v(\d+\.\d+\.\d+)$", filename)

        if version_match:
            version = f"v{version_match.group(1)}"
            base_name = filename[:version_match.start()]

            direction = None
            if base_name.endswith("_input"):
                direction = "input"
                capability = base_name[:-6]
            elif base_name.endswith("_output"):
                direction = "output"
                capability = base_name[:-7]
            elif base_name.startswith("input_"):
                direction = "input"
                capability = base_name[6:]
            elif base_name.startswith("output_"):
                direction = "output"
                capability = base_name[7:]
            else:
                capability = base_name

            return capability, version, direction

        return None, None, None

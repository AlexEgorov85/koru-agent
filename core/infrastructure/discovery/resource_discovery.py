"""
Авто-обнаружение ресурсов через файловую систему.

Этот модуль предоставляет классы для сканирования файловой системы
и загрузки ресурсов (промптов, контрактов, манифестов) с фильтрацией по статусам.

Принципы:
- prod → только status: active
- sandbox → status: active + draft
- dev → status: active + draft + inactive
"""
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime

from core.models.data.prompt import Prompt, PromptStatus
from core.models.data.contract import Contract, ContractDirection
from core.models.enums.common_enums import ComponentType, ComponentStatus
from core.infrastructure.logging import EventBusLogger


class ResourceDiscovery:
    """
    Авто-обнаружение ресурсов через файловую систему.

    Сканзирует директорию data/ и загружает ресурсы с разрешёнными статусами
    в зависимости от профиля работы.
    """

    # Маппинг профилей на разрешённые статусы
    PROFILE_STATUS_MAP: Dict[str, List[PromptStatus]] = {
        'prod': [PromptStatus.ACTIVE],
        'sandbox': [PromptStatus.ACTIVE, PromptStatus.DRAFT],
        'dev': [PromptStatus.ACTIVE, PromptStatus.DRAFT, PromptStatus.INACTIVE],
    }

    # Маппинг статусов компонентов
    COMPONENT_STATUS_MAP: Dict[str, List[ComponentStatus]] = {
        'prod': [ComponentStatus.ACTIVE],
        'sandbox': [ComponentStatus.ACTIVE, ComponentStatus.DRAFT],
        'dev': [ComponentStatus.ACTIVE, ComponentStatus.DRAFT, ComponentStatus.INACTIVE],
    }

    def __init__(self, base_dir: Path, profile: str = 'prod', event_bus=None):
        """
        Инициализация сканера ресурсов.

        ПАРАМЕТРЫ:
        - base_dir: Базовая директория данных (обычно data/)
        - profile: Профиль работы ('prod', 'sandbox', 'dev')
        - event_bus: Шина событий для логирования (опционально)
        """
        self.base_dir = Path(base_dir)
        self.profile = profile
        self.allowed_prompt_statuses = self.PROFILE_STATUS_MAP.get(
            profile, self.PROFILE_STATUS_MAP['prod']
        )
        self.allowed_component_statuses = self.COMPONENT_STATUS_MAP.get(
            profile, self.COMPONENT_STATUS_MAP['prod']
        )

        # Кэши загруженных ресурсов
        self._prompts_cache: Dict[Tuple[str, str], Prompt] = {}
        self._contracts_cache: Dict[Tuple[str, str, str], Contract] = {}

        # Статистика
        self._stats = {
            'prompts_scanned': 0,
            'prompts_loaded': 0,
            'prompts_skipped': 0,
            'contracts_scanned': 0,
            'contracts_loaded': 0,
            'contracts_skipped': 0,
        }

        # Инициализация логгера
        if event_bus is not None:
            self.logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="ResourceDiscovery")
            self._use_event_logging = True
        else:
            import logging
            self.logger = logging.getLogger(__name__)
            self._use_event_logging = False

        self._log_info(f"ResourceDiscovery инициализирован: base_dir={self.base_dir}, profile={self.profile}")

    def _log_info(self, message: str, *args, **kwargs):
        """Информационное сообщение."""
        if self._use_event_logging:
            self.logger.info_sync(message, *args, **kwargs)
        else:
            self.logger.info(message, *args, **kwargs)

    def _log_debug(self, message: str, *args, **kwargs):
        """Отладочное сообщение."""
        if self._use_event_logging:
            self.logger.debug_sync(message, *args, **kwargs)
        else:
            self.logger.debug(message, *args, **kwargs)

    def _log_warning(self, message: str, *args, **kwargs):
        """Предупреждение."""
        if self._use_event_logging:
            self.logger.warning_sync(message, *args, **kwargs)
        else:
            self.logger.warning(message, *args, **kwargs)

    def _log_error(self, message: str, *args, **kwargs):
        """Ошибка."""
        if self._use_event_logging:
            self.logger.error_sync(message, *args, **kwargs)
        else:
            self.logger.error(message, *args, **kwargs)
    
    def _should_load_resource(self, status: str, resource_type: str = 'prompt') -> bool:
        """
        Проверка можно ли загружать ресурс с данным статусом.

        ПАРАМЕТРЫ:
        - status: Статус ресурса
        - resource_type: Тип ресурса ('prompt', 'contract', 'component')

        ВОЗВРАЩАЕТ:
        - bool: True если ресурс можно загружать
        """
        try:
            if resource_type in ('prompt', 'contract'):
                prompt_status = PromptStatus(status)
                return prompt_status in self.allowed_prompt_statuses
            elif resource_type == 'component':
                component_status = ComponentStatus(status)
                return component_status in self.allowed_component_statuses
            else:
                self._log_warning(f"Неизвестный тип ресурса: {resource_type}")
                return False
        except ValueError:
            self._log_warning(f"Неизвестный статус '{status}' для {resource_type}")
            return False
    
    def _parse_prompt_file(self, file_path: Path) -> Optional[Prompt]:
        """
        Парсинг файла промпта.

        ПАРАМЕТРЫ:
        - file_path: Путь к файлу

        ВОЗВРАЩАЕТ:
        - Optional[Prompt]: Объект промпта или None при ошибке
        """
        import yaml

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                # ❌ УДАЛЕНО: Пропуск файлов с ошибками
                # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
                from core.errors.exceptions import ResourceLoadError
                raise ResourceLoadError(
                    f"Файл промпта {file_path} не содержит словарь. "
                    f"Проверьте корректность YAML формата.",
                    resource_path=str(file_path)
                )

            # Извлекаем обязательные поля
            capability = data.get('capability')
            version = data.get('version')
            status = data.get('status', 'draft')
            component_type = data.get('component_type')
            content = data.get('content', '')
            variables = data.get('variables', [])
            metadata = data.get('metadata', {})

            # Валидация обязательных полей
            if not capability or not version:
                # ❌ УДАЛЕНО: Пропуск файлов
                # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
                from core.errors.exceptions import ResourceLoadError
                raise ResourceLoadError(
                    f"Файл {file_path} не содержит capability или version. "
                    f"Это обязательные поля для промпта.",
                    resource_path=str(file_path)
                )

            # Проверяем статус
            if not self._should_load_resource(status, 'prompt'):
                # Пропускаем ресурсы с неподходящим статусом (это нормально)
                self._stats['prompts_skipped'] += 1
                return None

            # Парсинг переменных
            parsed_variables = []
            for var in variables:
                if isinstance(var, dict):
                    from core.models.data.prompt import PromptVariable
                    try:
                        parsed_variables.append(PromptVariable(**var))
                    except Exception as e:
                        # ❌ УДАЛЕНО: Пропуск ошибок парсинга переменных
                        # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
                        from core.errors.exceptions import ResourceLoadError
                        raise ResourceLoadError(
                            f"Ошибка парсинга переменной в {file_path}: {e}",
                            resource_path=str(file_path)
                        )

            # Определяем тип компонента
            if component_type:
                try:
                    comp_type = ComponentType(component_type)
                except ValueError:
                    # ❌ УДАЛЕНО: Default на SKILL
                    # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
                    from core.errors.exceptions import ResourceLoadError
                    raise ResourceLoadError(
                        f"Неизвестный тип компонента '{component_type}' в {file_path}. "
                        f"Допустимые значения: skill, service, tool, behavior",
                        resource_path=str(file_path)
                    )
            else:
                # Авто-определение по пути
                comp_type = self._infer_component_type_from_path(file_path)

            # Создаём объект Prompt
            prompt = Prompt(
                capability=capability,
                version=version,
                status=PromptStatus(status),
                component_type=comp_type,
                content=content,
                variables=parsed_variables,
                metadata=metadata
            )

            self._stats['prompts_loaded'] += 1
            return prompt

        except ResourceLoadError:
            # Пробрасываем ResourceLoadError дальше
            raise
        except Exception as e:
            # ❌ УДАЛЕНО: Пропуск файлов с ошибками
            # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
            from core.errors.exceptions import ResourceLoadError
            raise ResourceLoadError(
                f"Критическая ошибка загрузки ресурса {file_path}: {e}",
                resource_path=str(file_path)
            )

    def _parse_contract_file(self, file_path: Path) -> Optional[Contract]:
        """
        Парсинг файла контракта.

        ПАРАМЕТРЫ:
        - file_path: Путь к файлу

        ВОЗВРАЩАЕТ:
        - Optional[Contract]: Объект контракта или None при ошибке
        """
        import yaml
        import re

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                # ❌ УДАЛЕНО: Пропуск файлов с ошибками
                # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
                from core.errors.exceptions import ResourceLoadError
                raise ResourceLoadError(
                    f"Файл контракта {file_path} не содержит словарь. "
                    f"Проверьте корректность YAML формата.",
                    resource_path=str(file_path)
                )

            # Извлекаем поля
            capability = data.get('capability')
            version = data.get('version')
            status = data.get('status', 'draft')
            component_type = data.get('component_type')
            direction = data.get('direction')
            schema_data = data.get('schema', data.get('schema_data', {}))
            description = data.get('description', '')

            # Если capability/version не указаны в файле, пытаемся извлечь из имени файла
            if not capability or not version:
                capability, version, direction = self._parse_contract_filename(file_path)

            if not capability or not version:
                # ❌ УДАЛЕНО: Пропуск файлов
                # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
                from core.errors.exceptions import ResourceLoadError
                raise ResourceLoadError(
                    f"Не удалось определить capability/version для {file_path}. "
                    f"Укажите их в файле или используйте формат имени файла {{capability}}_{{direction}}_{{version}}.yaml",
                    resource_path=str(file_path)
                )

            # Проверяем статус
            if not self._should_load_resource(status, 'contract'):
                # Пропускаем ресурсы с неподходящим статусом (это нормально)
                self._stats['contracts_skipped'] += 1
                return None

            # Определяем направление если не указано
            if not direction:
                direction = self._infer_direction_from_filename(file_path)

            if not direction:
                # ❌ УДАЛЕНО: Пропуск файлов
                # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
                from core.errors.exceptions import ResourceLoadError
                raise ResourceLoadError(
                    f"Не удалось определить направление контракта для {file_path}. "
                    f"Используйте формат имени файла {{capability}}_{{direction}}_{{version}}.yaml "
                    f"или укажите direction: input|output в файле.",
                    resource_path=str(file_path)
                )

            # Определяем тип компонента
            if component_type:
                try:
                    comp_type = ComponentType(component_type)
                except ValueError:
                    # ❌ УДАЛЕНО: Default на SKILL
                    # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
                    from core.errors.exceptions import ResourceLoadError
                    raise ResourceLoadError(
                        f"Неизвестный тип компонента '{component_type}' в {file_path}. "
                        f"Допустимые значения: skill, service, tool, behavior",
                        resource_path=str(file_path)
                    )
            else:
                comp_type = self._infer_component_type_from_path(file_path)

            # Создаём объект Contract
            contract = Contract(
                capability=capability,
                version=version,
                status=PromptStatus(status),
                component_type=comp_type,
                direction=ContractDirection(direction),
                schema_data=schema_data if schema_data else {'type': 'object', 'properties': {}},
                description=description
            )

            self._stats['contracts_loaded'] += 1
            return contract

        except ResourceLoadError:
            # Пробрасываем ResourceLoadError дальше
            raise
        except Exception as e:
            # ❌ УДАЛЕНО: Пропуск файлов с ошибками
            # ✅ ТЕПЕРЬ: Выбрасываем ResourceLoadError
            from core.errors.exceptions import ResourceLoadError
            raise ResourceLoadError(
                f"Критическая ошибка загрузки ресурса {file_path}: {e}",
                resource_path=str(file_path)
            )

    # === Метод _parse_manifest_file() удалён ===
    # Манифесты удалены из системы

    def _infer_component_type_from_path(self, file_path: Path) -> ComponentType:
        """
        Авто-определение типа компонента по пути к файлу.
        
        ПАРАМЕТРЫ:
        - file_path: Путь к файлу
        
        ВОЗВРАЩАЕТ:
        - ComponentType: Тип компонента
        """
        path_str = str(file_path).lower()
        
        if '/skill/' in path_str or '\\skill\\' in path_str:
            return ComponentType.SKILL
        elif '/service/' in path_str or '\\service\\' in path_str:
            return ComponentType.SERVICE
        elif '/tool/' in path_str or '\\tool\\' in path_str:
            return ComponentType.TOOL
        elif '/behavior/' in path_str or '\\behavior\\' in path_str:
            return ComponentType.BEHAVIOR
        else:
            return ComponentType.SKILL  # Default
    
    def _infer_direction_from_filename(self, file_path: Path) -> Optional[str]:
        """
        Определение направления контракта (input/output) из имени файла.
        
        ПАРАМЕТРЫ:
        - file_path: Путь к файлу
        
        ВОЗВРАЩАЕТ:
        - Optional[str]: Направление или None
        """
        filename = file_path.stem.lower()
        
        if '_input' in filename or filename.startswith('input_'):
            return 'input'
        elif '_output' in filename or filename.startswith('output_'):
            return 'output'
        
        # Проверяем родительскую директорию
        parent_name = file_path.parent.name.lower()
        if 'input' in parent_name:
            return 'input'
        elif 'output' in parent_name:
            return 'output'
        
        return None
    
    def _parse_contract_filename(self, file_path: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Парсинг capability, version, direction из имени файла контракта.
        
        Форматы:
        - {capability}_{direction}_{version}.yaml
        - {direction}_{version}.yaml
        - {version}_{direction}.yaml
        
        ПАРАМЕТРЫ:
        - file_path: Путь к файлу
        
        ВОЗВРАЩАЕТ:
        - Tuple[capability, version, direction]
        """
        filename = file_path.stem  # Без расширения
        
        # Паттерн для версии: v1.0.0, v1.2.3
        import re
        version_match = re.search(r'_v(\d+\.\d+\.\d+)$', filename)
        
        if version_match:
            version = f"v{version_match.group(1)}"
            base_name = filename[:version_match.start()]
            
            # Проверяем направление
            direction = None
            if base_name.endswith('_input'):
                direction = 'input'
                capability = base_name[:-6]  # Удаляем '_input'
            elif base_name.endswith('_output'):
                direction = 'output'
                capability = base_name[:-7]  # Удаляем '_output'
            elif base_name.startswith('input_'):
                direction = 'input'
                capability = base_name[6:]
            elif base_name.startswith('output_'):
                direction = 'output'
                capability = base_name[7:]
            else:
                capability = base_name
            
            return capability, version, direction
        
        return None, None, None
    
    def discover_prompts(self) -> List[Prompt]:
        """
        Сканирование и загрузка всех промптов с разрешёнными статусами.

        ВОЗВРАЩАЕТ:
        - List[Prompt]: Список загруженных промптов
        """
        # ✅ Возвращаем из кэша если уже загружено (блокировка повторной загрузки)
        if self._prompts_cache:
            self._log_debug(f"discover_prompts: возвращаем из кэша {len(self._prompts_cache)} промптов")
            return list(self._prompts_cache.values())

        prompts = []
        prompts_dir = self.base_dir / 'prompts'

        if not prompts_dir.exists():
            self._log_warning(f"Директория промптов не найдена: {prompts_dir}")
            return prompts

        # Рекурсивный поиск всех YAML файлов
        yaml_files = list(prompts_dir.rglob('*.yaml')) + list(prompts_dir.rglob('*.yml'))

        self._stats['prompts_scanned'] = len(yaml_files)

        for file_path in yaml_files:
            prompt = self._parse_prompt_file(file_path)
            if prompt:
                key = (prompt.capability, prompt.version)
                self._prompts_cache[key] = prompt
                prompts.append(prompt)

        self._log_info(f"✅ Загружено {len(prompts)} промптов (просканировано: {self._stats['prompts_scanned']}, пропущено: {self._stats['prompts_skipped']})")
        return prompts

    def discover_contracts(self) -> List[Contract]:
        """
        Сканирование и загрузка всех контрактов с разрешёнными статусами.

        ВОЗВРАЩАЕТ:
        - List[Contract]: Список загруженных контрактов
        """
        # ✅ Возвращаем из кэша если уже загружено (блокировка повторной загрузки)
        if self._contracts_cache:
            self._log_debug(f"discover_contracts: возвращаем из кэша {len(self._contracts_cache)} контрактов")
            return list(self._contracts_cache.values())

        contracts = []
        contracts_dir = self.base_dir / 'contracts'

        if not contracts_dir.exists():
            self._log_warning(f"Директория контрактов не найдена: {contracts_dir}")
            return contracts

        # Рекурсивный поиск всех YAML файлов
        yaml_files = list(contracts_dir.rglob('*.yaml')) + list(contracts_dir.rglob('*.yml'))

        self._stats['contracts_scanned'] = len(yaml_files)

        for file_path in yaml_files:
            contract = self._parse_contract_file(file_path)
            if contract:
                key = (contract.capability, contract.version, contract.direction.value)
                self._contracts_cache[key] = contract
                contracts.append(contract)

        self._log_info(f"✅ Загружено {len(contracts)} контрактов (просканировано: {self._stats['contracts_scanned']}, пропущено: {self._stats['contracts_skipped']})")
        return contracts

    # === Метод discover_manifests() удалён ===
    # Манифесты удалены из системы. Зависимости объявляются через DEPENDENCIES в коде компонентов.
    
    def get_prompt(self, capability: str, version: str) -> Optional[Prompt]:
        """
        Получение конкретного промпта из кэша.
        
        ПАРАМЕТРЫ:
        - capability: Имя capability
        - version: Версия
        
        ВОЗВРАЩАЕТ:
        - Optional[Prompt]: Объект промпта или None
        """
        return self._prompts_cache.get((capability, version))
    
    def get_contract(
        self,
        capability: str,
        version: str,
        direction: str
    ) -> Optional[Contract]:
        """
        Получение конкретного контракта из кэша.
        
        ПАРАМЕТРЫ:
        - capability: Имя capability
        - version: Версия
        - direction: Направление (input/output)
        
        ВОЗВРАЩАЕТ:
        - Optional[Contract]: Объект контракта или None
        """
        return self._contracts_cache.get((capability, version, direction))

    # === Метод get_manifest() удалён ===
    # Манифесты удалены из системы
    
    def get_stats(self) -> Dict[str, int]:
        """
        Получение статистики сканирования.
        
        ВОЗВРАЩАЕТ:
        - Dict[str, int]: Статистика
        """
        return self._stats.copy()
    
    def get_validation_report(self) -> str:
        """
        Формирование отчёта о валидации.

        ВОЗВРАЩАЕТ:
        - str: Текстовый отчёт
        """
        lines = [
            "=" * 60,
            "ОТЧЁТ RESOURCE DISCOVERY",
            "=" * 60,
            f"Профиль: {self.profile}",
            f"Базовая директория: {self.base_dir}",
            "",
            "Промпты:",
            f"  - Просканировано файлов: {self._stats['prompts_scanned']}",
            f"  - Загружено: {self._stats['prompts_loaded']}",
            f"  - Пропущено (статус): {self._stats['prompts_skipped']}",
            "",
            "Контракты:",
            f"  - Просканировано файлов: {self._stats['contracts_scanned']}",
            f"  - Загружено: {self._stats['contracts_loaded']}",
            f"  - Пропущено (статус): {self._stats['contracts_skipped']}",
            "",
            "Манифесты: удалены из системы",
            "=" * 60,
        ]
        return "\n".join(lines)

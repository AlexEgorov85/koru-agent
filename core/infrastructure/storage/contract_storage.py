"""
Хранилище контрактов - только загрузка из файловой системы.
НЕ содержит кэширования - кэширование происходит в прикладном слое.
"""
from pathlib import Path
from typing import Optional
import json
import yaml
import logging
from core.models.data.contract import Contract
from core.models.errors.version_not_found import VersionNotFoundError
from core.infrastructure.interfaces.storage_interfaces import IContractStorage, ComponentType


class ContractStorage(IContractStorage):
    """
    Хранилище контрактов БЕЗ кэширования.
    Единственный источник истины для контрактов.
    Создаётся ОДИН раз в InfrastructureContext.
    """
    
    def __init__(self, contracts_dir: Path):
        self.contracts_dir = contracts_dir.resolve()
        self._validate_directory()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info(f"ContractStorage инициализировано: {self.contracts_dir}")
    
    def _validate_directory(self):
        if not self.contracts_dir.exists():
            self.contracts_dir.mkdir(parents=True, exist_ok=True)
        if not self.contracts_dir.is_dir():
            raise ValueError(f"Путь не является директорией: {self.contracts_dir}")
    
    async def load(self, capability_name: str, version: str, direction: str, component_type: Optional['ComponentType'] = None) -> Contract:
        """
        Загружает контракт из файловой системы.
        Вызывается ТОЛЬКО при инициализации ApplicationContext.
        """
        # Определяем возможные подкаталоги для поиска
        # Если указан component_type, используем его для более точного поиска
        if component_type:
            # Используем компонент-специфичные подкаталоги
            if component_type == ComponentType.SKILL:
                standard_subdirs = ['skills']
            elif component_type == ComponentType.SERVICE:
                standard_subdirs = ['services']
            elif component_type == ComponentType.TOOL:
                standard_subdirs = ['tools']
            elif component_type == ComponentType.SQL_GENERATION:
                standard_subdirs = ['sql_generation']
            elif component_type == ComponentType.CONTRACT:
                standard_subdirs = ['contracts']
            elif component_type == ComponentType.BEHAVIOR:
                standard_subdirs = ['behaviors']
            else:
                # DEFAULT или неизвестный тип - используем все стандартные подкаталоги
                standard_subdirs = ['skills', 'services', 'contracts', 'behaviors']
        else:
            # Если тип компонента не указан, используем все стандартные подкаталоги
            standard_subdirs = ['skills', 'services', 'contracts', 'behaviors']

        # Разбиваем capability_name на части
        parts = capability_name.split('.')
        subdir_specific_files = []  # Инициализируем здесь, чтобы избежать ошибки UnboundLocalError
        if len(parts) >= 2:
            category = parts[0]  # например, "planning"
            specific = parts[1]  # например, "create_plan"

            # Проверяем в компонент-специфичных подкаталогах
            for subdir in standard_subdirs:
                # Используем оба формата: {category}_{specific}_{direction}_{version}.yaml и {category}_{specific}_{version}.yaml
                # Формат 1: {category}_{specific}_{direction}_{version}.yaml (например, planning_create_plan_input_v1.0.0.yaml)
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{direction}_{version}.json")
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{direction}_{version}.yaml")
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{direction}_{version}.yml")
                # Формат 2: {category}_{specific}_{version}.yaml (например, llm_generate_input_v1.0.0.yaml)
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{version}.json")
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{version}.yaml")
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{version}.yml")
        else:
            # Если только одна часть, используем как есть
            category = capability_name  # например, "planning"
            specific = ""  # нет конкретного подтипа

        # Проверяем в подкаталоге категории (например, planning/ если он существует)
        category_specific_json = self.contracts_dir / category / f"{specific}_{direction}_{version}.json" if specific else self.contracts_dir / category / f"{direction}_{version}.json"
        category_specific_yaml = self.contracts_dir / category / f"{specific}_{direction}_{version}.yaml" if specific else self.contracts_dir / category / f"{direction}_{version}.yaml"
        category_specific_yml = self.contracts_dir / category / f"{specific}_{direction}_{version}.yml" if specific else self.contracts_dir / category / f"{direction}_{version}.yml"

        # Проверяем сначала JSON файлы в основном пути (по умолчанию не используется, но оставим для совместимости)
        # Используем capability_name с точками как путь к поддиректории
        capability_path_parts = capability_name.split('.')
        if len(capability_path_parts) >= 2:
            # Для формата category.capability используем подкаталоги
            capability_subpath = Path(*capability_path_parts)
        else:
            # Для одиночных имен используем как есть
            capability_subpath = Path(capability_name)

        contract_file_json = self.contracts_dir / capability_subpath / f"{version}_{direction}.json"
        contract_file_yaml = self.contracts_dir / capability_subpath / f"{version}_{direction}.yaml"
        contract_file_yml = self.contracts_dir / capability_subpath / f"{version}_{direction}.yml"

        # Альтернативные форматы (плоская структура)
        alt_file_json = self.contracts_dir / f"{capability_name.replace('.', '_')}_{direction}_{version}.json"
        alt_file_yaml = self.contracts_dir / f"{capability_name.replace('.', '_')}_{direction}_{version}.yaml"
        alt_file_yml = self.contracts_dir / f"{capability_name.replace('.', '_')}_{direction}_{version}.yml"

        # Проверяем файлы в порядке приоритета
        files_to_check = [
            contract_file_json, contract_file_yaml, contract_file_yml,
            alt_file_json, alt_file_yaml, alt_file_yml
        ]

        # Добавляем файлы из подкаталогов (компонент-специфичные)
        files_to_check.extend(subdir_specific_files)

        # Добавляем файлы из подкаталога категории (например, planning/ если он существует)
        if specific and category_specific_json:
            files_to_check.extend([category_specific_json, category_specific_yaml, category_specific_yml])
        elif not specific and 'category_specific_json' in locals() and category_specific_json:
            files_to_check.extend([category_specific_json, category_specific_yaml, category_specific_yml])

        contract_file = None
        file_format = None

        for file_path in files_to_check:
            if file_path and file_path.exists():
                contract_file = file_path
                if file_path.suffix.lower() == '.json':
                    file_format = 'json'
                elif file_path.suffix.lower() in ['.yaml', '.yml']:
                    file_format = 'yaml'
                break

        if contract_file is None:
            # Определяем значение для логирования в случае ошибки
            cat_spec_json = category_specific_json if 'category_specific_json' in locals() else 'N/A'
            cat_spec_yaml = category_specific_yaml if 'category_specific_yaml' in locals() else 'N/A'
            cat_spec_yml = category_specific_yml if 'category_specific_yml' in locals() else 'N/A'
            
            raise VersionNotFoundError(
                f"Контракт не найден: capability={capability_name}, version={version}, "
                f"direction={direction}, component_type={component_type}\n"
                f"Проверьте пути:\n  1. {contract_file_json}\n  2. {contract_file_yaml}\n  3. {contract_file_yml}\n"
                f"  4. {alt_file_json}\n  5. {alt_file_yaml}\n  6. {alt_file_yml}\n"
                f"  7+ Component-specific subdirectory files ({', '.join(standard_subdirs)})\n"
                f"  8. {cat_spec_json}\n  9. {cat_spec_yaml}\n 10. {cat_spec_yml}"
            )

        try:
            with open(contract_file, "r", encoding="utf-8") as f:
                if file_format == 'json':
                    import json
                    data = json.load(f)
                elif file_format == 'yaml':
                    import yaml
                    data = yaml.safe_load(f)

            # Проверяем, является ли файл новым форматом (с полной информацией) или старым (с метаданными)
            if isinstance(data, dict) and all(key in data for key in ['capability_name', 'version', 'direction', 'schema']):
                # Новый формат: файл содержит полный объект Contract
                return Contract(
                    capability_name=data['capability_name'],
                    version=data['version'],
                    direction=data['direction'],
                    schema_data=data['schema']
                )
            else:
                # Старый формат: файл содержит метаданные и схему (schema поле внутри)
                # Извлекаем только схему, игнорируя другие метаданные
                schema_data = data.get('schema', data) if isinstance(data, dict) else data
                return Contract(
                    capability_name=capability_name,
                    version=version,
                    direction=direction,
                    schema_data=schema_data
                )
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ошибка парсинга JSON контракта {capability_name}@{version} ({direction}): {e}")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Ошибка парсинга YAML контракта {capability_name}@{version} ({direction}): {e}")
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки контракта {capability_name}@{version} ({direction}): {e}")

    async def exists(self, capability_name: str, version: str, direction: str, component_type: Optional['ComponentType'] = None) -> bool:
        """Проверяет существование контракта без загрузки содержимого."""
        # Определяем возможные подкаталоги для поиска
        # Если указан component_type, используем его для более точного поиска
        if component_type:
            # Используем компонент-специфичные подкаталоги
            if component_type == ComponentType.SKILL:
                standard_subdirs = ['skills']
            elif component_type == ComponentType.SERVICE:
                standard_subdirs = ['services']
            elif component_type == ComponentType.TOOL:
                standard_subdirs = ['tools']
            elif component_type == ComponentType.SQL_GENERATION:
                standard_subdirs = ['sql_generation']
            elif component_type == ComponentType.CONTRACT:
                standard_subdirs = ['contracts']
            elif component_type == ComponentType.BEHAVIOR:
                standard_subdirs = ['behaviors']
            else:
                # DEFAULT или неизвестный тип - используем все стандартные подкаталоги
                standard_subdirs = ['skills', 'services', 'contracts', 'behaviors']
        else:
            # Если тип компонента не указан, используем все стандартные подкаталоги
            standard_subdirs = ['skills', 'services', 'contracts', 'behaviors']

        # Определяем возможные подкаталоги для поиска
        parts = capability_name.split('.')
        if len(parts) >= 2:
            category = parts[0]  # например, "planning"
            specific = parts[1]  # например, "create_plan"

            # Проверяем в компонент-специфичных подкаталогах
            subdir_specific_files = []
            for subdir in standard_subdirs:
                # Используем оба формата: {category}_{specific}_{direction}_{version}.yaml и {category}_{specific}_{version}.yaml
                # Формат 1: {category}_{specific}_{direction}_{version}.yaml (например, planning_create_plan_input_v1.0.0.yaml)
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{direction}_{version}.json")
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{direction}_{version}.yaml")
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{direction}_{version}.yml")
                # Формат 2: {category}_{specific}_{version}.yaml (например, llm_generate_input_v1.0.0.yaml)
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{version}.json")
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{version}.yaml")
                subdir_specific_files.append(self.contracts_dir / subdir / category / f"{category}_{specific}_{version}.yml")
        else:
            # Если только одна часть, используем как есть
            category = capability_name  # например, "planning"
            specific = ""  # нет конкретного подтипа
            subdir_specific_files = []

        # Проверяем в подкаталоге категории (например, planning/ если он существует)
        category_specific_json = self.contracts_dir / category / f"{specific}_{direction}_{version}.json" if specific else self.contracts_dir / category / f"{direction}_{version}.json"
        category_specific_yaml = self.contracts_dir / category / f"{specific}_{direction}_{version}.yaml" if specific else self.contracts_dir / category / f"{direction}_{version}.yaml"
        category_specific_yml = self.contracts_dir / category / f"{specific}_{direction}_{version}.yml" if specific else self.contracts_dir / category / f"{direction}_{version}.yml"

        # Проверяем сначала JSON файлы в основном пути (по умолчанию не используется, но оставим для совместимости)
        # Используем capability_name с точками как путь к поддиректории
        capability_path_parts = capability_name.split('.')
        if len(capability_path_parts) >= 2:
            # Для формата category.capability используем подкаталоги
            capability_subpath = Path(*capability_path_parts)
        else:
            # Для одиночных имен используем как есть
            capability_subpath = Path(capability_name)

        contract_file_json = self.contracts_dir / capability_subpath / f"{version}_{direction}.json"
        contract_file_yaml = self.contracts_dir / capability_subpath / f"{version}_{direction}.yaml"
        contract_file_yml = self.contracts_dir / capability_subpath / f"{version}_{direction}.yml"

        # Альтернативные форматы (плоская структура)
        alt_file_json = self.contracts_dir / f"{capability_name.replace('.', '_')}_{direction}_{version}.json"
        alt_file_yaml = self.contracts_dir / f"{capability_name.replace('.', '_')}_{direction}_{version}.yaml"
        alt_file_yml = self.contracts_dir / f"{capability_name.replace('.', '_')}_{direction}_{version}.yml"

        # Проверяем файлы в порядке приоритета
        files_to_check = [
            contract_file_json, contract_file_yaml, contract_file_yml,
            alt_file_json, alt_file_yaml, alt_file_yml
        ]

        # Добавляем файлы из подкаталогов (компонент-специфичные)
        files_to_check.extend(subdir_specific_files)

        # Добавляем файлы из подкаталога категории (например, planning/ если он существует)
        if specific and category_specific_json:
            files_to_check.extend([category_specific_json, category_specific_yaml, category_specific_yml])
        elif not specific and 'category_specific_json' in locals() and category_specific_json:
            files_to_check.extend([category_specific_json, category_specific_yaml, category_specific_yml])

        result = any(file_path.exists() for file_path in files_to_check if file_path)

        return result

    async def save(self, capability_name: str, version: str, direction: str, contract: Contract, component_type: Optional['ComponentType'] = None) -> None:
        """Сохраняет контракт в файловую систему."""
        # Определяем директорию для сохранения в зависимости от типа компонента
        if component_type:
            if component_type == ComponentType.SKILL:
                save_dir = self.contracts_dir / 'skills'
            elif component_type == ComponentType.SERVICE:
                save_dir = self.contracts_dir / 'services'
                save_dir = self.contracts_dir / 'strategies'
            elif component_type == ComponentType.TOOL:
                save_dir = self.contracts_dir / 'tools'
            elif component_type == ComponentType.SQL_GENERATION:
                save_dir = self.contracts_dir / 'sql_generation'
            elif component_type == ComponentType.CONTRACT:
                save_dir = self.contracts_dir / 'contracts'
            else:
                # DEFAULT или неизвестный тип - используем основной путь
                save_dir = self.contracts_dir
        else:
            # Если тип компонента не указан, используем основной путь
            save_dir = self.contracts_dir

        # Разбиваем capability_name на части для создания подкаталогов
        parts = capability_name.split('.')
        if len(parts) >= 2:
            category = parts[0]  # например, "planning"
            specific = parts[1]  # например, "create_plan"

            # Создаем подкаталог: save_dir/category/
            capability_dir = save_dir / category
        else:
            # Если только одна часть, используем как есть
            category = parts[0] if parts else capability_name
            capability_dir = save_dir / category

        capability_dir.mkdir(parents=True, exist_ok=True)

        # Определяем путь к файлу (по умолчанию используем YAML)
        # Формат: {specific}_{direction}_{version}.yaml (например, create_plan_input_v1.0.0.yaml)
        if len(parts) >= 2:
            specific = parts[1]
            contract_file = capability_dir / f"{specific}_{direction}_{version}.yaml"
        else:
            # Если только одна часть, используем только направление и версию
            contract_file = capability_dir / f"{direction}_{version}.yaml"

        # Подготовим данные для сохранения
        contract_dict = contract.model_dump()
        
        # Сохраняем в YAML формате
        import yaml
        with open(contract_file, 'w', encoding='utf-8') as f:
            yaml.dump(contract_dict, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        self.logger.info(f"Контракт сохранен: {capability_name}@{version} ({direction}) ({component_type}) -> {contract_file}")
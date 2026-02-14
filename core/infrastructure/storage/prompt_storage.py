"""
Хранилище промптов - только загрузка из файловой системы.
НЕ содержит кэширования - кэширование происходит в прикладном слое.
"""
from pathlib import Path
from typing import Optional
import json
import yaml
import logging
from core.models.prompt import Prompt, PromptMetadata
from core.errors.version_not_found import VersionNotFoundError
from core.infrastructure.interfaces.storage_interfaces import IPromptStorage


class PromptStorage(IPromptStorage):
    """
    Хранилище промптов БЕЗ кэширования.
    Единственный источник истины для промптов.
    Создаётся ОДИН раз в InfrastructureContext.
    """

    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir.resolve()
        self._validate_directory()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info(f"PromptStorage инициализировано: {self.prompts_dir}")

    def _validate_directory(self):
        if not self.prompts_dir.exists():
            self.prompts_dir.mkdir(parents=True, exist_ok=True)
        if not self.prompts_dir.is_dir():
            raise ValueError(f"Путь не является директорией: {self.prompts_dir}")

    async def load(self, capability_name: str, version: str, component_type: Optional['ComponentType'] = None) -> Prompt:
        """
        Загружает промпт из файловой системы.
        Вызывается ТОЛЬКО при инициализации ApplicationContext.
        """
        # Поддержка обоих форматов путей: точки → слэши
        capability_path = capability_name.replace(".", "/")

        # Определяем возможные подкаталоги для поиска
        # Если указан component_type, используем его для более точного поиска
        if component_type:
            # Используем компонент-специфичные подкаталоги
            if component_type == ComponentType.SKILL:
                standard_subdirs = ['skills']
            elif component_type == ComponentType.SERVICE:
                standard_subdirs = ['services']
            elif component_type == ComponentType.STRATEGY:
                standard_subdirs = ['strategies']
            elif component_type == ComponentType.TOOL:
                standard_subdirs = ['tools']
            elif component_type == ComponentType.SQL_GENERATION:
                standard_subdirs = ['sql_generation']
            elif component_type == ComponentType.CONTRACT:
                standard_subdirs = ['contracts']
            else:
                # DEFAULT или неизвестный тип - используем все стандартные подкаталоги
                standard_subdirs = ['skills', 'strategies', 'sql_generation', 'contracts']
        else:
            # Если тип компонента не указан, используем все стандартные подкаталоги
            standard_subdirs = ['skills', 'strategies', 'sql_generation', 'contracts']

        # Разбиваем capability_name на части
        parts = capability_name.split('.')
        if len(parts) >= 2:
            category = parts[0]  # например, "planning"
            specific = parts[1]  # например, "create_plan"

            # Проверяем в компонент-специфичных подкаталогах
            subdir_specific_files = []
            for subdir in standard_subdirs:
                subdir_specific_files.append(self.prompts_dir / subdir / category / f"{specific}_{version}.json")
                subdir_specific_files.append(self.prompts_dir / subdir / category / f"{specific}_{version}.yaml")
                subdir_specific_files.append(self.prompts_dir / subdir / category / f"{specific}_{version}.yml")
        else:
            # Если только одна часть, используем как есть
            category = parts[0]  # например, "planning"
            specific = ""  # нет конкретного подтипа
            subdir_specific_files = []

        # Проверяем в подкаталоге категории (например, planning/ если он существует)
        if specific:
            category_specific_json = self.prompts_dir / category / f"{specific}_{version}.json"
            category_specific_yaml = self.prompts_dir / category / f"{specific}_{version}.yaml"
            category_specific_yml = self.prompts_dir / category / f"{specific}_{version}.yml"
        else:
            category_specific_json = self.prompts_dir / category / f"{version}.json"
            category_specific_yaml = self.prompts_dir / category / f"{version}.yaml"
            category_specific_yml = self.prompts_dir / category / f"{version}.yml"

        # Проверяем сначала JSON файлы в основном пути
        prompt_file_json = self.prompts_dir / capability_path / f"{version}.json"
        prompt_file_yaml = self.prompts_dir / capability_path / f"{version}.yaml"
        prompt_file_yml = self.prompts_dir / capability_path / f"{version}.yml"

        # Альтернативные форматы (плоская структура)
        alt_file_json = self.prompts_dir / f"{capability_name.replace('.', '_')}_{version}.json"
        alt_file_yaml = self.prompts_dir / f"{capability_name.replace('.', '_')}_{version}.yaml"
        alt_file_yml = self.prompts_dir / f"{capability_name.replace('.', '_')}_{version}.yml"

        # Проверяем файлы в порядке приоритета
        files_to_check = [
            prompt_file_json, prompt_file_yaml, prompt_file_yml,
            alt_file_json, alt_file_yaml, alt_file_yml
        ]

        # Добавляем файлы из подкаталогов (компонент-специфичные)
        files_to_check.extend(subdir_specific_files)

        # Добавляем файлы из подкаталога категории (например, planning/ если он существует)
        if category_specific_json:
            files_to_check.extend([category_specific_json, category_specific_yaml, category_specific_yml])

        prompt_file = None
        file_format = None

        for file_path in files_to_check:
            if file_path and file_path.exists():
                prompt_file = file_path
                if file_path.suffix.lower() == '.json':
                    file_format = 'json'
                elif file_path.suffix.lower() in ['.yaml', '.yml']:
                    file_format = 'yaml'
                break

        if prompt_file is None:
            raise VersionNotFoundError(
                f"Промпт не найден: capability={capability_name}, version={version}, component_type={component_type}\n"
                f"Проверьте пути:\n  1. {prompt_file_json}\n  2. {prompt_file_yaml}\n  3. {prompt_file_yml}\n"
                f"  4. {alt_file_json}\n  5. {alt_file_yaml}\n  6. {alt_file_yml}\n"
                f"  7+ Component-specific subdirectory files ({', '.join(standard_subdirs)})\n"
                f"  8. {category_specific_json or 'N/A'}\n  9. {category_specific_yaml or 'N/A'}\n 10. {category_specific_yml or 'N/A'}"
            )

        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                if file_format == 'json':
                    data = json.load(f)
                    # Для JSON формата ожидаем структуру с вложенным metadata
                    result = Prompt(
                        content=data["content"],
                        metadata=PromptMetadata(**{
                            **data,
                            "version": version  # Убедимся, что версия установлена правильно
                        })
                    )
                    return result
                elif file_format == 'yaml':
                    data = yaml.safe_load(f)

                    # Для YAML формата структура немного отличается
                    # content находится на верхнем уровне, а остальные поля - метаданные
                    content = data.pop('content', '')

                    # Убедимся, что capability и version установлены правильно
                    data['capability'] = capability_name
                    if 'version' not in data:
                        data['version'] = version

                    result = Prompt(
                        content=content,
                        metadata=PromptMetadata(**data)
                    )
                    return result
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ошибка парсинга JSON промпта {capability_name}@{version}: {e}")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Ошибка парсинга YAML промпта {capability_name}@{version}: {e}")
        except KeyError as e:
            raise RuntimeError(f"Отсутствует обязательное поле в промпте {capability_name}@{version}: {e}")
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки промпта {capability_name}@{version}: {type(e).__name__}: {e}")

    async def exists(self, capability_name: str, version: str, component_type: Optional['ComponentType'] = None) -> bool:
        """Проверяет существование промпта без загрузки содержимого."""
        capability_path = capability_name.replace(".", "/")

        # Определяем возможные подкаталоги для поиска
        # Если указан component_type, используем его для более точного поиска
        if component_type:
            # Используем компонент-специфичные подкаталоги
            if component_type == ComponentType.SKILL:
                standard_subdirs = ['skills']
            elif component_type == ComponentType.SERVICE:
                standard_subdirs = ['services']
            elif component_type == ComponentType.STRATEGY:
                standard_subdirs = ['strategies']
            elif component_type == ComponentType.TOOL:
                standard_subdirs = ['tools']
            elif component_type == ComponentType.SQL_GENERATION:
                standard_subdirs = ['sql_generation']
            elif component_type == ComponentType.CONTRACT:
                standard_subdirs = ['contracts']
            else:
                # DEFAULT или неизвестный тип - используем все стандартные подкаталоги
                standard_subdirs = ['skills', 'strategies', 'sql_generation', 'contracts']
        else:
            # Если тип компонента не указан, используем все стандартные подкаталоги
            standard_subdirs = ['skills', 'strategies', 'sql_generation', 'contracts']

        # Определяем возможные подкаталоги для поиска
        parts = capability_name.split('.')
        if len(parts) >= 2:
            category = parts[0]  # например, "planning"
            specific = parts[1]  # например, "create_plan"

            # Проверяем в компонент-специфичных подкаталогах
            subdir_specific_files = []
            for subdir in standard_subdirs:
                subdir_specific_files.append(self.prompts_dir / subdir / category / f"{specific}_{version}.json")
                subdir_specific_files.append(self.prompts_dir / subdir / category / f"{specific}_{version}.yaml")
                subdir_specific_files.append(self.prompts_dir / subdir / category / f"{specific}_{version}.yml")
        else:
            # Если только одна часть, используем как есть
            category = parts[0]  # например, "planning"
            specific = ""  # нет конкретного подтипа
            subdir_specific_files = []

        # Проверяем в подкаталоге категории (например, planning/ если он существует)
        if specific:
            category_specific_json = self.prompts_dir / category / f"{specific}_{version}.json"
            category_specific_yaml = self.prompts_dir / category / f"{specific}_{version}.yaml"
            category_specific_yml = self.prompts_dir / category / f"{specific}_{version}.yml"
        else:
            category_specific_json = self.prompts_dir / category / f"{version}.json"
            category_specific_yaml = self.prompts_dir / category / f"{version}.yaml"
            category_specific_yml = self.prompts_dir / category / f"{version}.yml"

        # Проверяем JSON и YAML файлы
        prompt_file_json = self.prompts_dir / capability_path / f"{version}.json"
        prompt_file_yaml = self.prompts_dir / capability_path / f"{version}.yaml"
        prompt_file_yml = self.prompts_dir / capability_path / f"{version}.yml"

        # Альтернативные форматы (плоская структура)
        alt_file_json = self.prompts_dir / f"{capability_name.replace('.', '_')}_{version}.json"
        alt_file_yaml = self.prompts_dir / f"{capability_name.replace('.', '_')}_{version}.yaml"
        alt_file_yml = self.prompts_dir / f"{capability_name.replace('.', '_')}_{version}.yml"

        files_to_check = [
            prompt_file_json, prompt_file_yaml, prompt_file_yml,
            alt_file_json, alt_file_yaml, alt_file_yml
        ]

        # Добавляем файлы из подкаталогов (компонент-специфичные)
        files_to_check.extend(subdir_specific_files)

        if category_specific_json:
            files_to_check.extend([category_specific_json, category_specific_yaml, category_specific_yml])

        result = any(file_path.exists() for file_path in files_to_check if file_path)
        
        return result

    async def save(self, capability_name: str, version: str, prompt: Prompt, component_type: Optional['ComponentType'] = None) -> None:
        """Сохраняет промпт в файловую систему."""
        # Поддержка обоих форматов путей: точки → слэши
        capability_path = capability_name.replace(".", "/")

        # Определяем директорию для сохранения в зависимости от типа компонента
        if component_type:
            if component_type == ComponentType.SKILL:
                save_dir = self.prompts_dir / 'skills'
            elif component_type == ComponentType.SERVICE:
                save_dir = self.prompts_dir / 'services'
            elif component_type == ComponentType.STRATEGY:
                save_dir = self.prompts_dir / 'strategies'
            elif component_type == ComponentType.TOOL:
                save_dir = self.prompts_dir / 'tools'
            elif component_type == ComponentType.SQL_GENERATION:
                save_dir = self.prompts_dir / 'sql_generation'
            elif component_type == ComponentType.CONTRACT:
                save_dir = self.prompts_dir / 'contracts'
            else:
                # DEFAULT или неизвестный тип - используем основной путь
                save_dir = self.prompts_dir
        else:
            # Если тип компонента не указан, используем основной путь
            save_dir = self.prompts_dir

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
        # Формат: {specific}_{version}.yaml (например, create_plan_v1.0.0.yaml)
        if len(parts) >= 2:
            specific = parts[1]
            prompt_file = capability_dir / f"{specific}_{version}.yaml"
        else:
            # Если только одна часть, используем только версию
            prompt_file = capability_dir / f"{version}.yaml"

        # Подготовим данные для сохранения
        # Объединяем content и metadata в один словарь
        prompt_dict = prompt.model_dump()
        
        # Для YAML формата перемещаем content на верхний уровень
        content = prompt_dict.pop('content', '')
        metadata_dict = prompt_dict.get('metadata', {})
        
        # Объединяем метаданные с content
        yaml_data = {'content': content}
        yaml_data.update(metadata_dict)

        # Сохраняем в YAML формате
        import yaml
        with open(prompt_file, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, indent=2)

        self.logger.info(f"Промпт сохранен: {capability_name}@{version} ({component_type}) -> {prompt_file}")
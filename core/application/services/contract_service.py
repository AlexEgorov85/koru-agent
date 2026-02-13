"""
Contract Service - сервис управления контрактами с полной обратной совместимостью.

КЛЮЧЕВЫЕ ОСОБЕННОСТИ:
1. Не требует изменений в навыках — работает с существующим `parameters_schema`
2. Ленивая загрузка: контракты загружаются только при первом обращении
3. Режим «гибридный»: если контракт не найден — использует схему из Capability
4. Горячая перезагрузка (как в PromptService)
5. Поддержка конвертации Pydantic моделей в YAML и обратно
"""
from typing import Optional, Dict, Any, List, Type
from pydantic import BaseModel
from jsonschema import Draft202012Validator
import yaml
import os
from pathlib import Path
import hashlib
from datetime import datetime
import asyncio
from core.application.services.base_service import BaseService, ServiceInput, ServiceOutput
from models.capability import Capability


class ContractMeta:
    """Метаданные контракта (без самой схемы)"""
    def __init__(self, **kwargs):
        self.version = kwargs.get('version', '0.0.0')
        self.contract_type = kwargs.get('contract_type', 'capability_input')
        self.skill = kwargs.get('skill', '')
        self.capability = kwargs.get('capability', '')
        self.strategy = kwargs.get('strategy')
        self.language = kwargs.get('language', 'ru')
        self.tags = kwargs.get('tags', [])
        self.created_at = kwargs.get('created_at', datetime.now().isoformat())
        self.updated_at = kwargs.get('updated_at', datetime.now().isoformat())
        self.author = kwargs.get('author', 'system')
        self.compatibility = kwargs.get('compatibility', [])


class ContractServiceInput(ServiceInput):
    """Входные данные для ContractService"""
    def __init__(self, action: str, **kwargs):
        self.action = action  # "get_schema", "validate", "register", etc.
        self.kwargs = kwargs


class ContractServiceOutput(ServiceOutput):
    """Выходные данные для ContractService"""
    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


class ContractService(BaseService):
    """
    Сервис управления контрактами с полной обратной совместимостью.

    КЛЮЧЕВЫЕ ОСОБЕННОСТИ:
    1. Не требует изменений в навыках — работает с существующим `parameters_schema`
    2. Ленивая загрузка: контракты загружаются только при первом обращении
    3. Режим «гибридный»: если контракт не найден — использует схему из Capability
    4. Горячая перезагрузка (как в PromptService)
    5. Поддержка конвертации Pydantic моделей в YAML и обратно
    """

    @property
    def description(self) -> str:
        return "Сервис управления контрактами с версионированием и метаданными"

    def __init__(self, application_context, name="contract_service", component_config=None):
        from core.config.component_config import ComponentConfig
        # Создаем минимальный ComponentConfig, если не передан
        if component_config is None:
            component_config = ComponentConfig(
                variant_id="contract_service_default",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={}
            )
        super().__init__(name=name, application_context=application_context, component_config=component_config)
        # Не инициализируем зависимости в __init__ - делаем это в initialize()
        self.contracts_dir = None
        self._contract_cache: Dict[str, Dict[str, Any]] = {}  # {capability@version: schema}
        self._validator_cache: Dict[str, Draft202012Validator] = {}
        self._model_cache: Dict[str, Type[BaseModel]] = {}  # кэш для Pydantic моделей
        self._indexed = False

    async def initialize(self) -> bool:
        """Инициализация: индексация контрактов из файловой системы"""
        # Устанавливаем директорию контрактов при инициализации
        self.contracts_dir = Path(self.application_context.config.data_dir) / "contracts" if hasattr(self.application_context, 'config') and hasattr(self.application_context.config, 'data_dir') else Path("contracts")
        await self._index_contracts()

        # Вызываем родительскую инициализацию для правильной установки флага _initialized
        parent_result = await super().initialize()
        return parent_result

    async def preload_contracts(self, component_config) -> bool:
        """
        Предзагрузка всех контрактов, указанных в конфигурации компонента.

        ARGS:
        - component_config: конфигурация компонента с указанием версий контрактов

        RETURNS:
        - bool: True если все контракты успешно загружены
        """
        if not hasattr(component_config, 'input_contract_versions') or not hasattr(component_config, 'output_contract_versions'):
            self.logger.info("Нет конфигурации контрактов для предзагрузки")
            return True

        success = True
        
        # Загрузка входящих контрактов
        for capability_name, version in component_config.input_contract_versions.items():
            try:
                # Загружаем input контракт
                input_schema = await self.get_contract_schema(
                    capability_name=capability_name,
                    version=version,
                    direction="input"
                )

                # Сохраняем в кэш с явным указанием направления
                input_cache_key = f"{capability_name}@{version}.input"
                
                if input_schema:
                    self._contract_cache[input_cache_key] = input_schema

                self.logger.debug(f"Предзагружен входящий контракт {capability_name} версии {version}")

            except Exception as e:
                self.logger.error(f"Ошибка предзагрузки входящего контракта {capability_name} версии {version}: {e}")
                success = False

        # Загрузка исходящих контрактов
        for capability_name, version in component_config.output_contract_versions.items():
            try:
                # Загружаем output контракт
                output_schema = await self.get_contract_schema(
                    capability_name=capability_name,
                    version=version,
                    direction="output"
                )

                # Сохраняем в кэш с явным указанием направления
                output_cache_key = f"{capability_name}@{version}.output"
                
                if output_schema:
                    self._contract_cache[output_cache_key] = output_schema

                self.logger.debug(f"Предзагружен исходящий контракт {capability_name} версии {version}")

            except Exception as e:
                self.logger.error(f"Ошибка предзагрузки исходящего контракта {capability_name} версии {version}: {e}")
                success = False

        return success

    def get_contract_schema_from_cache(self, capability_name: str, version: Optional[str] = None, direction: str = "input") -> Optional[Dict[str, Any]]:
        """
        Получение схемы контракта ТОЛЬКО из кэша (без обращения к файловой системе).
        
        ARGS:
        - capability_name: имя capability
        - version: версия контракта (если None, используется latest)
        - direction: направление контракта ("input" или "output")
        
        RETURNS:
        - Dict[str, Any]: схема контракта или None если не найдена в кэше
        """
        cache_key = f"{capability_name}@{version or 'latest'}.{direction}"
        return self._contract_cache.get(cache_key)

    async def _index_contracts(self):
        """Индексация всех контрактов из файловой системы"""
        if not self.contracts_dir.exists():
            self.contracts_dir.mkdir(parents=True, exist_ok=True)
            return

        for contract_file in self.contracts_dir.rglob("*.yaml"):
            await self._process_contract_file(contract_file)

        self._indexed = True

    async def _process_contract_file(self, file_path: Path):
        """Обработка одного файла контракта"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                contract_data = yaml.safe_load(f)

            if not contract_data or 'schema' not in contract_data:
                return

            capability_name = contract_data.get('capability')
            version = contract_data.get('version', '0.0.0')
            direction = contract_data.get('contract_type', 'input')

            if capability_name:
                cache_key = f"{capability_name}@{version}.{direction}"
                self._contract_cache[cache_key] = contract_data['schema']

                # Также сохраняем с версией latest для упрощенного доступа
                latest_key = f"{capability_name}@latest.{direction}"
                self._contract_cache[latest_key] = contract_data['schema']

        except Exception as e:
            self.logger.error(f"Ошибка при обработке файла контракта {file_path}: {e}")

    async def get_contract_schema(
        self,
        capability_name: str,
        version: Optional[str] = None,
        direction: str = "input"  # "input" | "output"
    ) -> Optional[Dict[str, Any]]:
        """
        Получение схемы контракта.

        ПРИОРИТЕТ ЗАГРУЗКИ:
        1. Явно указанная версия из файла (если существует)
        2. Последняя версия из файла (если версия не указана)
        3. Схема из Capability.parameters_schema (fallback для существующих навыков)
        """
        # Формируем ключ для кэша
        cache_key = f"{capability_name}@{version or 'latest'}.{direction}"

        # 1. Проверяем кэш
        if cache_key in self._contract_cache:
            return self._contract_cache[cache_key]

        # 2. Ищем файл контракта
        schema = await self._load_contract_from_file(capability_name, version, direction)

        # 3. Fallback: если контракт не найден — используем схему из реестра
        if schema is None:
            capability = self.application_context.get_capability(capability_name) if hasattr(self.application_context, 'get_capability') else None
            if capability and hasattr(capability, 'parameters_schema') and capability.parameters_schema:
                schema = capability.parameters_schema
                # Маркируем как «встроенный контракт» для отладки
                if isinstance(schema, dict):
                    schema["_source"] = "capability.parameters_schema"
                else:
                    schema = {"_source": "capability.parameters_schema"}

        if schema:
            self._contract_cache[cache_key] = schema
            return schema

        return None

    async def _load_contract_from_file(
        self,
        capability_name: str,
        version: Optional[str],
        direction: str
    ) -> Optional[Dict[str, Any]]:
        """Загрузка контракта из YAML-файла (аналогично PromptService)"""
        # Формируем путь: contracts/skills/{skill}/{capability}_{direction}_v{version}.yaml
        skill_name = capability_name.split('.')[0]

        # Отладочный вывод
        self.logger.debug(f"Поиск контракта: capability={capability_name}, skill={skill_name}, version={version}, direction={direction}")

        # Если версия не указана, ищем latest
        if version is None or version == 'latest':
            # Ищем все файлы для данной capability и выбираем последнюю версию
            pattern = f"{capability_name.replace('.', '_')}_{direction}_v*.yaml"
            self.logger.debug(f"Поиск latest версии по паттерну: {pattern}")

            possible_files = []

            # Ищем в подкаталоге навыка
            skill_dir = self.contracts_dir / "skills" / skill_name
            self.logger.debug(f"Проверка директории: {skill_dir}")
            if skill_dir.exists():
                skill_files = list(skill_dir.glob(pattern))
                self.logger.debug(f"Найдено файлов в skill_dir: {skill_files}")
                possible_files.extend(skill_files)

            # Также ищем в общем каталоге
            global_files = list(self.contracts_dir.glob(pattern))
            self.logger.debug(f"Найдено файлов в global_dir: {global_files}")
            possible_files.extend(global_files)

            if possible_files:
                # Выбираем файл с наибольшей версией (упрощенно - по алфавиту)
                latest_file = max(possible_files, key=lambda x: x.name)
                self.logger.debug(f"Выбран файл latest: {latest_file}")
                try:
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        contract_data = yaml.safe_load(f)
                    return contract_data.get('schema') if contract_data else None
                except Exception as e:
                    self.logger.error(f"Ошибка при загрузке контракта из {latest_file}: {e}")
                    return None
        else:
            # Ищем конкретную версию
            filename = f"{capability_name.replace('.', '_')}_{direction}_v{version}.yaml"
            self.logger.debug(f"Поиск конкретной версии: {filename}")

            # Проверяем в подкаталоге навыка
            skill_dir = self.contracts_dir / "skills" / skill_name
            file_path = skill_dir / filename
            self.logger.debug(f"Проверка пути: {file_path}")

            if not file_path.exists():
                # Проверяем в общем каталоге
                file_path = self.contracts_dir / filename
                self.logger.debug(f"Файл не найден в skill_dir, проверяем: {file_path}")

            if file_path.exists():
                self.logger.debug(f"Файл найден: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        contract_data = yaml.safe_load(f)
                    return contract_data.get('schema') if contract_data else None
                except Exception as e:
                    self.logger.error(f"Ошибка при загрузке контракта из {file_path}: {e}")
                    return None
            else:
                self.logger.debug(f"Файл не найден: {file_path}")

        self.logger.debug("Контракт не найден в файлах")
        return None

    async def validate(
        self,
        capability_name: str,
        data: Dict[str, Any],
        direction: str = "input",
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Валидация данных против схемы контракта.

        ВОЗВРАЩАЕТ:
        {
            "is_valid": bool,
            "errors": List[str],  # пустой если валидно
            "validated_data": Optional[Dict]  # очищенные данные (с дефолтами)
        }
        """
        schema = await self.get_contract_schema(capability_name, version, direction)
        if not schema:
            return {"is_valid": True, "errors": [], "validated_data": data}  # Нет схемы = всегда валидно

        # Создаем/получаем валидатор из кэша
        validator = self._get_validator(schema)

        errors = []
        try:
            # Валидация
            validator.validate(data)
            return {"is_valid": True, "errors": [], "validated_data": data}
        except Exception as e:
            errors = self._extract_validation_errors(e)
            return {"is_valid": False, "errors": errors, "validated_data": None}

    def _get_validator(self, schema: Dict[str, Any]) -> Draft202012Validator:
        """Получение/создание валидатора с кэшированием"""
        # Хэш схемы для кэша
        schema_str = str(sorted(schema.items())) if isinstance(schema, dict) else str(schema)
        schema_hash = hashlib.md5(schema_str.encode()).hexdigest()

        cache_key = f"validator_{schema_hash}"
        if cache_key not in self._validator_cache:
            self._validator_cache[cache_key] = Draft202012Validator(schema)
        return self._validator_cache[cache_key]

    def _extract_validation_errors(self, validation_error: Exception) -> List[str]:
        """Извлечение сообщений об ошибках валидации"""
        # Простая реализация - возвращаем строковое представление ошибки
        # В реальном приложении можно использовать более сложную логику для извлечения деталей
        return [str(validation_error)]

    async def execute(self, input_data: ContractServiceInput) -> ContractServiceOutput:
        """
        Выполнение операций сервиса.

        ARGS:
        - input_data: входные данные с указанием действия

        RETURNS:
        - ContractServiceOutput: результат выполнения
        """
        try:
            if input_data.action == "get_schema":
                schema = await self.get_contract_schema(
                    capability_name=input_data.kwargs.get('capability_name'),
                    version=input_data.kwargs.get('version'),
                    direction=input_data.kwargs.get('direction', 'input')
                )
                return ContractServiceOutput(success=True, data=schema)

            elif input_data.action == "validate":
                validation_result = await self.validate(
                    capability_name=input_data.kwargs.get('capability_name'),
                    data=input_data.kwargs.get('data'),
                    direction=input_data.kwargs.get('direction', 'input'),
                    version=input_data.kwargs.get('version')
                )
                return ContractServiceOutput(success=True, data=validation_result)

            elif input_data.action == "register_contract":
                await self.register_contract(
                    capability_name=input_data.kwargs.get('capability_name'),
                    schema=input_data.kwargs.get('schema'),
                    version=input_data.kwargs.get('version', '1.0.0'),
                    direction=input_data.kwargs.get('direction', 'input')
                )
                return ContractServiceOutput(success=True, data="Contract registered")

            elif input_data.action == "convert_pydantic_to_yaml":
                result = await self.convert_pydantic_to_yaml(
                    capability_name=input_data.kwargs.get('capability_name'),
                    pydantic_model=input_data.kwargs.get('pydantic_model'),
                    version=input_data.kwargs.get('version', '1.0.0'),
                    direction=input_data.kwargs.get('direction', 'input')
                )
                return ContractServiceOutput(success=True, data=result)

            elif input_data.action == "get_pydantic_model":
                model = await self.get_pydantic_model(
                    capability_name=input_data.kwargs.get('capability_name'),
                    version=input_data.kwargs.get('version'),
                    direction=input_data.kwargs.get('direction', 'input')
                )
                return ContractServiceOutput(success=True, data=model)

            else:
                return ContractServiceOutput(success=False, error=f"Unknown action: {input_data.action}")

        except Exception as e:
            return ContractServiceOutput(success=False, error=str(e))

    async def convert_pydantic_to_yaml(self, capability_name: str, pydantic_model: Type[BaseModel], version: str = "1.0.0", direction: str = "input"):
        """
        Конвертирует Pydantic модель в YAML контракт и сохраняет в файл.
        """
        try:
            # Получаем JSON-схему из Pydantic модели
            schema = pydantic_model.model_json_schema()
            
            # Формируем данные контракта
            contract_data = {
                "version": version,
                "contract_type": direction,
                "skill": capability_name.split('.')[0],
                "capability": capability_name,
                "schema": schema
            }
            
            # Создаем путь к файлу
            skill_name = capability_name.split('.')[0]
            skill_dir = self.contracts_dir / "skills" / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{capability_name.replace('.', '_')}_{direction}_v{version}.yaml"
            file_path = skill_dir / filename
            
            # Сохраняем в YAML файл
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(contract_data, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            # Обновляем кэш
            cache_key = f"{capability_name}@{version}.{direction}"
            self._contract_cache[cache_key] = schema
            
            # Обновляем latest версию
            latest_key = f"{capability_name}@latest.{direction}"
            self._contract_cache[latest_key] = schema
            
            return {
                "message": f"Pydantic модель успешно конвертирована в YAML контракт: {file_path}",
                "file_path": str(file_path)
            }
        except Exception as e:
            self.logger.error(f"Ошибка при конвертации Pydantic модели в YAML: {e}")
            raise

    async def get_pydantic_model(self, capability_name: str, version: Optional[str] = None, direction: str = "input") -> Optional[Type[BaseModel]]:
        """
        Получает Pydantic модель из схемы контракта.
        """
        cache_key = f"model_{capability_name}@{version or 'latest'}.{direction}"
        
        # Проверяем кэш
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        # Получаем схему
        schema = await self.get_contract_schema(capability_name, version, direction)
        if not schema:
            return None
        
        # Создаем динамически Pydantic модель из схемы
        # Для этого мы создаем временную модель с использованием schema
        try:
            # Используем возможности Pydantic для создания модели из схемы
            # Это требует использования pydantic-factories или similar подхода
            # Но для простоты мы можем создать временную модель
            
            # Временное решение: создаем динамическую модель на основе схемы
            class DynamicModel(BaseModel):
                pass
            
            # Устанавливаем аннотации и значения на основе схемы
            annotations = {}
            field_defaults = {}
            
            properties = schema.get('properties', {})
            required_fields = schema.get('required', [])
            
            for field_name, field_schema in properties.items():
                # Определяем тип поля на основе схемы JSON
                field_type = self._get_python_type_from_json_schema(field_schema)
                
                if field_name in required_fields:
                    annotations[field_name] = field_type
                else:
                    # Поле не обязательно, используем Optional
                    from typing import Optional as OptionalType
                    annotations[field_name] = OptionalType[field_type]
                    
                    # Устанавливаем значение по умолчанию, если оно есть
                    if 'default' in field_schema:
                        field_defaults[field_name] = field_schema['default']
            
            # Устанавливаем аннотации
            DynamicModel.__annotations__ = annotations
            
            # Устанавливаем значения по умолчанию
            for field_name, default_value in field_defaults.items():
                setattr(DynamicModel, field_name, default_value)
            
            # Кэшируем модель
            self._model_cache[cache_key] = DynamicModel
            
            return DynamicModel
        except Exception as e:
            self.logger.error(f"Ошибка при создании Pydantic модели из схемы: {e}")
            return None

    def _get_python_type_from_json_schema(self, field_schema: Dict[str, Any]) -> type:
        """
        Определяет Python тип из JSON-схемы поля.
        """
        json_type = field_schema.get('type')
        
        if json_type == 'string':
            if 'format' in field_schema and field_schema['format'] == 'date-time':
                from datetime import datetime
                return datetime
            return str
        elif json_type == 'integer':
            return int
        elif json_type == 'number':
            return float
        elif json_type == 'boolean':
            return bool
        elif json_type == 'array':
            items_schema = field_schema.get('items', {})
            item_type = self._get_python_type_from_json_schema(items_schema)
            from typing import List
            return List[item_type]
        elif json_type == 'object':
            # Для объектов возвращаем Dict[str, Any] как наиболее общий случай
            from typing import Dict, Any
            return Dict[str, Any]
        else:
            return Any

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        # Очистка кэшей
        self._contract_cache.clear()
        self._validator_cache.clear()
        self._model_cache.clear()
        self.logger.info("ContractService завершил работу")

    async def reload_contracts(self):
        """Перезагрузка всех контрактов (горячая перезагрузка)"""
        self._contract_cache.clear()
        self._validator_cache.clear()
        self._model_cache.clear()  # очищаем кэш моделей тоже
        await self._index_contracts()

    async def register_contract(self, capability_name: str, schema: Dict[str, Any], version: str = "1.0.0", direction: str = "input"):
        """Регистрация нового контракта программно"""
        cache_key = f"{capability_name}@{version}.{direction}"
        self._contract_cache[cache_key] = schema

        # Обновляем latest версию
        latest_key = f"{capability_name}@latest.{direction}"
        self._contract_cache[latest_key] = schema

    async def check_version_exists(self, capability: str, version: str, direction: str = "input") -> bool:
        """
        Проверяет, существует ли конкретная версия контракта для указанной capability.
        
        :param capability: имя capability
        :param version: версия контракта
        :param direction: направление контракта ("input" или "output")
        :return: True если версия существует, иначе False
        """
        # Проверяем в кэше
        cache_key = f"{capability}@{version}.{direction}"
        if cache_key in self._contract_cache:
            return True
        
        # Проверяем в файловой системе
        schema = await self._load_contract_from_file(capability, version, direction)
        if schema is not None:
            return True
        
        return False
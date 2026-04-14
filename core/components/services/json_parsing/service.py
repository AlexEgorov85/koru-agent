"""
JsonParsingService — единый сервис для парсинка JSON ответов LLM.

ОТВЕТСТВЕННОСТЬ:
- Извлечение JSON из markdown-обёртки
- Парсинг JSON с детальными ошибками
- Создание Pydantic моделей из JSON Schema ($ref, вложенные объекты)
- Валидация данных
- Полное логирование каждого шага

НЕ ОТВЕТСТВЕННОСТЬ:
- Вызов LLM (это LLMOrchestrator)
- Бизнес-логика (это компоненты)

АРХИТЕКТУРА:
- Сервис обнаруживается автоматически через ComponentDiscovery
- Вызывается через ActionExecutor: json_parsing.parse_to_model
- Все шаги парсинга логируются с LogEventType
"""
import json
import re
from typing import Any, Optional, Dict, List, Type, Tuple
from pydantic import ValidationError, create_model

from core.components.services.service import Service
from core.config.component_config import ComponentConfig
from core.infrastructure.logging.event_types import LogEventType
from core.models.data.execution import ExecutionResult, ExecutionStatus
from .types import JsonParseResult, JsonParseStatus
from . import robust_extractor


class JsonParsingService(Service):
    """
    Сервис для парсинка и валидации JSON ответов LLM.

    ПОДДЕРЖИВАЕМЫЕ ДЕЙСТВИЯ:
    - json_parsing.extract_json — извлечь JSON из текста
    - json_parsing.parse_json — распарсить JSON строку
    - json_parsing.parse_to_model — полный цикл: extract → parse → Pydantic модель
    """

    @property
    def description(self) -> str:
        return "Единый сервис для парсинка JSON ответов LLM"

    def __init__(
        self,
        name: str = "json_parsing",
        component_config: ComponentConfig = None,
        executor: Any = None,
        application_context: Any = None
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )
        # Кэш созданных Pydantic моделей: {(model_name, schema_key): Type}
        self._model_cache: Dict[Tuple[str, str], Type] = {}

    async def _custom_initialize(self) -> bool:
        """Сервис не требует дополнительной инициализации."""
        self._log_info("JsonParsingService инициализирован")
        return True

    async def _execute_impl(
        self,
        capability: str,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Выполнение действий парсинга JSON.

        ARGS:
        - capability: Имя действия (extract_json, parse_json, parse_to_model)
        - parameters: Параметры действия
        - execution_context: Контекст выполнения

        RETURNS:
        - Dict с результатом парсинга (сериализуемый)
        """
        if capability == "extract_json":
            return await self._action_extract_json(parameters)
        elif capability == "parse_json":
            return await self._action_parse_json(parameters)
        elif capability == "parse_to_model":
            return await self._action_parse_to_model(parameters)
        else:
            self._log_error(
                f"Неизвестное действие: {capability}",
                event_type=LogEventType.ERROR
            )
            raise ValueError(f"Неизвестное действие: {capability}")

    async def extract_json(self, content: str) -> Dict[str, Any]:
        """
        Публичный API для извлечения JSON из текста.
        
        ARGS:
        - content: str — текст ответа LLM
        
        RETURNS:
        - {"status": "success", "extracted_json": str} или ошибка
        """
        return await self._action_extract_json({"content": content})
    
    async def parse_json(self, raw: str) -> Dict[str, Any]:
        """
        Публичный API для парсинга JSON строки.
        
        ARGS:
        - raw: str — JSON строка
        
        RETURNS:
        - {"status": "success", "parsed_data": dict} или ошибка
        """
        return await self._action_parse_json({"raw": raw})
    
    async def parse_to_model(
        self,
        raw_response: str,
        schema_def: Optional[Dict[str, Any]] = None,
        model_name: str = "DynamicModel"
    ) -> Dict[str, Any]:
        """
        Публичный API для полного цикла: extract → parse → Pydantic модель.
        
        ARGS:
        - raw_response: str — сырой ответ от LLM
        - schema_def: dict — JSON Schema для валидации
        - model_name: str — имя создаваемой модели
        
        RETURNS:
        - {"status": "success", "parsed_data": dict, "pydantic_model_data": dict} или ошибка
        """
        parameters = {
            "raw_response": raw_response,
            "schema_def": schema_def or {},
            "model_name": model_name
        }
        return await self._action_parse_to_model(parameters)
    
    async def _action_extract_json(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Действие: извлечь JSON из текста (markdown, braces, brackets).

        PARAMETERS:
        - content: str — текст ответа LLM

        RETURNS:
        - {"status": "success", "extracted_json": str} или ошибка
        """
        content = parameters.get("content", "")

        # Логирование входа
        self._log_info(
            f"📥 [JsonParsing.extract_json] Начало: входной текст {len(content)} симв.",
            event_type=LogEventType.INFO
        )
        self._log_debug(
            f"🔵 [JsonParsing.extract_json] Полный входной текст:\n{content}",
            event_type=LogEventType.INFO
        )

        if not content:
            self._log_warning(
                "⚠️ [JsonParsing.extract_json] Входной текст пустой",
                event_type=LogEventType.WARNING
            )
            return JsonParseResult(
                status=JsonParseStatus.EXTRACT_ERROR,
                raw_input="",
                error_type="empty_input",
                error_message="Входной текст пустой",
                processing_steps=["Получен пустой вход"]
            ).to_dict()

        # Шаг 1: Ищем markdown блоки с json
        self._log_debug(
            f"� [JsonParsing.extract_json] Шаг 1: поиск markdown блоков ```json...```",
            event_type=LogEventType.INFO
        )
        markdown_json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(markdown_json_pattern, content, re.DOTALL | re.IGNORECASE)
        self._log_debug(
            f"📊 [JsonParsing.extract_json] Шаг 1: найдено {len(matches)} блоков ```json```",
            event_type=LogEventType.INFO
        )
        for idx, match in enumerate(matches):
            json_content = match.strip()
            if json_content.startswith('{') or json_content.startswith('['):
                self._log_info(
                    f"✅ [JsonParsing.extract_json] JSON извлечён из ```json блока #{idx+1}: {len(json_content)} симв.",
                    event_type=LogEventType.INFO
                )
                self._log_debug(
                    f"🟢 [JsonParsing.extract_json] Извлечённый JSON:\n{json_content}",
                    event_type=LogEventType.INFO
                )
                return JsonParseResult(
                    status=JsonParseStatus.SUCCESS,
                    raw_input=content,
                    extracted_json=json_content,
                    processing_steps=[
                        f"Входной текст: {len(content)} симв.",
                        f"Найден markdown json блок #{idx+1}",
                        f"Извлечён JSON: {len(json_content)} симв."
                    ]
                ).to_dict()

        # Шаг 2: Ищем просто ``` без указания языка
        self._log_debug(
            f"🔍 [JsonParsing.extract_json] Шаг 2: поиск markdown блоков ```...```",
            event_type=LogEventType.INFO
        )
        markdown_pattern = r'```\s*(.*?)\s*```'
        matches = re.findall(markdown_pattern, content, re.DOTALL)
        self._log_debug(
            f"📊 [JsonParsing.extract_json] Шаг 2: найдено {len(matches)} блоков ``` ```",
            event_type=LogEventType.INFO
        )
        for idx, match in enumerate(matches):
            json_content = match.strip()
            if json_content.startswith('{') or json_content.startswith('['):
                self._log_info(
                    f"✅ [JsonParsing.extract_json] JSON извлечён из ``` блока #{idx+1}: {len(json_content)} симв.",
                    event_type=LogEventType.INFO
                )
                self._log_debug(
                    f"🟢 [JsonParsing.extract_json] Извлечённый JSON:\n{json_content}",
                    event_type=LogEventType.INFO
                )
                return JsonParseResult(
                    status=JsonParseStatus.SUCCESS,
                    raw_input=content,
                    extracted_json=json_content,
                    processing_steps=[
                        f"Входной текст: {len(content)} симв.",
                        f"Найден markdown блок #{idx+1}",
                        f"Извлечён JSON: {len(json_content)} симв."
                    ]
                ).to_dict()

        # Шаг 3: Robust extraction с балансировкой скобок
        self._log_debug(
            f"🔍 [JsonParsing.extract_json] Шаг 3: robust extraction с балансировкой",
            event_type=LogEventType.INFO
        )
        json_content, steps = robust_extractor.robust_extract_json(content)
        
        if json_content:
            self._log_info(
                f"✅ [JsonParsing.extract_json] JSON извлечён robust_extract: {len(json_content)} симв.",
                event_type=LogEventType.INFO
            )
            self._log_debug(
                f"🟢 [JsonParsing.extract_json] Извлечённый JSON:\n{json_content}",
                event_type=LogEventType.INFO
            )
            return JsonParseResult(
                status=JsonParseStatus.SUCCESS,
                raw_input=content,
                extracted_json=json_content,
                processing_steps=[
                    f"Входной текст: {len(content)} симв.",
                ] + steps
            ).to_dict()

        # Ничего не нашли
        self._log_debug(
            f"❌ [JsonParsing.extract_json] JSON не найден в тексте ({len(content)} симв.)",
            event_type=LogEventType.WARNING
        )
        return JsonParseResult(
            status=JsonParseStatus.EXTRACT_ERROR,
            raw_input=content,
            error_type="no_json_found",
            error_message="JSON не найден в тексте",
            processing_steps=[
                f"Входной текст: {len(content)} симв.",
            ] + steps
        ).to_dict()

    async def _action_parse_json(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Действие: распарсить JSON строку с детальными ошибками.

        PARAMETERS:
        - raw: str — JSON строка

        RETURNS:
        - {"status": "success", "parsed_data": dict} или ошибка
        """
        raw = parameters.get("raw", "")

        # Логирование входа
        self._log_info(
            f"📥 [JsonParsing.parse_json] Начало: входная строка {len(raw)} симв.",
            event_type=LogEventType.INFO
        )
        self._log_debug(
            f"🔵 [JsonParsing.parse_json] Полный входной текст:\n{raw}",
            event_type=LogEventType.INFO
        )

        if not raw:
            self._log_warning(
                "⚠️ [JsonParsing.parse_json] Входная строка пустая",
                event_type=LogEventType.WARNING
            )
            return JsonParseResult(
                status=JsonParseStatus.PARSE_ERROR,
                raw_input="",
                error_type="empty_input",
                error_message="Входная строка пустая",
                processing_steps=["Получена пустая строка"]
            ).to_dict()

        # Попытка парсинга с предобработкой
        # Сначала пробуем как есть
        try:
            parsed_data = json.loads(raw)
            
            # Логирование успешного парсинга
            if isinstance(parsed_data, dict):
                keys_info = list(parsed_data.keys())
                self._log_info(
                    f"✅ [JsonParsing.parse_json] JSON распарсен успешно: {len(raw)} симв., ключи={keys_info}",
                    event_type=LogEventType.INFO
                )
            elif isinstance(parsed_data, list):
                self._log_info(
                    f"✅ [JsonParsing.parse_json] JSON массив распарсен: {len(raw)} симв., элементов={len(parsed_data)}",
                    event_type=LogEventType.INFO
                )
            else:
                self._log_info(
                    f"✅ [JsonParsing.parse_json] JSON распарсен: {len(raw)} симв., тип={type(parsed_data).__name__}",
                    event_type=LogEventType.INFO
                )

            self._log_debug(
                f"🟢 [JsonParsing.parse_json] Распарсенные данные:\n{json.dumps(parsed_data, indent=2, ensure_ascii=False)}",
                event_type=LogEventType.INFO
            )

            return JsonParseResult(
                status=JsonParseStatus.SUCCESS,
                raw_input=raw,
                extracted_json=raw,
                parsed_data=parsed_data,
                processing_steps=[
                    f"Входная строка: {len(raw)} симв.",
                    f"JSON распарсен, ключи: {list(parsed_data.keys()) if isinstance(parsed_data, dict) else 'not a dict'}"
                ]
            ).to_dict()

        except json.JSONDecodeError as e:
            # Цикл исправлений: извлечение, запятые, скобки, мусор
            self._log_debug(
                f"⚠️ [JsonParsing.parse_json] Ошибка парсинга, попытка исправления: {type(e).__name__}: {e}",
                event_type=LogEventType.INFO
            )
            
            fixed_raw = raw
            fixes_applied = []
            
            # Попытка 0: Извлечь валидный JSON из мусора
            extracted = self._extract_and_fix_json(fixed_raw)
            if extracted and extracted != fixed_raw:
                fixes_applied.append("extract_from_garbage")
                fixed_raw = extracted
            
            # Попытка 1: Исправить запятые
            fixed_with_commas = self._fix_missing_commas(fixed_raw)
            if fixed_with_commas != fixed_raw:
                fixes_applied.append("missing_commas")
                fixed_raw = fixed_with_commas
            
            # Попытка 2: Исправить закрывающие скобки
            fixed_with_brackets = self._fix_missing_closing_brackets(fixed_raw)
            if fixed_with_brackets != fixed_raw:
                fixes_applied.append("missing_closing_brackets")
                fixed_raw = fixed_with_brackets
            
            # Попытка 3: Удалить мусор в конце
            fixed_clean = self._fix_json_trailing_garbage(fixed_raw)
            if fixed_clean != fixed_raw:
                fixes_applied.append("trailing_garbage")
                fixed_raw = fixed_clean
            
            if fixes_applied:
                self._log_info(
                    f"🔧 [JsonParsing.parse_json] Применены исправления: {', '.join(fixes_applied)}",
                    event_type=LogEventType.INFO
                )
                try:
                    parsed_data = json.loads(fixed_raw)
                    
                    # Логирование успешного парсинга после исправления
                    if isinstance(parsed_data, dict):
                        keys_info = list(parsed_data.keys())
                        self._log_info(
                            f"✅ [JsonParsing.parse_json] JSON распарсен после исправления: {len(fixed_raw)} симв., ключи={keys_info}",
                            event_type=LogEventType.INFO
                        )
                    elif isinstance(parsed_data, list):
                        self._log_info(
                            f"✅ [JsonParsing.parse_json] JSON массив распарсен после исправления: {len(fixed_raw)} симв., элементов={len(parsed_data)}",
                            event_type=LogEventType.INFO
                        )
                    else:
                        self._log_info(
                            f"✅ [JsonParsing.parse_json] JSON распарсен после исправления: {len(fixed_raw)} симв., тип={type(parsed_data).__name__}",
                            event_type=LogEventType.INFO
                        )

                    self._log_debug(
                        f"🟢 [JsonParsing.parse_json] Распарсенные данные:\n{json.dumps(parsed_data, indent=2, ensure_ascii=False)}",
                        event_type=LogEventType.INFO
                    )

                    return JsonParseResult(
                        status=JsonParseStatus.SUCCESS,
                        raw_input=raw,
                        extracted_json=fixed_raw,
                        parsed_data=parsed_data,
                        processing_steps=[
                            f"Входная строка: {len(raw)} симв.",
                            f"Применены исправления: {', '.join(fixes_applied)}",
                            f"JSON распарсен успешно: {len(fixed_raw)} симв."
                        ]
                    ).to_dict()
                except json.JSONDecodeError:
                    self._log_debug(
                        f"❌ [JsonParsing.parse_json] Исправления не помогли",
                        event_type=LogEventType.WARNING
                    )
            
            # Если исправления не помогли
            self._log_error(
                f"❌ [JsonParsing.parse_json] Ошибка парсинга JSON: {type(e).__name__}: {e}",
                event_type=LogEventType.ERROR
            )
            self._log_debug(
                f"🔴 [JsonParsing.parse_json] Невалидный JSON:\n{raw}",
                event_type=LogEventType.ERROR
            )
            return JsonParseResult(
                status=JsonParseStatus.PARSE_ERROR,
                raw_input=raw,
                error_type="json_decode_error",
                error_message=f"JSON decode error: {str(e)}",
                error_details=[{
                    "line": e.lineno,
                    "column": e.colno,
                    "position": e.pos,
                    "message": e.msg
                }],
                processing_steps=[
                    f"Входная строка: {len(raw)} симв.",
                    f"Ошибка JSON: {str(e)}"
                ]
            ).to_dict()

    async def _action_parse_to_model(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Действие: полный цикл — extract → parse → Pydantic модель.

        PARAMETERS:
        - raw_response: str — сырой ответ от LLM
        - schema_def: dict — JSON Schema для валидации
        - model_name: str — имя создаваемой модели

        RETURNS:
        - {"status": "success", "parsed_data": dict, "pydantic_model_data": dict} или ошибка
        """
        raw_response = parameters.get("raw_response", "")
        schema_def = parameters.get("schema_def", {})
        model_name = parameters.get("model_name", "DynamicModel")

        steps: List[str] = []

        # Логирование входа
        self._log_info(
            f"📥 [JsonParsing.parse_to_model] Начало: вход {len(raw_response)} симв., модель={model_name}, схема={bool(schema_def)}",
            event_type=LogEventType.INFO
        )
        self._log_debug(
            f"🔵 [JsonParsing.parse_to_model] Полный входной текст:\n{raw_response}",
            event_type=LogEventType.INFO
        )
        if schema_def:
            self._log_debug(
                f"🔵 [JsonParsing.parse_to_model] Схема модели:\n{json.dumps(schema_def, indent=2, ensure_ascii=False)}",
                event_type=LogEventType.INFO
            )
        steps.append(f"Вход: {len(raw_response)} симв., модель={model_name}, схема={bool(schema_def)}")

        extract_result = await self._action_extract_json({"content": raw_response})
        steps.extend(extract_result.get("processing_steps", []))

        if extract_result["status"] != JsonParseStatus.SUCCESS:
            self._log_error(
                f"❌ [JsonParsing.parse_to_model] Не удалось извлечь JSON: {extract_result.get('error_message')}",
                event_type=LogEventType.ERROR
            )
            return JsonParseResult(
                status=JsonParseStatus.EXTRACT_ERROR,
                raw_input=raw_response,
                error_type=extract_result.get("error_type"),
                error_message=extract_result.get("error_message"),
                processing_steps=steps
            ).to_dict()

        extracted_json = extract_result.get("extracted_json", "")

        # Шаг 2: Парсинг JSON
        self._log_debug(
            f"📥 [JsonParsing.parse_to_model] Парсинг JSON: {len(extracted_json)} симв.",
            event_type=LogEventType.INFO
        )
        steps.append(f"Парсинг JSON: {len(extracted_json)} симв.")

        parse_result = await self._action_parse_json({"raw": extracted_json})
        steps.extend(parse_result.get("processing_steps", []))

        if parse_result["status"] != JsonParseStatus.SUCCESS:
            self._log_error(
                f"❌ [JsonParsing.parse_to_model] Не удалось распарсить JSON: {parse_result.get('error_message')}",
                event_type=LogEventType.ERROR
            )
            return JsonParseResult(
                status=JsonParseStatus.PARSE_ERROR,
                raw_input=raw_response,
                extracted_json=extracted_json,
                error_type=parse_result.get("error_type"),
                error_message=parse_result.get("error_message"),
                error_details=parse_result.get("error_details"),
                processing_steps=steps
            ).to_dict()

        parsed_data = parse_result.get("parsed_data", {})

        # Шаг 3: Создание Pydantic модели из схемы
        if not schema_def:
            self._log_debug(
                f"⚠️ [JsonParsing.parse_to_model] Схема не указана, возвращаем сырые данные",
                event_type=LogEventType.WARNING
            )
            steps.append("Схема не указана, возвращаем сырые данные")
            return JsonParseResult(
                status=JsonParseStatus.SUCCESS,
                raw_input=raw_response,
                extracted_json=extracted_json,
                parsed_data=parsed_data,
                processing_steps=steps
            ).to_dict()

        self._log_debug(
            f"📥 [JsonParsing.parse_to_model] Создание модели {model_name} из схемы",
            event_type=LogEventType.INFO
        )
        steps.append(f"Создание модели {model_name} из схемы")

        try:
            defs = schema_def.get("$defs", {})
            cache_key = (model_name, str(schema_def))

            # Проверяем кэш
            if cache_key in self._model_cache:
                DynamicModel = self._model_cache[cache_key]
                self._log_debug(
                    f"📦 [JsonParsing.parse_to_model] Модель {model_name} взята из кэша",
                    event_type=LogEventType.INFO
                )
                steps.append(f"Модель {model_name} взята из кэша")
            else:
                self._log_debug(
                    f"🔨 [JsonParsing.parse_to_model] Создание модели {model_name} из схемы...",
                    event_type=LogEventType.INFO
                )
                DynamicModel = self._create_model_from_schema(model_name, schema_def, defs)
                self._model_cache[cache_key] = DynamicModel
                self._log_debug(
                    f"✅ [JsonParsing.parse_to_model] Модель {model_name} создана",
                    event_type=LogEventType.INFO
                )
                steps.append(f"Модель {model_name} создана из схемы")

            # Шаг 4: Валидация и создание модели
            self._log_debug(
                f"🔍 [JsonParsing.parse_to_model] Валидация данных и создание модели...",
                event_type=LogEventType.INFO
            )
            pydantic_instance = DynamicModel(**parsed_data)
            steps.append(f"Модель {model_name} валидирована успешно")

            self._log_info(
                f"✅ [JsonParsing.parse_to_model] Модель {model_name} создана и валидирована успешно",
                event_type=LogEventType.INFO
            )
            self._log_debug(
                f"🟢 [JsonParsing.parse_to_model] Данные модели:\n{json.dumps(pydantic_instance.model_dump(), indent=2, ensure_ascii=False)}",
                event_type=LogEventType.INFO
            )

            return JsonParseResult(
                status=JsonParseStatus.SUCCESS,
                raw_input=raw_response,
                extracted_json=extracted_json,
                parsed_data=parsed_data,
                pydantic_model=pydantic_instance,
                processing_steps=steps
            ).to_dict()

        except ValidationError as e:
            error_details = [
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", "validation error"),
                    "type": err.get("type", "unknown")
                }
                for err in e.errors()
            ]
            error_summary = "; ".join(
                f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
                for err in error_details
            )

            self._log_error(
                f"❌ [JsonParsing.parse_to_model] Ошибка валидации Pydantic: {error_summary}",
                event_type=LogEventType.ERROR
            )
            self._log_debug(
                f"🔴 [JsonParsing.parse_to_model] Невалидные данные:\n{json.dumps(parsed_data, indent=2, ensure_ascii=False)}",
                event_type=LogEventType.ERROR
            )
            steps.append(f"Ошибка валидации: {error_summary}")

            return JsonParseResult(
                status=JsonParseStatus.VALIDATION_ERROR,
                raw_input=raw_response,
                extracted_json=extracted_json,
                parsed_data=parsed_data,
                error_type="validation_error",
                error_message=f"{len(error_details)} validation error(s)",
                error_details=error_details,
                processing_steps=steps
            ).to_dict()

        except Exception as e:
            self._log_error(
                f"❌ [JsonParsing.parse_to_model] Ошибка создания модели: {e}",
                event_type=LogEventType.ERROR,
                exc_info=True
            )
            steps.append(f"Ошибка создания модели: {str(e)}")

            return JsonParseResult(
                status=JsonParseStatus.MODEL_ERROR,
                raw_input=raw_response,
                extracted_json=extracted_json,
                parsed_data=parsed_data,
                error_type="model_creation_error",
                error_message=str(e),
                processing_steps=steps
            ).to_dict()

    def _create_model_from_schema(
        self,
        model_name: str,
        schema: Dict[str, Any],
        defs: Dict[str, Any]
    ) -> Type:
        """
        Создать Pydantic модель из JSON Schema с поддержкой $ref.

        ARGS:
        - model_name: Имя создаваемой модели
        - schema: JSON Schema dict
        - defs: Определения типов ($defs)

        RETURNS:
        - Pydantic model class
        """
        def resolve_field_type(field_schema: Dict[str, Any], field_name: str = "field") -> Any:
            """Рекурсивное разрешение типов полей."""
            # Проверка на $ref
            if "$ref" in field_schema:
                ref_path = field_schema["$ref"]
                ref_name = ref_path.split("/")[-1]
                if ref_name in defs:
                    return resolve_field_type(defs[ref_name], ref_name)
                else:
                    self._log_warning(f"$ref '{ref_name}' не найден в $defs")
                    return Any

            field_type = field_schema.get("type", "any")

            if field_type == "string":
                return str
            elif field_type == "integer":
                return int
            elif field_type == "number":
                return float
            elif field_type == "boolean":
                return bool
            elif field_type == "array":
                items_schema = field_schema.get("items", {})
                item_type = resolve_field_type(items_schema, f"{field_name}_item")
                return List[item_type]
            elif field_type == "object":
                # Inline nested object
                nested_props = field_schema.get("properties", {})
                if nested_props:
                    nested_model_name = "".join(word.title() for word in field_name.split("_")) + "Nested"
                    nested_fields = {}
                    for prop_name, prop_schema in nested_props.items():
                        prop_type = resolve_field_type(prop_schema, prop_name)
                        nested_fields[prop_name] = (prop_type, ...)
                    return create_model(nested_model_name, **nested_fields)
                else:
                    return Dict[str, Any]
            else:
                return Any

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        fields = {}
        for field_name, field_schema in properties.items():
            field_type = resolve_field_type(field_schema, field_name)
            is_required = field_name in required

            if is_required:
                fields[field_name] = (field_type, ...)
            else:
                from typing import Optional
                fields[field_name] = (Optional[field_type], None)

        return create_model(model_name, **fields)

    def _fix_missing_commas(self, json_str: str) -> str:
        """
        Исправить отсутствующие запятые между полями JSON.

        ПРОБЛЕМА: LLM иногда генерирует JSON без запятых.

        РЕШЕНИЕ: Добавить запятые там где после значения идёт новый ключ.
        """
        import re
        
        patterns_to_fix = [
            (r'(")\s*\n\s*(")', r'\1,\n\2'),
            (r'(\}|\])\s*\n\s*(")', r'\1,\n\2'),
            (r'(\d|true|false|null)\s*\n\s*(")', r'\1,\n\2'),
            (r'(\})\s*\n\s*(\{)', r'\1,\n\2'),
        ]
        
        fixed = json_str
        for pattern, replacement in patterns_to_fix:
            fixed = re.sub(pattern, replacement, fixed)
        
        return fixed

    def _fix_missing_closing_brackets(self, json_str: str) -> str:
        """
        Исправить отсутствующие закрывающие скобки в JSON.

        ПРОБЛЕМА: LLM зацикливается или обрывает ответ без закрывающих скобок.

        РЕШЕНИЕ: Подсчитать баланс скобок и добавить недостающие.
        """
        # Удаляем trailing whitespace и мусор
        stripped = json_str.rstrip()
        
        # Находим последнюю значимую позицию
        last_meaningful_idx = -1
        for i in range(len(stripped) - 1, -1, -1):
            char = stripped[i]
            if char in '}"\'0123456789' or char.isalpha():
                last_meaningful_idx = i
                break
        
        if last_meaningful_idx == -1:
            return json_str
        
        core_json = stripped[:last_meaningful_idx + 1]
        
        # Подсчитываем баланс скобок
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        
        for char in core_json:
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\' and in_string:
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
        
        # Добавляем недостающие закрывающие скобки
        fixed = core_json
        
        while bracket_count > 0:
            fixed += ']'
            bracket_count -= 1
        
        while brace_count > 0:
            fixed += '}'
            brace_count -= 1
        
        return fixed

    def _fix_json_trailing_garbage(self, json_str: str) -> str:
        """
        Удалить мусор в конце JSON (переносы, пробелы, точки).

        ПРОБЛЕМА: LLM зацикливается после JSON.
        """
        last_brace = json_str.rfind('}')
        last_bracket = json_str.rfind(']')
        last_closing = max(last_brace, last_bracket)
        
        if last_closing != -1:
            after = json_str[last_closing + 1:].strip()
            if not after or all(c in '\n\r\t .,;' for c in after):
                return json_str[:last_closing + 1]
        
        return json_str

    def _extract_and_fix_json(self, json_str: str) -> Optional[str]:
        """
        Извлечь валидный JSON из строки с мусором.

        ПРОБЛЕМА: LLM генерирует кучу мусора ВНУТРИ JSON.

        РЕШЕНИЕ: Посимвольно идём по JSON, считаем баланс скобок.
        Как только баланс стал 0 - нашли конец валидного JSON.
        """
        if not json_str or not json_str.strip():
            return None
        
        # Находим первую { или [
        start_idx = -1
        for i, char in enumerate(json_str):
            if char in '{[':
                start_idx = i
                break
        
        if start_idx == -1:
            return None
        
        # Идём посимвольно и считаем баланс
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        last_valid_end = -1
        
        for i in range(start_idx, len(json_str)):
            char = json_str[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\' and in_string:
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
            
            if brace_count == 0 and bracket_count == 0:
                last_valid_end = i + 1
                break
        
        if last_valid_end == -1:
            # Не нашли конец - добавляем скобки
            stripped = json_str[start_idx:].rstrip()
            last_meaningful = -1
            for i in range(len(stripped) - 1, -1, -1):
                if stripped[i] in '}"\'0123456789' or stripped[i].isalpha():
                    last_meaningful = i
                    break
            
            if last_meaningful == -1:
                return None
            
            core = stripped[:last_meaningful + 1]
            
            b_count = br_count = 0
            in_str = esc = False
            for c in core:
                if esc:
                    esc = False
                    continue
                if c == '\\' and in_str:
                    esc = True
                    continue
                if c == '"':
                    in_str = not in_str
                    continue
                if not in_str:
                    if c == '{': b_count += 1
                    elif c == '}': b_count -= 1
                    elif c == '[': br_count += 1
                    elif c == ']': br_count -= 1
            
            while br_count > 0:
                core += ']'
                br_count -= 1
            while b_count > 0:
                core += '}'
                b_count -= 1
            
            return core
        
        return json_str[start_idx:last_valid_end]


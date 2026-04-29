"""
Observer — LLM-анализ результатов выполнения действий.

АРХИТЕКТУРА:
1. Анализирует результат действия через LLM
2. Оценивает статус, качество, проблемы
3. Генерирует insight и рекомендации для следующего шага
4. Использует контракт behavior.react.observe_output_v1.0.0

ОПТИМИЗАЦИЯ (Фаза 1):
- Поддержка режимов trigger_mode: "always", "on_error", "on_empty"
- Rule-based анализ для success-статусов (экономия LLM-вызовов)
"""
from typing import Any, Dict, Optional, Literal
from core.infrastructure.event_bus.unified_event_bus import EventType


class Observer:
    """
    Компонент наблюдения за результатами выполнения.
    
    ОТВЕТСТВЕННОСТЬ:
    - Анализ результата действия (success/error/empty/partial)
    - Оценка качества данных
    - Выявление проблем и инсайтов
    - Генерация рекомендаций для следующего шага
    
    КОНФИГУРАЦИЯ:
    - trigger_mode: "always" | "on_error" | "on_empty"
      - "always": вызывать LLM на каждом шаге (по умолчанию)
      - "on_error": вызывать LLM только при ошибках/пустых результатах
      - "on_empty": вызывать LLM только при пустых результатах
    """
    
    DEPENDENCIES = ["prompt_service", "contract_service", "llm_orchestrator"]
    
    def __init__(
        self,
        application_context=None,
        component_name: str = "observer",
        trigger_mode: Literal["always", "on_error", "on_empty"] = "always"
    ):
        self.application_context = application_context
        self.component_name = component_name
        self.trigger_mode = trigger_mode
    
    @property
    def llm_orchestrator(self):
        """Получить LLM orchestrator из контекста."""
        if self.application_context and hasattr(self.application_context, 'llm_orchestrator'):
            return self.application_context.llm_orchestrator
        return None
    
    @property
    def llm_provider(self):
        """Получить LLM провайдер из инфраструктурного контекста."""
        if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
            infra = self.application_context.infrastructure_context
            if infra.resource_registry:
                resource = infra.resource_registry.get_resource("default_llm")
                if resource:
                    return resource.instance
        return None
    
    def _log_info(self, message: str, event_type=None):
        """Логирование info уровня."""
        if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
            log_session = self.application_context.infrastructure_context.log_session
            logger = log_session.get_component_logger("observer")
            logger.info(message, extra={"event_type": event_type or EventType.INFO})

    def _log_error(self, message: str, exc_info=False):
        """Логирование error уровня."""
        if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
            log_session = self.application_context.infrastructure_context.log_session
            logger = log_session.get_component_logger("observer")
            logger.error(message, extra={"event_type": EventType.ERROR}, exc_info=exc_info)

    def _check_truncation(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: Any
    ) -> Optional[str]:
        """
        Проверяет, не обрезаны ли результаты из-за лимита.
        
        Если количество результатов >= лимиту (top_k, limit, max_results),
        возвращает предупреждение.
        """
        # Ищем лимит в параметрах (учитываем что значение может быть строкой)
        limit = None
        for key in ['top_k', 'limit', 'max_results', 'max_rows', 'n_results']:
            if key in parameters:
                try:
                    limit = int(parameters[key])  # int() корректно преобразует строку '5' в 5
                    break
                except (ValueError, TypeError):
                    pass
        
        if limit is None or limit <= 0:
            return None
        
        # Считаем количество результатов
        count = 0
        if isinstance(result, list):
            count = len(result)
        elif isinstance(result, dict):
            if 'rows' in result and isinstance(result['rows'], list):
                count = len(result['rows'])
            elif 'results' in result and isinstance(result['results'], list):
                count = len(result['results'])
            elif 'data' in result and isinstance(result['data'], list):
                count = len(result['data'])
            elif 'result' in result and isinstance(result['result'], list):
                count = len(result['result'])
        
        # КРИТИЧНО: если count == limit, результаты могли быть обрезаны!
        if count > 0 and count >= limit:
            new_limit = limit + 10 if limit < 100 else 0
            return (
                f"[TRUNCATION WARNING] Получено результатов ({count}) >= лимиту ({limit}). "
                f"Возможно, данные обрезаны. Для полных данных увеличьте top_k={new_limit} или 0 для безлимитно. "
                f"Или используйте data_analysis.analyze_step_data."
            )
        return None
    
    def should_call_llm(self, result: Any, error: Optional[str], status: Optional[str] = None) -> bool:
        """
        Определение необходимости вызова LLM на основе trigger_mode.
        
        ПАРАМЕТРЫ:
        - result: результат выполнения
        - error: ошибка (если есть)
        - status: статус выполнения (если известен заранее)
        
        ВОЗВРАЩАЕТ:
        - True если нужно вызвать LLM, False для rule-based fallback
        """
        # Определяем статус если не передан
        if status is None:
            if error:
                status = "error"
            elif result is None or (isinstance(result, (list, dict)) and len(result) == 0):
                status = "empty"
            else:
                status = "success"
        
        # Режимы trigger_mode
        if self.trigger_mode == "always":
            return True
        elif self.trigger_mode == "on_error":
            return status in ("error", "empty")
        elif self.trigger_mode == "on_empty":
            return status == "empty"
        
        return True
    
    def _rule_based_observation(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: Any,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rule-based анализ результата без вызова LLM.
        
        ПАРАМЕТРЫ:
        - action_name: имя действия
        - parameters: параметры действия
        - result: результат выполнения
        - error: ошибка (если есть)
        
        ВОЗВРАЩАЕТ:
        - observation: структурированное наблюдение
        """
        # Преобразуем Pydantic модели в стандартные типы Python
        if hasattr(result, 'model_dump'):
            result = result.model_dump()
        elif hasattr(result, 'dict'):
            result = result.dict()
        
        # Определяем статус
        if error:
            return {
                "status": "error",
                "observation": f"Error during execution: {error}",
                "key_findings": [f"Action '{action_name}' failed"],
                "data_quality": {"completeness": 0.0, "reliability": 0.0},
                "errors": [error],
                "next_step_suggestion": "Retry with different parameters or use recovery strategy",
                "requires_additional_action": True,
                "_rule_based": True
            }
        
        # Проверяем пустоту результата
        if result is None or (isinstance(result, (list, dict)) and len(result) == 0):
            return {
                "status": "empty",
                "observation": "Empty result received",
                "key_findings": [f"Action '{action_name}' returned no data"],
                "data_quality": {"completeness": 0.0, "reliability": 0.5},
                "errors": [],
                "next_step_suggestion": "Try different parameters or check data availability",
                "requires_additional_action": True,
                "_rule_based": True
            }
        
        # Успешный результат - анализируем данные и формируем информативное наблюдение
        completeness = 1.0
        reliability = 0.8
        observation_text = f"Action '{action_name}' completed successfully"
        key_findings = []
        
        # Для vector_search результатов (проверяем по имени действия или структуре данных)
        if "vector_search" in action_name or (isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict) and "score" in result[0]):
            results_list = []
            if isinstance(result, list):
                results_list = result
            elif isinstance(result, dict) and "results" in result:
                results_list = result.get("results", [])
            
            if results_list:
                count = len(results_list)
                query_text = ""
                if isinstance(result, dict) and "query" in result:
                    query_text = f" for query: {result['query'][:50]}"
                observation_text = f"Found {count} results{query_text}"
                
                key_findings.append(f"Found {count} results")
                
                # Добавляем примеры результатов
                for i, r in enumerate(results_list[:5]):
                    if isinstance(r, dict):
                        score = r.get('score', 0)
                        text = r.get('matched_text', r.get('content', r.get('text', str(r))))[:100]
                        key_findings.append(f"[{i+1}] (score={score:.2f}) {text}")
                
                if count > 5:
                    key_findings.append(f"... and {count - 5} more results")
                    observation_text += f". Use data_analysis.analyze_step_data to analyze all {count} results"
                
                completeness = 1.0 if count > 0 else 0.0
            else:
                # Диагностика: почему не найдены результаты
                if isinstance(result, list):
                    self._log_info(
                        f"⚠️ [Observer] Vector search вернул пустой список результатов",
                        event_type=EventType.WARNING
                    )
                elif isinstance(result, dict):
                    self._log_info(
                        f"⚠️ [Observer] Vector search вернул словарь без 'results'. Ключи: {list(result.keys())[:10]}",
                        event_type=EventType.WARNING
                    )
                else:
                    self._log_info(
                        f"⚠️ [Observer] Vector search вернул неожиданный тип: {type(result).__name__}",
                        event_type=EventType.WARNING
                    )
                
                observation_text = "No results found"
                completeness = 0.0
                key_findings.append("No results returned")
        
        # Для SQL результатов
        elif isinstance(result, dict) and ("rows" in result or "rowcount" in result):
            rows = result.get("rows", [])
            row_count = len(rows) if rows else result.get("rowcount", 0)
            
            if row_count > 0:
                observation_text = f"Query returned {row_count} rows"
                key_findings.append(f"Retrieved {row_count} rows")
                
                # Показываем примеры строк
                for i, row in enumerate(rows[:3]):
                    if isinstance(row, dict):
                        preview = {k: v for k, v in list(row.items())[:3]}
                        key_findings.append(f"[{i+1}] {preview}")
                
                if row_count > 3:
                    key_findings.append(f"... and {row_count - 3} more rows")
                    if row_count > 10:
                        observation_text += f". Use data_analysis.analyze_step_data for full analysis"
                
                completeness = 1.0 if row_count > 0 else 0.0
            else:
                observation_text = "Query returned no data"
                completeness = 0.0
                key_findings.append("Query returned empty result")
        
        # Для списков
        elif isinstance(result, list):
            count = len(result)
            if count > 0:
                observation_text = f"Received list with {count} items"
                key_findings.append(f"List contains {count} items")
                
                if count > 3:
                    key_findings.append(f"... and {count - 3} more items")
                    observation_text += f". Use data_analysis.analyze_step_data for full analysis"
                
                completeness = 0.8 if count < 5 else 1.0
            else:
                observation_text = "Received empty list"
                completeness = 0.0
                key_findings.append("Empty list returned")
        
        # Для словарей
        elif isinstance(result, dict):
            key_count = len(result)
            observation_text = f"Received dict with {key_count} keys"
            key_findings.append(f"Dict contains {key_count} keys")
            completeness = 0.8 if key_count > 0 else 0.0
        
        # Проверяем warning-флаги
        if isinstance(result, dict):
            if result.get('warning') or result.get('truncated'):
                reliability = 0.6
                key_findings.append(f"Warning: {result.get('warning', 'Result truncated')}")
                self._log_info(
                    f"⚠️ [Rule-based] Result has warnings: {result.get('warning', 'N/A')}",
                    event_type=EventType.WARNING
                )
        
        return {
            "status": "success",
            "observation": observation_text,
            "key_findings": key_findings,
            "data_quality": {"completeness": completeness, "reliability": reliability},
            "errors": [],
            "next_step_suggestion": "Continue with next step based on goal progress" if completeness > 0 else "Try different parameters or check data availability",
            "requires_additional_action": completeness == 0.0,
            "_rule_based": True
        }
    
    async def analyze(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: Any,
        error: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_number: Optional[int] = None,
        force_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Анализ результата действия через LLM.
        
        ПАРАМЕТРЫ:
        - action_name: имя выполненного действия
        - parameters: параметры действия
        - result: результат выполнения
        - error: ошибка (если есть)
        - session_id: ID сессии
        - agent_id: ID агента
        - step_number: номер шага
        - force_llm: принудительный вызов LLM (игнорирует trigger_mode)
        
        ВОЗВРАЩАЕТ:
        - observation: структурированное наблюдение
        """
        # Проверяем необходимость вызова LLM
        use_llm = force_llm or self.should_call_llm(result, error)
        
        if not use_llm:
            # Rule-based анализ без LLM
            self._log_info(
                f"⚡ [Observer.analyze] Skip LLM (trigger_mode={self.trigger_mode}): action={action_name}",
                event_type=EventType.INFO
            )
            observation = self._rule_based_observation(
                action_name=action_name,
                parameters=parameters,
                result=result,
                error=error
            )
            # Явно записываем метрику rule-based анализа
            # Вызывающий код (ObservationPhase) должен записать metrics.record_observer_call(used_llm=False)
            return observation
        
        try:
            from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
            
            # Получаем контракт через contract_service если доступен
            output_contract = None
            schema = None
            
            # Попытка 1: Через application_context.get_output_contract (если метод есть)
            if self.application_context and hasattr(self.application_context, 'get_output_contract'):
                try:
                    output_contract = self.application_context.get_output_contract("behavior.react.observe")
                except Exception:
                    pass
            
            # Попытка 2: Через contract_service если доступен
            if output_contract is None and self.application_context and hasattr(self.application_context, 'contract_service'):
                try:
                    contract_service = self.application_context.contract_service
                    if hasattr(contract_service, 'get_contract_schema_from_cache'):
                        # Получаем схему напрямую из кэша контрактов
                        schema = contract_service.get_contract_schema_from_cache("behavior.react.observe", "output")
                        # schema будет Dict с полями контракта, включая schema_data
                        if isinstance(schema, dict) and 'schema_data' in schema:
                            schema = schema['schema_data']
                    elif hasattr(contract_service, 'get_contract'):
                        output_contract = contract_service.get_contract("behavior.react.observe", direction="output")
                except Exception as e:
                    self._log_info(f"⚠️ [Observer.analyze] ContractService не вернул контракт: {e}", event_type=EventType.WARNING)
                    pass
            
            # Извлекаем схему из контракта
            if output_contract:
                if hasattr(output_contract, 'model_json_schema'):
                    schema = output_contract.model_json_schema()
                elif hasattr(output_contract, 'model_schema'):
                    schema = output_contract.model_schema
                elif isinstance(output_contract, dict):
                    schema = output_contract.get('schema_data')
            
            # Fallback схема если контракт не найден
            if schema is None:
                schema = {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["success", "partial", "error", "empty"],
                            "description": "Статус выполнения действия"
                        },
                        "observation": {
                            "type": "string",
                            "description": "Краткое описание наблюдаемого результата"
                        },
                        "key_findings": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Список важных фактов"
                        },
                        "data_quality": {
                            "type": "object",
                            "properties": {
                                "completeness": {"type": "number", "minimum": 0, "maximum": 1},
                                "reliability": {"type": "number", "minimum": 0, "maximum": 1}
                            }
                        },
                        "errors": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "next_step_suggestion": {
                            "type": "string",
                            "description": "Рекомендация для следующего шага"
                        },
                        "requires_additional_action": {
                            "type": "boolean"
                        }
                    },
                    "required": ["status", "observation", "requires_additional_action"],
                    "additionalProperties": True
                }
                self._log_info("⚠️ [Observer.analyze] Контракт behavior.react.observe не найден, используем fallback схему", event_type=EventType.WARNING)
            
            # Форматируем результат
            result_str = self._format_result(result)
            error_str = error or ""
            
            # Строим prompt
            prompt = self._build_observation_prompt(
                action_name=action_name,
                parameters=parameters,
                result=result_str,
                error=error_str
            )
            
            self._log_info(
                f"👁️ [Observer.analyze] Анализ результата: action={action_name}, error={bool(error)}",
                event_type=EventType.INFO
            )
            
            # Вызов LLM
            orchestrator = self.llm_orchestrator
            provider = self.llm_provider
            
            if not orchestrator or not provider:
                self._log_error("LLM orchestrator или provider не доступен")
                return self._fallback_observation(result, error)
            
            llm_request = LLMRequest(
                prompt=prompt,
                system_prompt="Ты — аналитик результатов выполнения действий агента. Твоя задача — объективно оценить результат и дать рекомендации.",
                temperature=0.2,
                max_tokens=800,
                structured_output=StructuredOutputConfig(
                    output_model=None,  # Не используем имя модели, передаём схему напрямую
                    schema_def=schema,
                    max_retries=2,
                    strict_mode=False
                )
            )
            
            result_obj = await orchestrator.execute_structured(
                request=llm_request,
                provider=provider,
                session_id=session_id,
                agent_id=agent_id,
                step_number=step_number,
                phase='observe',
                use_native_structured_output=False
            )
            
            if not result_obj or not hasattr(result_obj, 'parsed_content') or result_obj.parsed_content is None:
                self._log_error(f"LLM вернул невалидный ответ: {result_obj}")
                return self._fallback_observation(result, error)
            
            observation = result_obj.parsed_content
            
            # Конвертация в dict
            if hasattr(observation, 'model_dump'):
                obs_dict = observation.model_dump()
            elif hasattr(observation, 'dict'):
                obs_dict = observation.dict()
            elif isinstance(observation, dict):
                obs_dict = observation
            else:
                obs_dict = {"status": "partial", "observation": str(observation), "requires_additional_action": True}
            
            self._log_info(
                f"✅ [Observer.analyze] Наблюдение: status={obs_dict.get('status')}, quality={obs_dict.get('data_quality', {})}",
                event_type=EventType.INFO
            )
            
            return obs_dict
            
        except Exception as e:
            self._log_error(f"Ошибка в Observer.analyze: {e}", exc_info=True)
            return self._fallback_observation(result, error)
    
    def _build_observation_prompt(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: str,
        error: str
    ) -> str:
        """
        Построение prompt для анализа результата.
        
        ПАРАМЕТРЫ:
        - action_name: имя действия
        - parameters: параметры
        - result: результат
        - error: ошибка
        
        ВОЗВРАЩАЕТ:
        - prompt текст
        """
        # Формируем детальную информацию о параметрах
        params_detail = ""
        if parameters:
            for key, value in parameters.items():
                params_detail += f"  - {key}: {value}\n"
        
        return f"""
ACTION: {action_name}

PARAMETERS:
{self._truncate(str(parameters), 500)}

PARAMETER DETAILS:
{params_detail if params_detail else "  (none)"}

RESULT:
{self._truncate(result, 1500)}

ERROR:
{error if error else "None"}

---

Проанализируй результат выполнения действия. ВАЖНО: твой ответ должен быть информативным и содержать конкретные данные из результата.

1. STATUS: Был ли результат успешным?
   - success: данные получены и полезны
   - partial: данные получены но неполные
   - empty: данных нет (пустой результат)
   - error: произошла ошибка

2. OBSERVATION: Напиши ПОДРОБНОЕ описание что именно получено.
   - Для vector_search: укажи количество найденных результатов, примеры найденных текстов с оценками (score)
   - Для SQL запросов: укажи количество строк, примеры данных из первых строк
   - Для других инструментов: опиши структуру и содержимое результата
   - Если данных МНОГО (более 5 строк или 1000 символов) — укажи статистику и напиши: "Для полного анализа используйте data_analysis.analyze_step_data"

3. KEY FINDINGS: Извлеки КОНКРЕТНЫЕ факты из данных (например, найденные тексты, значения полей, статистика)

4. DATA_QUALITY: Насколько качественны данные?
   - completeness: 0.0–1.0 (насколько полные данные)
   - reliability: 0.0–1.0 (насколько надёжны данные)

5. NEXT STEP SUGGESTION: Что делать дальше?
   - Если данных много — рекомендуй использовать data_analysis.analyze_step_data
   - Если данных недостаточно — предложи изменить параметры или использовать другой инструмент

Ответь в формате JSON согласно схеме. Поле "observation" должно содержать ДЕТАЛЬНОЕ описание с конкретными данными.
""".strip()
    
    def _format_result(self, result: Any) -> str:
        """Форматирование результата в строку."""
        if result is None:
            return "None"
        
        if isinstance(result, dict):
            # Извлекаем полезные данные
            data = (
                result.get('result') or
                result.get('data') or
                result.get('rows') or
                result.get('output') or
                result
            )
            return self._truncate(str(data), 1000)
        
        if hasattr(result, 'model_dump'):
            return self._truncate(str(result.model_dump()), 1000)
        
        if hasattr(result, 'dict'):
            return self._truncate(str(result.dict()), 1000)
        
        return self._truncate(str(result), 1000)
    
    def _truncate(self, text: str, max_length: int) -> str:
        """Обрезка текста до максимальной длины."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "... [truncated]"
    
    def _fallback_observation(self, result: Any, error: Optional[str]) -> Dict[str, Any]:
        """
        Fallback наблюдение при ошибке LLM.
        
        ПАРАМЕТРЫ:
        - result: результат
        - error: ошибка
        
        ВОЗВРАЩАЕТ:
        - базовое наблюдение
        """
        if error:
            return {
                "status": "error",
                "observation": f"Error during execution: {error}",
                "key_findings": [],
                "data_quality": {"completeness": 0.0, "reliability": 0.0},
                "errors": [error],
                "next_step_suggestion": "Try a different approach or fix the error",
                "requires_additional_action": True
            }
        
        if result is None or (isinstance(result, (list, dict)) and len(result) == 0):
            return {
                "status": "empty",
                "observation": "Empty result received",
                "key_findings": [],
                "data_quality": {"completeness": 0.0, "reliability": 0.5},
                "errors": [],
                "next_step_suggestion": "Try different parameters or a different tool",
                "requires_additional_action": True
            }
        
        return {
            "status": "partial",
            "observation": "Result received but not analyzed by LLM",
            "key_findings": ["Result exists"],
            "data_quality": {"completeness": 0.5, "reliability": 0.5},
            "errors": [],
            "next_step_suggestion": "Continue with caution",
            "requires_additional_action": True
        }

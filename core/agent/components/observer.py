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
        
        # Успешный результат - базовая оценка качества
        completeness = 1.0
        reliability = 0.8
        
        if isinstance(result, dict):
            data = result.get('result') or result.get('data') or result.get('rows', [])
            if isinstance(data, list):
                row_count = len(data)
                if row_count == 0:
                    completeness = 0.0
                elif row_count < 5:
                    completeness = 0.5
                elif row_count > 100:
                    completeness = 1.0
                else:
                    completeness = 0.8
                
                # Проверяем наличие warning-флагов
                if result.get('warning') or result.get('truncated'):
                    reliability = 0.6
                    self._log_info(
                        f"⚠️ [Rule-based] Result has warnings: {result.get('warning', 'N/A')}",
                        event_type=EventType.WARNING
                    )
        elif isinstance(result, list):
            if len(result) == 0:
                completeness = 0.0
            elif len(result) < 5:
                completeness = 0.5
            else:
                completeness = 0.8
        
        return {
            "status": "success",
            "observation": f"Action '{action_name}' completed successfully",
            "key_findings": [f"Received {type(result).__name__} result"],
            "data_quality": {"completeness": completeness, "reliability": reliability},
            "errors": [],
            "next_step_suggestion": "Continue with next step based on goal progress",
            "requires_additional_action": False,
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
        return f"""
ACTION:
{action_name}

PARAMETERS:
{self._truncate(str(parameters), 500)}

RESULT:
{self._truncate(result, 1000)}

ERROR:
{error if error else "None"}

---

Проанализируй результат выполнения действия и оцени:

1. STATUS: Был ли результат успешным?
   - success: данные получены и полезны
   - partial: данные получены но неполные
   - empty: данных нет (пустой результат)
   - error: произошла ошибка

2. QUALITY: Насколько качественны данные?
   - completeness: 0.0–1.0 (насколько полные данные)
   - reliability: 0.0–1.0 (насколько надёжны данные)

3. KEY FINDINGS: Какие важные факты можно извлечь?

4. ERRORS: Какие проблемы обнаружены?

5. NEXT STEP SUGGESTION: Что делать дальше?

Ответь в формате JSON согласно схеме.
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

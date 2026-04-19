"""
Observer — LLM-анализ результатов выполнения действий.

АРХИТЕКТУРА:
1. Анализирует результат действия через LLM
2. Оценивает статус, качество, проблемы
3. Генерирует insight и рекомендации для следующего шага
4. Использует контракт behavior.react.observe_output_v1.0.0
"""
from typing import Any, Dict, Optional
from core.infrastructure.logging.event_types import LogEventType


class Observer:
    """
    Компонент наблюдения за результатами выполнения.
    
    ОТВЕТСТВЕННОСТЬ:
    - Анализ результата действия (success/error/empty/partial)
    - Оценка качества данных
    - Выявление проблем и инсайтов
    - Генерация рекомендаций для следующего шага
    """
    
    DEPENDENCIES = ["prompt_service", "contract_service", "llm_orchestrator"]
    
    def __init__(
        self,
        application_context=None,
        component_name: str = "observer"
    ):
        self.application_context = application_context
        self.component_name = component_name
    
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
            logger.info(message, extra={"event_type": event_type or LogEventType.INFO})

    def _log_error(self, message: str, exc_info=False):
        """Логирование error уровня."""
        if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
            log_session = self.application_context.infrastructure_context.log_session
            logger = log_session.get_component_logger("observer")
            logger.error(message, extra={"event_type": LogEventType.ERROR}, exc_info=exc_info)
    
    async def analyze(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: Any,
        error: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_number: Optional[int] = None
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
        
        ВОЗВРАЩАЕТ:
        - observation: структурированное наблюдение
        """
        try:
            from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
            
            # Получаем контракт
            output_contract = None
            if self.application_context and hasattr(self.application_context, 'get_output_contract'):
                output_contract = self.application_context.get_output_contract("behavior.react.observe")
            
            # Schema из контракта
            schema = None
            if output_contract:
                if hasattr(output_contract, 'model_json_schema'):
                    schema = output_contract.model_json_schema()
                elif hasattr(output_contract, 'model_schema'):
                    schema = output_contract.model_schema
            
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
                self._log_info("⚠️ [Observer.analyze] Контракт behavior.react.observe не найден, используем fallback схему", event_type=LogEventType.WARNING)
            
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
                event_type=LogEventType.INFO
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
                    output_model="ObservationResult",
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
                event_type=LogEventType.INFO
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

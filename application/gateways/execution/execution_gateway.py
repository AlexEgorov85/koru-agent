оаfrom typing import Dict, Any
from domain.abstractions.system.base_system_context import IBaseSystemContext
from domain.abstractions.system.base_session_context import BaseSessionContext
from domain.models.capability import Capability
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus
from application.services.llm_decision_validator import llm_validator, ValidationResult


class ExecutionGateway:
    """
    Шлюз выполнения capability.
    
    Отвечает за:
    1. Поиск навыка по capability
    2. Выполнение capability через навык
    3. Базовую обработку исключений
    """
    
    def __init__(self, system_context: IBaseSystemContext):
        self._system_context = system_context

    @staticmethod
    def _create_failed_result(error: str, summary: str) -> ExecutionResult:
        """Создание результата с ошибкой."""
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            result=None,
            observation_item_id=None,
            summary=summary,
            error=error
        )

    @staticmethod
    def _create_success_result(result: Any, summary: str) -> ExecutionResult:
        """Создание успешного результата."""
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result=result,
            observation_item_id=None,  # ID будет установлен в сессии
            summary=summary,
            error=None
        )

    async def execute_capability(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        session: BaseSessionContext,
        step_number: int = 0
    ) -> ExecutionResult:
        """
        Выполнение capability через соответствующий навык.
        Включает предварительную валидацию решения от LLM.
        
        Args:
            capability: Объект capability для выполнения
            parameters: Параметры для выполнения (может содержать LLMResponse)
            session: Контекст сессии
            step_number: Номер шага (для отслеживания)
            
        Returns:
            ExecutionResult с результатом выполнения
        """
        # Проверяем, является ли parameters объектом LLMResponse (или содержит его)
        from infrastructure.gateways.llm_providers.base_provider import LLMResponse
        llm_response = None
        actual_params = parameters

        if isinstance(parameters, dict):
            # Проверяем, есть ли в параметрах объект LLMResponse
            if 'llm_response' in parameters:
                llm_response = parameters['llm_response']
            elif isinstance(parameters.get('raw_text'), str):  # Вероятно, это сам LLMResponse
                # Извлекаем только нужные поля, учитывая порядок в определении LLMResponse
                llm_data = {k: v for k, v in parameters.items() if k in ['raw_text', 'model', 'tokens_used', 'generation_time', 'parsed', 'validation_error', 'validation_attempts', 'validation_chain', 'finish_reason', 'is_truncated', 'metadata']}
                # Убедимся, что обязательные поля присутствуют
                if 'raw_text' in llm_data and 'model' in llm_data and 'tokens_used' in llm_data and 'generation_time' in llm_data:
                    llm_response = LLMResponse(**llm_data)
                    actual_params = {}
                else:
                    actual_params = parameters
            else:
                actual_params = parameters
        elif isinstance(parameters, LLMResponse):
            llm_response = parameters
            actual_params = {}

        # Если есть ответ от LLM, выполняем валидацию
        if llm_response and hasattr(llm_response, 'raw_text'):
            # Проверяем, содержит ли ответ ошибку валидации
            if hasattr(llm_response, 'validation_error') and llm_response.validation_error:
                # Логируем ошибку валидации
                self._log_validation_error(llm_response.validation_error, llm_response.raw_text)
                
                # В зависимости от типа ошибки принимаем решение
                if self._is_critical_validation_error(llm_response.validation_error):
                    return self._create_failed_result(
                        error=f"Критическая ошибка валидации: {llm_response.validation_error}",
                        summary="Невозможно обработать решение от LLM"
                    )
                else:
                    # Пробуем fallback стратегию
                    return await self._handle_fallback_execution(capability, actual_params, session, llm_response)
            else:
                # Если валидация прошла успешно, используем parsed данные
                if llm_response.parsed:
                    actual_params = llm_response.parsed

        # 1. Получение навыка для capability
        skill = self._system_context.get_resource(capability.skill_name)
        if not skill:
            return self._create_failed_result(
                error=f"Skill for capability '{capability.name}' not found",
                summary=f"Cannot execute capability '{capability.name}'"
            )
        
        # 2. Выполнение через навык
        try:
            result = await skill.execute(actual_params, session)
            return self._create_success_result(
                result=result,
                summary=f"Capability '{capability.name}' executed successfully"
            )
        except Exception as e:
            return self._create_failed_result(
                error=str(e),
                summary=f"Error executing capability '{capability.name}': {str(e)}"
            )
    
    def _log_validation_error(self, validation_error: str, raw_text: str) -> None:
        """Логирование ошибки валидации"""
        print(f"Валидация LLM ответа не удалась: {validation_error}")
        print(f"Сырой ответ: {raw_text[:200]}...")
    
    def _is_critical_validation_error(self, validation_error: str) -> bool:
        """Проверяет, является ли ошибка критической"""
        # Критические ошибки - это те, которые указывают на серьезные проблемы
        critical_indicators = [
            "empty response",  # Пустой ответ
            "JSONDecodeError",  # Не удалось распарсить JSON
        ]
        return any(indicator in validation_error.lower() for indicator in critical_indicators)
    
    async def _handle_fallback_execution(self, capability: Capability, parameters: Dict[str, Any], 
                                      session: BaseSessionContext, llm_response) -> ExecutionResult:
        """Обработка выполнения с fallback стратегией"""
        # Пока используем стандартную логику, но в будущем можно добавить более сложную логику
        return await self.execute_capability(capability, parameters, session)
    

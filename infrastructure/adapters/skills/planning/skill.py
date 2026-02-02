"""
PlanningSkill - навык для планирования задач и генерации кода на основе требований.
"""
from typing import Dict, Any, List

from domain.abstractions.skills.base_skill import BaseSkill
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus
from domain.models.capability import Capability


class PlanningSkill(BaseSkill):
    """
    Навык для планирования задач и генерации кода на основе требований.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (адаптер)
    - Зависимости: только от абстракций (BaseSkill)
    - Ответственность: планирование и генерация кода
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    name = "planning"
    
    def __init__(self):
        """Инициализация навыка."""
        self.name = "planning"
    
    def get_capabilities(self) -> List[Capability]:
        """Получение списка capability навыка."""
        return [
            Capability(
                name="planning.generate_plan",
                description="Генерация плана реализации задачи",
                parameters_schema=None,
                parameters_class=None,
                skill_name=self.name
            ),
            Capability(
                name="planning.generate_code",
                description="Генерация кода на основе требований",
                parameters_schema=None,
                parameters_class=None,
                skill_name=self.name
            )
        ]
    
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """Выполнение capability навыка."""
        try:
            # Маршрутизация по capability
            if capability.name == "planning.generate_plan":
                return await self._generate_plan(parameters, context)
            elif capability.name == "planning.generate_code":
                return await self._generate_code(parameters, context)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Неизвестная capability: {capability.name}",
                    error="UNKNOWN_CAPABILITY"
                )
                
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка выполнения: {str(e)}",
                error="EXECUTION_ERROR"
            )
    
    async def _generate_plan(self, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """
        Генерация плана реализации задачи.
        """
        try:
            # Заглушка для реализации генерации плана
            result_data = {
                "message": "Plan generation completed",
                "parameters": parameters,
                "plan": []
            }
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=None,
                summary="Генерация плана завершена",
                error=None
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка генерации плана: {str(e)}",
                error="PLAN_GENERATION_ERROR"
            )
    
    async def _generate_code(self, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """
        Генерация кода на основе требований.
        """
        try:
            # Заглушка для реализации генерации кода
            result_data = {
                "message": "Code generation completed",
                "parameters": parameters,
                "generated_code": ""
            }
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=None,
                summary="Генерация кода завершена",
                error=None
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка генерации кода: {str(e)}",
                error="CODE_GENERATION_ERROR"
            )
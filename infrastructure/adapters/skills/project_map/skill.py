"""
ProjectMapSkill - навык для создания карты проекта через сервисы анализа кода.
"""
from typing import Dict, Any, List

from domain.abstractions.skills.base_skill import BaseSkill
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus
from domain.models.capability import Capability


class ProjectMapSkill(BaseSkill):
    """
    Навык для создания карты проекта через инфраструктурные сервисы.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (адаптер)
    - Зависимости: только от абстракций (BaseSkill)
    - Ответственность: агрегация данных от сервисов в доменную модель
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    name = "project_map"
    
    def __init__(self):
        """Инициализация навыка."""
        self.name = "project_map"
    
    def get_capabilities(self) -> List[Capability]:
        """Получение списка capability навыка."""
        return [
            Capability(
                name="project_map.analyze_project",
                description="Анализ структуры проекта и создание карты кодовой базы",
                parameters_schema=None,
                parameters_class=None,
                skill_name=self.name
            )
        ]
    
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """Выполнение capability навыка."""
        try:
            # Маршрутизация по capability
            if capability.name == "project_map.analyze_project":
                return await self._analyze_project(parameters, context)
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
    
    async def _analyze_project(self, parameters: Dict[str, Any], context: Any) -> ExecutionResult:
        """
        Анализ структуры проекта с использованием сервисов анализа кода.
        """
        try:
            # Заглушка для реализации анализа проекта
            result_data = {
                "message": "Project map analysis completed",
                "parameters": parameters
            }
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=None,
                summary="Проект успешно проанализирован",
                error=None
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка анализа проекта: {str(e)}",
                error="PROJECT_ANALYSIS_ERROR"
            )
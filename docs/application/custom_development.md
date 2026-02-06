# Разработка компонентов приложений под свои задачи

В этом разделе описаны рекомендации и практики по адаптации и расширению компонентов слоя приложений Composable AI Agent Framework для удовлетворения специфических требований и задач. Вы узнаете, как модифицировать существующие компоненты приложений и создавать новые для расширения функциональности системы.

## Архитектура слоя приложений

### 1. Сервисы приложений

Слой приложений содержит сервисы, которые координируют работу компонентов домена и инфраструктуры:

```python
# application/services/base_service.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from domain.abstractions.service import IService
import asyncio
import time
import logging

class IApplicationService(IService):
    """Интерфейс сервиса приложений"""
    
    @abstractmethod
    async def execute_operation(self, operation_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить операцию сервиса"""
        pass
    
    @abstractmethod
    def validate_operation(self, operation_name: str, parameters: Dict[str, Any]) -> bool:
        """Проверить корректность операции"""
        pass

class BaseService(IApplicationService, ABC):
    """Базовый класс для сервисов приложений"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialized = False
        self._metrics = {}
        self._event_publisher = None
        self._repository = None
        self._action_executor = None
        self._pattern_executor = None
        self._resource_manager = None
        self._security_monitor = None
    
    async def initialize(self):
        """Инициализировать сервис"""
        if not self._initialized:
            await self._perform_initialization()
            self._initialized = True
            self.logger.info(f"Сервис {self.__class__.__name__} инициализирован")
    
    async def _perform_initialization(self):
        """Выполнить специфическую инициализацию"""
        # Подключение к репозиторию
        if "repository_config" in self.config:
            self._repository = await self._create_repository(self.config["repository_config"])
        
        # Настройка публикатора событий
        if "event_publisher" in self.config:
            self._event_publisher = self.config["event_publisher"]
        
        # Настройка исполнителя действий
        if "action_executor" in self.config:
            self._action_executor = self.config["action_executor"]
        
        # Настройка исполнителя паттернов
        if "pattern_executor" in self.config:
            self._pattern_executor = self.config["pattern_executor"]
        
        # Инициализация менеджера ресурсов
        if "resource_limits" in self.config:
            from application.services.resource_manager import ResourceManager
            self._resource_manager = ResourceManager(self.config["resource_limits"])
        
        # Инициализация монитора безопасности
        if self.config.get("enable_security_monitoring", False):
            from application.services.security_monitor import SecurityMonitor
            self._security_monitor = SecurityMonitor()
    
    async def execute_operation(self, operation_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить операцию сервиса с обработкой ошибок и безопасностью"""
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Проверить безопасность операции
            security_check = await self._perform_security_check(operation_name, parameters)
            if not security_check["allowed"]:
                return {
                    "success": False,
                    "error": f"Операция не прошла проверку безопасности: {security_check['reason']}",
                    "security_violation": True
                }
            
            # Проверить ограничения ресурсов
            if self._resource_manager:
                if not await self._resource_manager.check_availability(parameters):
                    return {
                        "success": False,
                        "error": "Недостаточно ресурсов для выполнения операции",
                        "resource_limit_exceeded": True
                    }
            
            # Проверить операцию
            if not self.validate_operation(operation_name, parameters):
                return {
                    "success": False,
                    "error": f"Некорректная операция {operation_name} с параметрами {parameters}"
                }
            
            # Выполнить специфическую логику операции
            result = await self._execute_operation_logic(operation_name, parameters)
            
            # Обновить метрики
            execution_time = time.time() - start_time
            await self._update_metrics(operation_name, success=True, execution_time=execution_time)
            
            # Опубликовать событие успешного выполнения
            if self._event_publisher:
                await self._event_publisher.publish("operation_completed", {
                    "service": self.__class__.__name__,
                    "operation": operation_name,
                    "parameters": parameters,
                    "result": result,
                    "execution_time": execution_time
                })
            
            return {"success": True, **result}
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Обновить метрики ошибки
            await self._update_metrics(operation_name, success=False, execution_time=execution_time, error=str(e))
            
            # Опубликовать событие ошибки
            if self._event_publisher:
                await self._event_publisher.publish("operation_failed", {
                    "service": self.__class__.__name__,
                    "operation": operation_name,
                    "parameters": parameters,
                    "error": str(e),
                    "execution_time": execution_time
                })
            
            self.logger.error(f"Ошибка при выполнении операции {operation_name}: {str(e)}")
            
            return {
                "success": False,
                "error": f"Ошибка при выполнении операции: {str(e)}"
            }
    
    def validate_operation(self, operation_name: str, parameters: Dict[str, Any]) -> bool:
        """Проверить корректность операции"""
        # Проверить, поддерживается ли операция
        method_name = f"_validate_{operation_name}"
        if not hasattr(self, method_name):
            return False
        
        # Выполнить специфическую проверку
        validator = getattr(self, method_name)
        return validator(parameters)
    
    async def _execute_operation_logic(self, operation_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить логику операции"""
        method_name = f"_execute_{operation_name}"
        if not hasattr(self, method_name):
            raise ValueError(f"Операция {operation_name} не поддерживается сервисом {self.__class__.__name__}")
        
        executor = getattr(self, method_name)
        return await executor(parameters)
    
    async def _perform_security_check(self, operation_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить проверку безопасности операции"""
        if self._security_monitor:
            return await self._security_monitor.check_operation(operation_name, parameters)
        
        # Если монитор безопасности не инициализирован, выполнить базовую проверку
        return await self._perform_basic_security_check(operation_name, parameters)
    
    async def _perform_basic_security_check(self, operation_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить базовую проверку безопасности"""
        # Проверить на наличие чувствительных данных
        sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
        
        for field in sensitive_fields:
            if field in parameters:
                return {
                    "allowed": False,
                    "reason": f"Чувствительное поле '{field}' обнаружено в параметрах операции"
                }
        
        # Проверить размер параметров
        params_size = len(str(parameters))
        max_size = self.config.get("max_parameters_size", 10 * 1024 * 1024)  # 10MB
        if params_size > max_size:
            return {
                "allowed": False,
                "reason": f"Параметры операции слишком велики: {params_size} байт, максимум {max_size}"
            }
        
        return {"allowed": True, "reason": "Безопасность проверена"}
    
    async def _update_metrics(self, operation_name: str, success: bool, execution_time: float = 0, error: str = None):
        """Обновить метрики выполнения операции"""
        if operation_name not in self._metrics:
            self._metrics[operation_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_execution_time": 0,
                "avg_execution_time": 0,
                "errors": []
            }
        
        op_metrics = self._metrics[operation_name]
        op_metrics["total_calls"] += 1
        
        if success:
            op_metrics["successful_calls"] += 1
            op_metrics["total_execution_time"] += execution_time
            op_metrics["avg_execution_time"] = op_metrics["total_execution_time"] / op_metrics["successful_calls"]
        else:
            op_metrics["failed_calls"] += 1
            if error:
                op_metrics["errors"].append(error)
    
    async def _create_repository(self, repo_config: Dict[str, Any]):
        """Создать репозиторий для сервиса"""
        # В реальной реализации здесь будет создание репозитория
        # на основе конфигурации
        pass
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики сервиса"""
        return self._metrics.copy()
    
    def reset_metrics(self):
        """Сбросить метрики сервиса"""
        self._metrics = {}
```

### 2. Оркестрация приложений

Слой оркестрации координирует выполнение задач:

```python
# application/orchestration/base_orchestrator.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from domain.models.agent.agent_state import AgentState
from domain.abstractions.thinking_pattern import IThinkingPattern

class IOrchestrator(ABC):
    """Интерфейс оркестратора"""
    
    @abstractmethod
    async def execute_plan(self, plan: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить план действий"""
        pass
    
    @abstractmethod
    async def coordinate_agents(self, agents: List[Any], task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Координация работы агентов"""
        pass

class BaseOrchestrator(IOrchestrator, ABC):
    """Базовый класс для оркестраторов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._pattern_executor = None
        self._action_executor = None
        self._agent_coordinator = None
        self._task_scheduler = None
        self._resource_manager = None
        self._security_policy = self.config.get("security_policy", {})
        self._initialized = False
    
    async def initialize(self):
        """Инициализировать оркестратор"""
        if not self._initialized:
            await self._initialize_components()
            self._initialized = True
    
    async def _initialize_components(self):
        """Инициализировать компоненты оркестратора"""
        from application.orchestration.pattern_executor import PatternExecutor
        from application.orchestration.atomic_action_executor import AtomicActionExecutor
        from application.orchestration.agent_coordinator import AgentCoordinator
        from application.orchestration.task_scheduler import TaskScheduler
        from application.orchestration.resource_manager import ResourceManager
        
        self._pattern_executor = PatternExecutor()
        self._action_executor = AtomicActionExecutor()
        self._agent_coordinator = AgentCoordinator()
        self._task_scheduler = TaskScheduler()
        self._resource_manager = ResourceManager()
        
        # Инициализировать все компоненты
        components = [
            self._pattern_executor,
            self._action_executor,
            self._agent_coordinator,
            self._task_scheduler,
            self._resource_manager
        ]
        
        for component in components:
            if hasattr(component, 'initialize'):
                await component.initialize()
    
    async def execute_plan(self, plan: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить план действий с проверками безопасности и ресурсов"""
        if not self._initialized:
            await self.initialize()
        
        results = []
        
        for step in plan:
            step_type = step.get("type")
            step_params = step.get("parameters", {})
            
            try:
                # Проверить политику безопасности для шага
                if not self._check_step_security_policy(step_type, step_params):
                    return {
                        "success": False,
                        "error": f"Шаг {step_type} не соответствует политике безопасности",
                        "security_violation": True
                    }
                
                # Проверить доступность ресурсов для шага
                if self._resource_manager:
                    if not await self._resource_manager.check_step_resources(step_type, step_params):
                        return {
                            "success": False,
                            "error": f"Недостаточно ресурсов для выполнения шага {step_type}",
                            "resource_limit_exceeded": True
                        }
                
                if step_type == "pattern":
                    result = await self._execute_pattern_step(step_params, context)
                elif step_type == "action":
                    result = await self._execute_action_step(step_params, context)
                elif step_type == "task":
                    result = await self._execute_task_step(step_params, context)
                else:
                    result = {
                        "success": False,
                        "error": f"Неизвестный тип шага: {step_type}"
                    }
                
                results.append(result)
                
                # Проверить, нужно ли прервать выполнение
                if not result.get("continue_execution", True):
                    break
            except Exception as e:
                results.append({
                    "success": False,
                    "error": f"Ошибка при выполнении шага: {str(e)}",
                    "step": step
                })
                break
        
        return {
            "success": True,
            "results": results,
            "plan_executed": len(results),
            "plan_total": len(plan)
        }
    
    async def _execute_pattern_step(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг паттерна"""
        pattern_name = parameters.get("pattern_name")
        pattern_context = parameters.get("context", context)
        
        if not pattern_name:
            return {"success": False, "error": "Не указано имя паттерна"}
        
        # Найти и выполнить паттерн
        pattern = await self._find_pattern(pattern_name)
        if not pattern:
            return {"success": False, "error": f"Паттерн {pattern_name} не найден"}
        
        try:
            result = await pattern.execute(
                state=AgentState(),
                context=pattern_context,
                available_capabilities=parameters.get("available_capabilities", [])
            )
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": f"Ошибка выполнения паттерна: {str(e)}"}
    
    async def _execute_action_step(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг действия"""
        action_name = parameters.get("action_name")
        action_params = parameters.get("parameters", {})
        
        if not action_name:
            return {"success": False, "error": "Не указано имя действия"}
        
        try:
            result = await self._action_executor.execute_action(action_name, action_params)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": f"Ошибка выполнения действия: {str(e)}"}
    
    async def _execute_task_step(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг задачи"""
        task_description = parameters.get("task_description")
        task_context = parameters.get("context", context)
        
        if not task_description:
            return {"success": False, "error": "Не указано описание задачи"}
        
        # Выполнить задачу через координатора агентов
        result = await self._agent_coordinator.execute_task(task_description, task_context)
        return {"success": True, "result": result}
    
    async def _find_pattern(self, pattern_name: str) -> Optional[IThinkingPattern]:
        """Найти паттерн по имени"""
        # В реальной реализации здесь будет поиск паттерна
        # в реестре зарегистрированных паттернов
        pass
    
    def _check_step_security_policy(self, step_type: str, parameters: Dict[str, Any]) -> bool:
        """Проверить, соответствует ли шаг политике безопасности"""
        # Проверить политику безопасности для типа шага
        allowed_step_types = self._security_policy.get("allowed_step_types", [
            "pattern", "action", "task", "validation", "analysis"
        ])
        
        if step_type not in allowed_step_types:
            return False
        
        # Проверить параметры на безопасность
        sensitive_params = ["password", "token", "api_key", "secret", "credentials"]
        for param_name in sensitive_params:
            if param_name in parameters:
                return False  # Не разрешать чувствительные параметры в шагах
        
        return True
    
    async def coordinate_agents(self, agents: List[Any], task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Координация работы агентов с проверками безопасности"""
        if not self._initialized:
            await self.initialize()
        
        # Проверить политику безопасности для координации
        if not self._check_coordination_security_policy(agents, task, context):
            return {
                "success": False,
                "error": "Координация агентов не соответствует политике безопасности",
                "security_violation": True
            }
        
        # Планирование задач для агентов
        task_assignment = await self._plan_agent_tasks(agents, task, context)
        
        # Выполнение задач
        results = await self._execute_agent_tasks(agents, task_assignment)
        
        # Сбор результатов
        final_result = await self._aggregate_results(results)
        
        return final_result
    
    def _check_coordination_security_policy(self, agents: List[Any], task: str, context: Dict[str, Any]) -> bool:
        """Проверить политику безопасности для координации агентов"""
        # Проверить, что задача не пытается получить доступ к системным ресурсам
        task_lower = task.lower()
        if any(keyword in task_lower for keyword in ["system", "root", "admin", "kernel"]):
            return False
        
        # Проверить контекст на наличие чувствительных данных
        if context:
            sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
            for field in sensitive_fields:
                if field in context:
                    return False
        
        return True
    
    async def _plan_agent_tasks(self, agents: List[Any], task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Спланировать задачи для агентов"""
        # Определить, какие агенты могут выполнить задачу
        capable_agents = []
        for agent in agents:
            if await self._can_agent_handle_task(agent, task, context):
                capable_agents.append(agent)
        
        # Назначить задачи агентам
        task_assignments = {}
        for i, agent in enumerate(capable_agents):
            task_assignments[f"agent_{i}"] = {
                "agent": agent,
                "task": task,
                "context": context
            }
        
        return task_assignments
    
    async def _execute_agent_tasks(self, agents: List[Any], task_assignments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Выполнить задачи агентов"""
        results = []
        
        for agent_id, assignment in task_assignments.items():
            agent = assignment["agent"]
            task_desc = assignment["task"]
            task_context = assignment["context"]
            
            try:
                result = await agent.execute_task(task_desc, task_context)
                results.append({
                    "agent_id": agent_id,
                    "success": True,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "agent_id": agent_id,
                    "success": False,
                    "error": f"Ошибка выполнения задачи агентом: {str(e)}"
                })
        
        return results
    
    async def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Агрегировать результаты от агентов"""
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]
        
        return {
            "total_agents": len(results),
            "successful_agents": len(successful_results),
            "failed_agents": len(failed_results),
            "results": successful_results,
            "failures": failed_results,
            "overall_success": len(successful_results) == len(results)
        }
    
    async def _can_agent_handle_task(self, agent: Any, task: str, context: Dict[str, Any]) -> bool:
        """Проверить, может ли агент обработать задачу"""
        # В реальной реализации здесь будет проверка
        # возможностей агента и соответствия задаче
        return True
```

## Создание специфических компонентов приложений

### 1. Специфические сервисы

Для создания сервисов под специфические задачи:

```python
# application/services/specialized_services.py
from typing import Dict, Any, List
from application.services.base_service import BaseService
from domain.models.specialized_task import SpecializedTask
from domain.abstractions.specialized_pattern import ISpecializedPattern

class ISpecializedService(IService):
    """Интерфейс специфического сервиса"""
    
    @abstractmethod
    async def execute_specialized_operation(self, task: SpecializedTask) -> Dict[str, Any]:
        """Выполнить специфическую операцию"""
        pass
    
    @abstractmethod
    def get_specialized_capabilities(self) -> List[str]:
        """Получить специфические возможности сервиса"""
        pass

class SecurityAnalysisService(BaseService):
    """Сервис анализа безопасности"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._security_patterns = []
        self._vulnerability_database = None
        self._compliance_checker = None
        self._security_policy = config.get("security_policy", {})
        
        # Инициализировать специфические компоненты
        self._initialize_security_components()
    
    def _initialize_security_components(self):
        """Инициализировать компоненты безопасности"""
        # Инициализировать базу данных уязвимостей
        if self.config.get("enable_vulnerability_database", True):
            from application.services.vulnerability_database import VulnerabilityDatabase
            self._vulnerability_database = VulnerabilityDatabase(
                db_path=self.config.get("vulnerability_db_path", "./vulnerabilities.db")
            )
        
        # Инициализировать проверку соответствия
        if self.config.get("enable_compliance_checking", True):
            from application.services.compliance_checker import ComplianceChecker
            self._compliance_checker = ComplianceChecker(
                standards=self.config.get("compliance_standards", ["owasp_top_10"])
            )
    
    async def execute_specialized_operation(self, task: SpecializedTask) -> Dict[str, Any]:
        """Выполнить специфическую операцию анализа безопасности"""
        
        if task.domain != "security_analysis":
            return {
                "success": False,
                "error": f"Сервис не поддерживает домен {task.domain}"
            }
        
        operation_type = task.operation_type
        
        if operation_type == "vulnerability_scan":
            return await self._execute_vulnerability_scan(task)
        elif operation_type == "security_review":
            return await self._execute_security_review(task)
        elif operation_type == "compliance_check":
            return await self._execute_compliance_check(task)
        elif operation_type == "risk_assessment":
            return await self._execute_risk_assessment(task)
        else:
            return {
                "success": False,
                "error": f"Операция {operation_type} не поддерживается"
            }
    
    def get_specialized_capabilities(self) -> List[str]:
        """Получить специфические возможности сервиса"""
        return [
            "vulnerability_scanning",
            "security_analysis",
            "compliance_checking",
            "risk_assessment",
            "security_reporting",
            "threat_modeling"
        ]
    
    async def _execute_vulnerability_scan(self, task: SpecializedTask) -> Dict[str, Any]:
        """Выполнить сканирование уязвимостей"""
        try:
            target = task.parameters.get("target")
            scan_type = task.parameters.get("scan_type", "comprehensive")
            scan_depth = task.parameters.get("scan_depth", "deep")
            
            # Выполнить сканирование в зависимости от типа и глубины
            if scan_type == "comprehensive":
                if scan_depth == "deep":
                    scan_results = await self._perform_deep_comprehensive_scan(target)
                else:
                    scan_results = await self._perform_shallow_comprehensive_scan(target)
            elif scan_type == "focused":
                focus_area = task.parameters.get("focus_area", "all")
                scan_results = await self._perform_focused_scan(target, focus_area)
            else:
                scan_results = await self._perform_basic_scan(target)
            
            # Проверить результаты на соответствие стандартам
            compliance_results = await self._check_compliance(scan_results)
            
            return {
                "success": True,
                "scan_results": scan_results,
                "compliance_results": compliance_results,
                "scan_type": scan_type,
                "scan_depth": scan_depth
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при сканировании уязвимостей: {str(e)}"
            }
    
    async def _execute_security_review(self, task: SpecializedTask) -> Dict[str, Any]:
        """Выполнить ревью безопасности"""
        # Реализация ревью безопасности
        pass
    
    async def _execute_compliance_check(self, task: SpecializedTask) -> Dict[str, Any]:
        """Выполнить проверку соответствия"""
        # Реализация проверки соответствия
        pass
    
    async def _execute_risk_assessment(self, task: SpecializedTask) -> Dict[str, Any]:
        """Выполнить оценку рисков"""
        # Реализация оценки рисков
        pass
    
    async def _perform_deep_comprehensive_scan(self, target: str) -> Dict[str, Any]:
        """Выполнить глубокое комплексное сканирование"""
        # В реальной реализации здесь будет глубокое сканирование
        # на наличие различных типов уязвимостей
        pass
    
    async def _perform_shallow_comprehensive_scan(self, target: str) -> Dict[str, Any]:
        """Выполнить поверхностное комплексное сканирование"""
        # В реальной реализации здесь будет быстрое сканирование
        # только на наличие наиболее критических уязвимостей
        pass
    
    async def _perform_focused_scan(self, target: str, focus_area: str) -> Dict[str, Any]:
        """Выполнить целевое сканирование"""
        # В реальной реализации здесь будет сканирование
        # только в определенной области (например, только SQL-инъекции)
        pass
    
    async def _perform_basic_scan(self, target: str) -> Dict[str, Any]:
        """Выполнить базовое сканирование"""
        # В реальной реализации здесь будет базовое сканирование
        # на наличие наиболее распространенных уязвимостей
        pass
    
    async def _check_compliance(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """Проверить соответствие стандартам безопасности"""
        if self._compliance_checker:
            return await self._compliance_checker.check(scan_results)
        else:
            return {"compliant": True, "issues": []}
    
    def _validate_vulnerability_scan_params(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры сканирования уязвимостей"""
        required_fields = ["target"]
        if not all(field in parameters for field in required_fields):
            return False
        
        target = parameters["target"]
        if not isinstance(target, str) or not target.strip():
            return False
        
        scan_type = parameters.get("scan_type", "comprehensive")
        if scan_type not in ["basic", "focused", "comprehensive"]:
            return False
        
        scan_depth = parameters.get("scan_depth", "deep")
        if scan_depth not in ["shallow", "medium", "deep"]:
            return False
        
        return True
    
    def _validate_security_review_params(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры ревью безопасности"""
        required_fields = ["target", "review_criteria"]
        return all(field in parameters for field in required_fields)
    
    def _validate_compliance_check_params(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры проверки соответствия"""
        required_fields = ["target", "standard"]
        return all(field in parameters for field in required_fields)
    
    async def _perform_security_check(self, operation_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить проверку безопасности операции"""
        # Проверить политику безопасности для операции
        if operation_name in self._security_policy.get("restricted_operations", []):
            return {
                "allowed": False,
                "reason": f"Операция {operation_name} ограничена политикой безопасности"
            }
        
        # Проверить параметры на наличие чувствительных данных
        sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
        for field in sensitive_fields:
            if field in parameters:
                return {
                    "allowed": False,
                    "reason": f"Чувствительное поле '{field}' обнаружено в параметрах"
                }
        
        return {"allowed": True, "reason": "Безопасность проверена"}
```

### 2. Специфические оркестраторы

Для создания оркестраторов под специфические задачи:

```python
# application/orchestration/specialized_orchestrators.py
from typing import Dict, Any, List
from application.orchestration.base_orchestrator import BaseOrchestrator
from application.services.security_analysis_service import SecurityAnalysisService
from application.services.code_analysis_service import CodeAnalysisService

class ISpecializedOrchestrator(IOrchestrator):
    """Интерфейс специфического оркестратора"""
    
    @abstractmethod
    async def execute_domain_specific_plan(self, domain: str, plan: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить доменно-специфический план"""
        pass

class SecurityOrchestrator(BaseOrchestrator):
    """Оркестратор для задач безопасности"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.security_service = SecurityAnalysisService(
            config=config.get("security_service_config", {})
        )
        self._security_patterns = []
        self._risk_assessment_engine = None
        self._remediation_planner = None
        self._security_policy = config.get("security_policy", {})
        
        # Инициализировать специфические компоненты
        self._initialize_security_orchestration()
    
    async def _initialize_security_orchestration(self):
        """Инициализировать компоненты оркестрации безопасности"""
        await self.security_service.initialize()
        
        # Инициализировать движок оценки рисков
        if self.config.get("enable_risk_assessment", True):
            from application.services.risk_assessment_engine import RiskAssessmentEngine
            self._risk_assessment_engine = RiskAssessmentEngine(
                risk_model_path=self.config.get("risk_model_path", "./models/risk_model.pkl")
            )
        
        # Инициализировать планировщик устранения
        if self.config.get("enable_remediation_planning", True):
            from application.services.remediation_planner import RemediationPlanner
            self._remediation_planner = RemediationPlanner()
    
    async def execute_domain_specific_plan(self, domain: str, plan: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить план в домене безопасности"""
        if domain != "security_analysis":
            return {
                "success": False,
                "error": f"Оркестратор безопасности не поддерживает домен {domain}"
            }
        
        # Проверить политику безопасности для выполнения плана
        if not self._check_plan_security_policy(plan):
            return {
                "success": False,
                "error": "План не соответствует политике безопасности",
                "security_violation": True
            }
        
        # Выполнить план с учетом специфики безопасности
        security_context = await self._enrich_context_with_security_info(context)
        
        results = []
        for step in plan:
            result = await self._execute_security_step(step, security_context)
            results.append(result)
            
            # Проверить, нужно ли прервать выполнение из-за критических уязвимостей
            if self._has_critical_vulnerabilities(result):
                if self.config.get("stop_on_critical_vulnerabilities", False):
                    break
    
    async def _enrich_context_with_security_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Обогатить контекст информацией безопасности"""
        enriched_context = context.copy()
        
        # Добавить информацию о безопасности из различных источников
        if "code" in context:
            # Добавить анализ AST для безопасности
            enriched_context["ast_analysis"] = await self._analyze_code_ast(context["code"])
        
        if "dependencies" in context:
            # Проверить зависимости на уязвимости
            enriched_context["dependency_vulnerabilities"] = await self._check_dependency_vulnerabilities(
                context["dependencies"]
            )
        
        return enriched_context
    
    async def _execute_security_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить безопасный шаг плана"""
        step_type = step.get("type")
        
        if step_type == "security_scan":
            return await self._execute_security_scan_step(step, context)
        elif step_type == "vulnerability_assessment":
            return await self._execute_vulnerability_assessment_step(step, context)
        elif step_type == "compliance_check":
            return await self._execute_compliance_check_step(step, context)
        elif step_type == "risk_analysis":
            return await self._execute_risk_analysis_step(step, context)
        elif step_type == "remediation_planning":
            return await self._execute_remediation_planning_step(step, context)
        else:
            # Для других типов шагов использовать базовую реализацию
            return await super()._execute_step(step, context)
    
    async def _execute_security_scan_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг сканирования безопасности"""
        scan_params = step.get("parameters", {})
        
        # Создать задачу специфического анализа
        task = SpecializedTask(
            id=step.get("id", "security_scan_task"),
            description=step.get("description", "Security scan task"),
            domain="security_analysis",
            operation_type="vulnerability_scan",
            parameters=scan_params
        )
        
        # Выполнить задачу через сервис безопасности
        result = await self.security_service.execute_specialized_operation(task)
        
        # Если есть движок оценки рисков, выполнить оценку
        if self._risk_assessment_engine and result.get("success"):
            risk_assessment = await self._risk_assessment_engine.assess_risks(result.get("scan_results", {}))
            result["risk_assessment"] = risk_assessment
        
        return result
    
    async def _execute_vulnerability_assessment_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг оценки уязвимостей"""
        assessment_params = step.get("parameters", {})
        
        # Выполнить комплексную оценку уязвимостей
        assessment_result = await self._perform_vulnerability_assessment(assessment_params, context)
        
        # Сформировать рекомендации по устранению
        if self._remediation_planner:
            remediation_plan = await self._remediation_planner.create_remediation_plan(assessment_result)
            assessment_result["remediation_plan"] = remediation_plan
        
        return assessment_result
    
    async def _execute_compliance_check_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг проверки соответствия"""
        compliance_params = step.get("parameters", {})
        
        # Выполнить проверку соответствия
        compliance_result = await self._perform_compliance_check(compliance_params, context)
        
        return compliance_result
    
    async def _execute_risk_analysis_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг анализа рисков"""
        risk_params = step.get("parameters", {})
        
        if self._risk_assessment_engine:
            risk_analysis = await self._risk_assessment_engine.analyze_risks(risk_params, context)
            return {"success": True, "risk_analysis": risk_analysis}
        else:
            return {
                "success": False,
                "error": "Движок оценки рисков не инициализирован"
            }
    
    async def _execute_remediation_planning_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг планирования устранения"""
        remediation_params = step.get("parameters", {})
        
        if self._remediation_planner:
            remediation_plan = await self._remediation_planner.create_plan(remediation_params, context)
            return {"success": True, "remediation_plan": remediation_plan}
        else:
            return {
                "success": False,
                "error": "Планировщик устранения не инициализирован"
            }
    
    def _has_critical_vulnerabilities(self, result: Dict[str, Any]) -> bool:
        """Проверить, есть ли критические уязвимости в результате"""
        findings = result.get("scan_results", {}).get("findings", [])
        
        for finding in findings:
            if finding.get("severity", "").upper() in ["CRITICAL", "HIGH"]:
                return True
        
        return False
    
    def _check_plan_security_policy(self, plan: List[Dict[str, Any]]) -> bool:
        """Проверить, соответствует ли план политике безопасности"""
        # Проверить каждый шаг плана на соответствие политике безопасности
        for step in plan:
            step_type = step.get("type", "")
            if step_type in self._security_policy.get("restricted_step_types", []):
                return False
        
        return True
    
    async def _analyze_code_ast(self, code: str) -> Dict[str, Any]:
        """Анализ AST кода для безопасности"""
        # В реальной реализации здесь будет анализ AST
        # для выявления потенциальных уязвимостей
        pass
    
    async def _check_dependency_vulnerabilities(self, dependencies: List[str]) -> Dict[str, Any]:
        """Проверить зависимости на уязвимости"""
        # В реальной реализации здесь будет проверка
        # зависимостей на известные уязвимости
        pass
    
    async def _perform_vulnerability_assessment(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить оценку уязвимостей"""
        # Реализация оценки уязвимостей
        pass
    
    async def _perform_compliance_check(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить проверку соответствия"""
        # Реализация проверки соответствия
        pass

class CodeAnalysisOrchestrator(BaseOrchestrator):
    """Оркестратор для задач анализа кода"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.code_analysis_service = CodeAnalysisService(
            config=config.get("code_analysis_config", {})
        )
        self._code_metrics_calculator = None
        self._quality_assessor = None
        self._complexity_analyzer = None
        
        self._initialize_code_analysis_orchestration()
    
    async def _initialize_code_analysis_orchestration(self):
        """Инициализировать компоненты оркестрации анализа кода"""
        await self.code_analysis_service.initialize()
        
        # Инициализировать калькулятор метрик кода
        if self.config.get("enable_code_metrics", True):
            from application.services.code_metrics_calculator import CodeMetricsCalculator
            self._code_metrics_calculator = CodeMetricsCalculator()
        
        # Инициализировать оценщик качества
        if self.config.get("enable_quality_assessment", True):
            from application.services.quality_assessor import QualityAssessor
            self._quality_assessor = QualityAssessor(
                quality_standards=self.config.get("quality_standards", ["pep8", "security"])
            )
        
        # Инициализировать анализатор сложности
        if self.config.get("enable_complexity_analysis", True):
            from application.services.complexity_analyzer import ComplexityAnalyzer
            self._complexity_analyzer = ComplexityAnalyzer()
    
    async def execute_domain_specific_plan(self, domain: str, plan: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить план в домене анализа кода"""
        if domain != "code_analysis":
            return {
                "success": False,
                "error": f"Оркестратор анализа кода не поддерживает домен {domain}"
            }
        
        # Выполнить план с учетом специфики анализа кода
        code_context = await self._enrich_context_with_code_info(context)
        
        results = []
        for step in plan:
            result = await self._execute_code_analysis_step(step, code_context)
            results.append(result)
        
        return {
            "success": True,
            "results": results,
            "overall_assessment": await self._aggregate_code_analysis_results(results)
        }
    
    async def _enrich_context_with_code_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Обогатить контекст информацией о коде"""
        enriched_context = context.copy()
        
        if "code" in context:
            # Вычислить метрики кода
            if self._code_metrics_calculator:
                code_metrics = await self._code_metrics_calculator.calculate_metrics(context["code"])
                enriched_context["code_metrics"] = code_metrics
            
            # Оценить качество кода
            if self._quality_assessor:
                quality_assessment = await self._quality_assessor.assess_quality(context["code"])
                enriched_context["quality_assessment"] = quality_assessment
            
            # Проанализировать сложность кода
            if self._complexity_analyzer:
                complexity_analysis = await self._complexity_analyzer.analyze(context["code"])
                enriched_context["complexity_analysis"] = complexity_analysis
        
        return enriched_context
    
    async def _execute_code_analysis_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг анализа кода"""
        step_type = step.get("type")
        
        if step_type == "syntax_analysis":
            return await self._execute_syntax_analysis_step(step, context)
        elif step_type == "security_analysis":
            return await self._execute_security_analysis_step(step, context)
        elif step_type == "quality_assessment":
            return await self._execute_quality_assessment_step(step, context)
        elif step_type == "complexity_calculation":
            return await self._execute_complexity_calculation_step(step, context)
        elif step_type == "dependency_analysis":
            return await self._execute_dependency_analysis_step(step, context)
        else:
            # Для других типов шагов использовать базовую реализацию
            return await super()._execute_step(step, context)
    
    async def _execute_syntax_analysis_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить шаг синтаксического анализа"""
        syntax_params = step.get("parameters", {})
        
        # Создать задачу анализа кода
        task = SpecializedTask(
            id=step.get("id", "syntax_analysis_task"),
            description=step.get("description", "Syntax analysis task"),
            domain="code_analysis",
            operation_type="syntax_analysis",
            parameters=syntax_params
        )
        
        # Выполнить задачу через сервис анализа кода
        result = await self.code_analysis_service.execute_specialized_operation(task)
        
        return result
    
    async def _aggregate_code_analysis_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Агрегировать результаты анализа кода"""
        # Агрегировать результаты различных шагов анализа
        aggregated = {
            "total_steps": len(results),
            "successful_steps": len([r for r in results if r.get("success", False)]),
            "syntax_issues": [],
            "security_findings": [],
            "quality_issues": [],
            "complexity_metrics": {},
            "dependency_issues": []
        }
        
        for result in results:
            if result.get("success"):
                if "syntax_analysis" in result:
                    aggregated["syntax_issues"].extend(result["syntax_analysis"].get("issues", []))
                elif "security_analysis" in result:
                    aggregated["security_findings"].extend(result["security_analysis"].get("findings", []))
                elif "quality_assessment" in result:
                    aggregated["quality_issues"].extend(result["quality_assessment"].get("issues", []))
                elif "complexity_metrics" in result:
                    aggregated["complexity_metrics"] = result["complexity_metrics"]
                elif "dependency_analysis" in result:
                    aggregated["dependency_issues"].extend(result["dependency_analysis"].get("issues", []))
        
        return aggregated
```

## Интеграция специфических компонентов

### 1. Фабрика специфических компонентов

Для создания и управления специфическими компонентами приложений:

```python
# application/factories/specialized_application_factory.py
from typing import Type, Dict, Any
from domain.abstractions.service import IService
from domain.abstractions.orchestrator import IOrchestrator
from application.services.security_analysis_service import SecurityAnalysisService
from application.orchestration.security_orchestrator import SecurityOrchestrator

class SpecializedApplicationFactory:
    """Фабрика для создания специфических компонентов приложений"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._registered_service_types = {}
        self._registered_orchestrator_types = {}
        
        # Зарегистрировать встроенные типы
        self._register_builtin_types()
    
    def _register_builtin_types(self):
        """Зарегистрировать встроенные типы компонентов приложений"""
        self.register_service_type("security_analysis", SecurityAnalysisService)
        self.register_orchestrator_type("security", SecurityOrchestrator)
        # Можно добавить другие встроенные типы
    
    def register_service_type(self, name: str, service_class: Type[IService]):
        """Зарегистрировать тип сервиса"""
        self._registered_service_types[name] = service_class
    
    def register_orchestrator_type(self, name: str, orchestrator_class: Type[IOrchestrator]):
        """Зарегистрировать тип оркестратора"""
        self._registered_orchestrator_types[name] = orchestrator_class
    
    async def create_specialized_service(self, service_type: str, **kwargs) -> IService:
        """Создать специфический сервис"""
        if service_type not in self._registered_service_types:
            raise ValueError(f"Тип сервиса '{service_type}' не зарегистрирован")
        
        service_class = self._registered_service_types[service_type]
        full_config = {**self.config.get("service_defaults", {}), **kwargs}
        
        service = service_class(full_config)
        await service.initialize()
        
        return service
    
    async def create_specialized_orchestrator(self, orchestrator_type: str, **kwargs) -> IOrchestrator:
        """Создать специфический оркестратор"""
        if orchestrator_type not in self._registered_orchestrator_types:
            raise ValueError(f"Тип оркестратора '{orchestrator_type}' не зарегистрирован")
        
        orchestrator_class = self._registered_orchestrator_types[orchestrator_type]
        full_config = {**self.config.get("orchestrator_defaults", {}), **kwargs}
        
        orchestrator = orchestrator_class(full_config)
        await orchestrator.initialize()
        
        return orchestrator
    
    def get_available_service_types(self) -> List[str]:
        """Получить доступные типы сервисов"""
        return list(self._registered_service_types.keys())
    
    def get_available_orchestrator_types(self) -> List[str]:
        """Получить доступные типы оркестраторов"""
        return list(self._registered_orchestrator_types.keys())

class AdvancedApplicationFactory(SpecializedApplicationFactory):
    """Расширенная фабрика компонентов приложений с поддержкой сложных конфигураций"""
    
    def __init__(self, base_config: Dict[str, Any] = None):
        super().__init__(base_config)
        self._middleware_registry = {}
        self._validator_registry = {}
        self._enricher_registry = {}
        self._processor_registry = {}
    
    async def create_configurable_service(
        self,
        service_type: str,
        config: Dict[str, Any] = None,
        middleware: List[Callable] = None,
        validators: List[Callable] = None,
        enrichers: List[Callable] = None,
        processors: List[Callable] = None
    ) -> IService:
        """Создать настраиваемый сервис"""
        
        # Создать базовый сервис
        service = await self.create_specialized_service(service_type, **(config or {}))
        
        # Добавить middleware
        if middleware:
            for mw_func in middleware:
                if hasattr(service, 'add_middleware'):
                    service.add_middleware(mw_func)
        
        # Добавить валидаторы
        if validators:
            for validator_func in validators:
                if hasattr(service, 'add_validator'):
                    service.add_validator(validator_func)
        
        # Добавить enrichers
        if enrichers:
            for enricher_func in enrichers:
                if hasattr(service, 'add_enricher'):
                    service.add_enricher(enricher_func)
        
        # Добавить processors
        if processors:
            for processor_func in processors:
                if hasattr(service, 'add_processor'):
                    service.add_processor(processor_func)
        
        return service
    
    async def create_configurable_orchestrator(
        self,
        orchestrator_type: str,
        config: Dict[str, Any] = None,
        security_policy: Dict[str, Any] = None,
        resource_limits: Dict[str, Any] = None,
        task_scheduler_config: Dict[str, Any] = None
    ) -> IOrchestrator:
        """Создать настраиваемый оркестратор"""
        
        # Создать базовый оркестратор
        orchestrator = await self.create_specialized_orchestrator(orchestrator_type, **(config or {}))
        
        # Применить политику безопасности
        if security_policy:
            await self._apply_security_policy(orchestrator, security_policy)
        
        # Применить ограничения ресурсов
        if resource_limits:
            await self._apply_resource_limits(orchestrator, resource_limits)
        
        # Настроить планировщик задач
        if task_scheduler_config:
            await self._configure_task_scheduler(orchestrator, task_scheduler_config)
        
        return orchestrator
    
    async def _apply_security_policy(self, orchestrator: IOrchestrator, policy: Dict[str, Any]):
        """Применить политику безопасности к оркестратору"""
        if hasattr(orchestrator, 'set_security_policy'):
            orchestrator.set_security_policy(policy)
    
    async def _apply_resource_limits(self, orchestrator: IOrchestrator, limits: Dict[str, Any]):
        """Применить ограничения ресурсов к оркестратору"""
        if hasattr(orchestrator, 'set_resource_limits'):
            orchestrator.set_resource_limits(limits)
    
    async def _configure_task_scheduler(self, orchestrator: IOrchestrator, scheduler_config: Dict[str, Any]):
        """Настроить планировщик задач оркестратора"""
        if hasattr(orchestrator, 'configure_task_scheduler'):
            await orchestrator.configure_task_scheduler(scheduler_config)
    
    def register_middleware(self, name: str, middleware_func: Callable):
        """Зарегистрировать middleware"""
        self._middleware_registry[name] = middleware_func
    
    def register_validator(self, name: str, validator_func: Callable):
        """Зарегистрировать валидатор"""
        self._validator_registry[name] = validator_func
    
    def register_enricher(self, name: str, enricher_func: Callable):
        """Зарегистрировать enricher"""
        self._enricher_registry[name] = enricher_func
    
    def register_processor(self, name: str, processor_func: Callable):
        """Зарегистрировать processor"""
        self._processor_registry[name] = processor_func
    
    def get_registered_component(self, component_type: str, name: str):
        """Получить зарегистрированный компонент"""
        registries = {
            "middleware": self._middleware_registry,
            "validator": self._validator_registry,
            "enricher": self._enricher_registry,
            "processor": self._processor_registry
        }
        
        if component_type in registries:
            return registries[component_type].get(name)
        return None
```

### 2. Пример использования специфических компонентов

```python
# specialized_application_usage.py
from application.factories.advanced_application_factory import AdvancedApplicationFactory
from domain.value_objects.domain_type import DomainType

async def specialized_application_components_example():
    """Пример использования специфических компонентов приложений"""
    
    # Создать расширенную фабрику
    factory = AdvancedApplicationFactory({
        "service_defaults": {
            "timeout": 300,
            "retry_count": 3,
            "enable_security_monitoring": True
        },
        "orchestrator_defaults": {
            "max_concurrent_tasks": 10,
            "enable_monitoring": True
        },
        "security_defaults": {
            "enable_auditing": True,
            "encrypt_sensitive_data": True
        }
    })
    
    # Зарегистрировать специфические middleware
    def security_enrichment_middleware(params):
        """Middleware для обогащения параметров безопасности"""
        if "security_context" not in params:
            params["security_context"] = {
                "scan_depth": "comprehensive",
                "vulnerability_types": ["sql_injection", "xss", "command_injection"]
            }
        return params
    
    def code_quality_validator(params):
        """Валидатор качества кода"""
        if "code" in params:
            code = params["code"]
            if len(code) > 50000:  # Если код слишком длинный
                raise ValueError("Код слишком длинный для анализа (>50,000 символов)")
        
        return True
    
    def context_enricher(context):
        """Enricher для контекста"""
        if "code" in context and "language" not in context:
            context["language"] = "python"  # Установить язык по умолчанию
        return context
    
    factory.register_middleware("security_enrichment", security_enrichment_middleware)
    factory.register_validator("code_quality", code_quality_validator)
    factory.register_enricher("default_language", context_enricher)
    
    # Создать специфический сервис анализа безопасности
    security_service = await factory.create_configurable_service(
        "security_analysis",
        config={
            "enable_vulnerability_database": True,
            "compliance_standards": ["owasp_top_10", "pci_dss"],
            "max_file_size": 10 * 1024 * 1024  # 10MB
        },
        middleware=[factory.get_registered_component("middleware", "security_enrichment")],
        validators=[factory.get_registered_component("validator", "code_quality")], 
        enrichers=[factory.get_registered_component("enricher", "default_language")]
    )
    
    # Создать специфический оркестратор безопасности
    security_orchestrator = await factory.create_configurable_orchestrator(
        "security",
        config={
            "enable_risk_assessment": True,
            "stop_on_critical_vulnerabilities": True
        },
        security_policy={
            "allowed_step_types": ["security_scan", "vulnerability_assessment", "compliance_check"],
            "restricted_operations": ["system_access", "file_modification"],
            "audit_logging": True
        },
        resource_limits={
            "max_memory_mb": 2048,
            "max_cpu_percentage": 75.0,
            "max_network_requests": 50
        },
        task_scheduler_config={
            "max_concurrent_tasks": 5,
            "task_priority_enabled": True
        }
    )
    
    # Подготовить задачу анализа безопасности
    security_task = SpecializedTask(
        id="security_task_001",
        description="Комплексный анализ безопасности Python-кода",
        domain="security_analysis",
        operation_type="vulnerability_scan",
        parameters={
            "target": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)

def execute_user_command(cmd):
    import subprocess
    result = subprocess.check_output(cmd, shell=True)
    return result
""",
            "scan_type": "comprehensive",
            "scan_depth": "deep",
            "language": "python"
        }
    )
    
    # Выполнить задачу через специфический сервис
    service_result = await security_service.execute_specialized_operation(security_task)
    print(f"Результат выполнения через сервис: {service_result}")
    
    # Подготовить план оркестрации
    orchestration_plan = [
        {
            "type": "security_scan",
            "id": "initial_scan",
            "parameters": {
                "target": security_task.parameters["target"],
                "scan_type": "comprehensive",
                "scan_depth": "deep"
            }
        },
        {
            "type": "vulnerability_assessment",
            "id": "vulnerability_assessment",
            "parameters": {
                "findings": service_result.get("scan_results", {}).get("findings", [])
            }
        },
        {
            "type": "compliance_check",
            "id": "compliance_check",
            "parameters": {
                "standard": "owasp_top_10",
                "target": security_task.parameters["target"]
            }
        },
        {
            "type": "risk_analysis",
            "id": "risk_analysis",
            "parameters": {
                "vulnerabilities": service_result.get("scan_results", {}).get("findings", [])
            }
        }
    ]
    
    # Выполнить план через оркестратор
    orchestration_result = await security_orchestrator.execute_domain_specific_plan(
        domain="security_analysis",
        plan=orchestration_plan,
        context={
            "code": security_task.parameters["target"],
            "language": security_task.parameters["language"]
        }
    )
    
    print(f"Результат оркестрации: {orchestration_result}")
    
    # Получить метрики сервиса
    service_metrics = security_service.get_metrics()
    print(f"Метрики сервиса безопасности: {service_metrics}")
    
    return {
        "service_result": service_result,
        "orchestration_result": orchestration_result,
        "service_metrics": service_metrics
    }

# Интеграция с агентами
async def agent_application_integration_example():
    """Пример интеграции специфических компонентов приложений с агентами"""
    
    # Создать фабрику агентов
    from application.factories.agent_factory import AgentFactory
    agent_factory = AgentFactory()
    
    # Создать специфические компоненты приложений
    app_factory = AdvancedApplicationFactory()
    
    # Создать сервис безопасности
    security_service = await app_factory.create_specialized_service("security_analysis")
    
    # Создать оркестратор безопасности
    security_orchestrator = await app_factory.create_specialized_orchestrator("security")
    
    # Создать агента
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Интегрировать специфические компоненты с агентом
    agent.register_service("security_analysis", security_service)
    agent.register_orchestrator("security", security_orchestrator)
    
    # Выполнить задачу с использованием специфических компонентов
    task_result = await agent.execute_task(
        task_description="Проанализируй этот Python код на наличие уязвимостей безопасности",
        context={
            "code": """
class UserAuth:
    def authenticate(self, username, password):
        # Уязвимость: SQL-инъекция
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        return execute_query(query)
        
    def execute_user_command(self, cmd):
        # Еще одна уязвимость: выполнение команд
        import subprocess
        return subprocess.check_output(cmd, shell=True)
""",
            "language": "python"
        }
    )
    
    print(f"Результат выполнения через агента с интеграцией: {task_result}")
    
    return task_result
```

## Лучшие практики

### 1. Модульность и расширяемость

Создавайте компоненты приложений, которые можно легко расширять:

```python
# Хорошо: модульные и расширяемые компоненты
class BaseService:
    """Базовый сервис"""
    pass

class AnalysisService(BaseService):
    """Сервис анализа"""
    pass

class SecurityAnalysisService(AnalysisService):
    """Сервис анализа безопасности"""
    pass

# Плохо: монолитный сервис
class MonolithicService:
    """Монолитный сервис - сложно расширять и тестировать"""
    pass
```

### 2. Безопасность и валидация

Обязательно учитывайте безопасность при создании компонентов приложений:

```python
def _validate_operation_parameters(self, parameters: Dict[str, Any]) -> List[str]:
    """Проверить параметры операции на безопасность"""
    errors = []
    
    # Проверить чувствительные поля
    sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
    for field in sensitive_fields:
        if field in parameters:
            errors.append(f"Чувствительное поле '{field}' обнаружено в параметрах операции")
    
    # Проверить размер параметров
    params_size = len(str(parameters))
    max_size = 10 * 1024 * 1024  # 10MB
    if params_size > max_size:
        errors.append(f"Параметры операции слишком велики: {params_size} байт, максимум {max_size}")
    
    # Проверить пути к файлам на безопасность
    if "file_path" in parameters:
        file_path = parameters["file_path"]
        if not self._is_safe_path(file_path):
            errors.append(f"Небезопасный путь к файлу: {file_path}")
    
    return errors

def _is_safe_path(self, path: str) -> bool:
    """Проверить, является ли путь безопасным для использования"""
    try:
        # Преобразовать в абсолютный путь
        abs_path = Path(path).resolve()
        
        # Получить корневой каталог проекта
        project_root = Path.cwd().resolve()
        
        # Проверить, что путь находится внутри корневого каталога
        abs_path.relative_to(project_root)
        return True
    except ValueError:
        # Если путь вне корневого каталога, он небезопасен
        return False
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок в компонентах приложений:

```python
async def execute_operation(self, operation_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Выполнить операцию с надежной обработкой ошибок"""
    try:
        # Проверить ограничения безопасности
        security_check = await self._perform_security_check(operation_name, parameters)
        if not security_check["allowed"]:
            return {
                "success": False,
                "error": f"Операция не прошла проверку безопасности: {security_check['reason']}",
                "security_violation": True
            }
        
        # Проверить ограничения ресурсов
        if self._resource_manager:
            if not await self._resource_manager.check_availability(parameters):
                return {
                    "success": False,
                    "error": "Недостаточно ресурсов для выполнения операции",
                    "resource_limit_exceeded": True
                }
        
        # Выполнить основную логику
        result = await self._execute_extended_logic(operation_name, parameters)
        
        return {"success": True, **result}
    except ValidationError as e:
        return {
            "success": False,
            "error": f"Ошибка валидации: {str(e)}",
            "error_type": "validation"
        }
    except SecurityError as e:
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security",
            "critical": True
        }
    except ResourceLimitExceededError as e:
        return {
            "success": False,
            "error": f"Превышено ограничение ресурсов: {str(e)}",
            "error_type": "resource_limit"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal"
        }

def _check_resource_availability(self, operation_params: Dict[str, Any]) -> bool:
    """Проверить доступность ресурсов для операции"""
    # В реальной реализации здесь будет проверка
    # использования ресурсов против установленных лимитов
    import psutil
    
    # Проверить использование памяти
    memory_usage = psutil.virtual_memory().percent
    max_memory_limit = self.config.get("max_memory_percentage", 85.0)
    if memory_usage > max_memory_limit:
        return False
    
    # Проверить использование CPU
    cpu_usage = psutil.cpu_percent(interval=1)
    max_cpu_limit = self.config.get("max_cpu_percentage", 80.0)
    if cpu_usage > max_cpu_limit:
        return False
    
    return True
```

### 4. Тестирование специфических компонентов

Создавайте тесты для каждого специфического компонента:

```python
# test_specialized_application_components.py
import pytest
from unittest.mock import AsyncMock, Mock
import tempfile
import os

class TestSecurityAnalysisService:
    @pytest.mark.asyncio
    async def test_security_analysis_service_initialization(self):
        """Тест инициализации сервиса анализа безопасности"""
        # Создать сервис
        service = SecurityAnalysisService({
            "enable_vulnerability_database": True,
            "compliance_standards": ["owasp_top_10"]
        })
        
        # Инициализировать сервис
        await service.initialize()
        
        # Проверить, что зависимости были инициализированы
        assert service._vulnerability_database is not None
        assert service._compliance_checker is not None
    
    @pytest.mark.asyncio
    async def test_vulnerability_scan_operation(self):
        """Тест операции сканирования уязвимостей"""
        service = SecurityAnalysisService()
        await service.initialize()
        
        # Создать задачу
        task = SpecializedTask(
            id="test_scan",
            description="Тестовое сканирование",
            domain="security_analysis",
            operation_type="vulnerability_scan",
            parameters={
                "target": "def test(): pass",
                "scan_type": "basic"
            }
        )
        
        # Выполнить операцию
        result = await service.execute_specialized_operation(task)
        
        # Проверить результат
        assert "success" in result
        # В зависимости от реализации, проверить другие поля результата
    
    @pytest.mark.asyncio
    async def test_security_service_with_invalid_params(self):
        """Тест сервиса безопасности с некорректными параметрами"""
        service = SecurityAnalysisService()
        await service.initialize()
        
        # Создать задачу с некорректными параметрами
        task = SpecializedTask(
            id="test_invalid",
            description="Тест с некорректными параметрами",
            domain="security_analysis",
            operation_type="vulnerability_scan",
            parameters={}  # Нет обязательных параметров
        )
        
        # Выполнить операцию - должна вернуть ошибку
        result = await service.execute_specialized_operation(task)
        
        # Проверить, что операция не выполнена из-за некорректных параметров
        assert result["success"] is False
        assert "target" in result["error"]

class TestSecurityOrchestrator:
    @pytest.mark.asyncio
    async def test_security_orchestration_plan_execution(self):
        """Тест выполнения плана оркестрации безопасности"""
        # Создать оркестратор
        orchestrator = SecurityOrchestrator({
            "enable_risk_assessment": False,  # Отключить для теста
            "enable_remediation_planning": False
        })
        await orchestrator.initialize()
        
        # Подготовить план
        plan = [
            {
                "type": "security_scan",
                "id": "test_scan",
                "parameters": {
                    "target": "def vulnerable(): pass",
                    "scan_type": "basic"
                }
            }
        ]
        
        # Выполнить план
        result = await orchestrator.execute_domain_specific_plan(
            domain="security_analysis",
            plan=plan,
            context={"test": "context"}
        )
        
        # Проверить результат
        assert result["success"] is True
        assert "results" in result
        assert len(result["results"]) == 1
    
    @pytest.mark.asyncio
    async def test_plan_security_policy_check(self):
        """Тест проверки политики безопасности плана"""
        orchestrator = SecurityOrchestrator({
            "security_policy": {
                "restricted_step_types": ["system_access", "file_modification"]
            }
        })
        
        # План с разрешенным типом шага
        allowed_plan = [{"type": "security_scan", "parameters": {}}]
        assert orchestrator._check_plan_security_policy(allowed_plan) is True
        
        # План с запрещенным типом шага
        restricted_plan = [{"type": "system_access", "parameters": {}}]
        assert orchestrator._check_plan_security_policy(restricted_plan) is False

class TestAdvancedApplicationFactory:
    def test_service_type_registration(self):
        """Тест регистрации типов сервисов"""
        factory = AdvancedApplicationFactory()
        
        # Проверить, что встроенные типы зарегистрированы
        assert "security_analysis" in factory.get_available_service_types()
        assert "security" in factory.get_available_orchestrator_types()
    
    @pytest.mark.asyncio
    async def test_create_configurable_service(self):
        """Тест создания настраиваемого сервиса"""
        factory = AdvancedApplicationFactory()
        
        # Создать настраиваемый сервис
        service = await factory.create_configurable_service(
            "security_analysis",
            config={"timeout": 600},
            middleware=[lambda params: params],  # Простой middleware
            validators=[lambda params: True]  # Простой валидатор
        )
        
        # Проверить, что сервис создан
        assert service is not None
        assert hasattr(service, 'execute_specialized_operation')
    
    @pytest.mark.asyncio
    async def test_create_configurable_orchestrator(self):
        """Тест создания настраиваемого оркестратора"""
        factory = AdvancedApplicationFactory()
        
        # Создать настраиваемый оркестратор
        orchestrator = await factory.create_configurable_orchestrator(
            "security",
            config={"max_concurrent_tasks": 5},
            security_policy={"audit_logging": True},
            resource_limits={"max_memory_mb": 1024}
        )
        
        # Проверить, что оркестратор создан
        assert orchestrator is not None
        assert hasattr(orchestrator, 'execute_domain_specific_plan')
```

Эти примеры показывают, как адаптировать и расширять слой приложений Composable AI Agent Framework под специфические задачи, обеспечивая модульность, безопасность и надежность системы.

</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.

</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.



<environment_details>
# Visual Studio Code Visible Files
docs/application/custom_development.md

# Visual Studio Code Open Tabs
docs/application/custom_development.md
docs/getting_started.md
docs/index.md

# Current Time
2/6/2026, 1:14:04 PM (Europe/Moscow, UTC+3:00)

# Context Window Usage
624,928 / 1,000K tokens used (62%)

# Current Mode
ACT MODE
</environment_details>
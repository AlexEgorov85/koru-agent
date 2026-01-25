
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from core.session_context.base_session_context import BaseSessionContext
from models.execution import ExecutionResult

class ActionExecutor:
    """Единственная ответственность — выполнение capability."""
    
    def __init__(self, system_context: BaseSystemContext):
        self.system = system_context
        
    async def execute_capability(
        self,
        capability: Capability,
        parameters: dict,
        session_context: BaseSessionContext
    ) -> ExecutionResult:
        """Выполняет capability с заданными параметрами и контекстом."""
        return await self.system.execution_gateway.execute_capability(
            capability_name=capability.name,
            parameters=parameters,
            system_context=self.system,
            session_context=session_context
        )
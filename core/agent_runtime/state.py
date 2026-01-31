# Импортируем AgentState для обеспечения обратной совместимости
from models.agent_state import AgentState, AgentStatus

# Оставляем этот файл для обратной совместимости с предыдущими импортами
# Теперь AgentState определен в models.agent_state
# Этот файл позволяет старым модулям продолжать использовать import из core.agent_runtime.state

"""
Менеджер восстановления паттернов мышления после ошибок.
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime


class PatternRecoveryManager:
    """Менеджер восстановления паттернов мышления после ошибок."""
    
    def __init__(self, checkpoint_manager: Any = None):
        self.checkpoint_manager = checkpoint_manager
        self.recovery_history = []
    
    async def create_pattern_checkpoint(
        self,
        agent: Any,  # AgentRuntime
        pattern_name: str
    ) -> str:
        """Создать чекпоинт состояния паттерна мышления."""
        if self.checkpoint_manager is None:
            # Если нет менеджера чекпоинтов, сохраняем в памяти
            checkpoint = {
                "session_id": getattr(agent.session, 'session_id', 'unknown'),
                "pattern_name": pattern_name,
                "agent_state": agent.state.__dict__ if hasattr(agent.state, '__dict__') else {},
                "step": agent.state.step,
                "timestamp": datetime.utcnow().isoformat()
            }
            checkpoint_id = f"checkpoint_{pattern_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
            self.recovery_history.append((checkpoint_id, checkpoint))
            return checkpoint_id
        else:
            # Используем настоящий менеджер чекпоинтов
            checkpoint = {
                "session_id": getattr(agent.session, 'session_id', 'unknown'),
                "pattern_name": pattern_name,
                "agent_state": agent.state.model_dump() if hasattr(agent.state, 'model_dump') else agent.state.__dict__,
                "step": agent.state.step,
                "timestamp": datetime.utcnow().isoformat()
            }
            return await self.checkpoint_manager.save(checkpoint)
    
    async def restore_pattern_from_checkpoint(
        self,
        agent: Any,  # AgentRuntime
        checkpoint_id: str
    ) -> bool:
        """Восстановить паттерн мышления из чекпоинта."""
        if self.checkpoint_manager is None:
            # Ищем в истории восстановления
            for stored_id, checkpoint in self.recovery_history:
                if stored_id == checkpoint_id:
                    # Восстанавливаем состояние агента
                    if hasattr(agent.state, '__dict__'):
                        agent.state.__dict__.update(checkpoint["agent_state"])
                    else:
                        # Обновляем атрибуты состояния
                        for key, value in checkpoint["agent_state"].items():
                            setattr(agent.state, key, value)
                    
                    return True
            return False
        else:
            # Используем настоящий менеджер чекпоинтов
            checkpoint = await self.checkpoint_manager.load(checkpoint_id)
            if not checkpoint:
                return False
            
            # Восстанавливаем состояние агента
            if hasattr(agent.state, '__dict__'):
                agent.state.__dict__.update(checkpoint.get("agent_state", {}))
            else:
                # Обновляем атрибуты состояния
                for key, value in checkpoint.get("agent_state", {}).items():
                    setattr(agent.state, key, value)
            
            return True
    
    async def fallback_to_safe_pattern(
        self,
        agent: Any,  # AgentRuntime
        error_pattern: str
    ) -> bool:
        """Откат к безопасному паттерну мышления при критической ошибке."""
        # 1. Сохраняем чекпоинт текущего состояния
        await self.create_pattern_checkpoint(agent, error_pattern)
        
        # 2. Переключаемся на паттерн мышления fallback
        # В реальной реализации нужно получить fallback паттерн из реестра
        # и заменить текущий паттерн на него
        
        return True
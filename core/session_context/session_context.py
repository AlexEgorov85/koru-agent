"""
Простой контекст сессии агента.
ОСОБЕННОСТИ:
- Нет лишних зависимостей и сложной логики
- Легко понять и использовать
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.session_context.base_session_context import BaseSessionContext
from core.session_context.data_context import DataContext
from core.session_context.model import (
    ContextItem, ContextItemType, 
    ContextItemMetadata, AgentStep
)
from core.session_context.step_context import StepContext
from core.models.enums.common_enums import ExecutionStatus

class SessionContext(BaseSessionContext):
    """
    Контекст сессии агента.
    
    ПРИНЦИПЫ:
    1. Простота и минимальная зависимость от инфраструктуры
    2. Соответствие контракту SessionContextPort
    3. Легкость создания и использования
    
    СТРУКТУРА:
    - data_context: хранит все сырые данные
    - step_context: хранит шаги агента для LLM
    - goal: цель сессии
    - current_plan_item_id: ID текущего плана в контексте
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Создание контекста сессии.
        
        ПАРАМЕТРЫ:
        - session_id: Уникальный идентификатор сессии (опционально)
        
        ПРИМЕЧАНИЕ:
        Если session_id не указан, генерируется автоматически
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.goal = None
        self.current_plan_item_id: Optional[str] = None # Атрибут для хранения ID текущего плана
        self.current_plan_step_id: Optional[str] = None # Атрибут для хранения ID текущего шага плана
        self.final_answer = None  # Атрибут для хранения финального ответа

        # Контексты
        self.data_context = DataContext()
        self.step_context = StepContext()
    
    def set_goal(self, goal: str) -> None:
        """
        Установка цели сессии.
        
        ПАРАМЕТРЫ:
        - goal: текст цели
        """
        self.goal = goal
        self.last_activity = datetime.now()

    def get_goal(self) -> str:
        """
        Получение цели сессии.
        """
        return self.goal

    def _add_context_item(
        self,
        item_type: ContextItemType,
        content: Any,
        metadata: Optional[ContextItemMetadata] = None
    ) -> str:
        """
        Добавление элемента в контекст.
        
        ПАРАМЕТРЫ:
        - item_type: тип элемента
        - content: содержимое
        - meta метаданные (опционально)
        
        ВОЗВРАЩАЕТ:
        - item_id: уникальный идентификатор элемента
        """
        item_id = str(uuid.uuid4())
        item = ContextItem(
            item_id=item_id,
            session_id=self.session_id,
            item_type=item_type,
            content=content,
            metadata=metadata or ContextItemMetadata(),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        return self.data_context.add_item(item)
    
    def get_context_item(self, item_id: str) -> Optional[ContextItem]:
        """
        Получение элемента контекста по ID.

        ПАРАМЕТРЫ:
        - item_id: Уникальный идентификатор элемента

        ВОЗВРАЩАЕТ:
        - ContextItem если элемент найден
        - None если элемент не найден
        """
        return self.data_context.get_item(item_id, raise_on_missing=False)
    
    def register_step(
        self,
        step_number: int,
        capability_name: str,
        skill_name: str,
        action_item_id: str,
        observation_item_ids: List[str],
        summary: Optional[str] = None,
        status: Optional[ExecutionStatus] = None
    ) -> None:
        """
        Регистрация шага агента.
        
        ПАРАМЕТРЫ:
        - step_number: номер шага
        - capability_name: название capability
        - skill_name: название навыка
        - action_item_id: ID элемента действия
        - observation_item_ids: ID результатов
        - summary: краткое описание шага
        - status: .....
        - execution_time: .........
        """
        step = AgentStep(
            step_number=step_number,
            capability_name=capability_name,
            skill_name=skill_name,
            action_item_id=action_item_id,
            observation_item_ids=observation_item_ids,
            summary=summary,
            status=status
        )
        self.step_context.add_step(step)
        self.last_activity = datetime.now()
    
    def set_current_plan(self, plan_item_id: str) -> None:
        """
        Установка текущего плана.
        
        ПАРАМЕТРЫ:
        - plan_item_id: ID элемента с планом
        """
        self.current_plan_item_id = plan_item_id
    
    def get_current_plan(self) -> Optional[ContextItem]:
        """
        Получение текущего плана.

        ВОЗВРАЩАЕТ:
        - ContextItem с планом или None если план не установлен
        """
        if not self.current_plan_item_id:
            return None
        return self.data_context.get_item(self.current_plan_item_id, raise_on_missing=False)
    
    def is_expired(self, ttl_minutes: int = 60) -> bool:
        """
        Проверка истечения срока жизни сессии.
        
        ПАРАМЕТРЫ:
        - ttl_minutes: время жизни в минутах
        
        ВОЗВРАЩАЕТ:
        - True если сессия истекла
        - False если сессия еще активна
        """
        from datetime import timedelta
        elapsed = datetime.now() - self.last_activity
        return elapsed > timedelta(minutes=ttl_minutes)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Получение сводной информации о сессии.
        
        ВОЗВРАЩАЕТ:
        - Словарь с информацией о сессии
        """
        summary_dict = {
            "session_id": self.session_id,
            "goal": self.goal or "",
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "step_count": self.step_context.count(),
            "item_count": self.data_context.count(),
            "has_plan": self.current_plan_item_id is not None
        }
        
        # Добавляем информацию о последних шагах
        if self.step_context.steps:
            summary_dict["last_steps"] = []
            for step in self.step_context.steps[-3:]:  # Последние 3 шага
                step_data = {
                    "step_number": step.step_number,
                    "capability": step.capability_name,
                    "skill": step.skill_name,
                    "parameters": self.get_context_item(step.action_item_id).content.get("parameters") if self.get_context_item(step.action_item_id) else {},
                    "summary": step.summary
                }
                
                # Добавляем observation если есть
                if step.observation_item_ids:
                    observations = []
                    for obs_id in step.observation_item_ids:
                        obs_item = self.get_context_item(obs_id)
                        if obs_item:
                            obs_content = obs_item.content
                            # Извлекаем полезную информацию из observation
                            if isinstance(obs_content, dict):
                                # Пробуем разные ключи для извлечения данных
                                obs_data = (
                                    obs_content.get('result') or  # ExecutionResult.data
                                    obs_content.get('data') or
                                    obs_content.get('rows') or
                                    obs_content
                                )
                                # Сериализуем Pydantic модель если нужно
                                if hasattr(obs_data, 'model_dump'):
                                    obs_data = obs_data.model_dump()
                                elif hasattr(obs_data, 'dict'):
                                    obs_data = obs_data.dict()
                                observations.append(str(obs_data)[:300])  # Ограничиваем длину
                            else:
                                observations.append(str(obs_content)[:300])
                    if observations:
                        step_data["observation"] = "\n".join(observations)
                
                summary_dict["last_steps"].append(step_data)
        
        return summary_dict

    def record_action(self, action_data, step_number=None, metadata=None):
        """Запись действия агента в контекст"""
        meta = metadata or ContextItemMetadata(
            source="agent_runtime",
            step_number=step_number,
            confidence=0.9
        )
        return self._add_context_item(
            item_type=ContextItemType.ACTION,
            content=action_data,
            metadata=meta
        )
    
    def record_observation(self, observation_data, source=None, step_number=None, metadata=None):
        """Запись результата выполнения в контекст"""
        meta = metadata or ContextItemMetadata(
            source=source or "skill",
            step_number=step_number,
            confidence=0.8
        )
        return self._add_context_item(
            item_type=ContextItemType.OBSERVATION,
            content=observation_data,
            metadata=meta
        )
    
    def record_plan(self, plan_data, plan_type="initial", metadata=None):
        """Запись плана и его обновлений в контекст"""
        meta = metadata or ContextItemMetadata(
            source="planning_skill",
            confidence=0.95
        )
        plan_type_map = {
            "initial": ContextItemType.EXECUTION_PLAN,
            "update": ContextItemType.PLAN_UPDATE
        }
        item_type = plan_type_map.get(plan_type, ContextItemType.EXECUTION_PLAN)

        self.current_plan_item_id = self._add_context_item(
            item_type=item_type,
            content=plan_data,
            metadata=meta
        )
        return self.current_plan_item_id
    
    def record_decision(self, decision_data, reasoning=None, metadata=None):
        """Запись решения стратегии в контекст"""
        meta = metadata or ContextItemMetadata(
            source="behavior",
            confidence=0.85
        )
        content = {
            "decision": decision_data,
            "reasoning": reasoning
        }
        return self._add_context_item(
            item_type=ContextItemType.THOUGHT,
            content=content,
            metadata=meta
        )
    
    def record_error(self, error_data, error_type=None, step_number=None, metadata=None):
        """Запись ошибки выполнения в контекст"""
        meta = metadata or ContextItemMetadata(
            source=error_data.get("source", "unknown"),
            step_number=step_number,
            confidence=0.1
        )
        content = {
            "error": error_data,
            "error_type": error_type
        }
        return self._add_context_item(
            item_type=ContextItemType.ERROR_LOG,
            content=content,
            metadata=meta
        )
    
    def record_metric(self, name, value, unit=None, metadata=None):
        """Запись метрики выполнения в контекст"""
        meta = metadata or ContextItemMetadata(
            source="system_metric",
            confidence=1.0
        )
        content = {
            "name": name,
            "value": value,
            "unit": unit
        }
        return self._add_context_item(
            item_type=ContextItemType.TOOL_RESULT,
            content=content,
            metadata=meta
        )
    
    def record_system_event(self, event_type, description=None, metadata=None):
        """Запись системного события в контекст"""
        meta = metadata or ContextItemMetadata(
            source="agent_runtime",
            confidence=0.9
        )
        content = {
            "event_type": event_type,
            "description": description
        }
        return self._add_context_item(
            item_type=ContextItemType.THOUGHT,
            content=content,
            metadata=meta
        )
    
    def get_current_plan_step(self):
        """Получение текущего шага плана."""
        if not hasattr(self, 'current_plan_step_id') or not self.current_plan_step_id:
            return None
        
        # Получаем текущий план
        current_plan_item = self.get_current_plan()
        if not current_plan_item:
            return None
        
        plan_data = current_plan_item.content
        steps = plan_data.get("steps", [])
        
        # Находим текущий шаг по ID
        for step in steps:
            if step.get("step_id") == self.current_plan_step_id:
                return step
        
        return None
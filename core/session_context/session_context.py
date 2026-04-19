"""
Простой контекст сессии агента.
ОСОБЕННОСТИ:
- Нет лишних зависимостей и сложной логики
- Легко понять и использовать
"""
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.session_context.base_session_context import BaseSessionContext
from core.session_context.data_context import DataContext
from core.session_context.dialogue_context import DialogueHistory
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
    
    def __init__(self, session_id: Optional[str] = None, agent_id: Optional[str] = None):
        """
        Создание контекста сессии.
        
        ПАРАМЕТРЫ:
        - session_id: Уникальный идентификатор сессии (опционально)
        - agent_id: Идентификатор агента (опционально)
        
        ПРИМЕЧАНИЕ:
        Если session_id не указан, генерируется автоматически
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.agent_id = agent_id or "agent_001"
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.goal = None
        self.current_plan_item_id: Optional[str] = None
        self.current_plan_step_id: Optional[str] = None
        self.final_answer = None

        self.data_context = DataContext()
        self.step_context = StepContext()
        
        # История диалога для сохранения контекста между запросами
        self.dialogue_history = DialogueHistory(max_rounds=10)

        # Универсальный лог пустых результатов запросов
        self.empty_query_log: List[Dict[str, Any]] = []
    
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
        status: Optional[ExecutionStatus] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Регистрация шага агента.

        АРХИТЕКТУРНОЕ ПРАВИЛО:
        ⚠️ Данные хранятся ТОЛЬКО в data_context!
        ⚠️ observation_item_ids содержит ссылки на ContextItem с данными

        ПАРАМЕТРЫ:
        - step_number: номер шага
        - capability_name: название capability
        - skill_name: название навыка
        - action_item_id: ID элемента действия в data_context
        - observation_item_ids: ID результатов в data_context
        - summary: краткое описание шага
        - status: статус выполнения
        - parameters: параметры запуска действия/инструмента
        """
        step = AgentStep(
            step_number=step_number,
            capability_name=capability_name,
            skill_name=skill_name,
            action_item_id=action_item_id,
            observation_item_ids=observation_item_ids,
            summary=summary,
            status=status,
            parameters=parameters
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
                                observations.append(str(obs_data))
                            else:
                                observations.append(str(obs_content))
                    if observations:
                        step_data["observation"] = "\n".join(observations)

                summary_dict["last_steps"].append(step_data)

        return summary_dict

    # ========================================================================
    # QUERY HELPERS для Pattern (Этап 6)
    # ========================================================================

    def get_last_steps(self, n: int = 5) -> List[AgentStep]:
        """
        Получить последние n шагов.

        ПАРАМЕТРЫ:
        - n: количество шагов

        ВОЗВРАЩАЕТ:
        - List[AgentStep]: последние шаги

        ⚠️ ТОЛЬКО ЧТЕНИЕ: не принимает решений!
        Pattern сам анализирует шаги.
        """
        return list(self.step_context.steps[-n:])

    def get_consecutive_failures(self) -> int:
        """
        Получить счётчик последовательных ошибок.

        ВОЗВРАЩАЕТ:
        - int: количество последовательных failed шагов

        ⚠️ ТОЛЬКО ЧТЕНИЕ: не принимает решений!
        Pattern сам решает что делать с ошибками.
        """
        count = 0
        for step in reversed(self.step_context.steps):
            if step.status == ExecutionStatus.FAILED:
                count += 1
            else:
                break
        return count

    def has_no_progress(self, n_steps: int = 3) -> bool:
        """
        Проверка: были ли изменения за последние n шагов.

        ПАРАМЕТРЫ:
        - n_steps: количество шагов для проверки

        ВОЗВРАЩАЕТ:
        - bool: True если не было прогресса

        ⚠️ ТОЛЬКО ЧТЕНИЕ: не принимает решений!
        Pattern сам решает что делать при отсутствии прогресса.
        """
        if len(self.step_context.steps) < n_steps:
            return False
        
        recent_steps = list(self.step_context.steps[-n_steps:])
        # Проверяем были ли успешные действия
        return all(step.status == ExecutionStatus.FAILED for step in recent_steps)

    def get_errors_count(self) -> int:
        """
        Получить общее количество ошибок.

        ВОЗВРАЩАЕТ:
        - int: количество failed шагов

        ⚠️ ТОЛЬКО ЧТЕНИЕ: не принимает решений!
        """
        return sum(1 for step in self.step_context.steps if step.status == ExecutionStatus.FAILED)

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

    def commit_turn(self, user_query: str, assistant_response: str, tools_used: Optional[List[str]] = None) -> None:
        """
        Сохранение обмена репликами в историю диалога.

        Вызывается в конце успешного цикла (run) для сохранения
        вопроса пользователя и ответа агента.

        ПАРАМЕТРЫ:
        - user_query: текст запроса пользователя
        - assistant_response: текст ответа агента
        - tools_used: список инструментов, использованных при формировании ответа
        """
        self.dialogue_history.add_user_message(user_query)
        self.dialogue_history.add_assistant_message(assistant_response, tools_used)

    def copy_dialogue_from(self, other_dialogue_history: 'DialogueHistory') -> None:
        """
        Копирование истории диалога из другого источника.

        Используется при создании нового SessionContext для переноса
        истории предыдущих диалогов.

        ПАРАМЕТРЫ:
        - other_dialogue_history: источник истории для копирования
        """
        if other_dialogue_history is None:
            return
        
        # Копируем все сообщения
        for msg in other_dialogue_history.messages:
            self.dialogue_history.messages.append(
                type(msg)(role=msg.role, content=msg.content, tools_used=list(msg.tools_used))
            )

    # ========================================================================
    # EMPTY QUERY LOG - универсальный трекер пустых результатов
    # ========================================================================

    def record_empty_result(
        self,
        tool: str,
        tables: List[str],
        filters: Dict[str, Any],
        columns_used: Optional[List[str]] = None
    ) -> None:
        """
        Запись пустого результата запроса без привязки к конкретным скриптам.

        ПАРАМЕТРЫ:
        - tool: название инструмента/скилла
        - tables: список таблиц в запросе
        - filters: словарь использованных фильтров
        - columns_used: использованные колонки (опционально)
        """
        self.empty_query_log.append({
            "tool": tool,
            "tables": tables,
            "filters": filters,
            "columns": columns_used or [],
            "timestamp": time.time()
        })

    def needs_exploration(self, threshold: int = 2) -> bool:
        """
        Вернёт True, если запрос вернул пусто >= threshold раз подряд.

        ПАРАМЕТРЫ:
        - threshold: количество пустых результатов для активации режима исследования

        ВОЗВРАЩАЕТ:
        - bool: True если нужно исследовать данные
        """
        if not self.empty_query_log:
            return False
        return len(self.empty_query_log) >= threshold

    def get_exploration_context(self) -> str:
        """
        Генер��ция контекста для LLM на основе последних пустых запросов.

        ВОЗВРАЩАЕТ:
        - str: текстовый контекст для исследования данных
        """
        if not self.empty_query_log:
            return ""
        
        last = self.empty_query_log[-1]
        tables_str = ", ".join(last["tables"])
        filters_str = str(last["filters"])
        
        context = [
            "🔍 **ИСТОРИЯ ПУСТЫХ ЗАПРОСОВ:**",
            f"- Таблицы: `{tables_str}`",
            f"- Использованные фильтры: `{filters_str}`",
            "- Результат: 0 строк"
        ]
        
        if len(self.empty_query_log) > 1:
            context.append(f"- Всего пустых попыток: {len(self.empty_query_log)}")
        
        return "\n".join(context)

    def get_last_empty_query(self) -> Optional[Dict[str, Any]]:
        """
        Получение последнего пустого запроса.

        ВОЗВРАЩАЕТ:
        - Dict или None если лог пуст
        """
        if not self.empty_query_log:
            return None
        return self.empty_query_log[-1]

    def clear_empty_query_log(self) -> None:
        """Очистка лога пустых запросов (после успешного запроса)."""
        self.empty_query_log.clear()
"""
Простой контекст сессии агента.
ОСОБЕННОСТИ:
- Нет лишних зависимостей и сложной логики
- Легко понять и использовать
"""
import logging
import uuid
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict, deque
import heapq

from core.session_context.base_session_context import BaseSessionContext
from core.session_context.data_context import DataContext
from core.session_context.model import (
    ContextItem, ContextItemType, 
    ContextItemMetadata, AgentStep
)
from core.session_context.step_context import StepContext
from models.execution import ExecutionStatus
from core.domain_management.domain_manager import DomainManager
from core.composable_patterns.patterns import ReActPattern, PlanAndExecutePattern, ToolUsePattern, ReflectionPattern
from core.atomic_actions.actions import THINK, ACT, OBSERVE, PLAN, REFLECT, EVALUATE, VERIFY, ADAPT

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """
    Класс для отслеживания метрик производительности различных паттернов и доменов.
    """
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'success_count': 0,
            'failure_count': 0,
            'avg_execution_time': 0,
            'avg_steps_count': 0,
            'total_calls': 0
        })
    
    def record_execution(self, pattern_name: str, domain: str, success: bool, execution_time: float, steps_count: int):
        """Записывает результат выполнения паттерна в домене."""
        key = f"{pattern_name}:{domain}"
        metric = self.metrics[key]
        
        metric['total_calls'] += 1
        if success:
            metric['success_count'] += 1
        else:
            metric['failure_count'] += 1
            
        # Обновляем среднее время выполнения
        old_avg = metric['avg_execution_time']
        metric['avg_execution_time'] = ((old_avg * (metric['total_calls'] - 1) + execution_time) / 
                                       metric['total_calls'])
        
        # Обновляем среднее количество шагов
        old_avg_steps = metric['avg_steps_count']
        metric['avg_steps_count'] = ((old_avg_steps * (metric['total_calls'] - 1) + steps_count) / 
                                    metric['total_calls'])
    
    def get_performance_score(self, pattern_name: str, domain: str) -> float:
        """Возвращает оценку производительности паттерна в домене (0-1)."""
        key = f"{pattern_name}:{domain}"
        metric = self.metrics[key]
        
        if metric['total_calls'] == 0:
            return 0.5  # По умолчанию средняя производительность
        
        success_rate = metric['success_count'] / metric['total_calls']
        # Меньшее время выполнения и меньшее количество шагов лучше
        efficiency_factor = min(1.0, 10.0 / (1.0 + metric['avg_steps_count']))
        
        return (success_rate + efficiency_factor) / 2

class AdaptiveMemoryManager:
    """
    Класс для управления адаптивной памятью и сжатия контекста.
    """
    def __init__(self, max_context_size: int = 1000, compression_threshold: int = 500):
        self.max_context_size = max_context_size
        self.compression_threshold = compression_threshold
        self.context_summaries = {}
        self.relevance_scores = {}
        
    def compress_context(self, context_items: List[ContextItem], goal: str) -> List[ContextItem]:
        """
        Сжимает контекст, сохраняя наиболее релевантные элементы.
        """
        if len(context_items) <= self.compression_threshold:
            return context_items
        
        # Вычисляем релевантность каждого элемента к цели
        scored_items = []
        for item in context_items:
            relevance = self._calculate_relevance(item, goal)
            scored_items.append((relevance, item))
        
        # Сортируем по релевантности и оставляем только самые важные
        scored_items.sort(key=lambda x: x[0], reverse=True)
        compressed_items = [item for _, item in scored_items[:self.compression_threshold]]
        
        # Если у нас все равно слишком много элементов, применяем дополнительные методы сжатия
        if len(compressed_items) > self.max_context_size:
            compressed_items = compressed_items[-self.max_context_size:]  # Сохраняем последние элементы
        
        return compressed_items
    
    def _calculate_relevance(self, item: ContextItem, goal: str) -> float:
        """
        Вычисляет релевантность элемента контекста к цели.
        """
        # Используем простой алгоритм оценки релевантности на основе совпадения ключевых слов
        goal_lower = goal.lower()
        content_str = str(item.content).lower()
        
        # Повышаем релевантность для определенных типов элементов
        base_relevance = 0.1
        if item.item_type in [ContextItemType.EXECUTION_PLAN, ContextItemType.TASK, ContextItemType.USER_QUERY]:
            base_relevance += 0.3
        elif item.item_type in [ContextItemType.THUGHT, ContextItemType.ACTION]:
            base_relevance += 0.2
        elif item.item_type == ContextItemType.ERROR_LOG:
            base_relevance += 0.15  # Ошибки могут быть важны для обучения
        
        # Оцениваем совпадение по содержимому
        if goal and content_str:
            keywords = goal_lower.split()
            matches = sum(1 for keyword in keywords if keyword in content_str)
            content_relevance = min(matches / len(keywords) if keywords else 0, 0.5)
        else:
            content_relevance = 0
        
        # Учитываем доверие к источнику
        confidence_relevance = item.metadata.confidence * 0.3 if item.metadata else 0
        
        # Учитываем временную близость (последние элементы более релевантны)
        age_factor = 0.2 if item.created_at and (datetime.now() - item.created_at).seconds < 300 else 0.05
        
        total_relevance = base_relevance + content_relevance + confidence_relevance + age_factor
        return min(total_relevance, 1.0)
    
    def summarize_context(self, context_items: List[ContextItem], goal: str) -> str:
        """
        Создает краткое резюме контекста.
        """
        relevant_items = []
        for item in context_items:
            relevance = self._calculate_relevance(item, goal)
            if relevance > 0.2:  # Порог для включения в резюме
                relevant_items.append((relevance, item))
        
        # Сортируем по релевантности и берем топ 10 элементов
        relevant_items.sort(key=lambda x: x[0], reverse=True)
        top_items = [item for _, item in relevant_items[:10]]
        
        summary_parts = []
        for item in top_items:
            item_summary = f"Тип: {item.item_type}, Содержание: {str(item.content)[:100]}..."
            summary_parts.append(item_summary)
        
        return "\n".join(summary_parts)

class SessionContext(BaseSessionContext):
    """
    Контекст сессии агента с улучшенной адаптивностью и управлением памятью.
    
    ПРИНЦИПЫ:
    1. Простота и минимальная зависимость от инфраструктуры
    2. Соответствие контракту SessionContextPort
    3. Легкость создания и использования
    4. Автоматическая адаптация под домены и паттерны
    5. Эффективное управление памятью и сжатие контекста
    6. Поддержка интеграции с субагентами (новыми экземплярами агента) через регистрацию информации
    
    СТРУКТУРА:
    - data_context: хранит все сырые данные
    - step_context: хранит шаги агента для LLM
    - goal: цель сессии
    - current_plan_item_id: ID текущего плана в контексте
    - domain_manager: менеджер доменов для адаптации
    - memory_manager: менеджер памяти для сжатия и оптимизации
    - metrics: метрики производительности
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
        self.project_map = None
        self.current_plan_item_id: Optional[str] = None # Атрибут для хранения ID текущего плана
        self.current_plan_step_id: Optional[str] = None # Атрибут для хранения ID текущего шага плана
        
        # Контексты
        self.data_context = DataContext()
        self.step_context = StepContext()
        
        # Компоненты для адаптации
        self.domain_manager = DomainManager()
        self.memory_manager = AdaptiveMemoryManager()
        self.metrics = PerformanceMetrics()
        
        # Хранение текущего паттерна и домена
        self.current_pattern = None
        self.current_domain = None
        self.pattern_history = deque(maxlen=10)  # Хранит историю последних 10 паттернов
        
        # Хранение инсайтов по доменам
        self.domain_insights = defaultdict(list)
        
        # Управление субагентами (только для регистрации информации о них)
        # Полное управление субагентами осуществляется на уровне агента
        self.running_subagents = {}  # Словарь для отслеживания запущенных субагентов
    
    def set_goal(self, goal: str) -> None:
        """
        Установка цели сессии.
        
        ПАРАМЕТРЫ:
        - goal: текст цели
        """
        self.goal = goal
        self.last_activity = datetime.now()
        
        # Автоматически адаптируемся к домену на основе цели
        self.adapt_to_domain(goal)
    
    def get_goal(self) -> str:
        """
        Получение цели сессии.
        """
        return self.goal

    def add_context_item(
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
        - metadata: метаданные (опционально)
        
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
        return self.data_context.get_item(item_id)
    
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
        - status: статус выполнения
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
        return self.data_context.get_item(self.current_plan_item_id)
    
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
            "has_plan": self.current_plan_item_id is not None,
            "current_domain": self.current_domain,
            "current_pattern": self.current_pattern,
            "pattern_history": list(self.pattern_history)
        }
        
        # Добавляем информацию о последних шагах
        if self.step_context.steps:
            summary_dict["last_steps"] = []
            for step in self.step_context.steps[-3:]:  # Последние 3 шага
                summary_dict["last_steps"].append({
                    "step_number": step.step_number,
                    "capability": step.capability_name,
                    "skill": step.skill_name,
                    "parameters": getattr(self.get_context_item(step.action_item_id), 'content', {}).get("parameters"),
                    "summary": step.summary
                })
        
        return summary_dict

    def record_action(self, action_data, step_number=None, metadata=None):
        """Запись действия агента в контекст"""
        meta = metadata or ContextItemMetadata(
            source="agent_runtime",
            step_number=step_number,
            confidence=0.9
        )
        return self.add_context_item(
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
        return self.add_context_item(
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

        self.current_plan_item_id = self.add_context_item(
            item_type=item_type,
            content=plan_data,
            metadata=meta
        )
        return self.current_plan_item_id
    
    def record_decision(self, decision_data, reasoning=None, metadata=None):
        """Запись решения стратегии в контекст"""
        meta = metadata or ContextItemMetadata(
            source="strategy",
            confidence=0.85
        )
        content = {
            "decision": decision_data,
            "reasoning": reasoning
        }
        return self.add_context_item(
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
        return self.add_context_item(
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
        return self.add_context_item(
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
        return self.add_context_item(
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

    def adapt_to_domain(self, task_description: str):
        """
        Автоматическая адаптация к домену на основе описания задачи.
        
        ПАРАМЕТРЫ:
        - task_description: Описание задачи для классификации домена
        """
        domain = self.domain_manager.adapt_to_task(task_description)
        self.current_domain = domain
        
        # Устанавливаем соответствующий паттерн для домена
        pattern_name = self.domain_manager.get_domain_pattern(domain)
        self.adapt_to_pattern(pattern_name)
        
        logger.info(f"Session adapted to domain: {domain}, pattern: {pattern_name}")
        
        # Записываем инсайт о домене
        self.record_domain_insight({
            "task_description": task_description,
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "pattern_used": pattern_name
        })

    def adapt_to_pattern(self, pattern_name: str):
        """
        Адаптация к определенному паттерну мышления.
        
        ПАРАМЕТРЫ:
        - pattern_name: Название паттерна для адаптации
        """
        self.current_pattern = pattern_name
        self.pattern_history.append(pattern_name)
        
        logger.info(f"Session adapted to pattern: {pattern_name}")

    def get_relevant_context(self, limit: int = 20, relevance_threshold: float = 0.3) -> List[ContextItem]:
        """
        Получение наиболее релевантного контекста для текущей задачи.
        
        ПАРАМЕТРЫ:
        - limit: Максимальное количество элементов для возврата
        - relevance_threshold: Порог релевантности для фильтрации
        
        ВОЗВРАЩАЕТ:
        - Список наиболее релевантных элементов контекста
        """
        if not self.goal:
            # Если нет цели, возвращаем последние элементы
            return self.data_context.get_last_items(limit)
        
        # Получаем все элементы контекста
        all_items = self.data_context.get_all_items()
        
        # Вычисляем релевантность для каждого элемента
        relevant_items = []
        for item in all_items:
            relevance = self.memory_manager._calculate_relevance(item, self.goal)
            if relevance >= relevance_threshold:
                relevant_items.append((relevance, item))
        
        # Сортируем по релевантности и возвращаем топ элементов
        relevant_items.sort(key=lambda x: x[0], reverse=True)
        result = [item for _, item in relevant_items[:limit]]
        
        return result

    def optimize_memory(self):
        """
        Оптимизация памяти путем сжатия и удаления нерелевантного контекста.
        """
        all_items = self.data_context.get_all_items()
        optimized_items = self.memory_manager.compress_context(all_items, self.goal or "")
        
        # Пересоздаем data_context с оптимизированными элементами
        old_data_context = self.data_context
        self.data_context = DataContext()
        
        # Добавляем оптимизированные элементы обратно
        for item in optimized_items:
            self.data_context.add_item(item)
        
        logger.info(f"Memory optimized: reduced from {len(old_data_context.get_all_items())} to {len(optimized_items)} items")

    def record_performance_metrics(self, pattern_name: str, success: bool, execution_time: float, steps_count: int):
        """
        Запись метрик производительности для паттерна.
        
        ПАРАМЕТРЫ:
        - pattern_name: Название паттерна
        - success: Успешно ли выполнено
        - execution_time: Время выполнения
        - steps_count: Количество шагов
        """
        domain = self.current_domain or "general"
        self.metrics.record_execution(pattern_name, domain, success, execution_time, steps_count)

    def get_best_pattern_for_domain(self, domain: str) -> str:
        """
        Получение лучшего паттерна для указанного домена на основе метрик.
        
        ПАРАМЕТРЫ:
        - domain: Название домена
        
        ВОЗВРАЩАЕТ:
        - Название лучшего паттерна для домена
        """
        patterns = ["react", "plan_and_execute", "tool_use", "reflection", "code_analysis", "database_query", "research"]
        best_pattern = "react"  # По умолчанию
        best_score = 0.0
        
        for pattern in patterns:
            score = self.metrics.get_performance_score(pattern, domain)
            if score > best_score:
                best_score = score
                best_pattern = pattern
        
        return best_pattern

    def record_domain_insight(self, insight_data: Dict[str, Any]):
        """
        Запись инсайта о домене.
        
        ПАРАМЕТРЫ:
        - insight_data: Данные инсайта
        """
        domain = insight_data.get("domain", "general")
        self.domain_insights[domain].append(insight_data)
        
        # Сохраняем только последние 50 инсайтов для каждого домена
        if len(self.domain_insights[domain]) > 50:
            self.domain_insights[domain] = self.domain_insights[domain][-50:]

    def get_domain_insights(self, domain: str) -> List[Dict[str, Any]]:
        """
        Получение инсайтов для указанного домена.
        
        ПАРАМЕТРЫ:
        - domain: Название домена
        
        ВОЗВРАЩАЕТ:
        - Список инсайтов для домена
        """
        return self.domain_insights.get(domain, [])

    def get_context_summary(self) -> str:
        """
        Получение краткого резюме текущего контекста.
        
        ВОЗВРАЩАЕТ:
        - Строковое резюме контекста
        """
        all_items = self.data_context.get_all_items()
        return self.memory_manager.summarize_context(all_items, self.goal or "")

    def integrate_with_composable_pattern(self, pattern_name: str):
        """
        Интеграция с композиционным паттерном.
        
        ПАРАМЕТРЫ:
        - pattern_name: Название паттерна для интеграции
        """
        # Устанавливаем текущий паттерн
        self.adapt_to_pattern(pattern_name)
        
        # Записываем событие интеграции
        self.record_system_event(
            event_type="pattern_integration",
            description=f"Integrated with composable pattern: {pattern_name}",
            metadata=ContextItemMetadata(source="session_context", confidence=1.0)
        )

    def integrate_with_domain_manager(self, domain: str):
        """
        Интеграция с DomainManager.
        
        ПАРАМЕТРЫ:
        - domain: Название домена для интеграции
        """
        # Устанавливаем домен через DomainManager
        self.domain_manager.set_current_domain(domain)
        self.current_domain = domain
        
        # Устанавливаем соответствующий паттерн
        pattern_name = self.domain_manager.get_domain_pattern(domain)
        self.adapt_to_pattern(pattern_name)
        
        logger.info(f"Integrated with DomainManager: {domain}, pattern: {pattern_name}")

    def get_optimized_context_for_llm(self, max_items: int = 30) -> List[Dict[str, Any]]:
        """
        Получение оптимизированного контекста для передачи в LLM.
        
        ПАРАМЕТРЫ:
        - max_items: Максимальное количество элементов для возврата
        
        ВОЗВРАЩАЕТ:
        - Список элементов контекста в формате, подходящем для LLM
        """
        relevant_items = self.get_relevant_context(limit=max_items)
        
        # Преобразуем элементы в формат, подходящий для LLM
        llm_context = []
        for item in relevant_items:
            item_dict = {
                "id": item.item_id,
                "type": item.item_type.value,
                "content": item.content,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "confidence": item.metadata.confidence if item.metadata else 0.0,
                "source": item.metadata.source if item.metadata else "unknown"
            }
            llm_context.append(item_dict)
        
        return llm_context

    def record_subagent_start(self, agent_id: str, agent_name: str, task_description: str) -> str:
        """
        Записывает информацию о начале работы субагента в контекст.
        
        ПАРАМЕТРЫ:
        - agent_id: Уникальный идентификатор субагента
        - agent_name: Название субагента
        - task_description: Описание задачи, которую выполняет субагент
        
        ВОЗВРАЩАЕТ:
        - ID созданного элемента контекста
        """
        metadata = ContextItemMetadata(
            source=f"subagent.{agent_name}",
            confidence=0.9,
            additional_data={
                "agent_id": agent_id,
                "task_description": task_description,
                "start_time": datetime.now().isoformat()
            }
        )
        
        content = {
            "event": "subagent_started",
            "agent_name": agent_name,
            "agent_id": agent_id,
            "task": task_description,
            "timestamp": datetime.now().isoformat()
        }
        
        return self.add_context_item(
            item_type=ContextItemType.THOUGHT,
            content=content,
            metadata=metadata
        )

    def record_subagent_result(self, agent_id: str, agent_name: str, result: Any) -> str:
        """
        Записывает результат работы субагента в контекст.
        
        ПАРАМЕТРЫ:
        - agent_id: Уникальный идентификатор субагента
        - agent_name: Название субагента
        - result: Результат выполнения задачи субагентом
        
        ВОЗВРАЩАЕТ:
        - ID созданного элемента контекста
        """
        metadata = ContextItemMetadata(
            source=f"subagent.{agent_name}",
            confidence=0.85,
            additional_data={
                "agent_id": agent_id,
                "result_type": type(result).__name__,
                "completion_time": datetime.now().isoformat()
            }
        )
        
        content = {
            "event": "subagent_completed",
            "agent_name": agent_name,
            "agent_id": agent_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        return self.add_context_item(
            item_type=ContextItemType.SKILL_RESULT,
            content=content,
            metadata=metadata
        )

    def record_subagent_error(self, agent_id: str, agent_name: str, error_info: Dict[str, Any]) -> str:
        """
        Записывает информацию об ошибке субагента в контекст.
        
        ПАРАМЕТРЫ:
        - agent_id: Уникальный идентификатор субагента
        - agent_name: Название субагента
        - error_info: Информация об ошибке
        
        ВОЗВРАЩАЕТ:
        - ID созданного элемента контекста
        """
        metadata = ContextItemMetadata(
            source=f"subagent.{agent_name}",
            confidence=0.1,
            additional_data={
                "agent_id": agent_id,
                "error_phase": error_info.get("phase", "unknown")
            }
        )
        
        content = {
            "event": "subagent_error",
            "agent_name": agent_name,
            "agent_id": agent_id,
            "error": error_info["error"],
            "timestamp": error_info["timestamp"],
            "phase": error_info["phase"]
        }
        
        return self.add_context_item(
            item_type=ContextItemType.ERROR_LOG,
            content=content,
            metadata=metadata
        )

    def track_subagent(self, agent_id: str, agent_instance: Any, task_description: str):
        """
        Отслеживание субагента в рамках сессии.
        
        ПАРАМЕТРЫ:
        - agent_id: Уникальный идентификатор субагента
        - agent_instance: Экземпляр субагента
        - task_description: Описание задачи, которую выполняет субагент
        """
        self.running_subagents[agent_id] = {
            'instance': agent_instance,
            'task': task_description,
            'start_time': datetime.now(),
            'status': 'running'
        }

    def get_subagent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение статуса субагента.
        
        ПАРАМЕТРЫ:
        - agent_id: Уникальный идентификатор субагента
        
        ВОЗВРАЩАЕТ:
        - Словарь со статусом субагента или None если субагент не найден
        """
        return self.running_subagents.get(agent_id)

    def update_subagent_status(self, agent_id: str, status: str):
        """
        Обновление статуса субагента.
        
        ПАРАМЕТРЫ:
        - agent_id: Уникальный идентификатор субагента
        - status: Новый статус ('running', 'completed', 'failed', 'cancelled')
        """
        if agent_id in self.running_subagents:
            self.running_subagents[agent_id]['status'] = status
            self.running_subagents[agent_id]['updated_at'] = datetime.now()

    def remove_subagent(self, agent_id: str):
        """
        Удаление субагента из списка отслеживаемых.
        
        ПАРАМЕТРЫ:
        - agent_id: Уникальный идентификатор субагента
        """
        if agent_id in self.running_subagents:
            del self.running_subagents[agent_id]

    def get_running_subagents(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение всех запущенных субагентов.
        
        ВОЗВРАЩАЕТ:
        - Словарь с информацией обо всех запущенных субагентах
        """
        return self.running_subagents.copy()

    def should_spawn_subagents(self, task_breakdown: List[Dict[str, Any]]) -> bool:
        """
        Определение необходимости запуска субагентов на основе разбиения задачи.
        
        ПАРАМЕТРЫ:
        - task_breakdown: Список задач, на которые можно разбить основную задачу
        
        ВОЗВРАЩАЕТ:
        - True если рекомендуется запустить субагентов, иначе False
        """
        # Критерии для запуска субагентов:
        # 1. Есть более одной подзадачи
        # 2. Подзадачи являются независимыми (не зависят друг от друга)
        # 3. Подзадачи могут выполняться параллельно
        
        if len(task_breakdown) <= 1:
            return False
            
        # Проверяем, есть ли зависимости между задачами
        independent_tasks = 0
        for task in task_breakdown:
            # Если задача не зависит от других задач, считаем её независимой
            if not task.get('depends_on') or len(task['depends_on']) == 0:
                independent_tasks += 1
        
        # Если есть хотя бы 2 независимые задачи, имеет смысл запустить субагентов
        return independent_tasks >= 2

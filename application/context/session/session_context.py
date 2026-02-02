# Реализация контекста сессии
"""
SessionContext — реализация контекста сессии
"""
from typing import Any, Dict, Optional, List
from datetime import datetime
from domain.abstractions.system.base_session_context import BaseSessionContext
from domain.abstractions.event_system import IEventPublisher, EventType
import asyncio


class SessionContext(BaseSessionContext):
    """
    Реализация контекста сессии для управления состоянием сессии
    """
    
    def __init__(self, event_publisher: Optional[IEventPublisher] = None):
        """Инициализация контекста сессии."""
        self._event_publisher = event_publisher
        self._session_data: Dict[str, Any] = {
            "created_at": datetime.now(),
            "last_updated": datetime.now(),
            "goal": None,
            "steps": [],
            "metadata": {}
        }
        self._goal: Optional[str] = None
        self._initialized = False

    def get_session_data(self, key: str) -> Optional[Any]:
        """Получить данные сессии по ключу"""
        return self._session_data.get(key)

    def set_session_data(self, key: str, value: Any) -> None:
        """Установить данные сессии по ключу"""
        self._session_data[key] = value
        self._session_data["last_updated"] = datetime.now()

    async def initialize(self) -> bool:
        """Инициализировать контекст сессии"""
        try:
            self._session_data.clear()
            self._session_data = {
                "created_at": datetime.now(),
                "last_updated": datetime.now(),
                "goal": None,
                "steps": [],
                "metadata": {}
            }
            self._goal = None
            self._initialized = True
            
            # Публикация события через шину (если доступна)
            if self._event_publisher:
                try:
                    await self._event_publisher.publish(
                        event_type=EventType.INFO,
                        source="SessionContext",
                        data={
                            "message": "Session initialized",
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                except Exception:
                    # Не прерываем инициализацию при ошибке публикации
                    pass
            return True
        except Exception:
            return False

    async def cleanup(self) -> None:
        """Очистить ресурсы контекста сессии"""
        # Публикация события перед очисткой
        if self._event_publisher:
            try:
                await self._event_publisher.publish(
                    event_type=EventType.INFO,
                    source="SessionContext",
                    data={
                        "message": "Session cleaned up",
                        "timestamp": datetime.now().isoformat(),
                        "goal": self._goal
                    }
                )
            except Exception:
                pass
        
        # Базовая очистка
        self._session_data.clear()
        self._goal = None
        self._initialized = False

    def set_goal(self, goal: str) -> None:
        """Установка цели сессии с автоматической адаптацией к домену"""
        self._goal = goal
        self.set_session_data('goal', goal)
        
        # Базовая адаптация к домену через ключевые слова
        domain = self._detect_domain_from_goal(goal)
        self.set_session_data('detected_domain', domain)
        
        # Сохраняем цель в метаданные для аудита
        metadata = self.get_session_data('metadata') or {}
        metadata['goal_history'] = metadata.get('goal_history', [])
        metadata['goal_history'].append({
            'goal': goal,
            'domain': domain,
            'timestamp': datetime.now().isoformat()
        })
        self.set_session_data('metadata', metadata)
        
        # Публикация события
        if self._event_publisher:
            try:
                asyncio.create_task(self._event_publisher.publish(
                    event_type=EventType.INFO,
                    source="SessionContext",
                    data={
                        "goal": goal[:100],  # Обрезаем для логов
                        "domain": self.get_session_data('detected_domain'),
                        "timestamp": datetime.now().isoformat()
                    }
                ))
            except Exception:
                pass

    def get_goal(self) -> Optional[str]:
        """Получить цель сессии"""
        return self._goal

    def _detect_domain_from_goal(self, goal: str) -> str:
        """
        Определение домена задачи по ключевым словам в цели.
        Адаптировано из старой версии с упрощённой логикой.
        """
        goal_lower = goal.lower().strip()
        
        # Приоритетные домены (более специфичные)
        if any(kw in goal_lower for kw in ['sql', 'запрос', 'база данных', 'таблица', 'select', 'insert', 'join']):
            return 'sql_generation'
        if any(kw in goal_lower for kw in ['тест', 'покрытие', 'валидация', 'юнит-тест', 'тестирование']):
            return 'testing'
        if any(kw in goal_lower for kw in ['документация', 'док', 'описание', 'комментарий', 'документирование']):
            return 'documentation'
        
        # Общий домен анализа кода
        if any(kw in goal_lower for kw in [
            'код', 'анализ', 'файл', 'структура', 'зависимость', 'импорт',
            'класс', 'функция', 'метод', 'переменная', 'модуль', 'пакет'
        ]):
            return 'code_analysis'
        
        # Домен по умолчанию
        return 'general'

    def record_step(self,
                    step_number: int,
                    capability_name: str,
                    action_item_id: str,
                    observation_item_ids: List[str],
                    summary: str) -> None:
        """Записать шаг выполнения в контекст сессии"""
        step = {
            "step_number": step_number,
            "capability_name": capability_name,
            "action_item_id": action_item_id,
            "observation_item_ids": observation_item_ids,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
        
        # Получение текущего списка шагов
        steps = self.get_session_data('steps') or []
        steps.append(step)
        self.set_session_data('steps', steps)
        
        # Публикация события о шаге
        if self._event_publisher:
            try:
                asyncio.create_task(self._event_publisher.publish(
                    event_type=EventType.INFO,
                    source="SessionContext",
                    data={
                        "step_number": step_number,
                        "capability": capability_name,
                        "summary": summary[:100],
                        "timestamp": step["timestamp"]
                    }
                ))
            except Exception:
                pass

    def get_current_step_number(self) -> int:
        """Получить номер текущего шага (последнего)"""
        steps = self.get_session_data('steps') or []
        return len(steps)

    def get_last_steps(self, count: int) -> List[Dict]:
        """Получить последние N шагов"""
        steps = self.get_session_data('steps') or []
        return steps[-count:] if count <= len(steps) else steps[:]

"""
Метрики агента для отслеживания качества выполнения.

АРХИТЕКТУРА:
- Отслеживание ошибок, повторов действий, пустых результатов
- Интеграция с SessionContext через composition
- Используется для Reflection и Policy проверок

ОПТИМИЗАЦИЯ (Фаза 1):
- Метрика observer_skip_rate для мониторинга экономии LLM-вызовов
- Счётчик total_llm_calls для отслеживания количества вызовов LLM
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentMetrics:
    """
    Метрики выполнения агента.
    
    АТРИБУТЫ:
    - step_number: текущий номер шага
    - errors: список ошибок (тип + описание)
    - empty_results_count: счётчик пустых результатов
    - repeated_actions_count: счётчик повторяющихся действий
    - recent_actions: последние N действий для детектирования повторов
    - action_hashes: хеши действий с параметрами для точного детектирования повторов
    - observer_llm_calls: количество вызовов LLM в Observer
    - observer_skips: количество пропущенных LLM-вызовов (rule-based)
    """
    step_number: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    empty_results_count: int = 0
    repeated_actions_count: int = 0
    recent_actions: List[str] = field(default_factory=list)
    max_recent_actions: int = 10
    action_hashes: List[str] = field(default_factory=list)
    
    # Метрики Observer
    observer_llm_calls: int = 0
    observer_skips: int = 0
    total_tokens_used: int = 0

    def _hash_action(self, action_name: str, parameters: Dict[str, Any]) -> str:
        """Создаёт хеш действия учитывая имя и параметры."""
        import hashlib
        import json

        normalized_params = self._normalize_parameters(parameters)
        action_key = f"{action_name}:{json.dumps(normalized_params, sort_keys=True)}"
        return hashlib.md5(action_key.encode()).hexdigest()[:12]

    def _normalize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализует параметры для хеширования (убирает несущественные поля)."""
        if not params:
            return {}

        ignored_keys = {"session_id", "correlation_id", "agent_id", "context", "execution_context"}
        normalized = {k: v for k, v in params.items() if k not in ignored_keys}

        for k, v in normalized.items():
            if isinstance(v, dict):
                normalized[k] = self._normalize_parameters(v)
            elif isinstance(v, list):
                try:
                    normalized[k] = tuple(v)
                except TypeError:
                    normalized[k] = v

        return normalized

    def add_step(
        self,
        action_name: str,
        status: str,
        error: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Регистрация шага.

        ПАРАМЕТРЫ:
        - action_name: имя выполненного действия
        - status: статус выполнения (success, error, empty, partial)
        - error: описание ошибки (если есть)
        - parameters: параметры действия (учитываются в хеше)
        """
        self.step_number += 1

        action_hash = self._hash_action(action_name, parameters or {})
        self.action_hashes.append(action_hash)
        if len(self.action_hashes) > self.max_recent_actions:
            self.action_hashes.pop(0)

        self.recent_actions.append(action_name)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions.pop(0)
        
        # Обработка ошибок
        if status == "error" and error:
            self.errors.append({
                "step": self.step_number,
                "action": action_name,
                "error": error,
                "timestamp": datetime.now().isoformat()
            })
        
        # Обработка пустых результатов
        if status == "empty":
            self.empty_results_count += 1
    
    def add_error(self, error_type: str, description: str, action: Optional[str] = None):
        """
        Добавление ошибки.
        
        ПАРАМЕТРЫ:
        - error_type: тип ошибки (REFLECTION, POLICY, EXECUTION, OBSERVATION)
        - description: описание ошибки
        - action: имя действия (если применимо)
        """
        self.errors.append({
            "step": self.step_number,
            "type": error_type,
            "action": action,
            "description": description,
            "timestamp": datetime.now().isoformat()
        })
    
    def check_repeated_action(
        self,
        action_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Проверка: является ли действие повтором (с учётом параметров).

        ПАРАМЕТРЫ:
        - action_name: имя действия для проверки
        - parameters: параметры действия (опционально)

        ВОЗВРАЩАЕТ:
        - True если действие повторяется с теми же параметрами
        """
        if not parameters:
            parameters = {}

        current_hash = self._hash_action(action_name, parameters)

        recent_hashes = self.action_hashes[-5:] if len(self.action_hashes) >= 5 else self.action_hashes[:-1]
        is_exact_repeat = current_hash in recent_hashes

        if is_exact_repeat:
            self.repeated_actions_count += 1
            return True

        recent_actions_only = self.recent_actions[-5:] if len(self.recent_actions) >= 5 else self.recent_actions[:-1]
        name_repeat = action_name in recent_actions_only

        return name_repeat
    
    def get_recent_actions(self, n: int = 5) -> List[str]:
        """
        Получить последние N действий.
        
        ПАРАМЕТРЫ:
        - n: количество действий
        
        ВОЗВРАЩАЕТ:
        - список имён действий
        """
        return self.recent_actions[-n:] if n <= len(self.recent_actions) else self.recent_actions
    
    def get_errors_summary(self, n: int = 3) -> List[str]:
        """
        Получить краткое описание последних N ошибок.
        
        ПАРАМЕТРЫ:
        - n: количество ошибок
        
        ВОЗВРАЩАЕТ:
        - список строк с описанием ошибок
        """
        recent_errors = self.errors[-n:]
        return [
            f"[{e.get('type', 'UNKNOWN')}] {e.get('action', 'N/A')}: {e.get('description', 'No description')}"
            for e in recent_errors
        ]
    
    def should_stop(self, max_errors: int = 10, max_empty: int = 3, max_repeats: int = 3) -> tuple[bool, str]:
        """
        Проверка условий остановки.
        
        ПАРАМЕТРЫ:
        - max_errors: максимальное количество ошибок
        - max_empty: максимальное количество пустых результатов
        - max_repeats: максимальное количество повторов
        
        ВОЗВРАЩАЕТ:
        - (should_stop, reason)
        """
        if len(self.errors) >= max_errors:
            return True, f"max_errors_reached ({len(self.errors)})"
        
        if self.empty_results_count >= max_empty:
            return True, f"max_empty_results ({self.empty_results_count})"
        
        if self.repeated_actions_count >= max_repeats:
            return True, f"max_repeated_actions ({self.repeated_actions_count})"
        
        return False, ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для prompt."""
        return {
            "step_number": self.step_number,
            "total_errors": len(self.errors),
            "empty_results_count": self.empty_results_count,
            "repeated_actions_count": self.repeated_actions_count,
            "recent_actions": self.get_recent_actions(5),
            "last_errors": self.get_errors_summary(3),
            "observer_llm_calls": self.observer_llm_calls,
            "observer_skips": self.observer_skips,
            "total_tokens_used": self.total_tokens_used,
        }
    
    def record_observer_call(self, used_llm: bool):
        """
        Регистрация вызова Observer.
        
        ПАРАМЕТРЫ:
        - used_llm: True если был вызван LLM, False если использован rule-based
        """
        if used_llm:
            self.observer_llm_calls += 1
        else:
            self.observer_skips += 1
    
    def add_tokens(self, count: int):
        """Добавление использованных токенов."""
        self.total_tokens_used += count

    @property
    def observer_skip_rate(self) -> float:
        """Процент пропущенных LLM-вызовов от общего числа наблюдений."""
        total = self.observer_llm_calls + self.observer_skips
        if total == 0:
            return 0.0
        return self.observer_skips / total

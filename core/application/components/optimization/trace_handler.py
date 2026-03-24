"""
TraceHandler — обработка execution traces.

КОМПОНЕНТЫ:
- TraceHandler: получение и реконструкция traces из логов

FEATURES:
- Реконструкция ExecutionTrace из сессионных логов
- Получение traces по capability
- Фильтрация по успешности
- Анализ паттернов выполнения
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models.data.execution_trace import (
    ExecutionTrace,
    StepTrace,
    LLMRequest,
    LLMResponse,
    Action,
    ActionResult,
    ErrorDetail,
    ActionType,
    ErrorType,
)


class TraceHandler:
    """
    Обработчик execution traces.

    RESPONSIBILITIES:
    - Реконструкция traces из сессионных логов
    - Получение traces по capability
    - Фильтрация traces

    USAGE:
    ```python
    handler = TraceHandler(session_handler)
    trace = await handler.get_execution_trace(session_id)
    traces = await handler.get_traces_by_capability('book_library.search_books')
    ```
    """

    def __init__(self, session_handler=None, logs_dir: str = "data/logs"):
        """
        Инициализация TraceHandler.

        ARGS:
        - session_handler: обработчик сессий (опционально)
        - logs_dir: директория с логами
        """
        self.session_handler = session_handler
        self.logs_dir = Path(logs_dir)

    async def get_execution_trace(self, session_id: str) -> Optional[ExecutionTrace]:
        """
        Реконструкция полного ExecutionTrace из логов сессии.

        ARGS:
        - session_id: идентификатор сессии

        RETURNS:
        - ExecutionTrace или None если не найдено
        """
        # Попытка получить из session_handler
        if self.session_handler and hasattr(self.session_handler, 'get_session_logs'):
            logs = await self.session_handler.get_session_logs(session_id)
            return self._reconstruct_trace_from_logs(logs, session_id)

        # Попытка получить из файлов логов
        trace = await self._load_trace_from_file(session_id)
        if trace:
            return trace

        return None

    async def get_traces_by_capability(
        self,
        capability: str,
        limit: int = 100,
        success_filter: Optional[bool] = None
    ) -> List[ExecutionTrace]:
        """
        Получение traces для capability.

        ARGS:
        - capability: название способности
        - limit: максимум traces
        - success_filter: фильтр по успешности (True/False/None)

        RETURNS:
        - List[ExecutionTrace]: список traces
        """
        traces = []

        # Поиск в логах по capability
        if self.logs_dir.exists():
            traces = await self._search_traces_by_capability(
                capability, limit, success_filter
            )

        return traces

    async def get_failed_traces(
        self,
        capability: str,
        limit: int = 50
    ) -> List[ExecutionTrace]:
        """
        Получение только неудачных traces.

        ARGS:
        - capability: название способности
        - limit: максимум traces

        RETURNS:
        - List[ExecutionTrace]: список неудачных traces
        """
        return await self.get_traces_by_capability(
            capability,
            limit=limit,
            success_filter=False
        )

    async def get_successful_traces(
        self,
        capability: str,
        limit: int = 50
    ) -> List[ExecutionTrace]:
        """
        Получение только успешных traces.

        ARGS:
        - capability: название способности
        - limit: максимум traces

        RETURNS:
        - List[ExecutionTrace]: список успешных traces
        """
        return await self.get_traces_by_capability(
            capability,
            limit=limit,
            success_filter=True
        )

    def _reconstruct_trace_from_logs(
        self,
        logs: List[Dict[str, Any]],
        session_id: str
    ) -> Optional[ExecutionTrace]:
        """
        Реконструкция trace из логов.

        ARGS:
        - logs: список логов
        - session_id: идентификатор сессии

        RETURNS:
        - ExecutionTrace или None
        """
        if not logs:
            return None

        # Извлечение базовой информации
        goal = self._extract_goal(logs)
        agent_id = self._extract_agent_id(logs)
        started_at = self._extract_started_at(logs)

        trace = ExecutionTrace(
            session_id=session_id,
            agent_id=agent_id,
            goal=goal,
            started_at=started_at
        )

        # Реконструкция шагов
        steps = self._reconstruct_steps(logs)
        for step in steps:
            trace.add_step(step)

        # Извлечение финального ответа
        trace.final_answer = self._extract_final_answer(logs)

        return trace

    def _reconstruct_steps(
        self,
        logs: List[Dict[str, Any]]
    ) -> List[StepTrace]:
        """
        Реконструкция шагов из логов.

        ARGS:
        - logs: список логов

        RETURNS:
        - List[StepTrace]: список шагов
        """
        steps = []
        step_number = 0

        # Группировка логов по шагам
        step_logs = self._group_logs_by_step(logs)

        for step_id, step_log_group in step_logs.items():
            step = self._create_step_from_logs(step_number, step_log_group)
            if step:
                steps.append(step)
                step_number += 1

        return steps

    def _create_step_from_logs(
        self,
        step_number: int,
        logs: List[Dict[str, Any]]
    ) -> Optional[StepTrace]:
        """
        Создание шага из группы логов.

        ARGS:
        - step_number: номер шага
        - logs: логи шага

        RETURNS:
        - StepTrace или None
        """
        if not logs:
            return None

        # Извлечение информации о шаге
        capability = self._extract_capability(logs)
        goal = self._extract_step_goal(logs)

        step = StepTrace(
            step_number=step_number,
            capability=capability,
            goal=goal
        )

        # Извлечение LLM запроса/ответа
        step.llm_request = self._extract_llm_request(logs)
        step.llm_response = self._extract_llm_response(logs)

        # Извлечение действия
        step.action = self._extract_action(logs)
        step.action_result = self._extract_action_result(logs)

        # Извлечение ошибок
        step.errors = self._extract_errors(logs, step_number, capability)

        # Извлечение метрик
        step.time_ms = self._extract_step_time(logs)
        step.tokens_used = self._extract_step_tokens(logs)

        return step

    async def _load_trace_from_file(
        self,
        session_id: str
    ) -> Optional[ExecutionTrace]:
        """
        Загрузка trace из файла.

        ARGS:
        - session_id: идентификатор сессии

        RETURNS:
        - ExecutionTrace или None
        """
        # Поиск файла trace
        trace_file = self.logs_dir / "sessions" / f"{session_id}_trace.json"

        if not trace_file.exists():
            return None

        try:
            with open(trace_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return ExecutionTrace.from_dict(data)
        except Exception:
            return None

    async def _search_traces_by_capability(
        self,
        capability: str,
        limit: int,
        success_filter: Optional[bool]
    ) -> List[ExecutionTrace]:
        """
        Поиск traces по capability.

        ARGS:
        - capability: название способности
        - limit: максимум результатов
        - success_filter: фильтр по успешности

        RETURNS:
        - List[ExecutionTrace]: список traces
        """
        traces = []

        # Поиск в директории sessions
        sessions_dir = self.logs_dir / "sessions"
        if not sessions_dir.exists():
            return []

        for trace_file in sessions_dir.glob("*_trace.json"):
            if len(traces) >= limit:
                break

            try:
                with open(trace_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Проверка capability
                if not self._trace_has_capability(data, capability):
                    continue

                # Проверка success filter
                if success_filter is not None:
                    if data.get('success') != success_filter:
                        continue

                trace = ExecutionTrace.from_dict(data)
                traces.append(trace)

            except Exception:
                continue

        return traces

    # === Helper методы для извлечения данных ===

    def _extract_goal(self, logs: List[Dict[str, Any]]) -> str:
        """Извлечение цели из логов"""
        for log in logs:
            if log.get('event') == 'session_started':
                return log.get('data', {}).get('goal', '')
        return ""

    def _extract_agent_id(self, logs: List[Dict[str, Any]]) -> str:
        """Извлечение agent_id из логов"""
        for log in logs:
            if log.get('agent_id'):
                return log['agent_id']
        return "unknown"

    def _extract_started_at(self, logs: List[Dict[str, Any]]) -> datetime:
        """Извлечение времени начала"""
        for log in logs:
            if log.get('timestamp'):
                try:
                    return datetime.fromisoformat(log['timestamp'])
                except Exception:
                    pass
        return datetime.now()

    def _extract_capability(self, logs: List[Dict[str, Any]]) -> str:
        """Извлечение capability из логов"""
        for log in logs:
            if log.get('capability'):
                return log['capability']
            if log.get('data', {}).get('capability'):
                return log['data']['capability']
        return "unknown"

    def _extract_step_goal(self, logs: List[Dict[str, Any]]) -> str:
        """Извлечение цели шага"""
        for log in logs:
            if log.get('event') == 'capability_selected':
                return log.get('data', {}).get('goal', '')
        return ""

    def _extract_llm_request(self, logs: List[Dict[str, Any]]) -> Optional[LLMRequest]:
        """Извлечение LLM запроса"""
        for log in logs:
            if log.get('event') == 'llm_request':
                data = log.get('data', {})
                return LLMRequest(
                    prompt=data.get('prompt', ''),
                    system_prompt=data.get('system_prompt', ''),
                    temperature=data.get('temperature', 0.7),
                    max_tokens=data.get('max_tokens', 2048),
                    model=data.get('model', 'default')
                )
        return None

    def _extract_llm_response(self, logs: List[Dict[str, Any]]) -> Optional[LLMResponse]:
        """Извлечение LLM ответа"""
        for log in logs:
            if log.get('event') == 'llm_response':
                data = log.get('data', {})
                return LLMResponse(
                    content=data.get('content', ''),
                    tokens_used=data.get('tokens_used', 0),
                    latency_ms=data.get('latency_ms', 0),
                    model=data.get('model', 'default')
                )
        return None

    def _extract_action(self, logs: List[Dict[str, Any]]) -> Optional[Action]:
        """Извлечение действия"""
        for log in logs:
            if log.get('event') == 'action_executed':
                data = log.get('data', {})
                action_type = data.get('action_type', 'none')
                try:
                    action_type_enum = ActionType(action_type)
                except ValueError:
                    action_type_enum = ActionType.NONE

                return Action(
                    action_type=action_type_enum,
                    name=data.get('name', ''),
                    input_data=data.get('input_data', {})
                )
        return None

    def _extract_action_result(self, logs: List[Dict[str, Any]]) -> Optional[ActionResult]:
        """Извлечение результата действия"""
        for log in logs:
            if log.get('event') == 'action_result':
                data = log.get('data', {})
                return ActionResult(
                    success=data.get('success', False),
                    output_data=data.get('output_data'),
                    execution_time_ms=data.get('execution_time_ms', 0),
                    error=data.get('error')
                )
        return None

    def _extract_errors(
        self,
        logs: List[Dict[str, Any]],
        step_number: int,
        capability: str
    ) -> List[ErrorDetail]:
        """Извлечение ошибок"""
        errors = []

        for log in logs:
            if log.get('event') == 'error_occurred':
                data = log.get('data', {})
                error_type_str = data.get('error_type', 'unknown')
                try:
                    error_type = ErrorType(error_type_str)
                except ValueError:
                    error_type = ErrorType.UNKNOWN

                error = ErrorDetail(
                    error_type=error_type,
                    message=data.get('error_message', data.get('error', '')),
                    traceback=data.get('traceback'),
                    capability=capability,
                    step_number=step_number,
                    context=data.get('context', {})
                )
                errors.append(error)

        return errors

    def _extract_step_time(self, logs: List[Dict[str, Any]]) -> float:
        """Извлечение времени выполнения шага"""
        for log in logs:
            if log.get('event') == 'step_completed':
                return log.get('data', {}).get('time_ms', 0)
        return 0.0

    def _extract_step_tokens(self, logs: List[Dict[str, Any]]) -> int:
        """Извлечение количества токенов"""
        total = 0
        for log in logs:
            if log.get('event') == 'llm_response':
                total += log.get('data', {}).get('tokens_used', 0)
        return total

    def _extract_final_answer(self, logs: List[Dict[str, Any]]) -> Optional[str]:
        """Извлечение финального ответа"""
        for log in reversed(logs):
            if log.get('event') == 'session_completed':
                return log.get('data', {}).get('final_answer')
        return None

    def _group_logs_by_step(
        self,
        logs: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Группировка логов по шагам"""
        groups = {}
        current_step = "0"

        for log in logs:
            event = log.get('event', '')

            if event == 'step_started':
                current_step = log.get('data', {}).get('step_id', current_step)

            if current_step not in groups:
                groups[current_step] = []

            groups[current_step].append(log)

        return groups

    def _trace_has_capability(
        self,
        trace_data: Dict[str, Any],
        capability: str
    ) -> bool:
        """Проверка наличия capability в trace"""
        # Проверка в steps
        for step in trace_data.get('steps', []):
            if step.get('capability') == capability:
                return True

        # Проверка в capabilities_used
        if capability in trace_data.get('capabilities_used', []):
            return True

        return False

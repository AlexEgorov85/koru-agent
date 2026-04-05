"""
TraceHandler — обработка execution traces.

КОМПОНЕНТЫ:
- TraceHandler: получение и реконструкция traces из логов

FEATURES:
- Реконструкция ExecutionTrace из сессионных логов (JSONL)
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
        # Попытка загрузить из session.jsonl
        trace = await self._load_trace_from_jsonl(session_id)
        if trace:
            return trace

        # Попытка получить из session_handler
        if self.session_handler and hasattr(self.session_handler, 'get_session_logs'):
            logs = await self.session_handler.get_session_logs(session_id)
            return self._reconstruct_trace_from_logs(logs, session_id)

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

    async def _load_trace_from_jsonl(
        self,
        session_id: str
    ) -> Optional[ExecutionTrace]:
        """
        Загрузка и парсинг session.jsonl в ExecutionTrace.

        ФОРМАТ ЛОГОВ:
        {"timestamp": ..., "event_type": "llm.prompt.generated", "capability": "...", ...}
        {"timestamp": ..., "event_type": "llm.response.received", ...}
        {"timestamp": ..., "event_type": "log.info", "message": "Метрика: ..."}

        ARGS:
        - session_id: идентификатор сессии (имя директории)

        RETURNS:
        - ExecutionTrace или None
        """
        session_dir = self.logs_dir / "sessions" / session_id
        jsonl_file = session_dir / "session.jsonl"

        if not jsonl_file.exists():
            return None

        events = []
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            event = json.loads(line)
                            events.append(event)
                        except json.JSONDecodeError:
                            continue
        except Exception:
            return None

        if not events:
            return None

        # Извлечение реального session_id из событий
        real_session_id = session_id
        for event in events:
            sid = event.get('session_id')
            if sid and sid != 'system':
                real_session_id = sid
                break

        # Парсинг событий в trace
        return self._parse_events_to_trace(events, real_session_id)

    def _parse_events_to_trace(
        self,
        events: List[Dict[str, Any]],
        session_id: str
    ) -> ExecutionTrace:
        """
        Парсинг событий в ExecutionTrace.

        ARGS:
        - events: список событий из логов
        - session_id: идентификатор сессии

        RETURNS:
        - ExecutionTrace
        """
        # Извлечение базовой информации
        started_at = self._parse_timestamp(events[0].get('timestamp')) if events else datetime.now()
        goal = self._extract_goal_from_events(events)
        agent_id = "agent_001"  # Default

        trace = ExecutionTrace(
            session_id=session_id,
            agent_id=agent_id,
            goal=goal,
            started_at=started_at
        )

        # Парсинг шагов
        steps = self._parse_steps_from_events(events)
        for step in steps:
            trace.add_step(step)

        # Извлечение финального ответа
        trace.final_answer = self._extract_final_answer_from_events(events)

        # Определение успешности
        trace.success = self._determine_success_from_events(events)

        # Извлечение ошибки если есть
        if not trace.success:
            trace.error = self._extract_error_from_events(events)

        return trace

    def _parse_steps_from_events(
        self,
        events: List[Dict[str, Any]]
    ) -> List[StepTrace]:
        """
        Парсинг событий в список шагов.
        
        НОВАЯ ЛОГИКА (3 прохода):
        - Проход 1: Собираем метрики из metric.collected И log.info
        - Проход 2: Создаём шаги из llm.* событий
        - Проход 3: Привязываем метрики к шагам
        """
        # === ПРОХОД 1: Собираем метрики ===
        metrics_by_capability: Dict[str, Dict] = {}
        
        for event in events:
            event_type = event.get('event_type', '')
            
            if event_type == 'metric.collected':
                capability = event.get('capability', 'unknown')
                metric_name = event.get('name', '')
                metric_value = event.get('value', 0)
                
                if capability not in metrics_by_capability:
                    metrics_by_capability[capability] = {'count': 0}
                
                metrics_by_capability[capability]['count'] = metrics_by_capability[capability].get('count', 0) + 1
                
                if metric_name == 'execution_time_ms':
                    metrics_by_capability[capability]['execution_time_ms'] = float(metric_value)
                elif metric_name == 'tokens_used':
                    metrics_by_capability[capability]['tokens_used'] = int(metric_value)
                elif metric_name == 'success':
                    metrics_by_capability[capability]['success'] = float(metric_value) == 1.0
            
            elif event_type in ('log.info', 'log.debug', 'info'):
                message = event.get('message', '')
                if 'Метрика:' in message:
                    capability = self._extract_capability_from_event(event)
                    metric_info = self._parse_metric_message(message)
                    
                    if capability not in metrics_by_capability:
                        metrics_by_capability[capability] = {'count': 0}
                    
                    metrics_by_capability[capability]['count'] += 1
                    metrics_by_capability[capability]['execution_time_ms'] = metric_info['execution_time_ms']
                    metrics_by_capability[capability]['success'] = metric_info['success']
                    metrics_by_capability[capability]['rows'] = metric_info['rows']
        
        # === ПРОХОД 2: Создаём шаги ===
        steps = []
        current_step = None
        step_number = 0
        
        # Отслеживаем какие capability уже использованы
        used_capabilities: Dict[str, int] = {}
        
        for event in events:
            event_type = event.get('event_type', '')
            
            # Начало нового шага (LLM запрос)
            if event_type == 'llm.prompt.generated':
                if current_step:
                    steps.append(current_step)
                
                # Создаём новый шаг
                current_step = StepTrace(
                    step_number=step_number,
                    capability="unknown",
                    goal=""
                )
                current_step.llm_request = self._parse_llm_request(event)
                step_number += 1
            
            # LLM ответ
            elif event_type == 'llm.response.received':
                if current_step:
                    current_step.llm_response = self._parse_llm_response(event)
        
        # Добавляем последний шаг
        if current_step:
            steps.append(current_step)
        
        # === ПРОХОД 3: Привязываем метрики к шагам ===
        # Сопоставляем шаги с метриками по порядку появления capability
        for step in steps:
            # Ищем capability с метриками который ещё не использован
            for capability, metrics in metrics_by_capability.items():
                cap_count = used_capabilities.get(capability, 0)
                total_count = metrics.get('count', 0)
                
                # Если есть неиспользованные метрики для этого capability
                if cap_count < total_count and 'execution_time_ms' in metrics:
                    step.capability = capability
                    step.time_ms = metrics.get('execution_time_ms', 0)
                    step.tokens_used = metrics.get('tokens_used', 0)
                    
                    # Проверка успешности
                    if not metrics.get('success', True):
                        step.errors.append(ErrorDetail(
                            error_type=ErrorType.LOGIC_ERROR,
                            message='Execution failed',
                            capability=capability,
                            step_number=step.step_number
                        ))
                    
                    used_capabilities[capability] = cap_count + 1
                    break
        
        return steps

    def _parse_llm_request(self, event: Dict[str, Any]) -> Optional[LLMRequest]:
        """Парсинг LLM запроса из события"""
        return LLMRequest(
            prompt=event.get('message', '') or 'Prompt generated',
            system_prompt='',
            temperature=0.7,
            max_tokens=2048,
        )

    def _parse_llm_response(self, event: Dict[str, Any]) -> Optional[LLMResponse]:
        """Парсинг LLM ответа"""
        content = event.get('message', '')
        if not content:
            content = f"[LLM response received at {event.get('timestamp', 'unknown')}]"
        
        return LLMResponse(
            content=content,
            tokens_used=0,
            generation_time=0,
        )

    def _parse_metric_message(self, message: str) -> Dict[str, Any]:
        """
        Парсинг сообщения с метрикой.

        ФОРМАТ:
        "Метрика: capability | execution_type=static | execution_time=145.36ms | rows=5 | success=True"
        """
        result = {
            'success': True,
            'execution_time_ms': 0,
            'tokens': 0,
            'rows': 0
        }

        # Парсинг ключевых частей
        parts = message.split('|')
        for part in parts:
            part = part.strip()

            if 'execution_time=' in part:
                try:
                    time_str = part.split('=')[1].strip().replace('ms', '')
                    result['execution_time_ms'] = float(time_str)
                except (ValueError, IndexError):
                    pass

            elif 'success=' in part:
                result['success'] = 'True' in part

            elif 'rows=' in part:
                try:
                    result['rows'] = int(part.split('=')[1].strip())
                except (ValueError, IndexError):
                    pass

        return result

    def _extract_capability_from_event(self, event: Dict[str, Any]) -> str:
        """Извлечение capability из события"""
        
        # 1. Прямое поле capability (для metric.collected)
        capability = event.get('capability')
        if capability and capability != 'null' and capability != 'None':
            return capability
        
        # 2. Поиск в logger_name (формат: core.services.skills.book_library...)
        logger_name = event.get('logger_name', '')
        if logger_name:
            # Извлекаем skill/service name
            if 'skills.' in logger_name:
                parts = logger_name.split('skills.')
                if len(parts) > 1:
                    return parts[1].split('.')[0]
            if 'services.' in logger_name:
                parts = logger_name.split('services.')
                if len(parts) > 1:
                    return parts[1].split('.')[0]
        
        # 3. Поиск в message (старый формат "Метрика: capability | ...")
        message = event.get('message', '')
        if message and 'Метрика:' in message:
            parts = message.split('|')
            if parts:
                cap = parts[0].replace('Метрика:', '').strip()
                if cap and cap != 'None':
                    return cap
        
        return "unknown"

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """Парсинг timestamp строки"""
        if not timestamp_str:
            return datetime.now()

        try:
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            return datetime.now()

    def _extract_goal_from_events(self, events: List[Dict[str, Any]]) -> str:
        """Извлечение цели из событий"""
        for event in events:
            event_type = event.get('event_type', '')
            if event_type == 'session.started':
                goal = event.get('goal', '')
                if goal:
                    return goal
            message = event.get('message', '')
            if 'ЦЕЛЬ:' in message:
                parts = message.split('ЦЕЛЬ:', 1)
                if len(parts) > 1:
                    return parts[1].strip().split('\n')[0][:200]

        return "Session goal"

    def _extract_final_answer_from_events(self, events: List[Dict[str, Any]]) -> Optional[str]:
        """Извлечение финального ответа"""
        for event in reversed(events):
            message = event.get('message', '')
            if 'final_answer' in message.lower() or 'ответ:' in message.lower():
                return message[:500]
        return None

    def _determine_success_from_events(self, events: List[Dict[str, Any]]) -> bool:
        """Определение успешности из событий"""
        for event in events:
            message = event.get('message', '')
            if 'Метрика:' in message:
                metric = self._parse_metric_message(message)
                if not metric.get('success', True):
                    return False
        return True

    def _extract_error_from_events(self, events: List[Dict[str, Any]]) -> Optional[str]:
        """Извлечение ошибки из событий"""
        for event in events:
            message = event.get('message', '')
            if 'error' in message.lower() and 'None' not in message:
                return message[:200]
        return None

    async def _search_traces_by_capability(
        self,
        capability: str,
        limit: int,
        success_filter: Optional[bool]
    ) -> List[ExecutionTrace]:
        """
        Поиск traces по capability.

        СТРАТЕГИИ:
        1. Поиск *_trace.json файлов (готовые traces)
        2. Fallback: сканирование session.jsonl в директориях сессий

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

        # Стратегия 1: Поиск *_trace.json файлов
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

        # Стратегия 2 (fallback): Сканирование session.jsonl
        if len(traces) < limit:
            for session_dir in sorted(sessions_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if len(traces) >= limit:
                    break

                if not session_dir.is_dir():
                    continue

                jsonl_file = session_dir / "session.jsonl"
                if not jsonl_file.exists():
                    continue

                try:
                    trace = await self._load_trace_from_jsonl(session_dir.name)
                    if trace is None:
                        continue

                    # Проверка capability в trace
                    caps_used = trace.get_capabilities_used()
                    if not self._trace_matches_capability(trace, capability):
                        continue

                    # Проверка success filter
                    if success_filter is not None:
                        if trace.success != success_filter:
                            continue

                    traces.append(trace)

                except Exception as e:
                    continue

        return traces

    def _trace_matches_capability(
        self,
        trace: ExecutionTrace,
        capability: str
    ) -> bool:
        """Проверка наличия capability в ExecutionTrace"""
        # Проверка по шагам
        for step in trace.steps:
            if step.capability == capability or capability in step.capability:
                return True

        # Проверка по goal (если capability упоминается в цели)
        if capability in trace.goal:
            return True

        # Проверка capabilities_used
        caps = trace.get_capabilities_used()
        for cap in caps:
            if cap == capability or capability in cap or cap in capability:
                return True

        return False

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

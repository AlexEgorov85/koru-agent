"""
Парсер лога сессии агента для анализа и оптимизации промптов.

Извлекает из session.jsonl:
- Ошибки (event_type содержащий error/failed)
- LLM вызовы (llm.prompt.generated, llm.response.received)
- Решения агента (action)
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class LLMCall:
    """Один LLM вызов с prompt и response"""
    call_id: str
    timestamp: str
    success: bool
    duration_ms: float
    system_prompt: str
    user_prompt: str
    response: str
    raw_response: Optional[str] = None
    step_number: Optional[int] = None
    phase: Optional[str] = None
    goal: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AgentAction:
    """Действие агента"""
    timestamp: str
    action: str
    reasoning: str
    parameters: Dict[str, Any]
    result_status: str
    error: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class ParsedSession:
    """Распарсенная сессия"""
    path: Path
    session_id: Optional[str]
    agent_id: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    llm_calls: List[LLMCall] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)


class SessionLogParser:
    """Парсер лога сессии агента"""
    
    EVENT_TYPES = {
        'llm_prompt': 'llm.prompt.generated',
        'llm_response': 'llm.response.received',
        'error': 'error',
        'failed': 'failed',
        'action': 'action',
    }
    
    def parse_file(self, path: Path) -> ParsedSession:
        """Парсинг файла session.jsonl"""
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        session = ParsedSession(
            path=path,
            session_id=None,
            agent_id=None,
            start_time=None,
            end_time=None
        )
        
        # Для сопоставления prompt и response
        pending_prompts: Dict[str, Dict] = {}
        last_action: Optional[Dict] = None
        
        for line in lines:
            try:
                event = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            
            event_type = event.get('event_type', '')
            
            # Извлекаем session_id и agent_id
            if event.get('session_id'):
                session.session_id = event['session_id']
            if event.get('agent_id'):
                session.agent_id = event['agent_id']
            
            # Время начала/конца
            if not session.start_time:
                session.start_time = event.get('timestamp')
            session.end_time = event.get('timestamp')
            
            # LLM prompt
            if event_type == 'llm.prompt.generated':
                prompt_data = {
                    'call_id': event.get('call_id'),
                    'timestamp': event.get('timestamp'),
                    'system_prompt': event.get('system_prompt', ''),
                    'user_prompt': event.get('user_prompt', ''),
                    'step_number': event.get('step_number'),
                    'phase': event.get('phase'),
                    'goal': event.get('goal'),
                }
                pending_prompts[event.get('call_id')] = prompt_data
            
            # LLM response
            elif event_type == 'llm.response.received':
                call_id = event.get('call_id')
                prompt_data = pending_prompts.pop(call_id, {})
                
                llm_call = LLMCall(
                    call_id=call_id,
                    timestamp=event.get('timestamp'),
                    success=event.get('success', False),
                    duration_ms=event.get('duration_ms', 0),
                    system_prompt=prompt_data.get('system_prompt', ''),
                    user_prompt=prompt_data.get('user_prompt', ''),
                    response=event.get('response', ''),
                    raw_response=event.get('raw_response'),
                    step_number=prompt_data.get('step_number'),
                    phase=prompt_data.get('phase'),
                    goal=prompt_data.get('goal'),
                    error=event.get('error')
                )
                session.llm_calls.append(llm_call)
                
                # Извлекаем goal из user_prompt если есть
                if prompt_data.get('goal'):
                    session.goals.append(prompt_data['goal'])
                else:
                    user_prompt = prompt_data.get('user_prompt', '')
                    if 'ЦЕЛЬ:' in user_prompt:
                        goal_match = re.search(r'ЦЕЛЬ:\s*(.+?)(?:\n|$)', user_prompt)
                        if goal_match:
                            session.goals.append(goal_match.group(1).strip())
            
            # Ошибки - ищем в сообщениях
            message = event.get('message', '')
            
            # Ошибки от LLM
            if 'ERROR' in message and ('LLM' in message or 'llm' in message.lower()):
                session.errors.append({
                    'timestamp': event.get('timestamp'),
                    'message': message,
                    'event_type': event_type,
                    'severity': 'llm_error'
                })
            
            # Executor errors
            if '❌ ERROR' in message:
                session.errors.append({
                    'timestamp': event.get('timestamp'),
                    'message': message,
                    'event_type': event_type,
                    'severity': 'executor_error'
                })
            
            # Status failed
            if 'status=failed' in message or 'status=fail' in message:
                error_match = re.search(r'Error:\s*(.+?)(?:\n|$)', message)
                action_match = re.search(r'Executor\.execute\((\S+)\)', message)
                
                failed_action = AgentAction(
                    timestamp=event.get('timestamp', ''),
                    action=action_match.group(1) if action_match else 'unknown',
                    reasoning='',
                    parameters={},
                    result_status='failed',
                    error=error_match.group(1).strip() if error_match else 'Unknown error'
                )
                session.actions.append(failed_action)
                
                # Добавляем в ошибки
                session.errors.append({
                    'timestamp': event.get('timestamp'),
                    'action': failed_action.action,
                    'error': failed_action.error,
                    'event_type': 'action_failed',
                    'severity': 'action_error'
                })
            
            # Pattern.decide результаты
            if 'Pattern вернул' in message:
                type_match = re.search(r'type=(\w+)', message)
                action_match = re.search(r'action=(\S+)', message)
                reasoning_match = re.search(r'reasoning:\s*(.+?)(?:\.\.\.|$)', message)
                
                if type_match:
                    action_type = type_match.group(1)
                    if action_type == 'act' and action_match:
                        last_action = {
                            'timestamp': event.get('timestamp', ''),
                            'action': action_match.group(1),
                            'reasoning': reasoning_match.group(1) if reasoning_match else '',
                            'result_status': 'pending'
                        }
            
            # Executor результаты (завершение действия)
            if 'Executor завершил' in message:
                status_match = re.search(r'status=(\w+)', message)
                if status_match and last_action:
                    last_action['result_status'] = status_match.group(1)
                    
                    # Проверяем ошибку в сообщении
                    error_match = re.search(r'Error:\s*(.+)', message)
                    if error_match:
                        last_action['error'] = error_match.group(1).strip()
                    
                    # Добавляем в actions если это результат действия
                    if last_action.get('result_status') != 'pending':
                        session.actions.append(AgentAction(
                            timestamp=last_action.get('timestamp', ''),
                            action=last_action.get('action', ''),
                            reasoning=last_action.get('reasoning', ''),
                            parameters={},
                            result_status=last_action.get('result_status', ''),
                            error=last_action.get('error')
                        ))
                        last_action = None
        
        return session
    
    def get_failed_llm_calls(self, session: ParsedSession) -> List[LLMCall]:
        """Получить неуспешные LLM вызовы"""
        return [c for c in session.llm_calls if not c.success]
    
    def get_actions_with_errors(self, session: ParsedSession) -> List[AgentAction]:
        """Получить действия с ошибками"""
        return [a for a in session.actions if a.error]
    
    def extract_llm_reasoning_patterns(self, session: ParsedSession) -> Dict[str, int]:
        """Извлечь паттерны рассуждений LLM"""
        patterns = {}
        for call in session.llm_calls:
            # Ищем ключевые фразы в ответе
            response = call.response.lower()
            
            if 'execute_script' in response:
                patterns['uses_execute_script'] = patterns.get('uses_execute_script', 0) + 1
            if 'search_books' in response:
                patterns['uses_search_books'] = patterns.get('uses_search_books', 0) + 1
            if 'final_answer' in response:
                patterns['uses_final_answer'] = patterns.get('uses_final_answer', 0) + 1
            
            # Ищем проблемы
            if 'одно и то же действие' in response or 'повторя' in response:
                patterns['loops'] = patterns.get('loops', 0) + 1
            
            if 'данные уже получены' in response:
                patterns['data_already_received'] = patterns.get('data_already_received', 0) + 1
        
        return patterns
    
    def generate_analysis_report(self, session: ParsedSession) -> Dict[str, Any]:
        """Генерация отчёта анализа сессии"""
        failed_calls = self.get_failed_llm_calls(session)
        failed_actions = self.get_actions_with_errors(session)
        patterns = self.extract_llm_reasoning_patterns(session)
        
        return {
            'summary': {
                'total_llm_calls': len(session.llm_calls),
                'failed_llm_calls': len(failed_calls),
                'total_actions': len(session.actions),
                'actions_with_errors': len(failed_actions),
                'duration_seconds': self._calc_duration(session),
            },
            'goals': list(set(session.goals)),
            'patterns': patterns,
            'failed_calls': [
                {
                    'call_id': c.call_id,
                    'timestamp': c.timestamp,
                    'error': c.error,
                    'duration_ms': c.duration_ms
                }
                for c in failed_calls
            ],
            'failed_actions': [
                {
                    'action': a.action,
                    'timestamp': a.timestamp,
                    'error': a.error,
                    'reasoning': a.reasoning
                }
                for a in failed_actions
            ],
            'recommendations': self._generate_recommendations(session, patterns, failed_calls, failed_actions)
        }
    
    def _calc_duration(self, session: ParsedSession) -> Optional[float]:
        """Вычислить длительность сессии в секундах"""
        if session.start_time and session.end_time:
            try:
                start = datetime.fromisoformat(session.start_time)
                end = datetime.fromisoformat(session.end_time)
                return (end - start).total_seconds()
            except:
                return None
        return None
    
    def _generate_recommendations(
        self, 
        session: ParsedSession, 
        patterns: Dict[str, int],
        failed_calls: List[LLMCall],
        failed_actions: List[AgentAction]
    ) -> List[str]:
        """Генерация рекомендаций по улучшению"""
        recommendations = []
        
        # Анализ паттернов
        if patterns.get('loops', 0) > 0:
            recommendations.append(
                "Агент зацикливается: добавить правило в промпт для избежания повторения действий"
            )
        
        if patterns.get('uses_execute_script', 0) > patterns.get('uses_search_books', 0):
            recommendations.append(
                "Агент предпочитает execute_script вместо search_books: "
                "обновить промпт с примерами когда использовать search_books"
            )
        
        # Анализ ошибок
        for action in failed_actions:
            if 'Input validation failed' in action.error:
                recommendations.append(
                    f"Ошибка валидации для '{action.action}': "
                    f"проверить обязательные параметры скрипта"
                )
        
        # Анализ неуспешных LLM вызовов
        for call in failed_calls:
            if 'timeout' in str(call.error).lower():
                recommendations.append(
                    f"LLM timeout ({call.duration_ms:.0f}ms): "
                    f"увеличить таймаут или оптимизировать промпт"
                )
        
        if not recommendations:
            recommendations.append("Сессия прошла без критических ошибок")
        
        return recommendations


def parse_session_log(log_path: str) -> Dict[str, Any]:
    """Удобная функция для парсинга лога сессии"""
    parser = SessionLogParser()
    session = parser.parse_file(Path(log_path))
    return parser.generate_analysis_report(session)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        log_path = sys.argv[1]
    else:
        log_path = 'data/logs/sessions/2026-03-31_13-48-42/session.jsonl'
    
    report = parse_session_log(log_path)
    print(json.dumps(report, indent=2, ensure_ascii=False))

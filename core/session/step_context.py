"""
Контекст шага выполнения - хранение данных для каждого шага агента.

СОДЕРЖИТ:
- StepContext: Класс для хранения контекста выполнения шага
- StepData: Модель данных для шага
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional


class StepData:
    """Модель данных для одного шага выполнения."""
    
    def __init__(self, step_number: int, action: str, result: Any = None, timestamp: str = None):
        self.step_number = step_number
        self.action = action
        self.result = result
        self.timestamp = timestamp or datetime.now().isoformat()


class StepContext:
    """Контекст выполнения шагов агента."""
    
    def __init__(self):
        self.steps: List[StepData] = []
        self.metadata: Dict[str, Any] = {}
    
    def add_step(self, step_data: Dict[str, Any]):
        """Добавление шага в контекст."""
        step_number = step_data.get('step', len(self.steps))
        action = step_data.get('action', 'unknown')
        result = step_data.get('result')
        timestamp = step_data.get('timestamp', datetime.now().isoformat())
        
        step = StepData(
            step_number=step_number,
            action=action,
            result=result,
            timestamp=timestamp
        )
        self.steps.append(step)
    
    def get_step(self, step_number: int) -> Optional[StepData]:
        """Получение шага по номеру."""
        for step in self.steps:
            if step.step_number == step_number:
                return step
        return None
    
    def get_all_steps(self) -> List[StepData]:
        """Получение всех шагов."""
        return self.steps[:]
    
    def clear(self):
        """Очистка контекста шагов."""
        self.steps.clear()
        self.metadata.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для сериализации."""
        return {
            'steps': [
                {
                    'step_number': step.step_number,
                    'action': step.action,
                    'result': step.result,
                    'timestamp': step.timestamp
                }
                for step in self.steps
            ],
            'metadata': self.metadata
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """Загрузка из словаря."""
        self.steps.clear()
        self.metadata = data.get('metadata', {})
        
        for step_data in data.get('steps', []):
            step = StepData(
                step_number=step_data['step_number'],
                action=step_data['action'],
                result=step_data.get('result'),
                timestamp=step_data.get('timestamp')
            )
            self.steps.append(step)
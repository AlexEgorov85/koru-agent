#!/usr/bin/env python3
"""
Скрипт для замены ActionResult на ExecutionResult в action_executor.py
"""
import re

filepath = 'core/application/agent/components/action_executor.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Удаляем импорт TypeVar, Generic
content = re.sub(
    r'from typing import Dict, Any, Optional, TYPE_CHECKING, Generic, TypeVar',
    'from typing import Dict, Any, Optional, TYPE_CHECKING',
    content
)

# 2. Удаляем определение T = TypeVar('T')
content = re.sub(
    r"\n# Generic тип для типизированных данных в ActionResult\nT = TypeVar\('T'\)\n",
    '\n',
    content
)

# 3. Удаляем весь класс ActionResult (от class ActionResult до class ExecutionContext)
content = re.sub(
    r'\nclass ActionResult\(Generic\[T\]\):.*?class ExecutionContext:',
    '\n\nclass ExecutionContext:',
    content,
    flags=re.DOTALL
)

# 4. Заменяем -> ActionResult: на -> ExecutionResult:
content = re.sub(r'-> ActionResult:', '-> ExecutionResult:', content)

# 5. Заменяем ActionResult( на ExecutionResult(
content = re.sub(r'ActionResult\(', 'ExecutionResult(', content)

# 6. Заменяем success=False на status=ExecutionStatus.FAILED
content = re.sub(r'success=False,', 'status=ExecutionStatus.FAILED,', content)

# 7. Заменяем success=True на status=ExecutionStatus.COMPLETED
content = re.sub(r'success=True,', 'status=ExecutionStatus.COMPLETED,', content)

# 8. Добавляем ExecutionStatus в импорт
content = re.sub(
    r'from core.models.data.execution import ExecutionResult',
    'from core.models.data.execution import ExecutionResult, ExecutionStatus',
    content
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Done!")
print("   - ActionResult class removed")
print("   - All calls replaced with ExecutionResult")
print("   - success=True/False -> status=ExecutionStatus.COMPLETED/FAILED")

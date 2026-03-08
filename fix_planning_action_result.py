#!/usr/bin/env python3
"""
Script to replace ActionResult with ExecutionResult in planning/skill.py
"""
import re

filepath = 'core/application/skills/planning/skill.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix import
content = re.sub(
    r'from core.application.agent.components.action_executor import ExecutionContext, ActionResult',
    'from core.application.agent.components.action_executor import ExecutionContext\nfrom core.models.data.execution import ExecutionResult, ExecutionStatus',
    content
)

# 2. Replace -> ActionResult: with -> ExecutionResult:
content = re.sub(r'-> ActionResult:', '-> ExecutionResult:', content)

# 3. Replace ActionResult( with ExecutionResult(
content = re.sub(r'ActionResult\(', 'ExecutionResult(', content)

# 4. Replace success=False with status=ExecutionStatus.FAILED
content = re.sub(r'success=False,', 'status=ExecutionStatus.FAILED,', content)

# 5. Replace success=True with status=ExecutionStatus.COMPLETED
content = re.sub(r'success=True,', 'status=ExecutionStatus.COMPLETED,', content)

# 6. Replace isinstance(result, ActionResult) with isinstance(result, ExecutionResult)
content = re.sub(r'isinstance\(result, ActionResult\)', 'isinstance(result, ExecutionResult)', content)

# 7. Replace result.success with result.status == ExecutionStatus.COMPLETED
content = re.sub(r'result\.success', 'result.status == ExecutionStatus.COMPLETED', content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Done!")
print("   - Import fixed")
print("   - All ActionResult replaced with ExecutionResult")
print("   - success=True/False -> status=ExecutionStatus.COMPLETED/FAILED")

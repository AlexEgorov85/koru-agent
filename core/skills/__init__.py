"""
Skills module - содержит реализацию навыков агента.
"""

from .base_skill import BaseSkill
from .planning.skill import PlanningSkill

__all__ = [
    'BaseSkill',
    'PlanningSkill'
]
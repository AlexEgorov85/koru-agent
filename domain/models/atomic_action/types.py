"""
Типы атомарных действий
"""
from enum import Enum


class AtomicActionType(str, Enum):
    """
    Типы атомарных действий
    """
    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"
    PLAN = "plan"
    REFLECT = "reflect"
    EVALUATE = "evaluate"
    VERIFY = "verify"
    ADAPT = "adapt"
    FILE_OPERATION = "file_operation"
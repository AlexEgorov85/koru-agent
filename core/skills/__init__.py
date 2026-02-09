"""
Skills module - содержит реализацию навыков агента.
"""

from .base_skill import BaseSkill
from .book_library.skill import BookLibrarySkill

__all__ = [
    'BaseSkill',
    'BookLibrarySkill'
]
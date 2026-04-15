"""
Text Analysis Skill — анализ текста с LLM и MapReduce.

Поддерживает:
- Анализ текста любого размера
- MapReduce для параллельной обработки
- Автоматическое объединение результатов
"""

from core.components.skills.text_analysis.skill import TextAnalysisSkill

__all__ = ["TextAnalysisSkill"]

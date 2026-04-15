"""
Data Analysis Skill — анализ данных с LLM и MapReduce.

Поддерживает:
- Анализ текста любого размера
- Анализ строк (List[Dict])
- MapReduce для параллельной обработки
- Автоматическое сохранение результатов в контекст
"""

from core.components.skills.data_analysis.skill import DataAnalysisSkill

__all__ = ["DataAnalysisSkill"]

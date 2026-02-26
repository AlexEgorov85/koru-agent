"""
Data Analysis Skill - анализ сырых данных по шагу.

Поддерживает:
- Загрузку данных из файлов, БД и памяти
- Автоматический чанкинг для больших данных
- 4 стратегии агрегации: summary, statistical, extractive, generative
- Валидацию через контракты
"""

from core.application.skills.data_analysis.skill import DataAnalysisSkill

__all__ = ["DataAnalysisSkill"]

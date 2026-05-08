"""
Data Analysis Skill — анализ данных со стратегиями.

Архитектура:
- skill.py — оркестратор (выбор стратегии, сохранение результата)
- base_strategy.py — контракт стратегии (AbstractStrategy)
- strategies/ — реализации: PythonStrategy, LLMStrategy, MapReduceStrategy
- prompts.py — чистые функции рендеринга промптов
"""
from core.components.skills.data_analysis.skill import DataAnalysisSkill

__all__ = ["DataAnalysisSkill"]

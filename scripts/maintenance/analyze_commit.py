#!/usr/bin/env python3
"""
Анализирует коммит и определяет:
1. Какие версии нужно изменить
2. На какой уровень (major/minor/patch)
3. Какие зависимости нужно проверить
"""

import sys
import yaml
from pathlib import Path
from typing import Dict, List, Tuple
import re


class CommitAnalyzer:
    def __init__(self, rules_path: Path = Path("versioning/rules.yaml")):
        self.rules = yaml.safe_load(rules_path.read_text(encoding='utf-8'))
    
    def analyze_changed_files(self, changed_files: List[str]) -> Dict:
        """Определяет типы изменений по списку файлов"""
        changes = {
            "code": {"files": [], "impact": "none"},
            "prompts": {"files": [], "impact": "none"},
            "contracts": {"files": [], "impact": "none"},
            "config": {"files": [], "impact": "none"}
        }
        
        for file_path in changed_files:
            # Классификация файла
            if "core/skills" in file_path or "core/agent_runtime" in file_path:
                changes["code"]["files"].append(file_path)
            elif "prompts/" in file_path:
                changes["prompts"]["files"].append(file_path)
            elif "contracts/" in file_path:
                changes["contracts"]["files"].append(file_path)
            elif file_path.endswith((".yaml", ".toml")) and "config" in file_path:
                changes["config"]["files"].append(file_path)
        
        # Определение уровня воздействия
        for change_type, data in changes.items():
            if data["files"]:
                impact = self._determine_impact_level(change_type, data["files"])
                data["impact"] = impact
        
        return changes
    
    def _determine_impact_level(self, change_type: str, files: List[str]) -> str:
        """Определяет уровень воздействия (major/minor/patch)"""
        # Для промптов анализируем содержимое на семантические триггеры
        if change_type == "prompts":
            content = ""
            for f in files:
                if Path(f).exists():
                    try:
                        content += Path(f).read_text(encoding='utf-8')
                    except UnicodeDecodeError:
                        # Если не удается прочитать как UTF-8, пробуем с игнорированием ошибок
                        content += Path(f).read_text(encoding='utf-8', errors='ignore')
            
            if any(trigger in content.lower() for trigger in self.rules["semantic_triggers"]["breaking_changes"]):
                return "major"
            elif any(trigger in content.lower() for trigger in self.rules["semantic_triggers"]["new_features"]):
                return "minor"
            else:
                return "patch"
        
        # Для контрактов также анализируем содержимое
        if change_type == "contracts":
            content = ""
            for f in files:
                if Path(f).exists():
                    try:
                        content += Path(f).read_text(encoding='utf-8')
                    except UnicodeDecodeError:
                        content += Path(f).read_text(encoding='utf-8', errors='ignore')
            
            if any(trigger in content.lower() for trigger in self.rules["semantic_triggers"]["breaking_changes"]):
                return "major"
            elif any(trigger in content.lower() for trigger in self.rules["semantic_triggers"]["new_features"]):
                return "minor"
            else:
                return "patch"
        
        # Для кода — по пути файла
        if any("agent_runtime" in f for f in files):
            return "major"  # Изменения в ядре = major
        elif any("skills" in f for f in files):
            return "minor"  # Навыки = minor
        
        return "patch"
    
    def suggest_version_bumps(self, changes: Dict) -> Dict:
        """Генерирует рекомендации по инкременту версий"""
        suggestions = {}
        
        # Кодовая база
        if changes["code"]["impact"] != "none":
            suggestions["code_version"] = changes["code"]["impact"]
        
        # Промпты (по каждому компоненту)
        for prompt_file in changes["prompts"]["files"]:
            component = self._extract_component_from_path(prompt_file)
            if component:
                suggestions.setdefault("prompt_versions", {})[component] = changes["prompts"]["impact"]
        
        # Контракты
        for contract_file in changes["contracts"]["files"]:
            component = self._extract_component_from_path(contract_file)
            if component:
                suggestions.setdefault("contract_versions", {})[component] = changes["contracts"]["impact"]
        
        return suggestions
    
    def _extract_component_from_path(self, file_path: str) -> str:
        """Извлекает имя компонента из пути (например, 'planning' из 'prompts/skills/planning/...')"""
        parts = Path(file_path).parts
        try:
            skills_idx = -1
            for i, part in enumerate(parts):
                if part == "skills":
                    skills_idx = i
                    break
            if skills_idx != -1 and skills_idx + 1 < len(parts):
                return parts[skills_idx + 1]
        except ValueError:
            pass
        return None


if __name__ == "__main__":
    # Использование агентом:
    #   python scripts/versioning/analyze_commit.py file1.py file2.yaml ...
    changed_files = sys.argv[1:]
    
    if not changed_files:
        print("ERROR: No files provided to analyze")
        sys.exit(1)
    
    analyzer = CommitAnalyzer()
    changes = analyzer.analyze_changed_files(changed_files)
    suggestions = analyzer.suggest_version_bumps(changes)
    
    # Вывод в формате для агента
    import json
    result = {
        "changes_detected": changes,
        "version_bump_suggestions": suggestions,
        "requires_validation": bool(suggestions)
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
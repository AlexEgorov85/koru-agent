#!/usr/bin/env python3
"""
Применяет рекомендованные изменения версий:
1. Инкрементирует версии в манифесте
2. Обновляет метаданные промптов/контрактов
3. Создаёт записи в CHANGELOG
"""

import sys
import yaml
import json
from pathlib import Path
from datetime import datetime, timezone
from packaging import version as pkg_version


def bump_major(version: str) -> str:
    """Инкрементирует major версию"""
    # Убираем 'v' префикс если есть
    clean_version = version.lstrip('v')
    ver = pkg_version.parse(clean_version)
    return f"{ver.major + 1}.0.0"


def bump_minor(version: str) -> str:
    """Инкрементирует minor версию"""
    # Убираем 'v' префикс если есть
    clean_version = version.lstrip('v')
    ver = pkg_version.parse(clean_version)
    return f"{ver.major}.{ver.minor + 1}.0"


def bump_patch(version: str) -> str:
    """Инкрементирует patch версию"""
    # Убираем 'v' префикс если есть
    clean_version = version.lstrip('v')
    ver = pkg_version.parse(clean_version)
    return f"{ver.major}.{ver.minor}.{ver.micro + 1}"


class VersionApplier:
    def __init__(self, manifest_path: Path = Path("versioning/manifest.yaml")):
        self.manifest_path = manifest_path
        self.manifest = yaml.safe_load(manifest_path.read_text(encoding='utf-8'))
    
    def apply_bumps(self, suggestions: Dict, commit_message: str, author: str):
        """Применяет инкременты версий"""
        # 1. Инкремент глобальной версии кода
        if "code_version" in suggestions:
            old_ver = self.manifest["code_version"]
            new_ver = self._bump_version(old_ver, suggestions["code_version"])
            self.manifest["code_version"] = new_ver
            print(f"[OK] Кодовая версия: {old_ver} -> {new_ver}")
        
        # 2. Инкремент версий промптов по компонентам
        if "prompt_versions" in suggestions:
            for component, level in suggestions["prompt_versions"].items():
                if component in self.manifest["components"]:
                    caps = self.manifest["components"][component]["prompt_versions"]
                    for cap_name, old_ver in caps.items():
                        new_ver = self._bump_semver(old_ver, level)
                        caps[cap_name] = new_ver
                        # Обновляем сам файл промпта
                        self._update_prompt_metadata(cap_name, new_ver, commit_message, author)
                        print(f"[OK] Промпт {cap_name}: {old_ver} -> {new_ver}")
        
        # 3. Инкремент версий контрактов
        if "contract_versions" in suggestions:
            for component, level in suggestions["contract_versions"].items():
                if component in self.manifest["components"]:
                    caps = self.manifest["components"][component]["contract_versions"]
                    for cap_name, old_ver in caps.items():
                        new_ver = self._bump_semver(old_ver, level)
                        caps[cap_name] = new_ver
                        # Обновляем файл контракта
                        self._update_contract_metadata(cap_name, new_ver, commit_message, author)
                        print(f"[OK] Контракт {cap_name}: {old_ver} -> {new_ver}")
        
        # 4. Обновляем манифест
        self.manifest["build_id"] = f"{datetime.now().strftime('%Y.%m.%d')}-{self._next_build_number()}"
        self.manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Сохраняем
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.manifest, f, allow_unicode=True, sort_keys=False)
        
        # 5. Добавляем запись в CHANGELOG
        self._append_changelog(commit_message, suggestions, author)
    
    def _bump_version(self, version: str, level: str) -> str:
        """Инкремент версии по semver"""
        if level == "major":
            return bump_major(version)
        elif level == "minor":
            return bump_minor(version)
        else:
            return bump_patch(version)
    
    def _bump_semver(self, version: str, level: str) -> str:
        """Инкремент семантической версии (с 'v' префиксом)"""
        if version.startswith('v'):
            base = version[1:]
            bumped = self._bump_version(base, level)
            return f"v{bumped}"
        return self._bump_version(version, level)
    
    def _update_prompt_metadata(self, capability: str, new_version: str, message: str, author: str):
        """Обновляет метаданные промпта в YAML файле"""
        # Находим файл промпта по capability
        prompt_file = self._find_prompt_file(capability)
        if not prompt_file or not prompt_file.exists():
            print(f"! Файл промпта не найден для {capability}")
            return
        
        try:
            data = yaml.safe_load(prompt_file.read_text(encoding='utf-8'))
        except:
            print(f"! Не удалось прочитать файл промпта {prompt_file}")
            return
        
        old_ver = data.get('version', 'v1.0.0')
        
        # Обновляем метаданные
        data['version'] = new_version
        data['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        # Добавляем или создаем changelog
        if 'changelog' not in data:
            data['changelog'] = []
        
        data['changelog'].append({
            'version': new_version,
            'date': datetime.now(timezone.utc).isoformat(),
            'author': author,
            'message': message,
            'previous_version': old_ver
        })
        
        with open(prompt_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    
    def _find_prompt_file(self, capability: str) -> Path:
        """Находит файл промпта по имени capability"""
        # Простая реализация — можно улучшить поиском
        parts = capability.split('.')
        if len(parts) >= 2:
            skill_name = parts[0]
            prompt_name = parts[1]
            pattern = f"prompts/skills/{skill_name}/*{prompt_name}*.yaml"
            matches = list(Path('.').glob(pattern))
            return matches[0] if matches else None
        return None
    
    def _update_contract_metadata(self, capability: str, new_version: str, message: str, author: str):
        """Обновляет метаданные контракта в YAML файле"""
        # Находим файл контракта по capability
        contract_file = self._find_contract_file(capability)
        if not contract_file or not contract_file.exists():
            print(f"! Файл контракта не найден для {capability}")
            return
        
        try:
            data = yaml.safe_load(contract_file.read_text(encoding='utf-8'))
        except:
            print(f"! Не удалось прочитать файл контракта {contract_file}")
            return
        
        old_ver = data.get('version', 'v1.0.0')
        
        # Обновляем метаданные
        data['version'] = new_version
        data['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        # Добавляем или создаем changelog
        if 'changelog' not in data:
            data['changelog'] = []
        
        data['changelog'].append({
            'version': new_version,
            'date': datetime.now(timezone.utc).isoformat(),
            'author': author,
            'message': message,
            'previous_version': old_ver
        })
        
        with open(contract_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    
    def _find_contract_file(self, capability: str) -> Path:
        """Находит файл контракта по имени capability"""
        # Простая реализация — ищем по имени capability
        parts = capability.split('.')
        if len(parts) >= 2:
            skill_name = parts[0]
            capability_name = parts[1]
            # Ищем файлы контрактов
            pattern = f"contracts/skills/{skill_name}/*{capability_name}*.yaml"
            matches = list(Path('.').glob(pattern))
            if not matches:
                # Если не нашли в подкаталоге навыка, ищем в общем каталоге
                pattern = f"contracts/*{capability_name}*.yaml"
                matches = list(Path('.').glob(pattern))
            return matches[0] if matches else None
        return None
    
    def _append_changelog(self, message: str, suggestions: Dict, author: str):
        """Добавляет запись в CHANGELOG.md"""
        changelog_path = Path("CHANGELOG.md")
        if not changelog_path.exists():
            changelog_path.write_text("# CHANGELOG\n\n", encoding='utf-8')
        
        entry = f"""
## [{self.manifest['code_version']}] - {datetime.now().strftime('%Y-%m-%d')}

### Изменения

"""
        # Добавляем типы изменений
        if "code_version" in suggestions:
            entry += f"- **Ядро**: {message}\n"
        if "prompt_versions" in suggestions:
            comps = ", ".join(suggestions["prompt_versions"].keys())
            entry += f"- **Промпты** ({comps}): {message}\n"
        if "contract_versions" in suggestions:
            comps = ", ".join(suggestions["contract_versions"].keys())
            entry += f"- **Контракты** ({comps}): {message}\n"
        
        entry += f"\nАвтор: @{author}\n\n---\n"
        
        # Вставляем в начало CHANGELOG (после заголовка)
        content = changelog_path.read_text(encoding='utf-8')
        content = content.replace("# CHANGELOG\n\n", f"# CHANGELOG\n\n{entry}", 1)
        changelog_path.write_text(content, encoding='utf-8')
    
    def _next_build_number(self) -> str:
        """Генерирует следующий номер сборки"""
        # Простая реализация - увеличиваем на 1 последний номер в build_id
        build_id = self.manifest.get("build_id", "2026.02.11-001")
        if '-' in build_id:
            prefix, num = build_id.rsplit('-', 1)
            try:
                next_num = int(num) + 1
                return f"{prefix}-{next_num:03d}"
            except ValueError:
                pass
        return f"{build_id}-001"


if __name__ == "__main__":
    # Использование агентом:
    #   python scripts/versioning/apply_version.py '{"code_version": "minor", ...}' "Добавлена поддержка..." "alexey"
    if len(sys.argv) < 3:
        print("ERROR: Usage: apply_version.py <suggestions_json> <commit_message> [author]")
        sys.exit(1)
    
    suggestions_json = sys.argv[1]
    commit_message = sys.argv[2]
    author = sys.argv[3] if len(sys.argv) > 3 else "unknown"
    
    try:
        suggestions = json.loads(suggestions_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        sys.exit(1)
    
    applier = VersionApplier()
    applier.apply_bumps(suggestions, commit_message, author)
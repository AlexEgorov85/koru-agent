# Руководство по миграции Composable AI Agent Framework

Это руководство описывает процесс миграции Composable AI Agent Framework между версиями и адаптацию существующих компонентов к новым архитектурным изменениям. Вы узнаете, как безопасно обновлять фреймворк и адаптировать свои компоненты под новые версии.

## Общие принципы миграции

### 1. Подход к миграции

При миграции фреймворка следует использовать постепенный подход:

1. **Оценка изменений**: Определите, какие компоненты затронуты обновлением
2. **Тестирование**: Протестируйте изменения в изолированной среде
3. **Постепенное обновление**: Обновляйте компоненты по одному
4. **Валидация**: Проверьте корректность работы после обновления
5. **Резервное копирование**: Создайте резервные копии перед обновлением

### 2. Уровни совместимости

Фреймворк следует семантическому версионированию:

- **PATCH-обновления** (1.0.x): Обратно совместимы, не должны нарушать работу
- **MINOR-обновления** (1.x.0): Добавляют новую функциональность с сохранением совместимости
- **MAJOR-обновления** (x.0.0): Могут содержать изменения, нарушающие совместимость

## План миграции

### 1. Подготовка к миграции

Перед началом миграции выполните следующие шаги:

```bash
# 1. Создайте резервную копию текущего состояния
git checkout -b migration-backup-$(date +%Y%m%d-%H%M%S)

# 2. Зафиксируйте все изменения
git add .
git commit -m "Backup before framework migration"

# 3. Создайте резервную копию конфигурации
cp config.yaml config.yaml.backup.$(date +%Y%m%d-%H%M%S)
```

### 2. Проверка совместимости

Проверьте, какие компоненты могут быть затронуты обновлением:

```python
# migration/compatibility_checker.py
import re
from typing import List, Dict, Any
from pathlib import Path

class CompatibilityChecker:
    """Проверяет совместимость кода с новой версией фреймворка"""
    
    def __init__(self, current_version: str, target_version: str):
        self.current_version = current_version
        self.target_version = target_version
        self.changes_log = []
        self.compatibility_issues = []
    
    def check_compatibility(self, project_path: str = ".") -> Dict[str, Any]:
        """Проверить совместимость проекта с новой версией"""
        
        project_dir = Path(project_path)
        
        # Проверить импорты
        self._check_imports(project_dir)
        
        # Проверить использование устаревших API
        self._check_deprecated_api_usage(project_dir)
        
        # Проверить структуру файлов
        self._check_file_structure(project_dir)
        
        # Проверить конфигурацию
        self._check_config_files(project_dir)
        
        return {
            "compatible": len(self.compatibility_issues) == 0,
            "issues_found": len(self.compatibility_issues),
            "issues": self.compatibility_issues,
            "changes_log": self.changes_log
        }
    
    def _check_imports(self, project_dir: Path):
        """Проверить импорты на устаревшие пути"""
        deprecated_imports = {
            "0.9_to_1.0": [
                ("domain.abstractions.old_pattern", "domain.abstractions.thinking_pattern"),
                ("application.services.old_loader", "application.services.prompt_loader"),
                ("infrastructure.tools.old_tool", "infrastructure.tools.file_reader_tool")
            ]
        }
        
        changes = deprecated_imports.get(f"{self.current_version}_to_{self.target_version}", [])
        
        for old_import, new_import in changes:
            for py_file in project_dir.rglob("*.py"):
                content = py_file.read_text()
                
                if old_import in content:
                    self.compatibility_issues.append({
                        "type": "deprecated_import",
                        "file": str(py_file),
                        "old_import": old_import,
                        "new_import": new_import,
                        "severity": "high"
                    })
    
    def _check_deprecated_api_usage(self, project_dir: Path):
        """Проверить использование устаревших API"""
        deprecated_methods = {
            "0.9_to_1.0": [
                "old_method_name",
                "another_deprecated_method"
            ]
        }
        
        methods = deprecated_methods.get(f"{self.current_version}_to_{self.target_version}", [])
        
        for method in methods:
            for py_file in project_dir.rglob("*.py"):
                content = py_file.read_text()
                
                if re.search(rf"\b{method}\b", content):
                    self.compatibility_issues.append({
                        "type": "deprecated_api",
                        "file": str(py_file),
                        "method": method,
                        "severity": "medium"
                    })
    
    def _check_file_structure(self, project_dir: Path):
        """Проверить структуру файлов на совместимость"""
        # Проверить, что директории промтов соответствуют новой структуре
        prompts_dir = project_dir / "prompts"
        if prompts_dir.exists():
            # В новой версии структура: prompts/{domain}/{capability}/{role}/v{version}.md
            for domain_dir in prompts_dir.iterdir():
                if domain_dir.is_dir():
                    for capability_dir in domain_dir.iterdir():
                        if capability_dir.is_dir():
                            # Проверить, есть ли подкаталоги ролей
                            role_dirs = [
                                subdir for subdir in capability_dir.iterdir()
                                if subdir.is_dir() and subdir.name in ["system", "user", "assistant", "tool"]
                            ]
                            
                            if not role_dirs:
                                # Старая структура - потребуется миграция
                                self.compatibility_issues.append({
                                    "type": "file_structure",
                                    "file": str(capability_dir),
                                    "issue": "Требуется миграция структуры промтов",
                                    "severity": "medium"
                                })
    
    def _check_config_files(self, project_dir: Path):
        """Проверить файлы конфигурации на совместимость"""
        config_files = list(project_dir.rglob("*.yaml")) + list(project_dir.rglob("*.yml"))
        
        deprecated_config_keys = {
            "0.9_to_1.0": [
                "old_config_key",
                "another_deprecated_key"
            ]
        }
        
        keys = deprecated_config_keys.get(f"{self.current_version}_to_{self.target_version}", [])
        
        for config_file in config_files:
            content = config_file.read_text()
            
            for key in keys:
                if re.search(rf"^\s*{key}:", content, re.MULTILINE):
                    self.compatibility_issues.append({
                        "type": "deprecated_config",
                        "file": str(config_file),
                        "key": key,
                        "severity": "high"
                    })

# Пример использования
async def check_compatibility():
    checker = CompatibilityChecker("0.9", "1.0")
    compatibility_report = checker.check_compatibility("./")
    
    if not compatibility_report["compatible"]:
        print(f"Найдено {compatibility_report['issues_found']} проблем совместимости:")
        for issue in compatibility_report["issues"]:
            print(f"- {issue['type']}: {issue['file']} - {issue['severity']}")
    else:
        print("Проект совместим с новой версией фреймворка")
    
    return compatibility_report
```

## Миграция компонентов

### 1. Миграция агентов

При обновлении интерфейса агентов:

#### Старая версия:

```python
# Старый интерфейс агента
class OldAgentInterface:
    async def execute_task(self, task_description: str) -> Dict[str, Any]:
        pass
    
    def get_state(self) -> Dict[str, Any]:
        pass
```

#### Новая версия:

```python
# Новый интерфейс агента
class NewAgentInterface:
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        pass
    
    def get_state(self) -> AgentState:
        pass
    
    async def adapt_to_domain(self, domain_type: DomainType, capabilities: List[str]):
        pass
```

#### Адаптер миграции:

```python
# migration/agent_migration_adapter.py
from typing import Dict, Any, List
from domain.value_objects.domain_type import DomainType

class AgentMigrationAdapter:
    """Адаптер для миграции агентов между версиями"""
    
    def __init__(self, old_agent):
        self.old_agent = old_agent
        self.wrapped_methods = ["execute_task", "get_state"]
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Адаптировать вызов к новому интерфейсу"""
        if context:
            # Если контекст предоставлен, использовать его
            # В старой версии контекст не поддерживался, поэтому игнорируем
            pass
        
        # Вызвать старую реализацию
        result = await self.old_agent.execute_task(task_description)
        
        # Адаптировать результат к новому формату
        if isinstance(result, str):
            return {"success": True, "result": result}
        elif isinstance(result, dict):
            return result
        else:
            return {"success": True, "result": str(result)}
    
    def get_state(self) -> AgentState:
        """Адаптировать получение состояния"""
        old_state = self.old_agent.get_state()
        
        # Преобразовать старое состояние в новое
        if isinstance(old_state, dict):
            from domain.models.agent.agent_state import AgentState
            return AgentState(
                step=old_state.get("step", 0),
                error_count=old_state.get("error_count", 0),
                no_progress_steps=old_state.get("no_progress_steps", 0),
                finished=old_state.get("finished", False),
                metrics=old_state.get("metrics", {}),
                history=old_state.get("history", []),
                current_plan_step=old_state.get("current_plan_step")
            )
        else:
            # Если старое состояние не в формате словаря, создать новое
            return AgentState()
    
    async def adapt_to_domain(self, domain_type: DomainType, capabilities: List[str]):
        """Новый метод - просто заглушка для совместимости"""
        # В старой версии доменная адаптация не поддерживалась
        pass

# Функция миграции агентов
async def migrate_agent(agent_class, new_config: Dict[str, Any]) -> IAgent:
    """Мигрировать агента к новой версии"""
    
    if hasattr(agent_class, 'supports_new_interface'):
        # Если агент уже поддерживает новый интерфейс
        migrated_agent = agent_class(new_config)
    else:
        # Если агент использует старый интерфейс, обернуть адаптером
        old_agent = agent_class(new_config)
        migrated_agent = AgentMigrationAdapter(old_agent)
    
    return migrated_agent
```

### 2. Миграция паттернов мышления

При изменении интерфейса паттернов:

```python
# migration/pattern_migration_adapter.py
from typing import Any, Dict, List
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState

class PatternMigrationAdapter(IThinkingPattern):
    """Адаптер для миграции паттернов между версиями"""
    
    def __init__(self, old_pattern, new_config: Dict[str, Any] = None):
        self.old_pattern = old_pattern
        self.config = new_config or {}
        self.name = getattr(old_pattern, 'name', 'migrated_pattern')
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Адаптировать выполнение к новому интерфейсу"""
        
        # Проверить, есть ли в старом паттерне новый метод
        if hasattr(self.old_pattern, 'execute_new_interface'):
            # Использовать новый метод, если доступен
            return await self.old_pattern.execute_new_interface(state, context, available_capabilities)
        else:
            # Использовать старый метод и адаптировать результат
            old_result = await self.old_pattern.execute(context)
            
            # Адаптировать результат к новому формату
            if isinstance(old_result, dict):
                return {"success": True, **old_result}
            else:
                return {"success": True, "result": str(old_result)}
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать к задаче"""
        if hasattr(self.old_pattern, 'adapt_to_task'):
            old_adaptation = await self.old_pattern.adapt_to_task(task_description)
            
            # Адаптировать результат к новому формфату
            if isinstance(old_adaptation, dict):
                return old_adaptation
            else:
                return {"can_handle": True, "confidence": 0.8}
    
    def can_handle_task(self, task_description: str, context: Any = None) -> bool:
        """Проверить, может ли паттерн обработать задачу"""
        # В старой версии мог не быть этого метода
        if hasattr(self.old_pattern, 'can_handle_task'):
            return self.old_pattern.can_handle_task(task_description, context)
        else:
            # По умолчанию считаем, что может обработать
            return True
```

### 3. Миграция системы промтов

При изменении структуры хранения промтов:

```python
# migration/prompt_migration_service.py
from typing import List, Tuple, Dict, Any
from pathlib import Path
import yaml
import asyncio

class PromptMigrationService:
    """Сервис миграции промтов между версиями"""
    
    def __init__(self, old_base_path: str, new_base_path: str):
        self.old_base_path = Path(old_base_path)
        self.new_base_path = Path(new_base_path)
        self.migration_log = []
    
    async def migrate_prompts(self) -> Tuple[List[str], List[str]]:
        """Мигрировать все промты из старой структуры в новую"""
        
        migrated_prompts = []
        migration_errors = []
        
        # Найти все старые промты
        old_prompts = self._find_old_prompts()
        
        for old_prompt_path in old_prompts:
            try:
                # Загрузить старый промт
                old_prompt_data = await self._load_old_prompt(old_prompt_path)
                
                # Мигрировать структуру
                migrated_prompt = await self._migrate_prompt_structure(old_prompt_data, old_prompt_path)
                
                # Сохранить в новую структуру
                new_path = await self._save_migrated_prompt(migrated_prompt, old_prompt_path)
                
                migrated_prompts.append(str(new_path))
                self.migration_log.append({
                    "status": "success",
                    "old_path": str(old_prompt_path),
                    "new_path": str(new_path),
                    "timestamp": time.time()
                })
                
            except Exception as e:
                error_msg = f"Ошибка миграции промта {old_prompt_path}: {str(e)}"
                migration_errors.append(error_msg)
                self.migration_log.append({
                    "status": "error",
                    "old_path": str(old_prompt_path),
                    "error": error_msg,
                    "timestamp": time.time()
                })
        
        return migrated_prompts, migration_errors
    
    def _find_old_prompts(self) -> List[Path]:
        """Найти все старые промты"""
        old_prompts = []
        
        # Старая структура: prompts/{domain}/{capability}/v{version}.md
        for domain_dir in self.old_base_path.iterdir():
            if not domain_dir.is_dir():
                continue
            
            for capability_dir in domain_dir.iterdir():
                if not capability_dir.is_dir():
                    continue
                
                # Найти файлы версий в capability_dir
                for version_file in capability_dir.glob("v*.md"):
                    old_prompts.append(version_file)
        
        return old_prompts
    
    async def _load_old_prompt(self, prompt_path: Path) -> Dict[str, Any]:
        """Загрузить старый промт"""
        content = prompt_path.read_text(encoding='utf-8')
        
        # Извлечь frontmatter и содержимое
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter_yaml = parts[1]
                prompt_content = parts[2]
                
                metadata = yaml.safe_load(frontmatter_yaml) or {}
                return {
                    "metadata": metadata,
                    "content": prompt_content.strip()
                }
        
        # Если нет frontmatter, создать минимальные метаданные
        return {
            "metadata": {"status": "active"},
            "content": content.strip()
        }
    
    async def _migrate_prompt_structure(self, old_prompt: Dict[str, Any], old_path: Path) -> Dict[str, Any]:
        """Мигрировать структуру промта к новому формату"""
        old_metadata = old_prompt["metadata"]
        old_content = old_prompt["content"]
        
        # Определить домен, капабилити и роль из пути
        path_parts = old_path.parts
        domain = path_parts[path_parts.index("prompts") + 1] if "prompts" in path_parts else "default"
        capability = path_parts[path_parts.index("prompts") + 2] if len(path_parts) > path_parts.index("prompts") + 2 else "default"
        
        # Новая структура требует явной роли
        role = old_metadata.get("role", "system")  # По умолчанию system
        
        # Создать новую структуру метаданных
        new_metadata = {
            **old_metadata,
            "domain": domain,
            "capability": capability,
            "role": role
        }
        
        # Добавить новые поля, если их нет
        if "expected_response" not in new_metadata:
            new_metadata["expected_response"] = {}
        
        if "variables" not in new_metadata:
            new_metadata["variables"] = []
        
        return {
            "metadata": new_metadata,
            "content": old_content
        }
    
    async def _save_migrated_prompt(self, migrated_prompt: Dict[str, Any], old_path: Path) -> Path:
        """Сохранить мигрированный промт в новой структуре"""
        
        # Определить новую структуру пути: prompts/{domain}/{capability}/{role}/v{version}.md
        metadata = migrated_prompt["metadata"]
        domain = metadata.get("domain", "default")
        capability = metadata.get("capability", "default")
        role = metadata.get("role", "system")
        
        # Извлечь версию из имени файла или метаданных
        version = self._extract_version_from_path(old_path) or metadata.get("version", "1.0.0")
        
        new_path = self.new_base_path / domain / capability / role / f"v{version}.md"
        
        # Создать директории при необходимости
        new_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Создать содержимое с новым frontmatter
        yaml_frontmatter = yaml.dump(migrated_prompt["metadata"], default_flow_style=False)
        content = f"---\n{yaml_frontmatter}---\n\n{migrated_prompt['content']}"
        
        # Записать файл
        new_path.write_text(content, encoding='utf-8')
        
        return new_path
    
    def _extract_version_from_path(self, path: Path) -> str:
        """Извлечь версию из имени файла"""
        filename = path.stem  # имя файла без расширения
        # Извлекаем версию из формата v1.0.0
        import re
        version_match = re.search(r'v(\d+\.\d+\.\d+)', filename)
        if version_match:
            return version_match.group(1)
        return "1.0.0"  # версия по умолчанию

# Использование сервиса миграции
async def migrate_prompts_example():
    """Пример миграции промтов"""
    
    migration_service = PromptMigrationService(
        old_base_path="./old_prompts",
        new_base_path="./prompts"
    )
    
    migrated, errors = await migration_service.migrate_prompts()
    
    print(f"Мигрировано промтов: {len(migrated)}")
    print(f"Ошибок: {len(errors)}")
    
    if errors:
        print("Ошибки миграции:")
        for error in errors:
            print(f"- {error}")
    
    return migrated, errors
```

### 4. Миграция конфигурации

При изменении формата конфигурации:

```python
# migration/config_migration_service.py
from typing import Dict, Any
import yaml
import json

class ConfigMigrationService:
    """Сервис миграции конфигурации между версиями"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.backup_path = Path(f"{config_path}.backup.{time.strftime('%Y%m%d_%H%M%S')}")
    
    async def migrate_config(self, from_version: str, to_version: str) -> Dict[str, Any]:
        """Мигрировать конфигурацию с одной версии на другую"""
        
        # Создать резервную копию
        await self._create_backup()
        
        # Загрузить текущую конфигурацию
        current_config = await self._load_current_config()
        
        # Определить цепочку миграций
        migration_chain = self._get_migration_chain(from_version, to_version)
        
        if not migration_chain:
            raise ValueError(f"Невозможно выполнить миграцию с {from_version} на {to_version}")
        
        # Выполнить миграции по цепочке
        migrated_config = current_config
        for migration_step in migration_chain:
            migrated_config = await self._apply_migration_step(migrated_config, migration_step)
        
        # Сохранить мигрированную конфигурацию
        await self._save_config(migrated_config)
        
        return migrated_config
    
    async def _create_backup(self):
        """Создать резервную копию конфигурации"""
        if self.config_path.exists():
            if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                backup_content = self.config_path.read_text()
                self.backup_path.write_text(backup_content)
            elif self.config_path.suffix.lower() == '.json':
                backup_content = self.config_path.read_text()
                self.backup_path.with_suffix('.json').write_text(backup_content)
    
    async def _load_current_config(self) -> Dict[str, Any]:
        """Загрузить текущую конфигурацию"""
        if self.config_path.suffix.lower() in ['.yaml', '.yml']:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file) or {}
        elif self.config_path.suffix.lower() == '.json':
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {self.config_path.suffix}")
    
    def _get_migration_chain(self, from_version: str, to_version: str) -> List[str]:
        """Получить цепочку миграций"""
        # Простая реализация - в реальной системе может быть более сложная логика
        version_map = {
            ("0.9", "1.0"): ["0.9_to_1.0"],
            ("1.0", "1.1"): ["1.0_to_1.1"],
            ("0.9", "1.1"): ["0.9_to_1.0", "1.0_to_1.1"]
        }
        
        return version_map.get((from_version, to_version), [])
    
    async def _apply_migration_step(self, config: Dict[str, Any], step: str) -> Dict[str, Any]:
        """Применить шаг миграции к конфигурации"""
        
        if step == "0.9_to_1.0":
            return self._apply_09_to_10_migration(config)
        elif step == "1.0_to_1.1":
            return self._apply_10_to_11_migration(config)
        
        return config  # Если шаг неизвестен, вернуть без изменений
    
    def _apply_09_to_10_migration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Применить миграцию с версии 0.9 к 1.0"""
        migrated_config = config.copy()
        
        # Переименовать устаревшие поля
        field_mapping = {
            "max_iterations": "agent.max_iterations",
            "timeout_seconds": "agent.timeout",
            "enable_logging": "system.enable_logging",
            "llm_provider": "llm.provider",
            "llm_model": "llm.model"
        }
        
        for old_field, new_field in field_mapping.items():
            if old_field in migrated_config:
                value = migrated_config.pop(old_field)
                
                # Установить значение в новое поле (создавая вложенные структуры при необходимости)
                keys = new_field.split('.')
                current = migrated_config
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                current[keys[-1]] = value
        
        # Добавить новые поля по умолчанию
        if "prompts" not in migrated_config:
            migrated_config["prompts"] = {
                "cache_enabled": True,
                "cache_ttl": 3600,
                "validation_enabled": True
            }
        
        if "system" not in migrated_config:
            migrated_config["system"] = {
                "debug_mode": False,
                "log_level": "INFO",
                "enable_monitoring": True
            }
        
        return migrated_config
    
    def _apply_10_to_11_migration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Применить миграцию с версии 1.0 к 1.1"""
        migrated_config = config.copy()
        
        # Добавить новые возможности
        if "agent" in migrated_config:
            agent_config = migrated_config["agent"]
            if "max_concurrent_actions" not in agent_config:
                agent_config["max_concurrent_actions"] = 5
            if "memory_limit" not in agent_config:
                agent_config["memory_limit"] = "1GB"
        
        # Обновить формат LLM конфигурации
        if "llm" in migrated_config:
            llm_config = migrated_config["llm"]
            if "api_key" not in llm_config and "OPENAI_API_KEY" in os.environ:
                llm_config["api_key"] = "${OPENAI_API_KEY}"
        
        return migrated_config
    
    async def _save_config(self, config: Dict[str, Any]):
        """Сохранить мигрированную конфигурацию"""
        if self.config_path.suffix.lower() in ['.yaml', '.yml']:
            with open(self.config_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
        elif self.config_path.suffix.lower() == '.json':
            with open(self.config_path, 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=2, ensure_ascii=False)
        
        print(f"Конфигурация мигрирована к версии {self.target_version}")

# Пример использования
async def migrate_config_example():
    """Пример миграции конфигурации"""
    
    config_migration = ConfigMigrationService("config.yaml")
    
    # Мигрировать с версии 0.9 к 1.0
    migrated_config = await config_migration.migrate_config("0.9", "1.0")
    
    print(f"Конфигурация успешно мигрирована: {migrated_config}")
    
    return migrated_config
```

## Проверка после миграции

### 1. Тестирование мигрированных компонентов

После миграции обязательно протестируйте систему:

```python
# test_migration_verification.py
import pytest
from unittest.mock import AsyncMock, Mock
from migration.compatibility_checker import CompatibilityChecker

class TestMigrationVerification:
    @pytest.mark.asyncio
    async def test_agent_migration_compatibility(self):
        """Тест совместимости мигрированных агентов"""
        
        # Проверить, что мигрированный агент соответствует новому интерфейсу
        migrated_agent = await migrate_agent(OldAgent, {"test": "config"})
        
        # Проверить, что у агента есть все необходимые методы
        assert hasattr(migrated_agent, 'execute_task')
        assert hasattr(migrated_agent, 'get_state')
        assert hasattr(migrated_agent, 'adapt_to_domain')
        
        # Проверить выполнение задачи
        result = await migrated_agent.execute_task(
            task_description="Тестовая задача",
            context={"test": "data"}
        )
        
        assert "success" in result
    
    @pytest.mark.asyncio
    async def test_prompt_migration_compatibility(self):
        """Тест совместимости мигрированных промтов"""
        
        # Выполнить миграцию промтов
        migration_service = PromptMigrationService("./old_prompts", "./prompts")
        migrated, errors = await migration_service.migrate_prompts()
        
        # Проверить, что ошибок нет
        assert len(errors) == 0
        assert len(migrated) > 0
        
        # Проверить структуру мигрированных промтов
        from application.services.prompt_loader import PromptLoader
        loader = PromptLoader(base_path="./prompts")
        prompts, load_errors = loader.load_all_prompts()
        
        assert len(load_errors) == 0
        assert len(prompts) == len(migrated)
        
        # Проверить, что все промты имеют корректные метаданные
        for prompt in prompts:
            assert hasattr(prompt, 'domain')
            assert hasattr(prompt, 'role')
            assert hasattr(prompt, 'semantic_version')
    
    def test_config_migration_verification(self):
        """Тест совместимости мигрированной конфигурации"""
        
        # Мигрировать конфигурацию
        config_migration = ConfigMigrationService("test_config.yaml")
        migrated_config = config_migration.migrate_config("0.9", "1.0")
        
        # Проверить, что все новые поля присутствуют
        assert "agent" in migrated_config
        assert "llm" in migrated_config
        assert "prompts" in migrated_config
        assert "system" in migrated_config
        
        # Проверить, что устаревшие поля отсутствуют
        assert "max_iterations" not in migrated_config  # теперь в agent.max_iterations
        assert "timeout_seconds" not in migrated_config  # теперь в agent.timeout
    
    @pytest.mark.asyncio
    async def test_full_system_compatibility_check(self):
        """Полная проверка совместимости системы после миграции"""
        
        checker = CompatibilityChecker("0.9", "1.0")
        compatibility_report = checker.check_compatibility("./")
        
        # После успешной миграции не должно быть проблем совместимости
        assert compatibility_report["compatible"] is True
        assert compatibility_report["issues_found"] == 0
```

### 2. Валидация функциональности

Проверьте, что система работает корректно после миграции:

```python
# validation/functional_validation.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

class FunctionalValidator:
    """Валидатор функциональности системы после миграции"""
    
    def __init__(self):
        self.test_results = []
    
    async def validate_full_system_functionality(self) -> Dict[str, Any]:
        """Проверить полную функциональность системы"""
        
        results = {
            "agents_functional": await self._validate_agent_functionality(),
            "patterns_functional": await self._validate_pattern_functionality(),
            "prompts_functional": await self._validate_prompt_functionality(),
            "tools_functional": await self._validate_tool_functionality(),
            "security_functional": await self._validate_security_functionality()
        }
        
        all_passed = all(results.values())
        
        return {
            "all_tests_passed": all_passed,
            "individual_results": results,
            "validation_summary": {
                "total_tests": len(results),
                "passed_tests": sum(1 for passed in results.values() if passed),
                "failed_tests": sum(1 for passed in results.values() if not passed)
            }
        }
    
    async def _validate_agent_functionality(self) -> bool:
        """Проверить функциональность агентов"""
        try:
            # Создать агента
            agent = await AgentFactory().create_agent(
                agent_type="composable",
                domain=DomainType.CODE_ANALYSIS
            )
            
            # Выполнить простую задачу
            result = await agent.execute_task(
                task_description="Скажи 'Hello, World!'",
                context={}
            )
            
            # Проверить результат
            return "success" in result and result["success"] is True
        except Exception as e:
            print(f"Ошибка при проверке функциональности агента: {e}")
            return False
    
    async def _validate_pattern_functionality(self) -> bool:
        """Проверить функциональность паттернов"""
        try:
            # Проверить, что паттерны могут быть загружены и выполнены
            from application.services.pattern_loader import PatternLoader
            loader = PatternLoader()
            
            # Загрузить паттерны
            patterns = loader.load_patterns()
            
            # Проверить, что есть хотя бы один паттерн
            return len(patterns) > 0
        except Exception as e:
            print(f"Ошибка при проверке функциональности паттернов: {e}")
            return False
    
    async def _validate_prompt_functionality(self) -> bool:
        """Проверить функциональность системы промтов"""
        try:
            # Загрузить промты
            from application.services.prompt_loader import PromptLoader
            loader = PromptLoader(base_path="./prompts")
            prompts, errors = loader.load_all_prompts()
            
            # Проверить, что промты загружены без ошибок
            return len(errors) == 0 and len(prompts) > 0
        except Exception as e:
            print(f"Ошибка при проверке функциональности промтов: {e}")
            return False
    
    async def _validate_tool_functionality(self) -> bool:
        """Проверить функциональность инструментов"""
        try:
            # Проверить, что инструменты могут быть созданы и использованы
            from infrastructure.tools.file_reader_tool import FileReaderTool
            tool = FileReaderTool()
            
            # Проверить, что инструмент имеет корректный интерфейс
            return hasattr(tool, 'execute') and hasattr(tool, 'validate_parameters')
        except Exception as e:
            print(f"Ошибка при проверке функциональности инструментов: {e}")
            return False
    
    async def _validate_security_functionality(self) -> bool:
        """Проверить функциональность безопасности"""
        try:
            # Проверить, что система безопасности работает
            from application.services.security_validator import SecurityValidator
            validator = SecurityValidator()
            
            # Проверить валидацию безопасного содержимого
            safe_content = "This is safe content"
            validation_result = await validator.validate_content(safe_content)
            
            return validation_result["safe"] is True
        except Exception as e:
            print(f"Ошибка при проверке функциональности безопасности: {e}")
            return False

# Использование валидатора
async def validate_after_migration():
    """Проверить систему после миграции"""
    
    validator = FunctionalValidator()
    validation_results = await validator.validate_full_system_functionality()
    
    print("Результаты валидации после миграции:")
    print(f"Все тесты пройдены: {validation_results['all_tests_passed']}")
    print(f"Сводка: {validation_results['validation_summary']}")
    
    if not validation_results["all_tests_passed"]:
        print("Некоторые компоненты не прошли валидацию:")
        for component, passed in validation_results["individual_results"].items():
            if not passed:
                print(f"- {component}: FAILED")
    
    return validation_results
```

## Рекомендации по миграции

### 1. Подготовка

- **Резервное копирование**: Обязательно создайте резервные копии перед миграцией
- **Тестирование**: Подготовьте тесты для проверки корректности миграции
- **Документация**: Обновите документацию после миграции
- **Планирование**: Спланируйте миграцию с учетом зависимостей между компонентами

### 2. Выполнение

- **Постепенность**: Выполняйте миграцию поэтапно
- **Валидация**: Проверяйте каждый этап миграции
- **Тестирование**: Запускайте тесты после каждого этапа
- **Мониторинг**: Отслеживайте производительность после миграции

### 3. После миграции

- **Функциональное тестирование**: Проверьте полную функциональность системы
- **Интеграционное тестирование**: Проверьте взаимодействие между компонентами
- **Бенчмарки**: Сравните производительность до и после миграции
- **Обратная связь**: Собирайте отзывы от пользователей системы

### 4. Откат в случае проблем

Если возникнут проблемы после миграции:

```bash
# Если используется Git
git checkout migration-backup-[timestamp]

# Восстановить конфигурацию из резервной копии
cp config.yaml.backup.[timestamp] config.yaml
```

Или с использованием специального скрипта:

```python
# rollback_script.py
import shutil
import os

def rollback_migration():
    """Откатить миграцию в случае проблем"""
    
    # Найти резервные копии
    backup_files = []
    for file in os.listdir("."):
        if file.endswith(".backup"):
            backup_files.append(file)
    
    # Восстановить из резервных копий
    for backup_file in backup_files:
        original_file = backup_file.replace(".backup", "")
        shutil.copy2(backup_file, original_file)
        print(f"Восстановлен файл: {original_file} из {backup_file}")
    
    print("Миграция откачена. Система восстановлена из резервных копий.")

if __name__ == "__main__":
    rollback_migration()
```

Это руководство поможет вам безопасно и эффективно выполнить миграцию Composable AI Agent Framework на новые версии, адаптировав существующие компоненты к новым архитектурным изменениям.
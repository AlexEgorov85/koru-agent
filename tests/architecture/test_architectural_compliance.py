"""
Архитектурный аудит: проверка соблюдения принципов чистой архитектуры
и выявление дублирования классов/функциональности.

Запуск:
    python tests/architecture/test_architectural_compliance.py
    pytest tests/architecture/test_architectural_compliance.py -v
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import pytest


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ФОРМАТИРОВАНИЯ (вынесены на верхний уровень) ===

def _format_violation_report(violations: List[Dict], title: str) -> str:
    """Форматирование отчета о нарушениях"""
    report = f"\n{'='*80}\n{title}\n{'='*80}\n\n"
    for i, v in enumerate(violations, 1):
        line_info = f":{v['line']}" if 'line' in v else ""
        report += f"{i}. Файл: {v['file']}{line_info}\n"
        report += f"   Проблема: {v['message']}\n"
        report += f"   Решение: {v['recommendation']}\n\n"
    report += f"Всего нарушений: {len(violations)}\n"
    return report


def _format_full_report(violations: List[Dict]) -> str:
    """Полный форматированный отчет"""
    if not violations:
        return "✅ Архитектурный аудит пройден: все принципы соблюдены!\n"
    
    # Группировка по типам
    grouped: Dict[str, List[Dict]] = {}
    for v in violations:
        grouped.setdefault(v["type"], []).append(v)
    
    report = "🚨 АРХИТЕКТУРНЫЙ АУДИТ: НАРУШЕНИЯ ОБНАРУЖЕНЫ\n\n"
    report += f"Всего нарушений: {len(violations)}\n\n"
    
    type_descriptions = {
        "FORBIDDEN_IMPORT": "❌ Запрещенные импорты",
        "INFRASTRUCTURE_LEAKAGE": "🔥 Утечка инфраструктуры",
        "CONTEXT_CONTAMINATION": "💧 Загрязнение контекстов",
        "EVENT_PUBLISHING_VIOLATION": "📢 Неправильная публикация событий",
        "CLASS_DUPLICATION": "🔄 Дублирование классов",
        "SYNTAX_ERROR": "⚠️ Синтаксические ошибки",
    }
    
    for vtype, items in grouped.items():
        desc = type_descriptions.get(vtype, vtype)
        report += f"{desc} ({len(items)}):\n"
        for item in items[:10]:  # Первые 10 нарушения каждого типа
            line_info = f":{item['line']}" if 'line' in item else ""
            msg = item['message'][:200] + "..." if len(item['message']) > 80 else item['message']
            report += f"  • {item['file']}{line_info}: {msg}\n"
        if len(items) > 3:
            report += f"  ... и еще {len(items) - 10} нарушений этого типа\n"
        report += "\n"
    
    return report


# === ОСНОВНОЙ КЛАСС АУДИТОРА ===

class ArchitectureAuditor:
    """Аудитор архитектуры проекта"""
    
    def __init__(self, project_root: Path = Path(".")):
        self.project_root = project_root.resolve()
        self.violations: List[Dict] = []
        
        # Слои архитектуры и их пути (с проверкой существования)
        possible_layers = {
            "domain": project_root / "domain",
            "application": project_root / "application",
            "infrastructure": project_root / "infrastructure",
            "core": project_root / "core",
        }
        # Оставляем только существующие слои
        self.layers = {name: path for name, path in possible_layers.items() if path.exists()}
        
        # Запрещенные импорты для каждого слоя
        self.forbidden_imports = {
            "domain": ["infrastructure", "core/system_context", "core/session_context"],
            "application": ["infrastructure/adapters", "infrastructure/repositories"],
            "infrastructure": [],  # Инфраструктура может импортировать всё
        }
        
        # Классы/файлы, которые НЕ должны вызывать инфраструктуру напрямую
        self.no_infra_callers = [
            "thinking_patterns",
            "pattern",
            "composable_pattern",
            "agent_state",
            "session_context",
        ]
        
        # Классы/файлы, которые НЕ должны публиковать события
        self.no_event_publishers = [
            "thinking_pattern",
            "pattern",
            "agent_state",
            "session_context",
        ]
    
    def audit(self) -> List[Dict]:
        """Запустить полный аудит архитектуры"""
        self.violations = []
        
        # 1. Проверка направления зависимостей
        self._audit_dependency_direction()
        
        # 2. Проверка утечки инфраструктуры
        self._audit_infrastructure_leakage()
        
        # 3. Проверка контекстов на чистоту данных
        self._audit_context_purity()
        
        # 4. Проверка публикации событий
        self._audit_event_publishing()
        
        # 5. Поиск дублирующих классов
        self._audit_class_duplication()
        
        return self.violations
    
    def _read_file_safe(self, path: Path) -> str:
        """Безопасное чтение файла с обработкой кодировок"""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return path.read_text(encoding="cp1251")
            except Exception:
                return ""  # Пропустить файл с неизвестной кодировкой
    
    def _audit_dependency_direction(self):
        """Проверка: зависимости направлены ВНУТРЬ к домену"""
        for layer_name, layer_path in self.layers.items():
            for py_file in layer_path.rglob("*.py"):
                if self._is_test_file(py_file) or self._is_init_file(py_file):
                    continue
                
                content = self._read_file_safe(py_file)
                if not content:
                    continue
                
                try:
                    tree = ast.parse(content, filename=str(py_file))
                    imports = self._extract_imports(tree)
                    
                    for imp in imports:
                        # Проверка запрещенных импортов для слоя
                        if layer_name in self.forbidden_imports:
                            for forbidden in self.forbidden_imports[layer_name]:
                                if forbidden in imp:
                                    self.violations.append({
                                        "type": "FORBIDDEN_IMPORT",
                                        "file": str(py_file.relative_to(self.project_root)),
                                        "message": f"Запрещенный импорт '{imp}' в слое '{layer_name}'",
                                        "recommendation": f"Используйте порт (абстракцию) вместо прямого импорта инфраструктуры",
                                    })
                
                except (SyntaxError, ValueError) as e:
                    self.violations.append({
                        "type": "SYNTAX_ERROR",
                        "file": str(py_file.relative_to(self.project_root)),
                        "message": f"Ошибка разбора AST: {e}",
                        "recommendation": "Исправьте синтаксическую ошибку в файле",
                    })
    
    def _audit_infrastructure_leakage(self):
        """Проверка: нет прямых вызовов инфраструктуры из домена/приложения"""
        # Поиск прямых вызовов инфраструктуры
        patterns = [
            ".generate_response(",
            ".generate(",
            "llm_provider.",
            "prompt_renderer.",
            "prompt_repository.",
            "db_provider.",
            ".execute_query(",
            "tool_registry.",
            "skill_registry.",
            "event_publisher.publish(",
        ]
        
        for layer_name in ["domain", "application"]:
            layer_path = self.layers.get(layer_name)
            if not layer_path:
                continue
            
            for py_file in layer_path.rglob("*.py"):
                if self._is_test_file(py_file) or self._is_init_file(py_file):
                    continue
                
                content = self._read_file_safe(py_file)
                if not content:
                    continue
                
                rel_path = str(py_file.relative_to(self.project_root))
                
                # Пропустить разрешенные места (адаптеры, оркестратор)
                allowed_paths = [
                    "adapters", "repositories", "pattern_executor",
                    "runtime/runtime.py", "runtime/agent_runtime.py"
                ]
                if any(allowed in rel_path for allowed in allowed_paths):
                    continue
                
                # Проверка на вызовы инфраструктуры (игнорируя комментарии)
                for pattern in patterns:
                    if pattern in content:
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            stripped = line.strip()
                            if pattern in line and not stripped.startswith("#") and not stripped.startswith('"""') and not stripped.startswith("'''"):
                                self.violations.append({
                                    "type": "INFRASTRUCTURE_LEAKAGE",
                                    "file": rel_path,
                                    "line": i + 1,
                                    "message": f"Прямой вызов инфраструктуры обнаружен: '{pattern}'",
                                    "recommendation": "Вызовы инфраструктуры должны быть ТОЛЬКО в адаптерах (infrastructure/adapters/). Используйте порт IPatternExecutor для вызова LLM.",
                                })
                                break
    
    def _audit_context_purity(self):
        """Проверка: контексты содержат ТОЛЬКО данные (без зависимостей)"""
        # Автоматический поиск файлов контекстов
        context_patterns = [
            self.project_root / "core" / "session_context" / "session_context.py",
            self.project_root / "core" / "system_context" / "system_context.py",
            self.project_root / "application" / "context" / "session_context.py",
        ]
        
        context_files = [f for f in context_patterns if f.exists()]
        
        for ctx_file in context_files:
            content = self._read_file_safe(ctx_file)
            if not content:
                continue
            
            rel_path = str(ctx_file.relative_to(self.project_root))
            
            # Поиск полей с типами инфраструктуры в контексте
            infra_types = [
                "SystemContext", "ToolRegistry", "SkillRegistry", "LLMProvider",
                "PromptRepository", "EventPublisher", "ExecutionGateway",
                "IEventPublisher", "IPromptRepository", "BaseLLMProvider"
            ]
            
            lines = content.splitlines()
            for i, line in enumerate(lines):
                for infra_type in infra_types:
                    if f": {infra_type}" in line or f"= {infra_type}" in line:
                        # Исключаем аннотации возвращаемых значений методов и импорты
                        if "def " in line and "->" in line:
                            continue
                        if line.strip().startswith("from ") or line.strip().startswith("import "):
                            continue
                        
                        self.violations.append({
                            "type": "CONTEXT_CONTAMINATION",
                            "file": rel_path,
                            "line": i + 1,
                            "message": f"Контекст содержит зависимость от инфраструктуры: '{infra_type}'",
                            "recommendation": "SessionContext должен содержать ТОЛЬКО данные (session_id, goal, meta). SystemContext должен предоставлять ТОЛЬКО фабричные методы.",
                        })
                        break
    
    def _audit_event_publishing(self):
        """Проверка: события публикуются ТОЛЬКО из оркестратора (AgentRuntime)"""
        for layer_name, layer_path in self.layers.items():
            for py_file in layer_path.rglob("*.py"):
                if self._is_test_file(py_file) or self._is_init_file(py_file):
                    continue
                
                content = self._read_file_safe(py_file)
                if not content:
                    continue
                
                rel_path = str(py_file.relative_to(self.project_root))
                
                # Разрешенные места публикации событий
                allowed_publishers = [
                    "runtime/runtime.py",
                    "runtime/agent_runtime.py",
                    "adapters/events",
                    "infrastructure/adapters/events",
                ]
                
                if any(allowed in rel_path for allowed in allowed_publishers):
                    continue
                
                # Проверка публикации событий из запрещенных мест
                if ".publish(" in content:
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                        stripped = line.strip()
                        if ".publish(" in line and not stripped.startswith("#"):
                            # Проверка на запрещенные места
                            for forbidden in self.no_event_publishers:
                                if forbidden in rel_path.lower():
                                    self.violations.append({
                                        "type": "EVENT_PUBLISHING_VIOLATION",
                                        "file": rel_path,
                                        "line": i + 1,
                                        "message": "События публикуются из доменного/прикладного компонента (не из оркестратора)",
                                        "recommendation": "Публикация событий разрешена ТОЛЬКО в AgentRuntime. Паттерны мышления должны возвращать решения, а не публиковать события.",
                                    })
                                    break
    
    def _audit_class_duplication(self):
        """Поиск дублирующих классов по сигнатурам и функциональности"""
        # Сбор всех классов из проекта
        classes_by_name: Dict[str, List[Tuple[Path, ast.ClassDef]]] = {}
        
        for layer_path in self.layers.values():
            for py_file in layer_path.rglob("*.py"):
                if self._is_test_file(py_file) or self._is_init_file(py_file):
                    continue
                
                content = self._read_file_safe(py_file)
                if not content:
                    continue
                
                try:
                    tree = ast.parse(content, filename=str(py_file))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            if node.name not in classes_by_name:
                                classes_by_name[node.name] = []
                            classes_by_name[node.name].append((py_file, node))
                except (SyntaxError, ValueError):
                    continue
        
        # Анализ дубликатов
        for class_name, occurrences in classes_by_name.items():
            if len(occurrences) > 1:
                # Группировка по сигнатурам методов
                signature_groups: Dict[str, List[Tuple[Path, ast.ClassDef]]] = {}
                
                for file_path, class_node in occurrences:
                    # Сбор сигнатур публичных методов
                    methods = []
                    for item in class_node.body:
                        if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                            args = [arg.arg for arg in item.args.args if arg.arg != "self"]
                            methods.append(f"{item.name}({', '.join(args)})")
                    
                    signature = "|".join(sorted(methods))
                    if signature not in signature_groups:
                        signature_groups[signature] = []
                    signature_groups[signature].append((file_path, class_node))
                
                # Если есть группы с одинаковыми сигнатурами > 1 — дублирование
                for sig, group in signature_groups.items():
                    if len(group) > 1 and sig and len(sig) > 10:  # игнорируем слишком короткие сигнатуры
                        # Проверка на осмысленное дублирование (не абстракции и не исключения)
                        if not any(
                            "ABC" in str(cls_node.bases) or 
                            "Exception" in str(cls_node.bases) or
                            "Base" in cls_node.name or
                            "Mixin" in cls_node.name or
                            cls_node.name.startswith("I")  # Интерфейсы
                            for _, cls_node in group
                        ):
                            files = [str(fp.relative_to(self.project_root)) for fp, _ in group]
                            # Исключаем тестовые файлы и файлы с явными суффиксами различия
                            if not any("test" in f.lower() or "mock" in f.lower() or "base" in f.lower() for f in files):
                                self.violations.append({
                                    "type": "CLASS_DUPLICATION",
                                    "file": ", ".join(files[:10]),  # Первые 10 файла
                                    "message": f"Обнаружено дублирование класса '{class_name}' в {len(group)} файлах с одинаковой сигнатурой",
                                    "recommendation": f"Объедините дублирующие классы или создайте базовый класс. Файлы: {', '.join(files)}",
                                })
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Извлечение импортов из AST"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports
    
    def _is_test_file(self, path: Path) -> bool:
        """Проверка, является ли файл тестом"""
        path_str = str(path).lower()
        return (
            "test" in path_str or 
            "tests" in path.parts or 
            "conftest" in path.name or
            path.name.startswith("test_") or
            path.name.endswith("_test.py")
        )
    
    def _is_init_file(self, path: Path) -> bool:
        """Проверка, является ли файл __init__.py"""
        return path.name == "__init__.py"


# === ТЕСТОВЫЙ КЛАСС ===

class TestArchitecturalCompliance:
    """Тесты для проверки соблюдения архитектурных принципов"""
    
    @pytest.fixture(scope="class")
    def auditor(self) -> ArchitectureAuditor:
        """Фикстура: аудитор архитектуры"""
        # Автоматическое определение корня проекта
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent  # tests/architecture/ → корень проекта
        
        # Поиск корня проекта по признакам (на случай если структура другая)
        if not (project_root / "domain").exists():
            for parent in current_dir.parents:
                if (parent / "domain").exists():
                    project_root = parent
                    break
        
        return ArchitectureAuditor(project_root=project_root)
    
    def test_no_dependency_violations(self, auditor: ArchitectureAuditor):
        """Тест: нет нарушений направления зависимостей (зависимости направлены ВНУТРЬ)"""
        violations = auditor.audit()
        dep_violations = [v for v in violations if v["type"] == "FORBIDDEN_IMPORT"]
        
        if dep_violations:
            report = _format_violation_report(dep_violations, "НАРУШЕНИЯ НАПРАВЛЕНИЯ ЗАВИСИМОСТЕЙ")
            pytest.fail(report)
    
    def test_no_infrastructure_leakage(self, auditor: ArchitectureAuditor):
        """Тест: нет утечки инфраструктуры в домен/приложение"""
        violations = auditor.audit()
        leak_violations = [v for v in violations if v["type"] == "INFRASTRUCTURE_LEAKAGE"]
        
        if leak_violations:
            report = _format_violation_report(leak_violations, "УТЕЧКА ИНФРАСТРУКТУРЫ В ДОМЕН/ПРИЛОЖЕНИЕ")
            pytest.fail(report)
    
    def test_contexts_contain_only_data(self, auditor: ArchitectureAuditor):
        """Тест: контексты содержат ТОЛЬКО данные (без зависимостей от инфраструктуры)"""
        violations = auditor.audit()
        ctx_violations = [v for v in violations if v["type"] == "CONTEXT_CONTAMINATION"]
        
        if ctx_violations:
            report = _format_violation_report(ctx_violations, "ЗАГРЯЗНЕНИЕ КОНТЕКСТОВ ИНФРАСТРУКТУРОЙ")
            pytest.fail(report)
    
    def test_events_published_only_from_orchestrator(self, auditor: ArchitectureAuditor):
        """Тест: события публикуются ТОЛЬКО из оркестратора (AgentRuntime)"""
        violations = auditor.audit()
        event_violations = [v for v in violations if v["type"] == "EVENT_PUBLISHING_VIOLATION"]
        
        if event_violations:
            report = _format_violation_report(event_violations, "НЕПРАВИЛЬНАЯ ПУБЛИКАЦИЯ СОБЫТИЙ")
            pytest.fail(report)
    
    def test_no_class_duplication(self, auditor: ArchitectureAuditor):
        """Тест: нет дублирования классов и функциональности"""
        violations = auditor.audit()
        dup_violations = [v for v in violations if v["type"] == "CLASS_DUPLICATION"]
        
        if dup_violations:
            report = _format_violation_report(dup_violations, "ДУБЛИРОВАНИЕ КЛАССОВ")
            pytest.fail(report)
    
    def test_architecture_compliance_summary(self, auditor: ArchitectureAuditor):
        """Сводный отчет по архитектурному аудиту"""
        violations = auditor.audit()
        
        if violations:
            summary = _format_full_report(violations)
            print("\n" + "="*80)
            print(summary)
            print("="*80 + "\n")
            
            # Группировка по типам для удобства фикса
            by_type = {}
            for v in violations:
                by_type.setdefault(v["type"], []).append(v)
            
            print("\nРекомендации по исправлению:")
            print("  1. Сначала исправьте утечки инфраструктуры (самая критичная проблема)")
            print("  2. Затем очистите контексты от зависимостей")
            print("  3. Настройте правильную публикацию событий")
            print("  4. Устраните дублирование классов")
            print("  5. Исправьте направление зависимостей")


# === ТОЧКА ВХОДА ===

if __name__ == "__main__":
    # Определяем корень проекта
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # tests/architecture/ → корень
    
    # Поиск корня проекта по признакам
    if not (project_root / "domain").exists():
        for parent in script_dir.parents:
            if (parent / "domain").exists() or (parent / "application").exists():
                project_root = parent
                break
    
    print(f"Корень проекта: {project_root}")
    print(f"Найденные слои: {[f'{name}={path.exists()}' for name, path in ArchitectureAuditor(project_root).layers.items()]}")
    print()
    
    auditor = ArchitectureAuditor(project_root=project_root)
    violations = auditor.audit()
    
    # Выводим отчет
    print(_format_full_report(violations))
    
    # Возвращаем код выхода
    sys.exit(1 if violations else 0)
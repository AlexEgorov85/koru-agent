#!/usr/bin/env python3
"""
Скрипт автоматической генерации документации проекта koru-agent.

Запуск:
    python scripts/generate_docs.py --output docs/

Требования:
    pip install jinja2 pyyaml
"""

import argparse
import yaml
import re
import ast
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Исправление кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


@dataclass
class ComponentInfo:
    """Информация о компоненте"""
    name: str
    type: str  # service, skill, tool, behavior
    module: str
    file_path: str
    description: str = ""
    methods: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    prompt_versions: Dict[str, str] = field(default_factory=dict)
    input_contracts: Dict[str, str] = field(default_factory=dict)
    output_contracts: Dict[str, str] = field(default_factory=dict)


@dataclass
class DocContext:
    """Контекст для генерации документации"""
    title: str
    version: str = "5.1.0"
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    status: str = "draft"
    owner: str = "@system"
    components: List[ComponentInfo] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)


class ComponentScanner:
    """Сканер компонентов проекта"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.components: List[ComponentInfo] = []
    
    def scan(self) -> List[ComponentInfo]:
        """Сканирование проекта на наличие компонентов"""
        self._scan_services()
        self._scan_skills()
        self._scan_tools()
        self._scan_behaviors()
        return self.components
    
    def _scan_services(self):
        """Сканирование сервисов"""
        services_path = self.root_path / "core" / "application" / "services"
        if not services_path.exists():
            return
        
        for file in services_path.rglob("service.py"):
            comp = self._parse_component_file(file, "service")
            if comp:
                self.components.append(comp)
    
    def _scan_skills(self):
        """Сканирование навыков"""
        skills_path = self.root_path / "core" / "application" / "skills"
        if not skills_path.exists():
            return
        
        for file in skills_path.rglob("skill.py"):
            comp = self._parse_component_file(file, "skill")
            if comp:
                self.components.append(comp)
    
    def _scan_tools(self):
        """Сканирование инструментов"""
        tools_path = self.root_path / "core" / "application" / "tools"
        if not tools_path.exists():
            return
        
        for file in tools_path.rglob("*.py"):
            if file.name.startswith("_"):
                continue
            comp = self._parse_component_file(file, "tool")
            if comp:
                self.components.append(comp)
    
    def _scan_behaviors(self):
        """Сканирование паттернов поведения"""
        behaviors_path = self.root_path / "core" / "application" / "behaviors"
        if not behaviors_path.exists():
            return
        
        for file in behaviors_path.rglob("pattern.py"):
            comp = self._parse_component_file(file, "behavior")
            if comp:
                self.components.append(comp)
    
    def _parse_component_file(self, file_path: Path, comp_type: str) -> Optional[ComponentInfo]:
        """Парсинг файла компонента"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Извлечение имени класса
            class_match = re.search(r'class\s+(\w+)\s*\(', content)
            if not class_match:
                return None
            
            class_name = class_match.group(1)
            
            # Извлечение описания из docstring
            docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            description = docstring_match.group(1).strip() if docstring_match else ""
            
            # Извлечение методов
            methods = []
            for match in re.finditer(r'async\s+def\s+(\w+)\s*\((.*?)\)\s*(?:->\s*(\w+))?:', content):
                method_name = match.group(1)
                if not method_name.startswith("_"):
                    methods.append({
                        "name": method_name,
                        "params": match.group(2) or "",
                        "return_type": match.group(3) or "None"
                    })
            
            # Формирование модуля
            rel_path = file_path.relative_to(self.root_path)
            module = str(rel_path.with_suffix("")).replace("\\", "/").replace("/", ".")
            
            return ComponentInfo(
                name=self._snake_to_camel(class_name) if comp_type != "service" else class_name,
                type=comp_type,
                module=module,
                file_path=str(rel_path),
                description=description.split("\n")[0] if description else "",
                methods=methods
            )
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None
    
    def _snake_to_camel(self, name: str) -> str:
        """Преобразование snake_case в CamelCase"""
        return "".join(word.capitalize() for word in name.split("_"))


class RegistryLoader:
    """Загрузчик registry.yaml"""
    
    def __init__(self, registry_path: str):
        self.registry_path = Path(registry_path)
        self.data: Dict[str, Any] = {}
    
    def load(self) -> Dict[str, Any]:
        """Загрузка registry.yaml"""
        if not self.registry_path.exists():
            return {}
        
        with open(self.registry_path, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f)
        
        return self.data
    
    def get_components(self) -> Dict[str, Dict[str, Any]]:
        """Получение конфигурации компонентов"""
        components = {}
        
        for section in ["services", "skills", "behaviors"]:
            if section in self.data:
                for name, config in self.data[section].items():
                    components[name] = {
                        "type": section[:-1],  # services -> service
                        "enabled": config.get("enabled", False),
                        "dependencies": config.get("dependencies", []),
                        "prompt_versions": config.get("prompt_versions", {}),
                        "input_contracts": config.get("input_contract_versions", {}),
                        "output_contracts": config.get("output_contract_versions", {}),
                    }
        
        return components


class DocumentationGenerator:
    """Генератор документации"""
    
    def __init__(self, template_path: str, output_dir: str):
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        self.template: Optional[str] = None
    
    def load_template(self) -> str:
        """Загрузка шаблона"""
        if not self.template_path.exists():
            # Шаблон по умолчанию
            self.template = self._default_template()
        else:
            with open(self.template_path, "r", encoding="utf-8") as f:
                self.template = f.read()
        return self.template
    
    def _default_template(self) -> str:
        """Шаблон по умолчанию"""
        return """# {{title}}

> **Версия:** {{version}}  
> **Дата обновления:** {{date}}  
> **Статус:** {{status}}  
> **Владелец:** {{owner}}

---

## 🔍 Обзор

{{description}}

---

## 📚 Содержание

{{content}}

---

*Документ автоматически сгенерирован. Не редактируйте вручную.*
"""
    
    def render(self, context: DocContext) -> str:
        """Рендеринг документа"""
        if not self.template:
            self.load_template()
        
        result = self.template
        result = result.replace("{{title}}", context.title)
        result = result.replace("{{version}}", context.version)
        result = result.replace("{{date}}", context.date)
        result = result.replace("{{status}}", context.status)
        result = result.replace("{{owner}}", context.owner)
        
        # Рендеринг контента
        if "components" in context.extra_data:
            content = self._render_components_table(context.extra_data["components"])
            result = result.replace("{{content}}", content)
        
        if "description" in context.extra_data:
            result = result.replace("{{description}}", context.extra_data["description"])
        
        return result
    
    def _render_components_table(self, components: List[ComponentInfo]) -> str:
        """Рендеринг таблицы компонентов"""
        lines = ["| Компонент | Тип | Модуль | Описание |", "|-----------|-----|--------|----------|"]
        
        for comp in components:
            lines.append(f"| {comp.name} | {comp.type} | `{comp.module}` | {comp.description} |")
        
        return "\n".join(lines)
    
    def save(self, content: str, filename: str) -> Path:
        """Сохранение документа"""
        output_path = self.output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return output_path


def generate_api_reference(scanner: ComponentScanner, output_dir: Path) -> Path:
    """Генерация API Reference"""
    content = f"""# 🔌 API Reference

> **Версия:** 5.1.0  
> **Дата обновления:** {datetime.now().strftime("%Y-%m-%d")}  
> **Статус:** draft  
> **Владелец:** @system

---

## 📋 Оглавление

- [Сервисы](#сервисы)
- [Навыки](#навыки)
- [Инструменты](#инструменты)
- [Паттерны поведения](#паттерны-поведения)

---

## 🔍 Обзор

Этот документ содержит справочник API всех компонентов системы koru-agent.

---

## 🛠️ Сервисы

"""
    
    services = [c for c in scanner.components if c.type == "service"]
    for service in services:
        content += f"""### `{service.name}`

**Модуль:** `{service.module}`

**Описание:** {service.description or "Нет описания"}

**Методы:**

"""
        for method in service.methods:
            content += f"""#### `{method['name']}`

```python
async def {method['name']}({method['params']}) -> {method['return_type']}:
```

"""
    
    content += """
---

## 🎯 Навыки

"""
    
    skills = [c for c in scanner.components if c.type == "skill"]
    for skill in skills:
        content += f"""### `{skill.name}`

**Модуль:** `{skill.module}`

**Описание:** {skill.description or "Нет описания"}

**Методы:**

"""
        for method in skill.methods:
            content += f"""#### `{method['name']}`

```python
async def {method['name']}({method['params']}) -> {method['return_type']}:
```

"""
    
    content += """
---

## 🔧 Инструменты

"""
    
    tools = [c for c in scanner.components if c.type == "tool"]
    for tool in tools:
        content += f"""### `{tool.name}`

**Модуль:** `{tool.module}`

**Описание:** {tool.description or "Нет описания"}

"""
    
    content += """
---

## 🧠 Паттерны поведения

"""
    
    behaviors = [c for c in scanner.components if c.type == "behavior"]
    for behavior in behaviors:
        content += f"""### `{behavior.name}`

**Модуль:** `{behavior.module}`

**Описание:** {behavior.description or "Нет описания"}

"""
    
    output_path = output_dir / "API_REFERENCE.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Генерация документации koru-agent")
    parser.add_argument(
        "--output",
        type=str,
        default="docs/",
        help="Директория для вывода документации"
    )
    parser.add_argument(
        "--template",
        type=str,
        default="docs/templates/component_template.md",
        help="Шаблон для генерации"
    )
    parser.add_argument(
        "--registry",
        type=str,
        default="registry.yaml",
        help="Путь к registry.yaml"
    )
    parser.add_argument(
        "--components",
        nargs="*",
        help="Список компонентов для документирования"
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🔍 Сканирование проекта...")
    scanner = ComponentScanner(root_path=".")
    components = scanner.scan()
    print(f"   Найдено компонентов: {len(components)}")
    
    print(f"📄 Загрузка registry.yaml...")
    registry_loader = RegistryLoader(args.registry)
    registry_data = registry_loader.load()
    registry_components = registry_loader.get_components()
    print(f"   Зарегистрировано компонентов: {len(registry_components)}")
    
    print(f"📝 Генерация API Reference...")
    api_path = generate_api_reference(scanner, output_dir)
    print(f"   Сохранено: {api_path}")
    
    print(f"\n✅ Документация сгенерирована в {output_dir}")
    print(f"\n📁 Созданные файлы:")
    for f in output_dir.glob("*.md"):
        print(f"   - {f}")


if __name__ == "__main__":
    main()

# Миграция Capability v2

## Изменения в архитектуре

### До (v1):
```python
# Capability содержал схему параметров
class Capability(BaseModel):
    name: str
    description: str
    parameters_schema: Dict[str, Any]  # ← Встроенные схемы
    skill_name: str
    # ...
```

### После (v2):
```python
# Capability теперь только декларация
class Capability(BaseModel):
    name: str
    description: str
    skill_name: str
    meta: Dict[str, Any]  # ← Только метаданные
    # ...
```

## Миграционный скрипт

Для миграции существующих `parameters_schema` в контракты используйте следующий скрипт:

```python
import yaml
from pathlib import Path
from models.capability import Capability

def migrate_capability_schemas_to_contracts(capabilities: list[Capability], output_dir: str = "contracts/migrated"):
    """
    Мигрирует параметры из Capability в отдельные файлы контрактов.
    
    Args:
        capabilities: Список capability для миграции
        output_dir: Директория для сохранения контрактов
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for cap in capabilities:
        # Создаем контракт из старой схемы параметров
        if hasattr(cap, 'parameters_schema') and cap.parameters_schema:
            # Создаем input контракт
            input_contract = {
                "version": "v1.0.0-migrated",
                "contract_type": "input",
                "skill": cap.skill_name,
                "capability": cap.name,
                "schema": cap.parameters_schema
            }
            
            # Сохраняем в файл
            filename = f"{cap.name.replace('.', '_')}_input_v1.0.0-migrated.yaml"
            filepath = output_path / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(input_contract, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"Мигрирован контракт: {filepath}")

# Пример использования:
# migrate_capability_schemas_to_contracts(your_capabilities_list)
```

## Пошаговая инструкция для разработчиков навыков

### 1. Обновление метода get_capabilities()

**Было:**
```python
def get_capabilities(self) -> List[Capability]:
    return [
        Capability(
            name="my_skill.do_something",
            description="Описание действия",
            parameters_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "integer"}
                },
                "required": ["param1"]
            },
            skill_name=self.name
        )
    ]
```

**Стало:**
```python
def get_capabilities(self) -> List[Capability]:
    return [
        Capability(
            name="my_skill.do_something",
            description="Описание действия",
            skill_name=self.name,
            meta={
                "contract_version": "v1.0.0",  # ← Указываем версию контракта
                "prompt_version": "v1.0.0"    # ← Указываем версию промпта
            }
        )
    ]
```

### 2. Создание файлов контрактов

Создайте файлы контрактов в директории `contracts/skills/{skill_name}/`:

**Файл: `contracts/skills/my_skill/my_skill_do_something_input_v1.0.0.yaml`**
```yaml
version: v1.0.0
contract_type: input
skill: my_skill
capability: my_skill.do_something
schema:
  type: object
  properties:
    param1:
      type: string
      description: "Описание параметра 1"
    param2:
      type: integer
      description: "Описание параметра 2"
  required:
    - param1
```

### 3. Обновление логики выполнения

**Было (в методе execute):**
```python
async def execute(self, capability, parameters, context):
    # Прямой доступ к параметрам без валидации
    result = await self._do_work(parameters['param1'], parameters['param2'])
    return result
```

**Стало:**
```python
async def execute(self, capability, parameters, context):
    # Используем предзагруженный контракт для валидации
    input_contract = self.get_input_contract(capability.name)
    
    # Валидация параметров (если необходимо)
    # Логика выполнения с использованием параметров
    result = await self._do_work(parameters['param1'], parameters['param2'])
    return result
```

## Проверка миграции

После миграции проверьте:

1. Все capability больше не содержат `parameters_schema`
2. Все контракты созданы в соответствующих директориях
3. Навыки успешно инициализируются с предзагруженными ресурсами
4. Методы `get_prompt()` и `get_input_contract()` работают корректно
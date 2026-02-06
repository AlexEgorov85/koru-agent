# Интеграция промтов с агентами

Интеграция системы промтов с агентами Composable AI Agent Framework обеспечивает эффективное взаимодействие между компонентами фреймворка. Эта интеграция позволяет агентам использовать различные промты для выполнения задач, адаптации к доменам и взаимодействия с LLM.

## Архитектура интеграции

Система интеграции включает следующие компоненты:

### 1. Репозиторий промтов

Центральный компонент, обеспечивающий доступ к промтам:

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models.prompt.prompt_version import PromptVersion
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from domain.models.prompt.prompt_version import PromptRole

class IPromptRepository(ABC):
    """Интерфейс репозитория промтов"""
    
    @abstractmethod
    async def get_active_prompts(
        self,
        domain: DomainType,
        capability: str,
        role: Optional[PromptRole] = None
    ) -> List[PromptVersion]:
        """Получить активные промты для домена и капабилити"""
        pass
    
    @abstractmethod
    async def get_prompt_by_id(self, prompt_id: str) -> Optional[PromptVersion]:
        """Получить промт по ID"""
        pass
    
    @abstractmethod
    async def get_latest_version(
        self,
        domain: DomainType,
        capability: str,
        role: PromptRole
    ) -> Optional[PromptVersion]:
        """Получить последнюю версию промта"""
        pass
```

### 2. Сервис загрузки промтов

Компонент для загрузки промтов из файловой системы:

```python
from application.services.prompt_loader import PromptLoader
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository

class PromptService:
    """Сервис для работы с промтами"""
    
    def __init__(self, base_path: str = "./prompts"):
        self.loader = PromptLoader(base_path)
        self.repository = InMemoryPromptRepository()
    
    async def refresh_prompts(self) -> List[str]:
        """Обновить промты из файловой системы"""
        loaded_prompts, errors = self.loader.load_all_prompts()
        
        # Очистить репозиторий и загрузить новые промты
        self.repository.clear()
        
        for prompt in loaded_prompts:
            await self.repository.save(prompt)
        
        return errors
```

### 3. Адаптер промтов для агентов

Компонент, обеспечивающий интеграцию между агентами и промтами:

```python
class PromptAdapter:
    """Адаптер для интеграции промтов с агентами"""
    
    def __init__(self, prompt_repository: IPromptRepository):
        self.repository = prompt_repository
    
    async def get_appropriate_prompt(
        self,
        domain: DomainType,
        capability: str,
        role: PromptRole,
        context: dict
    ) -> Optional[PromptVersion]:
        """Получить подходящий промт для текущего контекста"""
        
        # Сначала пробуем получить последнюю активную версию
        prompt = await self.repository.get_latest_version(domain, capability, role)
        
        if prompt and prompt.status == "active":
            return prompt
        
        # Если нет активной версии, ищем другие подходящие
        all_prompts = await self.repository.get_active_prompts(domain, capability, role)
        
        # Фильтруем по статусу и совместимости с контекстом
        suitable_prompts = [
            p for p in all_prompts
            if p.status == "active" and self._is_compatible(p, context)
        ]
        
        return suitable_prompts[0] if suitable_prompts else None
    
    def _is_compatible(self, prompt: PromptVersion, context: dict) -> bool:
        """Проверить совместимость промта с контекстом"""
        # Проверяем, есть ли все необходимые переменные в контексте
        for variable in prompt.variables_schema:
            if variable.required and variable.name not in context:
                return False
        
        return True
```

## Интеграция с агентами

### 1. Адаптация агента к домену

При адаптации агента к домену он загружает соответствующие промты:

```python
class ComposableAgent:
    """Компонуемый агент с интеграцией промтов"""
    
    def __init__(self, prompt_adapter: PromptAdapter):
        self.prompt_adapter = prompt_adapter
        self.domain = None
        self.capabilities = []
        self.loaded_prompts = {}
    
    async def adapt_to_domain(self, domain: DomainType, capabilities: List[str]):
        """Адаптировать агента к домену с загрузкой промтов"""
        self.domain = domain
        self.capabilities = capabilities
        
        # Загрузка промтов для каждого capability
        for capability in capabilities:
            for role in [PromptRole.SYSTEM, PromptRole.USER, PromptRole.ASSISTANT, PromptRole.TOOL]:
                prompt = await self.prompt_adapter.get_appropriate_prompt(
                    domain=domain,
                    capability=capability,
                    role=role,
                    context={}
                )
                
                if prompt:
                    key = f"{domain.value}:{capability}:{role.value}"
                    self.loaded_prompts[key] = prompt
    
    async def get_prompt_for_task(self, capability: str, role: PromptRole, context: dict) -> Optional[str]:
        """Получить промт для конкретной задачи"""
        key = f"{self.domain.value}:{capability}:{role.value}"
        
        if key not in self.loaded_prompts:
            # Попробовать загрузить промт динамически
            prompt = await self.prompt_adapter.get_appropriate_prompt(
                domain=self.domain,
                capability=capability,
                role=role,
                context=context
            )
            
            if prompt:
                self.loaded_prompts[key] = prompt
            else:
                return None
        
        prompt = self.loaded_prompts[key]
        
        # Рендеринг промта с переменными из контекста
        return self._render_prompt(prompt, context)
    
    def _render_prompt(self, prompt: PromptVersion, context: dict) -> str:
        """Рендеринг промта с подстановкой переменных"""
        content = prompt.content
        
        # Заменяем переменные в формате {{variable_name}}
        for var_name, var_value in context.items():
            placeholder = f"{{{{{var_name}}}}}"
            content = content.replace(placeholder, str(var_value))
        
        return content
```

### 2. Использование промтов в паттернах мышления

Паттерны мышления могут использовать промты для выполнения задач:

```python
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState

class AnalysisPattern(IThinkingPattern):
    """Паттерн анализа с использованием промтов"""
    
    def __init__(self, agent: ComposableAgent):
        self.agent = agent
        self.name = "analysis_pattern"
    
    async def execute(
        self,
        state: AgentState,
        context: dict,
        available_capabilities: List[str]
    ) -> dict:
        """Выполнить паттерн анализа с использованием промтов"""
        
        # Получить системный промт для анализа
        system_prompt = await self.agent.get_prompt_for_task(
            capability="analysis",
            role=PromptRole.SYSTEM,
            context=context
        )
        
        if not system_prompt:
            return {"error": "No system prompt available for analysis"}
        
        # Получить пользовательский промт с данными для анализа
        user_context = {**context, "analysis_type": "security"}
        user_prompt = await self.agent.get_prompt_for_task(
            capability="analysis",
            role=PromptRole.USER,
            context=user_context
        )
        
        if not user_prompt:
            return {"error": "No user prompt available for analysis"}
        
        # Объединить промты и отправить LLM
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Вызвать LLM (реализация зависит от конкретного провайдера)
        llm_response = await self._call_llm(full_prompt)
        
        # Обработать ответ
        analysis_result = self._process_llm_response(llm_response)
        
        return {
            "success": True,
            "analysis": analysis_result,
            "next_action": "report_generation"
        }
    
    async def _call_llm(self, prompt: str) -> str:
        """Вызов LLM (реализация зависит от провайдера)"""
        # Здесь будет реализация вызова конкретного LLM провайдера
        pass
    
    def _process_llm_response(self, response: str) -> dict:
        """Обработка ответа от LLM"""
        # Обработка и структурирование ответа
        pass
```

## Пример интеграции в реальной задаче

### 1. Задача анализа кода

```python
# Пример использования промтов в задаче анализа кода
async def code_analysis_example():
    # Инициализация сервисов
    prompt_service = PromptService("./prompts")
    errors = await prompt_service.refresh_prompts()
    
    if errors:
        print(f"Errors loading prompts: {errors}")
    
    prompt_adapter = PromptAdapter(prompt_service.repository)
    agent = ComposableAgent(prompt_adapter)
    
    # Адаптация агента к домену анализа кода
    await agent.adapt_to_domain(
        domain=DomainType.CODE_ANALYSIS,
        capabilities=["security_analysis", "code_review", "vulnerability_detection"]
    )
    
    # Подготовка контекста задачи
    code_to_analyze = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = execute_query(query)
    return result
"""
    
    context = {
        "code": code_to_analyze,
        "task": "security_analysis",
        "target_vulnerabilities": ["sql_injection", "authentication_issues"]
    }
    
    # Выполнение анализа с использованием паттерна
    analysis_pattern = AnalysisPattern(agent)
    result = await analysis_pattern.execute(
        state=AgentState(),
        context=context,
        available_capabilities=["security_analysis", "code_review"]
    )
    
    print(f"Analysis result: {result}")
    
    return result
```

## Валидация интеграции

Система включает валидацию интеграции промтов с агентами:

```python
class IntegrationValidator:
    """Валидатор интеграции промтов с агентами"""
    
    def __init__(self, prompt_repository: IPromptRepository):
        self.repository = prompt_repository
    
    async def validate_agent_prompts(self, agent: ComposableAgent) -> ValidationResult:
        """Валидация промтов агента"""
        errors = []
        
        # Проверка, что у агента есть необходимые промты
        required_combinations = [
            (agent.domain, cap, role)
            for cap in agent.capabilities
            for role in [PromptRole.SYSTEM, PromptRole.USER]
        ]
        
        for domain, capability, role in required_combinations:
            prompts = await self.repository.get_active_prompts(domain, capability, role)
            
            if not prompts:
                errors.append(f"No {role.value} prompts available for {domain.value}:{capability}")
        
        # Проверка совместимости переменных
        for key, prompt in agent.loaded_prompts.items():
            if prompt.variables_schema:
                # Проверить, что переменные могут быть заполнены
                # (реализация зависит от конкретного случая)
                pass
        
        return ValidationResult(success=len(errors) == 0, errors=errors)
```

## Лучшие практики интеграции

### 1. Lazy loading

Загружайте промты по мере необходимости:

```python
async def get_prompt_efficiently(self, capability: str, role: PromptRole, context: dict):
    """Эффективное получение промта с кешированием"""
    key = f"{self.domain.value}:{capability}:{role.value}"
    
    if key not in self.loaded_prompts:
        # Загружаем промт только при необходимости
        prompt = await self.prompt_adapter.get_appropriate_prompt(
            domain=self.domain,
            capability=capability,
            role=role,
            context=context
        )
        
        if prompt:
            self.loaded_prompts[key] = prompt
    
    return self.loaded_prompts.get(key)
```

### 2. Кеширование

Используйте кеширование для улучшения производительности:

```python
from functools import lru_cache
import hashlib

class CachedPromptAdapter(PromptAdapter):
    """Адаптер промтов с кешированием"""
    
    def __init__(self, prompt_repository: IPromptRepository, cache_ttl: int = 3600):
        super().__init__(prompt_repository)
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._cache_timestamps = {}
    
    async def get_appropriate_prompt(
        self,
        domain: DomainType,
        capability: str,
        role: PromptRole,
        context: dict
    ) -> Optional[PromptVersion]:
        """Получить подходящий промт с кешированием"""
        # Создаем ключ кеша на основе параметров
        cache_key = self._generate_cache_key(domain, capability, role, context)
        current_time = time.time()
        
        # Проверяем, есть ли в кеше актуальные данные
        if cache_key in self._cache_timestamps:
            if current_time - self._cache_timestamps[cache_key] < self.cache_ttl:
                return self._cache[cache_key]
        
        # Загружаем данные и сохраняем в кеш
        prompt = await super().get_appropriate_prompt(domain, capability, role, context)
        self._cache[cache_key] = prompt
        self._cache_timestamps[cache_key] = current_time
        
        return prompt
    
    def _generate_cache_key(self, domain, capability, role, context) -> str:
        """Генерация ключа для кеширования"""
        context_str = str(sorted(context.items()))
        key_str = f"{domain.value}:{capability}:{role.value}:{context_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def get_prompt_with_fallback(
    self,
    capability: str,
    role: PromptRole,
    context: dict,
    fallback_prompt: Optional[str] = None
):
    """Получить промт с резервной стратегией"""
    try:
        prompt = await self.get_prompt_for_task(capability, role, context)
        if prompt:
            return prompt
    except Exception as e:
        print(f"Error getting prompt: {e}")
    
    # Использовать резервный промт или вернуть стандартный
    if fallback_prompt:
        return fallback_prompt
    
    # Или вернуть дефолтный промт для этой роли
    return self._get_default_prompt(role)
```

## Преимущества интеграции

### 1. Гибкость

- Возможность динамического выбора промтов
- Адаптация к различным доменам и задачам
- Поддержка различных версий промтов

### 2. Надежность

- Валидация промтов перед использованием
- Резервные стратегии при отсутствии промтов
- Обработка ошибок на всех уровнях

### 3. Производительность

- Кеширование часто используемых промтов
- Lazy loading для экономии ресурсов
- Эффективные стратегии поиска промтов

## Интеграция с другими компонентами

Интеграция промтов с агентами тесно связана с:

- **Системой паттернов мышления**: Паттерны используют промты для выполнения задач
- **Системой доменов**: Промты адаптируются к конкретным доменам
- **Системой событий**: События могут триггерить загрузку определенных промтов
- **Системой конфигурации**: Настройки могут влиять на выбор промтов
- **Системой логирования**: Использование промтов логируется для анализа
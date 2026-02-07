from domain.abstractions.pattern_executor import IPatternExecutor
from domain.value_objects.provider_type import LLMRequest, LLMResponse
from infrastructure.adapters.prompt_renderer import PromptRenderer
from domain.abstractions.event_types import IEventPublisher
from domain.abstractions.prompt_repository import ISnapshotManager
from domain.models.prompt.capability import Capability
from domain.value_objects.provider_type import LLMProviderType
from domain.models.prompt.prompt_role import PromptRole
from typing import Dict, Any, Optional


class PatternExecutor(IPatternExecutor):
    """Адаптер для выполнения рассуждений через LLM. ЕДИНСТВЕННОЕ место вызова инфраструктуры."""
    
    def __init__(
        self,
        prompt_renderer: PromptRenderer,      # ← ПЕРЕИСПОЛЬЗУЕМ существующий
        llm_provider: Any,                   # ← ПЕРЕИСПОЛЬЗУЕМ существующий провайдер
        event_publisher: IEventPublisher,     # ← ПЕРЕИСПОЛЬЗУЕМ существующую шину
        snapshot_manager: Optional[ISnapshotManager] = None  # ← ПЕРЕИСПОЛЬЗУЕМ существующий
    ):
        self.prompt_renderer = prompt_renderer
        self.llm_provider = llm_provider
        self.events = event_publisher
        self.snapshots = snapshot_manager
    
    async def execute_thinking(
        self,
        pattern_name: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> LLMResponse:
        # 1. Рендерим промты через СУЩЕСТВУЮЩИЙ PromptRenderer
        rendered_prompts, snapshot, errors = await self.prompt_renderer.render_and_create_snapshot(
            capability=Capability(
                name=f"thinking.{pattern_name}",
                description=f"{pattern_name} thinking capability",
                skill_name="thinking_skill",
                provider_type=LLMProviderType.OPENAI,
                versions={}
            ),
            provider_type=LLMProviderType.OPENAI,
            template_context=context,
            session_id=session_id
        )
        
        # 2. Формируем запрос через СУЩЕСТВУЮЩИЙ LLMRequest
        request = LLMRequest(
            prompt=rendered_prompts.get(PromptRole.USER, ""),
            system_prompt=rendered_prompts.get(PromptRole.SYSTEM, ""),
            max_tokens=context.get("max_tokens", 500),
            temperature=context.get("temperature", 0.7)
        )
        
        # 3. ВЫЗОВ LLM — ЕДИНСТВЕННОЕ место в системе!
        raw_response = await self.llm_provider.generate(request)
        
        # 4. Возвращаем СУЩЕСТВУЮЩИЙ LLMResponse (без создания новых моделей!)
        # Примечание: События публикуются ТОЛЬКО из AgentRuntime, не из адаптеров
        return raw_response
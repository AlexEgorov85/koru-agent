"""
JsonParsingService — единый сервис для парсинка JSON ответов LLM.

USAGE:
    # Через ActionExecutor:
    result = await executor.execute_action(
        action_name="json_parsing.parse_to_model",
        parameters={
            "raw_response": llm_response,
            "schema_def": output_schema,
            "model_name": "ReasoningResult"
        },
        context=execution_context
    )
"""
from .service import JsonParsingService
from .types import JsonParseResult, JsonParseStatus

__all__ = ["JsonParsingService", "JsonParseResult", "JsonParseStatus"]

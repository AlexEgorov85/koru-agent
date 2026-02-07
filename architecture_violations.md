# Architecture Violations Found

## 1. Infrastructure Dependencies in Thinking Patterns

### ReActPattern (`application/agent/thinking_patterns/react_pattern.py`)
- **Constructor receives infrastructure dependencies:**
  - `llm_provider` - direct LLM provider dependency
  - `prompt_renderer` - direct prompt rendering dependency  
  - `prompt_repository` - direct prompt repository dependency

- **Direct infrastructure calls in execute():**
  - `self.prompt_renderer.render()` calls inside atomic actions
  - `self.llm_provider.generate_response()` calls inside atomic actions

### PlanAndExecutePattern (`application/agent/thinking_patterns\plan_and_execute_pattern.py`)
- **Constructor receives infrastructure dependencies:**
  - `llm_provider` - direct LLM provider dependency
  - `prompt_renderer` - direct prompt rendering dependency
  - `prompt_repository` - direct prompt repository dependency

- **Direct infrastructure calls in execute():**
  - `self.prompt_renderer.render()` calls for plan generation
  - `self.llm_provider.generate_response()` calls for plan execution

## 2. Event Publishing from Thinking Patterns

Both patterns have infrastructure dependencies that could potentially publish events directly, violating the principle that only `AgentRuntime` should publish events.

## 3. SessionContext Issues

The `SessionContext` contains methods that reference infrastructure components like `system_context`, `event_publisher`, `execution_gateway`, etc., which violates the pure data container principle.

## 4. Missing Port Abstraction

There is no `IPatternExecutor` port abstraction to isolate infrastructure calls from domain logic.

## 5. AgentRuntime Responsibilities

The `AgentRuntime` currently delegates execution logic directly to thinking patterns without proper orchestration through ports.
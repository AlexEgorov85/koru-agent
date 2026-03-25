# КОМПЛЕКСНЫЙ АУДИТ КОДА

**Всего элементов:** 1886
**Уникальных имён:** 1295
**Дубликатов по имени:** 188

## СВОДКА ПО НАЗНАЧЕНИЮ

- **Утилита**: 458
- **Конфигурация**: 207
- **Контекст**: 154
- **Сервис**: 135
- **Провайдер**: 130
- **Обработчик**: 129
- **Ошибка**: 126
- **Хранилище**: 116
- **Агент**: 114
- **Поведение**: 55
- **Инструмент**: 44
- **Навык**: 40
- **Обнаружение**: 38
- **Логирование**: 33
- **Менеджер**: 27
- **Интерфейс**: 17
- **Базовый класс**: 14
- **Сборщик**: 12
- **Реестр**: 11
- **Валидатор**: 10
- **Фабрика**: 9
- **Загрузчик**: 3
- **Миксин**: 2
- **Исключение**: 1
- **Исполнитель**: 1

## ДУБЛИКАТЫ (одинаковое имя в разных файлах)

- **__init__**: 195x - vector_search_examples, base_component, base_tool, component_discovery
- **to_dict**: 43x - component_discovery, agent_config, logging_config, error_handler
- **__post_init__**: 17x - error_handler, model, model, benchmark
- **__repr__**: 14x - lifecycle, app_config, app_config, app_config
- **_get_event_type_for_success**: 14x - base_behavior_pattern, base_service, contract_service, prompt_service
- **description**: 13x - base_service, contract_service, prompt_service, table_description_service
- **_execute_impl**: 11x - base_behavior_pattern, base_service, contract_service, prompt_service
- **get_prompt**: 8x - data_repository, base_component, resource_discovery, base_behavior_pattern
- **get_stats**: 8x - error_handler, security_manager, lifecycle_manager, resource_discovery
- **Config**: 8x - analysis, analysis, vector_types, vector_types
- **from_dict**: 7x - logging_config, benchmark, benchmark, execution
- **is_initialized**: 6x - lifecycle, infrastructure_context, lifecycle_manager, log_search
- **_init_event_bus_logger**: 6x - logging, file_system_data_source, factory, runtime
- **validate**: 6x - paths, structured_actions, structured_actions, structured_actions
- **_safe_async_call**: 6x - base_behavior_pattern, table_description_service, file_tool, sql_tool
- **get_capabilities**: 6x - base_skill, base_tool, skill, skill
- **get_config**: 5x - app_config, __init__, chunking_strategy, text_chunking_strategy
- **subscribe**: 5x - event_bus, llm_event_subscriber, unified_event_bus, ports
- **get_resource**: 5x - infrastructure_context, lifecycle_manager, resource_registry, application_context
- **_validate_output**: 5x - skill, base_handler, execute_script_handler, search_books_handler
- **_log_info**: 4x - data_repository, resource_discovery, capability_registry, versioned_storage
- **_log_warning**: 4x - data_repository, resource_discovery, capability_registry, versioned_storage
- **_get_component_type**: 4x - file_system_data_source, base_service, base_skill, base_tool
- **_convert_params_to_input**: 4x - base_service, base_tool, file_tool, sql_tool
- **MockSQL**: 3x - vector_search_examples, vector_search_examples, vector_search_examples
- **_log_error**: 3x - data_repository, resource_discovery, versioned_storage
- **get_contract**: 3x - data_repository, resource_discovery, contract_service
- **get_input_contract**: 3x - base_component, base_behavior_pattern, application_context
- **get_output_contract**: 3x - base_component, base_behavior_pattern, application_context
- **ComponentStatus**: 3x - component_discovery, manifest, common_enums
- **ComponentNotFoundError**: 3x - component_discovery, exceptions, __init__
- **is_ready**: 3x - lifecycle, infrastructure_context, application_context
- **LogLevel**: 3x - logging_config, config, log_config
- **LogFormat**: 3x - logging_config, config, log_config
- **LoggingConfig**: 3x - logging_config, config, log_config
- **get_logging_config**: 3x - logging_config, config, log_config
- **configure_logging**: 3x - logging_config, config, log_config
- **logs_dir**: 3x - logging_config, paths, config
- **sessions_dir**: 3x - logging_config, paths, config
- **archive_dir**: 3x - logging_config, paths, log_config

## ЭЛЕМЕНТЫ (уникальные имена, первый файл)

### Утилита (361 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `Event` | unified_event_bus | - | 1 | 62 |
| `EventType` | unified_event_bus | Enum | 0 | 38 |
| `Prompt` | prompt | TemplateValidatorMixin, BaseModel | 3 | 25 |
| `Capability` | capability | BaseModel | 0 | 23 |
| `ComponentType` | manifest | Enum | 0 | 23 |
| `ExecutionStatus` | common_enums | Enum | 0 | 22 |
| `UnifiedEventBus` | unified_event_bus | - | 13 | 22 |
| `ExecutionResult` | execution | - | 8 | 18 |
| `Pattern` | pattern_analyzer | - | 1 | 14 |
| `LLMRequest` | execution_trace | - | 1 | 12 |
| `Action` | execution_trace | - | 1 | 12 |
| `Contract` | contract | TemplateValidatorMixin, BaseModel | 6 | 11 |
| `LLMResponse` | execution_trace | - | 1 | 9 |
| `PromptStatus` | common_enums | str, Enum | 0 | 9 |
| `StepTrace` | execution_trace | - | 3 | 6 |
| `ExecutionTrace` | execution_trace | - | 8 | 6 |
| `DBHealthStatus` | db_types | Enum | 0 | 6 |
| `ComponentState` | lifecycle | Enum | 0 | 5 |
| `ComponentStatus` | manifest | Enum | 0 | 5 |
| `ResourceType` | common_enums | str, Enum | 0 | 5 |
| `RetryDecision` | common_enums | str, Enum | 0 | 5 |
| `ContractDirection` | common_enums | str, Enum | 0 | 5 |
| `DBQueryResult` | db_types | - | 1 | 5 |
| `StructuredLLMResponse` | llm_types | Subscript(value=Name(id='Generic', ctx=Load()), slice=Name(id='T', ctx=Load()), ctx=Load()) | 2 | 5 |
| `DataRepository` | data_repository | - | 17 | 4 |
| `MetricType` | metrics | Enum | 0 | 4 |
| `MetricRecord` | metrics | - | 2 | 4 |
| `ReasoningResult` | react_models | BaseModel | 0 | 4 |
| `LLMHealthStatus` | llm_types | str, Enum | 0 | 4 |
| `VectorChunk` | vector_types | BaseModel | 0 | 4 |
| `Example` | example_extractor | - | 2 | 4 |
| `RootCause` | root_cause_analyzer | - | 1 | 4 |
| `LogType` | benchmark | Enum | 0 | 3 |
| `LogEntry` | benchmark | - | 2 | 3 |
| `ScenarioType` | benchmark | Enum | 0 | 3 |
| `MutationType` | benchmark | Enum | 0 | 3 |
| `OptimizationSample` | benchmark | - | 3 | 3 |
| `PromptVersion` | benchmark | - | 4 | 3 |
| `EvaluationResult` | benchmark | - | 2 | 3 |
| `AggregatedMetrics` | metrics | - | 3 | 3 |

### Конфигурация (153 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `Config` | analysis | - | 0 | 49 |
| `ComponentConfig` | component_config | BaseModel | 2 | 25 |
| `AppConfig` | app_config | BaseSettings | 15 | 10 |
| `LoggingConfig` | logging_config | BaseModel | 9 | 8 |
| `AgentConfig` | agent_config | BaseModel | 2 | 5 |
| `LogFormat` | logging_config | str, Enum | 0 | 5 |
| `StructuredOutputConfig` | llm_types | PydanticBaseModel | 1 | 5 |
| `LLMProviderConfig` | app_config | BaseModel | 2 | 4 |
| `DBProviderConfig` | app_config | BaseModel | 1 | 4 |
| `DBConnectionConfig` | db_types | - | 0 | 4 |
| `LogLevel` | logging_config | str, Enum | 2 | 3 |
| `RegistryConfig` | models | BaseModel | 1 | 3 |
| `SystemConfig` | models | BaseModelConfig | 4 | 3 |
| `VectorSearchConfig` | vector_config | BaseModel | 1 | 3 |
| `ConfigurationError` | exceptions | AgentBaseError | 1 | 3 |
| `FileConfig` | logging_config | BaseModel | 0 | 2 |
| `RetentionConfig` | logging_config | BaseModel | 0 | 2 |
| `IndexingConfig` | logging_config | BaseModel | 0 | 2 |
| `SymlinksConfig` | logging_config | BaseModel | 0 | 2 |
| `FAISSConfig` | vector_config | BaseModel | 1 | 2 |
| `EmbeddingConfig` | vector_config | BaseModel | 0 | 2 |
| `ConfigLoader` | __init__ | - | 1 | 2 |
| `LlamaCppConfig` | llama_cpp_provider | BaseModel | 0 | 2 |
| `MockLLMConfig` | mock_provider | BaseModel | 0 | 2 |
| `TraceCollectionConfig` | trace_collector | - | 0 | 2 |
| `DatabaseSettings` | app_config | BaseSettings | 4 | 1 |
| `LLMSettings` | app_config | BaseSettings | 4 | 1 |
| `AgentSettings` | app_config | BaseSettings | 2 | 1 |
| `ConsoleConfig` | logging_config | BaseModel | 0 | 1 |
| `SessionConfig` | logging_config | BaseModel | 0 | 1 |
| `BaseModelConfig` | models | BaseModel | 2 | 1 |
| `SkillConfig` | models | BaseModel | 0 | 1 |
| `ToolConfig` | models | BaseModel | 0 | 1 |
| `SecurityConfig` | models | BaseModel | 1 | 1 |
| `LogPaths` | paths | BaseModel | 16 | 1 |
| `AppPaths` | paths | BaseModel | 9 | 1 |
| `TimeoutConfig` | timeout_config | BaseModel | 4 | 1 |
| `ChunkingConfig` | vector_config | BaseModel | 0 | 1 |
| `VectorStorageConfig` | vector_config | BaseModel | 0 | 1 |
| `AnalysisCacheConfig` | vector_config | BaseModel | 0 | 1 |

### Контекст (114 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `ApplicationContext` | application_context | BaseSystemContext | 28 | 27 |
| `SessionContext` | session_context | BaseSessionContext | 18 | 10 |
| `InfrastructureContext` | infrastructure_context | - | 25 | 6 |
| `ResourceType` | lifecycle_manager | Enum | 0 | 5 |
| `BaseSessionContext` | base_session_context | - | 17 | 4 |
| `UserContext` | user_context | - | 3 | 3 |
| `ContextItemType` | model | str, Enum | 0 | 3 |
| `ContextItemMetadata` | model | - | 1 | 3 |
| `ContextItem` | model | - | 1 | 3 |
| `StepContext` | step_context | - | 6 | 3 |
| `BaseSystemContext` | base_system_context | ABC | 3 | 3 |
| `ValidationResult` | context_validator | - | 6 | 3 |
| `DataContext` | data_context | - | 7 | 2 |
| `LifecycleManager` | lifecycle_manager | - | 10 | 2 |
| `UserRole` | user_context | str, Enum | 0 | 1 |
| `encoding_context` | encoding | - | 3 | 1 |
| `ExecutionContextSnapshot` | execution | - | 2 | 1 |
| `ManagedResource` | lifecycle_manager | Protocol | 1 | 1 |
| `ResourceStatus` | lifecycle_manager | Enum | 0 | 1 |
| `ResourceRecord` | lifecycle_manager | - | 1 | 1 |
| `ResourceRegistry` | resource_registry | - | 7 | 1 |
| `ContextValidator` | context_validator | - | 8 | 1 |
| `application_context` | base_component | 1 params | - | - |
| `__init__` | user_context | 4 params | - | - |
| `_get_default_permissions` | user_context | 2 params | - | - |
| `has_permission` | user_context | 2 params | - | - |
| `set_goal` | base_session_context | 2 params | - | - |
| `get_goal` | base_session_context | 1 params | - | - |
| `add_context_item` | base_session_context | 4 params | - | - |
| `get_context_item` | base_session_context | 2 params | - | - |
| `register_step` | base_session_context | 7 params | - | - |
| `set_current_plan` | base_session_context | 2 params | - | - |
| `get_current_plan` | base_session_context | 1 params | - | - |
| `is_expired` | base_session_context | 2 params | - | - |
| `get_summary` | base_session_context | 1 params | - | - |
| `get_current_plan_step` | base_session_context | 1 params | - | - |
| `record_action` | base_session_context | 4 params | - | - |
| `record_observation` | base_session_context | 5 params | - | - |
| `record_plan` | base_session_context | 4 params | - | - |
| `record_decision` | base_session_context | 4 params | - | - |

### Сервис (89 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `ServiceInput` | base_service | ABC | 0 | 9 |
| `ServiceOutput` | base_service | ABC | 0 | 9 |
| `BaseService` | base_service | BaseComponent | 11 | 9 |
| `ExecutionError` | error_analyzer | - | 0 | 9 |
| `PromptService` | prompt_service | BaseService | 7 | 5 |
| `SQLErrorAnalyzer` | error_analyzer | BaseService | 7 | 5 |
| `MetricsPublisher` | metrics_publisher | - | 1 | 4 |
| `FallbackStrategyService` | fallback_strategy | - | 6 | 4 |
| `ContractService` | contract_service | BaseService | 7 | 3 |
| `ValidationResult` | validation_service | - | 3 | 3 |
| `ValidationService` | validation_service | - | 4 | 3 |
| `SQLCorrectionEngine` | correction | BaseService | 10 | 3 |
| `SQLGenerationService` | service | BaseService | 8 | 3 |
| `ServiceNotReadyError` | service_not_ready | Exception | 1 | 2 |
| `PromptBuilderService` | base_behavior_pattern | - | 8 | 2 |
| `DocumentIndexingService` | document_indexing_service | - | 1 | 2 |
| `MetricsContext` | metrics_publisher | - | 2 | 2 |
| `TableDescriptionService` | table_description_service | BaseService | 6 | 2 |
| `SQLGenerationResult` | service | - | 0 | 2 |
| `SQLQueryService` | service | BaseService | 5 | 2 |
| `SQLValidatorService` | service | BaseService | 10 | 2 |
| `ServiceExecutionError` | __init__ | ExecutionError | 0 | 1 |
| `CapabilityResolverService` | base_behavior_pattern | - | 5 | 1 |
| `TableDescriptionServiceInput` | table_description_service | ServiceInput | 1 | 1 |
| `TableDescriptionServiceOutput` | table_description_service | ServiceOutput | 1 | 1 |
| `SQLGenerationServiceOutput` | service | BaseServiceOutput | 1 | 1 |
| `SQLQueryServiceInput` | service | ServiceInput | 1 | 1 |
| `SQLQueryServiceOutput` | service | ServiceOutput | 1 | 1 |
| `SQLValidatorServiceInput` | service | ServiceInput | 1 | 1 |
| `SQLValidatorServiceOutput` | service | ServiceOutput | 1 | 1 |
| `ValidatedSQL` | service | - | 1 | 1 |
| `__init__` | service_not_ready | 2 params | - | - |
| `get_service` | application_context | 2 params | - | - |
| `get_prompt_service` | application_context | 1 params | - | - |
| `get_contract_service` | application_context | 1 params | - | - |
| `description` | base_service | 1 params | - | - |
| `get_dependency` | base_service | 2 params | - | - |
| `_convert_params_to_input` | base_service | 2 params | - | - |
| `_get_event_type_for_success` | base_service | 1 params | - | - |
| `_execute_impl` | base_service | 4 params | - | - |

### Провайдер (97 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `StructuredOutputError` | llama_cpp_provider | Exception | 2 | 7 |
| `LLMOrchestrator` | llm_orchestrator | - | 10 | 7 |
| `BaseProvider` | base_provider | IProvider | 8 | 6 |
| `DBHealthStatus` | base | - | 0 | 6 |
| `BaseDBProvider` | base | ABC | 1 | 6 |
| `FAISSProvider` | faiss_provider | IFAISSProvider | 2 | 6 |
| `BaseLLMProvider` | base_llm | BaseProvider, ABC | 4 | 5 |
| `TextChunkingStrategy` | text_chunking_strategy | IChunkingStrategy | 6 | 4 |
| `IEmbeddingProvider` | base_embedding_provider | ABC | 1 | 3 |
| `SentenceTransformersProvider` | sentence_transformers_provider | IEmbeddingProvider | 3 | 3 |
| `LlamaCppProvider` | llama_cpp_provider | BaseLLMProvider, LLMInterface | 4 | 3 |
| `IFAISSProvider` | base_faiss_provider | ABC | 0 | 3 |
| `ProviderError` | exceptions | AgentBaseError | 1 | 2 |
| `MockProviderError` | exceptions | ProviderError | 1 | 2 |
| `ProviderHealthStatus` | base_provider | - | 0 | 2 |
| `MemoryCacheProvider` | memory_cache_provider | - | 3 | 2 |
| `PostgreSQLProvider` | postgres_provider | BaseDBProvider | 1 | 2 |
| `MockEmbeddingProvider` | mock_embedding_provider | IEmbeddingProvider | 2 | 2 |
| `CallStatus` | llm_orchestrator | str, Enum | 0 | 2 |
| `IChunkingStrategy` | chunking_strategy | ABC | 1 | 2 |
| `MockFAISSProvider` | mock_faiss_provider | IFAISSProvider | 2 | 2 |
| `ProviderInitializationError` | exceptions | ProviderError | 1 | 1 |
| `ProviderConnectionError` | exceptions | ProviderError | 1 | 1 |
| `LLMProviderType` | llm_types | str, Enum | 0 | 1 |
| `IProvider` | base_provider | ABC | 1 | 1 |
| `DBProviderFactory` | factory | - | 1 | 1 |
| `MockDBProvider` | mock_provider | BaseDBProvider | 1 | 1 |
| `LLMProviderFactory` | factory | - | 1 | 1 |
| `RetryAttempt` | llm_orchestrator | - | 0 | 1 |
| `LLMMetrics` | llm_orchestrator | - | 6 | 1 |
| `CallRecord` | llm_orchestrator | - | 2 | 1 |
| `MockLLMProvider` | mock_provider | BaseLLMProvider | 10 | 1 |
| `get_provider` | infrastructure_context | 2 params | - | - |
| `get_faiss_provider` | infrastructure_context | 2 params | - | - |
| `get_embedding_provider` | infrastructure_context | 1 params | - | - |
| `get_info` | base_provider | 1 params | - | - |
| `__init__` | base_provider | 3 params | - | - |
| `_set_healthy_status` | base_provider | 1 params | - | - |
| `_set_degraded_status` | base_provider | 1 params | - | - |
| `_set_unhealthy_status` | base_provider | 1 params | - | - |

### Обработчик (109 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `BaseSkillHandler` | base_handler | ABC | 7 | 9 |
| `ErrorCategory` | error_handler | Enum | 0 | 7 |
| `ErrorInfo` | error_handler | - | 3 | 4 |
| `SessionLogHandler` | session_log_handler | - | 3 | 4 |
| `TraceHandler` | trace_handler | - | 30 | 4 |
| `ErrorContext` | error_handler | - | 2 | 3 |
| `ExecuteScriptHandler` | execute_script_handler | BaseSkillHandler | 6 | 3 |
| `SearchBooksHandler` | search_books_handler | BaseSkillHandler | 3 | 3 |
| `SemanticSearchHandler` | semantic_search_handler | BaseSkillHandler | 4 | 3 |
| `ErrorSeverity` | error_handler | Enum | 0 | 2 |
| `MetricsEventHandler` | event_handlers | - | 2 | 2 |
| `AuditEventHandler` | event_handlers | - | 2 | 2 |
| `CreatePlanHandler` | create_plan_handler | BaseSkillHandler | 1 | 2 |
| `UpdatePlanHandler` | update_plan_handler | BaseSkillHandler | 0 | 2 |
| `GenerateFinalAnswerHandler` | generate_handler | BaseSkillHandler | 2 | 2 |
| `AnalyzeStepDataHandler` | analyze_handler | BaseSkillHandler | 3 | 2 |
| `RetryPolicy` | error_handler | - | 4 | 1 |
| `ErrorHandler` | error_handler | - | 11 | 1 |
| `DebuggingEventHandler` | event_handlers | - | 2 | 1 |
| `TerminalLogFormatter` | handlers | - | 4 | 1 |
| `TerminalLogHandler` | handlers | - | 3 | 1 |
| `LoggingToEventBusHandler` | handlers | Attribute(value=Name(id='logging', ctx=Load()), attr='Handler', ctx=Load()) | 3 | 1 |
| `FileLogFormatter` | handlers | - | 1 | 1 |
| `FileLogHandler` | handlers | - | 1 | 1 |
| `get_error_handler` | error_handler | 1 params | - | - |
| `reset_error_handler` | error_handler | 0 params | - | - |
| `create_error_handler` | error_handler | 2 params | - | - |
| `__post_init__` | error_handler | 1 params | - | - |
| `to_dict` | error_handler | 1 params | - | - |
| `error_message` | error_handler | 1 params | - | - |
| `error_type` | error_handler | 1 params | - | - |
| `should_retry` | error_handler | 5 params | - | - |
| `get_delay` | error_handler | 2 params | - | - |
| `get_total_max_delay` | error_handler | 1 params | - | - |
| `__repr__` | error_handler | 1 params | - | - |
| `__init__` | error_handler | 3 params | - | - |
| `_register_default_handlers` | error_handler | 1 params | - | - |
| `register_handler` | error_handler | 5 params | - | - |
| `_classify_category` | error_handler | 2 params | - | - |
| `_classify_severity` | error_handler | 3 params | - | - |

### Ошибка (67 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `ValidationError` | exceptions | AgentBaseError | 1 | 13 |
| `ExecutionError` | __init__ | AgentError | 0 | 9 |
| `StructuredOutputError` | exceptions | AgentBaseError | 1 | 7 |
| `ErrorType` | execution_trace | Enum | 0 | 7 |
| `ErrorCategory` | common_enums | str, Enum | 0 | 7 |
| `InfrastructureError` | exceptions | AgentBaseError | 1 | 6 |
| `VersionNotFoundError` | version_not_found | Exception | 1 | 5 |
| `ExecutionErrorInfo` | retry_policy | - | 0 | 5 |
| `TimeoutError` | __init__ | ExecutionError | 0 | 4 |
| `ComponentNotFoundError` | component_discovery | Exception | 1 | 3 |
| `ComponentInitializationError` | exceptions | ComponentError | 1 | 3 |
| `VectorSearchError` | exceptions | InfrastructureError | 1 | 3 |
| `DataNotFoundError` | exceptions | AgentBaseError | 1 | 3 |
| `DataError` | exceptions | AgentBaseError | 1 | 3 |
| `ComponentError` | exceptions | AgentBaseError | 1 | 2 |
| `SecurityError` | exceptions | AgentBaseError | 1 | 2 |
| `ContractValidationError` | exceptions | ContractError | 1 | 2 |
| `PromptNotFoundError` | exceptions | PromptError | 1 | 2 |
| `SQLGenerationError` | exceptions | AgentBaseError | 1 | 2 |
| `SQLValidationError` | exceptions | AgentBaseError | 1 | 2 |
| `ResourceLoadError` | exceptions | InfrastructureError | 1 | 2 |
| `PermissionDeniedError` | authorizer | Exception | 1 | 2 |
| `ErrorDetail` | execution_trace | - | 1 | 2 |
| `ArchitectureViolationError` | architecture_violation | Exception | 2 | 2 |
| `CircularDependencyError` | architecture_violation | ArchitectureViolationError | 0 | 2 |
| `DependencyResolutionError` | architecture_violation | ArchitectureViolationError | 0 | 2 |
| `InvalidDecisionError` | architecture_violation | AgentError | 1 | 2 |
| `ErrorExample` | example_extractor | - | 2 | 2 |
| `ComponentLoadError` | component_discovery | Exception | 1 | 1 |
| `ComponentExecutionError` | exceptions | ComponentError | 1 | 1 |
| `AuthenticationError` | exceptions | SecurityError | 1 | 1 |
| `AuthorizationError` | exceptions | SecurityError | 1 | 1 |
| `ContractError` | exceptions | AgentBaseError | 1 | 1 |
| `PromptError` | exceptions | AgentBaseError | 1 | 1 |
| `PatternError` | architecture_violation | AgentError | 1 | 1 |
| `ComponentNotReadyError` | __init__ | ComponentError | 0 | 1 |
| `DependencyError` | __init__ | AgentError | 0 | 1 |
| `DependencyNotFoundError` | __init__ | DependencyError | 0 | 1 |
| `PromptValidationError` | __init__ | ValidationError | 0 | 1 |
| `ManifestValidationError` | __init__ | ValidationError | 0 | 1 |

### Хранилище (85 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `IMetricsStorage` | metrics_log_interfaces | ABC | 0 | 5 |
| `LogStorageInterface` | log_storage | Protocol | 0 | 4 |
| `MetricsStorageInterface` | metrics_storage | Protocol | 0 | 4 |
| `ResourceDataSource` | resource_data_source | ABC | 7 | 4 |
| `FileSystemMetricsStorage` | metrics_storage | Subscript(value=Name(id='FileSystemStorage', ctx=Load()), slice=Name(id='MetricRecord', ctx=Load()), ctx=Load()), IMetricsStorage | 12 | 3 |
| `ILogStorage` | metrics_log_interfaces | ABC | 0 | 3 |
| `FileSystemDataSource` | file_system_data_source | ResourceDataSource | 15 | 3 |
| `FileSystemStorage` | base_storage | Subscript(value=Name(id='Generic', ctx=Load()), slice=Name(id='T', ctx=Load()), ctx=Load()) | 10 | 3 |
| `StorageError` | exceptions | AgentBaseError | 1 | 1 |
| `StorageNotFoundError` | exceptions | StorageError | 1 | 1 |
| `FileSystemLogStorage` | log_storage | Subscript(value=Name(id='FileSystemStorage', ctx=Load()), slice=Name(id='LogEntry', ctx=Load()), ctx=Load()), ILogStorage | 11 | 1 |
| `StoragePort` | ports | Protocol | 0 | 1 |
| `IStorageResult` | storage_interfaces | ABC | 2 | 1 |
| `IPromptStorage` | storage_interfaces | ABC | 0 | 1 |
| `IContractStorage` | storage_interfaces | ABC | 0 | 1 |
| `IDataSource` | data_source | ABC | 0 | 1 |
| `MockDatabaseResourceDataSource` | mock_database_resource_data_source | ResourceDataSource | 12 | 1 |
| `VersionedStorage` | versioned_storage | ABC, Subscript(value=Name(id='Generic', ctx=Load()), slice=Name(id='T', ctx=Load()), ctx=Load()) | 12 | 1 |
| `BehaviorStorage` | behavior_storage | - | 3 | 1 |
| `__init__` | log_storage | 2 params | - | - |
| `_parse_item` | log_storage | 2 params | - | - |
| `_item_to_dict` | log_storage | 2 params | - | - |
| `_load_json_file` | log_storage | 2 params | - | - |
| `_save_json_file` | log_storage | 3 params | - | - |
| `_parse_log_entry` | log_storage | 2 params | - | - |
| `_get_agent_session_dir` | log_storage | 3 params | - | - |
| `_get_capability_dir` | log_storage | 2 params | - | - |
| `_get_all_logs_file` | log_storage | 2 params | - | - |
| `_get_agent_session_file` | log_storage | 3 params | - | - |
| `_get_capability_file` | log_storage | 2 params | - | - |
| `_load_metrics_file` | metrics_storage | 2 params | - | - |
| `_save_metrics_file` | metrics_storage | 3 params | - | - |
| `_load_metrics_from_file` | metrics_storage | 2 params | - | - |
| `_get_version_dir` | metrics_storage | 3 params | - | - |
| `_get_metrics_file` | metrics_storage | 4 params | - | - |
| `_get_aggregated_file` | metrics_storage | 3 params | - | - |
| `_get_latest_file` | metrics_storage | 2 params | - | - |
| `_update_latest_metrics` | metrics_storage | 2 params | - | - |
| `get_prompt_storage` | infrastructure_context | 1 params | - | - |
| `get_contract_storage` | infrastructure_context | 1 params | - | - |

### Агент (101 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `ExecutionContext` | action_executor | - | 1 | 19 |
| `ActionExecutor` | action_executor | - | 18 | 13 |
| `AgentPolicy` | policy | - | 5 | 7 |
| `FailureMemory` | failure_memory | - | 13 | 5 |
| `ErrorClassifier` | error_classifier | - | 3 | 4 |
| `ReasoningResult` | validation | - | 1 | 4 |
| `AgentError` | exceptions | AgentBaseError | 1 | 3 |
| `AgentStep` | model | - | 0 | 3 |
| `SafeExecutor` | safe_executor | - | 4 | 3 |
| `ValidationResult` | schema_validator | - | 2 | 3 |
| `AnalysisResult` | validation | - | 0 | 3 |
| `AgentStuckError` | architecture_violation | AgentError | 1 | 2 |
| `FailureRecord` | failure_memory | - | 3 | 2 |
| `StrategyDecisionType` | model | Enum | 0 | 2 |
| `ProgressScorer` | progress | - | 2 | 2 |
| `AgentState` | state | - | 5 | 2 |
| `AgentBaseError` | exceptions | Exception | 2 | 1 |
| `AgentInitializationError` | exceptions | AgentError | 1 | 1 |
| `AgentExecutionError` | exceptions | AgentError | 1 | 1 |
| `AgentTimeoutError` | exceptions | AgentExecutionError | 1 | 1 |
| `AgentMaxStepsError` | exceptions | AgentExecutionError | 1 | 1 |
| `ProgressMetrics` | runtime | - | 2 | 1 |
| `AgentRuntime` | runtime | - | 7 | 1 |
| `StrategyDecision` | model | - | 1 | 1 |
| `AgentStateSnapshot` | state | - | 3 | 1 |
| `ParameterSchema` | schema_validator | - | 0 | 1 |
| `CapabilitySchema` | schema_validator | - | 2 | 1 |
| `SchemaValidator` | schema_validator | - | 7 | 1 |
| `ContextAnalysis` | utils | - | 0 | 1 |
| `DecisionResult` | validation | - | 0 | 1 |
| `get_sessions_by_agent` | unified_event_bus | 2 params | - | - |
| `update_strategy_effectiveness` | runtime | 3 params | - | - |
| `get_state_metrics` | runtime | 1 params | - | - |
| `__init__` | runtime | 7 params | - | - |
| `_is_final_result` | runtime | 2 params | - | - |
| `is_running` | runtime | 1 params | - | - |
| `_update_state` | runtime | 2 params | - | - |
| `_should_stop` | runtime | 2 params | - | - |
| `_should_stop_early` | runtime | 1 params | - | - |
| `_log_debug` | action_executor | 2 params | - | - |

### Поведение (45 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `BehaviorDecisionType` | base | Enum | 0 | 8 |
| `BehaviorDecision` | base | - | 0 | 8 |
| `BaseBehaviorPattern` | base_behavior_pattern | BaseComponent, BehaviorPatternInterface | 8 | 5 |
| `PlanningPattern` | pattern | BaseBehaviorPattern | 4 | 4 |
| `BehaviorPatternInterface` | base | ABC | 1 | 3 |
| `EvaluationPattern` | pattern | BaseBehaviorPattern | 3 | 3 |
| `ReActPattern` | pattern | BaseBehaviorPattern | 5 | 3 |
| `BehaviorManager` | behavior_manager | - | 4 | 2 |
| `ReActInput` | base | BehaviorInput | 1 | 1 |
| `ReActOutput` | base | BehaviorOutput | 1 | 1 |
| `PlanningInput` | base | BehaviorInput | 1 | 1 |
| `PlanningOutput` | base | BehaviorOutput | 1 | 1 |
| `BehaviorInput` | base | - | 0 | - |
| `BehaviorOutput` | base | - | 0 | - |
| `__init__` | base | 5 params | - | - |
| `_filter_capabilities` | base | 2 params | - | - |
| `build_reasoning_prompt` | base_behavior_pattern | 6 params | - | - |
| `_build_input_context` | base_behavior_pattern | 3 params | - | - |
| `_build_step_history` | base_behavior_pattern | 3 params | - | - |
| `_extract_last_observation` | base_behavior_pattern | 3 params | - | - |
| `_extract_observations_from_step` | base_behavior_pattern | 3 params | - | - |
| `_format_small_data` | base_behavior_pattern | 2 params | - | - |
| `_render_prompt` | base_behavior_pattern | 3 params | - | - |
| `find_capability` | base_behavior_pattern | 3 params | - | - |
| `validate_parameters` | base_behavior_pattern | 5 params | - | - |
| `register_capability_schemas` | base_behavior_pattern | 5 params | - | - |
| `filter_capabilities` | base_behavior_pattern | 3 params | - | - |
| `exclude_capability` | base_behavior_pattern | 3 params | - | - |
| `get_prompt` | base_behavior_pattern | 2 params | - | - |
| `get_input_contract` | base_behavior_pattern | 2 params | - | - |
| `get_output_contract` | base_behavior_pattern | 2 params | - | - |
| `_get_event_type_for_success` | base_behavior_pattern | 1 params | - | - |
| `_execute_impl` | base_behavior_pattern | 4 params | - | - |
| `_safe_async_call` | base_behavior_pattern | 3 params | - | - |
| `get_behavior_pattern` | application_context | 2 params | - | - |
| `llm_orchestrator` | pattern | 1 params | - | - |
| `_inject_schema_into_system_prompt` | pattern | 3 params | - | - |
| `_is_plan_completed` | pattern | 2 params | - | - |
| `_are_dependencies_met` | pattern | 3 params | - | - |
| `_build_wait_decision` | pattern | 2 params | - | - |

### Инструмент (27 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `BaseTool` | base_tool | BaseComponent | 1 | 6 |
| `ToolInput` | base_tool | ABC | 0 | 4 |
| `SQLTool` | sql_tool | BaseTool | 7 | 4 |
| `ToolOutput` | base_tool | ABC | 0 | 3 |
| `FileTool` | file_tool | BaseTool | 6 | 3 |
| `VectorBooksTool` | vector_books_tool | BaseTool | 3 | 3 |
| `FileToolInput` | file_tool | ToolInput | 1 | 2 |
| `SQLToolInput` | sql_tool | ToolInput | 0 | 2 |
| `ToolExecutionError` | __init__ | ExecutionError | 0 | 1 |
| `FileToolOutput` | file_tool | ToolOutput | 1 | 1 |
| `SQLToolOutput` | sql_tool | ToolOutput | 0 | 1 |
| `__init__` | base_tool | 4 params | - | - |
| `_format_available_tools` | base_behavior_pattern | 3 params | - | - |
| `get_tool` | application_context | 2 params | - | - |
| `description` | base_tool | 1 params | - | - |
| `_get_event_type_for_success` | base_tool | 1 params | - | - |
| `_execute_impl` | base_tool | 4 params | - | - |
| `execute_specific` | base_tool | 2 params | - | - |
| `_convert_params_to_input` | base_tool | 2 params | - | - |
| `_get_component_type` | base_tool | 1 params | - | - |
| `get_allowed_operations` | base_tool | 1 params | - | - |
| `is_side_effects_enabled` | base_tool | 1 params | - | - |
| `get_capabilities` | base_tool | 1 params | - | - |
| `_is_write_operation` | file_tool | 2 params | - | - |
| `_safe_async_call` | file_tool | 3 params | - | - |
| `_is_write_query` | sql_tool | 2 params | - | - |
| `_get_infrastructure` | vector_books_tool | 1 params | - | - |

### Навык (25 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `BaseSkill` | base_skill | BaseComponent | 8 | 15 |
| `BookLibrarySkill` | skill | BaseSkill | 4 | 5 |
| `SkillExecutionError` | exceptions | ComponentExecutionError | 1 | 4 |
| `DataAnalysisSkill` | skill | BaseSkill | 6 | 2 |
| `FinalAnswerSkill` | skill | BaseSkill | 5 | 2 |
| `PlanningSkill` | skill | BaseComponent | 4 | 2 |
| `get_skill` | application_context | 2 params | - | - |
| `__init__` | base_skill | 6 params | - | - |
| `is_preloaded` | base_skill | 1 params | - | - |
| `get_capability_names` | base_skill | 1 params | - | - |
| `_get_component_type` | base_skill | 1 params | - | - |
| `get_required_capabilities_from_manifest` | base_skill | 1 params | - | - |
| `get_capabilities` | base_skill | 1 params | - | - |
| `get_capability_by_name` | base_skill | 2 params | - | - |
| `_get_event_type_for_success` | base_skill | 1 params | - | - |
| `create_book_library_skill` | skill | 4 params | - | - |
| `_get_allowed_scripts` | skill | 1 params | - | - |
| `_render_prompt` | skill | 3 params | - | - |
| `_parse_llm_response` | skill | 2 params | - | - |
| `_validate_output` | skill | 3 params | - | - |
| `_render_prompt_fallback` | skill | 9 params | - | - |
| `_build_steps_summary` | skill | 2 params | - | - |
| `serialize_for_prompt` | skill | 1 params | - | - |
| `format_book_data` | skill | 1 params | - | - |
| `_format_capabilities` | skill | 2 params | - | - |

### Обнаружение (35 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `ComponentStatus` | component_discovery | Enum | 0 | 5 |
| `ResourceDiscovery` | resource_discovery | - | 17 | 4 |
| `ComponentInfo` | component_discovery | - | 2 | 1 |
| `ComponentDiscovery` | component_discovery | - | 11 | 1 |
| `get_component_discovery` | component_discovery | 0 params | - | - |
| `create_component_discovery` | component_discovery | 1 params | - | - |
| `reset_component_discovery` | component_discovery | 0 params | - | - |
| `to_dict` | component_discovery | 1 params | - | - |
| `from_manifest` | component_discovery | 3 params | - | - |
| `__init__` | component_discovery | 3 params | - | - |
| `_register_component` | component_discovery | 2 params | - | - |
| `register_component_class` | component_discovery | 3 params | - | - |
| `get_component` | component_discovery | 2 params | - | - |
| `get_all_components` | component_discovery | 1 params | - | - |
| `get_by_type` | component_discovery | 2 params | - | - |
| `get_by_status` | component_discovery | 2 params | - | - |
| `has_component` | component_discovery | 2 params | - | - |
| `has_component_class` | component_discovery | 2 params | - | - |
| `validate_dependencies` | component_discovery | 2 params | - | - |
| `get_discovery_stats` | component_discovery | 1 params | - | - |
| `_log_info` | resource_discovery | 2 params | - | - |
| `_log_debug` | resource_discovery | 2 params | - | - |
| `_log_warning` | resource_discovery | 2 params | - | - |
| `_should_load_resource` | resource_discovery | 3 params | - | - |
| `_parse_prompt_file` | resource_discovery | 2 params | - | - |
| `_parse_contract_file` | resource_discovery | 2 params | - | - |
| `_infer_component_type_from_path` | resource_discovery | 2 params | - | - |
| `_infer_direction_from_filename` | resource_discovery | 2 params | - | - |
| `_parse_contract_filename` | resource_discovery | 2 params | - | - |
| `discover_prompts` | resource_discovery | 1 params | - | - |
| `discover_contracts` | resource_discovery | 1 params | - | - |
| `get_prompt` | resource_discovery | 3 params | - | - |
| `get_contract` | resource_discovery | 4 params | - | - |
| `get_stats` | resource_discovery | 1 params | - | - |
| `get_validation_report` | resource_discovery | 1 params | - | - |

### Логирование (29 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `EventBusLogger` | logger | SyncLoggerMixin, AsyncLoggerMixin | 1 | 37 |
| `LoggerInitializationState` | logger | Enum | 0 | 2 |
| `DummyLogger` | data_repository | - | 5 | 1 |
| `StructuredLoggerMixin` | structured | - | 2 | 1 |
| `ContextualLoggerMixin` | structured | - | 2 | 1 |
| `SyncLoggerWrapper` | application_context | - | 6 | 1 |
| `_get_logger_init_state` | base_component | 1 params | - | - |
| `_init_event_bus_logger` | logging | 2 params | - | - |
| `SyncLoggerMixin` | logger | - | 6 | - |
| `AsyncLoggerMixin` | logger | - | 4 | - |
| `LLMMixin` | logger | - | 0 | - |
| `SessionMixin` | logger | - | 0 | - |
| `SelfImprovementMixin` | logger | - | 0 | - |
| `create_logger` | logger | 4 params | - | - |
| `get_session_logger` | logger | 2 params | - | - |
| `get_global_logger` | logger | 0 params | - | - |
| `_write_sync` | logger | 4 params | - | - |
| `_write_fallback` | logger | 4 params | - | - |
| `info_sync` | logger | 2 params | - | - |
| `debug_sync` | logger | 2 params | - | - |
| `warning_sync` | logger | 2 params | - | - |
| `error_sync` | logger | 2 params | - | - |
| `_is_initializing` | logger | 1 params | - | - |
| `_set_initializing` | logger | 1 params | - | - |
| `_set_ready` | logger | 1 params | - | - |
| `_publish_sync` | logger | 4 params | - | - |
| `__init__` | logger | 6 params | - | - |
| `patch_event_bus_logger` | structured | 0 params | - | - |
| `logger` | action_executor | 1 params | - | - |

### Менеджер (20 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `VersionManager` | version_manager | - | 3 | 4 |
| `SecurityResourceType` | security_manager | Enum | 0 | 2 |
| `SecurityError` | security_manager | Exception | 2 | 2 |
| `SecurityAction` | security_manager | Enum | 0 | 1 |
| `SecurityAuditEvent` | security_manager | - | 1 | 1 |
| `SecurityManager` | security_manager | - | 6 | 1 |
| `VersionRegistry` | version_manager | - | 0 | 1 |
| `get_security_manager` | security_manager | 0 params | - | - |
| `create_security_manager` | security_manager | 1 params | - | - |
| `reset_security_manager` | security_manager | 0 params | - | - |
| `to_dict` | security_manager | 1 params | - | - |
| `__init__` | security_manager | 2 params | - | - |
| `_detect_sql_injection` | security_manager | 2 params | - | - |
| `_is_path_traversal` | security_manager | 2 params | - | - |
| `_is_forbidden_path` | security_manager | 2 params | - | - |
| `get_audit_log` | security_manager | 2 params | - | - |
| `get_stats` | security_manager | 1 params | - | - |
| `get_encoding_manager` | encoding | 0 params | - | - |
| `reset_event_bus_manager` | __init__ | 0 params | - | - |
| `_get_registry` | version_manager | 2 params | - | - |

### Интерфейс (14 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `EventBusInterface` | event_bus | Protocol | 3 | 5 |
| `LLMInterface` | llm | Protocol | 0 | 3 |
| `CacheInterface` | cache | Protocol | 1 | 2 |
| `DatabaseInterface` | database | Protocol | 0 | 2 |
| `VectorInterface` | vector | Protocol | 0 | 2 |
| `DatabasePort` | ports | Protocol | 0 | 1 |
| `LLMPort` | ports | Protocol | 0 | 1 |
| `VectorPort` | ports | Protocol | 0 | 1 |
| `CachePort` | ports | Protocol | 0 | 1 |
| `EventPort` | ports | Protocol | 2 | 1 |
| `MetricsPort` | ports | Protocol | 0 | 1 |
| `stats` | cache | 1 params | - | - |
| `subscribe` | event_bus | 4 params | - | - |
| `unsubscribe` | event_bus | 3 params | - | - |

### Базовый класс (13 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `BaseComponent` | base_component | LifecycleMixin, LoggingMixin | 9 | 20 |
| `BaseEventCollector` | base_collector | ABC | 4 | 3 |
| `RoleBasedAuthorizer` | authorizer | - | 1 | 1 |
| `__init__` | base_component | 6 params | - | - |
| `get_prompt` | base_component | 2 params | - | - |
| `get_input_contract` | base_component | 2 params | - | - |
| `get_output_contract` | base_component | 2 params | - | - |
| `validate_input_typed` | base_component | 3 params | - | - |
| `validate_output_typed` | base_component | 3 params | - | - |
| `render_prompt` | base_component | 2 params | - | - |
| `_subscribe` | base_collector | 3 params | - | - |
| `is_initialized` | base_collector | 1 params | - | - |
| `subscriptions_count` | base_collector | 1 params | - | - |

### Сборщик (10 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `TraceCollector` | trace_collector | - | 4 | 4 |
| `MetricsCollector` | metrics_collector | BaseEventCollector | 1 | 3 |
| `LogCollector` | log_collector | BaseEventCollector | 3 | 1 |
| `__init__` | log_collector | 3 params | - | - |
| `_subscribe` | log_collector | 3 params | - | - |
| `_sanitize_data` | log_collector | 2 params | - | - |
| `from_trace_collector` | dataset_builder | 3 params | - | - |
| `_balance_traces` | trace_collector | 2 params | - | - |
| `_trace_to_sample` | trace_collector | 2 params | - | - |
| `get_collection_stats` | trace_collector | 2 params | - | - |

### Реестр (11 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `ComponentRegistry` | component_registry | - | 9 | 3 |
| `ActionSchemaRegistry` | structured_actions | - | 3 | - |
| `__init__` | component_registry | 1 params | - | - |
| `register` | component_registry | 4 params | - | - |
| `get` | component_registry | 3 params | - | - |
| `all_of_type` | component_registry | 2 params | - | - |
| `all_components` | component_registry | 1 params | - | - |
| `clear` | component_registry | 1 params | - | - |
| `count` | component_registry | 2 params | - | - |
| `exists` | component_registry | 3 params | - | - |
| `__repr__` | component_registry | 1 params | - | - |

### Валидатор (10 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `TemplateValidatorMixin` | base_template_validator | - | 2 | 2 |
| `SQLSecurityValidator` | security_manager | SecurityValidator | 2 | 1 |
| `FileSecurityValidator` | security_manager | SecurityValidator | 3 | 1 |
| `SecurityValidator` | security_manager | - | 1 | - |
| `_register_default_validators` | security_manager | 1 params | - | - |
| `register_validator` | security_manager | 3 params | - | - |
| `get_validator` | security_manager | 2 params | - | - |
| `validate_jinja_template` | base_template_validator | 5 params | - | - |
| `validate_templates` | base_template_validator | 1 params | - | - |
| `ActionValidator` | structured_actions | - | 2 | - |

### Фабрика (8 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `ComponentFactory` | component_factory | - | 4 | 3 |
| `ProfileType` | factory | Enum | 0 | 1 |
| `VersionValidationError` | factory | Exception | 0 | 1 |
| `AgentFactory` | factory | - | 2 | 1 |
| `__init__` | factory | 2 params | - | - |
| `_get_resource_preloader` | component_factory | 2 params | - | - |
| `PlanningPatternFactory` | factory | - | 1 | - |
| `create_pattern` | factory | 2 params | - | - |

### Загрузчик (3 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `ResourcePreloader` | resource_preloader | - | 2 | 3 |
| `__init__` | resource_preloader | 3 params | - | - |
| `__repr__` | resource_preloader | 1 params | - | - |

### Миксин (2 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `LifecycleMixin` | lifecycle | - | 8 | 2 |
| `LoggingMixin` | logging | - | 3 | 1 |

### Исключение (1 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `exception` | data_repository | 2 params | - | - |

### Исполнитель (1 уникальных)

| Имя | Файл | Базовые/Параметры | Методы | Использ. |
|-----|------|-------------------|--------|----------|
| `set_executor_callback` | orchestrator | 2 params | - | - |

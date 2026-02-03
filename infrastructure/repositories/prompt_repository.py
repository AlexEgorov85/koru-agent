from typing import Optional, List, Dict, Any
from domain.models.prompt.prompt_version import PromptVersion, PromptStatus, PromptRole, PromptUsageMetrics, PromptExecutionSnapshot, VariableSchema
from domain.abstractions.prompt_repository import IPromptRepository, ISnapshotManager
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from infrastructure.gateways.database_providers.base_provider import BaseDBProvider
import json

class DatabasePromptRepository(IPromptRepository):
    """Репозиторий промтов с использованием существующего BaseDBProvider"""
    
    def __init__(self, db_provider: BaseDBProvider):
        self._db_provider = db_provider
    
    async def get_active_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить активную версию промта по адресу"""
        query = """
        SELECT * FROM prompt_versions 
        WHERE domain = $1 AND capability_name = $2 
        AND provider_type = $3 AND role = $4 
        AND status = $5
        ORDER BY activation_date DESC LIMIT 1
        """
        
        result = await self._db_provider.execute_query(query, [domain, capability_name, provider_type, role, 'active'])
        if result:
            return self._row_to_prompt_version(result[0])
        return None
    
    async def get_shadow_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить теневую (shadow) версию для A/B тестирования"""
        query = """
        SELECT * FROM prompt_versions 
        WHERE domain = $1 AND capability_name = $2 
        AND provider_type = $3 AND role = $4 
        AND status = $5
        ORDER BY activation_date DESC LIMIT 1
        """
        
        result = await self._db_provider.execute_query(query, [domain, capability_name, provider_type, role, 'shadow'])
        if result:
            return self._row_to_prompt_version(result[0])
        return None
    
    async def get_version_by_id(self, version_id: str) -> Optional[PromptVersion]:
        """Получить версию промта по ID"""
        query = "SELECT * FROM prompt_versions WHERE id = $1"
        
        result = await self._db_provider.execute_query(query, [version_id])
        if result:
            return self._row_to_prompt_version(result[0])
        return None
    
    async def save_version(self, version: PromptVersion) -> None:
        """Сохранить новую версию промта"""
        query = """
        INSERT INTO prompt_versions (
            id, semantic_version, domain, provider_type, capability_name, role,
            content, variables_schema, expected_response_schema, status,
            created_at, activation_date, deprecation_date, archived_date,
            parent_version_id, version_notes, usage_count, success_count,
            avg_generation_time, last_used_at, error_rate, rejection_count
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
        """
        
        values = self._prompt_version_to_values(version)
        await self._db_provider.execute_query(query, values)
    
    async def update_version_status(self, version_id: str, status: PromptStatus) -> None:
        """Обновить статус версии промта"""
        field_name = None
        if status == PromptStatus.ACTIVE:
            field_name = "activation_date"
        elif status == PromptStatus.DEPRECATED:
            field_name = "deprecation_date"
        elif status == PromptStatus.ARCHIVED:
            field_name = "archived_date"
        
        if field_name:
            query = f"UPDATE prompt_versions SET status = $1, {field_name} = CURRENT_TIMESTAMP WHERE id = $2"
        else:
            query = "UPDATE prompt_versions SET status = $1 WHERE id = $2"
        
        await self._db_provider.execute_query(query, [status.value, version_id])
    
    async def activate_version(self, version_id: str) -> None:
        """Активировать версию промта (и деактивировать текущую активную)"""
        # Получаем информацию о текущей версии для определения адреса
        current_version = await self.get_version_by_id(version_id)
        if not current_version:
            raise ValueError(f"Version with ID {version_id} not found")
        
        # Деактивировать текущую активную версию для этого адреса
        deactivate_query = """
        UPDATE prompt_versions SET status = 'deprecated', deprecation_date = CURRENT_TIMESTAMP
        WHERE domain = $1 AND capability_name = $2 AND provider_type = $3 AND role = $4 AND status = $5
        """
        await self._db_provider.execute_query(
            deactivate_query,
            [
                current_version.domain.value,
                current_version.capability_name,
                current_version.provider_type.value,
                current_version.role.value,
                'active'
            ]
        )
        
        # Активировать новую версию
        activate_query = """
        UPDATE prompt_versions SET status = 'active', activation_date = CURRENT_TIMESTAMP
        WHERE id = $1
        """
        await self._db_provider.execute_query(activate_query, [version_id])
    
    async def archive_version(self, version_id: str) -> None:
        """Архивировать версию промта"""
        query = """
        UPDATE prompt_versions 
        SET status = 'archived', archived_date = CURRENT_TIMESTAMP 
        WHERE id = $1
        """
        await self._db_provider.execute_query(query, [version_id])
    
    async def list_versions(self, capability_name: str) -> List[PromptVersion]:
        """Получить все версии для конкретной capability"""
        query = "SELECT * FROM prompt_versions WHERE capability_name = $1 ORDER BY created_at DESC"
        
        result = await self._db_provider.execute_query(query, [capability_name])
        return [self._row_to_prompt_version(row) for row in result] if result else []
    
    async def list_versions_by_address(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> List[PromptVersion]:
        """Получить все версии по адресу"""
        query = """
        SELECT * FROM prompt_versions 
        WHERE domain = $1 AND capability_name = $2 
        AND provider_type = $3 AND role = $4 
        ORDER BY created_at DESC
        """
        
        result = await self._db_provider.execute_query(query, [domain, capability_name, provider_type, role])
        return [self._row_to_prompt_version(row) for row in result] if result else []
    
    async def update_usage_metrics(
        self,
        version_id: str,
        metrics_update: PromptUsageMetrics
    ) -> None:
        """Обновить метрики использования версии промта"""
        # В GreenPlum сложные математические выражения могут работать медленнее
        # Поэтому сначала получим текущие метрики, а потом обновим
        current_version = await self.get_version_by_id(version_id)
        if not current_version:
            return
        
        current_metrics = current_version.usage_metrics
        total_usage = current_metrics.usage_count + metrics_update.usage_count
        
        if total_usage > 0:
            # Рассчитываем новые средние значения
            new_avg_time = (
                (current_metrics.avg_generation_time * current_metrics.usage_count + 
                 metrics_update.avg_generation_time * metrics_update.usage_count) / total_usage
            )
            
            new_error_rate = (
                (current_metrics.error_rate * current_metrics.usage_count + 
                 metrics_update.error_rate * metrics_update.usage_count) / total_usage
            )
        else:
            new_avg_time = 0.0
            new_error_rate = 0.0
        
        query = """
        UPDATE prompt_versions 
        SET 
            usage_count = usage_count + $1,
            success_count = success_count + $2,
            avg_generation_time = $3,
            last_used_at = COALESCE($4, last_used_at),
            error_rate = $5,
            rejection_count = rejection_count + $6
        WHERE id = $7
        """
        
        await self._db_provider.execute_query(
            query,
            [
                metrics_update.usage_count,
                metrics_update.success_count,
                new_avg_time,
                metrics_update.last_used_at,
                new_error_rate,
                metrics_update.rejection_count,
                version_id
            ]
        )
    
    def _row_to_prompt_version(self, row: Dict[str, Any]) -> PromptVersion:
        """Конвертировать строку БД в объект PromptVersion"""
        # Конвертируем JSON строки в объекты
        variables_schema_data = json.loads(row['variables_schema']) if row['variables_schema'] else []
        variables_schema = [
            VariableSchema(**var_data) for var_data in variables_schema_data
        ]
        
        # Создаем объект PromptVersion
        return PromptVersion(
            id=row['id'],
            semantic_version=row['semantic_version'],
            domain=DomainType(row['domain']),
            provider_type=LLMProviderType(row['provider_type']),
            capability_name=row['capability_name'],
            role=PromptRole(row['role']),
            content=row['content'],
            variables_schema=variables_schema,
            expected_response_schema=json.loads(row['expected_response_schema']) if row['expected_response_schema'] else None,
            status=PromptStatus(row['status']),
            created_at=row['created_at'],
            activation_date=row['activation_date'],
            deprecation_date=row['deprecation_date'],
            archived_date=row['archived_date'],
            parent_version_id=row['parent_version_id'],
            version_notes=row['version_notes'],
            usage_metrics=PromptUsageMetrics(
                usage_count=row['usage_count'],
                success_count=row['success_count'],
                avg_generation_time=row['avg_generation_time'],
                last_used_at=row['last_used_at'],
                error_rate=row['error_rate'],
                rejection_count=row['rejection_count']
            )
        )
    
    def _prompt_version_to_values(self, version: PromptVersion) -> tuple:
        """Конвертировать объект PromptVersion в кортеж значений для SQL"""
        return (
            version.id,
            version.semantic_version,
            version.domain.value,
            version.provider_type.value,
            version.capability_name,
            version.role.value,
            version.content,
            json.dumps([var.dict() for var in version.variables_schema]),
            json.dumps(version.expected_response_schema) if version.expected_response_schema else None,
            version.status.value,
            version.created_at,
            version.activation_date,
            version.deprecation_date,
            version.archived_date,
            version.parent_version_id,
            version.version_notes,
            version.usage_metrics.usage_count,
            version.usage_metrics.success_count,
            version.usage_metrics.avg_generation_time,
            version.usage_metrics.last_used_at,
            version.usage_metrics.error_rate,
            version.usage_metrics.rejection_count
        )


class DatabaseSnapshotManager(ISnapshotManager):
    """Менеджер снапшотов с использованием существующего BaseDBProvider"""
    
    def __init__(self, db_provider: BaseDBProvider):
        self._db_provider = db_provider
    
    async def save_snapshot(self, snapshot: PromptExecutionSnapshot) -> None:
        """Сохранить снапшот выполнения промта"""
        query = """
        INSERT INTO prompt_execution_snapshots (
            id, prompt_id, session_id, rendered_prompt, variables,
            response, execution_time, timestamp, success,
            error_message, rejection_reason, provider_response_time
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """
        
        values = (
            snapshot.id,
            snapshot.prompt_id,
            snapshot.session_id,
            snapshot.rendered_prompt,
            json.dumps(snapshot.variables),
            snapshot.response,
            snapshot.execution_time,
            snapshot.timestamp,
            snapshot.success,
            snapshot.error_message,
            snapshot.rejection_reason,
            snapshot.provider_response_time
        )
        
        await self._db_provider.execute_query(query, values)
    
    async def get_snapshots_by_prompt_id(self, prompt_id: str, limit: int = 100) -> List[PromptExecutionSnapshot]:
        """Получить снапшоты для конкретного промта"""
        query = """
        SELECT * FROM prompt_execution_snapshots 
        WHERE prompt_id = $1 
        ORDER BY timestamp DESC 
        LIMIT $2
        """
        
        result = await self._db_provider.execute_query(query, [prompt_id, limit])
        return [self._row_to_snapshot(row) for row in result] if result else []
    
    async def get_snapshots_by_session_id(self, session_id: str) -> List[PromptExecutionSnapshot]:
        """Получить снапшоты для конкретной сессии"""
        query = "SELECT * FROM prompt_execution_snapshots WHERE session_id = $1 ORDER BY timestamp ASC"
        
        result = await self._db_provider.execute_query(query, [session_id])
        return [self._row_to_snapshot(row) for row in result] if result else []
    
    async def calculate_rejection_rate(self, prompt_id: str) -> float:
        """Вычислить процент отклонений для промта"""
        query = """
        SELECT 
            COUNT(*) as total_executions,
            SUM(CASE WHEN rejection_reason IS NOT NULL THEN 1 ELSE 0 END) as rejections
        FROM prompt_execution_snapshots 
        WHERE prompt_id = $1
        """
        
        result = await self._db_provider.execute_query(query, [prompt_id])
        if result and len(result) > 0:
            row = result[0]
            total = row['total_executions'] or 0
            rejections = row['rejections'] or 0
            return rejections / total if total > 0 else 0.0
        
        return 0.0
    
    def _row_to_snapshot(self, row: Dict[str, Any]) -> PromptExecutionSnapshot:
        """Конвертировать строку БД в объект PromptExecutionSnapshot"""
        return PromptExecutionSnapshot(
            id=row['id'],
            prompt_id=row['prompt_id'],
            session_id=row['session_id'],
            rendered_prompt=row['rendered_prompt'],
            variables=json.loads(row['variables']) if row['variables'] else {},
            response=row['response'],
            execution_time=row['execution_time'],
            timestamp=row['timestamp'],
            success=row['success'],
            error_message=row['error_message'],
            rejection_reason=row['rejection_reason'],
            provider_response_time=row['provider_response_time']
        )
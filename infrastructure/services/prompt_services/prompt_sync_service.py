import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
from datetime import datetime
from domain.models.prompt.prompt_version import PromptUsageMetrics, PromptVersion, PromptStatus, PromptRole, VariableSchema
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from infrastructure.gateways.database_providers.base_provider import BaseDBProvider
import json

class PromptFileSyncService:
    """Служба синхронизации промтов между файлами и БД через существующий DBProvider"""
    
    def __init__(self, db_provider: BaseDBProvider, fs_directory: str = "./prompts"):
        self._db_provider = db_provider
        self._fs_dir = Path(fs_directory)
    
    async def sync_from_fs_to_db(self) -> None:
        """Синхронизировать промты из файловой системы в БД"""
        if not self._fs_dir.exists():
            print(f"Директория {self._fs_dir} не существует, пропускаем синхронизацию")
            return
        
        markdown_files = list(self._fs_dir.rglob("*.md"))
        print(f"Найдено {len(markdown_files)} файлов промтов для синхронизации")
        
        for md_file in markdown_files:
            try:
                # Проверяем, изменился ли файл с последней синхронизации
                file_hash = self._calculate_file_hash(md_file)
                is_new_or_changed = await self._is_file_new_or_changed(md_file, file_hash)
                
                if is_new_or_changed:
                    prompt_version = await self._parse_markdown_file(md_file)
                    if prompt_version:
                        print(f"Обновляем/создаем версию {prompt_version.id} из файла {md_file}")
                        await self._save_to_db(prompt_version)
                        
                        # Если статус active, активируем версию
                        if prompt_version.status == PromptStatus.ACTIVE:
                            await self._activate_version(prompt_version.id)
                        
                        # Регистрируем в логе синхронизации
                        await self._log_sync(md_file, file_hash)
                else:
                    print(f"Файл {md_file} не изменился, пропускаем")
                    
            except Exception as e:
                print(f"Ошибка при синхронизации файла {md_file}: {e}")
    
    async def _is_file_new_or_changed(self, file_path: Path, file_hash: str) -> bool:
        """Проверить, новый ли это файл или он изменился"""
        query = """
        SELECT COUNT(*) as count FROM prompt_file_sync_log 
        WHERE file_path = $1 AND file_hash = $2
        """
        
        result = await self._db_provider.execute_query(
            query, [str(file_path.absolute()), file_hash]
        )
        
        if result:
            return result[0]['count'] == 0
        return True
    
    async def _save_to_db(self, version: PromptVersion) -> None:
        """Сохранить версию в БД"""
        # Проверяем, существует ли версия
        existing = await self._get_by_id(version.id)
        if existing:
            # Обновляем существующую версию
            query = """
            UPDATE prompt_versions SET
                semantic_version = $2,
                domain = $3,
                provider_type = $4,
                capability_name = $5,
                role = $6,
                content = $7,
                variables_schema = $8,
                expected_response_schema = $9,
                status = $10,
                activation_date = $11,
                deprecation_date = $12,
                archived_date = $13,
                parent_version_id = $14,
                version_notes = $15,
                usage_count = $16,
                success_count = $17,
                avg_generation_time = $18,
                last_used_at = $19,
                error_rate = $20,
                rejection_count = $21
            WHERE id = $1
            """
            values = [
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
            ]
        else:
            # Вставляем новую версию
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
    
    async def _activate_version(self, version_id: str) -> None:
        """Активировать версию"""
        query = """
        UPDATE prompt_versions SET status = 'active', activation_date = CURRENT_TIMESTAMP
        WHERE id = $1
        """
        await self._db_provider.execute_query(query, [version_id])
    
    async def _log_sync(self, file_path: Path, file_hash: str) -> None:
        """Зарегистрировать в логе синхронизации"""
        query = """
        INSERT INTO prompt_file_sync_log (file_path, file_hash, sync_status)
        VALUES ($1, $2, 'completed')
        """
        await self._db_provider.execute_query(query, [str(file_path.absolute()), hash])
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Вычислить хэш файла"""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    
    async def _parse_markdown_file(self, file_path: Path) -> Optional[PromptVersion]:
        """Парсинг markdown файла с frontmatter в PromptVersion"""
        content = file_path.read_text(encoding='utf-8')
        
        # Разделение frontmatter и содержимого
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter_str = parts[1]
                prompt_content = parts[2].strip()
                
                try:
                    frontmatter = yaml.safe_load(frontmatter_str)
                    
                    # Конвертируем переменные из YAML в VariableSchema
                    variables_schema = []
                    if 'variables_schema' in frontmatter:
                        from domain.models.prompt.prompt_version import VariableSchema
                        for var_data in frontmatter['variables_schema']:
                            variables_schema.append(VariableSchema(**var_data))
                    
                    # Создаем PromptVersion
                    return PromptVersion(
                        id=frontmatter.get('id'),
                        semantic_version=frontmatter.get('semantic_version', '1.0.0'),
                        domain=DomainType(frontmatter.get('domain')),
                        provider_type=LLMProviderType(frontmatter.get('provider_type')),
                        capability_name=frontmatter.get('capability_name'),
                        role=PromptRole(frontmatter.get('role')),
                        content=prompt_content,
                        variables_schema=variables_schema,
                        expected_response_schema=frontmatter.get('expected_response_schema'),
                        status=PromptStatus(frontmatter.get('status', 'draft')),
                        created_at=datetime.fromisoformat(frontmatter.get('created_at')) if frontmatter.get('created_at') else datetime.utcnow(),
                        activation_date=datetime.fromisoformat(frontmatter.get('activation_date')) if frontmatter.get('activation_date') else None,
                        deprecation_date=datetime.fromisoformat(frontmatter.get('deprecation_date')) if frontmatter.get('deprecation_date') else None,
                        archived_date=datetime.fromisoformat(frontmatter.get('archived_date')) if frontmatter.get('archived_date') else None,
                        parent_version_id=frontmatter.get('parent_version_id'),
                        version_notes=frontmatter.get('version_notes', ''),
                        usage_metrics=PromptUsageMetrics()
                    )
                except Exception as e:
                    print(f"Ошибка при парсинге frontmatter файла {file_path}: {e}")
                    return None
        
        return None
    
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
    
    async def _get_by_id(self, version_id: str) -> Optional[PromptVersion]:
        """Получить версию по ID для проверки существования"""
        query = "SELECT * FROM prompt_versions WHERE id = $1 LIMIT 1"
        result = await self._db_provider.execute_query(query, [version_id])
        if result:
            return self._row_to_prompt_version(result[0])
        return None
    
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
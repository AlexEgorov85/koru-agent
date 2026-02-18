from typing import Dict, List, Set, Any
from core.models.data.manifest import Manifest
from core.application.data_repository import DataRepository


class ManifestValidationService:
    """Сервис валидации манифестов на отсутствие дублирования и конфликтов."""
    
    def __init__(self, data_repository: DataRepository):
        self.data_repository = data_repository
        self._validation_cache: Dict[str, List[str]] = {}
    
    async def validate_no_duplicates(self) -> Dict[str, Any]:
        """
        Проверка на отсутствие дублирования ресурсов.
        
        Возвращает:
        - duplicate_prompts: Список дублирующихся промптов
        - duplicate_contracts: Список дублирующихся контрактов
        - version_conflicts: Список конфликтов версий
        """
        report = {
            'duplicate_prompts': [],
            'duplicate_contracts': [],
            'version_conflicts': [],
            'is_valid': True
        }
        
        # Получаем все манифесты
        manifests = self.data_repository._manifest_cache.values()
        
        # Словарь для отслеживания версий
        prompt_versions: Dict[str, Set[str]] = {}
        contract_versions: Dict[str, Set[str]] = {}
        
        for manifest in manifests:
            component_key = f"{manifest.component_type.value}.{manifest.component_id}"
            
            # Собираем версии промптов из ComponentConfig
            if hasattr(manifest, 'prompt_versions'):
                for cap, ver in manifest.prompt_versions.items():
                    if cap not in prompt_versions:
                        prompt_versions[cap] = set()
                    prompt_versions[cap].add(ver)
            
            # Собираем версии контрактов
            if hasattr(manifest, 'input_contract_versions'):
                for cap, ver in manifest.input_contract_versions.items():
                    if cap not in contract_versions:
                        contract_versions[cap] = set()
                    contract_versions[cap].add(ver)
        
        # Проверка на дублирование версий промптов
        for cap, versions in prompt_versions.items():
            if len(versions) > 1:
                report['duplicate_prompts'].append({
                    'capability': cap,
                    'versions': list(versions),
                    'message': f"Capability '{cap}' имеет несколько версий: {versions}"
                })
                report['is_valid'] = False
        
        # Проверка на дублирование версий контрактов
        for cap, versions in contract_versions.items():
            if len(versions) > 1:
                report['duplicate_contracts'].append({
                    'capability': cap,
                    'versions': list(versions),
                    'message': f"Capability '{cap}' имеет несколько версий контрактов: {versions}"
                })
                report['is_valid'] = False
        
        # Проверка согласованности версий промптов и контрактов
        for cap in prompt_versions.keys():
            if cap in contract_versions:
                if prompt_versions[cap] != contract_versions[cap]:
                    report['version_conflicts'].append({
                        'capability': cap,
                        'prompt_versions': list(prompt_versions[cap]),
                        'contract_versions': list(contract_versions[cap]),
                        'message': f"Версии промптов и контрактов не совпадают для '{cap}'"
                    })
                    report['is_valid'] = False
        
        self._validation_cache['duplicates'] = report
        return report
    
    async def validate_schema_integrity(self) -> Dict[str, Any]:
        """
        Проверка целостности схем input/output контрактов.

        Возвращает:
        - missing_input: Контракты без input схемы
        - missing_output: Контракты без output схемы
        - schema_mismatch: Контракты с несовместимыми схемами
        """
        report = {
            'missing_input': [],
            'missing_output': [],
            'schema_mismatch': [],
            'is_valid': True
        }

        # Получаем все контракты из хранилища
        all_contracts = self.data_repository._contracts_index

        # Группируем по capability
        contracts_by_cap: Dict[str, Dict[str, Any]] = {}

        for (cap, ver, direction), contract in all_contracts.items():
            if cap not in contracts_by_cap:
                contracts_by_cap[cap] = {}
            contracts_by_cap[cap][direction] = contract

        # Проверка наличия input/output для каждой capability
        # Примечание: некоторые capability могут иметь только input или только output
        for cap, directions in contracts_by_cap.items():
            has_input = 'input' in directions
            has_output = 'output' in directions
            
            # Если нет ни input, ни output - это ошибка
            if not has_input and not has_output:
                report['missing_input'].append({
                    'capability': cap,
                    'message': f"Capability '{cap}' не имеет ни input, ни output контракта"
                })
                report['is_valid'] = False
            # Если есть только один тип, добавляем предупреждение (не ошибку)
            elif not has_input:
                report['missing_input'].append({
                    'capability': cap,
                    'message': f"Capability '{cap}' не имеет input контракта (только output)",
                    'severity': 'warning'
                })
            elif not has_output:
                report['missing_output'].append({
                    'capability': cap,
                    'message': f"Capability '{cap}' не имеет output контракта (только input)",
                    'severity': 'warning'
                })

        self._validation_cache['schema_integrity'] = report
        return report
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Возвращает полный отчёт валидации."""
        return {
            'duplicates': self._validation_cache.get('duplicates', {}),
            'schema_integrity': self._validation_cache.get('schema_integrity', {}),
            'is_valid': all([
                self._validation_cache.get('duplicates', {}).get('is_valid', True),
                self._validation_cache.get('schema_integrity', {}).get('is_valid', True)
            ])
        }
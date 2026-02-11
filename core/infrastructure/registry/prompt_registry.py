from typing import Dict, List, Optional, Tuple
from pathlib import Path
import yaml
from datetime import datetime
from ..models.prompt import Prompt, PromptStatus
from ..models.prompt_serialization import PromptSerializer


class PromptRegistryEntry:
    """Запись в реестре промптов"""
    def __init__(self, capability: str, version: str, status: PromptStatus, file_path: str, quality_metrics: Optional[Dict[str, float]] = None, archived_at: Optional[datetime] = None):
        self.capability = capability
        self.version = version
        self.status = status
        self.file_path = file_path
        self.quality_metrics = quality_metrics or {}
        self.archived_at = archived_at or datetime.utcnow()


class PromptRegistry:
    """Класс для управления реестром актуальных версий промптов"""
    
    def __init__(self, registry_path: Path = Path("prompts/registry.yaml")):
        self.registry_path = registry_path
        self.registry_data = {
            'registry_version': '1.0',
            'last_updated': datetime.utcnow().isoformat(),
            'author': 'system',
            'active_prompts': [],
            'archived_prompts': []
        }
        self.active_prompts: Dict[str, PromptRegistryEntry] = {}
        self.archived_prompts: Dict[Tuple[str, str], PromptRegistryEntry] = {}
        
        # Создаем директорию для реестра, если она не существует
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем существующий реестр, если он есть
        if self.registry_path.exists():
            self.load_registry()
        else:
            self.save_registry()

    def load_registry(self):
        """Загружает реестр из YAML файла"""
        with open(self.registry_path, 'r', encoding='utf-8') as f:
            self.registry_data = yaml.safe_load(f)
        
        # Восстанавливаем внутренние структуры данных
        self.active_prompts = {}
        self.archived_prompts = {}
        
        for entry_data in self.registry_data.get('active_prompts', []):
            entry = PromptRegistryEntry(
                capability=entry_data['capability'],
                version=entry_data['current_version'],
                status=PromptStatus(entry_data['status']),
                file_path=entry_data['file_path'],
                quality_metrics=entry_data.get('quality_metrics')
            )
            self.active_prompts[entry.capability] = entry
        
        for entry_data in self.registry_data.get('archived_prompts', []):
            entry = PromptRegistryEntry(
                capability=entry_data['capability'],
                version=entry_data['version'],
                status=PromptStatus(entry_data['status']),
                file_path=entry_data['file_path'],
                quality_metrics=entry_data.get('quality_metrics'),
                archived_at=datetime.fromisoformat(entry_data['archived_at']) if entry_data.get('archived_at') else None
            )
            self.archived_prompts[(entry.capability, entry.version)] = entry

    def save_registry(self):
        """Сохраняет реестр в YAML файл"""
        # Обновляем данные реестра из внутренних структур
        self.registry_data['last_updated'] = datetime.utcnow().isoformat()
        self.registry_data['active_prompts'] = [
            {
                'capability': entry.capability,
                'current_version': entry.version,
                'status': entry.status.value,
                'file_path': entry.file_path,
                'quality_metrics': entry.quality_metrics
            }
            for entry in self.active_prompts.values()
        ]
        self.registry_data['archived_prompts'] = [
            {
                'capability': entry.capability,
                'version': entry.version,
                'status': entry.status.value,
                'file_path': entry.file_path,
                'quality_metrics': entry.quality_metrics,
                'archived_at': entry.archived_at.isoformat() if entry.archived_at else None
            }
            for entry in self.archived_prompts.values()
        ]
        
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)

    def scan_directory(self, prompts_dir: Path = Path("prompts")) -> None:
        """Сканирует директорию и строит реестр на основе файловой структуры"""
        # Очищаем текущие данные
        self.active_prompts = {}
        self.archived_prompts = {}
        
        # Сканируем директорию промптов
        skills_dir = prompts_dir / "skills"
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    for prompt_file in skill_dir.rglob("*.yaml"):
                        try:
                            # Загружаем промпт из файла
                            prompt = PromptSerializer.from_yaml(prompt_file)
                            
                            # Создаем запись в реестре в зависимости от статуса
                            entry = PromptRegistryEntry(
                                capability=prompt.metadata.capability,
                                version=prompt.metadata.version,
                                status=prompt.metadata.status,
                                file_path=str(prompt_file.relative_to(prompts_dir))
                            )
                            
                            if prompt.metadata.status == PromptStatus.ARCHIVED:
                                self.archived_prompts[(entry.capability, entry.version)] = entry
                            else:
                                # Для активных промптов, если есть несколько версий, выбираем самую новую
                                if (entry.capability not in self.active_prompts or 
                                    self.compare_versions(entry.version, self.active_prompts[entry.capability].version) > 0):
                                    self.active_prompts[entry.capability] = entry
                        except Exception as e:
                            print(f"Ошибка при сканировании файла {prompt_file}: {e}")
        
        # Также сканируем архивную директорию
        archived_dir = prompts_dir / "archived"
        if archived_dir.exists():
            for skill_dir in archived_dir.iterdir():
                if skill_dir.is_dir():
                    for prompt_file in skill_dir.rglob("*.yaml"):
                        try:
                            # Загружаем промпт из файла
                            prompt = PromptSerializer.from_yaml(prompt_file)
                            
                            # Создаем запись в реестре
                            entry = PromptRegistryEntry(
                                capability=prompt.metadata.capability,
                                version=prompt.metadata.version,
                                status=PromptStatus.ARCHIVED,
                                file_path=str(prompt_file.relative_to(prompts_dir)),
                                archived_at=prompt.metadata.updated_at
                            )
                            
                            self.archived_prompts[(entry.capability, entry.version)] = entry
                        except Exception as e:
                            print(f"Ошибка при сканировании архивного файла {prompt_file}: {e}")
        
        # Сохраняем обновленный реестр
        self.save_registry()

    def get_active_prompt(self, capability: str) -> Optional[Prompt]:
        """Возвращает активную версию промпта"""
        if capability not in self.active_prompts:
            return None
        
        entry = self.active_prompts[capability]
        prompts_dir = self.registry_path.parent.parent  # поднимаемся на уровень выше, чтобы получить абсолютный путь
        prompt_path = prompts_dir / entry.file_path
        
        try:
            return PromptSerializer.from_yaml(prompt_path)
        except Exception as e:
            print(f"Ошибка при загрузке активного промпта {capability}: {e}")
            return None

    def get_prompt_by_capability_and_version(self, capability: str, version: str) -> Optional[Prompt]:
        """Возвращает промпт по capability и версии (может быть активным или архивным)"""
        # Сначала проверяем активные промпты
        if capability in self.active_prompts:
            active_entry = self.active_prompts[capability]
            if active_entry.version == version:
                return self.get_active_prompt(capability)
        
        # Затем проверяем архивные промпты
        if (capability, version) in self.archived_prompts:
            entry = self.archived_prompts[(capability, version)]
            prompts_dir = self.registry_path.parent.parent  # поднимаемся на уровень выше, чтобы получить абсолютный путь
            prompt_path = prompts_dir / entry.file_path
            
            try:
                return PromptSerializer.from_yaml(prompt_path)
            except Exception as e:
                print(f"Ошибка при загрузке архивного промпта {capability} версии {version}: {e}")
                return None
        
        return None

    def promote(self, prompt: Prompt) -> bool:
        """Переводит промпт в статус ACTIVE и обновляет реестр"""
        try:
            # Обновляем статус промпта
            prompt.metadata.status = PromptStatus.ACTIVE
            prompt.metadata.updated_at = datetime.utcnow()
            
            # Сохраняем промпт в файл
            base_path = self.registry_path.parent  # используем директорию реестра как базовую
            file_path = PromptSerializer.to_file(prompt, base_path / "skills")
            
            # Обновляем запись в реестре
            entry = PromptRegistryEntry(
                capability=prompt.metadata.capability,
                version=prompt.metadata.version,
                status=PromptStatus.ACTIVE,
                file_path=str(file_path.relative_to(base_path))
            )
            
            # Если уже есть активный промпт с такой же способностью, перемещаем его в архив
            if prompt.metadata.capability in self.active_prompts:
                old_entry = self.active_prompts[prompt.metadata.capability]
                archived_entry = PromptRegistryEntry(
                    capability=old_entry.capability,
                    version=old_entry.version,
                    status=PromptStatus.ARCHIVED,
                    file_path=old_entry.file_path,
                    archived_at=datetime.utcnow()
                )
                self.archived_prompts[(old_entry.capability, old_entry.version)] = archived_entry
            
            # Добавляем новый активный промпт
            self.active_prompts[prompt.metadata.capability] = entry
            
            # Сохраняем обновленный реестр
            self.save_registry()
            
            return True
        except Exception as e:
            print(f"Ошибка при продвижении промпта {prompt.metadata.capability}: {e}")
            return False

    def archive(self, capability: str, version: str, reason: str = "") -> bool:
        """Архивирует промпт с сохранением истории"""
        try:
            # Находим промпт в активных
            if capability not in self.active_prompts:
                return False
            
            active_entry = self.active_prompts[capability]
            if active_entry.version != version:
                # Возможно, запрашивается архивация версии, которая не является текущей активной
                # В этом случае ищем в архиве или возвращаем ошибку
                if (capability, version) not in self.archived_prompts:
                    return False
                # Если запрашиваемая версия уже в архиве, просто возвращаем успех
                return True
            
            # Перемещаем активный промпт в архив
            archived_entry = PromptRegistryEntry(
                capability=active_entry.capability,
                version=active_entry.version,
                status=PromptStatus.ARCHIVED,
                file_path=active_entry.file_path,
                archived_at=datetime.utcnow()
            )
            self.archived_prompts[(active_entry.capability, active_entry.version)] = archived_entry
            
            # Удаляем из активных
            del self.active_prompts[capability]
            
            # Обновляем промпт в файле, установив ему статус архивного
            prompts_dir = self.registry_path.parent.parent
            prompt_path = prompts_dir / active_entry.file_path
            if prompt_path.exists():
                prompt = PromptSerializer.from_yaml(prompt_path)
                prompt.metadata.status = PromptStatus.ARCHIVED
                prompt.metadata.changelog.append(f"Архивирован {datetime.utcnow().isoformat()}: {reason}")
                prompt.metadata.updated_at = datetime.utcnow()
                
                # Если архивная директория не существует, создаем ее
                archived_path = self.registry_path.parent / "archived"
                archived_path.mkdir(exist_ok=True)
                
                # Перемещаем файл в архивную директорию
                import shutil
                new_prompt_path = archived_path / prompt_path.name
                shutil.move(str(prompt_path), str(new_prompt_path))
                
                # Обновляем путь в записи
                archived_entry.file_path = str(new_prompt_path.relative_to(self.registry_path.parent))
            
            # Сохраняем обновленный реестр
            self.save_registry()
            
            return True
        except Exception as e:
            print(f"Ошибка при архивации промпта {capability} версии {version}: {e}")
            return False

    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """
        Сравнивает две версии в формате semver
        Возвращает:
        -1 если version1 < version2
         0 если version1 == version2
         1 если version1 > version2
        """
        # Убираем префикс 'v' если он есть
        v1_parts = version1.lstrip('v').split('.')
        v2_parts = version2.lstrip('v').split('.')
        
        # Преобразуем в числа и сравниваем
        for i in range(max(len(v1_parts), len(v2_parts))):
            val1 = int(v1_parts[i]) if i < len(v1_parts) else 0
            val2 = int(v2_parts[i]) if i < len(v2_parts) else 0
            
            if val1 < val2:
                return -1
            elif val1 > val2:
                return 1
        
        return 0
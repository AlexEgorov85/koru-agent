from typing import Dict, Any, List
from pydantic import BaseModel

from core.components.skills.handlers.base_handler import BaseSkillHandler


class ListScriptsHandler(BaseSkillHandler):
    """
    Обработчик получения списка доступных скриптов.

    RESPONSIBILITIES:
    - Предоставление информации о доступных скриптах
    - Генерация примеров параметров для каждого скрипта

    CAPABILITY:
    - book_library.list_scripts
    """

    capability_name = "book_library.list_scripts"

    async def execute(self, params: BaseModel = None, execution_context: Any = None) -> BaseModel:
        """
        Получение списка доступных скриптов.

        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (может быть None для информационных capability)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        await self.log_info("Запрос списка доступных скриптов")

        allowed_scripts = self._get_allowed_scripts()
        scripts_list = self._format_scripts_list(allowed_scripts)

        result_data = {
            "scripts": scripts_list,
            "total_count": len(scripts_list)
        }

        await self.log_info(f"Возвращено {len(scripts_list)} скриптов")

        output_schema = self.get_output_schema()
        if output_schema:
            validated_result = output_schema.model_validate(result_data)
            return validated_result

        return result_data

    def _get_allowed_scripts(self) -> Dict[str, Dict[str, Any]]:
        """Получение реестра разрешённых скриптов"""
        if self.skill._scripts_registry:
            return {name: config.to_dict() for name, config in self.skill._scripts_registry.items()}
        return self.skill._get_allowed_scripts()

    def _format_scripts_list(self, scripts: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Форматирование списка скриптов с примерами параметров.

        ARGS:
        - scripts: реестр скриптов

        RETURNS:
        - list: список скриптов с описаниями
        """
        scripts_list = []

        for script_name, script_config in scripts.items():
            example_params = self._generate_example_params(script_config)

            script_info = {
                "name": script_name,
                "description": script_config.get('description', 'Без описания'),
                "required_parameters": script_config.get('required_parameters', []),
                "optional_parameters": [
                    p for p in script_config.get('parameters', [])
                    if p not in script_config.get('required_parameters', [])
                ],
                "max_rows": script_config.get('max_rows', 100),
                "example_parameters": example_params
            }
            scripts_list.append(script_info)

        # Сортируем по имени
        scripts_list.sort(key=lambda x: x["name"])
        return scripts_list

    def _generate_example_params(self, script_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерация примеров параметров для скрипта.

        ARGS:
        - script_config: конфигурация скрипта

        RETURNS:
        - dict: примеры параметров
        """
        example_params = {}

        for param in script_config.get('required_parameters', []):
            if param == 'author':
                example_params[param] = "Лев Толстой"
            elif param == 'genre':
                example_params[param] = "Роман"
            elif param == 'year_from':
                example_params[param] = 1800
            elif param == 'year_to':
                example_params[param] = 1900
            elif param == 'book_id':
                example_params[param] = 1
            elif param == 'title_pattern':
                example_params[param] = "%Война%"
            else:
                example_params[param] = "значение"

        if 'max_rows' in script_config.get('parameters', []):
            example_params['max_rows'] = 10

        return example_params

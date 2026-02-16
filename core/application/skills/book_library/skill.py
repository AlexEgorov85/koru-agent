#!/usr/bin/env python3
"""
Полноценный класс Skill для book_library с промптами и контрактами.
"""
import sys
from typing import Dict, Any, List
from pathlib import Path

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


from core.components.base_component import BaseComponent
from core.config.component_config import ComponentConfig
# Импорты типов через строковые аннотации для избежания циклических зависимостей
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.action_executor import ActionExecutor

# Для использования в аннотациях типов вне блока TYPE_CHECKING
from core.application.context.application_context import ApplicationContext
from core.application.agent.components.action_executor import ActionExecutor
from pydantic import BaseModel, Field
from typing import Optional


class BookSearchInput(BaseModel):
    """Входная схема для поиска книг"""
    query: str = Field(..., description="Поисковый запрос")
    max_results: Optional[int] = Field(default=10, description="Максимальное количество результатов")


class BookItem(BaseModel):
    """Модель книги"""
    title: str = Field(..., description="Название книги")
    author: str = Field(..., description="Автор книги")
    year: Optional[int] = Field(default=None, description="Год публикации")
    isbn: Optional[str] = Field(default=None, description="ISBN")


class BookSearchOutput(BaseModel):
    """Выходная схема для поиска книг"""
    results: List[BookItem] = Field(..., description="Результаты поиска")
    total_found: int = Field(..., description="Общее количество найденных книг")


class BookLibrarySkill(BaseComponent):
    """
    Навык для работы с библиотекой книг.
    
    Этот навык предоставляет возможность поиска книг по различным критериям.
    """
    
    def __init__(
        self,
        name: str,
        application_context: 'ApplicationContext',
        component_config: ComponentConfig,
        executor: 'ActionExecutor'
    ):
        super().__init__(name, application_context, component_config, executor)
        
        # Регистрируем capability, которые использует этот навык
        self.supported_capabilities = {
            "book_library.search_books": self._search_books
        }
    
    async def initialize(self) -> bool:
        """Инициализация навыка с предзагрузкой необходимых ресурсов"""
        success = await super().initialize()
        if not success:
            return False
        
        # Проверяем, что все необходимые промпты и контракты загружены
        required_capability = "book_library.search_books"
        
        # Проверяем наличие промпта
        if required_capability not in self._cached_prompts:
            self.logger.error(f"Промпт для {required_capability} не загружен")
            return False
        
        # Проверяем наличие входной схемы
        if required_capability not in self._cached_input_schemas:
            self.logger.error(f"Входная схема для {required_capability} не загружена")
            return False

        # Проверяем наличие выходной схемы
        if required_capability not in self._cached_output_schemas:
            self.logger.error(f"Выходная схема для {required_capability} не загружена")
            return False
        
        self.logger.info(f"BookLibrarySkill инициализирован с capability: {required_capability}")
        return True
    
    async def execute(self, capability: str, parameters: Dict[str, Any], execution_context: Any) -> Dict[str, Any]:
        """
        Выполнение действия навыка.
        
        Args:
            capability: название capability для выполнения
            parameters: параметры действия
            execution_context: контекст выполнения
            
        Returns:
            Dict[str, Any]: результат выполнения
        """
        if capability not in self.supported_capabilities:
            raise ValueError(f"Навык не поддерживает capability: {capability}")
        
        # Выполняем действие
        result = await self.supported_capabilities[capability](parameters)
        return result
    
    async def _search_books(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Внутренний метод для поиска книг.
        
        Args:
            params: параметры поиска
            
        Returns:
            Dict[str, Any]: результаты поиска
        """
        # Валидируем входные параметры через кэшированную схему
        input_schema = self.get_cached_input_schema_safe("book_library.search_books")
        if input_schema:
            try:
                validated_params = input_schema.model_validate(params)
            except Exception as e:
                self.logger.error(f"Ошибка валидации параметров: {e}")
                return {"error": f"Неверные параметры: {str(e)}", "results": []}
        else:
            validated_params = BookSearchInput(**params)

        # Получаем промпт
        prompt_content = self.get_cached_prompt_safe("book_library.search_books")
        if not prompt_content:
            return {"error": "Промпт для поиска книг не найден", "results": []}

        # Рендерим промпт с параметрами (используем метод из BaseComponent)
        try:
            rendered_prompt = self.render_prompt("book_library.search_books", **vars(validated_params))
        except Exception as e:
            self.logger.error(f"Ошибка рендеринга промпта: {e}")
            return {"error": f"Ошибка рендеринга промпта: {str(e)}", "results": []}
        
        # Здесь должна быть логика вызова LLM или поиска в базе данных
        # Для демонстрации возвращаем фиктивные результаты
        fake_results = [
            BookItem(title="Искусственный интеллект", author="Стюарт Рассел", year=2020),
            BookItem(title="Глубокое обучение", author="Ян Гудфеллоу", year=2016),
            BookItem(title="Машинное обучение", author="Том Митчелл", year=1997)
        ]
        
        # Валидируем результаты через выходную схему
        output_schema = self.get_cached_output_schema_safe("book_library.search_books")
        if output_schema:
            try:
                result = output_schema.model_validate({
                    "results": [item.model_dump() for item in fake_results],
                    "total_found": len(fake_results)
                })
                return result.model_dump()
            except Exception as e:
                self.logger.error(f"Ошибка валидации результата: {e}")
                return {"error": f"Ошибка валидации результата: {str(e)}", "results": []}
        else:
            return {
                "results": [item.model_dump() for item in fake_results],
                "total_found": len(fake_results)
            }


# Функция для создания экземпляра навыка (фабричный метод)
def create_book_library_skill(
    name: str,
    application_context: ApplicationContext,
    component_config: ComponentConfig,
    executor: ActionExecutor
) -> 'BookLibrarySkill':
    """
    Фабричный метод для создания экземпляра BookLibrarySkill.

    Args:
        name: имя навыка
        application_context: контекст приложения
        component_config: конфигурация компонента
        executor: исполнитель действий

    Returns:
        BookLibrarySkill: экземпляр навыка
    """
    return BookLibrarySkill(name, application_context, component_config, executor)


if __name__ == "__main__":
    # Тестирование навыка
    print("BookLibrarySkill класс создан и готов к использованию")
    print("Поддерживаемые capabilities:", list(BookLibrarySkill(None, None, None, None).supported_capabilities.keys()))
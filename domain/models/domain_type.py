from enum import Enum

class DomainType(str, Enum):
    """
    Тип домена задачи.
    
    ПРЕДНАЗНАЧЕНИЕ:
    - Классификация задач по типу домена
    - Определение стратегии обработки задачи
    - Выбор соответствующих инструментов и навыков
    
    ИСПОЛЬЗОВАНИЕ:
    task_domain = DomainType.CODE_GENERATION
    if task_domain == DomainType.CODE_GENERATION:
        use_coding_skills()
    elif task_domain == DomainType.DATA_ANALYSIS:
        use_analysis_tools()
    """
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    TEXT_GENERATION = "text_generation"
    PROBLEM_SOLVING = "problem_solving"
    RESEARCH = "research"
    PLANNING = "planning"
    DEBUGGING = "debugging"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    DESIGN = "design"
    OPTIMIZATION = "optimization"
    SECURITY = "security"
    MAINTENANCE = "maintenance"
    LEARNING = "learning"
    COMMUNICATION = "communication"
    REASONING = "reasoning"
class PlanningPatternFactory:
    """Фабрика для устранения циклических зависимостей"""
    
    @staticmethod
    def create_pattern(
        prompt_service: 'PromptService',
        contract_service: 'ContractService'
    ) -> 'PlanningPattern':
        from core.agent.behaviors.planning.pattern import PlanningPattern
        return PlanningPattern(prompt_service, contract_service)
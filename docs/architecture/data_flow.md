# Поток данных (Data Flow)

1. Пользователь / система формирует цель
2. Создаётся SessionContext
3. Agent выбирает capability
4. Capability связывается с prompt-версиями
5. PromptRenderer:
   - подбирает нужный prompt
   - рендерит шаблон
6. Вызов LLM
7. Результат → StrategyDecision
8. Генерация событий
9. Обновление метрик и состояния

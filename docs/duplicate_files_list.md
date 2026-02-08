# Список файлов для удаления из-за дублирования

## Уже удалены:
- docs/best_practices_guide.md (дублировал docs/best_practices.md)

## Потенциально дублирующие файлы для рассмотрения:

### Overview файлы
- docs/overview.md
- docs/complete_overview.md  
- docs/final_overview.md

### Guide файлы
- docs/guide.md
- docs/complete_guide.md
- docs/customization_guide.md (специфический, возможно оставить)
- docs/integration_guide.md (специфический, возможно оставить)
- docs/migration_guide.md (специфический, возможно оставить)

### Conclusion файлы
- docs/conclusion.md
- docs/CONCLUSION_FINAL.md

### Summary файлы
- docs/final_summary.md
- docs/complete_system_guide.md
- docs/framework_summary.md

### Оглавления
- docs/SUMMARY_ALL.md
- docs/TABLE_OF_CONTENTS.md
- docs/index.md
- docs/readme.md (не путать с корневым README.md)

### Intro файлы
- docs/intro.md
- docs/introduction.md

### Custom development файлы (по одному в каждой подпапке - все дублируют друг друга)
- docs/architecture/custom_development.md
- docs/concepts/custom_development.md
- docs/prompts/custom_development.md
- docs/tools_skills/custom_development.md
- docs/core/custom_development.md
- docs/configuration/custom_development.md
- docs/events/custom_development.md
- docs/system/custom_development.md
- docs/application/custom_development.md

## Рекомендации:
1. Объединить дублирующиеся файлы в один с разделами
2. Удалить избыточные оглавления, оставить только docs/SUMMARY.md
3. Создать один общий файл custom_development.md с разделами по компонентам
4. Удалить дублирующие intro/overview/conclusion файлы
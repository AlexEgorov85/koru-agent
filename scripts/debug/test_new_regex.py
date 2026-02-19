import re

# Тестируем обновленное регулярное выражение
text = "{{ query }} {{ max_results|default(10) }} { variable2 } {{ var3|filter|another }}"
pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^\}]*)?\s*\}\}|\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}'
matches = re.findall(pattern, text)

print(f"Text: {text}")
print(f"Matches: {matches}")

# Обработка результатов
template_vars = set()
for match_tuple in matches:
    for item in match_tuple:
        if item:  # Если элемент не пустой
            template_vars.add(item)
            break  # Берем первый непустой элемент из кортежа

print(f"Extracted variables: {template_vars}")
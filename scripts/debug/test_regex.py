import re

# Тестируем регулярное выражение
text = "This is {{ variable1 }} and { variable2 } and {{ var3 }}"
pattern = r'\{?\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}?'
matches = re.findall(pattern, text)
print(f"Matches: {matches}")

# Проверим более точное регулярное выражение для двойных скобок
text2 = "{{ capabilities_list }} {{ goal }} {{ context }} {{ max_steps }}"
pattern2 = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}'
matches2 = re.findall(pattern2, text2)
print(f"Double braces matches: {matches2}")

# Объединенное регулярное выражение
pattern3 = r'(?:\{\{|\{)([a-zA-Z_][a-zA-Z0-9_]*)(?:\}\}|\})'
matches3 = re.findall(pattern3, text)
print(f"Combined matches: {matches3}")

# Правильное объединенное регулярное выражение
pattern4 = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}|\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
text4 = "{{ capabilities_list }} {{ goal }} { context } {{ max_steps }}"
matches4 = re.findall(pattern4, text4)
print(f"Correct combined matches: {matches4}")

# Обработка каждого кортежа результатов
results = []
for match in re.findall(pattern4, text4):
    if isinstance(match, tuple):
        # Если результат - кортеж, берем непустое значение
        result = next((item for item in match if item), None)
        if result:
            results.append(result)
    else:
        results.append(match)
print(f"Processed results: {results}")
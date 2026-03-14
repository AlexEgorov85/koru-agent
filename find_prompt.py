with open(r'c:\Users\Алексей\Documents\WORK\Agent_v5\output.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    # Ищем строки с SQL Generation prompt
    for i, line in enumerate(lines):
        if 'SQL Generation prompt' in line or 'prompt_len=27' in line:
            print(f"Строка {i}: {line.strip()}")
            # Показываем контекст
            if i > 0:
                print(f"  До: {lines[i-1].strip()}")
            if i < len(lines) - 1:
                print(f"  После: {lines[i+1].strip()}")
            print()

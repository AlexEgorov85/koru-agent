with open(r'c:\Users\Алексей\Documents\WORK\Agent_v5\output.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    print(f"Всего строк: {len(lines)}")
    print("\n=== ПОСЛЕДНИЕ 80 СТРОК ===\n")
    print(''.join(lines[-80:]))

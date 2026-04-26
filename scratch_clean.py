import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'^\s*rapport\["construction"\]\["[^"]+"\]\s*=\s*\{"kwargs":\s*_to_jsonable\(raw\),\s*"construit":[^}]+\}\s*\n', '', code, flags=re.MULTILINE)
code = re.sub(r'^\s*rapport\["construction"\]\["cylindre"\]\s*=\s*\{"kwargs":\s*_to_jsonable\(raw\),\s*"construit":[^}]+\}\s*\n', '', code, flags=re.MULTILINE)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(code)

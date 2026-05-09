import os

filepath = r'c:\Users\alpha\Documents\GitHub\SHSE-M\backend\main.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 2261 is index 2260
if 'resultat = {' in lines[2260]:
    lines[2260] = lines[2260].replace('resultat = {', 'resultat = {\n        "optimisation_carburant": rapport_optimisation_carburant,')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Replacement successful")
else:
    print(f"Content not found at line 2261: {repr(lines[2260])}")

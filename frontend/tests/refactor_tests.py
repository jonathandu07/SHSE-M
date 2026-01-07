import os
import re

TEST_DIR = r"d:\Documents\GitHub\SHSE-M\frontend\tests\sketches"
LOGGING_IMPORT = "from frontend.tests.conftest_logging import setup_test_logging\n"

def refactor_test_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already refactored
    if "setup_test_logging" in content:
        return
    
    # Extract test class name for logger
    match = re.search(r"class (Test\w+)\(", content)
    test_name = match.group(1) if match else os.path.basename(filepath).replace(".py", "")
    
    # Prepare lines
    lines = content.splitlines()
    new_lines = []
    inserted_logging = False
    
    for line in lines:
        new_lines.append(line)
        if not inserted_logging and (line.startswith("from ") or line.startswith("import ")):
            # Wait for last import roughly
            pass
        if not inserted_logging and "unittest.TestCase" in line:
            # We found the class, let's insert logger before it
            new_lines.insert(-1, f"\n{LOGGING_IMPORT}")
            new_lines.insert(-1, f"logger = setup_test_logging('{test_name}')\n")
            inserted_logging = True
            
    # Inject logger calls in test methods
    refactored_content = "\n".join(new_lines)
    refactored_content = re.sub(r"(def test_\w+\(self\):)", r"\1\n        logger.info('Démarrage du test')\n        try:", refactored_content)
    
    # This is a bit complex for a regex, but let's try to wrap the body in try/except or just add a logger.info at end
    # Simpler: just add a logger.info at the start of each test method.
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(refactored_content)

for filename in os.listdir(TEST_DIR):
    if filename.startswith("test_") and filename.endswith(".py"):
        refactor_test_file(os.path.join(TEST_DIR, filename))

import os
import sys
import re

# Configuration
FRONTEND_2D_DIR = os.path.join("frontend", "pieces", "sketches_2d")
TEST_2D_DIR = os.path.join("frontend", "tests", "test_sketches_2d")

def generate_test_content(module_name):
    # Determine the file path to read and extract attributes to mock
    source_file = os.path.join(FRONTEND_2D_DIR, f"{module_name}.py")
    attributes_to_mock = set()
    
    # Simple regex to find getattr(piece, 'NAME'...) calls in the source
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
            matches = re.findall(r"getattr\(piece,\s*['\"](\w+)['\"]", content)
            for m in matches:
                attributes_to_mock.add(m)
            
            # Also check for direct access if any (e.g. piece.nom)
            matches_direct = re.findall(r"piece\.(\w+)", content)
            for m in matches_direct:
                attributes_to_mock.add(m)
    except Exception as e:
        print(f"Warning: Could not read {source_file}: {e}")

    # Generate Mock Class properties
    mock_setup = ""
    for attr in attributes_to_mock:
        if attr == "nom":
            val = '"TestPiece"'
        elif "diametre" in attr or "alesage" in attr or "longueur" in attr or "hauteur" in attr or "entraxe" in attr:
            val = "0.1" # Default float
        else:
            val = "0.1"
        
        # Indentation must match __init__ body (16 spaces)
        mock_setup += f"                self.{attr} = {val}\n"

    # Template
    test_code = f"""import unittest
import matplotlib.pyplot as plt
from frontend.pieces.sketches_2d import {module_name}

class Test{module_name.title().replace('_', '')}2D(unittest.TestCase):
    def test_draw(self):
        fig, ax = plt.subplots()
        
        class MockPiece:
            def __init__(self):
                self.nom = "Test Piece"
{mock_setup}
        
        piece = MockPiece()
        
        # Should run without error
        {module_name}.draw(ax, piece)
        
        # Check if something was added (patches or text)
        has_content = len(ax.patches) > 0 or len(ax.texts) > 0
        self.assertTrue(has_content, "Draw function should add patches or text to the axes")
        
        plt.close(fig)

if __name__ == '__main__':
    unittest.main()
"""
    return test_code

def main():
    print(f"Scanning {FRONTEND_2D_DIR}...")
    if not os.path.exists(TEST_2D_DIR):
        os.makedirs(TEST_2D_DIR)

    # Allow importing from frontend
    sys.path.append(os.getcwd())

    files = [f for f in os.listdir(FRONTEND_2D_DIR) if f.endswith(".py") and f != "__init__.py"]
    
    count = 0
    for f in files:
        module_name = f[:-3]
        test_file_path = os.path.join(TEST_2D_DIR, f"test_{module_name}.py")
        
        content = generate_test_content(module_name)
        
        with open(test_file_path, 'w', encoding='utf-8') as out:
            out.write(content)
        count += 1

    # Create __init__.py in test dir
    with open(os.path.join(TEST_2D_DIR, "__init__.py"), 'w') as f:
        pass

    print(f"Generated {count} test files in {TEST_2D_DIR}.")

if __name__ == "__main__":
    main()

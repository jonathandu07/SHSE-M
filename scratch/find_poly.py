import os
import sys
import json
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from backend.modules.systeme.database import SecureDatabase

db = SecureDatabase(
    db_path=os.path.join(BASE_DIR, "backend", "shse_technical_data.db"),
    key_path=os.path.join(BASE_DIR, "backend", "secret.key")
)

res = db.load_main_report("latest")
if res:
    # Find exact paths for "poly"
    def find_paths(d, search, path=""):
        results = []
        if isinstance(d, str):
            if search.lower() in d.lower():
                results.append(f"{path} = {d}")
        elif isinstance(d, dict):
            for k, v in d.items():
                if search.lower() in k.lower():
                    results.append(f"{path}.{k} (key)")
                results.extend(find_paths(v, search, f"{path}.{k}"))
        elif isinstance(d, list):
            for i, v in enumerate(d):
                results.extend(find_paths(v, search, f"{path}[{i}]"))
        return results

    paths = find_paths(res, "poly")
    for p in paths:
        print(p)

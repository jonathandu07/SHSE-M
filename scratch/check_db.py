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
    print("Report keys:", list(res.keys()))
    if "resume_gui" in res:
        print("Resume GUI:", json.dumps(res["resume_gui"], indent=2))
    
    # Search for "poly" in the whole report
    def find_string(d, search):
        if isinstance(d, str):
            if search.lower() in d.lower():
                return True
        elif isinstance(d, dict):
            for k, v in d.items():
                if search.lower() in k.lower() or find_string(v, search):
                    return True
        elif isinstance(d, list):
            for v in d:
                if find_string(v, search):
                    return True
        return False

    if find_string(res, "poly"):
        print("Found 'poly' in report!")
    else:
        print("Did not find 'poly' in report.")
else:
    print("No report found in DB.")

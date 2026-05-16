import sys
import os

# Add root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from frontend.gui.report_adapter import adapt_backend_report

def test_report_adapter_basic():
    print("Test 1: Empty report")
    res = adapt_backend_report({})
    assert res["is_empty"] is True
    print("OK")

    print("Test 2: Only resume_gui")
    report = {"resume_gui": {"Architecture": "L4"}}
    res = adapt_backend_report(report)
    assert res["dashboard"]["kpis"][0]["value"] == "L4"
    print("OK")

    print("Test 3: derivees_chaine_energie.details")
    report = {"derivees_chaine_energie": {"details": {"p_traction_w": 50000}}}
    res = adapt_backend_report(report)
    items = res["dashboard"]["energy_chain"]
    p_trac = next(i for i in items if i["label"] == "Puissance Traction")
    assert p_trac["value"] == 50000
    print("OK")

if __name__ == "__main__":
    try:
        test_report_adapter_basic()
        print("BASE TESTS PASSED.")
    except Exception as e:
        print(f"BASE TEST FAILED: {e}")
        sys.exit(1)

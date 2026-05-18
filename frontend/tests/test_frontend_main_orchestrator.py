from __future__ import annotations

import json

import frontend.main as fm


def test_charger_etat_frontend_complet_depuis_rapport_courant(monkeypatch):
    class FakeBridge:
        raw_report = {
            "frontend": {"fields": [{"path": "x", "value": 1, "status": "computed"}]},
            "diagnostic": {"causes_racines": []},
            "cao_dossier": {"croquis_2d": []},
            "mechanical_graphs": {"graphiques": []},
        }
        ui_report = {}

        def run_100kw(self):
            raise AssertionError("scenario non demande")

        def run(self):
            raise AssertionError("run non demande")

    monkeypatch.setattr(fm, "get_backend_bridge", lambda: FakeBridge())

    state = fm.charger_etat_frontend_complet()

    json.dumps(state, ensure_ascii=False)
    assert state["raw_report"]["frontend"]["fields"][0]["path"] == "x"
    assert "visualisations" in state
    assert state["errors"] == []


def test_charger_rapport_backend_lance_100kw_uniquement_si_demande(monkeypatch):
    calls = []

    class FakeBridge:
        raw_report = {}

        def run_100kw(self):
            calls.append("100kw")
            self.raw_report = {"scenario": "100kw"}

        def run(self):
            calls.append("run")

    bridge = FakeBridge()
    monkeypatch.setattr(fm, "get_backend_bridge", lambda: bridge)

    assert fm.charger_rapport_backend() == {}
    assert calls == []
    assert fm.charger_rapport_backend(scenario="100kw") == {"scenario": "100kw"}
    assert calls == ["100kw"]

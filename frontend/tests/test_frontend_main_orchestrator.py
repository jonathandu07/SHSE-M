from __future__ import annotations

import json
import inspect

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


def test_lancer_calcul_puissance_sortie_ne_lance_pas_100kw(monkeypatch):
    calls = []

    class FakeBridge:
        raw_report = {}

        def run_100kw(self):
            raise AssertionError("run_100kw ne doit pas etre appele pour une puissance utilisateur")

        def run(self, config, **kwargs):
            calls.append({"config": dict(config), "kwargs": dict(kwargs)})
            self.raw_report = {
                "frontend_inputs": dict(config["frontend_inputs"]),
                "frontend": {"fields": []},
            }
            return {"raw_report": self.raw_report, "errors": [], "warnings": []}

    monkeypatch.setattr(fm, "get_backend_bridge", lambda: FakeBridge())

    state = fm.charger_etat_frontend_complet(puissance=100.0, unite="ch")

    assert calls
    assert calls[0]["kwargs"]["action"] == "power_input"
    assert calls[0]["config"]["puissance_sortie_moteur_electrique_kw"] > 0
    assert state["inputs"]["unite"] == "ch"
    assert state["raw_report"]["frontend_inputs"]["status"] == "input"


def test_frontend_main_monte_un_shell_de_pages():
    source = inspect.getsource(fm._make_kivy_app_class)

    assert "ScreenManager" in source
    for screen_name in ("home", "dashboard", "edit_parameters", "json_diagnostic", "technical_visualization", "cao_dossier", "raw_json"):
        assert f'"{screen_name}"' in source
    assert "_make_summary_text()" not in source.split("def build(self) -> Any:", 1)[1].split("def on_start", 1)[0]


def test_ui_report_ne_marque_pas_valeur_brute_comme_calculee():
    report = {"synthese": {"systeme": {"P_bus_dc_design_w": 120000.0}}}

    ui = fm.build_frontend_ui_report(report)
    bus = next(item for item in ui["kpis"] if item["label"] == "Bus DC design")

    assert bus["status"] == "partial"
    assert bus["confidence"] == "untraced_report_value"


def test_ui_report_accepte_computed_seulement_avec_trace():
    report = {
        "synthese": {"systeme": {"P_bus_dc_design_w": 120000.0}},
        "frontend": {
            "fields": [
                {
                    "path": "synthese.systeme.P_bus_dc_design_w",
                    "value": 120000.0,
                    "unit": "W",
                    "status": "computed",
                    "trace": {"source": "resolution_inconnues", "formule": "P/U"},
                }
            ]
        },
    }

    ui = fm.build_frontend_ui_report(report)
    bus = next(item for item in ui["kpis"] if item["label"] == "Bus DC design")

    assert bus["status"] == "computed"
    assert bus["trace_present"] is True

from __future__ import annotations

from pathlib import Path

from frontend.gui.backend_resource_adapter import (
    build_resource_catalog,
    discover_backend_resources,
    generate_or_load_resource,
    get_piece_resources,
)
from frontend.gui.report_adapter import adapt_backend_report


def test_discover_backend_resources_ne_fabrique_pas_de_modules():
    report = discover_backend_resources()
    assert report["resources"]
    assert all(str(item["backend_module"]).startswith("backend.") for item in report["resources"])
    assert not any(str(item["backend_module"]).startswith("frontend.") for item in report["resources"])


def test_resource_unavailable_si_module_absent():
    result = generate_or_load_resource(
        {
            "name": "croquis absent",
            "type": "sketches",
            "source": "backend.components.module_absent",
            "function": "generer_croquis",
        },
        {},
    )
    assert result["status"] == "unavailable"
    assert result["path"] is None


def test_resource_unavailable_si_donnees_requises_absentes():
    result = generate_or_load_resource(
        {
            "name": "json alternateur",
            "type": "json",
            "source": "backend.components.alternateur.alternateur",
            "function": "exporter_rapport_json",
        },
        {"resume_gui": {"Architecture": "L4"}},
    )
    assert result["status"] == "unavailable"
    assert "chemin" in result["missing_inputs"]


def test_resource_available_seulement_si_fichier_existe(tmp_path: Path):
    output = tmp_path / "rapport.json"
    result = generate_or_load_resource(
        {
            "name": "json alternateur",
            "type": "json",
            "source": "backend.components.alternateur.alternateur",
            "function": "exporter_rapport_json",
            "output_path": str(output),
        },
        {"resume_gui": {"Architecture": "L4"}},
    )
    assert result["status"] == "available"
    assert result["path"] == str(output)
    assert output.is_file()


def test_piece_resources_utilisent_rapport_backend():
    report = {
        "rapports_pieces": {
            "piston": {
                "dimensions": {
                    "cao": {
                        "diametre_exterieur_nominal_m": 0.08,
                    }
                }
            }
        }
    }
    resources = get_piece_resources("piston", report)
    assert any(item["status"] == "available" for item in resources["cao"])
    assert all(item["path"] is None for item in resources["cao"])


def test_charts_ne_sont_pas_inventes():
    catalog = build_resource_catalog({"rapports_pieces": {"piston": {"dimensions": {"diametre_m": 0.08}}}})
    charts = catalog["resources"]["charts"]
    assert not any(item["status"] == "available" and item.get("path") for item in charts)


def test_sketches_ne_sont_pas_inventes():
    catalog = build_resource_catalog({"rapports_pieces": {"piston": {"dimensions": {"diametre_m": 0.08}}}})
    sketches = catalog["resources"]["sketches"]
    assert sketches
    assert not any(item["status"] == "available" for item in sketches)


def test_three_d_ne_sont_pas_inventes():
    catalog = build_resource_catalog({"rapports_pieces": {"piston": {"dimensions": {"diametre_m": 0.08}}}})
    three_d = catalog["resources"]["three_d"]
    assert three_d
    assert not any(item["status"] == "available" for item in three_d)


def test_report_adapter_inclut_resource_summary():
    ui = adapt_backend_report({"rapports_pieces": {"piston": {"dimensions": {"diametre_m": 0.08}}}})
    assert "resources" in ui
    assert "resource_summary" in ui
    assert "sketches_available" in ui["resource_summary"]


def test_components_py_ne_importe_pas_backend():
    text = Path("frontend/gui/components.py").read_text(encoding="utf-8")
    forbidden = ("backend.components", "backend.ensemble", "import backend")
    assert not any(token in text for token in forbidden)

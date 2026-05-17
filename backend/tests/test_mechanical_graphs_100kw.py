from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from backend.scripts.validate_100kw_chain import valider_scenario_100kw


def test_graphiques_mecaniques_100kw_serialisables_et_sources(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    graphs = result["mechanical_graphs"]

    json.dumps(graphs, ensure_ascii=False)

    assert graphs["status"] == "available"
    assert graphs["graphs_available"] >= 5
    for graph in graphs["graphiques"]:
        assert "formula" in graph
        assert "source" in graph


def test_graphique_torsion_disponible_depuis_couple_et_materiaux_cdc(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    graph = _find(result["mechanical_graphs"]["graphiques"], "diametre_arbre_vs_contrainte_torsion")

    assert graph is not None
    assert graph["status"] == "available"
    assert graph["source"] == "backend.ensemble.calcul_stho_me"
    assert graph["formula"] == ["tau = 16*T/(pi*d^3)"]
    assert graph["dependencies"]["couple_moteur_thermique_nm"] > 0
    assert graph["dependencies"]["materiaux"]
    assert graph["markers"]
    assert all(marker["status"] == "candidate_from_cdc" for marker in graph["markers"])


def test_graphique_courant_bus_disponible_si_puissance_et_tension_backend(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    graph = _find(result["mechanical_graphs"]["graphiques"], "courant_bus_vs_tension")

    assert graph is not None
    assert graph["status"] == "available"
    assert graph["dependencies"]["puissance_bus_dc_w"] >= 100_000.0
    assert graph["dependencies"]["tension_bus_dc_v"] > 0
    assert graph["series"][0]["formula"] == "I = P/U"


def test_pertes_joule_ne_sont_pas_inventees_sans_resistance(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    graph = _find(result["mechanical_graphs"]["graphiques"], "pertes_joule_vs_courant")

    assert graph is not None
    assert graph["status"] == "missing_required"
    assert "resistance_electrique_ohm" in graph["missing"]
    assert graph["series"] == []


def test_exports_graphiques_et_dossier_cao_sont_crees(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)

    assert Path(result["paths"]["mechanical_graphs"]).is_file()
    assert Path(result["paths"]["cao_dossier"]).is_file()


def _find(items: list[Mapping[str, Any]], item_id: str) -> Mapping[str, Any] | None:
    for item in items:
        if isinstance(item, Mapping) and item.get("id") == item_id:
            return item
    return None

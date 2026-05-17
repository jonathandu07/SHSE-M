from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from backend.scripts.validate_100kw_chain import valider_scenario_100kw


def test_cao_dossier_100kw_est_json_serializable_et_progressif(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    dossier = result["cao_dossier"]
    validation = result["validation_chaine"]
    resume = dossier["resume"]

    json.dumps(dossier, ensure_ascii=False)

    assert validation["ok"] is True
    assert resume["step_export"] is False
    assert resume["solidworks_ready"] is False
    assert resume["sketches_available"] is True
    assert resume["views_3d_available"] is True
    assert resume["stress_graphs_available"] is True
    assert resume["drawing_data_available"] is True
    assert "materiau_verrouille" in resume["missing_for_solidworks"]


def test_croquis_arbre_disponible_si_couple_materiau_et_diametre_candidat(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    dossier = result["cao_dossier"]
    sketch = _find(dossier["croquis_2d"], "arbre_moteur_vue_longitudinale")

    assert sketch is not None
    assert sketch["statut"] == "exploitable_pour_redessin_solidworks"
    assert sketch["geometrie"]["cotes"][0]["nom"] == "diametre_min_torsion"
    assert sketch["geometrie"]["cotes"][0]["valeur"] is not None
    assert "longueur_arbre_m" in sketch["missing"]


def test_aucune_cote_manquante_n_est_remplacee_silencieusement(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    dossier = result["cao_dossier"]

    missing_cotes: list[Mapping[str, Any]] = []
    for sketch in dossier["croquis_2d"]:
        geometrie = sketch.get("geometrie") if isinstance(sketch, Mapping) else {}
        if not isinstance(geometrie, Mapping):
            continue
        for cote in geometrie.get("cotes", []):
            if isinstance(cote, Mapping) and cote.get("missing"):
                missing_cotes.append(cote)

    assert missing_cotes
    assert all(cote.get("valeur") is None for cote in missing_cotes)


def test_frontend_contract_expose_cao_indicative_sans_step(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    contract = result["frontend_contract"]

    assert contract["cao"]["available"] is False
    assert contract["cao"]["mode"] in {"3d_indicative", "croquis_cotes", "conceptuel_non_cote"}
    assert contract["cao"]["step_export"] is False
    assert contract["cao"]["solidworks_ready"] is False
    assert contract["cao"]["sketches_available"] is True
    assert contract["cao"]["stress_graphs_available"] is True
    assert contract["cao_dossier"]["resume"]["step_export"] is False


def _find(items: list[Mapping[str, Any]], item_id: str) -> Mapping[str, Any] | None:
    for item in items:
        if isinstance(item, Mapping) and item.get("id") == item_id:
            return item
    return None

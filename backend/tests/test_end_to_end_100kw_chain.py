from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from backend.modules.systeme.status import STATUS_VALIDATED_BY_OPTIMIZATION
from backend.scripts.validate_100kw_chain import valider_scenario_100kw


def test_end_to_end_100kw_chain_pre_dimensionnement(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    rapport = result["rapport"]
    frontend_contract = result["frontend_contract"]
    diagnostic = result["diagnostic"]
    validation = result["validation_chaine"]

    json.dumps(rapport, ensure_ascii=False)
    json.dumps(frontend_contract, ensure_ascii=False)
    json.dumps(diagnostic, ensure_ascii=False)

    for section in (
        "synthese",
        "strategie_energie",
        "sous_systemes",
        "optimisation",
        "resolution_inconnues",
        "frontend",
        "tracabilite",
    ):
        assert section in rapport
        assert rapport[section] is not None

    for subsystem in (
        "moteur_electrique",
        "batterie",
        "alternateur",
        "moteur_thermique",
        "boite_crabots",
    ):
        assert _present(_get_path(rapport, f"sous_systemes.{subsystem}"))

    assert _get_path(rapport, "synthese.moteur_electrique.puissance_sortie_w") == pytest.approx(100_000.0)
    assert _get_path(rapport, "synthese.systeme.P_bus_dc_design_w") >= 100_000.0
    assert _get_path(rapport, "synthese.etat.optimisation_lancee") is True

    assert validation["ok"] is True
    assert validation["score_chaine_100"] >= 80.0
    assert validation["valeurs"]["puissance_sortie_moteur_electrique_w"] == pytest.approx(100_000.0)
    assert validation["valeurs"]["puissance_bus_dc_design_w"] >= validation["valeurs"]["puissance_sortie_moteur_electrique_w"]
    assert validation["valeurs"]["puissance_alternateur_electrique_w"] is not None
    assert validation["valeurs"]["puissance_moteur_thermique_arbre_w"] is not None
    assert validation["valeurs"]["couple_moteur_thermique_nm"] is not None
    assert validation["valeurs"]["rapport_boite_alt"] is not None

    assert frontend_contract["summary"]["chain_validation"]["ok"] is True
    assert frontend_contract["cao"]["available"] is False

    if not validation["ok"]:
        assert diagnostic["causes_racines"]

    _assert_no_candidate_validated_without_optimization_trace(rapport)

    for path in result["paths"].values():
        assert Path(path).is_file()


def test_100kw_frontend_contract_blocks_real_cao_when_solidworks_missing(tmp_path: Path) -> None:
    result = valider_scenario_100kw(out_dir=tmp_path, strict=False)
    contract = result["frontend_contract"]

    assert contract["cao"]["available"] is False
    assert contract["cao"]["status"] == "missing_required"
    assert "Dossier de definition" in contract["cao"]["reason"]


def _assert_no_candidate_validated_without_optimization_trace(rapport: Mapping[str, Any]) -> None:
    opt_runs = _get_path(rapport, "tracabilite.optimization_runs") or _get_path(rapport, "tracabilite.optimisations") or []
    candidates = []
    candidates.extend(_get_path(rapport, "resolution_inconnues.candidates") or [])
    candidates.extend(_get_path(rapport, "resolution_candidates.candidates") or [])
    candidates.extend(_get_path(rapport, "tracabilite.candidates") or [])

    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        status = candidate.get("statut") or candidate.get("status")
        if status == STATUS_VALIDATED_BY_OPTIMIZATION:
            assert opt_runs, f"candidate valide sans trace optimisation: {candidate}"


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, Mapping):
        return any(_present(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return True

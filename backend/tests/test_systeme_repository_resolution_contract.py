from pathlib import Path

from backend.ensemble.STHO_ME import STHO_ME
from backend.modules.systeme.data_repository import SystemDataRepository
from backend.modules.systeme.frontend_contract import build_frontend_contract
from backend.modules.systeme.resolution_inconnues import DonneeCandidate, resoudre_inconnues_systeme
from backend.modules.systeme.status import (
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_PARTIAL,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    normalize_status,
)
from backend.modules.systeme.validation_candidates import valider_candidate


def _clean_report():
    return {"inconnues": {"impossibles": [], "partielles": [], "bloquantes": []}, "cao": {"available": True}}


def test_frontend_contract_ne_contient_pas_de_valeur_inventee():
    rapport = {
        "meta": {"project_id": "p1"},
        "synthese": {"moteur_thermique": {"alesage_m": 0.08}},
        "tracabilite": {"valeurs": {"synthese.moteur_thermique.alesage_m": {"source": "computed", "from": "STHO_ME"}}},
        "inconnues": {"impossibles": [], "partielles": []},
        "cao": {"solidworks_ready_detaille": False},
    }

    contract = build_frontend_contract(rapport, project_id="p1")

    assert contract["fields"][0]["value"] == rapport["synthese"]["moteur_thermique"]["alesage_m"]
    assert all(field["status"] in {"computed", "derived", "database", "partial"} for field in contract["fields"])


def test_frontend_contract_ne_valide_pas_une_valeur_sans_trace():
    rapport = {
        "meta": {"project_id": "p1"},
        "synthese": {"moteur_thermique": {"alesage_m": 0.08}},
        "inconnues": {"impossibles": [], "partielles": []},
        "cao": {"solidworks_ready_detaille": False},
    }

    contract = build_frontend_contract(rapport, project_id="p1")

    assert contract["fields"][0]["status"] == STATUS_PARTIAL
    assert contract["fields"][0]["confidence"] == "untraced_report_value"


def test_libelles_legacy_optimisation_ne_valident_pas_sans_trace():
    assert normalize_status("optimisee") == STATUS_CANDIDATE_FROM_CDC
    assert normalize_status("candidate_optimized") == STATUS_CANDIDATE_FROM_CDC
    assert normalize_status("optimisee") != STATUS_VALIDATED_BY_OPTIMIZATION


def test_inconnue_en_bdd_est_recuperee_source_database(tmp_path):
    repo = SystemDataRepository(db_path=str(tmp_path / "repo.json"))
    repo.save_project_parameter(
        project_id="p1",
        path="tension_bus_dc_v",
        name="Tension bus",
        value=420.0,
        unit="V",
        source="essai_bdd",
        status="database",
    )
    result = resoudre_inconnues_systeme(
        config={},
        rapport={"inconnues": {"partielles": [{"nom": "tension_bus_dc_v", "path": "tension_bus_dc_v"}], "impossibles": []}},
        cahier_des_charges={},
        repository=repo,
        project_id="p1",
        recalculer=lambda cfg: _clean_report(),
    )

    assert result.accepte is True
    assert result.config_completee["tension_bus_dc_v"] == 420.0
    assert any(c.source == "database" for c in result.candidates)


def test_inconnue_deductible_est_source_computed():
    result = resoudre_inconnues_systeme(
        config={"puissance_bus_dc_w": 84_000.0, "tension_bus_dc_v": 420.0},
        rapport={"inconnues": {"partielles": [{"nom": "courant_bus_dc_a", "path": "courant_bus_dc_a"}], "impossibles": []}},
        cahier_des_charges={},
        recalculer=lambda cfg: _clean_report(),
    )

    assert result.accepte is True
    assert result.config_completee["courant_bus_dc_a"] == 200.0
    assert any(c.source == "computed" for c in result.candidates)


def test_mode_strict_n_injecte_pas_tension_ni_rpm_depuis_cdc():
    result = resoudre_inconnues_systeme(
        config={},
        rapport={
            "inconnues": {
                "partielles": [
                    {"nom": "tension_bus_dc_v", "path": "tension_bus_dc_v"},
                    {"nom": "rpm_moteur", "path": "rpm_moteur_nominal"},
                ],
                "impossibles": [],
            }
        },
        cahier_des_charges={"tension_bus_dc_v": 400.0, "rpm_moteur_min": 2500.0, "rpm_moteur_max": 3500.0},
        strict=True,
        recalculer=lambda cfg: _clean_report(),
    )

    assert result.accepte is False
    assert "tension_bus_dc_v" not in result.config_completee
    assert "rpm_moteur_nominal" not in result.config_completee
    assert all(c.statut != "computed" for c in result.candidates)


def test_candidate_genere_depuis_cahier_des_charges_est_trace():
    result = resoudre_inconnues_systeme(
        config={"course_m": 0.1},
        rapport={"inconnues": {"partielles": [{"nom": "longueur_bielle_m", "path": "pieces.bielle.longueur_bielle_m"}], "impossibles": []}},
        cahier_des_charges={"ratio_bielle_course_min": 3.0, "ratio_bielle_course_max": 3.5},
        recalculer=lambda cfg: _clean_report(),
    )

    assert result.accepte is False
    assert "pieces" not in result.config_completee
    assert any(c.source == "generated_from_cahier_des_charges" for c in result.candidates)
    assert any(c.statut == "candidate_from_cdc" for c in result.candidates)


def test_candidate_incompatible_est_rejete():
    candidate = DonneeCandidate(
        nom="longueur_bielle_m",
        path="pieces.bielle.longueur_bielle_m",
        valeur=0.8,
        source="generated_from_cahier_des_charges",
        statut="candidate_from_cdc",
        raison="Candidat de test issu d'une borne CDC.",
        dependances=["cdc.borne"],
        metadata={"domaine": {"min": 0.2, "max": 0.5}},
    )

    validation = valider_candidate(
        candidate=candidate,
        rapport_avant=_clean_report(),
        rapport_apres=_clean_report(),
        cahier_des_charges={"bornes": {"pieces.bielle.longueur_bielle_m": {"min": 0.2, "max": 0.5}}},
    )

    assert validation["ok"] is False
    assert "borne" in validation["raison"]


def test_stho_me_analyser_fonctionne_sans_systeme_complet():
    rapport = STHO_ME.depuis_config(
        {
            "meta": {"project_id": "p1"},
            "analyses": {
                "moteur_thermique_definition": {
                    "puissance_visee_w": 40_000.0,
                    "rpm": 3000.0,
                    "pression_moyenne_effective_pa": 900_000.0,
                }
            },
        }
    ).analyser(optimize=False)

    assert rapport["meta"]["orchestrateur"] == "STHO_ME.py"
    assert rapport["construction"]["composants"]["systeme_complet"]["statut"] == "remplace_par_fallback_STHO_ME"
    assert "frontend" in rapport


def test_aucun_import_direct_obligatoire_systeme_complet():
    root = Path("backend")
    offenders = []
    for path in root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        import_from = "from backend.ensemble." + "systeme_complet import"
        import_module = "import backend.ensemble." + "systeme_complet"
        if import_from in text or import_module in text:
            offenders.append(str(path))
    assert offenders == []


def test_cao_incomplete_contract_bloque_3d_reelle():
    contract = build_frontend_contract(
        {
            "inconnues": {"impossibles": [{"champ": "synthese.moteur_thermique.alesage_m"}], "partielles": []},
            "cao": {"solidworks_ready_detaille": False},
        }
    )

    assert contract["cao"]["available"] is False
    assert "synthese.moteur_thermique.alesage_m" in contract["cao"]["missing_required_fields"]


def test_inconnues_dedoublonnees():
    result = resoudre_inconnues_systeme(
        config={},
        rapport={
            "inconnues": {
                "partielles": [
                    {"nom": "x", "path": "a.b", "raison": "manquant"},
                    {"nom": "x", "path": "a.b", "raison": "manquant"},
                ],
                "impossibles": [],
            }
        },
        cahier_des_charges={},
    )

    assert len(result.inconnues_restantes) == 1


def test_repository_locked_non_ecrase_sans_autorisation(tmp_path):
    repo = SystemDataRepository(db_path=str(tmp_path / "repo.json"))
    repo.save_project_parameter(
        project_id="p1",
        path="tension_bus_dc_v",
        name="Tension bus",
        value=420.0,
        source="input",
        status="input",
        locked=True,
    )
    try:
        repo.save_project_parameter(
            project_id="p1",
            path="tension_bus_dc_v",
            name="Tension bus",
            value=430.0,
            source="test",
            status="input",
        )
    except ValueError as exc:
        assert "verrouille" in str(exc)
    else:
        raise AssertionError("La valeur verrouillee a ete ecrasee sans autorisation.")

import sys
import types
from dataclasses import dataclass

import pytest

from backend.ensemble.STHO_ME import concevoir_systeme_stho_me
from backend.ensemble.optimisation import optimiser_rapport_sthome
from backend.ensemble.resolution_inconnues import (
    STATUS_CANDIDATE_FROM_POWER_PROFILE,
    get_alias_paths,
    resoudre_inconnues_systeme,
)
from backend.ensemble.strategie_energie import analyser_strategie_energie


def test_resolution_stricte_puissance_seule_ne_injecte_pas_profil():
    report = resoudre_inconnues_systeme({"puissance_sortie_kw": 100}, strict=True)

    assert report.payload_resolu["puissance_sortie_w"] == pytest.approx(100_000.0)
    assert report.payload_resolu["puissance_sortie_moteur_electrique_w"] == pytest.approx(100_000.0)
    assert "puissance_bus_dc_w" not in report.payload_resolu
    assert "tension_bus_dc_v" not in report.payload_resolu
    assert "rpm_moteur" not in report.payload_resolu
    assert "alesage_m" not in report.payload_resolu
    assert not any(h.status == STATUS_CANDIDATE_FROM_POWER_PROFILE for h in report.hypotheses)
    assert any(c.statut == STATUS_CANDIDATE_FROM_POWER_PROFILE for c in report.candidates)


def test_resolution_pre_dimensionnement_trace_les_candidats_profil():
    report = resoudre_inconnues_systeme(
        {"puissance_sortie_kw": 100},
        strict=False,
        mode="pre_dimensionnement",
    )

    assert report.payload_resolu["puissance_sortie_w"] == pytest.approx(100_000.0)
    assert report.payload_resolu["puissance_bus_dc_w"] > 100_000.0
    assert any(h.status == STATUS_CANDIDATE_FROM_POWER_PROFILE for h in report.hypotheses)
    assert any(c["statut"] == STATUS_CANDIDATE_FROM_POWER_PROFILE for c in report.tracabilite["candidats"])


def test_orchestrateur_strict_expose_sections_sans_moteur_fictif():
    rapport = concevoir_systeme_stho_me({"puissance_sortie_kw": 100}, strict=True, optimize=False)

    for key in ("synthese", "resolution_inconnues", "frontend", "cao", "inconnues"):
        assert key in rapport
    assert "strategie_energie" in rapport["rapports"]
    assert rapport["rapports"]["optimisation"]["mode"] == "desactive"
    assert rapport["synthese"]["puissance_sortie_max_demandee_kw"] == pytest.approx(100.0)
    assert rapport["synthese"]["architecture_moteur"] is None
    assert rapport["synthese"]["alesage_m"] is None
    assert rapport["synthese"]["P_arbre_thermique_requise_pleine_sortie_kw"] is None
    assert rapport["cao"]["sketches_available"] is False
    assert "missing_reason" in rapport["frontend"]["resume_cards"][1]


def test_alias_puissance_sortie_depuis_plusieurs_chemins():
    aliases = get_alias_paths("puissance_sortie_w")
    assert "sortie.puissance_sortie_max_w" in aliases

    report = resoudre_inconnues_systeme({"sortie": {"puissance_sortie_max_w": 100_000.0}}, strict=True)
    assert report.payload_resolu["puissance_sortie_w"] == pytest.approx(100_000.0)
    assert report.payload_resolu["puissance_sortie_moteur_electrique_w"] == pytest.approx(100_000.0)


def test_optimisation_expose_actions_score_inconnues_et_trace():
    rapport = {
        "synthese": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "rapports": {"pieces": {}, "composants": {}},
    }

    out = optimiser_rapport_sthome(rapport_backend=rapport, strict=True, max_iterations=1)

    assert "actions" in out
    assert "score_global" in out
    assert "inconnues" in out
    assert "trace" in out
    assert "historique_iterations" in out
    assert "patch_configuration" in out


def test_strategie_energie_refuse_fallback_bus_egale_sortie():
    out = analyser_strategie_energie(
        etat_systeme={"puissance_sortie_demandee_w": 100_000.0, "v_bus_dc_v": 400.0},
        composants={"batterie": {}},
    )

    assert out["bilan_bus_dc"]["puissance_electrique_usage_w"] is None
    assert out["bilan_bus_dc"]["puissance_bus_dc_totale_w"] is None
    assert any(item["nom"] == "p_traction_bus_dc_w" for item in out["inconnues"]["partielles"])


def test_pieces_recoivent_les_pieces_precedentes(monkeypatch):
    source_module = types.ModuleType("source_piece")
    sink_module = types.ModuleType("sink_piece")

    @dataclass
    class SourcePiece:
        def analyser(self, *, strict=False):
            return {"piece": "source_piece", "cao": {"solidworks_ready": False}}

    @dataclass
    class SinkPiece:
        source_piece: object | None = None

        def analyser(self, *, strict=False):
            return {
                "piece": "sink_piece",
                "liaisons": {"source_piece_presente": self.source_piece is not None},
                "cao": {"solidworks_ready": False},
            }

    source_module.SourcePiece = SourcePiece
    sink_module.SinkPiece = SinkPiece
    monkeypatch.setitem(sys.modules, "source_piece", source_module)
    monkeypatch.setitem(sys.modules, "sink_piece", sink_module)

    rapport = concevoir_systeme_stho_me(
        {"puissance_sortie_kw": 100, "pieces": {"source_piece": {}, "sink_piece": {}}},
        strict=True,
        optimize=False,
    )

    assert rapport["rapports"]["pieces"]["sink_piece"]["liaisons"]["source_piece_presente"] is True
    assert "source_piece" in rapport["construction"]["pieces"]["sink_piece"]["contexte_recu"]


def test_anciennes_fonctions_backend_restent_importables():
    import backend.main as main
    import backend.modules.main.main_systeme as main_systeme

    assert callable(main.analyser_depuis_puissance)
    assert callable(main.optimiser_depuis_puissance)
    assert callable(main.generer_rapport_json)
    assert callable(main.dimensionner_systeme_shsem)
    assert callable(main_systeme.main_systeme)

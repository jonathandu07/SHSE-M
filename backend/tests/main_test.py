import importlib
import json
from typing import Any, Dict

import pytest


@pytest.fixture
def main_mod():
    return importlib.import_module("backend.main")


class _Recorder:
    """Objet simple qui mémorise les kwargs reçus."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = dict(kwargs)
        type(self).instances.append(self)

    @classmethod
    def reset(cls):
        cls.instances = []


class _FakeSystemeComplet:
    def __init__(self, **kwargs):
        self.kwargs = dict(kwargs)
        self.calls = []

    def analyser(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "synthese": {
                "moteur_thermique": {
                    "architecture": "ligne",
                    "nombre_cylindres": 2,
                    "alesage_m": 0.08,
                    "course_m": 0.06,
                    "rpm_nominal": 3000.0,
                    "pme_pa": 8.0e5,
                    "cylindree_totale_cc": 603.19,
                    "puissance_requise_W": 42000.0,
                    "couple_requis_Nm": 130.0,
                    "epaisseur_cylindre_retenue_m": 0.004,
                },
                "vehicule": {
                    "puissance_bus_dc_design_w": 47000.0,
                },
                "batterie": {
                    "energie_utile_kwh": 24.0,
                },
            },
            "cao": {
                "moteur_thermique": {
                    "alesage_mm": 80.0,
                    "course_mm": 60.0,
                }
            },
            "liaisons": {
                "moteur_thermique_exigences": {
                    "rpm_moteur_thermique": 3000.0,
                }
            },
            "entrees": {
                "moteur_thermique_criteres": {
                    "pression_max_pa": 3.0e6,
                }
            },
        }


class _FakeOptimisationSysteme:
    def __init__(self, **kwargs):
        self.kwargs = dict(kwargs)

    def analyser(self):
        return {
            "synthese_optimisation": {
                "score_coherence_100": 91.0,
                "score_global_100": 88.5,
            }
        }


class _FakeDriveChainGenerator:
    def __init__(self):
        self.results = None
        self.seen = []

    def compute(self, power_kw: float):
        self.seen.append(power_kw)
        self.results = {"puissance_kw": power_kw, "ok": True}


def test_helpers_validation_and_navigation(main_mod):
    assert main_mod._is_finite(1)
    assert main_mod._is_finite(1.5)
    assert not main_mod._is_finite(True)
    assert not main_mod._is_finite(float("inf"))
    assert not main_mod._is_finite("3")

    assert main_mod._req_finite("x", 2) == 2.0
    with pytest.raises(ValueError, match="x doit être un nombre fini"):
        main_mod._req_finite("x", None)

    assert main_mod._req_pos("p", 0, strict=False) == 0.0
    assert main_mod._req_pos("p", 1) == 1.0
    with pytest.raises(ValueError, match="p doit être > 0"):
        main_mod._req_pos("p", 0)
    with pytest.raises(ValueError, match="p doit être >= 0"):
        main_mod._req_pos("p", -1, strict=False)

    assert main_mod._safe_float(4) == 4.0
    assert main_mod._safe_float("4") is None
    assert main_mod._safe_dict({"a": 1}) == {"a": 1}
    assert main_mod._safe_dict(None) == {}
    assert main_mod._first_finite(None, "x", 2, 3) == 2.0
    assert main_mod._first_finite(None, "x") is None
    assert main_mod._get_nested({"a": {"b": {"c": 9}}}, "a", "b", "c") == 9
    assert main_mod._get_nested({"a": 1}, "a", "b") is None


def test_main_imports_real_reorganized_components(main_mod):
    expected = {
        "MoteurElectrique",
        "Batterie",
        "Alternateur",
        "MoteurThermique",
        "BoiteCrabots",
        "Architecture",
        "DriveChainGenerator",
    }

    for name in expected:
        assert getattr(main_mod, name) is not None, name


def test_dimensionner_systeme_shsem_simple_uses_reorganized_system_modules(main_mod):
    result = main_mod.dimensionner_systeme_shsem_simple(40.0)

    assert result["N_cyl"] == 4
    assert result["Architecture"] == "L4"
    assert result["Bore_mm"] > 0.0
    assert result["Stroke_mm"] > 0.0
    assert sorted(result["drivetrain"]) == ["alternateur", "batterie", "boite_crabots", "moteur_electrique"]


def test_constructors_forward_expected_arguments(monkeypatch, main_mod):
    class FakeMoteurElectrique(_Recorder):
        pass

    class FakeBatterie(_Recorder):
        pass

    class FakeAlternateur(_Recorder):
        pass

    class FakeMoteurThermique(_Recorder):
        pass

    class FakeBoiteCrabots(_Recorder):
        pass

    class FakeArchitecture(_Recorder):
        pass

    for cls in (
        FakeMoteurElectrique,
        FakeBatterie,
        FakeAlternateur,
        FakeMoteurThermique,
        FakeBoiteCrabots,
        FakeArchitecture,
    ):
        cls.reset()

    monkeypatch.setattr(main_mod, "MoteurElectrique", FakeMoteurElectrique)
    monkeypatch.setattr(main_mod, "Batterie", FakeBatterie)
    monkeypatch.setattr(main_mod, "Alternateur", FakeAlternateur)
    monkeypatch.setattr(main_mod, "MoteurThermique", FakeMoteurThermique)
    monkeypatch.setattr(main_mod, "BoiteCrabots", FakeBoiteCrabots)
    monkeypatch.setattr(main_mod, "Architecture", FakeArchitecture)

    me = main_mod.construire_moteur_electrique(tension_bus_v=650.0, rendement_moteur=0.95)
    ba = main_mod.construire_batterie(tension_nominale_v=700.0, rendement_charge=0.91)
    alt = main_mod.construire_alternateur()
    mt = main_mod.construire_moteur_thermique_base(
        temps_moteur=2,
        nombre_cylindres=3,
        alesage_m=0.09,
        course_m=0.07,
        rendement_mecanique_nominal=0.87,
    )
    bc = main_mod.construire_boite_crabots()
    ar = main_mod.construire_architecture(temps_moteur=2, rendement_mecanique=0.81, ratio_course_alesage_max=1.1)

    assert isinstance(me, FakeMoteurElectrique)
    assert me.kwargs["tension_bus_v"] == 650.0
    assert me.kwargs["rendement_moteur"] == 0.95

    assert isinstance(ba, FakeBatterie)
    assert ba.kwargs["tension_nominale_v"] == 700.0
    assert ba.kwargs["rendement_charge"] == 0.91

    assert isinstance(alt, FakeAlternateur)
    assert alt.kwargs == {"connexion": "etoile", "nombre_poles": 12}

    assert isinstance(mt, FakeMoteurThermique)
    assert mt.kwargs["temps_moteur"] == 2
    assert mt.kwargs["nombre_cylindres"] == 3
    assert mt.kwargs["alesage_m"] == 0.09
    assert mt.kwargs["course_m"] == 0.07
    assert mt.kwargs["rendement_mecanique_nominal"] == 0.87

    assert isinstance(bc, FakeBoiteCrabots)
    assert bc.kwargs == {}

    assert isinstance(ar, FakeArchitecture)
    assert ar.kwargs == {
        "temps_moteur": 2,
        "rendement_mecanique": 0.81,
        "ratio_course_alesage_max": 1.1,
    }


def test_construire_pieces_depuis_systeme_instantiates_expected_parts(monkeypatch, main_mod):
    created: Dict[str, Any] = {}

    def make_part(name: str):
        class Part:
            def __init__(self, **kwargs):
                self.kwargs = dict(kwargs)
                created[name] = self

        Part.__name__ = f"Fake{name.title().replace('_', '')}"
        return Part

    mapping = {
        "Cylindre": make_part("cylindre"),
        "Piston": make_part("piston"),
        "JointPiston": make_part("joint_piston"),
        "ArbrePiston": make_part("arbre_piston"),
        "CorpsBielle": make_part("bielle"),
        "CoussinetArbrePiston": make_part("coussinet_arbre_piston"),
        "ArbreVilbrequin": make_part("arbre_vilebrequin"),
        "Vilbrequin": make_part("vilbrequin"),
        "RoulementAiguilleArbre": make_part("roulement_aiguille_arbre"),
        "RoulementAiguilleArbreVilebrequin": make_part("roulement_aiguille_arbre_vilebrequin"),
        "CouvercleCylindre": make_part("couvercle_cylindre"),
        "VisCouvercleCylindre": make_part("vis_couvercle_cylindre"),
        "Deplaceur": make_part("deplaceur"),
        "JointDeplaceur": make_part("joint_deplaceur"),
    }
    for attr, fake in mapping.items():
        monkeypatch.setattr(main_mod, attr, fake)

    rapport_systeme = {
        "synthese": {
            "moteur_thermique": {
                "alesage_m": 0.08,
                "course_m": 0.06,
                "nombre_cylindres": 2,
                "rpm_nominal": 3100.0,
                "pme_pa": 7.5e5,
                "couple_requis_Nm": 140.0,
                "epaisseur_cylindre_retenue_m": 0.0035,
            }
        },
        "cao": {"moteur_thermique": {"alesage_mm": 80.0, "course_mm": 60.0}},
        "liaisons": {"moteur_thermique_exigences": {"rpm_moteur_thermique": 3000.0}},
        "entrees": {"moteur_thermique_criteres": {"pression_max_pa": 2.5e6}},
    }

    pieces = main_mod.construire_pieces_depuis_systeme(rapport_systeme=rapport_systeme)

    expected_keys = {
        "cylindre",
        "piston",
        "joint_piston",
        "arbre_piston",
        "bielle",
        "coussinet_arbre_piston",
        "arbre_vilebrequin",
        "vilbrequin",
        "roulement_aiguille_arbre",
        "roulement_aiguille_arbre_vilebrequin",
        "couvercle_cylindre",
        "vis_couvercle_cylindre",
        "deplaceur",
        "joint_deplaceur",
    }
    assert expected_keys.issubset(pieces.keys())

    cyl = pieces["cylindre"]
    assert cyl.kwargs["alesage_m"] == 0.08
    assert cyl.kwargs["course_m"] == 0.06
    assert cyl.kwargs["longueur_utile_m"] == pytest.approx(0.09)
    assert cyl.kwargs["pression_service_pa"] == 7.5e5
    assert cyl.kwargs["pression_max_pa"] == 2.5e6
    assert cyl.kwargs["epaisseur_imposee_m"] == 0.0035

    piston = pieces["piston"]
    assert piston.kwargs["cylindre"] is cyl
    assert piston.kwargs["pression_max_pa"] == 2.5e6
    assert piston.kwargs["rpm"] == 3100.0

    vilbrequin = pieces["vilbrequin"]
    assert vilbrequin.kwargs["nb_manetons"] == 2
    assert vilbrequin.kwargs["nb_journaux_principaux"] == 3
    assert vilbrequin.kwargs["course_m"] == 0.06
    assert vilbrequin.kwargs["couple_max_Nm"] == 140.0


def test_construire_pieces_depuis_systeme_tolerates_missing_optional_modules(monkeypatch, main_mod):
    monkeypatch.setattr(main_mod, "Cylindre", None)
    monkeypatch.setattr(main_mod, "Piston", None)
    monkeypatch.setattr(main_mod, "JointPiston", None)
    monkeypatch.setattr(main_mod, "ArbrePiston", None)
    monkeypatch.setattr(main_mod, "CorpsBielle", None)
    monkeypatch.setattr(main_mod, "CoussinetArbrePiston", None)
    monkeypatch.setattr(main_mod, "ArbreVilbrequin", None)
    monkeypatch.setattr(main_mod, "Vilbrequin", None)
    monkeypatch.setattr(main_mod, "RoulementAiguilleArbre", None)
    monkeypatch.setattr(main_mod, "RoulementAiguilleArbreVilebrequin", None)
    monkeypatch.setattr(main_mod, "CouvercleCylindre", None)
    monkeypatch.setattr(main_mod, "VisCouvercleCylindre", None)
    monkeypatch.setattr(main_mod, "Deplaceur", None)
    monkeypatch.setattr(main_mod, "JointDeplaceur", None)

    pieces = main_mod.construire_pieces_depuis_systeme(
        rapport_systeme={
            "synthese": {"moteur_thermique": {"alesage_m": 0.08, "course_m": 0.06}},
        }
    )

    assert pieces == {}


def test_dimensionner_systeme_shsem_returns_complete_config(monkeypatch, main_mod):
    fake_system_holder = {}

    def fake_builder(name):
        return {"name": name}

    monkeypatch.setattr(main_mod, "construire_moteur_electrique", lambda: fake_builder("me"))
    monkeypatch.setattr(main_mod, "construire_batterie", lambda: fake_builder("bat"))
    monkeypatch.setattr(main_mod, "construire_alternateur", lambda: fake_builder("alt"))
    monkeypatch.setattr(main_mod, "construire_moteur_thermique_base", lambda: fake_builder("mt"))
    monkeypatch.setattr(main_mod, "construire_boite_crabots", lambda: fake_builder("bc"))
    monkeypatch.setattr(main_mod, "construire_architecture", lambda: fake_builder("arch"))

    def fake_systeme_ctor(**kwargs):
        obj = _FakeSystemeComplet(**kwargs)
        fake_system_holder["obj"] = obj
        return obj

    monkeypatch.setattr(main_mod, "SystemeComplet", fake_systeme_ctor)
    monkeypatch.setattr(main_mod, "OptimisationSysteme", _FakeOptimisationSysteme)

    fake_pieces = {
        "cylindre": object(),
        "piston": object(),
        "joint_piston": object(),
        "deplaceur": object(),
        "joint_deplaceur": object(),
        "bielle": object(),
        "arbre_piston": object(),
        "coussinet_arbre_piston": object(),
        "arbre_vilebrequin": object(),
        "vilbrequin": object(),
        "roulement_aiguille_arbre": object(),
        "roulement_aiguille_arbre_vilebrequin": object(),
        "couvercle_cylindre": object(),
        "vis_couvercle_cylindre": object(),
        "clavette_arbre": object(),
    }
    monkeypatch.setattr(main_mod, "construire_pieces_depuis_systeme", lambda rapport_systeme: fake_pieces)
    monkeypatch.setattr(
        main_mod,
        "dimensionner_pieces_completes",
        lambda **kwargs: {"legacy_piece_ok": True, "inputs": kwargs},
    )
    monkeypatch.setattr(main_mod, "DriveChainGenerator", _FakeDriveChainGenerator)

    config = main_mod.dimensionner_systeme_shsem(
        puissance_traction_kw=40.0,
        charger_batterie=True,
        distance_km=200.0,
        vitesse_moyenne_kmh=80.0,
        masse_estimee_max_kg=500.0,
        cout_matiere_max_eur=1500.0,
        indice_maintenance_max=7.0,
        duree_vie_cible_h=4000.0,
    )

    assert config["meta"]["backend"] == "main.py"
    assert config["meta"]["orchestrateur"] == "SystemeComplet + OptimisationSysteme"

    resume = config["resume_gui"]
    assert resume["N_cyl"] == 2
    assert resume["Architecture"] == "ligne"
    assert resume["Bore_mm"] == 80.0
    assert resume["Stroke_mm"] == 60.0
    assert resume["RPM"] == 3000.0
    assert resume["PME"] == 8.0e5
    assert resume["vd_tot_cc"] == 603.19
    assert resume["P_bus_dc_design_w"] == 47000.0
    assert resume["energie_batterie_kwh"] == 24.0
    assert resume["score_coherence_100"] == 91.0
    assert resume["score_global_100"] == 88.5

    assert config["pieces"] is fake_pieces
    assert config["optimisation"]["synthese_optimisation"]["score_global_100"] == 88.5
    assert config["legacy"]["dimensionner_pieces_completes"]["legacy_piece_ok"] is True
    assert config["legacy"]["drivechain"] == {"puissance_kw": 40.0, "ok": True}

    system_call = fake_system_holder["obj"].calls[0]
    assert system_call["puissance_moyenne_kw"] == 40.0
    assert system_call["puissance_pic_kw"] == 40.0
    assert system_call["distance_km"] == 200.0
    assert system_call["vitesse_moyenne_kmh"] == 80.0
    assert system_call["calculer_puissance_charge_requise"] is True
    assert system_call["scenario_bus_dc"] == "traction_plus_charge"
    assert system_call["puissance_elec_alt_cible_w"] is None
    assert system_call["puissance_auxiliaire_w"] == 0.0
    assert system_call["masse_estimee_max_kg"] == 500.0
    assert system_call["cout_matiere_max_eur"] == 1500.0
    assert system_call["indice_maintenance_max"] == 7.0
    assert system_call["duree_vie_cible_h"] == 4000.0
    assert system_call["rapports_boite_candidates"] is None
    assert "puissance_auxiliaire_w absente" in " ".join(config.get("notes_modele") or [])
    assert any(
        item.get("nom") == "puissance_auxiliaire_w"
        for item in ((config.get("inconnues") or {}).get("partielles") or [])
    )


def test_dimensionner_systeme_shsem_without_battery_charge_and_legacy_errors(monkeypatch, main_mod):
    fake_system_holder = {}

    monkeypatch.setattr(main_mod, "construire_moteur_electrique", lambda: object())
    monkeypatch.setattr(main_mod, "construire_batterie", lambda: object())
    monkeypatch.setattr(main_mod, "construire_alternateur", lambda: object())
    monkeypatch.setattr(main_mod, "construire_moteur_thermique_base", lambda: object())
    monkeypatch.setattr(main_mod, "construire_boite_crabots", lambda: object())
    monkeypatch.setattr(main_mod, "construire_architecture", lambda: object())

    def fake_systeme_ctor(**kwargs):
        obj = _FakeSystemeComplet(**kwargs)
        fake_system_holder["obj"] = obj
        return obj

    monkeypatch.setattr(main_mod, "SystemeComplet", fake_systeme_ctor)
    monkeypatch.setattr(main_mod, "OptimisationSysteme", _FakeOptimisationSysteme)
    monkeypatch.setattr(main_mod, "construire_pieces_depuis_systeme", lambda rapport_systeme: {})

    def boom_legacy(**kwargs):
        raise RuntimeError("legacy boom")

    class BrokenDriveChain:
        def compute(self, power_kw: float):
            raise RuntimeError("drivechain boom")

    monkeypatch.setattr(main_mod, "dimensionner_pieces_completes", boom_legacy)
    monkeypatch.setattr(main_mod, "DriveChainGenerator", BrokenDriveChain)

    config = main_mod.dimensionner_systeme_shsem(
        puissance_traction_kw=25.0,
        charger_batterie=False,
    )

    system_call = fake_system_holder["obj"].calls[0]
    assert system_call["calculer_puissance_charge_requise"] is False
    assert system_call["scenario_bus_dc"] == "traction"
    assert system_call["puissance_elec_alt_cible_w"] is None

    assert "legacy boom" in config["legacy"]["dimensionner_pieces_completes_erreur"]
    assert "drivechain boom" in config["legacy"]["drivechain_erreur"]


def test_dimensionner_systeme_shsem_surfaces_nested_component_piece_reports(monkeypatch, main_mod):
    monkeypatch.setattr(main_mod, "construire_moteur_electrique", lambda: object())
    monkeypatch.setattr(main_mod, "construire_batterie", lambda: object())
    monkeypatch.setattr(main_mod, "construire_alternateur", lambda: object())
    monkeypatch.setattr(main_mod, "construire_moteur_thermique_base", lambda: object())
    monkeypatch.setattr(main_mod, "construire_boite_crabots", lambda: object())
    monkeypatch.setattr(main_mod, "construire_architecture", lambda: object())
    monkeypatch.setattr(main_mod, "SystemeComplet", lambda **kwargs: _FakeSystemeComplet(**kwargs))
    monkeypatch.setattr(main_mod, "OptimisationSysteme", _FakeOptimisationSysteme)
    monkeypatch.setattr(main_mod, "construire_pieces_depuis_systeme", lambda **kwargs: ({}, {"construction": {}, "inconnues": {"impossibles": [], "partielles": []}}))
    monkeypatch.setattr(main_mod, "analyser_pieces", lambda pieces: {})
    monkeypatch.setattr(main_mod, "dimensionner_pieces_completes", lambda **kwargs: {})

    monkeypatch.setattr(
        main_mod,
        "analyser_composants_complementaires",
        lambda **kwargs: {
            "alternateur": {
                "pieces": {
                    "rotor": {"piece": "rotor", "inconnues": {"impossibles": [], "partielles": []}},
                }
            },
            "boite_crabots_chaine": {
                "pieces": {
                    "crabot": {"piece": "crabot", "inconnues": {"impossibles": [], "partielles": []}},
                }
            },
        },
    )

    config = main_mod.dimensionner_systeme_shsem(
        puissance_traction_kw=40.0,
        charger_batterie=False,
    )

    assert "alternateur.rotor" in config["inventaire"]["pieces"]
    assert config["inventaire"]["pieces"]["alternateur.rotor"]["source_composant"] == "alternateur"
    assert "boite_crabots_chaine.crabot" in config["rapports_pieces"]
    assert config["rapports_pieces"]["boite_crabots_chaine.crabot"]["piece"] == "crabot"


def test_dimensionner_systeme_shsem_rejects_non_positive_power(main_mod):
    with pytest.raises(ValueError, match="puissance_traction_kw doit être > 0"):
        main_mod.dimensionner_systeme_shsem(0)


def test_main_exposes_strict_power_optimizer(main_mod):
    report = main_mod.optimiser_systeme_depuis_puissance(
        100,
        "kw",
        espace_recherche={"rpm_sortie": [1000.0], "tension_dc_v": [800.0]},
    )

    assert report["meta"]["mode"] == "optimisation_puissance_sortie_stricte"
    assert report["selection"]["couple_sortie_max"]["valeur"] == pytest.approx(954.9296586)
    assert report["selection"]["courant_dc_min"]["valeur"] == pytest.approx(125.0)


def test_generer_rapport_puissance_json_bdd_exports_and_saves(tmp_path, main_mod):
    from backend.modules.systeme.database import SecureDatabase

    db_path = tmp_path / "shse.db"
    key_path = tmp_path / "secret.key"
    out_dir = tmp_path / "rapports"

    result = main_mod.generer_rapport_puissance_json_bdd(
        100,
        "kw",
        report_name="test_100kw",
        output_dir=out_dir,
        db_path=db_path,
        key_path=key_path,
        espace_recherche={
            "rpm_sortie": [1000.0, 2000.0],
            "tension_dc_v": [400.0, 800.0],
        },
    )

    assert result["report_name"] == "test_100kw"
    assert result["records_saved"] > 0

    json_path = out_dir / "test_100kw.json"
    assert result["json_path"] == str(json_path.resolve())
    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["meta"]["orchestrateur"] == "backend.main.generer_rapport_puissance_json_bdd"
    assert exported["selection"]["couple_sortie_max"]["valeur"] == pytest.approx(954.9296586)
    assert exported["selection"]["courant_dc_min"]["valeur"] == pytest.approx(125.0)

    db = SecureDatabase(db_path=str(db_path), key_path=str(key_path))
    saved = db.load_power_report("test_100kw")
    assert saved["selection"]["courant_dc_min"]["valeur"] == pytest.approx(125.0)
    assert db.load_power_section("test_100kw", "selection")["couple_sortie_max"]["valeur"] == pytest.approx(954.9296586)


def test_generer_rapport_puissance_only_records_unknowns_without_invention(tmp_path, main_mod):
    json_path = tmp_path / "moteur_200ch.json"

    result = main_mod.generer_rapport_puissance_json_bdd(
        200,
        "ch",
        output_path=json_path,
        sauvegarder_bdd=False,
    )

    report = result["rapport"]
    assert result["db_path"] is None
    assert report["analyse_base"]["calculs"]["puissance_sortie"]["kw"] == pytest.approx(147.09975)
    assert report["selection"] == {}

    unknown_names = {item["nom"] for item in report["inconnues"]["impossibles"] + report["inconnues"]["partielles"]}
    assert "espace_recherche" in unknown_names
    assert "rpm_sortie" in unknown_names
    assert "tension_dc_v" in unknown_names

    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["selection"] == {}


def test_generer_rapport_puissance_can_embed_piece_orchestration(monkeypatch, tmp_path, main_mod):
    def fake_enrich(report):
        enriched = dict(report)
        enriched["orchestration_pieces"] = {"active": True}
        enriched["inventaire"] = {"pieces": {"cylindre": {"type": "Cylindre", "construit": True}}}
        enriched["pieces"] = {"cylindre": {"nom": "cylindre"}}
        enriched["rapports_pieces"] = {"cylindre": {"piece": "cylindre"}}
        enriched["construction_pieces"] = {"construction": {"cylindre": {"construit": True}}}
        return enriched

    monkeypatch.setattr(main_mod, "enrichir_rapport_puissance_avec_pieces_systeme", fake_enrich)

    json_path = tmp_path / "rapport.json"
    result = main_mod.generer_rapport_puissance_json_bdd(
        100,
        "kw",
        output_path=json_path,
        sauvegarder_bdd=False,
        espace_recherche={"rpm_sortie": [1000.0], "tension_dc_v": [800.0]},
    )

    assert result["rapport"]["orchestration_pieces"]["active"] is True
    assert "cylindre" in result["rapport"]["pieces"]
    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["inventaire"]["pieces"]["cylindre"]["construit"] is True


def test_analyser_composants_complementaires_exposes_power_electronics_block(main_mod):
    rapports = main_mod.analyser_composants_complementaires(
        composants={},
        rapport_systeme={
            "liaisons": {
                "bus_dc": {
                    "P_bus_dc_design_w": 48000.0,
                    "V_bus_dc_v": 400.0,
                    "scenario_bus_dc": "traction_plus_charge",
                    "energie_a_recharger_kwh": 24.0,
                }
            },
            "synthese": {
                "vehicule": {"puissance_bus_dc_design_w": 48000.0},
                "batterie": {"tension_nominale_v": 400.0},
            },
        },
        definition_moteur={},
    )

    bloc = rapports["electronique_puissance"]
    assert bloc["bus_dc"]["puissance_design_w"] == 48000.0
    assert bloc["bus_dc"]["tension_nominale_v"] == 400.0
    assert bloc["bus_dc"]["courant_nominal_a"] == pytest.approx(120.0)
    assert bloc["redressement"]["puissance_sortie_dc_w"] == 48000.0


def test_analyser_composants_complementaires_supports_multifuel_worst_case(main_mod):
    class FakeMoteur:
        def analyser_bilan_carburant(self, **kwargs):
            fuel = kwargs["carburant"]
            power = float(kwargs["puissance_utile_w"])
            mdot = power / float(fuel.pci_j_kg)
            qdot = mdot / float(fuel.densite_kg_m3) if fuel.densite_kg_m3 else None
            return {
                "entrees": {"carburant": fuel.nom},
                "bilan": {
                    "debit_massique_carburant_kg_s": mdot,
                    "debit_volumique_carburant_m3_s": qdot,
                    "puissance_chimique_w": power,
                },
                "inconnues": {"impossibles": [], "partielles": []},
                "notes_modele": [],
            }

    rapports = main_mod.analyser_composants_complementaires(
        composants={"moteur_thermique": FakeMoteur()},
        rapport_systeme={
            "synthese": {
                "moteur_thermique": {"puissance_requise_W": 100000.0},
            },
        },
        definition_moteur={
            "carburant": None,
            "mode_carburant": "multi_carburant",
            "carburants_autorises": ["diesel", "essence", "ethanol", "hydrogene"],
        },
    )

    bloc = rapports["moteur_thermique_bilan_carburant"]
    assert bloc["mode"] == "multi_carburant_optimise_sur_pire_cas"
    assert bloc["carburant_dimensionnant"] == "hydrogene"
    assert bloc["carburant_optimal"] == "diesel"
    assert "comparatif" in bloc
    assert bloc["bilan_dimensionnant"]["entrees"]["carburant"] == "hydrogene"


def test_print_resume_console_outputs_key_lines(main_mod, capsys):
    config = {
        "resume_gui": {
            "Architecture": "ligne",
            "N_cyl": 2,
            "Bore_mm": 80.0,
            "Stroke_mm": 60.0,
            "RPM": 3000.0,
            "PME": 800000.0,
            "vd_tot_cc": 603.2,
            "P_bus_dc_design_w": 47000.0,
            "energie_batterie_kwh": 24.0,
        },
        "optimisation": {
            "synthese_optimisation": {
                "score_coherence_100": 91.0,
                "score_global_100": 88.5,
            }
        },
    }

    main_mod._print_resume_console(config)
    out = capsys.readouterr().out

    assert "=== DIMENSIONNEMENT SYSTÈME SHSE-M ===" in out
    assert "Architecture   : ligne" in out
    assert "N cylindres    : 2" in out
    assert "Alésage        : 80.0 mm" in out
    assert "Course         : 60.0 mm" in out
    assert "Régime         : 3000.0 rpm" in out
    assert "PME            : 800000.0 Pa" in out
    assert "Cylindrée      : 603.2 cc" in out
    assert "Bus DC design  : 47000.0 W" in out
    assert "Batterie utile : 24.0 kWh" in out
    assert "Score cohérence: 91.0" in out
    assert "Score global   : 88.5" in out

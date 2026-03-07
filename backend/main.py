# backend/main.py
from __future__ import annotations

import sys
import os
import math
from typing import Any, Dict, Optional, Sequence

# Ajout du chemin racine pour les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ============================================================
# Imports robustes
# ============================================================

# Orchestrateurs modernes
try:
    from backend.ensemble.systeme_complet import SystemeComplet
except Exception:
    from backend.ensemble.systeme_complet import SystemeComplet  # type: ignore

try:
    from backend.ensemble.optimisation import OptimisationSysteme
except Exception:
    from backend.ensemble.optimisation import OptimisationSysteme  # type: ignore

# Composants système
try:
    from backend.components.moteur_electrique import MoteurElectrique
    from backend.components.batterie import Batterie
    from backend.components.alternateur import Alternateur
    from backend.components.moteur_thermique import MoteurThermique
    from backend.components.boite_crabots import BoiteCrabots
    from backend.components.architecture import Architecture
except Exception:
    from backend.components.moteur_electrique import MoteurElectrique  # type: ignore
    from backend.components.batterie import Batterie  # type: ignore
    from backend.components.alternateur import Alternateur  # type: ignore
    from backend.components.moteur_thermique import MoteurThermique  # type: ignore
    from backend.components.boite_crabots import BoiteCrabots  # type: ignore
    from backend.components.architecture import Architecture  # type: ignore

# Pièces
try:
    from backend.pieces.cylindre import Cylindre
    from backend.pieces.piston import Piston
    from backend.pieces.joint_piston import JointPiston
    from backend.pieces.bielle import CorpsBielle
    from backend.pieces.arbre_piston import ArbrePiston
    from backend.pieces.coussinet_arbre_piston import CoussinetArbrePiston
    from backend.pieces.arbre_vilbrequin import ArbreVilbrequin
    from backend.pieces.vilbrequin import Vilbrequin
    from backend.pieces.roulement_aiguille_arbre import RoulementAiguilleArbre
    from backend.pieces.roulement_aiguille_arbre_vilebrequin import RoulementAiguilleArbreVilebrequin
    from backend.pieces.couvercle_cylindre import CouvercleCylindre
    from backend.pieces.vis_couvercle_cylindre import VisCouvercleCylindre
    from backend.pieces.deplaceur import Deplaceur
    from backend.pieces.joint_deplaceur import JointDeplaceur
except Exception:
    # si certains modules sont absents dans l’environnement courant,
    # on laisse à None pour conserver l’orchestrateur exécutable
    Cylindre = None  # type: ignore
    Piston = None  # type: ignore
    JointPiston = None  # type: ignore
    CorpsBielle = None  # type: ignore
    ArbrePiston = None  # type: ignore
    CoussinetArbrePiston = None  # type: ignore
    ArbreVilbrequin = None  # type: ignore
    Vilbrequin = None  # type: ignore
    RoulementAiguilleArbre = None  # type: ignore
    RoulementAiguilleArbreVilebrequin = None  # type: ignore
    CouvercleCylindre = None  # type: ignore
    VisCouvercleCylindre = None  # type: ignore
    Deplaceur = None  # type: ignore
    JointDeplaceur = None  # type: ignore
    ClavetteArbre = None  # type: ignore

# Héritage ancien pipeline, gardé en enrichissement facultatif
try:
    from backend.definition_pieces import dimensionner_pieces_completes
except Exception:
    dimensionner_pieces_completes = None  # type: ignore

try:
    from backend.system_generator import DriveChainGenerator
except Exception:
    DriveChainGenerator = None  # type: ignore


# ============================================================
# Helpers
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_dict(d: Any) -> Dict[str, Any]:
    return d if isinstance(d, dict) else {}


def _first_finite(*vals: Any) -> Optional[float]:
    for v in vals:
        if _is_finite(v):
            return float(v)
    return None


def _get_nested(d: Dict[str, Any], *path: str) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


# ============================================================
# Construction des composants
# ============================================================

def construire_moteur_electrique(
    *,
    tension_bus_v: float = 400.0,
    rendement_moteur: float = 0.92,
    pertes_fixes_w: float = 150.0,
    puissance_max_w: float = 120_000.0,
    regime_max_rpm: float = 10_000.0,
    couple_max_nm: float = 300.0,
) -> MoteurElectrique:
    return MoteurElectrique(
        puissance_max_w=puissance_max_w,
        regime_max_rpm=regime_max_rpm,
        couple_max_nm=couple_max_nm,
        tension_bus_v=tension_bus_v,
        rendement_moteur=rendement_moteur,
        pertes_fixes_w=pertes_fixes_w,
    )


def construire_batterie(
    *,
    tension_nominale_v: float = 400.0,
    rendement_charge: float = 0.94,
    tension_charge_v: float = 420.0,
) -> Batterie:
    return Batterie(
        tension_nominale_v=tension_nominale_v,
        rendement_charge=rendement_charge,
        tension_charge_v=tension_charge_v,
    )


def construire_alternateur() -> Alternateur:
    return Alternateur(
        connexion="etoile",
        nombre_poles=12,
    )


def construire_moteur_thermique_base(
    *,
    temps_moteur: int = 4,
    nombre_cylindres: int = 1,
    alesage_m: Optional[float] = None,
    course_m: Optional[float] = None,
    rendement_mecanique_nominal: float = 0.85,
) -> MoteurThermique:
    kwargs: Dict[str, Any] = {
        "temps_moteur": temps_moteur,
        "nombre_cylindres": nombre_cylindres,
        "rendement_mecanique_nominal": rendement_mecanique_nominal,
    }
    if alesage_m is not None:
        kwargs["alesage_m"] = alesage_m
    if course_m is not None:
        kwargs["course_m"] = course_m
    return MoteurThermique(**kwargs)


def construire_boite_crabots() -> BoiteCrabots:
    return BoiteCrabots()


def construire_architecture(
    *,
    temps_moteur: int = 4,
    rendement_mecanique: float = 0.85,
    ratio_course_alesage_max: float = 1.20,
) -> Architecture:
    return Architecture(
        temps_moteur=temps_moteur,
        rendement_mecanique=rendement_mecanique,
        ratio_course_alesage_max=ratio_course_alesage_max,
    )


# ============================================================
# Construction des pièces mécaniques à partir du système
# ============================================================

def construire_pieces_depuis_systeme(
    *,
    rapport_systeme: Dict[str, Any],
    materiau_metal_cle: str = "acier_42crmo4_qt",
    materiau_piston_cle: str = "alu_6061_t6",
    materiau_joint_cle: str = "ptfe",
    materiau_coussinet_cle: str = "bronze_cusn12",
) -> Dict[str, Any]:
    synth = _safe_dict(rapport_systeme.get("synthese"))
    mt = _safe_dict(synth.get("moteur_thermique"))
    cao = _safe_dict(rapport_systeme.get("cao"))
    cao_mt = _safe_dict(cao.get("moteur_thermique"))
    liaisons = _safe_dict(rapport_systeme.get("liaisons"))
    ex_mth = _safe_dict(liaisons.get("moteur_thermique_exigences"))

    alesage_m = _first_finite(mt.get("alesage_m"), (_safe_float(cao_mt.get("alesage_mm")) or 0.0) / 1000.0)
    course_m = _first_finite(mt.get("course_m"), (_safe_float(cao_mt.get("course_mm")) or 0.0) / 1000.0)
    nb_cyl = int(mt.get("nombre_cylindres", 1) or 1)
    rpm = _first_finite(mt.get("rpm_nominal"), ex_mth.get("rpm_moteur_thermique"))
    pme_pa = _safe_float(mt.get("pme_pa"))
    pression_max_pa = _first_finite(
        _get_nested(rapport_systeme, "entrees", "moteur_thermique_criteres", "pression_max_pa"),
        pme_pa * 2.0 if _is_finite(pme_pa) else None,
    )
    epaisseur_cylindre_m = _safe_float(mt.get("epaisseur_cylindre_retenue_m"))

    pieces: Dict[str, Any] = {}

    # Cylindre
    if Cylindre is not None and alesage_m is not None and course_m is not None:
        kwargs_cyl: Dict[str, Any] = {
            "alesage_m": alesage_m,
            "course_m": course_m,
            "pression_max_pa": pression_max_pa,
            "materiau_cle": materiau_metal_cle,
        }
        if epaisseur_cylindre_m is not None:
            kwargs_cyl["epaisseur_imposee_m"] = epaisseur_cylindre_m
        pieces["cylindre"] = Cylindre(**kwargs_cyl)

    # Piston
    if Piston is not None and pieces.get("cylindre") is not None:
        pieces["piston"] = Piston(
            cylindre=pieces["cylindre"],
            materiau_cle=materiau_piston_cle,
            pression_max_pa=pression_max_pa,
            rpm=rpm,
        )

    # Joint piston
    if JointPiston is not None and pieces.get("piston") is not None:
        pieces["joint_piston"] = JointPiston(
            piston=pieces["piston"],
            cylindre=pieces.get("cylindre"),
            materiau_cle=materiau_joint_cle,
        )

    # Arbre piston
    if ArbrePiston is not None and pieces.get("piston") is not None:
        pieces["arbre_piston"] = ArbrePiston(
            piston=pieces["piston"],
            cylindre=pieces.get("cylindre"),
            materiau_cle=materiau_metal_cle,
            rpm=rpm,
        )

    # Bielle
    if CorpsBielle is not None:
        pieces["bielle"] = CorpsBielle(
            piston=pieces.get("piston"),
            arbre_piston=pieces.get("arbre_piston"),
            cylindre=pieces.get("cylindre"),
            moteur_thermique=None,
            longueur_bielle_m=3.0 * course_m if course_m is not None else None,
            materiau_cle=materiau_metal_cle,
        )

    # Coussinet arbre-piston
    if CoussinetArbrePiston is not None:
        pieces["coussinet_arbre_piston"] = CoussinetArbrePiston(
            arbre_piston=pieces.get("arbre_piston"),
            materiau_cle=materiau_coussinet_cle,
            rpm=rpm,
        )

    # Arbre vilebrequin
    if ArbreVilbrequin is not None:
        pieces["arbre_vilebrequin"] = ArbreVilbrequin(
            cylindre=pieces.get("cylindre"),
            piston=pieces.get("piston"),
            bielle=pieces.get("bielle"),
            moteur_thermique=None,
            materiau_cle=materiau_metal_cle,
            rpm=rpm,
        )

    # Vilbrequin global
    if Vilbrequin is not None:
        pieces["vilbrequin"] = Vilbrequin(
            arbre=pieces.get("arbre_vilebrequin"),
            cylindre=pieces.get("cylindre"),
            piston=pieces.get("piston"),
            bielle=pieces.get("bielle"),
            nb_manetons=nb_cyl,
            nb_journaux_principaux=max(2, nb_cyl + 1),
            course_m=course_m,
            rpm=rpm,
            couple_max_Nm=_safe_float(mt.get("couple_requis_Nm")),
            materiau_cle=materiau_metal_cle,
        )

    # Roulements
    if RoulementAiguilleArbre is not None:
        pieces["roulement_aiguille_arbre"] = RoulementAiguilleArbre(
            vilbrequin=pieces.get("vilbrequin"),
            arbre_vilbrequin=pieces.get("arbre_vilebrequin"),
            bielle=pieces.get("bielle"),
            piston=pieces.get("piston"),
            cylindre=pieces.get("cylindre"),
            rpm=rpm,
            duree_vie_cible_h=5000.0,
            exposant_vie_p=10.0 / 3.0,
            materiau_cle=materiau_metal_cle if "materiau_cle" in getattr(RoulementAiguilleArbre, "__dataclass_fields__", {}) else None,
        )

    if RoulementAiguilleArbreVilbrequin is not None:
        pieces["roulement_aiguille_arbre_vilebrequin"] = RoulementAiguilleArbreVilbrequin(
            bielle=pieces.get("bielle"),
            arbre_vilebrequin=pieces.get("arbre_vilebrequin"),
            vilbrequin=pieces.get("vilbrequin"),
            rpm=rpm,
            duree_vie_cible_h=5000.0,
            exposant_vie_p=10.0 / 3.0,
        )

    # Couvercle + vis
    if CouvercleCylindre is not None and pieces.get("cylindre") is not None:
        pieces["couvercle_cylindre"] = CouvercleCylindre(
            cylindre=pieces["cylindre"],
            materiau_cle=materiau_metal_cle,
            pression_max_pa=pression_max_pa,
        )

    if VisCouvercleCylindre is not None and pieces.get("couvercle_cylindre") is not None:
        pieces["vis_couvercle_cylindre"] = VisCouvercleCylindre(
            cylindre=pieces.get("cylindre"),
            couvercle=pieces.get("couvercle_cylindre"),
            classe_vis="10.9",
        )

    # Déplaceur + joint déplaceur
    if Deplaceur is not None and pieces.get("cylindre") is not None:
        pieces["deplaceur"] = Deplaceur(
            cylindre=pieces["cylindre"],
            materiau_cle=materiau_metal_cle,
        )

    if JointDeplaceur is not None and pieces.get("deplaceur") is not None:
        pieces["joint_deplaceur"] = JointDeplaceur(
            deplaceur=pieces["deplaceur"],
            cylindre=pieces.get("cylindre"),
            materiau_cle=materiau_joint_cle,
        )

    # Clavette
    if ClavetteArbre is not None and pieces.get("arbre_vilebrequin") is not None:
        try:
            pieces["clavette_arbre"] = ClavetteArbre(
                arbre=pieces["arbre_vilebrequin"],
                materiau_cle=materiau_metal_cle,
            )
        except Exception:
            pieces["clavette_arbre"] = None

    return pieces


# ============================================================
# Orchestration principale
# ============================================================

def dimensionner_systeme_shsem(
    puissance_traction_kw: float,
    *,
    charger_batterie: bool = True,
    distance_km: Optional[float] = None,
    vitesse_moyenne_kmh: Optional[float] = None,
    temps_charge_cible_h: float = 1.0,
    vitesse_moteur_thermique_rpm: float = 3000.0,
    rapport_vitesse_alt_sur_moteur: float = 2.0,
    pme_pa: float = 8.0e5,
    vitesse_piston_max_ms: float = 10.0,
    longueur_dispo_m: float = 1.2,
    largeur_dispo_m: float = 0.8,
    pression_max_pa: float = 3.0e6,
    contrainte_admissible_pa: float = 1.2e8,
    densite_materiau_kg_m3: float = 7800.0,
    cout_matiere_eur_kg: float = 2.0,
    rendement_mecanique_cible_min: float = 0.80,
    masse_estimee_max_kg: Optional[float] = None,
    cout_matiere_max_eur: Optional[float] = None,
    indice_maintenance_max: Optional[float] = None,
    duree_vie_cible_h: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Orchestrateur backend complet.
    Il :
    1. construit les composants système,
    2. calcule le système complet,
    3. instancie les pièces mécaniques,
    4. optimise/cohère les interfaces,
    5. renvoie un paquet complet exploitable par GUI / API / CAO.
    """
    p_trac_kw = _req_pos("puissance_traction_kw", puissance_traction_kw)

    # --------------------------------------------------------
    # 1) Construction composants
    # --------------------------------------------------------
    moteur_electrique = construire_moteur_electrique()
    batterie = construire_batterie()
    alternateur = construire_alternateur()
    moteur_thermique = construire_moteur_thermique_base()
    boite_crabots = construire_boite_crabots()
    architecture = construire_architecture()

    systeme = SystemeComplet(
        moteur_electrique=moteur_electrique,
        batterie=batterie,
        alternateur=alternateur,
        moteur_thermique=moteur_thermique,
        boite_crabots=boite_crabots,
        architecture=architecture,
    )

    # --------------------------------------------------------
    # 2) Définition du scénario de charge
    # --------------------------------------------------------
    puissance_charge_kw = 20.0 if charger_batterie else 0.0
    puissance_auxiliaire_w = 5000.0

    rapports_boite_candidates: Sequence[float] = (1.0, 1.5, 2.0, 2.5, 3.0)

    rapport_systeme = systeme.analyser(
        puissance_moyenne_kw=p_trac_kw,
        puissance_pic_kw=p_trac_kw,
        distance_km=distance_km,
        vitesse_moyenne_kmh=vitesse_moyenne_kmh,
        temps_charge_cible_h=temps_charge_cible_h,
        energie_utile_imposee_kwh=None,
        calculer_puissance_charge_requise=charger_batterie,
        scenario_bus_dc="traction_plus_charge" if charger_batterie else "traction",
        vitesse_moteur_thermique_rpm=vitesse_moteur_thermique_rpm,
        rapport_vitesse_alt_sur_moteur=rapport_vitesse_alt_sur_moteur,
        rapports_boite_candidates=rapports_boite_candidates,
        pme_pa=pme_pa,
        vitesse_piston_max_ms=vitesse_piston_max_ms,
        longueur_dispo_m=longueur_dispo_m,
        largeur_dispo_m=largeur_dispo_m,
        pression_max_pa=pression_max_pa,
        contrainte_admissible_pa=contrainte_admissible_pa,
        densite_materiau_kg_m3=densite_materiau_kg_m3,
        cout_matiere_eur_kg=cout_matiere_eur_kg,
        rendement_mecanique_cible_min=rendement_mecanique_cible_min,
        masse_estimee_max_kg=masse_estimee_max_kg,
        cout_matiere_max_eur=cout_matiere_max_eur,
        indice_maintenance_max=indice_maintenance_max,
        duree_vie_cible_h=duree_vie_cible_h,
        puissance_auxiliaire_w=puissance_auxiliaire_w,
        puissance_elec_alt_cible_w=(puissance_charge_kw * 1000.0) if charger_batterie else None,
    )

    # --------------------------------------------------------
    # 3) Construction des pièces à partir du système
    # --------------------------------------------------------
    pieces = construire_pieces_depuis_systeme(rapport_systeme=rapport_systeme)

    # --------------------------------------------------------
    # 4) Optimisation inter-pièces
    # --------------------------------------------------------
    optimiseur = OptimisationSysteme(
        systeme_complet=systeme,
        cylindre=pieces.get("cylindre"),
        piston=pieces.get("piston"),
        joint_piston=pieces.get("joint_piston"),
        deplaceur=pieces.get("deplaceur"),
        joint_deplaceur=pieces.get("joint_deplaceur"),
        bielle=pieces.get("bielle"),
        arbre_piston=pieces.get("arbre_piston"),
        coussinet_arbre_piston=pieces.get("coussinet_arbre_piston"),
        arbre_vilebrequin=pieces.get("arbre_vilebrequin"),
        vilbrequin=pieces.get("vilbrequin"),
        roulement_aiguille_arbre=pieces.get("roulement_aiguille_arbre"),
        roulement_aiguille_arbre_vilebrequin=pieces.get("roulement_aiguille_arbre_vilebrequin"),
        couvercle_cylindre=pieces.get("couvercle_cylindre"),
        vis_couvercle_cylindre=pieces.get("vis_couvercle_cylindre"),
        clavette_arbre=pieces.get("clavette_arbre"),
    )

    rapport_optimisation = optimiseur.analyser()

    # --------------------------------------------------------
    # 5) Héritage ancien pipeline (facultatif)
    # --------------------------------------------------------
    legacy: Dict[str, Any] = {}

    if callable(dimensionner_pieces_completes):
        try:
            mt = _safe_dict(_safe_dict(rapport_systeme.get("synthese")).get("moteur_thermique"))
            legacy["dimensionner_pieces_completes"] = dimensionner_pieces_completes(
                puissance_cible_w=mt.get("puissance_requise_W"),
                regime_tr_min=mt.get("rpm_nominal"),
                n_cyl=mt.get("nombre_cylindres"),
                pression_max_pa=pression_max_pa,
            )
        except Exception as e:
            legacy["dimensionner_pieces_completes_erreur"] = str(e)

    if DriveChainGenerator is not None:
        try:
            gen = DriveChainGenerator()
            gen.compute(p_trac_kw)
            legacy["drivechain"] = getattr(gen, "results", None)
        except Exception as e:
            legacy["drivechain_erreur"] = str(e)

    # --------------------------------------------------------
    # 6) Format GUI / API
    # --------------------------------------------------------
    synth = _safe_dict(rapport_systeme.get("synthese"))
    mt = _safe_dict(synth.get("moteur_thermique"))
    veh = _safe_dict(synth.get("vehicule"))
    batt = _safe_dict(synth.get("batterie"))

    architecture_nom = mt.get("architecture")
    nb_cyl = mt.get("nombre_cylindres")
    bore_mm = (_safe_float(mt.get("alesage_m")) or 0.0) * 1000.0 if _is_finite(mt.get("alesage_m")) else None
    stroke_mm = (_safe_float(mt.get("course_m")) or 0.0) * 1000.0 if _is_finite(mt.get("course_m")) else None
    vd_cc = (_safe_float(mt.get("cylindree_totale_cc")))

    config = {
        "meta": {
            "backend": "main.py",
            "orchestrateur": "SystemeComplet + OptimisationSysteme",
        },
        "resume_gui": {
            "N_cyl": nb_cyl,
            "Architecture": architecture_nom,
            "Bore_mm": bore_mm,
            "Stroke_mm": stroke_mm,
            "RPM": mt.get("rpm_nominal"),
            "PME": mt.get("pme_pa"),
            "vd_tot_cc": vd_cc,
            "P_bus_dc_design_w": veh.get("puissance_bus_dc_design_w"),
            "energie_batterie_kwh": batt.get("energie_utile_kwh"),
            "score_coherence_100": _get_nested(rapport_optimisation, "synthese_optimisation", "score_coherence_100"),
            "score_global_100": _get_nested(rapport_optimisation, "synthese_optimisation", "score_global_100"),
        },
        "systeme_complet": rapport_systeme,
        "pieces": pieces,
        "optimisation": rapport_optimisation,
        "legacy": legacy,
    }

    return config


# ============================================================
# CLI
# ============================================================

def _print_resume_console(config: Dict[str, Any]) -> None:
    gui = _safe_dict(config.get("resume_gui"))
    opt = _safe_dict(config.get("optimisation"))
    opt_syn = _safe_dict(opt.get("synthese_optimisation"))

    print("=== DIMENSIONNEMENT SYSTÈME SHSE-M ===")
    print(f"Architecture   : {gui.get('Architecture')}")
    print(f"N cylindres    : {gui.get('N_cyl')}")
    print(f"Alésage        : {gui.get('Bore_mm')} mm")
    print(f"Course         : {gui.get('Stroke_mm')} mm")
    print(f"Régime         : {gui.get('RPM')} rpm")
    print(f"PME            : {gui.get('PME')} Pa")
    print(f"Cylindrée      : {gui.get('vd_tot_cc')} cc")
    print(f"Bus DC design  : {gui.get('P_bus_dc_design_w')} W")
    print(f"Batterie utile : {gui.get('energie_batterie_kwh')} kWh")
    print(f"Score cohérence: {opt_syn.get('score_coherence_100')}")
    print(f"Score global   : {opt_syn.get('score_global_100')}")


if __name__ == "__main__":
    puissance_kw = 40.0
    if len(sys.argv) > 1:
        try:
            puissance_kw = float(sys.argv[1])
        except ValueError:
            pass

    rep = dimensionner_systeme_shsem(
        puissance_traction_kw=puissance_kw,
        charger_batterie=True,
        temps_charge_cible_h=1.0,
        vitesse_moteur_thermique_rpm=3000.0,
        rapport_vitesse_alt_sur_moteur=2.0,
        pme_pa=8.0e5,
        vitesse_piston_max_ms=10.0,
        longueur_dispo_m=1.2,
        largeur_dispo_m=0.8,
        pression_max_pa=3.0e6,
        contrainte_admissible_pa=1.2e8,
        densite_materiau_kg_m3=7800.0,
        cout_matiere_eur_kg=2.0,
        rendement_mecanique_cible_min=0.80,
    )
    _print_resume_console(rep)
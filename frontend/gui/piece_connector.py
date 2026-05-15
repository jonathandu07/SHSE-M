"""
frontend/gui/piece_connector.py
Connecteur universel : mappe un nom de pièce vers l'instance Python réelle
du backend, en injectant les paramètres moteur courants.
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

# Import des classes backend (imports différés dans les fonctions pour éviter les cycles)

def _f(d: Dict, key: str) -> Optional[float]:
    """Strictly retrieves a float or None. No default invention."""
    val = d.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

# ---------------------------------------------------------------------------
# Instanciateurs par pièce
# ---------------------------------------------------------------------------

def _make_cylindre(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre
    return Cylindre(
        alesage_m=_f(ep, "alesage_m"),
        course_m=_f(ep, "course_m"),
        longueur_utile_m=_f(ep, "longueur_utile_m") or (_f(ep, "course_m") * 1.5 if _f(ep, "course_m") else None),
        pression_service_pa=_f(ep, "pression_service_pa"),
        pression_max_pa=_f(ep, "pression_max_pa"),
        materiau_cle=ep.get("materiau_cylindre_cle", "acier_42crmo4_qt")
    )

def _make_piston(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.piston import Piston
    cylindre = _make_cylindre(ep)
    return Piston(
        cylindre=cylindre,
        alesage_nominal_m=_f(ep, "alesage_m"),
        course_m=_f(ep, "course_m"),
        materiau_piston_cle=ep.get("materiau_piston_cle", "alu_6061_t6")
    )

def _make_bielle(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.bielle import CorpsBielle
    piston = _make_piston(ep)
    return CorpsBielle(
        piston=piston,
        longueur_bielle_m=_f(ep, "longueur_bielle_m") or (_f(ep, "course_m") * 2.0 if _f(ep, "course_m") else None),
        materiau_cle=ep.get("materiau_bielle_cle", "acier_42crmo4_qt")
    )

def _make_arbre_vilebrequin(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilbrequin
    return ArbreVilbrequin(
        course_m=_f(ep, "course_m"),
        materiau_cle=ep.get("materiau_vilebrequin_cle", "acier_42crmo4_qt")
    )

def _make_arbre_piston(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.arbre_piston import ArbrePiston
    return ArbrePiston(
        diametre_fut_central_m=_f(ep, "diametre_axe_piston_m"),
        longueur_totale_m=_f(ep, "longueur_axe_piston_m"),
        materiau_cle=ep.get("materiau_axe_piston_cle", "acier_42crmo4_qt")
    )

def _make_coussinet(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.coussinet_arbre_piston import CoussinetArbrePiston
    return CoussinetArbrePiston(
        diametre_portee_m=_f(ep, "diametre_coussinet_m"),
        longueur_coussinet_m=_f(ep, "longueur_coussinet_m"),
        materiau_coussinet=ep.get("materiau_coussinet_cle", "bronze_cusn12")
    )

def _make_couvercle(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.couvercle_cylindre import CouvercleCylindre
    return CouvercleCylindre(
        diametre_ouverture_m=_f(ep, "diametre_ouverture_culasse_m"),
        rayon_externe_m=_f(ep, "rayon_externe_culasse_m"),
        epaisseur_m=_f(ep, "epaisseur_culasse_m"),
        materiau_cle=ep.get("materiau_culasse_cle", "fonte_en_gjl_250")
    )

def _make_joint_piston(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.joint_piston import JointPiston
    return JointPiston(
        diametre_interieur_cylindre_m=_f(ep, "alesage_m"),
        materiau_joint_cle=ep.get("materiau_joint_piston_cle", "ptfe")
    )

def _make_alternateur(ep: Dict[str, Any]) -> Any:
    from backend.components.alternateur.alternateur import Alternateur
    return Alternateur()

def _make_batterie(ep: Dict[str, Any]) -> Any:
    from backend.components.batterie.batterie import Batterie
    return Batterie(
        tension_nominale_v=_f(ep, "tension_nominale_v")
    )

def _make_architecture(ep: Dict[str, Any]) -> Any:
    from backend.components.architechture.architecture import Architecture
    return Architecture()

def _make_arbre(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.arbre import ArbreMoteur
    return ArbreMoteur(
        couple_max_Nm=_f(ep, "couple_max_Nm") or _f(ep, "couple_max_nm"),
        rpm=_f(ep, "rpm_nominal") or _f(ep, "rpm_moteur"),
        nombre_cylindres=_f(ep, "nombre_cylindres") or _f(ep, "n_cyl"),
        entraxe_cylindres_m=_f(ep, "entraxe_cylindres_m"),
        diametre_externe_cylindre_m=_f(ep, "diametre_externe_cylindre_m"),
        diametre_arbre_m=_f(ep, "diametre_arbre_m"),
    )

def _make_moteur_electrique(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_electrique.moteur_electrique import MoteurElectrique
    return MoteurElectrique(
        puissance_max_w=_f(ep, "puissance_max_w") or _f(ep, "puissance_moteur_w"),
        regime_max_rpm=_f(ep, "regime_max_rpm"),
        couple_max_nm=_f(ep, "couple_max_nm"),
        rendement_moteur=_f(ep, "rendement_moteur"),
        tension_bus_v=_f(ep, "tension_nominale_v"),
    )

def _make_boite_crabots(ep: Dict[str, Any]) -> Any:
    from backend.components.boite_crabots.boite_crabots import BoiteCrabots
    return BoiteCrabots()

def _make_moteur_thermique(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.moteur_thermique import MoteurThermique
    return MoteurThermique(
        nombre_cylindres=_f(ep, "nombre_cylindres") or _f(ep, "n_cyl"),
        alesage_m=_f(ep, "alesage_m"),
        course_m=_f(ep, "course_m"),
        rpm_nominal=_f(ep, "rpm_nominal") or _f(ep, "rpm_moteur"),
        pme_nominale_pa=_f(ep, "pme_pa"),
    )

def _make_deplaceur(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.deplaceur import Deplaceur
    cylindre = _make_cylindre(ep)
    return Deplaceur(
        cylindre=cylindre,
        diametre_exterieur_m=_f(ep, "alesage_m") * 0.98 if _f(ep, "alesage_m") else None,
        longueur_totale_m=_f(ep, "longueur_deplaceur_m"),
        materiau_cle=ep.get("materiau_deplaceur_cle", "acier_310s")
    )

def _make_joint_deplaceur(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.joint_deplaceur import JointDeplaceur
    return JointDeplaceur(
        alesage_cylindre_m=_f(ep, "alesage_m"),
        materiau_joint_cle=ep.get("materiau_joint_deplaceur_cle", "graphite")
    )

# ---------------------------------------------------------------------------
# Registre
# ---------------------------------------------------------------------------

_CONNECTORS = {
    "piston": _make_piston,
    "cylindre": _make_cylindre,
    "bielle": _make_bielle,
    "corps_bielle": _make_bielle,
    "arbre_vilbrequin": _make_arbre_vilebrequin,
    "arbre_vilebrequin": _make_arbre_vilebrequin,
    "arbre": _make_arbre,
    "arbremoteur": _make_arbre,
    "arbre_piston": _make_arbre_piston,
    "coussinet": _make_coussinet,
    "coussinet_arbre_piston": _make_coussinet,
    "couvercle": _make_couvercle,
    "couvercle_cylindre": _make_couvercle,
    "joint_piston": _make_joint_piston,
    "alternateur": _make_alternateur,
    "batterie": _make_batterie,
    "architecture": _make_architecture,
    "moteur_electrique": _make_moteur_electrique,
    "boite_crabots": _make_boite_crabots,
    "moteur_thermique": _make_moteur_thermique,
    "deplaceur": _make_deplaceur,
    "joint_deplaceur": _make_joint_deplaceur,
}


def _first_mapping(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _apply_attrs(target: Any, attrs: Dict[str, Any]) -> None:
    for key, value in attrs.items():
        if key.startswith("_"):
            continue
        current = getattr(target, key, None)
        if isinstance(value, dict) and current is not None and hasattr(current, "__dict__"):
            _apply_attrs(current, value)
            continue
        if callable(current):
            continue
        try:
            setattr(target, key, value)
        except Exception:
            pass

def hydrate_piece(piece_obj: Any, db_data: Dict[str, Any]) -> Any:
    """
    Force l'injection des données calculées en backend dans une instance de pièce.
    Priorité aux attributs sérialisés puis aux données du rapport.
    """
    if not piece_obj or not isinstance(db_data, dict):
        return piece_obj

    # 1. Extraction des attributs sérialisés (haute fidélité)
    inventaire = _first_mapping(db_data.get("inventaire"))
    attrs = _first_mapping(
        db_data.get("objet_serialise"),
        db_data.get("objet"),
        inventaire.get("objet"),
        db_data.get("attributs"),
    )
    if not attrs:
        attrs = db_data

    # 2. Injection forcée
    _apply_attrs(piece_obj, attrs)

    # 3. Mock de la méthode analyser() si un rapport est présent
    # Cela permet aux visualisations d'utiliser le rapport calculé par le backend
    # au lieu de relancer des calculs potentiellement différents.
    rapport = _first_mapping(
        db_data.get("rapport"),
        inventaire.get("rapport"),
    )
    if rapport and hasattr(piece_obj, "analyser"):
        def mocked_analyser(*args, **kwargs):
            return rapport
        try:
            piece_obj.analyser = mocked_analyser
        except Exception:
            pass
    if rapport and hasattr(piece_obj, "calculer"):
        def mocked_calculer(*args, **kwargs):
            return rapport
        try:
            piece_obj.calculer = mocked_calculer
        except Exception:
            pass

    return piece_obj


def _build_generic_piece(piece_name: str, engine_params: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    class GenericPiece:
        pass

    piece = GenericPiece()
    piece.nom = piece_name
    for key, value in (engine_params or {}).items():
        try:
            setattr(piece, key, value)
        except Exception:
            pass
    if db_data:
        piece = hydrate_piece(piece, db_data)
    return piece


def get_piece_instance(piece_name: str, engine_params: Dict, db_data: Optional[Dict] = None) -> Optional[Any]:
    """
    Instancie la classe Python réelle d'une pièce avec les paramètres moteur,
    et l'hydrate avec les données de la base si fournies.
    """
    key = piece_name.lower().replace(" ", "_")
    
    # Correction typos communes
    if key == "vilebrequin": key = "arbre_vilebrequin"
    if key == "vilbrequin": key = "arbre_vilebrequin"
    if key == "arbre_vilbrequin": key = "arbre_vilebrequin"

    factory = _CONNECTORS.get(key)
    if factory is None:
        return _build_generic_piece(piece_name, engine_params, db_data=db_data) if db_data else None
    try:
        p = factory(engine_params)
        if db_data:
            p = hydrate_piece(p, db_data)
        return p
    except Exception:
        print(f"[piece_connector] Échec instanciation '{piece_name}':\n{traceback.format_exc()}")
        return None

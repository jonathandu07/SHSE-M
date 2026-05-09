"""
frontend/gui/piece_connector.py
Connecteur universel : mappe un nom de pièce vers l'instance Python réelle
du backend, en injectant les paramètres moteur courants.
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

# Import des classes backend (imports différés dans les fonctions pour éviter les cycles)

def _f(d: Dict, key: str, default: float = 0.0) -> float:
    try:
        return float(d.get(key, default))
    except (TypeError, ValueError):
        return default

# ---------------------------------------------------------------------------
# Instanciateurs par pièce
# ---------------------------------------------------------------------------

def _make_cylindre(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre
    return Cylindre(
        alesage_m=_f(ep, "alesage_m", 0.130),
        course_m=_f(ep, "course_m", 0.150),
        longueur_utile_m=_f(ep, "course_m", 0.150) * 1.5,
        pression_service_pa=10e6,
        pression_max_pa=15e6,
        materiau_cle="acier_42crmo4_qt"
    )

def _make_piston(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.piston import Piston
    cylindre = _make_cylindre(ep)
    return Piston(
        cylindre=cylindre,
        alesage_nominal_m=_f(ep, "alesage_m", 0.130),
        course_m=_f(ep, "course_m", 0.150),
        materiau_piston_cle="alu_6061_t6"
    )

def _make_bielle(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.bielle import CorpsBielle
    piston = _make_piston(ep)
    return CorpsBielle(
        piston=piston,
        longueur_bielle_m=_f(ep, "course_m", 0.150) * 2.0,
        materiau_cle="acier_42crmo4_qt"
    )

def _make_arbre_vilebrequin(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilbrequin
    return ArbreVilbrequin(
        course_m=_f(ep, "course_m", 0.150),
        materiau_cle="acier_42crmo4_qt"
    )

def _make_arbre_piston(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.arbre_piston import Arbre
    return Arbre(
        diametre_arbre_m=0.030,
        longueur_arbre_m=0.100,
        materiau_cle="acier_42crmo4_qt"
    )

def _make_coussinet(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.coussinet_arbre_piston import Coussinet
    return Coussinet(
        diametre_interieur_m=0.030,
        longueur_m=0.040,
        materiau_cle="bronze_cusn12"
    )

def _make_couvercle(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.couvercle_cylindre import Couvercle
    return Couvercle(
        diametre_exterieur_m=0.200,
        epaisseur_m=0.020,
        materiau_cle="fonte_en_gjl_250"
    )

def _make_joint_piston(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.joint_piston import JointPiston
    return JointPiston(
        diametre_nominal_m=_f(ep, "alesage_m", 0.130),
        materiau_cle="ptfe"
    )

def _make_alternateur(ep: Dict[str, Any]) -> Any:
    from backend.components.alternateur.alternateur import Alternateur
    return Alternateur()

def _make_batterie(ep: Dict[str, Any]) -> Any:
    from backend.components.batterie.batterie import Batterie
    return Batterie(
        tension_nominale_v=_f(ep, "tension_nominale_v", 400.0)
    )

def _make_architecture(ep: Dict[str, Any]) -> Any:
    from backend.components.architechture.architecture import Architecture
    return Architecture(
        architecture_forcee="V",
        nombre_cylindres=8
    )

def _make_deplaceur(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.deplaceur import Deplaceur
    cylindre = _make_cylindre(ep)
    return Deplaceur(
        cylindre=cylindre,
        diametre_deplaceur_m=_f(ep, "alesage_m", 0.130) * 0.98,
        longueur_deplaceur_m=0.150,
        materiau_cle="acier_310s"
    )

def _make_joint_deplaceur(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.joint_deplaceur import JointDeplaceur
    return JointDeplaceur(
        diametre_nominal_m=_f(ep, "alesage_m", 0.130),
        materiau_cle="graphite"
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
    "arbre_piston": _make_arbre_piston,
    "coussinet": _make_coussinet,
    "couvercle": _make_couvercle,
    "joint_piston": _make_joint_piston,
    "alternateur": _make_alternateur,
    "batterie": _make_batterie,
    "architecture": _make_architecture,
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
        piece_obj.analyser = mocked_analyser
    if rapport and hasattr(piece_obj, "calculer"):
        def mocked_calculer(*args, **kwargs):
            return rapport
        piece_obj.calculer = mocked_calculer

    return piece_obj


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
        return None
    try:
        p = factory(engine_params)
        if db_data:
            p = hydrate_piece(p, db_data)
        return p
    except Exception:
        print(f"[piece_connector] Échec instanciation '{piece_name}':\n{traceback.format_exc()}")
        return None

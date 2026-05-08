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
        materiau_cle="acier_allie_trempe"
    )

def _make_piston(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.piston import Piston
    cylindre = _make_cylindre(ep)
    return Piston(
        cylindre=cylindre,
        alesage_nominal_m=_f(ep, "alesage_m", 0.130),
        course_m=_f(ep, "course_m", 0.150),
        materiau_piston_cle="alliage_aluminium_silicium"
    )

def _make_bielle(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.bielle import CorpsBielle
    piston = _make_piston(ep)
    return CorpsBielle(
        piston=piston,
        longueur_bielle_m=_f(ep, "course_m", 0.150) * 2.0,
        materiau_cle="acier_forge"
    )

def _make_arbre_vilebrequin(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilbrequin
    return ArbreVilbrequin(
        course_m=_f(ep, "course_m", 0.150),
        materiau_cle="acier_allie_trempe"
    )

def _make_arbre_piston(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.arbre_piston import Arbre
    return Arbre(
        diametre_arbre_m=0.030,
        longueur_arbre_m=0.100,
        materiau_cle="acier_allie_trempe"
    )

def _make_coussinet(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.coussinet_arbre_piston import Coussinet
    return Coussinet(
        diametre_interieur_m=0.030,
        longueur_m=0.040,
        materiau_cle="bronze_pb"
    )

def _make_couvercle(ep: Dict[str, Any]) -> Any:
    from backend.components.moteur_thermique.pieces.couvercle_cylindre import Couvercle
    return Couvercle(
        diametre_exterieur_m=0.200,
        epaisseur_m=0.020,
        materiau_cle="fonte_gs"
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
}

def get_piece_instance(piece_name: str, engine_params: Dict) -> Optional[Any]:
    """
    Instancie la classe Python réelle d'une pièce avec les paramètres moteur.
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
        return factory(engine_params)
    except Exception:
        print(f"[piece_connector] Échec instanciation '{piece_name}':\n{traceback.format_exc()}")
        return None

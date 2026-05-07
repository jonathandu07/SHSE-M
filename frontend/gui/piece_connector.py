"""
frontend/gui/piece_connector.py
Connecteur universel : mappe un nom de pièce vers l'instance Python réelle
du backend, en injectant les paramètres moteur courants.
"""
from __future__ import annotations

import inspect
import traceback
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _s(d: Dict, *keys, default=None):
    """Recherche récursive dans un dict."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur


def _f(d: Dict, *keys, default: float = 0.0) -> float:
    v = _s(d, *keys, default=None)
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _build_engine_params(db_data: Dict, user_params: Dict) -> Dict:
    """Fusionne les données BDD avec les surcharges utilisateur."""
    params = {}
    if isinstance(db_data, dict):
        params.update(db_data)
    if isinstance(user_params, dict):
        params.update(user_params)
    return params


# ---------------------------------------------------------------------------
# Instanciateurs par pièce
# ---------------------------------------------------------------------------

def _make_piston(ep: Dict) -> Any:
    """Instancie un Piston avec les paramètres moteur courants."""
    from backend.components.moteur_thermique.pieces.piston import Piston
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre

    alesage = _f(ep, "alesage_m", default=0.13)
    course = _f(ep, "course_m", default=0.15)
    rpm = _f(ep, "rpm_nominal", default=1500.0)
    p_max = _f(ep, "pression_max_pa", default=8.0e6)

    cylindre = Cylindre(
        alesage_nominal_m=alesage,
        course_m=course,
        rpm=rpm,
        pression_max_pa=p_max,
    )
    return Piston(
        cylindre=cylindre,
        alesage_nominal_m=alesage,
        course_m=course,
        rpm=rpm,
        pression_max_pa=p_max,
    )


def _make_cylindre(ep: Dict) -> Any:
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre
    return Cylindre(
        alesage_nominal_m=_f(ep, "alesage_m", default=0.13),
        course_m=_f(ep, "course_m", default=0.15),
        rpm=_f(ep, "rpm_nominal", default=1500.0),
        pression_max_pa=_f(ep, "pression_max_pa", default=8.0e6),
    )


def _make_bielle(ep: Dict) -> Any:
    from backend.components.moteur_thermique.pieces.bielle import CorpsBielle
    alesage = _f(ep, "alesage_m", default=0.13)
    course = _f(ep, "course_m", default=0.15)
    rayon_manivelle = course / 2.0
    # longueur bielle ≈ 1.7 × course (ratio classique moteur diesel)
    longueur = _f(ep, "longueur_bielle_m", default=rayon_manivelle * 3.4)
    p_max = _f(ep, "pression_max_pa", default=8.0e6)
    force_axiale = p_max * 3.14159 * (alesage / 2.0) ** 2

    sig = inspect.signature(CorpsBielle.__init__)
    kwargs: Dict = {}
    defaults_map = {
        "longueur_bielle_m": longueur,
        "rayon_manivelle_m": rayon_manivelle,
        "force_axiale_max_N": force_axiale,
        "alesage_m": alesage,
        "pression_max_pa": p_max,
    }
    for k, v in defaults_map.items():
        if k in sig.parameters:
            kwargs[k] = v
    return CorpsBielle(**kwargs)


def _make_couvercle_cylindre(ep: Dict) -> Any:
    from backend.components.moteur_thermique.pieces.couvercle_cylindre import CouvercleCylindre
    sig = inspect.signature(CouvercleCylindre.__init__)
    kwargs: Dict = {}
    defaults_map = {
        "alesage_nominal_m": _f(ep, "alesage_m", default=0.13),
        "pression_max_pa": _f(ep, "pression_max_pa", default=8.0e6),
        "rpm": _f(ep, "rpm_nominal", default=1500.0),
    }
    for k, v in defaults_map.items():
        if k in sig.parameters:
            kwargs[k] = v
    return CouvercleCylindre(**kwargs)


def _make_arbre_vilebrequin(ep: Dict) -> Any:
    from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilebrequin
    sig = inspect.signature(ArbreVilebrequin.__init__)
    alesage = _f(ep, "alesage_m", default=0.13)
    course = _f(ep, "course_m", default=0.15)
    p_max = _f(ep, "pression_max_pa", default=8.0e6)
    force = p_max * 3.14159 * (alesage / 2.0) ** 2
    kwargs: Dict = {}
    defaults_map = {
        "rayon_manivelle_m": course / 2.0,
        "force_bielle_n": force,
        "rpm": _f(ep, "rpm_nominal", default=1500.0),
        "nombre_cylindres": int(_f(ep, "nombre_cylindres", default=6.0)),
        "alesage_m": alesage,
    }
    for k, v in defaults_map.items():
        if k in sig.parameters:
            kwargs[k] = v
    return ArbreVilebrequin(**kwargs)


# ---------------------------------------------------------------------------
# Registre
# ---------------------------------------------------------------------------

_CONNECTORS = {
    "piston": _make_piston,
    "cylindre": _make_cylindre,
    "bielle": _make_bielle,
    "corps_bielle": _make_bielle,
    "couvercle_cylindre": _make_couvercle_cylindre,
    "arbre_vilbrequin": _make_arbre_vilebrequin,
    "arbre_vilebrequin": _make_arbre_vilebrequin,
}


def get_piece_instance(piece_name: str, engine_params: Dict) -> Optional[Any]:
    """
    Instancie la classe Python réelle d'une pièce avec les paramètres moteur.
    Retourne None si la pièce n'est pas dans le registre ou si l'instanciation échoue.
    """
    key = piece_name.lower().replace(" ", "_")
    factory = _CONNECTORS.get(key)
    if factory is None:
        return None
    try:
        return factory(engine_params)
    except Exception:
        print(f"[piece_connector] Échec instanciation '{piece_name}':\n{traceback.format_exc()}")
        return None

from __future__ import annotations

"""Alias centralises pour les chemins critiques du systeme STHO-ME."""

from typing import Any, Mapping


ALIASES_CHAMPS: dict[str, list[str]] = {
    "puissance_traction_w": [
        "puissance_traction_w",
        "puissance_moteur_requise_W",
        "entrees.puissance_traction_w",
        "synthese.vehicule.puissance_traction_w",
        "liaisons.puissance_traction_w",
    ],
    "puissance_bus_dc_w": [
        "puissance_bus_dc_w",
        "production_electrique_sortie_w",
        "synthese.systeme.P_bus_dc_design_w",
        "liaisons.puissance_bus_dc_w",
    ],
    "tension_bus_dc_v": [
        "tension_bus_dc_v",
        "V_bus_dc_v",
        "synthese.systeme.V_bus_dc_v",
        "liaisons.tension_bus_dc_v",
    ],
    "rpm_moteur": [
        "rpm_moteur",
        "rpm_moteur_nominal",
        "vitesse_moteur_thermique_rpm",
        "synthese.moteur_thermique.rpm_nominal",
        "liaisons.rpm_moteur_thermique",
    ],
    "omega_moteur_rad_s": [
        "omega_moteur_rad_s",
        "omega_moteur",
        "synthese.moteur_thermique.omega_rad_s",
    ],
    "couple_moteur_nm": [
        "couple_moteur_nm",
        "couple_moteur_max_Nm",
        "couple_moteur_thermique_Nm",
        "synthese.moteur_thermique.couple_requis_Nm",
    ],
    "couple_alternateur_nm": [
        "couple_alternateur_nm",
        "alternateur.couple_alternateur_nm",
        "synthese.alternateur.couple_nm",
        "liaisons.couple_alternateur_nm",
    ],
    "pme_pa": [
        "pme_pa",
        "PME_Pa",
        "pression_moyenne_effective_pa",
        "synthese.moteur_thermique.pme_pa",
    ],
    "pression_max_pa": [
        "pression_max_pa",
        "pmax_pa",
        "synthese.moteur_thermique.pression_max_pa",
    ],
    "alesage_m": [
        "alesage_m",
        "bore_m",
        "synthese.moteur_thermique.alesage_m",
        "cao.moteur_thermique.alesage_m",
    ],
    "course_m": [
        "course_m",
        "stroke_m",
        "synthese.moteur_thermique.course_m",
        "cao.moteur_thermique.course_m",
    ],
    "nombre_cylindres": [
        "nombre_cylindres",
        "nb_cylindres",
        "n_cyl",
        "synthese.moteur_thermique.nombre_cylindres",
    ],
    "architecture": [
        "architecture",
        "architecture_moteur",
        "synthese.moteur_thermique.architecture",
    ],
    "materiau": [
        "materiau",
        "materiau_principal",
        "materiaux.materiau",
    ],
    "carburant": [
        "carburant",
        "carburant_impose",
        "strategie_energie.carburant",
    ],
    "energie_batterie_kwh": [
        "energie_batterie_kwh",
        "energie_utile_imposee_kwh",
        "synthese.batterie.energie_utile_kwh",
    ],
    "ns_batterie": [
        "ns_batterie",
        "nombre_cellules_serie",
        "batterie.Ns",
    ],
    "np_batterie": [
        "np_batterie",
        "nombre_cellules_parallele",
        "batterie.Np",
    ],
    "rapport_alternateur_moteur": [
        "rapport_alternateur_moteur",
        "rapport_vitesse_alt_sur_moteur",
        "rapport_boite_alt",
        "boite_crabots.rapports",
        "composants.boite_crabots.rapports",
    ],
    "solidworks_ready": [
        "solidworks_ready",
        "cao.solidworks_ready",
        "cao.solidworks_ready_detaille",
        "cao.available",
        "synthese.cao.solidworks_ready",
    ],
}

_REVERSE: dict[str, str] = {}
for canonical, paths in ALIASES_CHAMPS.items():
    _REVERSE[_normalize_token(canonical)] = canonical
    for path in paths:
        _REVERSE[_normalize_token(path.split(".")[-1])] = canonical
        _REVERSE[_normalize_token(path)] = canonical


def get_alias_paths(field_name: str) -> list[str]:
    canonical = canonical_field_name(field_name)
    return list(ALIASES_CHAMPS.get(canonical, [field_name]))


def canonical_field_name(field_name: Any) -> str:
    raw = str(field_name or "").strip()
    if not raw:
        return ""
    normalized = _normalize_token(raw)
    if normalized in _REVERSE:
        return _REVERSE[normalized]
    for alias, canonical in _REVERSE.items():
        if alias and alias in normalized:
            return canonical
    return raw.split(".")[-1]


def get_first_available_value(
    field_name: str,
    *roots: Mapping[str, Any],
    default: Any = None,
) -> tuple[Any, str | None]:
    for path in get_alias_paths(field_name):
        for root in roots:
            value = get_path(root, path)
            if value is not None:
                return value, path
    return default, None


def get_path(data: Mapping[str, Any], path: str) -> Any:
    if path in data:
        return data[path]
    cur: Any = data
    for part in str(path).split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _normalize_token(value: Any) -> str:
    raw = str(value or "").lower()
    out = []
    for char in raw:
        if char.isalnum():
            out.append(char)
        else:
            out.append("_")
    return "_".join(part for part in "".join(out).split("_") if part)

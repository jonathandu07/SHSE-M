from __future__ import annotations

"""Validation de chaine de puissance STHO-ME.

Le validateur ne dimensionne rien. Il lit un rapport deja produit par le
backend, verifie que les grandeurs necessaires a une chaine de puissance sont
presentes et controle quelques relations de coherence simples.
"""

import math
from typing import Any, Mapping

from backend.modules.systeme.aliases import get_alias_paths


def valider_chaine_puissance_sthome(
    rapport: dict,
    *,
    puissance_sortie_w: float,
    strict: bool = True,
) -> dict:
    """Valide la chaine 100 kW sortie moteur electrique sans inventer de valeur."""

    data = rapport if isinstance(rapport, dict) else {}
    expected = _num(puissance_sortie_w)
    checks: list[dict[str, Any]] = []

    p_out, p_out_path = _first_number(
        data,
        "puissance_sortie_moteur_electrique_w",
        "resolution_inconnues.payload_resolu.puissance_sortie_moteur_electrique_w",
        "resolution_inconnues.payload_resolu.synthese.moteur_electrique.puissance_sortie_w",
        "synthese.moteur_electrique.puissance_sortie_w",
    )
    _add_check(
        checks,
        "sortie_moteur_electrique_connue",
        p_out is not None and (expected is None or p_out >= expected * 0.999),
        "blocking",
        "Puissance de sortie moteur electrique absente ou inferieure a la demande.",
        [p_out_path],
        value=p_out,
    )

    p_bus, p_bus_path = _first_number(
        data,
        "puissance_bus_dc_w",
        "resolution_inconnues.payload_resolu.puissance_bus_dc_w",
        "resolution_inconnues.payload_resolu.P_bus_dc_design_w",
        "resolution_inconnues.payload_resolu.synthese.bus_dc.puissance_design_w",
        "synthese.systeme.P_bus_dc_design_w",
        "synthese.bus_dc.puissance_design_w",
        "synthese.systeme_complet.vehicule.puissance_bus_dc_design_w",
    )
    _add_check(
        checks,
        "bus_dc_connu",
        p_bus is not None,
        "blocking",
        "Puissance bus DC design absente.",
        [p_bus_path],
        value=p_bus,
    )
    _add_check(
        checks,
        "bus_dc_superieur_sortie",
        p_out is not None and p_bus is not None and p_bus >= p_out,
        "blocking",
        "La puissance bus DC doit couvrir la sortie moteur electrique et les rendements amont.",
        [p_out_path, p_bus_path],
        value={"puissance_sortie_w": p_out, "puissance_bus_dc_w": p_bus},
    )

    tension, tension_path = _first_number(
        data,
        "tension_bus_dc_v",
        "resolution_inconnues.payload_resolu.tension_bus_dc_v",
        "resolution_inconnues.payload_resolu.V_bus_dc_v",
        "synthese.systeme.V_bus_dc_v",
        "synthese.systeme_complet.vehicule.tension_bus_dc_v",
    )
    courant, courant_path = _first_number(
        data,
        "courant_bus_dc_a",
        "resolution_inconnues.payload_resolu.courant_bus_dc_a",
        "synthese.systeme.courant_bus_dc_a",
    )
    current_ok = p_bus is not None and tension is not None and tension > 0.0 and courant is not None
    if p_bus is not None and tension is not None and tension > 0.0 and courant is None:
        courant = p_bus / tension
        courant_path = "calcul_validation_depuis_backend.P_bus/U_bus"
        current_ok = True
    _add_check(
        checks,
        "courant_bus_calculable_si_tension_connue",
        current_ok,
        "warning",
        "Courant bus DC non exploitable faute de tension ou de courant backend.",
        [p_bus_path, tension_path, courant_path],
        value=courant,
    )

    _add_presence_check(
        checks,
        data,
        "batterie_presente",
        [
            "sous_systemes.batterie",
            "synthese.batterie",
            "synthese.systeme_complet.batterie",
            "resolution_inconnues.payload_resolu.batterie",
            "resolution_inconnues.payload_resolu.synthese.batterie",
        ],
        "Batterie absente du rapport exploitable.",
    )
    _add_presence_check(
        checks,
        data,
        "alternateur_present",
        [
            "sous_systemes.alternateur",
            "synthese.alternateur",
            "synthese.systeme_complet.alternateur",
            "resolution_inconnues.payload_resolu.synthese.alternateur",
        ],
        "Alternateur absent du rapport exploitable.",
    )
    _add_presence_check(
        checks,
        data,
        "moteur_thermique_present",
        [
            "sous_systemes.moteur_thermique",
            "synthese.moteur_thermique",
            "synthese.systeme_complet.moteur_thermique",
            "resolution_inconnues.payload_resolu.synthese.moteur_thermique",
        ],
        "Moteur thermique absent du rapport exploitable.",
    )

    rpm_mt, rpm_mt_path = _first_number(
        data,
        "rpm_moteur",
        "resolution_inconnues.payload_resolu.rpm_moteur",
        "resolution_inconnues.payload_resolu.rpm_moteur_nominal",
        "synthese.moteur_thermique.rpm_nominal",
        "synthese.systeme_complet.moteur_thermique.rpm_nominal",
    )
    _add_check(
        checks,
        "rpm_moteur_connu_ou_candidat",
        rpm_mt is not None,
        "blocking",
        "Regime moteur thermique absent : impossible de fermer omega, couple et boite.",
        [rpm_mt_path],
        value=rpm_mt,
    )

    p_mt, p_mt_path = _first_number(
        data,
        "puissance_moteur_thermique_arbre_w",
        "resolution_inconnues.payload_resolu.puissance_moteur_thermique_arbre_w",
        "resolution_inconnues.payload_resolu.puissance_moteur_requise_W",
        "resolution_inconnues.payload_resolu.synthese.moteur_thermique.puissance_requise_W",
        "synthese.moteur_thermique.puissance_requise_W",
        "synthese.systeme_complet.moteur_thermique.puissance_requise_W",
    )
    torque_mt, torque_mt_path = _first_number(
        data,
        "couple_moteur_nm",
        "resolution_inconnues.payload_resolu.couple_moteur_nm",
        "resolution_inconnues.payload_resolu.synthese.moteur_thermique.couple_requis_Nm",
        "synthese.moteur_thermique.couple_requis_Nm",
        "synthese.systeme_complet.moteur_thermique.couple_requis_Nm",
    )
    if torque_mt is None and p_mt is not None and rpm_mt is not None and rpm_mt > 0.0:
        torque_mt = p_mt / (2.0 * math.pi * rpm_mt / 60.0)
        torque_mt_path = "calcul_validation_depuis_backend.P_mt/omega_mt"
    _add_check(
        checks,
        "couple_moteur_thermique_calculable",
        p_mt is not None and rpm_mt is not None and torque_mt is not None,
        "blocking",
        "Couple moteur thermique non calculable faute de puissance arbre ou rpm.",
        [p_mt_path, rpm_mt_path, torque_mt_path],
        value=torque_mt,
    )

    p_alt, p_alt_path = _first_number(
        data,
        "puissance_alternateur_electrique_w",
        "resolution_inconnues.payload_resolu.puissance_alternateur_electrique_w",
        "resolution_inconnues.payload_resolu.production_electrique_sortie_w",
        "resolution_inconnues.payload_resolu.synthese.alternateur.puissance_electrique_design_w",
        "synthese.alternateur.puissance_electrique_design_w",
    )
    duty, duty_path = _first_number(
        data,
        "criteres_conception.duty_cycle_moteur_thermique_max",
        "meta.meta_utilisateur.cahier_des_charges.duty_cycle_moteur_thermique_max",
        "resolution_inconnues.coherence_systeme.cdc.duty_cycle_moteur_thermique_max",
    )
    if duty is None:
        duty = 0.5 if not strict else None
        duty_path = "non_fourni" if strict else "pre_dimensionnement.cdc_default"
    required_alt = p_bus / duty if p_bus is not None and duty is not None and duty > 0.0 else None
    alt_ok = p_alt is not None and required_alt is not None and p_alt >= required_alt * 0.999
    _add_check(
        checks,
        "alternateur_coherent_duty_cycle",
        alt_ok,
        "blocking",
        "Puissance alternateur electrique incoherente avec le duty cycle thermique maximal.",
        [p_alt_path, p_bus_path, duty_path],
        value={"puissance_alternateur_w": p_alt, "minimum_attendu_w": required_alt},
    )

    ratio, ratio_path = _first_number(
        data,
        "rapport_alternateur_moteur",
        "resolution_inconnues.payload_resolu.rapport_vitesse_alt_sur_moteur",
        "resolution_inconnues.payload_resolu.rapport_boite_alt",
        "synthese.boite_crabots.rapport_vitesse_alt_sur_moteur",
        "liaisons.rapport_vitesse_alt_sur_moteur",
    )
    rpm_alt, rpm_alt_path = _first_number(
        data,
        "rpm_alternateur",
        "resolution_inconnues.payload_resolu.rpm_alternateur",
        "resolution_inconnues.payload_resolu.vitesse_alternateur_rpm",
        "synthese.alternateur.rpm_nominal",
    )
    reliable = ratio is not None or (rpm_mt is not None and rpm_alt is not None)
    _add_check(
        checks,
        "boite_reliable",
        reliable,
        "blocking",
        "Boite non reliable : rapport ou couple rpm moteur/alternateur absent.",
        [ratio_path, rpm_mt_path, rpm_alt_path],
        value={"rapport": ratio, "rpm_moteur": rpm_mt, "rpm_alternateur": rpm_alt},
    )

    optimisation = _get_path(data, "optimisation") or _get_path(data, "rapports.optimisation")
    _add_check(
        checks,
        "optimisation_presente",
        isinstance(optimisation, Mapping) and bool(optimisation),
        "warning",
        "Rapport optimisation absent.",
        ["optimisation", "rapports.optimisation"],
    )

    blocking_failed = [check for check in checks if not check["ok"] and check["severity"] == "blocking"]
    diagnostic = _get_path(data, "diagnostic") or _get_path(data, "frontend.diagnostic")
    _add_check(
        checks,
        "diagnostic_present_si_blocage",
        not blocking_failed or isinstance(diagnostic, Mapping),
        "warning",
        "La chaine est bloquee mais aucun diagnostic causal n'est attache au rapport.",
        ["diagnostic", "frontend.diagnostic"],
    )

    score = _score(checks)
    actions = _actions(checks)
    return {
        "ok": not blocking_failed,
        "score_chaine_100": score,
        "checks": checks,
        "points_bloquants": [check for check in checks if not check["ok"] and check["severity"] == "blocking"],
        "actions": actions,
        "valeurs": {
            "puissance_sortie_moteur_electrique_w": p_out,
            "puissance_bus_dc_design_w": p_bus,
            "courant_bus_dc_a": courant,
            "puissance_alternateur_electrique_w": p_alt,
            "puissance_moteur_thermique_arbre_w": p_mt,
            "rpm_moteur_thermique": rpm_mt,
            "couple_moteur_thermique_nm": torque_mt,
            "rapport_boite_alt": ratio,
        },
    }


def _add_presence_check(checks: list[dict[str, Any]], data: Mapping[str, Any], name: str, paths: list[str], reason: str) -> None:
    for path in paths:
        value = _get_path(data, path)
        if _present(value):
            _add_check(checks, name, True, "blocking", reason, [path], value=_summarize(value))
            return
    _add_check(checks, name, False, "blocking", reason, paths)


def _add_check(
    checks: list[dict[str, Any]],
    name: str,
    ok: bool,
    severity: str,
    reason: str,
    paths: list[Any],
    *,
    value: Any = None,
) -> None:
    checks.append(
        {
            "name": name,
            "ok": bool(ok),
            "severity": severity,
            "reason": None if ok else reason,
            "paths": [str(path) for path in paths if path],
            "value": _jsonable(value),
        }
    )


def _first_number(data: Mapping[str, Any], canonical: str, *extra_paths: str) -> tuple[float | None, str | None]:
    for path in [*extra_paths, *get_alias_paths(canonical)]:
        value = _get_path(data, path)
        if _is_number(value):
            return float(value), path
    return None, None


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    if not isinstance(data, Mapping) or not path:
        return None
    if path in data:
        return data[path]
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
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _summarize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {"keys": sorted(str(k) for k in value.keys())[:20]}
    if isinstance(value, (list, tuple, set)):
        return {"count": len(value)}
    return value


def _score(checks: list[dict[str, Any]]) -> float:
    weights = {"blocking": 2.0, "warning": 1.0, "info": 0.5}
    total = sum(weights.get(str(check.get("severity")), 1.0) for check in checks)
    if total <= 0:
        return 0.0
    ok = sum(weights.get(str(check.get("severity")), 1.0) for check in checks if check.get("ok"))
    return round(100.0 * ok / total, 2)


def _actions(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for check in checks:
        if check.get("ok"):
            continue
        out.append(
            {
                "check": check.get("name"),
                "severity": check.get("severity"),
                "action": check.get("reason"),
                "paths": check.get("paths", []),
            }
        )
    return out


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _num(value: Any) -> float | None:
    return float(value) if _is_number(value) else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


__all__ = ["valider_chaine_puissance_sthome"]

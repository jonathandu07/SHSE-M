from __future__ import annotations

"""Resolution d'inconnues systeme avec candidats, recalcul et validation."""

from dataclasses import asdict, dataclass, field, is_dataclass
import copy
import math
from typing import Any, Callable, Dict, List, Mapping

from backend.modules.systeme.status import (
    SOURCE_CDC,
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_COMPUTED,
    STATUS_DATABASE,
    STATUS_DERIVED,
    STATUS_INPUT,
    STATUS_REJECTED_BY_OPTIMIZATION,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    normalize_status,
)


@dataclass
class DonneeCandidate:
    nom: str
    path: str | None
    valeur: Any
    unite: str | None = None
    source: str = "unknown"
    statut: str = "candidate"
    raison: str = ""
    dependances: list[str] = field(default_factory=list)
    verifiee_par: list[str] = field(default_factory=list)
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionInconnuesResult:
    config_completee: dict[str, Any]
    candidates: list[DonneeCandidate]
    rapport_avant: dict[str, Any]
    rapport_apres: dict[str, Any] | None
    inconnues_restantes: dict[str, Any]
    accepte: bool
    raison_refus: str | None = None

    def en_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


def resoudre_inconnues_systeme(
    *,
    config: dict[str, Any],
    rapport: dict[str, Any],
    cahier_des_charges: dict[str, Any],
    repository: Any | None = None,
    project_id: str | None = None,
    recalculer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    optimiser: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    strict: bool = True,
    max_iterations: int = 5,
) -> ResolutionInconnuesResult:
    from backend.modules.systeme.generation_candidates import generer_candidates_pour_inconnue
    from backend.modules.systeme.validation_candidates import valider_candidate

    config_completee = copy.deepcopy(config or {})
    rapport_avant = copy.deepcopy(rapport or {})
    candidates: List[DonneeCandidate] = []
    accepted_any = False
    rejected: List[dict[str, Any]] = []
    rapport_courant = copy.deepcopy(rapport_avant)

    unknowns = _extract_unknowns(rapport_courant, cahier_des_charges)
    for iteration in range(max(1, max_iterations)):
        changed = False
        for unknown in unknowns:
            nom = str(unknown.get("nom") or unknown.get("champ") or unknown.get("path") or "")
            path = unknown.get("path") or unknown.get("champ") or nom
            if not nom and not path:
                continue
            if _has_value(config_completee, str(path)):
                candidates.append(_candidate(nom, str(path), _get_path(config_completee, str(path)), STATUS_INPUT, "Valeur deja presente dans config."))
                continue

            repo_value = None
            if repository is not None and project_id is not None:
                repo_value = repository.get_project_parameter(project_id, str(path))
                if repo_value is not None:
                    cand = _candidate(nom, str(path), repo_value, STATUS_DATABASE, "Valeur recuperee depuis repository/BDD.")
                    if _try_accept(cand, config_completee, rapport_courant, cahier_des_charges, recalculer, optimiser, strict, valider_candidate):
                        candidates.append(cand)
                        changed = accepted_any = True
                        continue
                    candidates.append(cand)

            report_value = _get_path(rapport_courant, str(path))
            if report_value is not None:
                cand = _candidate(nom, str(path), report_value, STATUS_DERIVED, "Valeur propagee depuis un rapport deja calcule.")
                if _try_accept(cand, config_completee, rapport_courant, cahier_des_charges, recalculer, optimiser, strict, valider_candidate):
                    candidates.append(cand)
                    changed = accepted_any = True
                    continue
                candidates.append(cand)

            exact = _derive_exact(str(path), config_completee, rapport_courant)
            if exact is not None:
                cand = _candidate(nom, str(path), exact["valeur"], exact["source"], exact["raison"], exact.get("dependances", []), exact.get("unite"))
                if _try_accept(cand, config_completee, rapport_courant, cahier_des_charges, recalculer, optimiser, strict, valider_candidate):
                    candidates.append(cand)
                    changed = accepted_any = True
                    continue
                candidates.append(cand)

            generated = generer_candidates_pour_inconnue(
                nom=nom,
                path=str(path),
                raison=str(unknown.get("raison") or ""),
                config=config_completee,
                rapport=rapport_courant,
                cahier_des_charges=cahier_des_charges,
            )
            best: DonneeCandidate | None = None
            best_report: dict[str, Any] | None = None
            for cand in generated:
                cand.statut = normalize_status(cand.statut or cand.source, default=STATUS_CANDIDATE_FROM_CDC)
                is_cdc_candidate = cand.source == SOURCE_CDC or cand.statut == STATUS_CANDIDATE_FROM_CDC
                if strict and is_cdc_candidate:
                    cand.metadata.setdefault("validation", {"ok": False, "raison": "mode strict: candidat CDC non injecte"})
                    candidates.append(cand)
                    continue
                if is_cdc_candidate and optimiser is None:
                    cand.metadata.setdefault("validation", {"ok": False, "raison": "optimisation absente: candidat CDC non valide"})
                    candidates.append(cand)
                    continue
                trial_config = copy.deepcopy(config_completee)
                _set_path(trial_config, cand.path or cand.nom, cand.valeur)
                trial_report = recalculer(trial_config) if recalculer is not None else rapport_courant
                opt_report = optimiser(trial_report) if optimiser is not None else None
                validation = valider_candidate(
                    candidate=cand,
                    rapport_avant=rapport_courant,
                    rapport_apres=trial_report,
                    cahier_des_charges=cahier_des_charges,
                    optimisation=opt_report,
                    strict=strict,
                )
                cand.score = validation.get("score")
                cand.verifiee_par.append("validation_candidates.valider_candidate")
                cand.metadata["validation"] = validation
                if validation.get("ok"):
                    if best is None or (cand.score or 0.0) > (best.score or 0.0):
                        best = cand
                        best_report = trial_report
                else:
                    cand.statut = STATUS_REJECTED_BY_OPTIMIZATION if is_cdc_candidate else "candidate_rejected"
                    rejected.append(_jsonable(cand))
                candidates.append(cand)
            if best is not None:
                best.statut = STATUS_VALIDATED_BY_OPTIMIZATION if (best.source == SOURCE_CDC or normalize_status(best.statut) == STATUS_CANDIDATE_FROM_CDC) else normalize_status(best.statut or best.source)
                _set_path(config_completee, best.path or best.nom, best.valeur)
                rapport_courant = best_report or rapport_courant
                changed = accepted_any = True
                if repository is not None and project_id is not None and hasattr(repository, "save_generated_candidate"):
                    repository.save_generated_candidate(project_id=project_id, candidate=best)

        if not changed:
            break
        unknowns = _extract_unknowns(rapport_courant, cahier_des_charges)

    restantes = _dedupe_unknowns(_extract_unknowns(rapport_courant, cahier_des_charges))
    if rejected:
        rapport_courant.setdefault("tracabilite", {}).setdefault("rejected_candidates", []).extend(rejected)

    return ResolutionInconnuesResult(
        config_completee=config_completee,
        candidates=candidates,
        rapport_avant=rapport_avant,
        rapport_apres=rapport_courant if accepted_any else None,
        inconnues_restantes=restantes,
        accepte=accepted_any,
        raison_refus=None if accepted_any else "Aucune candidate n'a ete acceptee.",
    )


def _try_accept(
    candidate: DonneeCandidate,
    config: dict[str, Any],
    rapport: dict[str, Any],
    cdc: dict[str, Any],
    recalculer: Callable[[dict[str, Any]], dict[str, Any]] | None,
    optimiser: Callable[[dict[str, Any]], dict[str, Any]] | None,
    strict: bool,
    validator: Callable[..., dict[str, Any]],
) -> bool:
    trial = copy.deepcopy(config)
    _set_path(trial, candidate.path or candidate.nom, candidate.valeur)
    rapport_apres = recalculer(trial) if recalculer is not None else rapport
    optimisation = optimiser(rapport_apres) if optimiser is not None else None
    validation = validator(
        candidate=candidate,
        rapport_avant=rapport,
        rapport_apres=rapport_apres,
        cahier_des_charges=cdc,
        optimisation=optimisation,
        strict=strict,
    )
    candidate.metadata["validation"] = validation
    candidate.score = validation.get("score")
    candidate.verifiee_par.append("validation_candidates.valider_candidate")
    if validation.get("ok"):
        if candidate.source == SOURCE_CDC or normalize_status(candidate.statut or candidate.source) == STATUS_CANDIDATE_FROM_CDC:
            if strict or optimiser is None:
                candidate.statut = STATUS_CANDIDATE_FROM_CDC
                candidate.metadata["validation"] = {
                    "ok": False,
                    "raison": "candidat CDC non valide sans optimisation ou hors mode strict",
                }
                return False
            candidate.statut = STATUS_VALIDATED_BY_OPTIMIZATION
        else:
            candidate.statut = normalize_status(candidate.source, default=str(candidate.source))
        config.clear()
        config.update(trial)
        return True
    candidate.statut = STATUS_REJECTED_BY_OPTIMIZATION if candidate.source == SOURCE_CDC else "candidate_rejected"
    return False


def _extract_unknowns(rapport: Mapping[str, Any], cdc: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: List[dict[str, Any]] = []
    inc = rapport.get("inconnues", {})
    if isinstance(inc, Mapping):
        for key in ("impossibles", "partielles", "bloquantes", "restantes_catalogue", "restantes_physiques"):
            values = inc.get(key) or []
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, Mapping):
                        data = dict(item)
                        data.setdefault("categorie", key)
                        out.append(data)
    for path in cdc.get("required_fields", []) if isinstance(cdc.get("required_fields"), list) else []:
        if _get_path(rapport, str(path)) is None:
            out.append({"nom": str(path).split(".")[-1], "path": str(path), "raison": "Champ requis par CDC absent.", "categorie": "required_fields"})
    return _dedupe_unknowns(out)


def _dedupe_unknowns(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = (item.get("path"), item.get("champ"), item.get("nom"), item.get("raison"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _candidate(nom: str, path: str, value: Any, source: str, reason: str, deps: list[str] | None = None, unit: str | None = None) -> DonneeCandidate:
    return DonneeCandidate(nom=nom, path=path, valeur=value, unite=unit, source=source, statut=normalize_status(source, default="candidate"), raison=reason, dependances=deps or [])


def _derive_exact(path: str, config: Mapping[str, Any], rapport: Mapping[str, Any]) -> dict[str, Any] | None:
    p = path.lower()
    if "omega" in p:
        rpm = _first_number(config, rapport, "rpm_moteur_nominal", "vitesse_moteur_thermique_rpm", "synthese.moteur_thermique.rpm_nominal")
        if rpm:
            return {"valeur": 2.0 * math.pi * rpm / 60.0, "source": STATUS_COMPUTED, "raison": "omega = 2*pi*rpm/60", "dependances": ["rpm"], "unite": "rad/s"}
    if "courant_bus" in p:
        power = _first_number(config, rapport, "puissance_bus_dc_w", "synthese.systeme.P_bus_dc_design_w")
        voltage = _first_number(config, rapport, "tension_bus_dc_v")
        if power is not None and voltage:
            return {"valeur": power / voltage, "source": STATUS_COMPUTED, "raison": "I = P/U", "dependances": ["puissance_bus_dc_w", "tension_bus_dc_v"], "unite": "A"}
    if "couple" in p:
        power = _first_number(config, rapport, "puissance_moteur_requise_W", "puissance_moteur_w")
        omega = _first_number(config, rapport, "omega_moteur_rad_s")
        if power is not None and omega:
            return {"valeur": power / omega, "source": STATUS_COMPUTED, "raison": "C = P/omega", "dependances": ["puissance_moteur_requise_W", "omega_moteur_rad_s"], "unite": "N.m"}
    return None


def _has_value(data: Mapping[str, Any], path: str) -> bool:
    value = _get_path(data, path)
    return value is not None


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    if path in data:
        return data[path]
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _set_path(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = [p for p in path.split(".") if p]
    cur = data
    for part in parts[:-1]:
        node = cur.get(part)
        if not isinstance(node, dict):
            node = {}
            cur[part] = node
        cur = node
    cur[parts[-1]] = value


def _first_number(config: Mapping[str, Any], rapport: Mapping[str, Any], *paths: str) -> float | None:
    for path in paths:
        for root in (config, rapport):
            value = _get_path(root, path)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value

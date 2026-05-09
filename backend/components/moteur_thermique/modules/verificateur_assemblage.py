from __future__ import annotations

"""
backend/components/moteur_thermique/modules/verificateur_assemblage.py
===============================================================================
Vérificateur / optimiseur d'assemblage des pièces du moteur thermique.
===============================================================================

Objectif :
- normaliser les rapports hétérogènes des pièces ;
- vérifier que les interfaces géométriques et mécaniques s'emboîtent ;
- isoler le point bloquant prioritaire ;
- relancer le dimensionnement uniquement sur ce point bloquant ;
- conserver les paramètres déjà validés ;
- ne pas inventer de cote catalogue : toute marge fonctionnelle est paramétrable.

Le module est volontairement autonome : il ne dépend pas des classes concrètes des
pièces. Il travaille sur les rapports générés par analyser()/calculer() ou sur des
objets pièce compatibles.
"""

import copy
import inspect
import json
import math
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple


# =============================================================================
# Types publics
# =============================================================================

GraviteAssemblage = str  # "erreur", "avertissement", "info"
StrategieCorrection = str  # "conserver_piece_amont" | "corriger_piece_amont"


class PieceLike(Protocol):
    def analyser(self, *, strict: bool = False) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class AssemblyTolerances:
    """
    Tolérances et jeux minimaux utilisés par les règles.

    Par défaut, les jeux minimaux valent 0 pour rester strictement non inventif.
    Si tu veux une vraie logique CAO/usinage, fournis explicitement tes jeux :
    piston/cylindre, axe/logement, maneton/bielle, etc.
    """

    # Tolérance relative pour considérer deux cotes comme équivalentes.
    rel_tol: float = 1e-4
    abs_tol_m: float = 1e-9

    # Jeux fonctionnels minimaux, en diamètre, sauf mention contraire.
    jeu_diametral_piston_cylindre_min_m: float = 0.0
    jeu_diametral_axe_logement_min_m: float = 0.0
    jeu_diametral_coussinet_arbre_min_m: float = 0.0
    jeu_diametral_bielle_maneton_min_m: float = 0.0
    jeu_radial_deplaceur_cylindre_min_m: float = 0.0

    # Marges de recouvrement / garde-fous géométriques.
    marge_couvercle_sur_cylindre_m: float = 0.0
    marge_bride_vis_m: float = 0.0

    # Squeeze joint optionnel. None = pas de jugement si la donnée existe.
    squeeze_joint_min: Optional[float] = None
    squeeze_joint_max: Optional[float] = None

    # Limite de fuite optionnelle. None = pas de jugement si la donnée existe.
    fuite_max_m3_s: Optional[float] = None


@dataclass
class AssemblyCorrection:
    """Correction ciblée sur une pièce et un champ d'entrée possible."""

    piece: str
    champ: str
    valeur: Any
    raison: str
    confiance: str = "prudente"  # prudente | forte | faible

    def en_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AssemblyIssue:
    piece_a: str
    piece_b: str
    regle: str
    message: str
    valeur_a: Any = None
    valeur_b: Any = None
    chemin_a: Optional[str] = None
    chemin_b: Optional[str] = None
    attendu: Optional[str] = None
    ecart: Optional[float] = None
    gravite: GraviteAssemblage = "erreur"
    bloquant: bool = True
    priorite: int = 100
    corrections: List[AssemblyCorrection] = field(default_factory=list)
    parametres_valides: Dict[str, Any] = field(default_factory=dict)
    donnees_manquantes: List[str] = field(default_factory=list)

    @property
    def parametre_correcteur(self) -> Dict[str, Any]:
        """
        Compatibilité avec ton ancien script.
        Renvoie une version plate, mais la nouvelle API garde les corrections
        pièce par pièce dans `corrections`.
        """
        return {c.champ: c.valeur for c in self.corrections}

    def en_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["parametre_correcteur"] = self.parametre_correcteur
        return out


@dataclass
class AssemblyIteration:
    iteration: int
    ok: bool
    nb_issues: int
    nb_bloquants: int
    point_bloquant: Optional[AssemblyIssue] = None
    corrections_appliquees: List[AssemblyCorrection] = field(default_factory=list)
    parametres_apres_correction: Dict[str, Any] = field(default_factory=dict)

    def en_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "ok": self.ok,
            "nb_issues": self.nb_issues,
            "nb_bloquants": self.nb_bloquants,
            "point_bloquant": self.point_bloquant.en_dict() if self.point_bloquant else None,
            "corrections_appliquees": [c.en_dict() for c in self.corrections_appliquees],
            "parametres_apres_correction": _to_jsonable(self.parametres_apres_correction),
        }


@dataclass
class AssemblyOptimizationResult:
    ok: bool
    rapports: Dict[str, Dict[str, Any]]
    parametres_finaux: Dict[str, Any]
    issues_finales: List[AssemblyIssue]
    historique: List[AssemblyIteration]
    raison_arret: str

    def en_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "rapports": _to_jsonable(self.rapports),
            "parametres_finaux": _to_jsonable(self.parametres_finaux),
            "issues_finales": [i.en_dict() for i in self.issues_finales],
            "historique": [h.en_dict() for h in self.historique],
            "raison_arret": self.raison_arret,
        }


# =============================================================================
# Helpers robustes
# =============================================================================

KNOWN_PIECES: Tuple[str, ...] = (
    "cylindre",
    "piston",
    "joint_piston",
    "arbre_piston",
    "bielle",
    "coussinet_arbre_piston",
    "couvercle_cylindre",
    "vis_couvercle_cylindre",
    "deplaceur",
    "joint_deplaceur",
    "arbre_vilebrequin",
    "vilbrequin",
    "roulement_aiguille_arbre",
    "roulement_aiguille_arbre_vilebrequin",
    "arbre",
    "clavette_arbre",
)

PIECE_BUILD_ORDER: Tuple[str, ...] = (
    "cylindre",
    "piston",
    "joint_piston",
    "arbre_piston",
    "bielle",
    "coussinet_arbre_piston",
    "couvercle_cylindre",
    "vis_couvercle_cylindre",
    "deplaceur",
    "joint_deplaceur",
    "arbre_vilebrequin",
    "vilbrequin",
    "roulement_aiguille_arbre",
    "roulement_aiguille_arbre_vilebrequin",
    "arbre",
    "clavette_arbre",
)


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    if _is_finite(x) and abs(float(x) - round(float(x))) < 1e-9:
        return int(round(float(x)))
    return None


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _dig(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


def _first_non_none(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _first_finite(*vals: Any) -> Optional[float]:
    for v in vals:
        if _is_finite(v):
            return float(v)
    return None


def _first_int(*vals: Any) -> Optional[int]:
    for v in vals:
        iv = _safe_int(v)
        if iv is not None:
            return iv
    return None


def _close_or_ordered(
    valeur_interne: Optional[float],
    valeur_externe: Optional[float],
    *,
    jeu_min: float,
    rel_tol: float,
    abs_tol: float,
) -> bool:
    """
    True si valeur_externe peut entrer dans valeur_interne avec jeu_min.
    Les noms sont volontairement génériques :
    - valeur_interne = alésage / logement / tête de bielle ;
    - valeur_externe = piston / axe / maneton.
    """
    if valeur_interne is None or valeur_externe is None:
        return True
    attendu_max = valeur_interne - jeu_min
    if valeur_externe <= attendu_max:
        return True
    return math.isclose(valeur_externe, attendu_max, rel_tol=rel_tol, abs_tol=abs_tol)


def _ecart(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return float(b) - float(a)


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if is_dataclass(value):
        try:
            return _to_jsonable(asdict(value))
        except Exception:
            pass
    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _to_jsonable(value.en_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            attrs = {k: v for k, v in vars(value).items() if not k.startswith("_") and not callable(v)}
            return {"type": type(value).__name__, "attributs": _to_jsonable(attrs)}
        except Exception:
            pass
    return {"type": type(value).__name__}


def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return dict(obj)
    for method_name in ("analyser", "calculer", "analyser_dimensionnement"):
        fn = getattr(obj, method_name, None)
        if not callable(fn):
            continue
        try:
            out = fn(strict=False)
            if isinstance(out, Mapping):
                return dict(out)
        except TypeError:
            try:
                out = fn()
                if isinstance(out, Mapping):
                    return dict(out)
            except Exception:
                continue
        except Exception:
            continue
    return None


def _nested_get_many(source: Mapping[str, Any], paths: Sequence[Sequence[str]]) -> Any:
    for path in paths:
        v = _dig(source, *path)
        if v is not None:
            return v
    return None


def _finite_from_paths(source: Mapping[str, Any], paths: Sequence[Sequence[str]]) -> Optional[float]:
    return _safe_float(_nested_get_many(source, paths))


def _int_from_paths(source: Mapping[str, Any], paths: Sequence[Sequence[str]]) -> Optional[int]:
    return _safe_int(_nested_get_many(source, paths))


def _has_piece(rapports: Mapping[str, Any], name: str) -> bool:
    return isinstance(rapports.get(name), Mapping) and bool(rapports.get(name))


def normaliser_rapports_pieces(source: Any) -> Dict[str, Dict[str, Any]]:
    """
    Accepte plusieurs formes :
    - {"cylindre": {...}, "piston": {...}}
    - {"pieces": {"cylindre": {...}}}
    - {"rapports": {"pieces": {...}}}
    - {"rapports": {"composants": {"moteur_thermique": {"pieces": {...}}}}}
    - objets pièce dans un dict.
    """
    out: Dict[str, Dict[str, Any]] = {}
    if source is None:
        return out

    if not isinstance(source, Mapping):
        rep = _try_call_report(source)
        if isinstance(rep, dict):
            source = rep
        else:
            return out

    src = dict(source)

    candidates: List[Any] = [src]
    for path in (
        ("pieces",),
        ("rapports", "pieces"),
        ("rapports", "pieces_moteur_thermique"),
        ("rapports", "composants", "moteur_thermique", "pieces"),
        ("sous_systemes", "moteur_thermique", "pieces"),
        ("moteur_thermique", "pieces"),
    ):
        block = _dig(src, *path)
        if isinstance(block, Mapping):
            candidates.append(block)

    # Cas composant.piece si les noms arrivent sous forme "moteur_thermique.piston".
    for block in list(candidates):
        if not isinstance(block, Mapping):
            continue
        for key, val in block.items():
            k = str(key)
            if "." in k:
                suffix = k.split(".")[-1]
                if suffix in KNOWN_PIECES:
                    candidates.append({suffix: val})

    for block in candidates:
        if not isinstance(block, Mapping):
            continue
        for name in KNOWN_PIECES:
            if name not in block:
                continue
            value = block.get(name)
            rep = _try_call_report(value)
            if isinstance(rep, dict):
                out[name] = rep

    return out


def _extract_params_piece(params: Mapping[str, Any], piece: str) -> Dict[str, Any]:
    """Extrait les paramètres utilisateur connus pour une pièce."""
    out: Dict[str, Any] = {}
    for path in (
        (piece,),
        ("pieces", piece),
        ("pieces_definition", piece),
        ("moteur_thermique", "pieces", piece),
        ("composants_definition", "moteur_thermique", "pieces", piece),
    ):
        v = _dig(params, *path)
        if isinstance(v, Mapping):
            out.update(dict(v))
    return out


def _set_nested_dict(root: Dict[str, Any], path: Sequence[str], value: Any) -> None:
    cur: Dict[str, Any] = root
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[path[-1]] = value


def _apply_piece_correction(params: Dict[str, Any], correction: AssemblyCorrection) -> None:
    """
    Applique une correction dans les emplacements probables sans écraser les
    autres pièces. On met à jour `pieces_definition` et `pieces`, car tes
    orchestrateurs utilisent fréquemment l'un ou l'autre.
    """
    piece = correction.piece
    champ = correction.champ
    valeur = correction.valeur

    _set_nested_dict(params, ("pieces_definition", piece, champ), valeur)
    _set_nested_dict(params, ("pieces", piece, champ), valeur)

    # Si la pièce existe déjà en top-level sous forme dict, on l'aligne aussi.
    if isinstance(params.get(piece), dict):
        params[piece][champ] = valeur

    # Si un format à points existe déjà, on le renseigne sans l'imposer partout.
    dotted_key = f"{piece}.{champ}"
    if dotted_key in params:
        params[dotted_key] = valeur


def _call_dimensionnement(callback: Callable[[Dict[str, Any]], Any], params: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    raw = callback(copy.deepcopy(params))
    return normaliser_rapports_pieces(raw)


def _callback_accepts_single_dict(callback: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(callback)
    except Exception:
        return True
    params = list(sig.parameters.values())
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return len(positional) <= 1 or any(p.kind == p.VAR_POSITIONAL for p in params)


# =============================================================================
# Vérificateur d'assemblage
# =============================================================================

class VerificateurAssemblage:
    """
    Vérifie la cohérence géométrique et mécanique des pièces du moteur thermique.

    Usage simple :
        verif = VerificateurAssemblage(rapports_pieces)
        issues = verif.verifier_tout()

    Usage avec relance :
        resultat = verif.optimiser_et_relancer(params, callback_dimensionnement)
    """

    def __init__(
        self,
        rapports_pieces: Optional[Mapping[str, Any]] = None,
        pieces_instances: Optional[Mapping[str, Any]] = None,
        *,
        tolerances: Optional[AssemblyTolerances] = None,
        strategie_correction: StrategieCorrection = "conserver_piece_amont",
        verifier_pieces_absentes: bool = False,
    ):
        self.rapports: Dict[str, Dict[str, Any]] = normaliser_rapports_pieces(rapports_pieces or {})
        self.instances = dict(pieces_instances or {})
        self.tolerances = tolerances or AssemblyTolerances()
        self.strategie_correction = strategie_correction
        self.verifier_pieces_absentes = bool(verifier_pieces_absentes)
        self.issues: List[AssemblyIssue] = []
        self.parametres_courants: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def verifier_tout(self, parametres_courants: Optional[Mapping[str, Any]] = None) -> List[AssemblyIssue]:
        self.issues = []
        self.parametres_courants = dict(parametres_courants or {})

        # Complète les rapports depuis les instances si nécessaire.
        for name, obj in self.instances.items():
            if name not in self.rapports:
                rep = _try_call_report(obj)
                if isinstance(rep, dict):
                    self.rapports[name] = rep

        if self.verifier_pieces_absentes:
            self._check_pieces_absentes()

        # Interfaces principales.
        self._check_cylindre_piston()
        self._check_piston_joint_piston()
        self._check_piston_axe()
        self._check_axe_bielle()
        self._check_axe_coussinet_pied_bielle()
        self._check_bielle_vilbrequin()
        self._check_arbre_vilebrequin_vilbrequin()
        self._check_vilbrequin_roulement()
        self._check_cylindre_couvercle()
        self._check_couvercle_vis()
        self._check_cylindre_deplaceur()
        self._check_deplaceur_joint()
        self._check_arbre_clavette()
        self._check_fuites_et_frottements_optionnels()

        self.issues.sort(key=lambda i: (0 if i.bloquant else 1, i.priorite, i.piece_a, i.piece_b, i.regle))
        return self.issues

    def verifier_rapport(self, parametres_courants: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        issues = self.verifier_tout(parametres_courants=parametres_courants)
        bloquants = [i for i in issues if i.bloquant and i.gravite == "erreur"]
        return {
            "ok": not bloquants,
            "nb_issues": len(issues),
            "nb_bloquants": len(bloquants),
            "issues": [i.en_dict() for i in issues],
            "pieces_verifiees": sorted(self.rapports.keys()),
        }

    def optimiser_et_relancer(
        self,
        parametres_initiaux: Mapping[str, Any],
        callback_dimensionnement: Callable[[Dict[str, Any]], Any],
        *,
        max_iterations: int = 5,
        appliquer_une_seule_correction_par_iteration: bool = True,
        stop_si_cycle: bool = True,
        verbose: bool = False,
    ) -> AssemblyOptimizationResult:
        """
        Relance le calcul en ciblant le point bloquant prioritaire.

        Le callback doit accepter un dict de paramètres et renvoyer soit :
        - directement {piece: rapport},
        - soit un rapport global contenant un bloc `pieces`, `rapports.pieces`, etc.
        """
        current_params = copy.deepcopy(dict(parametres_initiaux or {}))
        current_reports = copy.deepcopy(self.rapports)
        historique: List[AssemblyIteration] = []
        signatures_vues: set[str] = set()
        raison_arret = "max_iterations_atteint"

        if not current_reports:
            try:
                current_reports = _call_dimensionnement(callback_dimensionnement, current_params)
            except Exception as exc:
                return AssemblyOptimizationResult(
                    ok=False,
                    rapports={},
                    parametres_finaux=current_params,
                    issues_finales=[
                        AssemblyIssue(
                            piece_a="dimensionnement",
                            piece_b="callback",
                            regle="appel initial",
                            message=f"Échec du callback de dimensionnement : {exc}",
                            gravite="erreur",
                            bloquant=True,
                            priorite=0,
                        )
                    ],
                    historique=[],
                    raison_arret="erreur_callback_initial",
                )

        issues: List[AssemblyIssue] = []
        for iteration in range(max(1, int(max_iterations)) + 1):
            self.rapports = normaliser_rapports_pieces(current_reports)
            issues = self.verifier_tout(parametres_courants=current_params)
            bloquants = [i for i in issues if i.bloquant and i.gravite == "erreur"]

            if not bloquants:
                historique.append(
                    AssemblyIteration(
                        iteration=iteration,
                        ok=True,
                        nb_issues=len(issues),
                        nb_bloquants=0,
                        parametres_apres_correction=copy.deepcopy(current_params),
                    )
                )
                raison_arret = "assemblage_valide"
                return AssemblyOptimizationResult(
                    ok=True,
                    rapports=self.rapports,
                    parametres_finaux=current_params,
                    issues_finales=issues,
                    historique=historique,
                    raison_arret=raison_arret,
                )

            point_bloquant = bloquants[0]
            corrections = list(point_bloquant.corrections)
            if not corrections:
                historique.append(
                    AssemblyIteration(
                        iteration=iteration,
                        ok=False,
                        nb_issues=len(issues),
                        nb_bloquants=len(bloquants),
                        point_bloquant=point_bloquant,
                        corrections_appliquees=[],
                        parametres_apres_correction=copy.deepcopy(current_params),
                    )
                )
                raison_arret = "point_bloquant_sans_correction_automatique"
                break

            if appliquer_une_seule_correction_par_iteration:
                corrections = corrections[:1]

            signature = json.dumps(
                [(c.piece, c.champ, _to_jsonable(c.valeur)) for c in corrections],
                sort_keys=True,
                ensure_ascii=False,
            )
            if stop_si_cycle and signature in signatures_vues:
                raison_arret = "cycle_correction_detecte"
                break
            signatures_vues.add(signature)

            for correction in corrections:
                _apply_piece_correction(current_params, correction)

            historique.append(
                AssemblyIteration(
                    iteration=iteration,
                    ok=False,
                    nb_issues=len(issues),
                    nb_bloquants=len(bloquants),
                    point_bloquant=point_bloquant,
                    corrections_appliquees=corrections,
                    parametres_apres_correction=copy.deepcopy(current_params),
                )
            )

            if verbose:
                print(
                    f"[VERIFICATEUR_ASSEMBLAGE] it={iteration} "
                    f"blocage={point_bloquant.piece_a}/{point_bloquant.piece_b} "
                    f"regle={point_bloquant.regle} corrections="
                    f"{[(c.piece, c.champ, c.valeur) for c in corrections]}"
                )

            try:
                current_reports = _call_dimensionnement(callback_dimensionnement, current_params)
            except Exception as exc:
                raison_arret = "erreur_callback_apres_correction"
                issues = [
                    AssemblyIssue(
                        piece_a="dimensionnement",
                        piece_b="callback",
                        regle="relance après correction",
                        message=f"Échec du callback après correction : {exc}",
                        gravite="erreur",
                        bloquant=True,
                        priorite=0,
                        corrections=[],
                    )
                ]
                break

        return AssemblyOptimizationResult(
            ok=False,
            rapports=normaliser_rapports_pieces(current_reports),
            parametres_finaux=current_params,
            issues_finales=issues,
            historique=historique,
            raison_arret=raison_arret,
        )

    def resoudre_et_relancer(
        self,
        parametres_initiaux: Dict[str, Any],
        callback_dimensionnement: Callable[[Dict[str, Any]], Any],
        max_iterations: int = 3,
    ) -> Tuple[Dict[str, Dict[str, Any]], List[AssemblyIssue]]:
        """
        Compatibilité avec ton ancienne signature.
        Pour le rapport complet, utilise plutôt optimiser_et_relancer(...).en_dict().
        """
        result = self.optimiser_et_relancer(
            parametres_initiaux,
            callback_dimensionnement,
            max_iterations=max_iterations,
        )
        return result.rapports, result.issues_finales

    # ------------------------------------------------------------------
    # Extraction de cotes normalisées
    # ------------------------------------------------------------------

    def _r(self, piece: str) -> Dict[str, Any]:
        return _safe_dict(self.rapports.get(piece))

    def _params_valides(self, *pieces_bloquees: str) -> Dict[str, Any]:
        """Renvoie les paramètres actuels en excluant les pièces bloquées."""
        if not self.parametres_courants:
            return {}
        out = copy.deepcopy(self.parametres_courants)
        for container in ("pieces", "pieces_definition"):
            block = _safe_dict(out.get(container))
            for p in pieces_bloquees:
                block.pop(p, None)
            if block:
                out[container] = block
        for p in pieces_bloquees:
            if isinstance(out.get(p), dict):
                out.pop(p, None)
        return out

    def _add_issue(
        self,
        *,
        piece_a: str,
        piece_b: str,
        regle: str,
        message: str,
        valeur_a: Any = None,
        valeur_b: Any = None,
        chemin_a: Optional[str] = None,
        chemin_b: Optional[str] = None,
        attendu: Optional[str] = None,
        ecart: Optional[float] = None,
        gravite: GraviteAssemblage = "erreur",
        bloquant: bool = True,
        priorite: int = 100,
        corrections: Optional[List[AssemblyCorrection]] = None,
        donnees_manquantes: Optional[List[str]] = None,
    ) -> None:
        self.issues.append(
            AssemblyIssue(
                piece_a=piece_a,
                piece_b=piece_b,
                regle=regle,
                message=message,
                valeur_a=valeur_a,
                valeur_b=valeur_b,
                chemin_a=chemin_a,
                chemin_b=chemin_b,
                attendu=attendu,
                ecart=ecart,
                gravite=gravite,
                bloquant=bloquant,
                priorite=priorite,
                corrections=corrections or [],
                parametres_valides=self._params_valides(piece_a, piece_b),
                donnees_manquantes=donnees_manquantes or [],
            )
        )

    def _missing(self, piece_a: str, piece_b: str, regle: str, missing: List[str], *, priorite: int = 900) -> None:
        self._add_issue(
            piece_a=piece_a,
            piece_b=piece_b,
            regle=regle,
            message="Vérification impossible : données manquantes ou non numériques.",
            gravite="avertissement",
            bloquant=False,
            priorite=priorite,
            donnees_manquantes=missing,
        )

    # --- métriques pièces ------------------------------------------------------

    def _cylindre(self) -> Dict[str, Optional[float]]:
        r = self._r("cylindre")
        return {
            "alesage_m": _finite_from_paths(r, (
                ("entrees", "alesage_m"),
                ("geometrie", "alesage_m"),
                ("geometrie", "diametre_interne_m"),
                ("geometrie", "diametre_interieur_m"),
                ("geometrie", "diametre_interieur_nominal_m"),
                ("geometrie", "cao", "diametre_interieur_nominal_m"),
                ("cao", "diametre_interieur_nominal_m"),
            )),
            "diametre_exterieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_exterieur_m"),
                ("geometrie", "diametre_externe_m"),
                ("geometrie", "cao", "diametre_exterieur_nominal_m"),
                ("cao", "diametre_exterieur_nominal_m"),
            )),
            "diametre_bride_externe_m": _finite_from_paths(r, (
                ("assemblage", "diametre_bride_externe_m"),
                ("geometrie", "diametre_bride_externe_m"),
            )),
            "diametre_cercle_percage_m": _finite_from_paths(r, (
                ("assemblage", "diametre_cercle_percage_m"),
                ("geometrie", "diametre_cercle_percage_m"),
            )),
            "force_separation_N": _finite_from_paths(r, (
                ("assemblage", "force_separation_N"),
                ("assemblage", "force_pression_piston_max_N"),
            )),
        }

    def _piston(self) -> Dict[str, Optional[float]]:
        r = self._r("piston")
        return {
            "diametre_exterieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_exterieur_m"),
                ("dimensions", "diametre_exterieur_m"),
                ("cao", "diametre_exterieur_nominal_m"),
                ("entrees", "diametre_exterieur_m"),
                ("entrees", "alesage_nominal_m"),
            )),
            "diametre_axe_m": _finite_from_paths(r, (
                ("geometrie", "diametre_axe_m"),
                ("geometrie", "diametre_logement_axe_m"),
                ("dimensions", "diametre_axe_m"),
                ("axes", "diametre_axe_m"),
                ("entrees", "diametre_axe_m"),
            )),
            "diametre_fond_rainure_m": _finite_from_paths(r, (
                ("joints", "diametre_fond_rainure_m"),
                ("geometrie", "diametre_fond_rainure_m"),
                ("rainures", "diametre_fond_rainure_m"),
            )),
            "nb_joints": _int_from_paths(r, (
                ("joints", "nb_joints"),
                ("rainures", "nb_joints"),
                ("entrees", "nb_joints"),
            )),
        }

    def _joint_piston(self) -> Dict[str, Optional[float]]:
        r = self._r("joint_piston")
        return {
            "diametre_interieur_cylindre_m": _finite_from_paths(r, (
                ("geometrie_joint", "diametre_interieur_cylindre_m"),
                ("geometrie", "diametre_interieur_cylindre_m"),
                ("entrees", "diametre_interieur_cylindre_m"),
            )),
            "diametre_interieur_joint_m": _finite_from_paths(r, (
                ("geometrie_joint", "diametre_interieur_joint_m"),
                ("geometrie", "diametre_interieur_joint_m"),
            )),
            "diametre_fond_gorge_m": _finite_from_paths(r, (
                ("gorge", "diametre_fond_gorge_m"),
                ("geometrie", "diametre_fond_gorge_m"),
            )),
            "section_joint_m": _finite_from_paths(r, (
                ("geometrie_joint", "section_joint_m"),
                ("geometrie_joint", "diametre_section_joint_m"),
                ("geometrie", "section_joint_m"),
            )),
            "squeeze": _finite_from_paths(r, (
                ("coherences", "squeeze"),
                ("assemblage", "squeeze"),
            )),
            "nb_joints": _int_from_paths(r, (
                ("rainures", "nb_joints"),
                ("geometrie_joint", "nb_joints"),
                ("entrees", "nb_joints"),
            )),
        }

    def _arbre_piston(self) -> Dict[str, Optional[float]]:
        r = self._r("arbre_piston")
        return {
            "diametre_exterieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_exterieur_m"),
                ("geometrie", "diametre_axe_m"),
                ("dimensions", "diametre_exterieur_m"),
                ("entrees", "diametre_axe_m"),
            )),
            "longueur_m": _finite_from_paths(r, (
                ("geometrie", "longueur_m"),
                ("dimensions", "longueur_m"),
            )),
        }

    def _bielle(self) -> Dict[str, Optional[float]]:
        r = self._r("bielle")
        return {
            "diametre_axe_piston_m": _finite_from_paths(r, (
                ("geometrie", "diametre_axe_piston_m"),
                ("geometrie", "diametre_petite_tete_m"),
                ("geometrie", "alesage_petite_tete_m"),
                ("interfaces", "diametre_axe_piston_m"),
                ("entrees", "diametre_axe_piston_m"),
            )),
            "diametre_maneton_m": _finite_from_paths(r, (
                ("geometrie", "diametre_maneton_m"),
                ("geometrie", "diametre_grande_tete_m"),
                ("geometrie", "alesage_grande_tete_m"),
                ("interfaces", "diametre_maneton_m"),
                ("entrees", "diametre_maneton_m"),
            )),
            "longueur_bielle_m": _finite_from_paths(r, (
                ("geometrie", "longueur_bielle_m"),
                ("entrees", "longueur_bielle_m"),
            )),
        }

    def _coussinet(self) -> Dict[str, Optional[float]]:
        r = self._r("coussinet_arbre_piston")
        return {
            "diametre_interieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_interieur_m"),
                ("dimensions", "diametre_interieur_m"),
                ("interfaces", "diametre_interieur_m"),
            )),
            "diametre_exterieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_exterieur_m"),
                ("dimensions", "diametre_exterieur_m"),
                ("interfaces", "diametre_exterieur_m"),
            )),
        }

    def _vilebrequin(self, piece: str = "vilbrequin") -> Dict[str, Optional[float]]:
        r = self._r(piece)
        return {
            "diametre_maneton_m": _finite_from_paths(r, (
                ("geometrie", "diametre_maneton_m"),
                ("maneton", "diametre_maneton_m"),
                ("interfaces", "diametre_maneton_m"),
                ("entrees", "diametre_maneton_m"),
            )),
            "diametre_palier_m": _finite_from_paths(r, (
                ("geometrie", "diametre_palier_m"),
                ("paliers", "diametre_palier_m"),
                ("interfaces", "diametre_palier_m"),
            )),
            "course_m": _finite_from_paths(r, (
                ("geometrie", "course_m"),
                ("entrees", "course_m"),
            )),
        }

    def _roulement(self, piece: str) -> Dict[str, Optional[float]]:
        r = self._r(piece)
        return {
            "diametre_interieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_interieur_m"),
                ("dimensions", "diametre_interieur_m"),
                ("interfaces", "diametre_interieur_m"),
                ("entrees", "diametre_interieur_m"),
            )),
            "diametre_exterieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_exterieur_m"),
                ("dimensions", "diametre_exterieur_m"),
                ("interfaces", "diametre_exterieur_m"),
            )),
        }

    def _couvercle(self) -> Dict[str, Optional[float]]:
        r = self._r("couvercle_cylindre")
        return {
            "diametre_exterieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_exterieur_m"),
                ("dimensions", "diametre_exterieur_m"),
                ("entrees", "diametre_exterieur_m"),
            )),
            "diametre_cercle_percage_m": _finite_from_paths(r, (
                ("assemblage", "diametre_cercle_percage_m"),
                ("geometrie", "diametre_cercle_percage_m"),
                ("entrees", "diametre_cercle_percage_m"),
            )),
            "nb_vis": _int_from_paths(r, (
                ("assemblage", "nb_vis"),
                ("entrees", "nb_vis"),
            )),
        }

    def _vis(self) -> Dict[str, Optional[float]]:
        r = self._r("vis_couvercle_cylindre")
        return {
            "diametre_nominal_m": _finite_from_paths(r, (
                ("geometrie", "diametre_nominal_m"),
                ("dimensions", "diametre_nominal_m"),
                ("entrees", "diametre_nominal_m"),
            )),
            "nb_vis": _int_from_paths(r, (
                ("assemblage", "nb_vis"),
                ("entrees", "nb_vis"),
            )),
            "precharge_totale_N": _finite_from_paths(r, (
                ("assemblage", "precharge_totale_N"),
                ("resultats", "precharge_totale_N"),
                ("precharge", "precharge_totale_N"),
            )),
        }

    def _deplaceur(self, piece: str = "deplaceur") -> Dict[str, Optional[float]]:
        r = self._r(piece)
        return {
            "diametre_exterieur_m": _finite_from_paths(r, (
                ("geometrie", "diametre_exterieur_m"),
                ("dimensions", "diametre_exterieur_m"),
                ("entrees", "diametre_exterieur_m"),
            )),
            "jeu_radial_m": _finite_from_paths(r, (
                ("geometrie", "jeu_radial_m"),
                ("assemblage", "jeu_radial_m"),
            )),
        }

    def _arbre(self) -> Dict[str, Optional[float]]:
        r = self._r("arbre")
        return {
            "diametre_m": _finite_from_paths(r, (
                ("geometrie", "diametre_m"),
                ("geometrie", "diametre_arbre_m"),
                ("dimensions", "diametre_m"),
                ("interfaces", "diametre_arbre_m"),
                ("entrees", "diametre_arbre_m"),
            )),
            "longueur_portee_clavette_disponible_m": _finite_from_paths(r, (
                ("interfaces", "longueur_portee_clavette_disponible_m"),
                ("entrees", "longueur_portee_clavette_disponible_m"),
            )),
            "clavette_b_m": _finite_from_paths(r, (
                ("clavette", "b_m"),
                ("interfaces", "clavette_b_m"),
                ("entrees", "clavette_b_m"),
            )),
            "clavette_h_m": _finite_from_paths(r, (
                ("clavette", "h_m"),
                ("interfaces", "clavette_h_m"),
                ("entrees", "clavette_h_m"),
            )),
        }

    def _clavette(self) -> Dict[str, Optional[float]]:
        r = self._r("clavette_arbre")
        return {
            "diametre_arbre_m": _finite_from_paths(r, (
                ("interfaces", "diametre_arbre_m"),
                ("entrees", "diametre_arbre_m"),
            )),
            "b_m": _finite_from_paths(r, (
                ("dimensions", "b_m"),
                ("clavette", "b_m"),
                ("interfaces", "clavette_b_m"),
            )),
            "h_m": _finite_from_paths(r, (
                ("dimensions", "h_m"),
                ("clavette", "h_m"),
                ("interfaces", "clavette_h_m"),
            )),
            "longueur_m": _finite_from_paths(r, (
                ("dimensions", "longueur_m"),
                ("clavette", "longueur_m"),
                ("interfaces", "longueur_clavette_m"),
            )),
        }

    # ------------------------------------------------------------------
    # Règles
    # ------------------------------------------------------------------

    def _check_pieces_absentes(self) -> None:
        for piece in PIECE_BUILD_ORDER:
            if piece == "clavette_arbre":
                continue
            if not _has_piece(self.rapports, piece):
                self._add_issue(
                    piece_a=piece,
                    piece_b="assemblage",
                    regle="présence pièce",
                    message=f"Pièce absente du rapport d'assemblage : {piece}.",
                    gravite="avertissement",
                    bloquant=False,
                    priorite=950,
                )

    def _check_cylindre_piston(self) -> None:
        if not (_has_piece(self.rapports, "cylindre") and _has_piece(self.rapports, "piston")):
            return
        cyl = self._cylindre()
        pis = self._piston()
        bore = cyl["alesage_m"]
        d_piston = pis["diametre_exterieur_m"]
        jeu = self.tolerances.jeu_diametral_piston_cylindre_min_m
        if bore is None or d_piston is None:
            self._missing("cylindre", "piston", "piston dans alésage", ["cylindre.alesage_m", "piston.diametre_exterieur_m"])
            return
        if not _close_or_ordered(bore, d_piston, jeu_min=jeu, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
            if self.strategie_correction == "corriger_piece_amont":
                corrections = [AssemblyCorrection("cylindre", "alesage_m", d_piston + jeu, "Agrandir l'alésage pour accepter le piston et le jeu minimal.")]
            else:
                corrections = [
                    AssemblyCorrection("piston", "alesage_nominal_m", bore, "Recalculer le piston sur l'alésage validé du cylindre."),
                    AssemblyCorrection("piston", "diametre_exterieur_m", max(0.0, bore - jeu), "Limiter le diamètre extérieur du piston pour l'emboîtement."),
                ]
            self._add_issue(
                piece_a="cylindre",
                piece_b="piston",
                regle="diamètre piston <= alésage cylindre - jeu",
                valeur_a=bore,
                valeur_b=d_piston,
                chemin_a="cylindre.alesage_m",
                chemin_b="piston.diametre_exterieur_m",
                attendu=f"diametre_piston_m <= {bore - jeu:.9g} m",
                ecart=d_piston - (bore - jeu),
                message=f"Le piston ({d_piston * 1000:.3f} mm) ne rentre pas dans l'alésage utile ({(bore - jeu) * 1000:.3f} mm).",
                priorite=10,
                corrections=corrections,
            )

    def _check_piston_joint_piston(self) -> None:
        if not _has_piece(self.rapports, "joint_piston"):
            return
        cyl = self._cylindre()
        pis = self._piston()
        jp = self._joint_piston()
        bore = cyl["alesage_m"]
        d_cyl_joint = jp["diametre_interieur_cylindre_m"]
        if bore is not None and d_cyl_joint is not None:
            if not math.isclose(bore, d_cyl_joint, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
                self._add_issue(
                    piece_a="cylindre",
                    piece_b="joint_piston",
                    regle="joint piston calé sur alésage",
                    valeur_a=bore,
                    valeur_b=d_cyl_joint,
                    chemin_a="cylindre.alesage_m",
                    chemin_b="joint_piston.diametre_interieur_cylindre_m",
                    attendu="diametre_interieur_cylindre_m == alesage_m",
                    ecart=d_cyl_joint - bore,
                    message=f"Le joint piston référence un cylindre de {d_cyl_joint * 1000:.3f} mm au lieu de {bore * 1000:.3f} mm.",
                    priorite=30,
                    corrections=[AssemblyCorrection("joint_piston", "diametre_interieur_cylindre_m", bore, "Recalculer le joint piston sur l'alésage validé.")],
                )

        nb_pis = pis.get("nb_joints")
        nb_joint = jp.get("nb_joints")
        if nb_pis is not None and nb_joint is not None and nb_pis != nb_joint:
            self._add_issue(
                piece_a="piston",
                piece_b="joint_piston",
                regle="nombre de joints cohérent",
                valeur_a=nb_pis,
                valeur_b=nb_joint,
                chemin_a="piston.nb_joints",
                chemin_b="joint_piston.nb_joints",
                attendu="même nombre de joints/rainures",
                message=f"Le piston annonce {nb_pis} joint(s), le module joint_piston en annonce {nb_joint}.",
                priorite=35,
                corrections=[AssemblyCorrection("joint_piston", "nb_joints", nb_pis, "Aligner le nombre de joints sur le piston validé.")],
            )

        squeeze = jp.get("squeeze")
        if squeeze is not None:
            smin = self.tolerances.squeeze_joint_min
            smax = self.tolerances.squeeze_joint_max
            if smin is not None and squeeze < smin:
                self._add_issue(
                    piece_a="piston",
                    piece_b="joint_piston",
                    regle="squeeze joint piston minimal",
                    valeur_a=smin,
                    valeur_b=squeeze,
                    attendu=f"squeeze >= {smin}",
                    message=f"Squeeze du joint piston trop faible : {squeeze} < {smin}.",
                    priorite=80,
                    corrections=[],
                )
            if smax is not None and squeeze > smax:
                self._add_issue(
                    piece_a="piston",
                    piece_b="joint_piston",
                    regle="squeeze joint piston maximal",
                    valeur_a=smax,
                    valeur_b=squeeze,
                    attendu=f"squeeze <= {smax}",
                    message=f"Squeeze du joint piston trop fort : {squeeze} > {smax}.",
                    priorite=80,
                    corrections=[],
                )

    def _check_piston_axe(self) -> None:
        if not (_has_piece(self.rapports, "piston") and _has_piece(self.rapports, "arbre_piston")):
            return
        pis = self._piston()
        axe = self._arbre_piston()
        logement = pis["diametre_axe_m"]
        d_axe = axe["diametre_exterieur_m"]
        jeu = self.tolerances.jeu_diametral_axe_logement_min_m
        if logement is None or d_axe is None:
            self._missing("piston", "arbre_piston", "axe dans logement piston", ["piston.diametre_axe_m", "arbre_piston.diametre_exterieur_m"])
            return
        if not _close_or_ordered(logement, d_axe, jeu_min=jeu, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
            self._add_issue(
                piece_a="piston",
                piece_b="arbre_piston",
                regle="axe piston <= logement piston - jeu",
                valeur_a=logement,
                valeur_b=d_axe,
                chemin_a="piston.diametre_axe_m",
                chemin_b="arbre_piston.diametre_exterieur_m",
                attendu=f"diametre_axe <= {logement - jeu:.9g} m",
                ecart=d_axe - (logement - jeu),
                message=f"L'axe piston ({d_axe * 1000:.3f} mm) est incompatible avec le logement ({logement * 1000:.3f} mm).",
                priorite=20,
                corrections=[AssemblyCorrection("arbre_piston", "diametre_exterieur_m", max(0.0, logement - jeu), "Recalculer l'axe sur le logement piston validé.")],
            )

    def _check_axe_bielle(self) -> None:
        if not (_has_piece(self.rapports, "arbre_piston") and _has_piece(self.rapports, "bielle")):
            return
        axe = self._arbre_piston()
        bie = self._bielle()
        d_axe = axe["diametre_exterieur_m"]
        d_petite_tete = bie["diametre_axe_piston_m"]
        jeu = self.tolerances.jeu_diametral_axe_logement_min_m
        if d_axe is None or d_petite_tete is None:
            self._missing("arbre_piston", "bielle", "axe dans petite tête de bielle", ["arbre_piston.diametre_exterieur_m", "bielle.diametre_axe_piston_m"])
            return
        if not _close_or_ordered(d_petite_tete, d_axe, jeu_min=jeu, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
            self._add_issue(
                piece_a="arbre_piston",
                piece_b="bielle",
                regle="axe piston <= petite tête bielle - jeu",
                valeur_a=d_axe,
                valeur_b=d_petite_tete,
                chemin_a="arbre_piston.diametre_exterieur_m",
                chemin_b="bielle.diametre_axe_piston_m",
                attendu=f"diametre_petite_tete >= {d_axe + jeu:.9g} m",
                ecart=d_axe - (d_petite_tete - jeu),
                message=f"La petite tête de bielle ({d_petite_tete * 1000:.3f} mm) n'accepte pas l'axe ({d_axe * 1000:.3f} mm).",
                priorite=25,
                corrections=[AssemblyCorrection("bielle", "diametre_axe_piston_m", d_axe + jeu, "Recalculer la petite tête sur l'axe piston validé.")],
            )

    def _check_axe_coussinet_pied_bielle(self) -> None:
        if not (_has_piece(self.rapports, "arbre_piston") and _has_piece(self.rapports, "coussinet_arbre_piston")):
            return
        axe = self._arbre_piston()
        cous = self._coussinet()
        d_axe = axe["diametre_exterieur_m"]
        d_int = cous["diametre_interieur_m"]
        jeu = self.tolerances.jeu_diametral_coussinet_arbre_min_m
        if d_axe is None or d_int is None:
            self._missing("arbre_piston", "coussinet_arbre_piston", "axe dans coussinet", ["arbre_piston.diametre_exterieur_m", "coussinet.diametre_interieur_m"])
            return
        if not _close_or_ordered(d_int, d_axe, jeu_min=jeu, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
            self._add_issue(
                piece_a="arbre_piston",
                piece_b="coussinet_arbre_piston",
                regle="axe <= diamètre intérieur coussinet - jeu",
                valeur_a=d_axe,
                valeur_b=d_int,
                attendu=f"diametre_interieur_coussinet >= {d_axe + jeu:.9g} m",
                ecart=d_axe - (d_int - jeu),
                message=f"Le coussinet de pied de bielle ({d_int * 1000:.3f} mm intérieur) n'accepte pas l'axe ({d_axe * 1000:.3f} mm).",
                priorite=28,
                corrections=[AssemblyCorrection("coussinet_arbre_piston", "diametre_interieur_m", d_axe + jeu, "Recalculer le coussinet sur l'axe validé.")],
            )

        # Coussinet extérieur dans petite tête de bielle si les deux données existent.
        bie = self._bielle()
        d_ext_cous = cous["diametre_exterieur_m"]
        d_petite_tete = bie["diametre_axe_piston_m"]
        if d_ext_cous is not None and d_petite_tete is not None and d_ext_cous > d_petite_tete + self.tolerances.abs_tol_m:
            self._add_issue(
                piece_a="bielle",
                piece_b="coussinet_arbre_piston",
                regle="coussinet extérieur <= logement bielle",
                valeur_a=d_petite_tete,
                valeur_b=d_ext_cous,
                attendu="diametre_exterieur_coussinet <= diametre_petite_tete_bielle",
                ecart=d_ext_cous - d_petite_tete,
                message=f"Le coussinet extérieur ({d_ext_cous * 1000:.3f} mm) est plus grand que le logement de bielle ({d_petite_tete * 1000:.3f} mm).",
                priorite=29,
                corrections=[AssemblyCorrection("bielle", "diametre_axe_piston_m", d_ext_cous, "Agrandir le logement de pied de bielle pour accepter le coussinet.")],
            )

    def _check_bielle_vilbrequin(self) -> None:
        if not _has_piece(self.rapports, "bielle"):
            return
        vil_piece = "vilbrequin" if _has_piece(self.rapports, "vilbrequin") else "arbre_vilebrequin"
        if not _has_piece(self.rapports, vil_piece):
            return
        bie = self._bielle()
        vil = self._vilebrequin(vil_piece)
        d_big = bie["diametre_maneton_m"]
        d_maneton = vil["diametre_maneton_m"]
        jeu = self.tolerances.jeu_diametral_bielle_maneton_min_m
        if d_big is None or d_maneton is None:
            self._missing("bielle", vil_piece, "grande tête de bielle sur maneton", ["bielle.diametre_maneton_m", f"{vil_piece}.diametre_maneton_m"])
            return
        if not _close_or_ordered(d_big, d_maneton, jeu_min=jeu, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
            self._add_issue(
                piece_a="bielle",
                piece_b=vil_piece,
                regle="maneton <= grande tête bielle - jeu",
                valeur_a=d_big,
                valeur_b=d_maneton,
                chemin_a="bielle.diametre_maneton_m",
                chemin_b=f"{vil_piece}.diametre_maneton_m",
                attendu=f"diametre_grande_tete >= {d_maneton + jeu:.9g} m",
                ecart=d_maneton - (d_big - jeu),
                message=f"Le maneton ({d_maneton * 1000:.3f} mm) ne rentre pas dans la grande tête de bielle ({d_big * 1000:.3f} mm).",
                priorite=40,
                corrections=[AssemblyCorrection("bielle", "diametre_maneton_m", d_maneton + jeu, "Recalculer la grande tête de bielle sur le maneton validé.")],
            )

    def _check_arbre_vilebrequin_vilbrequin(self) -> None:
        if not (_has_piece(self.rapports, "arbre_vilebrequin") and _has_piece(self.rapports, "vilbrequin")):
            return
        av = self._vilebrequin("arbre_vilebrequin")
        vb = self._vilebrequin("vilbrequin")
        for field_name in ("diametre_maneton_m", "course_m"):
            a = av.get(field_name)
            b = vb.get(field_name)
            if a is None or b is None:
                continue
            if not math.isclose(a, b, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
                self._add_issue(
                    piece_a="arbre_vilebrequin",
                    piece_b="vilbrequin",
                    regle=f"cohérence {field_name}",
                    valeur_a=a,
                    valeur_b=b,
                    attendu=f"arbre_vilebrequin.{field_name} == vilbrequin.{field_name}",
                    ecart=b - a,
                    message=f"Incohérence {field_name} entre arbre_vilebrequin ({a}) et vilbrequin ({b}).",
                    priorite=42,
                    corrections=[AssemblyCorrection("vilbrequin", field_name, a, "Aligner le vilebrequin sur l'arbre vilebrequin validé.")],
                )

    def _check_vilbrequin_roulement(self) -> None:
        vil_piece = "vilbrequin" if _has_piece(self.rapports, "vilbrequin") else "arbre_vilebrequin"
        if not _has_piece(self.rapports, vil_piece):
            return
        vil = self._vilebrequin(vil_piece)
        d_palier = vil["diametre_palier_m"]
        for roulement_piece in ("roulement_aiguille_arbre", "roulement_aiguille_arbre_vilebrequin"):
            if not _has_piece(self.rapports, roulement_piece):
                continue
            rou = self._roulement(roulement_piece)
            d_int = rou["diametre_interieur_m"]
            if d_palier is None or d_int is None:
                self._missing(vil_piece, roulement_piece, "palier dans roulement", [f"{vil_piece}.diametre_palier_m", f"{roulement_piece}.diametre_interieur_m"], priorite=910)
                continue
            if not math.isclose(d_palier, d_int, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
                self._add_issue(
                    piece_a=vil_piece,
                    piece_b=roulement_piece,
                    regle="diamètre palier / roulement",
                    valeur_a=d_palier,
                    valeur_b=d_int,
                    attendu="diametre_interieur_roulement ~= diametre_palier",
                    ecart=d_int - d_palier,
                    message=f"Le roulement {roulement_piece} a un diamètre intérieur {d_int * 1000:.3f} mm incompatible avec le palier {d_palier * 1000:.3f} mm.",
                    priorite=50,
                    corrections=[AssemblyCorrection(roulement_piece, "diametre_interieur_m", d_palier, "Aligner le roulement sur le palier validé.")],
                )

    def _check_cylindre_couvercle(self) -> None:
        if not (_has_piece(self.rapports, "cylindre") and _has_piece(self.rapports, "couvercle_cylindre")):
            return
        cyl = self._cylindre()
        cov = self._couvercle()
        d_ref = _first_finite(cyl["diametre_bride_externe_m"], cyl["diametre_exterieur_m"], cyl["alesage_m"])
        d_cov = cov["diametre_exterieur_m"]
        marge = self.tolerances.marge_couvercle_sur_cylindre_m
        if d_ref is None or d_cov is None:
            self._missing("cylindre", "couvercle_cylindre", "couvercle couvre cylindre/bride", ["cylindre.diametre_exterieur_m ou bride", "couvercle.diametre_exterieur_m"])
            return
        if d_cov + self.tolerances.abs_tol_m < d_ref + marge:
            self._add_issue(
                piece_a="cylindre",
                piece_b="couvercle_cylindre",
                regle="diamètre couvercle >= cylindre/bride + marge",
                valeur_a=d_ref,
                valeur_b=d_cov,
                attendu=f"diametre_couvercle >= {d_ref + marge:.9g} m",
                ecart=(d_ref + marge) - d_cov,
                message=f"Le couvercle ({d_cov * 1000:.3f} mm) est trop petit pour le cylindre/bride ({(d_ref + marge) * 1000:.3f} mm requis).",
                priorite=60,
                corrections=[AssemblyCorrection("couvercle_cylindre", "diametre_exterieur_m", d_ref + marge, "Agrandir le couvercle sur la bride/cylindre validé.")],
            )

        pcd_cyl = cyl["diametre_cercle_percage_m"]
        pcd_cov = cov["diametre_cercle_percage_m"]
        if pcd_cyl is not None and pcd_cov is not None:
            if not math.isclose(pcd_cyl, pcd_cov, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
                self._add_issue(
                    piece_a="cylindre",
                    piece_b="couvercle_cylindre",
                    regle="cercle de perçage commun",
                    valeur_a=pcd_cyl,
                    valeur_b=pcd_cov,
                    attendu="même diamètre de cercle de perçage",
                    ecart=pcd_cov - pcd_cyl,
                    message=f"Cercle de perçage couvercle ({pcd_cov * 1000:.3f} mm) différent du cylindre ({pcd_cyl * 1000:.3f} mm).",
                    priorite=62,
                    corrections=[AssemblyCorrection("couvercle_cylindre", "diametre_cercle_percage_m", pcd_cyl, "Aligner le perçage du couvercle sur celui du cylindre.")],
                )

    def _check_couvercle_vis(self) -> None:
        if not _has_piece(self.rapports, "vis_couvercle_cylindre"):
            return
        cov = self._couvercle()
        vis = self._vis()
        nb_cov = cov.get("nb_vis")
        nb_vis = vis.get("nb_vis")
        if nb_cov is not None and nb_vis is not None and nb_cov != nb_vis:
            self._add_issue(
                piece_a="couvercle_cylindre",
                piece_b="vis_couvercle_cylindre",
                regle="nombre de vis",
                valeur_a=nb_cov,
                valeur_b=nb_vis,
                attendu="même nombre de vis",
                message=f"Le couvercle attend {nb_cov} vis, le module vis en fournit {nb_vis}.",
                priorite=65,
                corrections=[AssemblyCorrection("vis_couvercle_cylindre", "nb_vis", nb_cov, "Aligner le nombre de vis sur le couvercle validé.")],
            )

        cyl = self._cylindre()
        force_sep = cyl.get("force_separation_N")
        precharge = vis.get("precharge_totale_N")
        if force_sep is not None and precharge is not None and precharge + self.tolerances.abs_tol_m < force_sep:
            self._add_issue(
                piece_a="cylindre",
                piece_b="vis_couvercle_cylindre",
                regle="précharge vis >= force séparation",
                valeur_a=force_sep,
                valeur_b=precharge,
                attendu="precharge_totale_N >= force_separation_N",
                ecart=force_sep - precharge,
                message=f"Précharge totale des vis insuffisante ({precharge:.1f} N) face à la force de séparation ({force_sep:.1f} N).",
                priorite=66,
                corrections=[AssemblyCorrection("vis_couvercle_cylindre", "force_precharge_totale_requise_N", force_sep, "Recalculer les vis sur la force de séparation validée.")],
            )

    def _check_cylindre_deplaceur(self) -> None:
        if not (_has_piece(self.rapports, "cylindre") and _has_piece(self.rapports, "deplaceur")):
            return
        cyl = self._cylindre()
        dep = self._deplaceur("deplaceur")
        bore = cyl["alesage_m"]
        d_dep = dep["diametre_exterieur_m"]
        jeu_radial = self.tolerances.jeu_radial_deplaceur_cylindre_min_m
        jeu_diam = 2.0 * jeu_radial
        if bore is None or d_dep is None:
            self._missing("cylindre", "deplaceur", "déplaceur dans cylindre", ["cylindre.alesage_m", "deplaceur.diametre_exterieur_m"])
            return
        if d_dep > bore - jeu_diam + self.tolerances.abs_tol_m:
            self._add_issue(
                piece_a="cylindre",
                piece_b="deplaceur",
                regle="déplaceur <= alésage - jeu radial*2",
                valeur_a=bore,
                valeur_b=d_dep,
                attendu=f"diametre_deplaceur <= {bore - jeu_diam:.9g} m",
                ecart=d_dep - (bore - jeu_diam),
                message=f"Le déplaceur ({d_dep * 1000:.3f} mm) ne rentre pas dans l'alésage utile ({(bore - jeu_diam) * 1000:.3f} mm).",
                priorite=70,
                corrections=[AssemblyCorrection("deplaceur", "diametre_exterieur_m", max(0.0, bore - jeu_diam), "Recalculer le déplaceur sur l'alésage validé.")],
            )

    def _check_deplaceur_joint(self) -> None:
        if not (_has_piece(self.rapports, "deplaceur") and _has_piece(self.rapports, "joint_deplaceur")):
            return
        dep = self._deplaceur("deplaceur")
        jd = self._deplaceur("joint_deplaceur")
        d_dep = dep["diametre_exterieur_m"]
        d_joint = jd["diametre_exterieur_m"]
        if d_dep is None or d_joint is None:
            self._missing("deplaceur", "joint_deplaceur", "joint déplaceur cohérent", ["deplaceur.diametre_exterieur_m", "joint_deplaceur.diametre_exterieur_m"], priorite=920)
            return
        # Le joint peut volontairement dépasser selon son squeeze. On ne bloque que si
        # le module joint annonce un diamètre inférieur au déplaceur sans autre donnée.
        if d_joint + self.tolerances.abs_tol_m < d_dep:
            self._add_issue(
                piece_a="deplaceur",
                piece_b="joint_deplaceur",
                regle="joint déplaceur couvre le déplaceur",
                valeur_a=d_dep,
                valeur_b=d_joint,
                attendu="diametre_joint_deplaceur >= diametre_deplaceur",
                ecart=d_dep - d_joint,
                message=f"Le joint de déplaceur ({d_joint * 1000:.3f} mm) est inférieur au déplaceur ({d_dep * 1000:.3f} mm).",
                priorite=75,
                corrections=[AssemblyCorrection("joint_deplaceur", "diametre_exterieur_m", d_dep, "Aligner le joint sur le diamètre du déplaceur validé.")],
            )

    def _check_arbre_clavette(self) -> None:
        if not (_has_piece(self.rapports, "arbre") and _has_piece(self.rapports, "clavette_arbre")):
            return
        arb = self._arbre()
        cla = self._clavette()
        d_arb = arb["diametre_m"]
        d_cla = cla["diametre_arbre_m"]
        if d_arb is not None and d_cla is not None:
            if not math.isclose(d_arb, d_cla, rel_tol=self.tolerances.rel_tol, abs_tol=self.tolerances.abs_tol_m):
                self._add_issue(
                    piece_a="arbre",
                    piece_b="clavette_arbre",
                    regle="clavette calée sur diamètre d'arbre",
                    valeur_a=d_arb,
                    valeur_b=d_cla,
                    attendu="clavette.diametre_arbre_m == arbre.diametre_m",
                    ecart=d_cla - d_arb,
                    message=f"La clavette est définie pour un arbre de {d_cla * 1000:.3f} mm au lieu de {d_arb * 1000:.3f} mm.",
                    priorite=85,
                    corrections=[AssemblyCorrection("clavette_arbre", "diametre_arbre_m", d_arb, "Recalculer la clavette sur l'arbre validé.")],
                )

        L_dispo = arb["longueur_portee_clavette_disponible_m"]
        L_cla = cla["longueur_m"]
        if L_dispo is not None and L_cla is not None and L_cla > L_dispo + self.tolerances.abs_tol_m:
            self._add_issue(
                piece_a="arbre",
                piece_b="clavette_arbre",
                regle="longueur clavette <= portée disponible",
                valeur_a=L_dispo,
                valeur_b=L_cla,
                attendu="longueur_clavette <= longueur_portee_disponible",
                ecart=L_cla - L_dispo,
                message=f"La clavette ({L_cla * 1000:.3f} mm) dépasse la portée disponible ({L_dispo * 1000:.3f} mm).",
                priorite=86,
                corrections=[AssemblyCorrection("clavette_arbre", "longueur_m", L_dispo, "Limiter la clavette à la portée disponible validée.")],
            )

    def _check_fuites_et_frottements_optionnels(self) -> None:
        if self.tolerances.fuite_max_m3_s is None:
            return
        limite = float(self.tolerances.fuite_max_m3_s)
        for piece in ("piston", "joint_piston", "deplaceur", "joint_deplaceur"):
            r = self._r(piece)
            q = _finite_from_paths(r, (
                ("etancheite", "Q_fuite_m3_s"),
                ("pertes", "Q_fuite_m3_s"),
                ("resultats", "Q_fuite_m3_s"),
                ("Q_fuite_m3_s",),
            ))
            if q is not None and q > limite:
                self._add_issue(
                    piece_a=piece,
                    piece_b="etancheite",
                    regle="débit de fuite maximal",
                    valeur_a=limite,
                    valeur_b=q,
                    attendu=f"Q_fuite_m3_s <= {limite}",
                    ecart=q - limite,
                    message=f"Débit de fuite trop élevé sur {piece}: {q:.6g} m³/s > {limite:.6g} m³/s.",
                    gravite="avertissement",
                    bloquant=False,
                    priorite=500,
                )


# =============================================================================
# Fonctions utilitaires publiques
# =============================================================================

def verifier_assemblage_moteur_thermique(
    rapports_pieces: Mapping[str, Any],
    *,
    tolerances: Optional[AssemblyTolerances] = None,
    parametres_courants: Optional[Mapping[str, Any]] = None,
    verifier_pieces_absentes: bool = False,
) -> Dict[str, Any]:
    verif = VerificateurAssemblage(
        rapports_pieces,
        tolerances=tolerances,
        verifier_pieces_absentes=verifier_pieces_absentes,
    )
    return verif.verifier_rapport(parametres_courants=parametres_courants)


def optimiser_assemblage_moteur_thermique(
    parametres_initiaux: Mapping[str, Any],
    callback_dimensionnement: Callable[[Dict[str, Any]], Any],
    *,
    rapports_initiaux: Optional[Mapping[str, Any]] = None,
    tolerances: Optional[AssemblyTolerances] = None,
    max_iterations: int = 5,
    strategie_correction: StrategieCorrection = "conserver_piece_amont",
    verbose: bool = False,
) -> AssemblyOptimizationResult:
    verif = VerificateurAssemblage(
        rapports_initiaux or {},
        tolerances=tolerances,
        strategie_correction=strategie_correction,
    )
    return verif.optimiser_et_relancer(
        dict(parametres_initiaux or {}),
        callback_dimensionnement,
        max_iterations=max_iterations,
        verbose=verbose,
    )


def exporter_rapport_assemblage(resultat: AssemblyOptimizationResult | Dict[str, Any], chemin: str | Path) -> Path:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = resultat.en_dict() if hasattr(resultat, "en_dict") else resultat
    path.write_text(json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


__all__ = [
    "AssemblyTolerances",
    "AssemblyCorrection",
    "AssemblyIssue",
    "AssemblyIteration",
    "AssemblyOptimizationResult",
    "VerificateurAssemblage",
    "normaliser_rapports_pieces",
    "verifier_assemblage_moteur_thermique",
    "optimiser_assemblage_moteur_thermique",
    "exporter_rapport_assemblage",
]

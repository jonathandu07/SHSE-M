"""
frontend/gui/viz_utils.py
===============================================================================
Résolution robuste des modules de visualisation frontend : 2D, 3D, graphiques.
===============================================================================

Rôle :
- charger dynamiquement les modules de visualisation associés aux composants/pièces ;
- respecter l'architecture miroir du backend ;
- accepter les variations de noms historiques : vilebrequin/vilbrequin,
  architecture/architechture, arbre_vilbrequin/arbre_vilebrequin, etc. ;
- produire une Figure Matplotlib si une fonction de dessin existe ;
- tomber proprement sur un fallback générique si aucun module spécialisé n'existe ;
- ne jamais inventer de géométrie ni de donnée technique.

Important :
- ce module ne calcule pas de dimensions physiques ;
- il transmet uniquement piece_obj aux fonctions de visualisation existantes ;
- toute absence de module ou de fonction est diagnostiquée.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import math
import re
import traceback
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


LOGGER = logging.getLogger(__name__)


# =============================================================================
# Types publics
# =============================================================================

VizType = str

VIZ_SKETCHES_2D = "sketches_2d"
VIZ_VIEWS_3D = "views_3d"
VIZ_CHARTS = "charts"

VALID_VIZ_TYPES: Tuple[str, ...] = (
    VIZ_SKETCHES_2D,
    VIZ_VIEWS_3D,
    VIZ_CHARTS,
)


@dataclass(frozen=True)
class VizCandidate:
    path: str
    reason: str = ""


@dataclass
class VizResolution:
    piece_name: str
    piece_key: str
    viz_type: str
    module: Optional[Any] = None
    module_path: Optional[str] = None
    attempted_paths: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
    fallback_used: bool = False

    @property
    def ok(self) -> bool:
        return self.module is not None


@dataclass
class VizFigureResult:
    ok: bool
    figure: Optional[Any] = None
    piece_name: str = ""
    piece_key: str = ""
    viz_type: str = ""
    module_path: Optional[str] = None
    draw_function: Optional[str] = None
    fallback_used: bool = False
    errors: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Normalisation des noms
# =============================================================================

_COMPONENT_KEYS: Tuple[str, ...] = (
    "alternateur",
    "batterie",
    "architechture",
    "architecture",
    "boite_crabots",
    "moteur_electrique",
    "moteur_thermique",
)

_SUBSYSTEM_KEYS: Tuple[str, ...] = (
    "alternateur",
    "batterie",
    "boite_crabots",
    "moteur_electrique",
    "moteur_thermique",
    "architecture",
    "architechture",
)

_ALIASES: Dict[str, str] = {
    # historique orthographe / typo
    "architecture": "architechture",
    "archi": "architechture",
    "architechture": "architechture",

    # vilebrequin / vilbrequin
    "vilebrequin": "vilbrequin",
    "vilbrequin": "vilbrequin",
    "arbre_vilbrequin": "arbre_vilebrequin",
    "arbre_vilebrequin": "arbre_vilebrequin",
    "arbre_vilebrequin": "arbre_vilebrequin",

    # noms collés / variantes
    "arbremoteur": "arbre",
    "arbre_moteur": "arbre",
    "arbre": "arbre",

    # raccourcis pièces moteur thermique
    "couvercle": "couvercle_cylindre",
    "couvercle_cylindre": "couvercle_cylindre",
    "vis_couvercle": "vis_couvercle_cylindre",
    "vis_couvercle_cylindre": "vis_couvercle_cylindre",
    "coussinet": "coussinet_arbre_piston",
    "coussinet_arbre_piston": "coussinet_arbre_piston",
    "bielle": "bielle",
    "corps_bielle": "bielle",
    "joint": "joint_piston",
    "joint_piston": "joint_piston",
    "joint_deplaceur": "joint_deplaceur",
    "déplaceur": "deplaceur",
    "deplaceur": "deplaceur",
    "piston": "piston",
    "cylindre": "cylindre",

    # composants
    "boite": "boite_crabots",
    "boite_crabot": "boite_crabots",
    "boite_crabots": "boite_crabots",
    "moteur_elec": "moteur_electrique",
    "moteur_electrique": "moteur_electrique",
    "moteur_thermique": "moteur_thermique",
}


_VIZ_TYPE_ALIASES: Dict[str, str] = {
    "2d": VIZ_SKETCHES_2D,
    "sketch": VIZ_SKETCHES_2D,
    "sketches": VIZ_SKETCHES_2D,
    "sketches_2d": VIZ_SKETCHES_2D,
    "croquis": VIZ_SKETCHES_2D,
    "croquis_2d": VIZ_SKETCHES_2D,

    "3d": VIZ_VIEWS_3D,
    "view_3d": VIZ_VIEWS_3D,
    "views_3d": VIZ_VIEWS_3D,
    "mesh_3d": VIZ_VIEWS_3D,
    "model_3d": VIZ_VIEWS_3D,
    "modele_3d": VIZ_VIEWS_3D,

    "chart": VIZ_CHARTS,
    "charts": VIZ_CHARTS,
    "graph": VIZ_CHARTS,
    "graphs": VIZ_CHARTS,
    "graphe": VIZ_CHARTS,
    "graphiques": VIZ_CHARTS,
}


def _slugify(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("é", "e").replace("è", "e").replace("ê", "e")
    text = text.replace("à", "a").replace("â", "a")
    text = text.replace("î", "i").replace("ï", "i")
    text = text.replace("ô", "o")
    text = text.replace("ù", "u").replace("û", "u")
    text = text.replace("ç", "c")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _finite_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    return None


def normalize_piece_key(piece_name: Any) -> str:
    key = _slugify(piece_name)
    return _ALIASES.get(key, key)


def normalize_viz_type(viz_type: Any) -> str:
    key = _slugify(viz_type)
    out = _VIZ_TYPE_ALIASES.get(key)
    if out is None:
        raise ValueError(
            f"Type de visualisation inconnu : {viz_type!r}. "
            f"Types acceptés : {', '.join(VALID_VIZ_TYPES)}."
        )
    return out


def infer_piece_name(piece_obj: Any, fallback: str = "piece") -> str:
    """
    Essaie d'extraire un nom stable depuis :
    - dict de rapport ;
    - objet pièce ;
    - dataclass ;
    - attributs usuels.
    """
    if isinstance(piece_obj, Mapping):
        for key in (
            "piece",
            "piece_name",
            "nom_piece",
            "name",
            "nom",
            "type",
            "ref",
            "source_key",
        ):
            value = piece_obj.get(key)
            if value:
                raw = str(value)
                if "." in raw:
                    raw = raw.split(".")[-1]
                return raw

    for attr in (
        "piece",
        "piece_name",
        "nom_piece",
        "name",
        "nom",
        "ref",
    ):
        try:
            value = getattr(piece_obj, attr)
            if value:
                raw = str(value)
                if "." in raw:
                    raw = raw.split(".")[-1]
                return raw
        except Exception:
            pass

    if piece_obj is not None:
        cls_name = type(piece_obj).__name__
        if cls_name and cls_name != "dict":
            return cls_name

    return fallback


def infer_subsystem(piece_obj: Any) -> Optional[str]:
    """
    Déduit un sous-système si le rapport ou l'objet l'indique.
    Ne devine pas depuis des valeurs physiques.
    """
    if isinstance(piece_obj, Mapping):
        for key in (
            "subsystem",
            "sous_systeme",
            "component",
            "composant",
            "source_composant",
            "module",
            "famille",
        ):
            value = piece_obj.get(key)
            if value:
                return normalize_piece_key(value)

        ref = piece_obj.get("ref")
        if isinstance(ref, str) and "." in ref:
            parts = [normalize_piece_key(p) for p in ref.split(".") if p]
            for p in parts:
                if p in _SUBSYSTEM_KEYS:
                    return p

    for attr in (
        "subsystem",
        "sous_systeme",
        "component",
        "composant",
        "source_composant",
        "module",
        "famille",
    ):
        try:
            value = getattr(piece_obj, attr)
            if value:
                return normalize_piece_key(value)
        except Exception:
            pass

    return None


# =============================================================================
# Génération des chemins candidats
# =============================================================================

def _viz_module_name_variants(viz_type: str) -> Tuple[str, ...]:
    vt = normalize_viz_type(viz_type)

    if vt == VIZ_SKETCHES_2D:
        return (
            "sketches_2d",
            "croquis_2d",
            "sketch_2d",
            "drawing_2d",
            "views_2d",
        )

    if vt == VIZ_VIEWS_3D:
        return (
            "views_3d",
            "mesh_3d",
            "model_3d",
            "modele_3d",
            "solid_3d",
        )

    if vt == VIZ_CHARTS:
        return (
            "charts",
            "chart",
            "graphs",
            "graphiques",
            "plots",
        )

    return (vt,)


def _alternate_piece_keys(piece_key: str) -> Tuple[str, ...]:
    keys: List[str] = [piece_key]

    reverse_aliases = [k for k, v in _ALIASES.items() if v == piece_key]
    keys.extend(reverse_aliases)

    # variantes historiques ciblées
    if "vilebrequin" in piece_key:
        keys.append(piece_key.replace("vilebrequin", "vilbrequin"))
    if "vilbrequin" in piece_key:
        keys.append(piece_key.replace("vilbrequin", "vilebrequin"))

    if piece_key == "architechture":
        keys.append("architecture")
    if piece_key == "architecture":
        keys.append("architechture")

    # déduplication stable
    out: List[str] = []
    seen = set()
    for key in keys:
        k = normalize_piece_key(key)
        if k not in seen:
            seen.add(k)
            out.append(k)
    return tuple(out)


def build_viz_module_candidates(
    piece_name: Any,
    viz_type: Any,
    *,
    subsystem: Optional[str] = None,
) -> List[VizCandidate]:
    """
    Construit les chemins de modules possibles, du plus spécifique au plus générique.
    """
    vt = normalize_viz_type(viz_type)
    piece_key = normalize_piece_key(piece_name)
    subsystem_key = normalize_piece_key(subsystem) if subsystem else None

    module_names = _viz_module_name_variants(vt)
    piece_keys = _alternate_piece_keys(piece_key)

    candidates: List[VizCandidate] = []

    def add(path: str, reason: str) -> None:
        candidates.append(VizCandidate(path=path, reason=reason))

    # 1) Si la ressource est un composant complet.
    for pk in piece_keys:
        if pk in _COMPONENT_KEYS:
            for mod_name in module_names:
                add(f"frontend.components.{pk}.{mod_name}", "composant direct")

    # 2) Si un sous-système est fourni : chercher dans ses pièces.
    if subsystem_key:
        subsystem_variants = _alternate_piece_keys(subsystem_key)
        for ss in subsystem_variants:
            for pk in piece_keys:
                for mod_name in module_names:
                    add(
                        f"frontend.components.{ss}.pieces.{pk}.{mod_name}",
                        "pièce dans sous-système explicite",
                    )
                    add(
                        f"frontend.components.{ss}.{pk}.{mod_name}",
                        "module direct dans sous-système explicite",
                    )

    # 3) Chemin historique prioritaire : pièces moteur thermique.
    for pk in piece_keys:
        for mod_name in module_names:
            add(
                f"frontend.components.moteur_thermique.pieces.{pk}.{mod_name}",
                "pièce moteur thermique historique",
            )

    # 4) Recherche miroir dans tous les sous-systèmes connus.
    for ss in _SUBSYSTEM_KEYS:
        for pk in piece_keys:
            for mod_name in module_names:
                add(
                    f"frontend.components.{ss}.pieces.{pk}.{mod_name}",
                    "pièce dans sous-système connu",
                )

    # 5) Modules génériques par sous-système.
    for pk in piece_keys:
        for ss in _SUBSYSTEM_KEYS:
            for mod_name in module_names:
                add(
                    f"frontend.components.{ss}.{pk}.{mod_name}",
                    "module direct sous-système connu",
                )

    # 6) Fallbacks frontend ensemble.
    if vt == VIZ_SKETCHES_2D:
        add("frontend.ensemble.viz_2d_generic", "fallback générique 2D")
    elif vt == VIZ_VIEWS_3D:
        add("frontend.ensemble.viz_3d_generic", "fallback générique 3D")
    elif vt == VIZ_CHARTS:
        add("frontend.ensemble.viz_radar_template", "fallback générique chart")

    # Déduplication stable.
    out: List[VizCandidate] = []
    seen = set()
    for cand in candidates:
        if cand.path in seen:
            continue
        seen.add(cand.path)
        out.append(cand)

    return out


# =============================================================================
# Import robuste
# =============================================================================

@lru_cache(maxsize=1024)
def _try_import_module_cached(path: str) -> Tuple[Optional[Any], Optional[str]]:
    try:
        return importlib.import_module(path), None
    except ImportError as exc:
        return None, str(exc)
    except Exception as exc:
        details = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        return None, details


def resolve_viz_module_detailed(
    piece_name: Any,
    viz_type: Any,
    *,
    subsystem: Optional[str] = None,
    include_generic_fallback: bool = True,
) -> VizResolution:
    vt = normalize_viz_type(viz_type)
    piece_key = normalize_piece_key(piece_name)

    result = VizResolution(
        piece_name=str(piece_name),
        piece_key=piece_key,
        viz_type=vt,
    )

    candidates = build_viz_module_candidates(
        piece_name=piece_name,
        viz_type=vt,
        subsystem=subsystem,
    )

    for cand in candidates:
        if not include_generic_fallback and "frontend.ensemble." in cand.path:
            continue

        result.attempted_paths.append(cand.path)

        module, error = _try_import_module_cached(cand.path)
        if module is not None:
            result.module = module
            result.module_path = cand.path
            result.fallback_used = "frontend.ensemble." in cand.path
            return result

        if error:
            result.errors[cand.path] = error

    return result


def resolve_viz_module(
    piece_name: Any,
    viz_type: Any,
    *,
    subsystem: Optional[str] = None,
) -> Optional[Any]:
    """
    API historique conservée.
    Retourne seulement le module, ou None.
    """
    resolution = resolve_viz_module_detailed(
        piece_name=piece_name,
        viz_type=viz_type,
        subsystem=subsystem,
    )
    if not resolution.ok:
        LOGGER.debug(
            "Aucun module viz trouvé pour %s / %s. Chemins testés: %s",
            piece_name,
            viz_type,
            resolution.attempted_paths,
        )
    return resolution.module


# =============================================================================
# Résolution des fonctions de dessin
# =============================================================================

def _callable_name(fn: Callable[..., Any]) -> str:
    return getattr(fn, "__name__", type(fn).__name__)


def _find_first_callable(module: Any, names: Sequence[str]) -> Optional[Callable[..., Any]]:
    if module is None:
        return None

    for name in names:
        value = getattr(module, name, None)
        if callable(value):
            return value

    return None


def _find_sketch_callable(module: Any) -> Optional[Callable[..., Any]]:
    fn = _find_first_callable(
        module,
        (
            "draw",
            "dessiner",
            "make_figure",
            "build_figure",
            "create_figure",
            "plot",
            "render",
        ),
    )
    if fn:
        return fn

    if module is not None:
        for attr in dir(module):
            if attr.startswith("tracer_croquis_") and attr.endswith("_2d"):
                value = getattr(module, attr, None)
                if callable(value):
                    return value

        for attr in dir(module):
            if attr.startswith(("draw_", "plot_", "make_")):
                value = getattr(module, attr, None)
                if callable(value):
                    return value

    return None


def _find_3d_callable(module: Any) -> Optional[Callable[..., Any]]:
    return _find_first_callable(
        module,
        (
            "draw_3d",
            "draw",
            "dessiner_3d",
            "make_figure",
            "build_figure",
            "create_figure",
            "render",
        ),
    )


def _find_chart_callable(module: Any) -> Optional[Callable[..., Any]]:
    return _find_first_callable(
        module,
        (
            "plot_data",
            "plot",
            "draw",
            "make_figure",
            "build_figure",
            "create_figure",
            "render",
        ),
    )


def _function_accepts(fn: Callable[..., Any], name: str) -> bool:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return True

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return True

    return name in sig.parameters


def _function_positional_count(fn: Callable[..., Any]) -> Tuple[int, bool]:
    """
    Retourne (nombre de paramètres positionnels requis, accepte *args).
    """
    try:
        sig = inspect.signature(fn)
    except Exception:
        return 0, True

    required = 0
    accepts_varargs = False

    for p in sig.parameters.values():
        if p.kind == inspect.Parameter.VAR_POSITIONAL:
            accepts_varargs = True
            continue

        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            if p.default is inspect.Parameter.empty:
                required += 1

    return required, accepts_varargs


# =============================================================================
# Création des figures
# =============================================================================

def _import_pyplot() -> Any:
    """
    Import différé pour éviter de charger Matplotlib au démarrage de l'app Kivy.
    """
    import matplotlib.pyplot as plt

    return plt


def _ensure_figure_from_result(result: Any) -> Optional[Any]:
    """
    Certaines fonctions retournent :
    - fig ;
    - (fig, ax) ;
    - ax ;
    - None.
    """
    if result is None:
        return None

    # (fig, ax) ou [fig, ax]
    if isinstance(result, (tuple, list)) and result:
        return _ensure_figure_from_result(result[0])

    # Matplotlib Figure
    if hasattr(result, "savefig") and hasattr(result, "axes"):
        return result

    # Matplotlib Axes
    fig = getattr(result, "figure", None)
    if fig is not None and hasattr(fig, "savefig"):
        return fig

    return None


def _call_sketch_function(fn: Callable[..., Any], piece_obj: Any) -> Optional[Any]:
    """
    Appelle une fonction 2D selon sa signature.
    """
    plt = _import_pyplot()

    # Fonctions qui créent elles-mêmes la figure.
    if _function_accepts(fn, "afficher"):
        res = fn(piece_obj, afficher=False)
        return _ensure_figure_from_result(res)

    if _function_accepts(fn, "show"):
        res = fn(piece_obj, show=False)
        return _ensure_figure_from_result(res)

    required_count, accepts_varargs = _function_positional_count(fn)

    if required_count <= 1 and not accepts_varargs:
        res = fn(piece_obj)
        fig = _ensure_figure_from_result(res)
        if fig is not None:
            return fig

    # Fonctions type draw(ax, piece_obj)
    fig, ax = plt.subplots(figsize=(6, 6))
    try:
        if accepts_varargs or required_count >= 2:
            res = fn(ax, piece_obj)
        else:
            res = fn(piece_obj)

        fig_from_res = _ensure_figure_from_result(res)
        return fig_from_res or fig
    except Exception:
        plt.close(fig)
        raise


def _call_3d_function(fn: Callable[..., Any], piece_obj: Any) -> Optional[Any]:
    plt = _import_pyplot()
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    required_count, accepts_varargs = _function_positional_count(fn)

    # Fonctions qui créent elles-mêmes la figure.
    if required_count <= 1 and not accepts_varargs:
        res = fn(piece_obj)
        fig = _ensure_figure_from_result(res)
        if fig is not None:
            return fig

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="3d")

    try:
        res = fn(ax, piece_obj)
        fig_from_res = _ensure_figure_from_result(res)
        return fig_from_res or fig
    except Exception:
        plt.close(fig)
        raise


def _call_chart_function(fn: Callable[..., Any], piece_obj: Any) -> Optional[Any]:
    plt = _import_pyplot()

    required_count, accepts_varargs = _function_positional_count(fn)

    # Fonctions autonomes.
    if required_count <= 1 and not accepts_varargs:
        res = fn(piece_obj)
        fig = _ensure_figure_from_result(res)
        if fig is not None:
            return fig

    # Par défaut : radar/polar, cohérent avec ton fallback historique.
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, polar=True)

    try:
        res = fn(ax, piece_obj)
        fig_from_res = _ensure_figure_from_result(res)
        return fig_from_res or fig
    except Exception:
        plt.close(fig)
        raise


def _fallback_module_for(viz_type: str) -> Optional[Any]:
    vt = normalize_viz_type(viz_type)

    fallback_paths = {
        VIZ_SKETCHES_2D: "frontend.ensemble.viz_2d_generic",
        VIZ_VIEWS_3D: "frontend.ensemble.viz_3d_generic",
        VIZ_CHARTS: "frontend.ensemble.viz_radar_template",
    }

    path = fallback_paths.get(vt)
    if not path:
        return None

    module, error = _try_import_module_cached(path)
    if module is None and error:
        LOGGER.debug("Fallback indisponible %s : %s", path, error)
    return module


def _unavailable_figure(piece_name: Any, viz_type: str, reason: str) -> Any:
    """Figure d'etat vide : elle ne dessine aucune geometrie metier."""
    plt = _import_pyplot()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.axis("off")
    ax.text(
        0.5,
        0.55,
        "Visualisation indisponible",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
    )
    ax.text(
        0.5,
        0.38,
        f"{piece_name} - {viz_type}\n{reason}",
        ha="center",
        va="center",
        fontsize=9,
        wrap=True,
    )
    fig.tight_layout()
    return fig


def get_draw_3d_func(piece_name: Any, *, subsystem: Optional[str] = None) -> Callable[..., Any]:
    """
    API historique conservée.
    Retourne une fonction compatible draw_3d(ax, piece_obj) si possible.
    """
    resolution = resolve_viz_module_detailed(
        piece_name=piece_name,
        viz_type=VIZ_VIEWS_3D,
        subsystem=subsystem,
    )

    fn = _find_3d_callable(resolution.module)
    if fn:
        return fn

    fallback = _fallback_module_for(VIZ_VIEWS_3D)
    fn = _find_3d_callable(fallback)
    if fn:
        return fn

    def _noop(ax: Any, p: Any) -> None:
        return None

    return _noop


def get_viz_figure_result(
    piece_name: Any,
    piece_obj: Any,
    viz_type: Any,
    *,
    subsystem: Optional[str] = None,
    allow_fallback: bool = True,
) -> VizFigureResult:
    """
    Version détaillée : retourne la figure + diagnostics.
    """
    vt = normalize_viz_type(viz_type)
    piece_key = normalize_piece_key(piece_name)

    result = VizFigureResult(
        ok=False,
        piece_name=str(piece_name),
        piece_key=piece_key,
        viz_type=vt,
    )

    resolution = resolve_viz_module_detailed(
        piece_name=piece_name,
        viz_type=vt,
        subsystem=subsystem,
        include_generic_fallback=allow_fallback,
    )

    result.module_path = resolution.module_path
    result.fallback_used = resolution.fallback_used
    result.diagnostics["attempted_paths"] = resolution.attempted_paths
    result.diagnostics["resolution_errors"] = resolution.errors

    module = resolution.module

    if module is None and allow_fallback:
        module = _fallback_module_for(vt)
        result.fallback_used = True

    if module is None:
        result.errors.append("Aucun module de visualisation disponible.")
        return result

    try:
        if vt == VIZ_SKETCHES_2D:
            fn = _find_sketch_callable(module)
            if fn is None:
                result.errors.append("Aucune fonction 2D compatible trouvée.")
                return result

            result.draw_function = _callable_name(fn)
            fig = _call_sketch_function(fn, piece_obj)

        elif vt == VIZ_VIEWS_3D:
            fn = _find_3d_callable(module)
            if fn is None:
                result.errors.append("Aucune fonction 3D compatible trouvée.")
                return result

            result.draw_function = _callable_name(fn)
            fig = _call_3d_function(fn, piece_obj)

        elif vt == VIZ_CHARTS:
            fn = _find_chart_callable(module)
            if fn is None:
                result.errors.append("Aucune fonction graphique compatible trouvée.")
                return result

            result.draw_function = _callable_name(fn)
            fig = _call_chart_function(fn, piece_obj)

        else:
            result.errors.append(f"Type de visualisation non supporté : {vt}")
            return result

        result.figure = fig
        result.ok = fig is not None

        if fig is None:
            result.errors.append("La fonction appelée n'a pas retourné de Figure Matplotlib exploitable.")

        return result

    except Exception as exc:
        result.errors.append(f"{type(exc).__name__}: {exc}")
        result.diagnostics["traceback"] = traceback.format_exc(limit=8)
        if allow_fallback:
            result.figure = _unavailable_figure(piece_name, vt, str(exc))
            result.ok = True
            result.fallback_used = True
            result.diagnostics["unavailable_state"] = True

        LOGGER.warning(
            "Erreur get_viz_figure_result(piece=%s, type=%s, module=%s): %s",
            piece_name,
            vt,
            result.module_path,
            exc,
        )
        return result


def get_viz_figure(
    piece_name: Any,
    piece_obj: Any,
    viz_type: Any,
    *,
    subsystem: Optional[str] = None,
    allow_fallback: bool = True,
) -> Optional[Any]:
    """
    API historique conservée.
    Retourne uniquement la Figure Matplotlib ou None.
    """
    res = get_viz_figure_result(
        piece_name=piece_name,
        piece_obj=piece_obj,
        viz_type=viz_type,
        subsystem=subsystem,
        allow_fallback=allow_fallback,
    )
    return res.figure if res.ok else None


def backend_graph_to_figure(graph: Mapping[str, Any]) -> Optional[Any]:
    """
    Rend un graphique mécanique fourni par le backend.
    Ne génère aucun point : seules les séries et markers présents dans le JSON
    backend sont affichés.
    """
    if not isinstance(graph, Mapping):
        return None

    plt = _import_pyplot()
    fig, ax = plt.subplots(figsize=(7, 4.5))

    title = str(graph.get("title") or graph.get("id") or "Graphique backend")
    ax.set_title(title)
    ax.set_xlabel(str(graph.get("x_label") or ""))
    ax.set_ylabel(str(graph.get("y_label") or ""))

    series = graph.get("series", [])
    plotted = False
    if isinstance(series, list):
        for serie in series:
            if not isinstance(serie, Mapping):
                continue
            points = serie.get("points", [])
            if not isinstance(points, list):
                continue
            xs: list[float] = []
            ys: list[float] = []
            for point in points:
                if not isinstance(point, Mapping):
                    continue
                x = _finite_float(point.get("x"))
                y = _finite_float(point.get("y"))
                if x is None or y is None:
                    continue
                xs.append(x)
                ys.append(y)
            if xs and ys:
                ax.plot(xs, ys, label=str(serie.get("name") or "serie"))
                plotted = True

    markers = graph.get("markers", [])
    if isinstance(markers, list):
        for marker in markers:
            if not isinstance(marker, Mapping):
                continue
            x = _finite_float(marker.get("x"))
            y = _finite_float(marker.get("y"))
            if x is None or y is None:
                continue
            label = str(marker.get("name") or "marker")
            ax.scatter([x], [y], marker="o")
            ax.annotate(label, (x, y), fontsize=8)
            plotted = True

    if plotted:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    else:
        status = str(graph.get("status") or "missing_required")
        missing = graph.get("missing", [])
        missing_text = ", ".join(str(x) for x in missing) if isinstance(missing, list) else ""
        ax.axis("off")
        ax.text(
            0.5,
            0.55,
            f"Graphique {status}",
            ha="center",
            va="center",
            fontsize=12,
            fontweight="bold",
        )
        ax.text(
            0.5,
            0.38,
            missing_text or "Aucune série backend disponible.",
            ha="center",
            va="center",
            fontsize=9,
            wrap=True,
        )

    interpretation = graph.get("interpretation")
    if interpretation:
        fig.text(0.02, 0.01, str(interpretation), fontsize=8, ha="left", va="bottom", wrap=True)

    fig.tight_layout()
    return fig


def backend_graphs_available(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Retourne les graphes backend affichables sans les modifier."""
    graphs = payload.get("graphiques", []) if isinstance(payload, Mapping) else []
    return [dict(graph) for graph in graphs if isinstance(graph, Mapping)]


# =============================================================================
# Fonctions utilitaires pour l'UI
# =============================================================================

def available_visualizations(
    piece_name: Any,
    piece_obj: Any = None,
    *,
    subsystem: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Indique quelles visualisations semblent disponibles.
    Ne crée pas les figures, se limite à résoudre les modules/fonctions.
    """
    out: Dict[str, Dict[str, Any]] = {}

    for vt in VALID_VIZ_TYPES:
        resolution = resolve_viz_module_detailed(
            piece_name=piece_name,
            viz_type=vt,
            subsystem=subsystem,
        )

        module = resolution.module
        fn: Optional[Callable[..., Any]]

        if vt == VIZ_SKETCHES_2D:
            fn = _find_sketch_callable(module)
        elif vt == VIZ_VIEWS_3D:
            fn = _find_3d_callable(module)
        else:
            fn = _find_chart_callable(module)

        out[vt] = {
            "available": fn is not None,
            "module_path": resolution.module_path,
            "function": _callable_name(fn) if fn else None,
            "fallback_used": resolution.fallback_used,
            "attempted_paths": resolution.attempted_paths,
        }

    return out


def save_viz_figure(
    piece_name: Any,
    piece_obj: Any,
    viz_type: Any,
    output_path: str | Path,
    *,
    subsystem: Optional[str] = None,
    dpi: int = 160,
    allow_fallback: bool = True,
) -> Dict[str, Any]:
    """
    Génère puis sauvegarde une figure.
    Ne crée aucune donnée technique, seulement un rendu de ce qui existe.
    """
    res = get_viz_figure_result(
        piece_name=piece_name,
        piece_obj=piece_obj,
        viz_type=viz_type,
        subsystem=subsystem,
        allow_fallback=allow_fallback,
    )

    path = Path(output_path)

    if not res.ok or res.figure is None:
        return {
            "ok": False,
            "path": str(path),
            "errors": res.errors,
            "diagnostics": res.diagnostics,
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    res.figure.savefig(path, dpi=dpi, bbox_inches="tight")

    return {
        "ok": True,
        "path": str(path),
        "piece_name": res.piece_name,
        "piece_key": res.piece_key,
        "viz_type": res.viz_type,
        "module_path": res.module_path,
        "draw_function": res.draw_function,
        "fallback_used": res.fallback_used,
    }


def figure_to_png_bytes(
    figure: Any,
    *,
    dpi: int = 160,
) -> Optional[bytes]:
    """
    Convertit une Figure Matplotlib en bytes PNG.
    Utile pour intégration Kivy texture/image.
    """
    if figure is None or not hasattr(figure, "savefig"):
        return None

    from io import BytesIO

    buf = BytesIO()
    figure.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    return buf.getvalue()


def close_figure(figure: Any) -> None:
    """
    Ferme proprement une figure Matplotlib pour éviter les fuites mémoire.
    """
    if figure is None:
        return

    try:
        plt = _import_pyplot()
        plt.close(figure)
    except Exception:
        pass


def clear_viz_import_cache() -> None:
    """
    Vide le cache d'import.
    Utile en développement si Codex/Antigravity génère de nouveaux modules
    pendant que l'app est ouverte.
    """
    _try_import_module_cached.cache_clear()

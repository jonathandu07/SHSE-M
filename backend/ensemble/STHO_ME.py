# backend\ensemble\STHO_ME.py
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# =============================================================================
# Préparation du chemin projet
# =============================================================================

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent

# Cas nominal : fichier placé dans backend/ensemble/STHO_ME.py
# Fallback : fichier exécuté seul ailleurs.
for candidate in (
    _THIS_DIR,
    _THIS_DIR.parent,
    _THIS_DIR.parent.parent,
    Path.cwd(),
):
    if str(candidate) not in sys.path:
        sys.path.append(str(candidate))


# =============================================================================
# Imports robustes des composants / pièces
# =============================================================================


def _import_attr(module_names: Sequence[str], attr: str) -> Any:
    last_error: Optional[Exception] = None
    for module_name in module_names:
        try:
            module = __import__(module_name, fromlist=[attr])
            return getattr(module, attr)
        except Exception as exc:  # pragma: no cover - robustesse runtime
            last_error = exc
            continue
    if last_error is None:
        raise ImportError(f"Impossible d'importer {attr}.")
    raise ImportError(f"Impossible d'importer {attr} : {last_error}") from last_error


# Composants
SystemeComplet = _import_attr(
    ("backend.ensemble.systeme_complet", "systeme_complet"),
    "SystemeComplet",
)
MoteurElectrique = _import_attr(
    ("backend.components.moteur_electrique", "moteur_electrique"),
    "MoteurElectrique",
)
Batterie = _import_attr(
    ("backend.components.batterie", "batterie"),
    "Batterie",
)
Alternateur = _import_attr(
    ("backend.components.alternateur", "alternateur"),
    "Alternateur",
)
MoteurThermique = _import_attr(
    ("backend.components.moteur_thermique", "moteur_thermique"),
    "MoteurThermique",
)
BoiteCrabots = _import_attr(
    ("backend.components.boite_crabots", "boite_crabots"),
    "BoiteCrabots",
)
Architecture = _import_attr(
    ("backend.components.architecture", "architecture"),
    "Architecture",
)

# Pièces
Cylindre = _import_attr(("backend.components.moteur_thermique.pieces.cylindre", "cylindre"), "Cylindre")
Piston = _import_attr(("backend.components.moteur_thermique.pieces.piston", "piston"), "Piston")
JointPiston = _import_attr(("backend.components.moteur_thermique.pieces.joint_piston", "joint_piston"), "JointPiston")
CorpsBielle = _import_attr(("backend.components.moteur_thermique.pieces.bielle", "bielle"), "CorpsBielle")
ArbrePiston = _import_attr(("backend.components.moteur_thermique.pieces.arbre_piston", "arbre_piston"), "ArbrePiston")
CoussinetArbrePiston = _import_attr(
    ("backend.components.moteur_thermique.pieces.coussinet_arbre_piston", "coussinet_arbre_piston"),
    "CoussinetArbrePiston",
)
ArbreVilbrequin = _import_attr(
    ("backend.components.moteur_thermique.pieces.arbre_vilbrequin", "arbre_vilbrequin"),
    "ArbreVilbrequin",
)
Vilbrequin = _import_attr(("backend.components.moteur_thermique.pieces.vilbrequin", "vilbrequin"), "Vilbrequin")
RoulementAiguilleArbre = _import_attr(
    ("backend.components.moteur_thermique.pieces.roulement_aiguille_arbre", "roulement_aiguille_arbre"),
    "RoulementAiguilleArbre",
)
RoulementAiguilleArbreVilebrequin = _import_attr(
    ("backend.components.moteur_thermique.pieces.roulement_aiguille_arbre_vilebrequin", "roulement_aiguille_arbre_vilebrequin"),
    "RoulementAiguilleArbreVilebrequin",
)
CouvercleCylindre = _import_attr(
    ("backend.components.moteur_thermique.pieces.couvercle_cylindre", "couvercle_cylindre"),
    "CouvercleCylindre",
)
VisCouvercleCylindre = _import_attr(
    ("backend.components.moteur_thermique.pieces.vis_couvercle_cylindre", "vis_couvercle_cylindre"),
    "VisCouvercleCylindre",
)
Deplaceur = _import_attr(("backend.components.moteur_thermique.pieces.deplaceur", "deplaceur"), "Deplaceur")
JointDeplaceur = _import_attr(
    ("backend.components.moteur_thermique.pieces.joint_deplaceur", "joint_deplaceur"),
    "JointDeplaceur",
)
ArbreMoteur = _import_attr(("backend.components.moteur_thermique.pieces.arbre", "arbre"), "ArbreMoteur")


# =============================================================================
# Helpers généraux
# =============================================================================


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))



def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None



def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    if _is_finite(x):
        return int(float(x))
    return None



def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}



def _deep_get(x: Any, *path: str) -> Any:
    cur = x
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
        if cur is None:
            return None
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



def _serialize_minimal(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, dict):
        return {k: _serialize_minimal(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_serialize_minimal(v) for v in x]
    if is_dataclass(x):
        return asdict(x)
    if hasattr(x, "en_dict") and callable(getattr(x, "en_dict")):
        try:
            return x.en_dict()
        except Exception:
            pass
    return {"type": type(x).__name__}



def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append(
        {"nom": str(nom), "raison": str(raison)}
    )



def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for categorie in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out: List[Dict[str, str]] = []
        for item in list(inc.get(categorie, []) or []):
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append({"nom": key[0], "raison": key[1]})
        inc[categorie] = out



def _merge_inconnues(dst: Dict[str, Any], src_report: Optional[Dict[str, Any]], *, prefix: str) -> None:
    if not isinstance(src_report, dict):
        return
    inc = src_report.get("inconnues", {})
    for categorie in ("impossibles", "partielles"):
        for item in list(_safe_dict(inc).get(categorie, []) or []):
            _push_inconnue(
                dst,
                categorie,
                f"{prefix} :: {item.get('nom', '')}",
                str(item.get("raison", "")),
            )



def _add_note(rapport: Dict[str, Any], note: str) -> None:
    rapport.setdefault("notes_modele", []).append(str(note))



def _safe_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for method_name in ("analyser", "calculer"):
        fn = getattr(obj, method_name, None)
        if callable(fn):
            try:
                out = fn(strict=False)
                return out if isinstance(out, dict) else None
            except TypeError:
                try:
                    out = fn()
                    return out if isinstance(out, dict) else None
                except Exception:
                    continue
            except Exception:
                continue
    return None



def _run_named_analysis(obj: Any, method_name: str, kwargs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    fn = getattr(obj, method_name, None)
    if not callable(fn):
        return None
    out = fn(**dict(kwargs))
    return out if isinstance(out, dict) else {"resultat": out}



def _instantiate_or_passthrough(
    cls: Any,
    payload: Any,
    *,
    rapport: Dict[str, Any],
    nom: str,
) -> Any:
    if payload is None:
        return None
    if isinstance(payload, cls):
        return payload
    if isinstance(payload, dict):
        try:
            return cls(**payload)
        except Exception as exc:
            _push_inconnue(
                rapport,
                "impossibles",
                f"construction {nom}",
                f"Instantiation impossible avec les paramètres fournis : {exc}",
            )
            return None
    return payload



def _context_moteur(systeme_report: Optional[Dict[str, Any]], moteur_thermique: Any) -> Dict[str, Any]:
    synth_mt = _safe_dict(_deep_get(systeme_report, "synthese", "moteur_thermique"))
    return {
        "alesage_m": _first_finite(
            synth_mt.get("alesage_m"),
            getattr(moteur_thermique, "alesage_m", None),
        ),
        "course_m": _first_finite(
            synth_mt.get("course_m"),
            getattr(moteur_thermique, "course_m", None),
        ),
        "pression_max_pa": _first_finite(
            synth_mt.get("pression_max_pa"),
            getattr(moteur_thermique, "pression_max_pa", None),
        ),
        "pme_pa": _first_finite(
            synth_mt.get("pme_pa"),
            getattr(moteur_thermique, "pression_moyenne_effective_pa", None),
        ),
        "rpm_nominal": _first_finite(
            synth_mt.get("rpm_nominal"),
            getattr(moteur_thermique, "rpm_nominal", None),
        ),
        "nombre_cylindres": _safe_int(
            _first_non_none(
                synth_mt.get("nombre_cylindres"),
                getattr(moteur_thermique, "nombre_cylindres", None),
            )
        ),
        "architecture": _first_non_none(
            synth_mt.get("architecture"),
            getattr(moteur_thermique, "architecture", None),
        ),
    }


# =============================================================================
# Cartographie des sous-ensembles
# =============================================================================


COMPONENT_CLASSES: Dict[str, Any] = {
    "moteur_electrique": MoteurElectrique,
    "batterie": Batterie,
    "alternateur": Alternateur,
    "moteur_thermique": MoteurThermique,
    "boite_crabots": BoiteCrabots,
    "architecture": Architecture,
}

PIECE_CLASSES: Dict[str, Any] = {
    "cylindre": Cylindre,
    "piston": Piston,
    "joint_piston": JointPiston,
    "bielle": CorpsBielle,
    "arbre_piston": ArbrePiston,
    "coussinet_arbre_piston": CoussinetArbrePiston,
    "arbre_vilebrequin": ArbreVilbrequin,
    "vilbrequin": Vilbrequin,
    "roulement_aiguille_arbre": RoulementAiguilleArbre,
    "roulement_aiguille_arbre_vilebrequin": RoulementAiguilleArbreVilebrequin,
    "couvercle_cylindre": CouvercleCylindre,
    "vis_couvercle_cylindre": VisCouvercleCylindre,
    "deplaceur": Deplaceur,
    "joint_deplaceur": JointDeplaceur,
    "arbre": ArbreMoteur,
}

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
)

PIECE_DEPENDENCIES: Dict[str, Dict[str, str]] = {
    "piston": {"cylindre": "cylindre"},
    "joint_piston": {"piston": "piston", "cylindre": "cylindre"},
    "arbre_piston": {"piston": "piston", "bielle": "bielle", "cylindre": "cylindre"},
    "bielle": {
        "piston": "piston",
        "arbre_piston": "arbre_piston",
        "cylindre": "cylindre",
        "moteur_thermique": "moteur_thermique",
    },
    "coussinet_arbre_piston": {"arbre_piston": "arbre_piston"},
    "couvercle_cylindre": {"cylindre": "cylindre"},
    "vis_couvercle_cylindre": {"cylindre": "cylindre", "couvercle": "couvercle_cylindre"},
    "deplaceur": {"cylindre": "cylindre"},
    "joint_deplaceur": {"deplaceur": "deplaceur", "cylindre": "cylindre"},
    "arbre_vilebrequin": {
        "cylindre": "cylindre",
        "piston": "piston",
        "bielle": "bielle",
        "moteur_thermique": "moteur_thermique",
        "roulement_aiguille": "roulement_aiguille_arbre",
    },
    "vilbrequin": {
        "arbre": "arbre_vilebrequin",
        "cylindre": "cylindre",
        "piston": "piston",
        "bielle": "bielle",
        "deplaceur": "deplaceur",
        "systeme_complet": "systeme_complet_obj",
        "moteur_thermique": "moteur_thermique",
    },
    "roulement_aiguille_arbre": {
        "vilbrequin": "vilbrequin",
        "arbre_vilbrequin": "arbre_vilebrequin",
        "bielle": "bielle",
        "piston": "piston",
        "cylindre": "cylindre",
    },
    "roulement_aiguille_arbre_vilebrequin": {
        "corps_bielle": "bielle",
        "arbre_vilebrequin": "arbre_vilebrequin",
        "moteur_thermique": "moteur_thermique",
    },
    "arbre": {
        "cylindre": "cylindre",
        "moteur_thermique": "moteur_thermique",
        "systeme_complet": "systeme_complet_obj",
        "vilbrequin": "vilbrequin",
        "roulement_aiguille": "roulement_aiguille_arbre",
    },
}


# =============================================================================
# Orchestrateur principal
# =============================================================================


@dataclass
class STHO_ME:
    """
    Orchestrateur haut niveau pour la conception du système STHO-ME.

    Philosophie :
    - ne rien inventer ;
    - construire les composants uniquement à partir des paramètres fournis ;
    - réinjecter uniquement les valeurs déjà calculées par le système global ;
    - analyser chaque brique et agréger les inconnues restantes.
    """

    composants: Dict[str, Any] = field(default_factory=dict)
    pieces: Dict[str, Any] = field(default_factory=dict)
    analyses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    composants_obj: Dict[str, Any] = field(default_factory=dict, init=False)
    pieces_obj: Dict[str, Any] = field(default_factory=dict, init=False)
    systeme_complet_obj: Optional[Any] = field(default=None, init=False)
    rapport_definition_moteur_thermique: Optional[Dict[str, Any]] = field(default=None, init=False)

    # ---------------------------------------------------------------------
    # Construction des composants
    # ---------------------------------------------------------------------
    def _build_components(self, rapport: Dict[str, Any]) -> None:
        rapport.setdefault("construction", {}).setdefault("composants", {})

        for name, cls in COMPONENT_CLASSES.items():
            payload = self.composants.get(name)
            obj = _instantiate_or_passthrough(cls, payload, rapport=rapport, nom=name)
            if obj is not None:
                self.composants_obj[name] = obj
                rapport["construction"]["composants"][name] = {
                    "type": type(obj).__name__,
                    "source": "objet" if not isinstance(payload, dict) else "dict",
                }

        if self.composants_obj.get("moteur_thermique") is None:
            definition = self.analyses.get("moteur_thermique_definition")
            if definition:
                try:
                    rep_def = MoteurThermique.definir_depuis_exigences(**definition)
                    self.rapport_definition_moteur_thermique = rep_def if isinstance(rep_def, dict) else None
                    moteur_defini = _deep_get(rep_def, "moteur_defini")
                    if moteur_defini is not None:
                        self.composants_obj["moteur_thermique"] = moteur_defini
                        rapport["construction"]["composants"]["moteur_thermique"] = {
                            "type": type(moteur_defini).__name__,
                            "source": "definition_depuis_exigences",
                        }
                    else:
                        _push_inconnue(
                            rapport,
                            "impossibles",
                            "moteur_thermique",
                            "La définition par exigences n'a pas produit de moteur exploitable.",
                        )
                except Exception as exc:
                    _push_inconnue(
                        rapport,
                        "impossibles",
                        "moteur_thermique",
                        f"Définition par exigences impossible : {exc}",
                    )

        core_names = ("moteur_electrique", "batterie", "alternateur", "moteur_thermique")
        if all(self.composants_obj.get(n) is not None for n in core_names):
            try:
                self.systeme_complet_obj = SystemeComplet(
                    moteur_electrique=self.composants_obj["moteur_electrique"],
                    batterie=self.composants_obj["batterie"],
                    alternateur=self.composants_obj["alternateur"],
                    moteur_thermique=self.composants_obj["moteur_thermique"],
                    boite_crabots=self.composants_obj.get("boite_crabots"),
                    architecture=self.composants_obj.get("architecture"),
                )
                rapport["construction"]["composants"]["systeme_complet"] = {
                    "type": type(self.systeme_complet_obj).__name__,
                    "source": "assemblage",
                }
            except Exception as exc:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "systeme_complet",
                    f"Assemblage de SystemeComplet impossible : {exc}",
                )
        else:
            missing = [n for n in core_names if self.composants_obj.get(n) is None]
            _push_inconnue(
                rapport,
                "partielles",
                "systeme_complet",
                f"Assemblage incomplet : composants manquants = {', '.join(missing)}.",
            )

    # ---------------------------------------------------------------------
    # Analyses des composants
    # ---------------------------------------------------------------------
    def _run_component_analyses(self, rapport: Dict[str, Any]) -> None:
        rapport.setdefault("rapports", {}).setdefault("composants", {})

        if self.rapport_definition_moteur_thermique is not None:
            rapport["rapports"]["composants"]["moteur_thermique_definition"] = self.rapport_definition_moteur_thermique
            _merge_inconnues(rapport, self.rapport_definition_moteur_thermique, prefix="moteur_thermique_definition")

        if self.systeme_complet_obj is not None:
            params = self.analyses.get("systeme_complet", {})
            try:
                rep_systeme = self.systeme_complet_obj.analyser(**params)
                rapport["rapports"]["composants"]["systeme_complet"] = rep_systeme
                _merge_inconnues(rapport, rep_systeme, prefix="systeme_complet")
            except Exception as exc:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "analyse systeme_complet",
                    f"Appel SystemeComplet.analyser impossible : {exc}",
                )

        batterie = self.composants_obj.get("batterie")
        if batterie is not None and self.analyses.get("batterie"):
            try:
                rep = batterie.analyser_dimensionnement(**self.analyses["batterie"])
                rapport["rapports"]["composants"]["batterie_dimensionnement"] = rep
                _merge_inconnues(rapport, rep, prefix="batterie_dimensionnement")
            except Exception as exc:
                _push_inconnue(rapport, "impossibles", "batterie_dimensionnement", str(exc))

        alternateur = self.composants_obj.get("alternateur")
        if alternateur is not None and self.analyses.get("alternateur_bus_dc"):
            try:
                rep = alternateur.analyser_pour_bus_dc(**self.analyses["alternateur_bus_dc"])
                rapport["rapports"]["composants"]["alternateur_bus_dc"] = rep
                _merge_inconnues(rapport, rep, prefix="alternateur_bus_dc")
            except Exception as exc:
                _push_inconnue(rapport, "impossibles", "alternateur_bus_dc", str(exc))

        if alternateur is not None and self.analyses.get("alternateur_point"):
            try:
                rep = alternateur.analyser_point_de_fonctionnement(**self.analyses["alternateur_point"])
                rapport["rapports"]["composants"]["alternateur_point"] = rep
                _merge_inconnues(rapport, rep, prefix="alternateur_point")
            except Exception as exc:
                _push_inconnue(rapport, "impossibles", "alternateur_point", str(exc))

        architecture = self.composants_obj.get("architecture")
        if architecture is not None and self.analyses.get("architecture"):
            try:
                rep = architecture.analyser(**self.analyses["architecture"])
                rapport["rapports"]["composants"]["architecture"] = rep
                _merge_inconnues(rapport, rep, prefix="architecture")
            except Exception as exc:
                _push_inconnue(rapport, "impossibles", "architecture", str(exc))

        moteur_thermique = self.composants_obj.get("moteur_thermique")
        if moteur_thermique is not None:
            for key, method_name in (
                ("moteur_thermique_geometrie", "analyser_geometrie_definition"),
                ("moteur_thermique_cycle", "analyser_cycle_mecanique"),
                ("moteur_thermique_point", "analyser_point_de_fonctionnement"),
                ("moteur_thermique_bilan_carburant", "analyser_bilan_carburant"),
            ):
                params = self.analyses.get(key)
                if not params:
                    continue
                try:
                    rep = _run_named_analysis(moteur_thermique, method_name, params)
                    if rep is not None:
                        rapport["rapports"]["composants"][key] = rep
                        _merge_inconnues(rapport, rep, prefix=key)
                except Exception as exc:
                    _push_inconnue(rapport, "impossibles", key, str(exc))

        boite = self.composants_obj.get("boite_crabots")
        if boite is not None:
            if self.analyses.get("boite_point"):
                try:
                    rep = boite.analyser_point(**self.analyses["boite_point"])
                    rapport["rapports"]["composants"]["boite_point"] = rep
                    _merge_inconnues(rapport, rep, prefix="boite_point")
                except Exception as exc:
                    _push_inconnue(rapport, "impossibles", "boite_point", str(exc))
            if self.analyses.get("boite_chaine"):
                try:
                    rep = boite.analyser_chaine_moteur_alternateur(**self.analyses["boite_chaine"])
                    rapport["rapports"]["composants"]["boite_chaine"] = rep
                    _merge_inconnues(rapport, rep, prefix="boite_chaine")
                except Exception as exc:
                    _push_inconnue(rapport, "impossibles", "boite_chaine", str(exc))

    # ---------------------------------------------------------------------
    # Construction des pièces
    # ---------------------------------------------------------------------
    def _prepare_piece_kwargs(self, name: str, rapport: Dict[str, Any]) -> Dict[str, Any]:
        raw = self.pieces.get(name)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            return {"__passthrough__": raw}

        kwargs = dict(raw)
        sys_rep = _deep_get(rapport, "rapports", "composants", "systeme_complet")
        mt_ctx = _context_moteur(sys_rep, self.composants_obj.get("moteur_thermique"))

        # Dépendances objets
        for param_name, source_name in PIECE_DEPENDENCIES.get(name, {}).items():
            value = self.pieces_obj.get(source_name)
            if value is None and source_name == "moteur_thermique":
                value = self.composants_obj.get("moteur_thermique")
            if value is None and source_name == "systeme_complet_obj":
                value = self.systeme_complet_obj
            if value is not None:
                kwargs.setdefault(param_name, value)

        # Enrichissements strictement déductibles du système
        if name == "cylindre":
            if mt_ctx["alesage_m"] is not None:
                kwargs.setdefault("alesage_m", mt_ctx["alesage_m"])
            if mt_ctx["course_m"] is not None:
                kwargs.setdefault("course_m", mt_ctx["course_m"])
            if mt_ctx["pression_max_pa"] is not None:
                kwargs.setdefault("pression_max_pa", mt_ctx["pression_max_pa"])
            if mt_ctx["pme_pa"] is not None:
                kwargs.setdefault("pression_service_pa", mt_ctx["pme_pa"])

        if name in {"piston", "arbre_piston", "coussinet_arbre_piston"}:
            if mt_ctx["rpm_nominal"] is not None:
                kwargs.setdefault("rpm", mt_ctx["rpm_nominal"])

        if name == "piston":
            if mt_ctx["pression_max_pa"] is not None:
                kwargs.setdefault("pression_max_pa", mt_ctx["pression_max_pa"])
            if mt_ctx["alesage_m"] is not None:
                kwargs.setdefault("alesage_nominal_m", mt_ctx["alesage_m"])
            if mt_ctx["course_m"] is not None:
                kwargs.setdefault("course_m", mt_ctx["course_m"])

        if name == "bielle":
            if mt_ctx["course_m"] is not None and "longueur_bielle_m" not in kwargs:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "bielle.longueur_bielle_m",
                    "Aucune longueur de bielle fournie ; aucune règle interne n'est appliquée automatiquement ici.",
                )

        if name == "arbre_vilebrequin":
            if mt_ctx["course_m"] is not None:
                kwargs.setdefault("course_m", mt_ctx["course_m"])
            if mt_ctx["rpm_nominal"] is not None:
                kwargs.setdefault("rpm", mt_ctx["rpm_nominal"])
            couple = _deep_get(sys_rep, "synthese", "moteur_thermique", "couple_requis_Nm")
            if couple is not None:
                kwargs.setdefault("couple_max_Nm", couple)

        if name == "vilbrequin":
            if mt_ctx["course_m"] is not None:
                kwargs.setdefault("course_m", mt_ctx["course_m"])
            if mt_ctx["rpm_nominal"] is not None:
                kwargs.setdefault("rpm", mt_ctx["rpm_nominal"])
            couple = _deep_get(sys_rep, "synthese", "moteur_thermique", "couple_requis_Nm")
            if couple is not None:
                kwargs.setdefault("couple_max_Nm", couple)

        if name == "roulement_aiguille_arbre":
            if mt_ctx["rpm_nominal"] is not None:
                kwargs.setdefault("rpm", mt_ctx["rpm_nominal"])
            couple = _deep_get(sys_rep, "synthese", "moteur_thermique", "couple_requis_Nm")
            if couple is not None:
                kwargs.setdefault("couple_max_Nm", couple)
            if mt_ctx["course_m"] is not None:
                kwargs.setdefault("rayon_manivelle_m", 0.5 * float(mt_ctx["course_m"]))

        if name == "roulement_aiguille_arbre_vilebrequin":
            if mt_ctx["rpm_nominal"] is not None:
                kwargs.setdefault("rpm_vilebrequin", mt_ctx["rpm_nominal"])

        if name == "couvercle_cylindre":
            if mt_ctx["pression_max_pa"] is not None:
                kwargs.setdefault("pression_max_pa", mt_ctx["pression_max_pa"])
            if mt_ctx["pme_pa"] is not None:
                kwargs.setdefault("pression_service_pa", mt_ctx["pme_pa"])

        if name == "vis_couvercle_cylindre":
            if mt_ctx["pression_max_pa"] is not None:
                kwargs.setdefault("pression_max_pa", mt_ctx["pression_max_pa"])

        if name == "deplaceur":
            if mt_ctx["pression_max_pa"] is not None:
                kwargs.setdefault("pression_froid_pa", mt_ctx["pression_max_pa"])

        if name == "arbre":
            if mt_ctx["rpm_nominal"] is not None:
                kwargs.setdefault("rpm", mt_ctx["rpm_nominal"])
            couple = _deep_get(sys_rep, "synthese", "moteur_thermique", "couple_requis_Nm")
            if couple is not None:
                kwargs.setdefault("couple_max_Nm", couple)
            nb_cyl = mt_ctx["nombre_cylindres"]
            if nb_cyl is not None:
                kwargs.setdefault("nombre_cylindres", nb_cyl)

        return kwargs

    def _build_pieces(self, rapport: Dict[str, Any]) -> None:
        rapport.setdefault("construction", {}).setdefault("pieces", {})

        for name in PIECE_BUILD_ORDER:
            if name not in self.pieces:
                continue
            payload = self.pieces.get(name)
            if not isinstance(payload, dict):
                obj = _instantiate_or_passthrough(PIECE_CLASSES[name], payload, rapport=rapport, nom=name)
                if obj is not None:
                    self.pieces_obj[name] = obj
                    rapport["construction"]["pieces"][name] = {
                        "type": type(obj).__name__,
                        "source": "objet",
                    }
                continue

            kwargs = self._prepare_piece_kwargs(name, rapport)
            kwargs.pop("__passthrough__", None)
            try:
                obj = PIECE_CLASSES[name](**kwargs)
                self.pieces_obj[name] = obj
                rapport["construction"]["pieces"][name] = {
                    "type": type(obj).__name__,
                    "source": "dict_enrichi",
                }
            except Exception as exc:
                self.pieces_obj[name] = None
                _push_inconnue(
                    rapport,
                    "impossibles",
                    f"construction pièce {name}",
                    f"Instantiation impossible : {exc}",
                )

    # ---------------------------------------------------------------------
    # Analyses des pièces
    # ---------------------------------------------------------------------
    def _run_piece_analyses(self, rapport: Dict[str, Any]) -> None:
        rapport.setdefault("rapports", {}).setdefault("pieces", {})
        for name in PIECE_BUILD_ORDER:
            obj = self.pieces_obj.get(name)
            if obj is None:
                continue
            rep = _safe_call_report(obj)
            if rep is not None:
                rapport["rapports"]["pieces"][name] = rep
                _merge_inconnues(rapport, rep, prefix=name)
            else:
                rapport["rapports"]["pieces"][name] = {"note": "Pas de rapport dict retourné."}

    # ---------------------------------------------------------------------
    # Synthèse
    # ---------------------------------------------------------------------
    def _build_synthesis(self, rapport: Dict[str, Any]) -> None:
        rapport.setdefault("synthese", {})
        rep_sys = _deep_get(rapport, "rapports", "composants", "systeme_complet")
        rep_mt_def = _deep_get(rapport, "rapports", "composants", "moteur_thermique_definition")

        rep_pieces = _safe_dict(_deep_get(rapport, "rapports", "pieces"))
        piece_ok = sorted([k for k, v in rep_pieces.items() if isinstance(v, dict)])
        piece_missing = sorted([k for k in self.pieces.keys() if k not in piece_ok])

        mt_ctx = _context_moteur(rep_sys, self.composants_obj.get("moteur_thermique"))

        rapport["synthese"] = {
            "moteur_thermique": {
                "architecture": mt_ctx.get("architecture"),
                "nombre_cylindres": mt_ctx.get("nombre_cylindres"),
                "alesage_m": mt_ctx.get("alesage_m"),
                "course_m": mt_ctx.get("course_m"),
                "rpm_nominal": mt_ctx.get("rpm_nominal"),
                "pression_max_pa": mt_ctx.get("pression_max_pa"),
                "pme_pa": mt_ctx.get("pme_pa"),
                "source": "systeme_complet" if rep_sys else ("definition_depuis_exigences" if rep_mt_def else None),
            },
            "systeme_complet": _deep_get(rep_sys, "synthese") if isinstance(rep_sys, dict) else None,
            "pieces_analysees": piece_ok,
            "pieces_non_fermees": piece_missing,
            "composants_construits": sorted(self.composants_obj.keys()),
            "nb_inconnues_impossibles": len(rapport.get("inconnues", {}).get("impossibles", [])),
            "nb_inconnues_partielles": len(rapport.get("inconnues", {}).get("partielles", [])),
        }

        if rep_sys is None:
            _add_note(
                rapport,
                "Le système complet n'a pas été analysé ; la synthèse dépend alors uniquement des composants et pièces disponibles.",
            )
        if rep_mt_def is not None:
            _add_note(
                rapport,
                "Le moteur thermique a pu être défini à partir d'exigences via MoteurThermique.definir_depuis_exigences().",
            )
        if piece_missing:
            _add_note(
                rapport,
                "Certaines pièces n'ont pas été fermées faute de paramètres suffisants ou de dépendances déjà construites.",
            )

    # ---------------------------------------------------------------------
    # API publique
    # ---------------------------------------------------------------------
    def analyser(self) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "meta": {
                "orchestrateur": "STHO_ME.py",
                "classe": type(self).__name__,
                "version": "1.0.0",
                "repertoire": str(_THIS_DIR),
                "meta_utilisateur": _serialize_minimal(self.meta),
            },
            "construction": {
                "composants": {},
                "pieces": {},
            },
            "rapports": {
                "composants": {},
                "pieces": {},
            },
            "synthese": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        self._build_components(rapport)
        self._run_component_analyses(rapport)
        self._build_pieces(rapport)
        self._run_piece_analyses(rapport)
        self._build_synthesis(rapport)
        _dedup_inconnues(rapport)
        return rapport

    def export_json(self, path: str | os.PathLike[str], *, indent: int = 2) -> str:
        rapport = self.analyser()
        out = Path(path)
        out.write_text(json.dumps(rapport, ensure_ascii=False, indent=indent), encoding="utf-8")
        return str(out)

    @classmethod
    def depuis_config(cls, config: Mapping[str, Any]) -> "STHO_ME":
        return cls(
            composants=dict(_safe_dict(config.get("composants"))),
            pieces=dict(_safe_dict(config.get("pieces"))),
            analyses=dict(_safe_dict(config.get("analyses"))),
            meta=dict(_safe_dict(config.get("meta"))),
        )


# =============================================================================
# Fonctions utilitaires de haut niveau
# =============================================================================


def concevoir_systeme_stho_me(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Entrée haut niveau recommandée depuis API / GUI / notebook."""
    return STHO_ME.depuis_config(config).analyser()



def sauvegarder_conception_stho_me(config: Mapping[str, Any], path_json: str | os.PathLike[str]) -> str:
    """Construit le système et sauvegarde le rapport JSON complet."""
    orch = STHO_ME.depuis_config(config)
    return orch.export_json(path_json)


# =============================================================================
# Exemple CLI minimal
# =============================================================================


if __name__ == "__main__":
    exemple_config: Dict[str, Any] = {
        "meta": {
            "nom_projet": "STHO-ME",
            "mode": "exemple_minimal",
        },
        "composants": {
            "moteur_electrique": {
                "puissance_max_w": 80_000.0,
                "regime_max_rpm": 8_000.0,
                "couple_max_nm": 220.0,
                "tension_bus_v": 400.0,
                "rendement_moteur": 0.93,
            },
            "batterie": {
                "tension_nominale_v": 400.0,
                "fenetre_soc": 0.8,
                "rendement_charge": 0.94,
                "tension_charge_v": 420.0,
            },
            "alternateur": {
                "nombre_poles": 12,
                "connexion": "Y",
            },
            "architecture": {
                "temps_moteur": 4,
                "rendement_mecanique": 0.85,
            },
        },
        "analyses": {
            "moteur_thermique_definition": {
                "puissance_visee_w": 70_000.0,
                "type_puissance": "frein",
                "rpm": 3_000.0,
                "pression_moyenne_effective_pa": 8.0e5,
                "temps_moteur": 4,
                "rendement_mecanique": 0.85,
                "vitesse_piston_max_ms": 10.0,
                "ratio_course_alesage_max": 1.2,
                "L_max_m": 1.2,
                "W_max_m": 0.8,
                "architectures_autorisees": ("L", "V", "Etoile", "Boxer"),
                "pression_max_pa": 3.0e6,
                "contrainte_admissible_pa": 1.2e8,
            },
            "systeme_complet": {
                "puissance_moyenne_kw": 50.0,
                "puissance_pic_kw": 80.0,
                "scenario_bus_dc": "max",
                "vitesse_moteur_thermique_rpm": 3_000.0,
                "rapport_vitesse_alt_sur_moteur": 2.0,
                "pme_pa": 8.0e5,
                "vitesse_piston_max_ms": 10.0,
                "longueur_dispo_m": 1.2,
                "largeur_dispo_m": 0.8,
                "pression_max_pa": 3.0e6,
                "contrainte_admissible_pa": 1.2e8,
                "puissance_auxiliaire_w": 2_000.0,
            },
        },
        "pieces": {
            "cylindre": {
                "longueur_utile_m": 0.18,
                "materiau_cle": "acier_42crmo4_qt",
            },
            "piston": {
                "materiau_piston_cle": "alu_6061_t6",
            },
            "joint_piston": {
                "materiau_joint_cle": "ptfe",
            },
            "bielle": {
                "materiau_cle": "acier_42crmo4_qt",
                "longueur_bielle_m": 0.24,
            },
            "arbre_piston": {
                "materiau_cle": "acier_42crmo4_qt",
                "longueur_totale_m": 0.30,
                "longueur_fut_central_m": 0.16,
            },
            "coussinet_arbre_piston": {
                "materiau_coussinet": "bronze_cusn12",
            },
            "couvercle_cylindre": {
                "materiau_cle": "acier_42crmo4_qt",
            },
            "vis_couvercle_cylindre": {
                "classe_vis_iso898": "10.9",
            },
            "deplaceur": {
                "longueur_totale_m": 0.14,
                "materiau_cle": "inox_316l",
            },
            "joint_deplaceur": {
                "materiau_joint_cle": "ptfe",
            },
            "arbre_vilebrequin": {
                "materiau_cle": "acier_42crmo4_qt",
            },
            "vilbrequin": {
                "materiau_cle": "acier_42crmo4_qt",
            },
            "roulement_aiguille_arbre": {
                "duree_vie_cible_h": 5_000.0,
                "exposant_vie_p": 10.0 / 3.0,
            },
            "roulement_aiguille_arbre_vilebrequin": {
                "vie_cible_heures": 5_000.0,
            },
            "arbre": {
                "materiau_arbre_cle": "acier_42crmo4_qt",
            },
        },
    }

    rapport = concevoir_systeme_stho_me(exemple_config)
    print(json.dumps(rapport["synthese"], ensure_ascii=False, indent=2))

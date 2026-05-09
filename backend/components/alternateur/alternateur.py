# backend/components/alternateur.py
from __future__ import annotations

"""
Composant alternateur — orchestrateur robuste SHSE-M / STHO-ME.

Objectif :
- utiliser les modules de calcul alternateur fournis ;
- ne pas inventer de rendement global ni de pertes non calculées ;
- fonctionner dans l'arborescence backend, dans une arborescence modules/, ou en fichier isolé ;
- produire un rapport complet, JSON-sérialisable, exploitable par l'orchestrateur STHO_ME.
"""

from dataclasses import asdict, dataclass, is_dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Mapping, Optional, Tuple
import inspect
import json
import math
import os
import sys


# =============================================================================
# Chemins / imports robustes
# =============================================================================

_HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
for _p in (
    _HERE,
    _HERE / "modules",
    _HERE / "pieces",
    _HERE.parent,
    _HERE.parent / "modules" / "alternateur",
    _HERE.parent / "components" / "alternateur" / "modules",
    _HERE.parent / "components" / "alternateur" / "pieces",
):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_IMPORT_ERRORS: Dict[str, str] = {}


def _import_attr(module_names: Iterable[str], attr: str, *, required: bool = True) -> Any:
    last_exc: Optional[BaseException] = None
    tried: list[str] = []
    for module_name in module_names:
        tried.append(module_name)
        try:
            mod = import_module(module_name)
            return getattr(mod, attr)
        except BaseException as exc:  # ImportError, AttributeError, dépendance interne cassée...
            last_exc = exc
            continue
    key = f"{attr} ({', '.join(tried[:3])}{'...' if len(tried) > 3 else ''})"
    _IMPORT_ERRORS[key] = f"{type(last_exc).__name__}: {last_exc}"
    if required:
        raise ImportError(f"Impossible d'importer {attr}. Dernière erreur: {last_exc}")
    return None


def _alts(module_basename: str) -> Tuple[str, ...]:
    return (
        f"backend.components.alternateur.modules.{module_basename}",
        f"backend.modules.alternateur.{module_basename}",
        f"components.alternateur.modules.{module_basename}",
        f"modules.alternateur.{module_basename}",
        f"modules.{module_basename}",
        module_basename,
    )


def _piece_alts(module_basename: str) -> Tuple[str, ...]:
    return (
        f"backend.components.alternateur.pieces.{module_basename}",
        f"backend.modules.alternateur.pieces.{module_basename}",
        f"components.alternateur.pieces.{module_basename}",
        f"pieces.{module_basename}",
        module_basename,
    )


calcul_vitesse_angulaire = _import_attr(_alts("calcul_vitesse_angulaire"), "calcul_vitesse_angulaire")
calcul_frequence_synchrone = _import_attr(_alts("calcul_frequence_synchrone"), "calcul_frequence_synchrone")

calcul_fem_induite = _import_attr(_alts("calcul_fem_induite"), "calcul_fem_induite")
calcul_fem_induite_avec_induction = _import_attr(_alts("calcul_fem_induite"), "calcul_fem_induite_avec_induction", required=False)
calcul_flux_pole = _import_attr(_alts("calcul_fem_induite"), "calcul_flux_pole", required=False)
tension_ligne_depuis_phase = _import_attr(_alts("calcul_fem_induite"), "tension_ligne_depuis_phase", required=False)
tension_phase_depuis_ligne = _import_attr(_alts("calcul_fem_induite"), "tension_phase_depuis_ligne", required=False)

calcul_puissance_triphase = _import_attr(_alts("calcul_puissance_electrique"), "calcul_puissance_triphase")
calcul_puissance_monophase = _import_attr(_alts("calcul_puissance_electrique"), "calcul_puissance_monophase")
calcul_puissance_dc = _import_attr(_alts("calcul_puissance_electrique"), "calcul_puissance_dc")

calcul_resistance_enroulement = _import_attr(_alts("calcul_pertes_cuivre"), "calcul_resistance_enroulement")
calcul_pertes_cuivre_phase = _import_attr(_alts("calcul_pertes_cuivre"), "calcul_pertes_cuivre_phase")
calcul_pertes_cuivre_triphase = _import_attr(_alts("calcul_pertes_cuivre"), "calcul_pertes_cuivre_triphase")

calcul_pertes_fer_steinmetz = _import_attr(_alts("calcul_pertes_fer"), "calcul_pertes_fer_steinmetz")
calcul_rendement_alternateur = _import_attr(_alts("calcul_rendement_alternateur"), "calcul_rendement_alternateur")
calcul_puissance_mecanique = _import_attr(_alts("calcul_puissance_mecanique"), "calcul_puissance_mecanique")
calcul_couple_alternateur = _import_attr(_alts("calcul_couple_alternateur"), "calcul_couple_alternateur")
calcul_echauffement_thermique = _import_attr(_alts("calcul_echauffement_thermique"), "calcul_echauffement_thermique")

# Module batterie optionnel pour estimer le temps de charge du bus DC.
calcul_temps_charge = _import_attr(
    (
        "backend.components.batterie.modules.calcul_temps_charge",
        "backend.modules.batterie.calcul_temps_charge",
        "components.batterie.modules.calcul_temps_charge",
        "modules.batterie.calcul_temps_charge",
        "calcul_temps_charge",
    ),
    "calcul_temps_charge",
    required=False,
)

# Pièces optionnelles. Elles peuvent être utilisées si elles sont corrigées dans le projet ;
# sinon l'orchestrateur produit ses propres rapports pièce sans planter.
Rotor = _import_attr(_piece_alts("rotor"), "Rotor", required=False)
Stator = _import_attr(_piece_alts("stator"), "Stator", required=False)
ArbreAlternateur = _import_attr(_piece_alts("arbre_alternateur"), "ArbreAlternateur", required=False)
CarterAlternateur = _import_attr(_piece_alts("carter_alternateur"), "CarterAlternateur", required=False)
Ventilateur = _import_attr(_piece_alts("ventilateur"), "Ventilateur", required=False)
BobineExcitation = _import_attr(_piece_alts("bobine_excite"), "BobineExcitation", required=False)
RoulementAlternateur = _import_attr(_piece_alts("roulement_alternateur"), "RoulementAlternateur", required=False)


# =============================================================================
# Types / helpers
# =============================================================================

ModeElectrique = Literal["triphase_ac", "monophase_ac", "dc"]
Connexion = Literal["Y", "Delta"]
ModePoles = Literal["poles", "pair_poles", "pole_pairs"]
Onde = Literal["sinus", "carree", "custom"]


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _req_eta(name: str, eta: Any) -> float:
    v = _req_finite(name, eta)
    if not (0.0 < v <= 1.0):
        raise ValueError(f"{name} doit être dans (0,1] (reçu: {v}).")
    return v


def _req_int(name: str, x: Any, *, min_value: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _push_inconnue(rep: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rep.setdefault("inconnues", {}).setdefault(cat, []).append({"nom": nom, "raison": raison})


def _dedup_inconnues(rep: Dict[str, Any]) -> None:
    inc = rep.setdefault("inconnues", {})
    for cat in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out = []
        for item in inc.setdefault(cat, []):
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(item)
        inc[cat] = out


def _safe_get(obj: Any, *path_or_names: str) -> Any:
    if obj is None:
        return None
    if len(path_or_names) == 1:
        names = path_or_names[0].split(".")
    else:
        names = list(path_or_names)
    cur = obj
    for name in names:
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(name)
        else:
            cur = getattr(cur, name, None)
    return cur


def _coalesce(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _phase_line_from_connexion(connexion: Connexion) -> Tuple[float, float]:
    """Retourne (V_ligne/V_phase, I_phase/I_ligne)."""
    if connexion == "Y":
        return math.sqrt(3.0), 1.0
    if connexion == "Delta":
        return 1.0, 1.0 / math.sqrt(3.0)
    raise ValueError("connexion doit être 'Y' ou 'Delta'.")


def _call_with_supported_kwargs(fn: Any, /, **kwargs: Any) -> Any:
    sig = inspect.signature(fn)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return fn(**accepted)


def _to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, float):
            if math.isnan(obj):
                return None
            if math.isinf(obj):
                return "inf" if obj > 0 else "-inf"
        return obj
    if is_dataclass(obj):
        return _to_jsonable(asdict(obj))
    if isinstance(obj, Mapping):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    try:
        import numpy as np  # type: ignore
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
    except Exception:
        pass
    return str(obj)


def exporter_rapport_json(rapport: Mapping[str, Any], chemin: str | os.PathLike[str]) -> str:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(dict(rapport)), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


# =============================================================================
# Alternateur
# =============================================================================

@dataclass
class Alternateur:
    """
    Alternateur calculatoire.

    Le composant distingue :
    - les grandeurs réellement calculées ;
    - les grandeurs calculées seulement sur pertes connues ;
    - les inconnues qui empêchent une conclusion complète.
    """

    # Cinématique / topologie
    nombre_poles: Optional[int] = None
    mode_poles: ModePoles = "poles"
    connexion: Connexion = "Y"

    # Enroulement / magnétisme
    nombre_spires_serie: Optional[int] = None
    facteur_enroulement: Optional[float] = None
    flux_max_pole_wb: Optional[float] = None
    induction_gap_t: Optional[float] = None
    aire_pole_m2: Optional[float] = None
    onde: Onde = "sinus"
    constante_custom: Optional[float] = None

    # Cuivre
    resistance_phase_ohm: Optional[float] = None
    resistivite_ohm_m: Optional[float] = None
    longueur_fil_m: Optional[float] = None
    section_fil_m2: Optional[float] = None
    temperature_c: Optional[float] = None
    temperature_ref_c: float = 20.0
    coef_temperature: float = 0.00393

    # Fer / Steinmetz
    k_h: Optional[float] = None
    k_e: Optional[float] = None
    exposant_steinmetz: Optional[float] = None
    induction_max_t: Optional[float] = None
    eddy_freq_exp: float = 2.0
    eddy_induction_exp: float = 2.0
    masse_fer_kg: Optional[float] = None
    volume_fer_m3: Optional[float] = None

    # Pertes / rendement
    pertes_fixes_w: float = 0.0
    rendement_alternateur_impose: Optional[float] = None

    # Thermique
    resistance_thermique_k_w: Optional[float] = None
    temperature_ambiante_c: float = 20.0
    offset_temperature_c: float = 0.0
    temperature_max_admissible_c: Optional[float] = None

    # Dimensionnement arbre / roulement / ventilation / excitation
    diametre_arbre_m: Optional[float] = None
    tau_admissible_pa: Optional[float] = None
    charge_radiale_roulement_n: Optional[float] = None
    facteur_charge_roulement: float = 1.0
    capacite_dynamique_roulement_n: Optional[float] = None
    surface_echange_m2: Optional[float] = None
    coeff_convection_w_m2k: Optional[float] = None
    nombre_spires_excitation: Optional[int] = None
    courant_excitation_a: Optional[float] = None
    resistance_excitation_ohm: Optional[float] = None
    longueur_fil_excitation_m: Optional[float] = None
    section_fil_excitation_m2: Optional[float] = None
    resistivite_excitation_ohm_m: Optional[float] = None

    # Pièces externes optionnelles
    piece_rotor: Optional[Any] = None
    piece_stator: Optional[Any] = None
    piece_arbre: Optional[Any] = None
    piece_carter: Optional[Any] = None
    piece_ventilateur: Optional[Any] = None
    piece_bobine_excite: Optional[Any] = None
    piece_roulement: Optional[Any] = None

    clamp_non_negative: bool = True

    def __post_init__(self) -> None:
        _req_finite("pertes_fixes_w", self.pertes_fixes_w)
        _req_finite("temperature_ambiante_c", self.temperature_ambiante_c)
        _req_finite("offset_temperature_c", self.offset_temperature_c)
        if self.nombre_poles is not None:
            _req_int("nombre_poles", self.nombre_poles, min_value=1)
        if self.nombre_spires_serie is not None:
            _req_int("nombre_spires_serie", self.nombre_spires_serie, min_value=0)
        if self.rendement_alternateur_impose is not None:
            _req_eta("rendement_alternateur_impose", self.rendement_alternateur_impose)
        if self.masse_fer_kg is not None and self.volume_fer_m3 is not None:
            raise ValueError("Fournis soit masse_fer_kg, soit volume_fer_m3, pas les deux.")
        if self.connexion not in ("Y", "Delta"):
            raise ValueError("connexion doit être 'Y' ou 'Delta'.")

    # ------------------------------------------------------------------
    # Analyse principale
    # ------------------------------------------------------------------
    def analyser_point_de_fonctionnement(
        self,
        *,
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        mode_electrique: ModeElectrique = "triphase_ac",
        tension_v: Optional[float] = None,
        courant_a: Optional[float] = None,
        facteur_puissance: float = 1.0,
        entree_puissance_ac: Literal["VLL_IL", "Vph_Iph"] = "VLL_IL",
        courant_est_ligne: bool = True,
        puissance_electrique_cible_w: Optional[float] = None,
        courant_phase_rms_stator_a: Optional[float] = None,
        energie_a_recharger_kwh: Optional[float] = None,
        rendement_charge: float = 1.0,
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "composant": "alternateur",
            "entrees": {},
            "cinematique": {},
            "electromagnetique": {},
            "sortie_electrique": {},
            "pertes": {},
            "rendement": {},
            "mecanique": {},
            "thermique": {},
            "charge_batterie": {},
            "pieces": {},
            "imports": {"erreurs_optionnelles": dict(_IMPORT_ERRORS)},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        rep["entrees"].update({
            "vitesse_rotation_rpm": vitesse_rotation_rpm,
            "vitesse_angulaire_rad_s": vitesse_angulaire_rad_s,
            "mode_electrique": mode_electrique,
            "tension_v": tension_v,
            "courant_a": courant_a,
            "facteur_puissance": facteur_puissance,
            "entree_puissance_ac": entree_puissance_ac,
            "courant_est_ligne": courant_est_ligne,
            "puissance_electrique_cible_w": puissance_electrique_cible_w,
            "connexion": self.connexion,
            "nombre_poles": self.nombre_poles,
        })

        # 1) Vitesse mécanique
        omega: Optional[float] = None
        rpm: Optional[float] = None
        if vitesse_angulaire_rad_s is not None:
            omega = calcul_vitesse_angulaire(vitesse_angulaire_rad_s, input_unite="rad_s")
            rpm = (omega * 60.0) / (2.0 * math.pi)
        elif vitesse_rotation_rpm is not None:
            rpm = _req_finite("vitesse_rotation_rpm", vitesse_rotation_rpm)
            omega = calcul_vitesse_angulaire(rpm, input_unite="rpm")
        else:
            _push_inconnue(rep, "impossibles", "vitesse_rotation_rpm ou vitesse_angulaire_rad_s", "Vitesse requise pour fréquence, puissance mécanique et couple.")

        rep["cinematique"]["vitesse_rotation_rpm"] = rpm
        rep["cinematique"]["vitesse_angulaire_rad_s"] = omega

        # 2) Fréquence synchrone
        frequence_hz: Optional[float] = None
        if rpm is not None and self.nombre_poles is not None:
            frequence_hz = calcul_frequence_synchrone(
                vitesse_rotation_tr_min=rpm,
                nombre_poles=self.nombre_poles,
                mode_poles=self.mode_poles,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(rep, "partielles", "frequence_synchrone_hz", "Calculable si vitesse et nombre_poles sont fournis.")
        rep["cinematique"]["frequence_synchrone_hz"] = frequence_hz

        # 3) Flux / FEM
        flux_wb = self.flux_max_pole_wb
        if flux_wb is None and self.induction_gap_t is not None and self.aire_pole_m2 is not None and calcul_flux_pole is not None:
            flux_wb = calcul_flux_pole(
                induction_gap_t=self.induction_gap_t,
                aire_pole_m2=self.aire_pole_m2,
                flux_model="B*A",
            )
        elif flux_wb is None:
            _push_inconnue(rep, "partielles", "flux_max_pole_wb", "Fournir flux_max_pole_wb ou induction_gap_t + aire_pole_m2.")

        fem_phase_v: Optional[float] = None
        fem_ligne_v: Optional[float] = None
        if frequence_hz is not None and self.nombre_spires_serie is not None and flux_wb is not None and self.facteur_enroulement is not None:
            fem_phase_v = calcul_fem_induite(
                frequence_hz=frequence_hz,
                nombre_spires_serie=self.nombre_spires_serie,
                flux_max_pole_wb=flux_wb,
                facteur_enroulement_kw=self.facteur_enroulement,
                onde=self.onde,
                constante_custom=self.constante_custom,
                clamp_non_negative=True,
            )
            k_vll, _ = _phase_line_from_connexion(self.connexion)
            fem_ligne_v = fem_phase_v * k_vll
        else:
            _push_inconnue(rep, "partielles", "fem_induite", "Calculable si fréquence, spires, flux et facteur d'enroulement sont fournis.")

        rep["electromagnetique"].update({
            "flux_max_pole_wb": flux_wb,
            "fem_phase_rms_v": fem_phase_v,
            "fem_ligne_ligne_rms_v": fem_ligne_v,
            "nombre_spires_serie": self.nombre_spires_serie,
            "facteur_enroulement": self.facteur_enroulement,
            "onde": self.onde,
        })

        # 4) Puissance électrique utile
        P_out: Optional[float] = puissance_electrique_cible_w
        V_sortie: Optional[float] = None if tension_v is None else _req_finite("tension_v", tension_v)
        I_ligne_ou_dc: Optional[float] = None if courant_a is None else _req_finite("courant_a", courant_a)

        if P_out is None and V_sortie is not None and I_ligne_ou_dc is not None:
            if mode_electrique == "triphase_ac":
                P_out = calcul_puissance_triphase(
                    tension_composee=V_sortie,
                    courant_ligne=I_ligne_ou_dc,
                    facteur_puissance=facteur_puissance,
                    entree=entree_puissance_ac,
                    connexion=self.connexion,
                    clamp_non_negative=self.clamp_non_negative,
                )
            elif mode_electrique == "monophase_ac":
                P_out = calcul_puissance_monophase(
                    tension=V_sortie,
                    courant=I_ligne_ou_dc,
                    facteur_puissance=facteur_puissance,
                    clamp_non_negative=self.clamp_non_negative,
                )
            elif mode_electrique == "dc":
                P_out = calcul_puissance_dc(
                    tension_dc=V_sortie,
                    courant_dc=I_ligne_ou_dc,
                    clamp_non_negative=self.clamp_non_negative,
                )
            else:
                raise ValueError("mode_electrique doit être 'triphase_ac', 'monophase_ac' ou 'dc'.")
        elif P_out is None:
            _push_inconnue(rep, "impossibles", "puissance_electrique_sortie_w", "Fournir puissance_electrique_cible_w ou tension_v + courant_a.")

        if P_out is not None:
            P_out = _req_finite("puissance_electrique_sortie_w", P_out)

        rep["sortie_electrique"].update({
            "mode": mode_electrique,
            "tension_v": V_sortie,
            "courant_a": I_ligne_ou_dc,
            "facteur_puissance": facteur_puissance,
            "puissance_utile_w": P_out,
        })

        # 5) Courant de phase stator
        courant_phase: Optional[float] = courant_phase_rms_stator_a
        if courant_phase is None and I_ligne_ou_dc is not None and mode_electrique == "triphase_ac":
            _, k_iph_from_il = _phase_line_from_connexion(self.connexion)
            courant_phase = I_ligne_ou_dc * k_iph_from_il if courant_est_ligne else I_ligne_ou_dc
        elif courant_phase is None and I_ligne_ou_dc is not None and mode_electrique == "monophase_ac":
            courant_phase = I_ligne_ou_dc
        elif courant_phase is None and P_out is not None and V_sortie is not None and V_sortie != 0.0:
            if mode_electrique == "dc":
                courant_phase = None
            elif mode_electrique == "triphase_ac":
                I_est_ligne = abs(P_out) / max(math.sqrt(3.0) * abs(V_sortie) * max(abs(facteur_puissance), 1e-12), 1e-12)
                _, k_iph_from_il = _phase_line_from_connexion(self.connexion)
                courant_phase = I_est_ligne * k_iph_from_il
            elif mode_electrique == "monophase_ac":
                courant_phase = abs(P_out) / max(abs(V_sortie) * max(abs(facteur_puissance), 1e-12), 1e-12)

        rep["sortie_electrique"]["courant_phase_rms_stator_a"] = courant_phase

        # 6) Résistance phase + pertes cuivre
        R_phase = self.resistance_phase_ohm
        if R_phase is None and self.resistivite_ohm_m is not None and self.longueur_fil_m is not None and self.section_fil_m2 is not None:
            R_phase = calcul_resistance_enroulement(
                resistivite=self.resistivite_ohm_m,
                longueur_fil=self.longueur_fil_m,
                section_fil=self.section_fil_m2,
                temperature_c=self.temperature_c,
                temperature_ref_c=self.temperature_ref_c,
                coef_temperature=self.coef_temperature,
                clamp_non_negative=True,
            )
        elif R_phase is None:
            _push_inconnue(rep, "partielles", "resistance_phase_ohm", "Fournir R_phase ou résistivité + longueur_fil + section_fil.")
        if R_phase is not None:
            R_phase = _req_pos("resistance_phase_ohm", R_phase, strict=False)

        P_cu: Optional[float] = None
        if R_phase is not None and courant_phase is not None:
            if mode_electrique == "triphase_ac":
                P_cu = calcul_pertes_cuivre_triphase(
                    courant_phase=courant_phase,
                    resistance_phase=R_phase,
                    courant_type="rms",
                    connexion=self.connexion,
                    courant_est_ligne=False,
                    clamp_non_negative=True,
                )
            else:
                P_cu = calcul_pertes_cuivre_phase(
                    courant=courant_phase,
                    resistance=R_phase,
                    courant_type="rms",
                    clamp_non_negative=True,
                )
        elif mode_electrique != "dc":
            _push_inconnue(rep, "partielles", "pertes_cuivre_w", "Calculables si courant phase et résistance phase sont connus.")

        rep["pertes"].update({
            "resistance_phase_ohm": R_phase,
            "pertes_cuivre_w": P_cu,
        })

        # 7) Pertes fer
        P_fe: Optional[float] = None
        if frequence_hz is not None and self.induction_max_t is not None and self.k_h is not None and self.k_e is not None and self.exposant_steinmetz is not None:
            d_fe = calcul_pertes_fer_steinmetz(
                k_h=self.k_h,
                frequence=frequence_hz,
                induction_max=self.induction_max_t,
                exposant_steinmetz=self.exposant_steinmetz,
                k_e=self.k_e,
                eddy_freq_exp=self.eddy_freq_exp,
                eddy_induction_exp=self.eddy_induction_exp,
                masse_kg=self.masse_fer_kg,
                volume_m3=self.volume_fer_m3,
                return_details=True,
                clamp_non_negative=True,
            )
            P_fe = float(d_fe["P_total"])
            rep["pertes"]["detail_pertes_fer"] = d_fe
        else:
            _push_inconnue(rep, "partielles", "pertes_fer_w", "Calculables si fréquence, induction_max, k_h, k_e et exposant Steinmetz sont fournis.")
        rep["pertes"]["pertes_fer_w"] = P_fe
        rep["pertes"]["pertes_fixes_w"] = float(self.pertes_fixes_w)

        pertes_connues = [float(self.pertes_fixes_w)]
        if P_cu is not None:
            pertes_connues.append(float(P_cu))
        if P_fe is not None:
            pertes_connues.append(float(P_fe))
        P_pertes_connues = sum(pertes_connues)
        rep["pertes"]["pertes_connues_total_w"] = P_pertes_connues
        rep["pertes"]["pertes_connues_incompletes"] = bool(P_cu is None or P_fe is None)
        if P_cu is None or P_fe is None:
            rep["notes_modele"].append("Les pertes totales réelles ne sont pas conclues : les pertes cuivre et/ou fer sont manquantes.")

        # 8) Rendement / puissance mécanique / couple
        eta_impose = self.rendement_alternateur_impose
        eta_sur_pertes_connues: Optional[float] = None
        if P_out is not None:
            eta_sur_pertes_connues = calcul_rendement_alternateur(
                puissance_utile_out=P_out,
                liste_pertes=pertes_connues,
                clamp_0_1=True,
                return_details=False,
            )
        rep["rendement"].update({
            "rendement_impose": eta_impose,
            "eta_sur_pertes_connues": eta_sur_pertes_connues,
            "eta_sur_pertes_connues_est_partiel": bool(P_cu is None or P_fe is None),
        })

        eta_pour_dimensionnement = eta_impose
        if eta_pour_dimensionnement is None:
            _push_inconnue(rep, "partielles", "rendement_alternateur_impose", "Requis pour conclure la puissance mécanique et le couple dimensionnants sans supposer les pertes manquantes.")

        if P_out is not None:
            rep["mecanique"]["puissance_mecanique_sur_pertes_connues_w"] = P_out + P_pertes_connues
            if omega is not None and abs(omega) > 1e-12:
                rep["mecanique"]["couple_sur_pertes_connues_nm"] = (P_out + P_pertes_connues) / abs(omega)

        if P_out is not None and eta_pour_dimensionnement is not None:
            P_mec = calcul_puissance_mecanique(
                puissance_electrique_cible=P_out,
                rendement_alternateur=eta_pour_dimensionnement,
                pertes_fixes_w=float(self.pertes_fixes_w),
                clamp_non_negative=self.clamp_non_negative,
                mode_signe="abs" if self.clamp_non_negative else "conserver",
            )
            rep["mecanique"]["puissance_mecanique_dimensionnante_w"] = P_mec
            if omega is not None and abs(omega) > 1e-12:
                couple = calcul_couple_alternateur(
                    puissance_electrique_cible=P_out,
                    rendement_alternateur=eta_pour_dimensionnement,
                    vitesse_angulaire=omega,
                    pertes_fixes_w=float(self.pertes_fixes_w),
                    clamp_non_negative=self.clamp_non_negative,
                    mode_signe="abs_omega" if self.clamp_non_negative else "conserver",
                )
                rep["mecanique"]["couple_mecanique_dimensionnant_nm"] = couple
            elif omega is None:
                _push_inconnue(rep, "partielles", "couple_mecanique_dimensionnant_nm", "Calculable si vitesse angulaire disponible.")

        # 9) Thermique
        if self.resistance_thermique_k_w is not None:
            delta_t_connues = calcul_echauffement_thermique(
                puissance_pertes_totale=P_pertes_connues,
                resistance_thermique=self.resistance_thermique_k_w,
                offset_temperature=self.offset_temperature_c,
                clamp_non_negative=True,
            )
            temperature_estimee = self.temperature_ambiante_c + delta_t_connues
            rep["thermique"].update({
                "resistance_thermique_k_w": self.resistance_thermique_k_w,
                "echauffement_sur_pertes_connues_k": delta_t_connues,
                "temperature_estimee_sur_pertes_connues_c": temperature_estimee,
                "temperature_max_admissible_c": self.temperature_max_admissible_c,
            })
            if self.temperature_max_admissible_c is not None:
                rep["thermique"]["ok_temperature_sur_pertes_connues"] = temperature_estimee <= self.temperature_max_admissible_c
        else:
            _push_inconnue(rep, "partielles", "resistance_thermique_k_w", "Requise pour évaluer l'échauffement.")

        # 10) Temps de charge batterie optionnel
        if calcul_temps_charge is not None and energie_a_recharger_kwh is not None and P_out is not None and P_out > 0.0:
            P_kw = P_out / 1000.0
            rep["charge_batterie"]["temps_charge_h"] = calcul_temps_charge(
                energie_utile_kwh=energie_a_recharger_kwh,
                puissance_charge_kw=P_kw,
                rendement_charge=rendement_charge,
            )
            rep["charge_batterie"]["energie_a_recharger_kwh"] = energie_a_recharger_kwh
            rep["charge_batterie"]["puissance_charge_kw"] = P_kw
        elif energie_a_recharger_kwh is not None:
            _push_inconnue(rep, "partielles", "temps_charge_h", "Calculable si puissance électrique de sortie > 0 et module calcul_temps_charge disponible.")

        # 11) Rapports pièces : rapports internes robustes + pièces externes si fournies
        contexte = {
            "rpm": rpm,
            "omega": omega,
            "frequence_hz": frequence_hz,
            "P_out": P_out,
            "eta": eta_impose,
            "eta_sur_pertes_connues": eta_sur_pertes_connues,
            "P_pertes_connues": P_pertes_connues,
            "P_cu": P_cu,
            "P_fe": P_fe,
            "R_phase": R_phase,
            "courant_phase": courant_phase,
            "flux_wb": flux_wb,
            "fem_phase_v": fem_phase_v,
            "fem_ligne_v": fem_ligne_v,
        }
        rep["pieces"] = self._analyser_pieces(contexte)

        _dedup_inconnues(rep)
        return _to_jsonable(rep)

    # ------------------------------------------------------------------
    # Intégration bus DC
    # ------------------------------------------------------------------
    def analyser_pour_bus_dc(
        self,
        *,
        puissance_bus_dc_w: float,
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Any = None,
        moteur: Any = None,
        energie_a_recharger_kwh: Optional[float] = None,
        rendement_charge: float = 1.0,
    ) -> Dict[str, Any]:
        Pdc = _req_finite("puissance_bus_dc_w", puissance_bus_dc_w)
        Vdc = tension_bus_dc_v
        if Vdc is None:
            Vdc = _coalesce(
                _safe_get(batterie, "tension_charge_v"),
                _safe_get(batterie, "tension_nominale_v"),
                _safe_get(batterie, "entrees", "tension_nominale_v"),
                _safe_get(batterie, "bus_dc", "tension_v"),
                _safe_get(moteur, "tension_bus_v"),
                _safe_get(moteur, "entrees", "tension_bus_v"),
            )
        if Vdc is not None:
            Vdc = _req_pos("tension_bus_dc_v", Vdc, strict=True)
            Idc = Pdc / Vdc
        else:
            Idc = None

        rep = {
            "composant": "alternateur_bus_dc",
            "entrees": {
                "puissance_bus_dc_w": Pdc,
                "tension_bus_dc_v": Vdc,
                "courant_bus_dc_a": Idc,
                "energie_a_recharger_kwh": energie_a_recharger_kwh,
            },
            "alternateur": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        if Vdc is None:
            _push_inconnue(rep, "partielles", "tension_bus_dc_v", "Fournir tension_bus_dc_v ou un objet batterie/moteur contenant la tension nominale.")

        rep["alternateur"] = self.analyser_point_de_fonctionnement(
            vitesse_rotation_rpm=vitesse_rotation_rpm,
            vitesse_angulaire_rad_s=vitesse_angulaire_rad_s,
            mode_electrique="dc",
            tension_v=Vdc,
            courant_a=Idc,
            puissance_electrique_cible_w=Pdc,
            energie_a_recharger_kwh=energie_a_recharger_kwh,
            rendement_charge=rendement_charge,
        )
        _dedup_inconnues(rep)
        return _to_jsonable(rep)

    # ------------------------------------------------------------------
    # Pièces : analyse interne robuste
    # ------------------------------------------------------------------
    def _analyser_pieces(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        pieces: Dict[str, Any] = {
            "rotor": self._piece_rotor(ctx),
            "stator": self._piece_stator(ctx),
            "arbre": self._piece_arbre(ctx),
            "carter": self._piece_carter(ctx),
            "ventilateur": self._piece_ventilateur(ctx),
            "bobine_excitation": self._piece_bobine(ctx),
            "roulement": self._piece_roulement(ctx),
        }

        externes = {
            "rotor_externe": self.piece_rotor,
            "stator_externe": self.piece_stator,
            "arbre_externe": self.piece_arbre,
            "carter_externe": self.piece_carter,
            "ventilateur_externe": self.piece_ventilateur,
            "bobine_excite_externe": self.piece_bobine_excite,
            "roulement_externe": self.piece_roulement,
        }
        for nom, piece in externes.items():
            if piece is not None and hasattr(piece, "analyser"):
                try:
                    pieces[nom] = piece.analyser()
                except TypeError:
                    try:
                        pieces[nom] = piece.analyser(strict=False)
                    except Exception as exc:
                        pieces[nom] = {"erreur": str(exc)}
                except Exception as exc:
                    pieces[nom] = {"erreur": str(exc)}
        return pieces

    def _piece_rotor(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "rotor", "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}}
        rpm = ctx.get("rpm")
        P_out = ctx.get("P_out")
        eta = ctx.get("eta")
        if rpm is not None and self.nombre_poles is not None:
            rep["resultats"]["frequence_synchrone_hz"] = calcul_frequence_synchrone(
                vitesse_rotation_tr_min=float(rpm),
                nombre_poles=int(self.nombre_poles),
                mode_poles=self.mode_poles,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(rep, "partielles", "frequence_synchrone_hz", "vitesse_rotation_rpm et nombre_poles requis.")
        if P_out is not None and eta is not None and rpm is not None and float(rpm) != 0.0:
            omega = calcul_vitesse_angulaire(float(rpm), input_unite="rpm", clamp_non_negative=True)
            rep["resultats"]["puissance_mecanique_absorbee_w"] = calcul_puissance_mecanique(
                puissance_electrique_cible=float(P_out),
                rendement_alternateur=float(eta),
                pertes_fixes_w=float(self.pertes_fixes_w),
                clamp_non_negative=True,
                mode_signe="abs",
            )
            rep["resultats"]["couple_resistant_nm"] = calcul_couple_alternateur(
                puissance_electrique_cible=float(P_out),
                rendement_alternateur=float(eta),
                vitesse_angulaire=omega,
                pertes_fixes_w=float(self.pertes_fixes_w),
                clamp_non_negative=True,
                mode_signe="abs_omega",
            )
        else:
            _push_inconnue(rep, "partielles", "couple_resistant_nm", "P_out, rendement imposé et vitesse non nulle requis pour une valeur dimensionnante.")
        return rep

    def _piece_stator(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "stator", "resultats": {}, "pertes": {}, "inconnues": {"impossibles": [], "partielles": []}}
        rep["resultats"]["fem_phase_rms_v"] = ctx.get("fem_phase_v")
        rep["resultats"]["fem_ligne_ligne_rms_v"] = ctx.get("fem_ligne_v")
        rep["resultats"]["resistance_phase_ohm"] = ctx.get("R_phase")
        rep["pertes"]["P_cuivre_total_w"] = ctx.get("P_cu")
        rep["pertes"]["P_fer_total_w"] = ctx.get("P_fe")
        if ctx.get("fem_phase_v") is None:
            _push_inconnue(rep, "partielles", "fem_phase_rms_v", "Fréquence, spires, flux et facteur d'enroulement requis.")
        if ctx.get("P_cu") is None:
            _push_inconnue(rep, "partielles", "P_cuivre_total_w", "Courant phase et résistance phase requis.")
        if ctx.get("P_fe") is None:
            _push_inconnue(rep, "partielles", "P_fer_total_w", "Paramètres Steinmetz requis.")
        return rep

    def _piece_arbre(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "arbre_alternateur", "entrees": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}}
        T = _coalesce(_safe_get(ctx, "couple_mecanique_dimensionnant_nm"), _safe_get(ctx, "couple_sur_pertes_connues_nm"))
        # Le contexte est un dict plat : récupérer aussi depuis mécanique si déjà passé autrement.
        T = _coalesce(T, ctx.get("couple_dimensionnant"))
        if T is None and ctx.get("omega") is not None and ctx.get("P_out") is not None:
            # Valeur partielle seulement, basée sur pertes connues.
            Pm = float(ctx.get("P_out") or 0.0) + float(ctx.get("P_pertes_connues") or 0.0)
            omega = abs(float(ctx["omega"]))
            if omega > 1e-12:
                T = Pm / omega
                rep["contraintes"]["couple_base"] = "sur_pertes_connues"
        if T is not None:
            rep["entrees"]["couple_nm"] = float(T)
        else:
            _push_inconnue(rep, "impossibles", "couple_nm", "Requis pour vérifier la torsion de l'arbre.")
        if T is not None and self.diametre_arbre_m is not None:
            d = _req_pos("diametre_arbre_m", self.diametre_arbre_m, strict=True)
            tau = 16.0 * abs(float(T)) / (math.pi * d**3)
            rep["contraintes"]["tau_torsion_pa"] = tau
            rep["entrees"]["diametre_arbre_m"] = d
            if self.tau_admissible_pa is not None:
                tau_adm = _req_pos("tau_admissible_pa", self.tau_admissible_pa, strict=True)
                rep["contraintes"]["ok_torsion"] = tau <= tau_adm
                rep["contraintes"]["diametre_min_torsion_m"] = (16.0 * abs(float(T)) / (math.pi * tau_adm)) ** (1.0 / 3.0)
            else:
                _push_inconnue(rep, "partielles", "tau_admissible_pa", "Requis pour vérifier le coefficient de sécurité.")
        elif self.diametre_arbre_m is None:
            _push_inconnue(rep, "partielles", "diametre_arbre_m", "Requis pour calculer la contrainte de torsion.")
        return rep

    def _piece_carter(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "carter_alternateur", "thermique": {}, "inconnues": {"impossibles": [], "partielles": []}}
        P_loss = ctx.get("P_pertes_connues")
        rep["thermique"]["puissance_pertes_connues_w"] = P_loss
        if P_loss is not None and self.resistance_thermique_k_w is not None:
            delta = calcul_echauffement_thermique(
                puissance_pertes_totale=float(P_loss),
                resistance_thermique=float(self.resistance_thermique_k_w),
                offset_temperature=self.offset_temperature_c,
                clamp_non_negative=True,
            )
            rep["thermique"]["echauffement_sur_pertes_connues_k"] = delta
            rep["thermique"]["temperature_sur_pertes_connues_c"] = self.temperature_ambiante_c + delta
        else:
            _push_inconnue(rep, "partielles", "echauffement", "Pertes connues et résistance thermique requises.")
        return rep

    def _piece_ventilateur(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "ventilateur", "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}}
        rpm = ctx.get("rpm")
        h = self.coeff_convection_w_m2k
        if h is None and rpm is not None and float(rpm) >= 0.0:
            # Modèle explicitement simplifié : coefficient proxy, pas une valeur industrielle.
            h = 0.1 * math.sqrt(float(rpm))
            rep["resultats"]["coeff_convection_estime_w_m2k"] = h
            rep["notes_modele"] = ["Coefficient de convection proxy h=0.1*sqrt(rpm), à remplacer par corrélation aéraulique réelle."]
        elif h is None:
            _push_inconnue(rep, "partielles", "coeff_convection_w_m2k", "Fournir coeff_convection ou vitesse rpm pour une estimation proxy.")
        if h is not None and self.surface_echange_m2 is not None and ctx.get("P_pertes_connues") is not None:
            A = _req_pos("surface_echange_m2", self.surface_echange_m2, strict=True)
            rep["resultats"]["delta_t_refroidissement_proxy_k"] = float(ctx["P_pertes_connues"]) / max(float(h) * A, 1e-12)
        else:
            _push_inconnue(rep, "partielles", "delta_t_refroidissement_proxy_k", "h, surface d'échange et pertes connues requis.")
        return rep

    def _piece_bobine(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "bobine_excitation", "entrees": {}, "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}}
        if self.nombre_spires_excitation is not None:
            rep["entrees"]["nombre_spires_excitation"] = self.nombre_spires_excitation
        else:
            _push_inconnue(rep, "partielles", "nombre_spires_excitation", "Requis pour caractériser la bobine d'excitation.")
        if self.courant_excitation_a is not None:
            rep["entrees"]["courant_excitation_a"] = self.courant_excitation_a
        else:
            _push_inconnue(rep, "partielles", "courant_excitation_a", "Requis pour calculer les pertes d'excitation.")

        R_exc = self.resistance_excitation_ohm
        if R_exc is None and self.resistivite_excitation_ohm_m is not None and self.longueur_fil_excitation_m is not None and self.section_fil_excitation_m2 is not None:
            R_exc = calcul_resistance_enroulement(
                resistivite=self.resistivite_excitation_ohm_m,
                longueur_fil=self.longueur_fil_excitation_m,
                section_fil=self.section_fil_excitation_m2,
                temperature_c=self.temperature_c,
                temperature_ref_c=self.temperature_ref_c,
                coef_temperature=self.coef_temperature,
                clamp_non_negative=True,
            )
        if R_exc is not None:
            rep["resultats"]["resistance_excitation_ohm"] = R_exc
        else:
            _push_inconnue(rep, "partielles", "resistance_excitation_ohm", "Fournir R excitation ou géométrie du fil.")
        if R_exc is not None and self.courant_excitation_a is not None:
            rep["resultats"]["pertes_cuivre_excitation_w"] = float(self.courant_excitation_a) ** 2 * float(R_exc)
        return rep

    def _piece_roulement(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "roulement_alternateur", "entrees": {}, "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}}
        rpm = ctx.get("rpm")
        if self.charge_radiale_roulement_n is None:
            _push_inconnue(rep, "partielles", "charge_radiale_roulement_n", "Requise pour la durée de vie L10.")
            return rep
        if rpm is None:
            _push_inconnue(rep, "partielles", "vitesse_rotation_rpm", "Requise pour exprimer la durée de vie en heures.")
            return rep
        P = _req_pos("charge_radiale_roulement_n", self.charge_radiale_roulement_n, strict=True) * _req_pos("facteur_charge_roulement", self.facteur_charge_roulement, strict=True)
        C = self.capacite_dynamique_roulement_n
        rep["entrees"].update({"charge_equivalente_n": P, "vitesse_rpm": rpm, "capacite_dynamique_n": C})
        if C is None:
            _push_inconnue(rep, "partielles", "capacite_dynamique_roulement_n", "Requise pour calculer L10 ISO-281 simplifiée.")
            return rep
        C = _req_pos("capacite_dynamique_roulement_n", C, strict=True)
        millions_rev = (C / P) ** 3
        heures = (millions_rev * 1_000_000.0) / (60.0 * max(abs(float(rpm)), 1e-12))
        rep["resultats"]["duree_vie_l10_h"] = heures
        return rep


# =============================================================================
# Constructeurs / orchestration haut niveau
# =============================================================================

def construire_alternateur(config: Optional[Mapping[str, Any]] = None, **overrides: Any) -> Alternateur:
    cfg: Dict[str, Any] = dict(config or {})
    if "alternateur" in cfg and isinstance(cfg["alternateur"], Mapping):
        merged = dict(cfg["alternateur"])
        # Les clés top-level gardent la priorité si elles correspondent au constructeur.
        merged.update({k: v for k, v in cfg.items() if k != "alternateur"})
        cfg = merged
    cfg.update({k: v for k, v in overrides.items() if v is not None})

    allowed = set(inspect.signature(Alternateur).parameters.keys())
    kwargs = {k: v for k, v in cfg.items() if k in allowed}
    return Alternateur(**kwargs)


def concevoir_alternateur(config: Optional[Mapping[str, Any]] = None, **overrides: Any) -> Dict[str, Any]:
    cfg: Dict[str, Any] = dict(config or {})
    cfg.update(overrides)
    alt = construire_alternateur(cfg)

    point = {}
    for key in ("point", "point_de_fonctionnement", "fonctionnement"):
        if isinstance(cfg.get(key), Mapping):
            point.update(dict(cfg[key]))
    # Les clés top-level compatibles avec analyser_point_de_fonctionnement sont acceptées.
    allowed_point = set(inspect.signature(Alternateur.analyser_point_de_fonctionnement).parameters.keys()) - {"self"}
    point.update({k: v for k, v in cfg.items() if k in allowed_point})

    bus_dc = {}
    for key in ("bus_dc", "analyse_bus_dc"):
        if isinstance(cfg.get(key), Mapping):
            bus_dc.update(dict(cfg[key]))

    if bus_dc or "puissance_bus_dc_w" in cfg:
        allowed_bus = set(inspect.signature(Alternateur.analyser_pour_bus_dc).parameters.keys()) - {"self"}
        bus_dc.update({k: v for k, v in cfg.items() if k in allowed_bus})
        return alt.analyser_pour_bus_dc(**bus_dc)

    return alt.analyser_point_de_fonctionnement(**point)


__all__ = [
    "ModeElectrique",
    "Connexion",
    "ModePoles",
    "Alternateur",
    "construire_alternateur",
    "concevoir_alternateur",
    "exporter_rapport_json",
]


if __name__ == "__main__":
    exemple = concevoir_alternateur({
        "nombre_poles": 8,
        "mode_poles": "poles",
        "connexion": "Y",
        "nombre_spires_serie": 40,
        "facteur_enroulement": 0.95,
        "induction_gap_t": 0.9,
        "aire_pole_m2": 1.2e-3,
        "resistance_phase_ohm": 0.08,
        "k_h": 0.02,
        "k_e": 1e-5,
        "exposant_steinmetz": 1.7,
        "induction_max_t": 0.9,
        "masse_fer_kg": 12.0,
        "pertes_fixes_w": 250.0,
        "rendement_alternateur_impose": 0.92,
        "resistance_thermique_k_w": 0.08,
        "surface_echange_m2": 0.5,
        "diametre_arbre_m": 0.035,
        "tau_admissible_pa": 90e6,
        "point_de_fonctionnement": {
            "vitesse_rotation_rpm": 4500.0,
            "mode_electrique": "triphase_ac",
            "tension_v": 400.0,
            "courant_a": 80.0,
            "facteur_puissance": 0.95,
        },
    })
    print(json.dumps(_to_jsonable(exemple), ensure_ascii=False, indent=2))

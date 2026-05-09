# backend/components/moteur_thermique/pieces/arbre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
import math


# =============================================================================
# Utilitaires
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _push_inconnue(rapport: Dict[str, Any], kind: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(kind, []).append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    for k in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in rapport["inconnues"].get(k, []):
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        rapport["inconnues"][k] = out


def _borne(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))


def _get(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        for n in names:
            if n in obj:
                return obj.get(n)
        return None
    for n in names:
        if hasattr(obj, n):
            try:
                return getattr(obj, n)
            except Exception:
                pass
    return None


def _dig(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for m in ("analyser", "calculer"):
        fn = getattr(obj, m, None)
        if callable(fn):
            try:
                out = fn(strict=False) if m == "analyser" else fn(strict=False)
                if isinstance(out, dict):
                    return out
            except TypeError:
                try:
                    out = fn()
                    if isinstance(out, dict):
                        return out
                except Exception:
                    pass
            except Exception:
                pass
    return None


# =============================================================================
# DIN 6885 (table partielle explicite)
# =============================================================================

def _din6885_recommandation(d_arbre_m: float, norme: int = 1) -> Optional[Dict[str, float]]:
    d_mm = _req_pos("d_arbre_m", d_arbre_m) * 1e3

    if norme == 1:
        ranges: List[Tuple[float, float, float, float, float, float, float, float]] = [
            (6.0,  8.0,  2, 2, 1.0, 0.1, 1.2, 0.1),
            (8.0, 10.0,  3, 3, 1.4, 0.1, 1.8, 0.1),
            (10.0, 12.0, 4, 4, 1.8, 0.1, 2.5, 0.1),
            (12.0, 17.0, 5, 5, 2.3, 0.1, 3.0, 0.1),
            (17.0, 22.0, 6, 6, 2.8, 0.1, 3.5, 0.1),
            (22.0, 30.0, 8, 7, 3.3, 0.2, 4.0, 0.2),
            (30.0, 38.0, 10, 8, 3.3, 0.2, 5.0, 0.2),
            (38.0, 44.0, 12, 8, 3.3, 0.2, 5.0, 0.2),
            (44.0, 50.0, 14, 9, 3.8, 0.2, 5.5, 0.2),
        ]
        for i, (dmin, dmax, b, h, t2, tol2, t4, tol4) in enumerate(ranges):
            ok = (d_mm >= dmin and d_mm <= dmax) if i == 0 else (d_mm > dmin and d_mm <= dmax)
            if ok:
                return {
                    "norme": 1.0,
                    "plage_d_min_mm": float(dmin),
                    "plage_d_max_mm": float(dmax),
                    "b_m": b / 1e3,
                    "h_m": h / 1e3,
                    "profondeur_rainure_arbre_m": t2 / 1e3,
                    "tol_plus_t2_m": tol2 / 1e3,
                    "profondeur_rainure_moyeu_m": t4 / 1e3,
                    "tol_plus_t4_m": tol4 / 1e3,
                }
        return None

    if norme == 2:
        ranges2: List[Tuple[float, float, float, float, float, float, float, float]] = [
            (10.0, 12.0, 4, 4, 1.1, 0.1, 3.0, 0.1),
            (12.0, 17.0, 5, 5, 1.3, 0.1, 3.8, 0.1),
            (17.0, 22.0, 6, 6, 1.7, 0.1, 4.4, 0.1),
            (22.0, 30.0, 8, 7, 1.7, 0.2, 5.4, 0.2),
            (30.0, 38.0, 10, 8, 2.1, 0.2, 6.0, 0.2),
            (38.0, 44.0, 12, 8, 2.1, 0.2, 6.0, 0.2),
            (44.0, 50.0, 14, 9, 2.6, 0.2, 6.5, 0.2),
        ]
        for i, (dmin, dmax, b, h, t2, tol2, t4, tol4) in enumerate(ranges2):
            ok = (d_mm >= dmin and d_mm <= dmax) if i == 0 else (d_mm > dmin and d_mm <= dmax)
            if ok:
                return {
                    "norme": 2.0,
                    "plage_d_min_mm": float(dmin),
                    "plage_d_max_mm": float(dmax),
                    "b_m": b / 1e3,
                    "h_m": h / 1e3,
                    "profondeur_rainure_arbre_m": t2 / 1e3,
                    "tol_plus_t2_m": tol2 / 1e3,
                    "profondeur_rainure_moyeu_m": t4 / 1e3,
                    "tol_plus_t4_m": tol4 / 1e3,
                }
        return None

    raise ValueError("norme doit valoir 1 ou 2.")


# =============================================================================
# Matériaux
# =============================================================================

def _resoudre_materiau(
    *,
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
) -> Dict[str, Optional[float]]:
    rho = float(densite_kg_m3) if _is_finite(densite_kg_m3) else None
    Re = float(limite_elastique_pa) if _is_finite(limite_elastique_pa) else None
    E = float(module_young_pa) if _is_finite(module_young_pa) else None

    if materiau_cle:
        for modname in ("backend.ensemble.materiaux", "backend.materiaux", "materiaux"):
            try:
                mod = __import__(modname, fromlist=["get_materiau"])
                get_materiau = getattr(mod, "get_materiau")
                mat = get_materiau(materiau_cle)
                valeur = getattr(mod, "valeur", None)

                def _pick(value: Any, mode: str) -> Optional[float]:
                    if _is_finite(value):
                        return float(value)
                    if callable(valeur):
                        try:
                            out = valeur(value, mode=mode)
                            if _is_finite(out):
                                return float(out)
                        except Exception:
                            pass
                    return None

                if rho is None:
                    v = _get(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                    rho = _pick(v, "typique")

                if Re is None:
                    v = _get(mat, "limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa")
                    Re = _pick(v, "min")
                    if Re is None and hasattr(mat, "limite_elastique_effective_pa"):
                        try:
                            v = mat.limite_elastique_effective_pa(mode="min")
                            if _is_finite(v):
                                Re = float(v)
                        except Exception:
                            pass
                    if Re is None:
                        try:
                            segs = list(getattr(mat, "resistance_par_section", ()) or ())
                            vals = [
                                float(seg.rp02_pa_min)
                                for seg in segs
                                if _is_finite(getattr(seg, "rp02_pa_min", None))
                            ]
                            if vals:
                                Re = min(vals)
                        except Exception:
                            pass

                if E is None:
                    v = _get(mat, "module_young_pa", "E_pa", "young_pa", "young_modulus_pa")
                    E = _pick(v, "typique")

                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "limite_elastique_pa": Re,
        "module_young_pa": E,
    }


# =============================================================================
# Formules RDM arbre plein
# =============================================================================

def _aire_disque(d: float) -> float:
    r = 0.5 * _req_pos("d", d)
    return math.pi * r * r


def _moment_inertie_cercle(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**4) / 64.0


def _moment_polaire_cercle(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**4) / 32.0


def _diam_min_torsion(T_Nm: float, tau_adm_pa: float) -> float:
    T = abs(_req_finite("couple_max_Nm", T_Nm))
    tau = _req_pos("tau_adm_pa", tau_adm_pa)
    return (16.0 * T / (math.pi * tau)) ** (1.0 / 3.0)


def _diam_min_flexion(M_Nm: float, sigma_adm_pa: float) -> float:
    M = abs(_req_finite("moment_flexion_max_Nm", M_Nm))
    sigma = _req_pos("sigma_adm_pa", sigma_adm_pa)
    return (32.0 * M / (math.pi * sigma)) ** (1.0 / 3.0)


def _diam_min_traction(F_N: float, sigma_adm_pa: float) -> float:
    F = abs(_req_finite("force_axiale_N", F_N))
    sigma = _req_pos("sigma_adm_pa", sigma_adm_pa)
    return math.sqrt((4.0 * F) / (math.pi * sigma))


def _tau_torsion_max(T_Nm: float, d_m: float) -> float:
    return (16.0 * abs(float(T_Nm))) / (math.pi * float(d_m) ** 3)


def _sigma_flexion_max(M_Nm: float, d_m: float) -> float:
    return (32.0 * abs(float(M_Nm))) / (math.pi * float(d_m) ** 3)


def _sigma_axiale_max(F_N: float, d_m: float) -> float:
    A = _aire_disque(d_m)
    return abs(float(F_N)) / A


def _von_mises_sigma_tau(sigma: float, tau: float) -> float:
    return math.sqrt(float(sigma) ** 2 + 3.0 * float(tau) ** 2)


def _diam_min_von_mises_combine(
    *,
    T_Nm: Optional[float],
    M_Nm: Optional[float],
    F_N: Optional[float],
    sigma_adm_pa: float,
) -> Optional[float]:
    """
    Résout numériquement :
    sqrt((sigma_b + sigma_a)^2 + 3*tau^2) <= sigma_adm
    pour une section circulaire pleine.
    """
    sigma_adm = _req_pos("sigma_adm_pa", sigma_adm_pa)

    has_any = any(_is_finite(v) and abs(float(v)) > 0.0 for v in (T_Nm, M_Nm, F_N))
    if not has_any:
        return None

    def sigma_eq(d: float) -> float:
        sigma = 0.0
        tau = 0.0
        if T_Nm is not None and _is_finite(T_Nm):
            tau += _tau_torsion_max(float(T_Nm), d)
        if M_Nm is not None and _is_finite(M_Nm):
            sigma += _sigma_flexion_max(float(M_Nm), d)
        if F_N is not None and _is_finite(F_N):
            sigma += _sigma_axiale_max(float(F_N), d)
        return _von_mises_sigma_tau(sigma, tau)

    d_lo = 1e-6
    d_hi = 1e-3
    while sigma_eq(d_hi) > sigma_adm:
        d_hi *= 1.5
        if d_hi > 10.0:
            raise ValueError("Résolution d_min_von_mises_combine impossible : borne supérieure excessive.")

    for _ in range(120):
        d_mid = 0.5 * (d_lo + d_hi)
        if sigma_eq(d_mid) > sigma_adm:
            d_lo = d_mid
        else:
            d_hi = d_mid

    return d_hi


# =============================================================================
# Clavette
# =============================================================================

def _clavette_longueur_min_cisaillement(T: float, d: float, b: float, tau_adm: float) -> float:
    return (2.0 * abs(float(T))) / (_req_pos("d", d) * _req_pos("b", b) * _req_pos("tau_adm", tau_adm))


def _clavette_longueur_min_ecrasement(T: float, d: float, h: float, sigma_adm: float) -> float:
    return (4.0 * abs(float(T))) / (_req_pos("d", d) * _req_pos("h", h) * _req_pos("sigma_adm", sigma_adm))


# =============================================================================
# Arbre moteur
# =============================================================================

@dataclass
class ArbreMoteur:
    """
    Arbre moteur / arbre d'entraînement.

    Objectif :
    - définir l'arbre par le calcul à partir :
      * des contraintes mécaniques,
      * du nombre de cylindres,
      * des autres pièces du projet.
    - ne rien choisir si la donnée n'est pas calculable.
    """

    cylindre: Optional[Any] = None
    moteur_thermique: Optional[Any] = None
    systeme_complet: Optional[Any] = None
    vilbrequin: Optional[Any] = None
    roulement_aiguille: Optional[Any] = None

    # Efforts / cinématique
    couple_max_Nm: Optional[float] = None
    rpm: Optional[float] = None
    moment_flexion_max_Nm: Optional[float] = None
    force_radiale_N: Optional[float] = None
    force_axiale_N: Optional[float] = None

    # Diamètre / passage
    diametre_arbre_m: Optional[float] = None
    diametre_passage_arbre_m: Optional[float] = None
    jeu_passage_arbre_m: Optional[float] = None

    # Architecture
    nombre_cylindres: Optional[int] = None
    entraxe_cylindres_m: Optional[float] = None
    diametre_externe_cylindre_m: Optional[float] = None
    empilement_annexe_cote_entree_m: Optional[float] = None
    empilement_annexe_cote_sortie_m: Optional[float] = None
    depassement_cote_entree_m: Optional[float] = None
    depassement_cote_sortie_m: Optional[float] = None

    # Interfaces vilebrequin / roulements / moyeux
    largeur_moyeu_vilbrequin_m: Optional[float] = None
    largeur_portee_roulement_m: Optional[float] = None
    longueur_portee_clavette_disponible_m: Optional[float] = None

    # Clavette
    norme_din_6885: int = 1
    utiliser_din: bool = True
    clavette_b_m: Optional[float] = None
    clavette_h_m: Optional[float] = None

    # Matériaux
    materiau_arbre_cle: Optional[str] = None
    limite_elastique_arbre_pa: Optional[float] = None
    module_young_arbre_pa: Optional[float] = None
    densite_arbre_kg_m3: Optional[float] = None

    materiau_clavette_cle: Optional[str] = None
    limite_elastique_clavette_pa: Optional[float] = None

    materiau_moyeu_cle: Optional[str] = None
    limite_elastique_moyeu_pa: Optional[float] = None

    # Sécurité
    facteur_securite: float = 2.0

    # Admissibles explicites
    tau_admissible_arbre_pa: Optional[float] = None
    tau_admissible_clavette_pa: Optional[float] = None
    sigma_admissible_appui_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "arbre_moteur",
            "entrees": {},
            "recuperations": {},
            "materiau": {},
            "contraintes": {},
            "dimensionnements": {},
            "clavette": {},
            "longueur": {},
            "interfaces": {},
            "masses": {},
            "cao": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ---------------------------------------------------------------------
        # 1) Rapports dépendances
        # ---------------------------------------------------------------------
        rep_vb = _try_call_report(self.vilbrequin)
        rep_ra = _try_call_report(self.roulement_aiguille)
        rep_cyl = _try_call_report(self.cylindre)
        rep_sys = _try_call_report(self.systeme_complet)
        rep_mot = _try_call_report(self.moteur_thermique)

        rapport["recuperations"] = {
            "vilbrequin": bool(rep_vb),
            "roulement_aiguille": bool(rep_ra),
            "cylindre": bool(rep_cyl),
            "systeme_complet": bool(rep_sys),
            "moteur_thermique": bool(rep_mot),
        }

        # ---------------------------------------------------------------------
        # 2) Couple / rpm / efforts
        # ---------------------------------------------------------------------
        T = self.couple_max_Nm
        if T is None:
            T = _dig(rep_vb, "cinematique", "couple_max_Nm")
        if T is None:
            T = _get(self.vilbrequin, "couple_max_Nm")
        if T is None:
            T = _get(self.systeme_complet, "couple_max_Nm", "couple_nm", "couple_Nm")
        if T is None:
            T = _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
        if T is not None:
            T = _req_pos("couple_max_Nm", T, strictly=False)
            rapport["dimensionnements"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rapport, "impossibles", "couple_max_Nm", "Requis pour dimensionner l'arbre en torsion.")

        rpm = self.rpm
        if rpm is None:
            rpm = _dig(rep_vb, "cinematique", "rpm")
        if rpm is None:
            rpm = _get(self.systeme_complet, "rpm", "regime_rpm")
        if rpm is None:
            rpm = _get(self.moteur_thermique, "rpm", "regime_rpm")
        if rpm is not None:
            rpm = _req_pos("rpm", rpm, strictly=False)
            rapport["dimensionnements"]["rpm"] = rpm
        else:
            _push_inconnue(rapport, "partielles", "rpm", "Utile pour la cinématique et les vérifications d'interface.")

        M = self.moment_flexion_max_Nm
        if M is None:
            M = _dig(rep_vb, "cinematique", "moment_flexion_max_Nm")
        if M is None:
            M = _get(self.vilbrequin, "moment_flexion_max_Nm")
        if M is not None:
            M = _req_pos("moment_flexion_max_Nm", M, strictly=False)
            rapport["dimensionnements"]["moment_flexion_max_Nm"] = M
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "moment_flexion_max_Nm",
                "Requis pour le dimensionnement en flexion ; non déduit automatiquement sans modèle d'appuis.",
            )

        Fr = self.force_radiale_N
        if Fr is None:
            Fr = _get(self.roulement_aiguille, "force_radiale_equivalente_N")
        if Fr is None:
            Fr = _dig(rep_ra, "charges", "force_radiale_equivalente_N")
        if Fr is None:
            Fr = _dig(rep_ra, "charges", "P_equivalente_N")
        if Fr is not None:
            Fr = _req_pos("force_radiale_N", Fr, strictly=False)
            rapport["dimensionnements"]["force_radiale_N"] = Fr
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force_radiale_N",
                "Utile pour un modèle de flexion si tu relies la charge radiale à une portée/appui.",
            )

        Fa = self.force_axiale_N
        if Fa is not None:
            Fa = _req_pos("force_axiale_N", Fa, strictly=False)
            rapport["dimensionnements"]["force_axiale_N"] = Fa

        # ---------------------------------------------------------------------
        # 3) Matériaux et admissibles
        # ---------------------------------------------------------------------
        props_arbre = _resoudre_materiau(
            materiau_cle=self.materiau_arbre_cle,
            densite_kg_m3=self.densite_arbre_kg_m3,
            limite_elastique_pa=self.limite_elastique_arbre_pa,
            module_young_pa=self.module_young_arbre_pa,
        )
        props_clavette = _resoudre_materiau(
            materiau_cle=self.materiau_clavette_cle,
            densite_kg_m3=None,
            limite_elastique_pa=self.limite_elastique_clavette_pa,
            module_young_pa=None,
        )
        props_moyeu = _resoudre_materiau(
            materiau_cle=self.materiau_moyeu_cle,
            densite_kg_m3=None,
            limite_elastique_pa=self.limite_elastique_moyeu_pa,
            module_young_pa=None,
        )

        rapport["materiau"] = {
            "arbre": {"materiau_cle": self.materiau_arbre_cle, **props_arbre},
            "clavette": {"materiau_cle": self.materiau_clavette_cle, **props_clavette},
            "moyeu": {"materiau_cle": self.materiau_moyeu_cle, **props_moyeu},
        }

        Re_arbre = props_arbre["limite_elastique_pa"]
        rho_arbre = props_arbre["densite_kg_m3"]

        tau_arbre = float(self.tau_admissible_arbre_pa) if _is_finite(self.tau_admissible_arbre_pa) else None
        if tau_arbre is None and Re_arbre is not None:
            tau_arbre = float(Re_arbre) / (FS * math.sqrt(3.0))
            rapport["notes_modele"].append("tau_admissible_arbre_pa déduit par von Mises : Re/(FS*sqrt(3)).")

        sigma_arbre = (float(Re_arbre) / FS) if Re_arbre is not None else None

        tau_cle = float(self.tau_admissible_clavette_pa) if _is_finite(self.tau_admissible_clavette_pa) else None
        if tau_cle is None and props_clavette["limite_elastique_pa"] is not None:
            tau_cle = float(props_clavette["limite_elastique_pa"]) / (FS * math.sqrt(3.0))
            rapport["notes_modele"].append("tau_admissible_clavette_pa déduit par von Mises : Re/(FS*sqrt(3)).")

        sigma_appui = float(self.sigma_admissible_appui_pa) if _is_finite(self.sigma_admissible_appui_pa) else None
        if sigma_appui is None:
            Re_candidates = [x for x in (props_clavette["limite_elastique_pa"], props_moyeu["limite_elastique_pa"]) if _is_finite(x)]
            if Re_candidates:
                sigma_appui = min(float(x) for x in Re_candidates) / FS
                rapport["notes_modele"].append("sigma_admissible_appui_pa déduit du matériau limitant (min(Re_clavette, Re_moyeu)/FS).")

        rapport["contraintes"] = {
            "tau_admissible_arbre_pa": tau_arbre,
            "sigma_admissible_arbre_pa": sigma_arbre,
            "tau_admissible_clavette_pa": tau_cle,
            "sigma_admissible_appui_pa": sigma_appui,
        }

        if tau_arbre is None:
            _push_inconnue(rapport, "impossibles", "tau_admissible_arbre_pa", "Requise pour dimensionner l'arbre en torsion.")
        if sigma_arbre is None:
            _push_inconnue(rapport, "partielles", "sigma_admissible_arbre_pa", "Requise pour flexion/traction/von Mises combiné.")
        if tau_cle is None:
            _push_inconnue(rapport, "partielles", "tau_admissible_clavette_pa", "Requise pour la longueur mini de clavette en cisaillement.")
        if sigma_appui is None:
            _push_inconnue(rapport, "partielles", "sigma_admissible_appui_pa", "Requise pour la longueur mini de clavette en écrasement.")

        # ---------------------------------------------------------------------
        # 4) Diamètre minimal mécanique
        # ---------------------------------------------------------------------
        d_min_tors = None
        if T is not None and tau_arbre is not None:
            d_min_tors = _diam_min_torsion(T, tau_arbre)
            rapport["dimensionnements"]["d_min_torsion_m"] = d_min_tors

        d_min_flex = None
        if M is not None and sigma_arbre is not None:
            d_min_flex = _diam_min_flexion(M, sigma_arbre)
            rapport["dimensionnements"]["d_min_flexion_m"] = d_min_flex

        d_min_ax = None
        if Fa is not None and sigma_arbre is not None:
            d_min_ax = _diam_min_traction(Fa, sigma_arbre)
            rapport["dimensionnements"]["d_min_traction_m"] = d_min_ax

        d_min_vm = None
        if sigma_arbre is not None:
            d_min_vm = _diam_min_von_mises_combine(
                T_Nm=T,
                M_Nm=M,
                F_N=Fa,
                sigma_adm_pa=sigma_arbre,
            )
            if d_min_vm is not None:
                rapport["dimensionnements"]["d_min_von_mises_combine_m"] = d_min_vm

        d_min_global = None
        ds = [x for x in (d_min_tors, d_min_flex, d_min_ax, d_min_vm) if x is not None]
        if ds:
            d_min_global = max(ds)
            rapport["dimensionnements"]["d_min_global_m"] = d_min_global
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "d_min_global_m",
                "Impossible sans couple et/ou efforts + contraintes admissibles.",
            )

        # ---------------------------------------------------------------------
        # 5) Contrainte de passage
        # ---------------------------------------------------------------------
        d_max_passage = None
        if _is_finite(self.diametre_passage_arbre_m) and _is_finite(self.jeu_passage_arbre_m):
            d_pass = _req_pos("diametre_passage_arbre_m", self.diametre_passage_arbre_m)
            jeu = _req_pos("jeu_passage_arbre_m", self.jeu_passage_arbre_m, strictly=False)
            d_max_passage = d_pass - 2.0 * jeu
            if d_max_passage <= 0.0:
                raise ValueError("Contrainte de passage incohérente : d_max_passage_m <= 0.")
            rapport["dimensionnements"]["d_max_passage_m"] = d_max_passage
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "d_max_passage_m",
                "Calculable si diametre_passage_arbre_m et jeu_passage_arbre_m sont fournis.",
            )

        # ---------------------------------------------------------------------
        # 6) Diamètre de conception retenu
        # ---------------------------------------------------------------------
        d_impose = self.diametre_arbre_m
        d_design = None

        if d_impose is not None:
            d_design = _req_pos("diametre_arbre_m", d_impose)
            rapport["dimensionnements"]["diametre_arbre_impose_m"] = d_design
        elif d_min_global is not None:
            d_design = float(d_min_global)
            rapport["dimensionnements"]["diametre_arbre_calcule_m"] = d_design
            rapport["notes_modele"].append("diametre_arbre_m retenu automatiquement = d_min_global_m.")
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "diametre_arbre_m",
                "Aucun diamètre retenable sans d_min_global_m.",
            )

        if d_design is not None:
            if d_min_global is not None:
                rapport["dimensionnements"]["check_d_vs_dmin_ok"] = (d_design >= d_min_global)
                rapport["dimensionnements"]["check_d_vs_dmin_ratio"] = d_design / d_min_global if d_min_global > 0 else None
            if d_max_passage is not None:
                rapport["dimensionnements"]["check_d_vs_passage_ok"] = (d_design <= d_max_passage)
                rapport["dimensionnements"]["check_d_vs_passage_ratio"] = d_design / d_max_passage if d_max_passage > 0 else None

        # ---------------------------------------------------------------------
        # 7) Clavette
        # ---------------------------------------------------------------------
        reco = None
        b = h = t2 = t4 = None

        if d_design is not None and self.utiliser_din:
            reco = _din6885_recommandation(d_design, norme=int(self.norme_din_6885))
            rapport["clavette"]["recommandation_din"] = reco
            if reco is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "din6885",
                    "Diamètre hors domaine de la table partielle intégrée, ou norme non couverte.",
                )

        if reco is not None:
            b = reco["b_m"]
            h = reco["h_m"]
            t2 = reco["profondeur_rainure_arbre_m"]
            t4 = reco["profondeur_rainure_moyeu_m"]
        else:
            if _is_finite(self.clavette_b_m) and _is_finite(self.clavette_h_m):
                b = _req_pos("clavette_b_m", self.clavette_b_m)
                h = _req_pos("clavette_h_m", self.clavette_h_m)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "clavette_b_h",
                    "Fournir clavette_b_m + clavette_h_m, ou utiliser DIN avec un diamètre d'arbre calculé/imposé.",
                )

        rapport["clavette"].update({
            "b_m": b,
            "h_m": h,
            "profondeur_rainure_arbre_m": t2,
            "profondeur_rainure_moyeu_m": t4,
        })

        L_cle_shear = None
        L_cle_bearing = None
        L_cle_req = None

        if T is not None and d_design is not None and b is not None and tau_cle is not None:
            L_cle_shear = _clavette_longueur_min_cisaillement(T, d_design, b, tau_cle)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "longueur_clavette_cisaillement_m",
                "Calculable si couple, diamètre d'arbre, b et tau_admissible_clavette sont connus.",
            )

        if T is not None and d_design is not None and h is not None and sigma_appui is not None:
            L_cle_bearing = _clavette_longueur_min_ecrasement(T, d_design, h, sigma_appui)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "longueur_clavette_ecrasement_m",
                "Calculable si couple, diamètre d'arbre, h et sigma_admissible_appui sont connus.",
            )

        Ls = [x for x in (L_cle_shear, L_cle_bearing) if x is not None]
        if Ls:
            L_cle_req = max(Ls)
            rapport["clavette"]["longueur_min_cisaillement_m"] = L_cle_shear
            rapport["clavette"]["longueur_min_ecrasement_m"] = L_cle_bearing
            rapport["clavette"]["longueur_min_requise_m"] = L_cle_req

        L_cle_dispo = self.longueur_portee_clavette_disponible_m
        if L_cle_dispo is not None:
            L_cle_dispo = _req_pos("longueur_portee_clavette_disponible_m", L_cle_dispo)
            rapport["clavette"]["longueur_disponible_m"] = L_cle_dispo
            if L_cle_req is not None:
                rapport["clavette"]["check_longueur_ok"] = (L_cle_dispo >= L_cle_req)
                rapport["clavette"]["check_longueur_ratio"] = L_cle_dispo / L_cle_req if L_cle_req > 0 else None

        # ---------------------------------------------------------------------
        # 8) Interfaces vilebrequin / roulement / moyeu
        # ---------------------------------------------------------------------
        largeur_moyeu = self.largeur_moyeu_vilbrequin_m
        if largeur_moyeu is None:
            largeur_moyeu = _dig(rep_vb, "geometrie", "largeur_portee_journal_m")
        if largeur_moyeu is not None:
            largeur_moyeu = _req_pos("largeur_moyeu_vilbrequin_m", largeur_moyeu)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "largeur_moyeu_vilbrequin_m",
                "Utile pour la longueur d'arbre et la zone de clavette.",
            )

        largeur_roulement = self.largeur_portee_roulement_m
        if largeur_roulement is None:
            largeur_roulement = _dig(rep_ra, "dimensions_reference", "B_largeur_m")
        if largeur_roulement is None:
            largeur_roulement = _dig(rep_ra, "dimensions_requises", "B_largeur_requise_m")
        if largeur_roulement is not None:
            largeur_roulement = _req_pos("largeur_portee_roulement_m", largeur_roulement)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "largeur_portee_roulement_m",
                "Utile pour la longueur d'arbre si l'arbre porte un roulement.",
            )

        rapport["interfaces"] = {
            "largeur_moyeu_vilbrequin_m": largeur_moyeu,
            "largeur_portee_roulement_m": largeur_roulement,
            "longueur_portee_clavette_disponible_m": L_cle_dispo,
            "largeur_rainure_moyeu_m": b,
            "profondeur_rainure_moyeu_m": t4,
        }

        # ---------------------------------------------------------------------
        # 9) Longueur d'arbre depuis nombre de cylindres
        # ---------------------------------------------------------------------
        n = self.nombre_cylindres
        if n is None:
            n = _get(self.systeme_complet, "nombre_cylindres")
        if n is None:
            n = _get(self.moteur_thermique, "nombre_cylindres")
        if n is not None:
            n = _req_int_ge("nombre_cylindres", n, min_value=1)
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "nombre_cylindres",
                "Requis pour dimensionner la longueur de l'arbre par architecture.",
            )

        entraxe = self.entraxe_cylindres_m
        if entraxe is None:
            entraxe = _get(self.systeme_complet, "entraxe_cylindres_m")
        if entraxe is not None:
            entraxe = _req_pos("entraxe_cylindres_m", entraxe)

        d_ext_cyl = self.diametre_externe_cylindre_m
        if d_ext_cyl is None:
            d_ext_cyl = _get(self.cylindre, "diametre_externe_m", "diametre_exterieur_m")
        if d_ext_cyl is None:
            d_ext_cyl = _dig(rep_cyl, "geometrie", "diametre_externe_m")
        if d_ext_cyl is not None:
            d_ext_cyl = _req_pos("diametre_externe_cylindre_m", d_ext_cyl)

        dep_in = self.depassement_cote_entree_m
        dep_out = self.depassement_cote_sortie_m
        emp_in = self.empilement_annexe_cote_entree_m
        emp_out = self.empilement_annexe_cote_sortie_m

        if dep_in is not None:
            dep_in = _req_pos("depassement_cote_entree_m", dep_in, strictly=False)
        if dep_out is not None:
            dep_out = _req_pos("depassement_cote_sortie_m", dep_out, strictly=False)
        if emp_in is not None:
            emp_in = _req_pos("empilement_annexe_cote_entree_m", emp_in, strictly=False)
        if emp_out is not None:
            emp_out = _req_pos("empilement_annexe_cote_sortie_m", emp_out, strictly=False)

        # bloc axial des cylindres :
        # - n = 1 : longueur = D_ext_cyl
        # - n >= 2 : longueur = D_ext_cyl + (n-1)*entraxe
        bloc_cyl = None
        if n is not None and d_ext_cyl is not None:
            if n == 1:
                bloc_cyl = d_ext_cyl
            else:
                if entraxe is None:
                    _push_inconnue(
                        rapport,
                        "impossibles",
                        "entraxe_cylindres_m",
                        "Requis si nombre_cylindres >= 2 pour calculer la longueur du bloc.",
                    )
                else:
                    bloc_cyl = d_ext_cyl + (n - 1) * entraxe
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "bloc_cylindres_longueur_m",
                "Calculable si nombre_cylindres et diametre_externe_cylindre_m sont connus, plus entraxe si n>=2.",
            )

        if bloc_cyl is not None:
            rapport["longueur"]["bloc_cylindres_longueur_m"] = bloc_cyl

        # empilement annexe mini calculable
        emp_in_calc = emp_in
        emp_out_calc = emp_out

        if emp_in_calc is None:
            candidates_in = [x for x in (largeur_roulement, largeur_moyeu, L_cle_req, dep_in) if x is not None]
            if candidates_in:
                emp_in_calc = max(candidates_in)
                rapport["notes_modele"].append("empilement_annexe_cote_entree_m déduit par max(interface/roulement/clavette/dépassement).")

        if emp_out_calc is None:
            candidates_out = [x for x in (largeur_roulement, dep_out) if x is not None]
            if candidates_out:
                emp_out_calc = max(candidates_out)
                rapport["notes_modele"].append("empilement_annexe_cote_sortie_m déduit par max(roulement/dépassement).")

        L_total = None
        if bloc_cyl is not None and emp_in_calc is not None and emp_out_calc is not None:
            L_total = bloc_cyl + emp_in_calc + emp_out_calc
            rapport["longueur"]["longueur_totale_arbre_m"] = L_total
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "longueur_totale_arbre_m",
                "Calculable si bloc_cylindres_longueur_m et empilements d'extrémité sont connus/calculables.",
            )

        rapport["longueur"].update({
            "nombre_cylindres": n,
            "entraxe_cylindres_m": entraxe,
            "diametre_externe_cylindre_m": d_ext_cyl,
            "empilement_annexe_cote_entree_m": emp_in_calc,
            "empilement_annexe_cote_sortie_m": emp_out_calc,
            "depassement_cote_entree_m": dep_in,
            "depassement_cote_sortie_m": dep_out,
        })

        # ---------------------------------------------------------------------
        # 10) Masse / inertie arbre modèle
        # ---------------------------------------------------------------------
        if d_design is not None and L_total is not None and rho_arbre is not None:
            V = _aire_disque(d_design) * L_total
            m = rho_arbre * V
            I_p = 0.5 * m * (0.5 * d_design) ** 2
            rapport["masses"] = {
                "volume_modele_m3": V,
                "masse_modele_kg": m,
                "densite_kg_m3": rho_arbre,
            }
            rapport["masses"]["inertie_polaire_modele_kg_m2"] = I_p
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "masse_modele_kg",
                "Calculable si diametre_arbre, longueur_totale_arbre et densité matériau sont connus.",
            )

        # ---------------------------------------------------------------------
        # 11) Bloc CAO
        # ---------------------------------------------------------------------
        chanfrein = None
        rayon_conge = None
        if d_design is not None:
            chanfrein = _borne(0.03 * d_design, 0.0005, 0.0020)
            rayon_conge = _borne(0.05 * d_design, 0.0005, 0.0030)

        rapport["cao"] = {
            "diametre_nominal_arbre_m": d_design,
            "longueur_totale_m": L_total,
            "zone_clavette": {
                "b_m": b,
                "h_m": h,
                "longueur_m": L_cle_req,
                "profondeur_rainure_arbre_m": t2,
                "profondeur_rainure_moyeu_m": t4,
            },
            "epaulements": {
                "largeur_moyeu_vilbrequin_m": largeur_moyeu,
                "largeur_portee_roulement_m": largeur_roulement,
            },
            "rayon_conge_epaulement_m": rayon_conge,
            "chanfrein_extremite_m": chanfrein,
            "note": "Bloc CAO calculé sans série normalisée cachée. Les dimensions restent conditionnées aux données mécaniques et d’architecture disponibles.",
        }

        # ---------------------------------------------------------------------
        # 12) Entrées
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "couple_max_Nm": self.couple_max_Nm,
            "rpm": self.rpm,
            "moment_flexion_max_Nm": self.moment_flexion_max_Nm,
            "force_radiale_N": self.force_radiale_N,
            "force_axiale_N": self.force_axiale_N,
            "diametre_arbre_m": self.diametre_arbre_m,
            "diametre_passage_arbre_m": self.diametre_passage_arbre_m,
            "jeu_passage_arbre_m": self.jeu_passage_arbre_m,
            "nombre_cylindres": self.nombre_cylindres,
            "entraxe_cylindres_m": self.entraxe_cylindres_m,
            "diametre_externe_cylindre_m": self.diametre_externe_cylindre_m,
            "empilement_annexe_cote_entree_m": self.empilement_annexe_cote_entree_m,
            "empilement_annexe_cote_sortie_m": self.empilement_annexe_cote_sortie_m,
            "depassement_cote_entree_m": self.depassement_cote_entree_m,
            "depassement_cote_sortie_m": self.depassement_cote_sortie_m,
            "largeur_moyeu_vilbrequin_m": self.largeur_moyeu_vilbrequin_m,
            "largeur_portee_roulement_m": self.largeur_portee_roulement_m,
            "longueur_portee_clavette_disponible_m": self.longueur_portee_clavette_disponible_m,
            "norme_din_6885": self.norme_din_6885,
            "utiliser_din": self.utiliser_din,
            "clavette_b_m": self.clavette_b_m,
            "clavette_h_m": self.clavette_h_m,
            "materiau_arbre_cle": self.materiau_arbre_cle,
            "limite_elastique_arbre_pa": self.limite_elastique_arbre_pa,
            "module_young_arbre_pa": self.module_young_arbre_pa,
            "densite_arbre_kg_m3": self.densite_arbre_kg_m3,
            "materiau_clavette_cle": self.materiau_clavette_cle,
            "limite_elastique_clavette_pa": self.limite_elastique_clavette_pa,
            "materiau_moyeu_cle": self.materiau_moyeu_cle,
            "limite_elastique_moyeu_pa": self.limite_elastique_moyeu_pa,
            "facteur_securite": self.facteur_securite,
            "tau_admissible_arbre_pa": self.tau_admissible_arbre_pa,
            "tau_admissible_clavette_pa": self.tau_admissible_clavette_pa,
            "sigma_admissible_appui_pa": self.sigma_admissible_appui_pa,
        }

        _dedup_inconnues(rapport)

        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "ArbreMoteur(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# Alias pratique
Arbre = ArbreMoteur


if __name__ == "__main__":
    from pprint import pprint

    a = ArbreMoteur(
        couple_max_Nm=120.0,
        moment_flexion_max_Nm=40.0,
        nombre_cylindres=2,
        entraxe_cylindres_m=0.120,
        diametre_externe_cylindre_m=0.090,
        depassement_cote_entree_m=0.020,
        depassement_cote_sortie_m=0.015,
        limite_elastique_arbre_pa=700e6,
        densite_arbre_kg_m3=7800.0,
        facteur_securite=2.0,
        limite_elastique_clavette_pa=500e6,
        limite_elastique_moyeu_pa=450e6,
    )

    pprint(a.analyser(strict=False))

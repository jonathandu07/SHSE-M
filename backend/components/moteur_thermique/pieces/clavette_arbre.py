# backend/components/moteur_thermique/pieces/clavette_arbre.py
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


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append(
        {"nom": nom, "raison": raison}
    )


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    for k in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in list(rapport.get("inconnues", {}).get(k, []) or []):
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        rapport.setdefault("inconnues", {})[k] = out


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
        try:
            if hasattr(obj, n):
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
                out = fn(strict=False)
            except TypeError:
                try:
                    out = fn()
                except Exception:
                    continue
            except Exception:
                continue
            if isinstance(out, dict):
                return out
    return None


# =============================================================================
# DIN 6885 (table partielle)
# =============================================================================

def _din6885_recommandation(d_arbre_m: float, norme: int = 1) -> Optional[Dict[str, float]]:
    d_mm = _req_pos("d_arbre_m", d_arbre_m) * 1e3

    if norme == 1:
        ranges = [
            (6.0, 8.0, 2, 2, 1.0, 0.1, 1.2, 0.1),
            (8.0, 10.0, 3, 3, 1.4, 0.1, 1.8, 0.1),
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
        ranges2 = [
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
        for modname in (
            "backend.ensemble.materiaux",
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                mat = None
                if hasattr(mod, "get_materiau"):
                    mat = mod.get_materiau(materiau_cle)  # type: ignore[attr-defined]
                elif hasattr(mod, "MATERIAUX"):
                    mats = getattr(mod, "MATERIAUX")
                    if isinstance(mats, dict):
                        mat = mats.get(materiau_cle)
                if mat is None:
                    continue
                valeur = getattr(mod, "valeur", None)

                def g(obj: Any, *names: str, mode: str = "typique") -> Optional[float]:
                    for n in names:
                        if isinstance(obj, dict) and n in obj:
                            v = obj.get(n)
                        else:
                            v = getattr(obj, n, None)
                        if _is_finite(v):
                            return float(v)
                        if callable(valeur):
                            try:
                                out = valeur(v, mode=mode)
                                if _is_finite(out):
                                    return float(out)
                            except Exception:
                                pass
                    return None

                if rho is None:
                    rho = g(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                if Re is None:
                    Re = g(mat, "limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa", mode="min")
                    if Re is None and hasattr(mat, "limite_elastique_effective_pa"):
                        try:
                            v = mat.limite_elastique_effective_pa(mode="min")
                            if _is_finite(v):
                                Re = float(v)
                        except Exception:
                            pass
                if E is None:
                    E = g(mat, "module_young_pa", "E_pa", "young_pa", "young_modulus_pa")
                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "limite_elastique_pa": Re,
        "module_young_pa": E,
    }


# =============================================================================
# Formules clavette
# =============================================================================

def _clavette_longueur_min_cisaillement(T: float, d: float, b: float, tau_adm: float) -> float:
    return (2.0 * abs(float(T))) / (
        _req_pos("d", d) * _req_pos("b", b) * _req_pos("tau_adm", tau_adm)
    )


def _clavette_longueur_min_ecrasement(T: float, d: float, h: float, sigma_adm: float) -> float:
    return (4.0 * abs(float(T))) / (
        _req_pos("d", d) * _req_pos("h", h) * _req_pos("sigma_adm", sigma_adm)
    )


# =============================================================================
# Pièce : Clavette d'arbre pour anneau intérieur de roulement
# =============================================================================

@dataclass
class ClavetteArbre:
    """
    Clavette parallèle montée sur arbre pour empêcher la rotation relative
    de l'anneau intérieur d'un roulement par rapport à l'arbre.

    Hypothèses explicites :
    - clavette parallèle type DIN 6885 ;
    - transmission du couple par cisaillement de clavette et pression d'appui ;
    - la longueur utile de clavette est bornée par la largeur de l'anneau intérieur
      (ou par une longueur explicitement imposée plus restrictive) ;
    - aucun frettage/interférence n'est supposé partager le couple ;
    - aucun choix catalogue caché.
    """

    # Dépendances
    arbre: Optional[Any] = None
    arbre_vilbrequin: Optional[Any] = None
    roulement: Optional[Any] = None
    roulement_aiguille_arbre: Optional[Any] = None
    vilbrequin: Optional[Any] = None
    systeme_complet: Optional[Any] = None
    moteur_thermique: Optional[Any] = None

    # Interfaces / efforts explicites
    couple_transmis_Nm: Optional[float] = None
    diametre_arbre_m: Optional[float] = None
    largeur_anneau_interieur_m: Optional[float] = None
    longueur_clavette_disponible_m: Optional[float] = None

    # Norme / géométrie
    utiliser_din: bool = True
    norme_din_6885: int = 1
    clavette_b_m: Optional[float] = None
    clavette_h_m: Optional[float] = None
    profondeur_rainure_arbre_m: Optional[float] = None
    profondeur_rainure_anneau_m: Optional[float] = None

    # Matériaux
    materiau_clavette_cle: Optional[str] = None
    limite_elastique_clavette_pa: Optional[float] = None
    materiau_anneau_interieur_cle: Optional[str] = None
    limite_elastique_anneau_interieur_pa: Optional[float] = None

    # Admissibles
    tau_admissible_clavette_pa: Optional[float] = None
    sigma_admissible_appui_pa: Optional[float] = None
    facteur_securite: float = 2.0

    # Détail de montage
    jeu_extremite_total_m: float = 0.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "clavette_arbre",
            "entrees": {},
            "recuperations": {},
            "materiaux": {},
            "contraintes": {},
            "dimensions": {},
            "verifications": {},
            "interfaces": {},
            "cao": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)
        jeu_ext = _req_pos("jeu_extremite_total_m", self.jeu_extremite_total_m, strictly=False)

        # ---------------------------------------------------------------------
        # 1) Rapports dépendances
        # ---------------------------------------------------------------------
        roulement_obj = self.roulement if self.roulement is not None else self.roulement_aiguille_arbre

        rep_arbre = _try_call_report(self.arbre)
        rep_av = _try_call_report(self.arbre_vilbrequin)
        rep_roul = _try_call_report(roulement_obj)
        rep_vb = _try_call_report(self.vilbrequin)
        rep_sys = _try_call_report(self.systeme_complet)
        rep_mot = _try_call_report(self.moteur_thermique)

        rapport["recuperations"] = {
            "arbre": bool(rep_arbre),
            "arbre_vilebrequin": bool(rep_av),
            "roulement": bool(rep_roul),
            "vilbrequin": bool(rep_vb),
            "systeme_complet": bool(rep_sys),
            "moteur_thermique": bool(rep_mot),
        }

        # ---------------------------------------------------------------------
        # 2) Couple transmis
        # ---------------------------------------------------------------------
        T = self.couple_transmis_Nm
        if T is None:
            T = _dig(rep_arbre, "dimensionnements", "couple_max_Nm")
        if T is None:
            T = _dig(rep_vb, "cinematique", "couple_max_Nm")
        if T is None:
            T = _get(self.vilbrequin, "couple_max_Nm")
        if T is None:
            T = _get(self.systeme_complet, "couple_max_Nm", "couple_nm", "couple_Nm")
        if T is None:
            T = _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")

        if T is not None:
            T = _req_pos("couple_transmis_Nm", T, strictly=False)
            rapport["dimensions"]["couple_transmis_Nm"] = T
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "couple_transmis_Nm",
                "Requis pour dimensionner la clavette.",
            )

        # ---------------------------------------------------------------------
        # 3) Diamètre d'arbre à la portée du roulement
        # ---------------------------------------------------------------------
        d = self.diametre_arbre_m
        if d is None:
            d = _dig(rep_arbre, "cao", "diametre_nominal_arbre_m")
        if d is None:
            d = _dig(rep_arbre, "dimensionnements", "diametre_arbre_impose_m")
        if d is None:
            d = _dig(rep_arbre, "dimensionnements", "diametre_arbre_calcule_m")
        if d is None:
            d = _dig(rep_roul, "dimensions_reference", "d_interieur_m")
        if d is None:
            d = _dig(rep_roul, "dimensions_requises", "d_interieur_requis_m")
        if d is None:
            d = _dig(rep_roul, "dimensions_requises", "journal", "d_interieur_requis_m")
        if d is None:
            d = _get(roulement_obj, "d_interieur_m", "diametre_interieur_m")
        if d is None:
            d = _get(
                self.arbre_vilbrequin,
                "diametre_journal_m",
                "diametre_arbre_m",
                "diametre_portee_roulement_m",
            )

        if d is not None:
            d = _req_pos("diametre_arbre_m", d)
            rapport["interfaces"]["diametre_arbre_m"] = d
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "diametre_arbre_m",
                "Requis pour la géométrie et les vérifications de clavette.",
            )

        # ---------------------------------------------------------------------
        # 4) Largeur disponible sous l'anneau intérieur
        # ---------------------------------------------------------------------
        B = self.largeur_anneau_interieur_m
        if B is None:
            B = _dig(rep_roul, "dimensions_reference", "B_largeur_m")
        if B is None:
            B = _dig(rep_roul, "dimensions_requises", "B_largeur_requise_m")
        if B is None:
            B = _dig(rep_roul, "dimensions_requises", "journal", "B_largeur_requise_m")
        if B is None:
            B = _get(roulement_obj, "B_largeur_m", "largeur_m", "largeur_roulement_m")

        if B is not None:
            B = _req_pos("largeur_anneau_interieur_m", B)
            rapport["interfaces"]["largeur_anneau_interieur_m"] = B
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "largeur_anneau_interieur_m",
                "Utile pour borner la longueur disponible de clavette sous l'anneau intérieur.",
            )

        L_dispo = self.longueur_clavette_disponible_m
        if L_dispo is None and B is not None:
            L_dispo = B
            rapport["notes_modele"].append(
                "longueur_clavette_disponible_m déduite de la largeur de l'anneau intérieur du roulement."
            )

        if L_dispo is not None:
            L_dispo = _req_pos("longueur_clavette_disponible_m", L_dispo)
            rapport["interfaces"]["longueur_clavette_disponible_m"] = L_dispo
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "longueur_clavette_disponible_m",
                "Fournir explicitement ou via la largeur de l'anneau intérieur du roulement.",
            )

        # ---------------------------------------------------------------------
        # 5) Matériaux et admissibles
        # ---------------------------------------------------------------------
        props_cle = _resoudre_materiau(
            materiau_cle=self.materiau_clavette_cle,
            densite_kg_m3=None,
            limite_elastique_pa=self.limite_elastique_clavette_pa,
            module_young_pa=None,
        )
        props_ai = _resoudre_materiau(
            materiau_cle=self.materiau_anneau_interieur_cle,
            densite_kg_m3=None,
            limite_elastique_pa=self.limite_elastique_anneau_interieur_pa,
            module_young_pa=None,
        )

        rapport["materiaux"] = {
            "clavette": {"materiau_cle": self.materiau_clavette_cle, **props_cle},
            "anneau_interieur": {
                "materiau_cle": self.materiau_anneau_interieur_cle,
                **props_ai,
            },
        }

        tau_cle = (
            float(self.tau_admissible_clavette_pa)
            if _is_finite(self.tau_admissible_clavette_pa)
            else None
        )
        if tau_cle is None and props_cle["limite_elastique_pa"] is not None:
            tau_cle = float(props_cle["limite_elastique_pa"]) / (FS * math.sqrt(3.0))
            rapport["notes_modele"].append(
                "tau_admissible_clavette_pa déduit par von Mises : Re/(FS*sqrt(3))."
            )

        sigma_appui = (
            float(self.sigma_admissible_appui_pa)
            if _is_finite(self.sigma_admissible_appui_pa)
            else None
        )
        if sigma_appui is None:
            Re_candidates = [
                x
                for x in (
                    props_cle["limite_elastique_pa"],
                    props_ai["limite_elastique_pa"],
                )
                if _is_finite(x)
            ]
            if Re_candidates:
                sigma_appui = min(float(x) for x in Re_candidates) / FS
                rapport["notes_modele"].append(
                    "sigma_admissible_appui_pa déduit du matériau limitant min(Re_clavette, Re_anneau_interieur)/FS."
                )

        rapport["contraintes"] = {
            "tau_admissible_clavette_pa": tau_cle,
            "sigma_admissible_appui_pa": sigma_appui,
        }

        if tau_cle is None:
            _push_inconnue(
                rapport,
                "partielles",
                "tau_admissible_clavette_pa",
                "Requise pour la vérification au cisaillement.",
            )
        if sigma_appui is None:
            _push_inconnue(
                rapport,
                "partielles",
                "sigma_admissible_appui_pa",
                "Requise pour la vérification à l'appui sur l'anneau intérieur.",
            )

        # ---------------------------------------------------------------------
        # 6) Géométrie de clavette
        # ---------------------------------------------------------------------
        reco = None
        b = h = t2 = t4 = None

        if d is not None and self.utiliser_din:
            reco = _din6885_recommandation(d, norme=int(self.norme_din_6885))
            rapport["dimensions"]["recommandation_din"] = reco
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
                    "impossibles",
                    "clavette_b_m_h_m",
                    "Fournir clavette_b_m + clavette_h_m, ou activer utiliser_din avec un diamètre d'arbre connu.",
                )

            if _is_finite(self.profondeur_rainure_arbre_m):
                t2 = _req_pos("profondeur_rainure_arbre_m", self.profondeur_rainure_arbre_m)
            if _is_finite(self.profondeur_rainure_anneau_m):
                t4 = _req_pos("profondeur_rainure_anneau_m", self.profondeur_rainure_anneau_m)

        rapport["dimensions"].update(
            {
                "b_m": b,
                "h_m": h,
                "profondeur_rainure_arbre_m": t2,
                "profondeur_rainure_anneau_interieur_m": t4,
            }
        )

        # ---------------------------------------------------------------------
        # 7) Longueur utile requise / disponible
        # ---------------------------------------------------------------------
        L_shear = None
        L_bearing = None
        L_req = None

        if T is not None and d is not None and b is not None and tau_cle is not None:
            L_shear = _clavette_longueur_min_cisaillement(T, d, b, tau_cle)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "longueur_min_cisaillement_m",
                "Calculable si couple, diamètre, largeur b et tau admissible sont connus.",
            )

        if T is not None and d is not None and h is not None and sigma_appui is not None:
            L_bearing = _clavette_longueur_min_ecrasement(T, d, h, sigma_appui)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "longueur_min_ecrasement_m",
                "Calculable si couple, diamètre, hauteur h et sigma admissible d'appui sont connus.",
            )

        reqs = [x for x in (L_shear, L_bearing) if x is not None]
        if reqs:
            L_req = max(reqs)

        L_utile_max = None
        if L_dispo is not None:
            L_utile_max = max(0.0, L_dispo - jeu_ext)
            rapport["verifications"]["jeu_extremite_total_m"] = jeu_ext
            rapport["verifications"]["longueur_utile_max_m"] = L_utile_max
            if B is not None and L_dispo > B:
                rapport["notes_modele"].append(
                    "longueur_clavette_disponible_m > largeur_anneau_interieur_m : vérifier qu'une partie de clavette n'empiète pas hors bague."
                )

        effort_tangent = None
        if T is not None and d is not None and d > 0.0:
            effort_tangent = 2.0 * T / d

        rapport["verifications"].update(
            {
                "effort_tangent_theorique_N": effort_tangent,
                "longueur_min_cisaillement_m": L_shear,
                "longueur_min_ecrasement_m": L_bearing,
                "longueur_min_requise_m": L_req,
            }
        )

        if L_req is not None and L_utile_max is not None:
            rapport["verifications"]["check_longueur_ok"] = (L_utile_max >= L_req)
            rapport["verifications"]["check_longueur_ratio"] = (
                (L_utile_max / L_req) if L_req > 0 else None
            )

        # ---------------------------------------------------------------------
        # 8) Vérifications géométriques
        # ---------------------------------------------------------------------
        if b is not None and d is not None:
            rapport["verifications"]["rapport_b_sur_d"] = b / d
        if h is not None and d is not None:
            rapport["verifications"]["rapport_h_sur_d"] = h / d

        if h is not None and t2 is not None and h <= t2:
            _push_inconnue(
                rapport,
                "partielles",
                "profondeur_rainure_arbre_m",
                "La profondeur de rainure arbre ne peut pas être >= à la hauteur totale h de clavette.",
            )

        if h is not None and t2 is not None and t4 is not None:
            rapport["verifications"]["depassement_radial_clavette_m"] = h - t2
            rapport["verifications"]["somme_rainures_m"] = t2 + t4

        # ---------------------------------------------------------------------
        # 9) Bloc CAO
        # ---------------------------------------------------------------------
        chanfrein = None
        rayon_fond_rainure = None
        if b is not None:
            chanfrein = _borne(0.10 * b, 0.0002, 0.0010)
            rayon_fond_rainure = _borne(0.08 * b, 0.0002, 0.0008)

        longueur_cao = L_req if L_req is not None else L_utile_max

        rapport["cao"] = {
            "diametre_portee_m": d,
            "longueur_zone_clavette_m": longueur_cao,
            "clavette": {
                "b_m": b,
                "h_m": h,
                "longueur_m": longueur_cao,
            },
            "rainure_arbre": {
                "largeur_m": b,
                "profondeur_m": t2,
                "rayon_fond_m": rayon_fond_rainure,
            },
            "rainure_anneau_interieur": {
                "largeur_m": b,
                "profondeur_m": t4,
            },
            "chanfrein_clavette_m": chanfrein,
            "note": (
                "La longueur CAO est bornée par la largeur d'anneau intérieur disponible. "
                "Vérifier le montage réel si le roulement est normalement fretté : dans ce cas la clavette peut devenir inutile."
            ),
        }

        # ---------------------------------------------------------------------
        # 10) Entrées
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "couple_transmis_Nm": self.couple_transmis_Nm,
            "diametre_arbre_m": self.diametre_arbre_m,
            "largeur_anneau_interieur_m": self.largeur_anneau_interieur_m,
            "longueur_clavette_disponible_m": self.longueur_clavette_disponible_m,
            "utiliser_din": self.utiliser_din,
            "norme_din_6885": self.norme_din_6885,
            "clavette_b_m": self.clavette_b_m,
            "clavette_h_m": self.clavette_h_m,
            "profondeur_rainure_arbre_m": self.profondeur_rainure_arbre_m,
            "profondeur_rainure_anneau_m": self.profondeur_rainure_anneau_m,
            "materiau_clavette_cle": self.materiau_clavette_cle,
            "limite_elastique_clavette_pa": self.limite_elastique_clavette_pa,
            "materiau_anneau_interieur_cle": self.materiau_anneau_interieur_cle,
            "limite_elastique_anneau_interieur_pa": self.limite_elastique_anneau_interieur_pa,
            "tau_admissible_clavette_pa": self.tau_admissible_clavette_pa,
            "sigma_admissible_appui_pa": self.sigma_admissible_appui_pa,
            "facteur_securite": self.facteur_securite,
            "jeu_extremite_total_m": self.jeu_extremite_total_m,
        }

        _dedup_inconnues(rapport)

        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "ClavetteArbre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport



if __name__ == "__main__":
    from pprint import pprint

    c = ClavetteArbre(
        couple_transmis_Nm=120.0,
        diametre_arbre_m=0.020,
        largeur_anneau_interieur_m=0.016,
        limite_elastique_clavette_pa=500e6,
        limite_elastique_anneau_interieur_pa=900e6,
    )
    pprint(c.analyser(strict=False))

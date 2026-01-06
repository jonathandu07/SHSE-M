# backend/pieces/arbre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
import math


# =============================================================================
# Utilitaires (validation + inconnues)
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v

def _push_inconnue(rapport: Dict[str, Any], kind: str, nom: str, raison: str) -> None:
    rapport["inconnues"][kind].append({"nom": nom, "raison": raison})

def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    for k in ("impossibles", "partielles"):
        seen = set()
        out = []
        for it in rapport["inconnues"][k]:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        rapport["inconnues"][k] = out

def _try_get_float(obj: Any, *names: str) -> Optional[float]:
    for n in names:
        if obj is None:
            return None
        if isinstance(obj, dict) and n in obj and _is_finite(obj[n]):
            return float(obj[n])
        if hasattr(obj, n):
            v = getattr(obj, n)
            if _is_finite(v):
                return float(v)
    return None

def _try_get_int(obj: Any, *names: str) -> Optional[int]:
    for n in names:
        if obj is None:
            return None
        if isinstance(obj, dict) and n in obj:
            v = obj[n]
            if isinstance(v, int):
                return v
            if _is_finite(v):
                return int(v)
        if hasattr(obj, n):
            v = getattr(obj, n)
            if isinstance(v, int):
                return v
            if _is_finite(v):
                return int(v)
    return None


# =============================================================================
# DIN 6885 - recommandation (b, h, profondeurs rainures)
# (Table extraite : domaine typique 6..50 mm)
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
            if i == 0:
                ok = (d_mm >= dmin and d_mm <= dmax)
            else:
                ok = (d_mm > dmin and d_mm <= dmax)
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
            if i == 0:
                ok = (d_mm >= dmin and d_mm <= dmax)
            else:
                ok = (d_mm > dmin and d_mm <= dmax)
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
# Matériaux (sans inventer) : on tente de résoudre via ton module matériaux
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
                if rho is None and _is_finite(getattr(mat, "densite_kg_m3", None)):
                    rho = float(getattr(mat, "densite_kg_m3"))
                if Re is None and _is_finite(getattr(mat, "limite_elastique_pa", None)):
                    Re = float(getattr(mat, "limite_elastique_pa"))
                if E is None and _is_finite(getattr(mat, "module_young_pa", None)):
                    E = float(getattr(mat, "module_young_pa"))
                break
            except Exception:
                continue

    return {"densite_kg_m3": rho, "limite_elastique_pa": Re, "module_young_pa": E}


# =============================================================================
# Formules arbre + clavette
# =============================================================================

def _diam_min_torsion(couple_nm: float, tau_adm_pa: float) -> float:
    # arbre circulaire plein : tau = 16*T / (pi*d^3)
    return (16.0 * couple_nm / (math.pi * tau_adm_pa)) ** (1.0 / 3.0)

def _clavette_longueur_min_cisaillement(T: float, d: float, b: float, tau_adm: float) -> float:
    # F = 2T/d ; tau = F / (b*L) => L >= 2T/(d*b*tau)
    return (2.0 * T) / (d * b * tau_adm)

def _clavette_longueur_min_ecrasement(T: float, d: float, h: float, sigma_adm: float) -> float:
    # F = 2T/d ; sigma = F / ((h/2)*L) => L >= 4T/(d*h*sigma)
    return (4.0 * T) / (d * h * sigma_adm)


@dataclass
class ArbreMoteur:
    """
    Arbre moteur :
    - dimensionnement torsion (si couple + tau admissible disponible),
    - recommandation clavette (DIN 6885) : b, h, profondeurs t2 (arbre) et t4 (moyeu),
    - longueur mini de clavette (si admissibles disponibles),
    - longueur d'arbre : calculable si architecture/empilement défini.

    IMPORTANT :
    - La clavette est sur l'arbre moteur (rainure arbre).
    - Le moyeu (vilbrequin partie latérale) porte la rainure correspondante (profondeur t4).
    """

    cylindre: Optional[Any] = None
    moteur_thermique: Optional[Any] = None
    systeme_complet: Optional[Any] = None
    vilbrequin: Optional[Any] = None  # moyeu côté vilbrequin (si tu as une pièce dédiée)

    couple_max_Nm: Optional[float] = None
    rpm: Optional[float] = None

    diametre_arbre_m: Optional[float] = None

    diametre_passage_arbre_m: Optional[float] = None
    jeu_passage_arbre_m: Optional[float] = None

    nombre_cylindres: Optional[int] = None
    entraxe_cylindres_m: Optional[float] = None
    diametre_externe_cylindre_m: Optional[float] = None
    depassement_cote_boite_m: Optional[float] = None
    depassement_cote_oppose_m: Optional[float] = None  # (sans accent)

    norme_din_6885: int = 1  # 1 ou 2
    utiliser_din: bool = True

    clavette_b_m: Optional[float] = None
    clavette_h_m: Optional[float] = None

    materiau_arbre_cle: Optional[str] = None
    limite_elastique_arbre_pa: Optional[float] = None
    module_young_arbre_pa: Optional[float] = None

    materiau_clavette_cle: Optional[str] = None
    limite_elastique_clavette_pa: Optional[float] = None

    materiau_moyeu_cle: Optional[str] = None
    limite_elastique_moyeu_pa: Optional[float] = None

    facteur_securite: float = 2.0

    # Admissibles :
    # - torsion arbre : tau_admissible_arbre_pa
    # - cisaillement clavette : tau_admissible_clavette_pa
    # - écrasement appui (clavette/moyeu) : sigma_admissible_appui_pa
    tau_admissible_arbre_pa: Optional[float] = None
    tau_admissible_clavette_pa: Optional[float] = None
    sigma_admissible_appui_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "arbre_moteur",
            "entrees": {},
            "recuperations": {},
            "contraintes": {},
            "dimensionnements": {},
            "clavette": {},
            "longueur": {},
            "interface_moyeu_vilbrequin": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        _req_pos("facteur_securite", self.facteur_securite)

        # 1) Couple & rpm
        couple = _try_get_float(self, "couple_max_Nm")
        if couple is None and self.moteur_thermique is not None:
            couple = _try_get_float(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
            if couple is not None:
                rapport["notes_modele"].append("couple_max_Nm récupéré depuis moteur_thermique.")
        if couple is None and self.systeme_complet is not None:
            couple = _try_get_float(self.systeme_complet, "couple_max_Nm", "couple_nm", "couple_Nm")
            if couple is not None:
                rapport["notes_modele"].append("couple_max_Nm récupéré depuis systeme_complet.")

        rpm = _try_get_float(self, "rpm")
        if rpm is None and self.moteur_thermique is not None:
            rpm = _try_get_float(self.moteur_thermique, "rpm", "regime_rpm")
            if rpm is not None:
                rapport["notes_modele"].append("rpm récupéré depuis moteur_thermique.")
        if rpm is None and self.systeme_complet is not None:
            rpm = _try_get_float(self.systeme_complet, "rpm", "regime_rpm")
            if rpm is not None:
                rapport["notes_modele"].append("rpm récupéré depuis systeme_complet.")

        rapport["entrees"]["couple_max_Nm"] = couple
        rapport["entrees"]["rpm"] = rpm
        if couple is None:
            _push_inconnue(rapport, "partielles", "couple_max_Nm", "Nécessaire pour dimensionner d_min torsion et la clavette.")

        # 2) Matériaux (résolution sans déduction automatique)
        mat_arbre = _resoudre_materiau(
            materiau_cle=self.materiau_arbre_cle,
            densite_kg_m3=None,
            limite_elastique_pa=self.limite_elastique_arbre_pa,
            module_young_pa=self.module_young_arbre_pa,
        )
        mat_clavette = _resoudre_materiau(
            materiau_cle=self.materiau_clavette_cle,
            densite_kg_m3=None,
            limite_elastique_pa=self.limite_elastique_clavette_pa,
            module_young_pa=None,
        )
        mat_moyeu = _resoudre_materiau(
            materiau_cle=self.materiau_moyeu_cle,
            densite_kg_m3=None,
            limite_elastique_pa=self.limite_elastique_moyeu_pa,
            module_young_pa=None,
        )
        rapport["recuperations"]["materiau_arbre"] = {"materiau_cle": self.materiau_arbre_cle, **mat_arbre}
        rapport["recuperations"]["materiau_clavette"] = {"materiau_cle": self.materiau_clavette_cle, **mat_clavette}
        rapport["recuperations"]["materiau_moyeu"] = {"materiau_cle": self.materiau_moyeu_cle, **mat_moyeu}

        tau_arbre = float(self.tau_admissible_arbre_pa) if _is_finite(self.tau_admissible_arbre_pa) else None
        tau_cle = float(self.tau_admissible_clavette_pa) if _is_finite(self.tau_admissible_clavette_pa) else None
        sig_appui = float(self.sigma_admissible_appui_pa) if _is_finite(self.sigma_admissible_appui_pa) else None

        rapport["contraintes"]["tau_admissible_arbre_pa"] = tau_arbre
        rapport["contraintes"]["tau_admissible_clavette_pa"] = tau_cle
        rapport["contraintes"]["sigma_admissible_appui_pa"] = sig_appui

        if tau_arbre is None:
            _push_inconnue(rapport, "partielles", "tau_admissible_arbre_pa", "À fournir pour dimensionner d_min torsion.")
        if tau_cle is None:
            _push_inconnue(rapport, "partielles", "tau_admissible_clavette_pa", "À fournir pour longueur mini en cisaillement.")
        if sig_appui is None:
            _push_inconnue(rapport, "partielles", "sigma_admissible_appui_pa", "À fournir pour longueur mini en écrasement (appui clavette/moyeu).")

        # 3) Diamètre : passage + torsion
        d_impose = _try_get_float(self, "diametre_arbre_m")
        d_max_passage = None
        if _is_finite(self.diametre_passage_arbre_m) and _is_finite(self.jeu_passage_arbre_m):
            d_pass = _req_pos("diametre_passage_arbre_m", self.diametre_passage_arbre_m)
            jeu = _req_pos("jeu_passage_arbre_m", self.jeu_passage_arbre_m, strictly=False)
            d_max_passage = d_pass - 2.0 * jeu
            rapport["dimensionnements"]["d_max_passage_m"] = d_max_passage
            if d_max_passage <= 0:
                raise ValueError("Contrainte de passage incohérente : d_max_passage_m <= 0.")
        else:
            _push_inconnue(rapport, "partielles", "d_max_passage_m", "Fournir diametre_passage_arbre_m et jeu_passage_arbre_m pour contraindre le diamètre.")

        d_min_torsion = None
        if couple is not None and tau_arbre is not None:
            d_min_torsion = _diam_min_torsion(_req_pos("couple_max_Nm", couple), _req_pos("tau_admissible_arbre_pa", tau_arbre))
            rapport["dimensionnements"]["d_min_torsion_m"] = d_min_torsion
        else:
            _push_inconnue(rapport, "partielles", "d_min_torsion_m", "Calculable si couple_max_Nm + tau_admissible_arbre_pa connus.")

        d_arbre = d_impose
        if d_arbre is not None:
            d_arbre = _req_pos("diametre_arbre_m", d_arbre)
            if d_min_torsion is not None:
                rapport["dimensionnements"]["check_d_torsion_ok"] = (d_arbre >= d_min_torsion)
                rapport["dimensionnements"]["check_d_torsion_ratio"] = d_arbre / d_min_torsion
            if d_max_passage is not None:
                rapport["dimensionnements"]["check_d_passage_ok"] = (d_arbre <= d_max_passage)
                rapport["dimensionnements"]["check_d_passage_ratio"] = d_arbre / d_max_passage
        else:
            rapport["dimensionnements"]["diametre_arbre_m"] = None
            _push_inconnue(rapport, "impossibles" if strict else "partielles", "diametre_arbre_m", "Non imposé : choisir un diamètre satisfaisant d_min_torsion et d_max_passage (si applicable).")

        # 4) Clavette : DIN ou b/h imposés
        reco = None
        if d_arbre is not None and self.utiliser_din:
            reco = _din6885_recommandation(d_arbre, norme=int(self.norme_din_6885))
            if reco is None:
                _push_inconnue(rapport, "partielles", "din6885", "Diamètre hors domaine 6..50 mm (table extraite) ou norme invalide.")
        elif d_arbre is None and self.utiliser_din:
            _push_inconnue(rapport, "partielles", "din6885", "DIN possible si diametre_arbre_m est imposé.")
        rapport["clavette"]["recommandation_din"] = reco

        b = h = t2 = t4 = None
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
                _push_inconnue(rapport, "impossibles" if strict else "partielles", "clavette_b_h", "Fournir clavette_b_m + clavette_h_m, ou utiliser_din avec un diamètre d'arbre.")

        if t2 is None:
            _push_inconnue(rapport, "partielles", "profondeur_rainure_arbre_m", "Disponible via DIN 6885 ou à fournir explicitement.")
        if t4 is None:
            _push_inconnue(rapport, "partielles", "profondeur_rainure_moyeu_m", "Disponible via DIN 6885 ou à fournir explicitement.")

        rapport["clavette"]["b_m"] = b
        rapport["clavette"]["h_m"] = h
        rapport["clavette"]["profondeur_rainure_arbre_m"] = t2
        rapport["clavette"]["profondeur_rainure_moyeu_m"] = t4

        L_min_shear = None
        L_min_bear = None
        if couple is not None and d_arbre is not None and b is not None and tau_cle is not None:
            L_min_shear = _clavette_longueur_min_cisaillement(_req_pos("couple_max_Nm", couple), d_arbre, b, _req_pos("tau_admissible_clavette_pa", tau_cle))
        else:
            _push_inconnue(rapport, "partielles", "L_min_cisaillement", "Calculable si couple + d + b + tau_admissible_clavette_pa connus.")

        if couple is not None and d_arbre is not None and h is not None and sig_appui is not None:
            L_min_bear = _clavette_longueur_min_ecrasement(_req_pos("couple_max_Nm", couple), d_arbre, h, _req_pos("sigma_admissible_appui_pa", sig_appui))
        else:
            _push_inconnue(rapport, "partielles", "L_min_ecrasement", "Calculable si couple + d + h + sigma_admissible_appui_pa connus.")

        if L_min_shear is not None or L_min_bear is not None:
            L_req = max([x for x in (L_min_shear, L_min_bear) if x is not None])
            rapport["clavette"]["longueur_min_requise_m"] = L_req
            rapport["clavette"]["longueur_min_cisaillement_m"] = L_min_shear
            rapport["clavette"]["longueur_min_ecrasement_m"] = L_min_bear
        else:
            rapport["clavette"]["longueur_min_requise_m"] = None

        rapport["interface_moyeu_vilbrequin"] = {
            "largeur_rainure_moyeu_m": b,
            "profondeur_rainure_moyeu_m": t4,
            "hauteur_clavette_m": h,
            "note": "Le moyeu (vilbrequin partie latérale) doit avoir une rainure compatible.",
        }

        # 5) Longueur arbre : empilement
        n = _try_get_int(self, "nombre_cylindres")
        if n is None and self.systeme_complet is not None:
            n = _try_get_int(self.systeme_complet, "nombre_cylindres")

        entraxe = _try_get_float(self, "entraxe_cylindres_m")
        d_ext = _try_get_float(self, "diametre_externe_cylindre_m")
        if d_ext is None and self.cylindre is not None:
            d_ext = _try_get_float(self.cylindre, "diametre_externe_m", "diametre_exterieur_m")

        dep_boite = _try_get_float(self, "depassement_cote_boite_m")
        # compat rétro si tu avais déjà le champ avec accent ailleurs
        dep_oppose = _try_get_float(self, "depassement_cote_oppose_m") or _try_get_float(self, "depassement_cote_opposé_m")

        rapport["longueur"]["nombre_cylindres"] = n
        rapport["longueur"]["entraxe_cylindres_m"] = entraxe
        rapport["longueur"]["diametre_externe_cylindre_m"] = d_ext
        rapport["longueur"]["depassement_cote_boite_m"] = dep_boite
        rapport["longueur"]["depassement_cote_oppose_m"] = dep_oppose

        L_total = None
        if n is not None and d_ext is not None and dep_boite is not None and dep_oppose is not None:
            n = int(n)
            if n <= 0:
                raise ValueError("nombre_cylindres doit être >= 1.")
            base = _req_pos("diametre_externe_cylindre_m", d_ext) * n
            if n >= 2:
                if entraxe is None:
                    _push_inconnue(rapport, "impossibles" if strict else "partielles", "entraxe_cylindres_m", "Requis si nombre_cylindres >= 2.")
                else:
                    base += _req_pos("entraxe_cylindres_m", entraxe) * (n - 1)
            if entraxe is not None or n == 1:
                L_total = base + _req_pos("depassement_cote_boite_m", dep_boite) + _req_pos("depassement_cote_oppose_m", dep_oppose)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "longueur_totale_arbre_m",
                "Calculable si (nombre_cylindres, diametre_externe_cylindre_m, depassements) connus (+ entraxe si n>=2)."
            )

        rapport["longueur"]["longueur_totale_arbre_m"] = L_total

        _dedup_inconnues(rapport)
        return rapport


# Alias pratique si tu veux faire: from backend.pieces.arbre import Arbre
Arbre = ArbreMoteur

# backend\pieces\bielle.py
# =============================================================================
# CORPS DE BIELLE — SHSE-M (calculatoire, inter-pièces, sans spéculation)
# =============================================================================
# Principe :
# - On calcule tout ce qui est calculable.
# - On récupère explicitement les données des autres pièces (piston, arbre_piston,
#   moteur_thermique, cylindre) si elles existent et si leur format le permet.
# - On n’invente pas : si une donnée manque, elle est déclarée "inconnue".
#
# Sorties principales :
# - Efforts axiaux max/min (si déductibles)
# - Section minimale A_min et (optionnel) dimensions géométriques d'un fût rectangulaire
#   SI tu fournis un rapport largeur/épaisseur (sinon on ne choisit pas).
# - Diamètre équivalent (représentation) d_eq à partir de A_min
# - Flambage Euler (si E, I_min, L et K fournis/déductibles)
# - Pressions moyennes de contact dans les têtes (si d et longueurs de portée fournis)
#
# NOTE IMPORTANTE :
# - La "géométrie complète" d’une bielle (profil I/H, épaisseurs locales, congés, etc.)
#   est une décision de conception. Ici on ne choisit pas ces formes : on calcule
#   les équivalents (A, I_min) et/ou les dimensions SI tu fixes une famille (rectangle + ratio).
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
import math


# =============================================================================
# Utilitaires généraux
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _req_pos(name: str, x: Any, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly and v <= 0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if (not strictly) and v < 0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v

def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": nom, "raison": raison})

def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: List[dict]) -> List[dict]:
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out
    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])

def _deep_get(d: Any, path: Tuple[str, ...]) -> Any:
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        if k not in cur:
            return None
        cur = cur[k]
    return cur

def _first_numeric_from_dict(d: Dict[str, Any], candidates: List[Tuple[str, ...]]) -> Optional[float]:
    for path in candidates:
        v = _deep_get(d, path)
        if _is_finite(v):
            return float(v)
    return None

def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Appelle une méthode standard si elle existe : calculer(), analyser().
    Retourne dict si possible.
    """
    if obj is None:
        return None
    for m in ("calculer", "analyser"):
        try:
            if hasattr(obj, m) and callable(getattr(obj, m)):
                r = getattr(obj, m)()
                if isinstance(r, dict):
                    return r
        except Exception:
            continue
    return None

def _aire_disque(d: float) -> float:
    r = 0.5 * d
    return math.pi * r * r

def _inertie_cercle(d: float) -> float:
    return (math.pi * d**4) / 64.0

def _sigma_axiale(F: float, A: float) -> float:
    return F / A

def _euler_pcrit(E: float, I: float, L: float, K: float) -> float:
    return (math.pi**2) * E * I / ((K * L) ** 2)

def _resoudre_materiau(
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
) -> Dict[str, Optional[float]]:
    """
    Tente de compléter rho, Re, E via backend/materiaux.py (ou variantes).
    Ne crée aucune valeur : si introuvable -> retourne seulement ce qui est fourni.
    """
    rho = densite_kg_m3
    Re = limite_elastique_pa
    E = module_young_pa

    if materiau_cle:
        for modname in (
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                mat = None
                if hasattr(mod, "get_materiau"):
                    mat = mod.get_materiau(materiau_cle)  # type: ignore
                elif hasattr(mod, "MATERIAUX"):
                    mats = getattr(mod, "MATERIAUX")
                    if isinstance(mats, dict):
                        mat = mats.get(materiau_cle)

                if mat is None:
                    continue

                def g(obj: Any, *names: str) -> Optional[float]:
                    for n in names:
                        if isinstance(obj, dict) and n in obj:
                            v = obj.get(n)
                        else:
                            v = getattr(obj, n, None)
                        if v is not None and _is_finite(v):
                            return float(v)
                    return None

                rho = rho if rho is not None else g(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                Re = Re if Re is not None else g(mat, "limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa")
                E = E if E is not None else g(mat, "module_young_pa", "E_pa", "young_pa", "young_modulus_pa")
                break
            except Exception:
                continue

    return {"densite_kg_m3": rho, "limite_elastique_pa": Re, "module_young_pa": E}


# =============================================================================
# Pièce : CorpsBielle
# =============================================================================

@dataclass
class CorpsBielle:
    """
    Corps (fût) de bielle + cohérence géométrique avec petites/grandes têtes.

    IMPORTANT :
    - On ne "choisit" pas une forme : on calcule A_min, d_eq (représentation),
      et si tu imposes une famille (rectangle + ratio), on calcule b/h.
    """

    # Liens vers autres pièces
    piston: Optional[Any] = None
    arbre_piston: Optional[Any] = None
    cylindre: Optional[Any] = None
    moteur_thermique: Optional[Any] = None

    # Longueur de bielle (entraxe) : indispensable pour flambage + masse
    longueur_bielle_m: Optional[float] = None

    # Matériau
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None

    # Sécurité
    facteur_securite: float = 2.0

    # Flambage
    K_flambage: Optional[float] = None  # conditions aux appuis (doit être fourni)

    # Efforts (si non déductibles)
    force_axiale_max_N: Optional[float] = None
    force_axiale_min_N: Optional[float] = None  # si tu as un cycle complet
    effort_lateral_max_N: Optional[float] = None  # pour futurs modèles

    # Géométrie fût : si tu les donnes, on calcule exact
    # A) Rond équivalent imposé
    diametre_equivalent_fut_m: Optional[float] = None
    # B) Rectangle imposé
    largeur_fut_m: Optional[float] = None
    epaisseur_fut_m: Optional[float] = None
    # C) Propriétés directes
    section_fut_m2: Optional[float] = None
    inertie_min_fut_m4: Optional[float] = None

    # Si tu veux "des dimensions géométriques" SANS inventer :
    # -> tu fixes un ratio de forme (b/h) pour un rectangle, et on calcule (b,h) à partir de A.
    ratio_largeur_sur_epaisseur: Optional[float] = None  # b/h

    # Têtes : si non fournis, on tente de déduire
    diametre_axe_piston_m: Optional[float] = None
    longueur_portee_petite_tete_m: Optional[float] = None
    pression_admissible_petite_tete_pa: Optional[float] = None

    diametre_maneton_m: Optional[float] = None
    longueur_portee_grande_tete_m: Optional[float] = None
    pression_admissible_grande_tete_pa: Optional[float] = None

    # -------------------------------------------------------------------------
    # Extraction inter-pièces (sans supposer un format unique)
    # -------------------------------------------------------------------------

    def _extraire_efforts_depuis_piston(self, rapport: Dict[str, Any]) -> Optional[float]:
        rp = _try_call_report(self.piston)
        if not isinstance(rp, dict):
            _push_inconnue(rapport, "partielles", "efforts piston", "Impossible de lire piston (pas de dict retourné).")
            return None

        # On accepte plusieurs conventions de clés
        candidates = [
            ("resultats", "force_gaz_N"),
            ("resultats", "force_pression_piston_max_N"),
            ("dimensionnement", "force_pression_piston_max_N"),
            ("dimensionnement", "force_pression_piston_service_N"),
            ("force_gaz_N",),
            ("force_pression_N",),
        ]
        F = _first_numeric_from_dict(rp, candidates)
        if F is not None:
            rapport["notes_modele"].append("force_axiale_max_N déduite depuis piston.")
        else:
            _push_inconnue(rapport, "partielles", "force piston", "Aucune clé d'effort reconnue dans le rapport piston.")
        return F

    def _extraire_efforts_depuis_moteur_thermique(self, rapport: Dict[str, Any]) -> Optional[float]:
        rm = _try_call_report(self.moteur_thermique)
        if not isinstance(rm, dict):
            _push_inconnue(rapport, "partielles", "efforts moteur_thermique", "Impossible de lire moteur_thermique (pas de dict).")
            return None

        # On cherche explicitement une force bielle ou force axiale équivalente
        candidates = [
            ("resultats", "force_bielle_N"),
            ("resultats", "F_bielle_N"),
            ("resultats", "force_bielle_max_N"),
            ("dimensionnement", "force_bielle_N"),
            ("force_bielle_N",),
            ("F_bielle_N",),
        ]
        F = _first_numeric_from_dict(rm, candidates)
        if F is not None:
            rapport["notes_modele"].append("force_axiale_max_N déduite depuis moteur_thermique.")
        else:
            _push_inconnue(rapport, "partielles", "force bielle", "Aucune clé force_bielle reconnue dans moteur_thermique.")
        return F

    def _extraire_diametre_axe_depuis_arbre_piston(self, rapport: Dict[str, Any]) -> Optional[float]:
        # 1) attributs directs
        for attr in (
            "diametre_portee_coussinet_m",
            "diametre_fut_central_m",
            "diametre_teton_gauche_m",
            "diametre_teton_droit_m",
            "diametre_arbre_m",
        ):
            try:
                v = getattr(self.arbre_piston, attr, None)
                if _is_finite(v):
                    rapport["notes_modele"].append(f"diametre_axe_piston_m déduit depuis arbre_piston.{attr}.")
                    return float(v)
            except Exception:
                pass

        # 2) rapport analyser()
        ra = _try_call_report(self.arbre_piston)
        if isinstance(ra, dict):
            candidates = [
                ("geometrie", "diametre_portee_coussinet_m"),
                ("geometrie", "diametre_fut_central_m"),
                ("geometrie", "diametre_teton_gauche_m"),
                ("geometrie", "diametre_teton_droit_m"),
                ("geometrie", "diametre_arbre_m"),
                ("entrees", "diametre_portee_coussinet_m"),
                ("entrees", "diametre_fut_central_m"),
                ("entrees", "diametre_arbre_m"),
            ]
            d = _first_numeric_from_dict(ra, candidates)
            if d is not None:
                rapport["notes_modele"].append("diametre_axe_piston_m déduit depuis le rapport arbre_piston.")
                return d

        _push_inconnue(
            rapport,
            "partielles",
            "diametre_axe_piston_m",
            "Impossible de déduire depuis arbre_piston (attributs/rapport).",
        )
        return None

    def _extraire_longueur_bielle(self, rapport: Dict[str, Any]) -> Optional[float]:
        # Sans inventer : seulement si autre pièce fournit explicitement une longueur
        # (ex: moteur_thermique.longueur_bielle_m ou cylindre.XXX)
        for src in (self.moteur_thermique, self.cylindre):
            if src is None:
                continue
            for attr in ("longueur_bielle_m", "entraxe_bielle_m"):
                try:
                    v = getattr(src, attr, None)
                    if _is_finite(v):
                        rapport["notes_modele"].append(f"longueur_bielle_m déduite depuis {src.__class__.__name__}.{attr}.")
                        return float(v)
                except Exception:
                    pass

            r = _try_call_report(src)
            if isinstance(r, dict):
                candidates = [
                    ("entrees", "longueur_bielle_m"),
                    ("geometrie", "longueur_bielle_m"),
                    ("resultats", "longueur_bielle_m"),
                ]
                v = _first_numeric_from_dict(r, candidates)
                if v is not None:
                    rapport["notes_modele"].append("longueur_bielle_m déduite depuis un rapport (moteur_thermique/cylindre).")
                    return v

        _push_inconnue(
            rapport,
            "impossibles",
            "longueur_bielle_m",
            "Nécessaire pour flambage/masse. Non fournie et non déductible d'une autre pièce.",
        )
        return None

    # -------------------------------------------------------------------------
    # Calcul principal
    # -------------------------------------------------------------------------

    def calculer(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "corps_bielle",
            "entrees": {},
            "materiau": {},
            "efforts": {},
            "geometrie": {
                "fut": {},
                "petite_tete": {},
                "grande_tete": {},
            },
            "dimensionnements": {},
            "contraintes": {},
            "flambage": {},
            "contacts_tetes": {},
            "masse": {},
            "notes_modele": [],
            "inconnues": {"impossibles": [], "partielles": []},
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # 1) Matériau
        props = _resoudre_materiau(self.materiau_cle, self.densite_kg_m3, self.limite_elastique_pa, self.module_young_pa)
        rho = props["densite_kg_m3"]
        Re = props["limite_elastique_pa"]
        E = props["module_young_pa"]

        rapport["materiau"] = {
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": rho,
            "limite_elastique_pa": Re,
            "module_young_pa": E,
        }

        # 2) Efforts : priorité à l'entrée, sinon moteur_thermique, sinon piston
        Fmax = self.force_axiale_max_N
        Fmin = self.force_axiale_min_N

        if Fmax is None and self.moteur_thermique is not None:
            Fmax = self._extraire_efforts_depuis_moteur_thermique(rapport)

        if Fmax is None and self.piston is not None:
            Fmax = self._extraire_efforts_depuis_piston(rapport)

        if Fmax is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "force_axiale_max_N",
                "Indispensable pour dimensionner la bielle. Fournir force_axiale_max_N, ou rendre déductible via piston/moteur_thermique.",
            )

        rapport["efforts"] = {
            "force_axiale_max_N": Fmax,
            "force_axiale_min_N": Fmin,
            "effort_lateral_max_N": self.effort_lateral_max_N,
        }

        # 3) Longueur de bielle : entrée ou déduction explicite
        L = self.longueur_bielle_m
        if L is None:
            L = self._extraire_longueur_bielle(rapport)
        else:
            L = _req_pos("longueur_bielle_m", L)

        # 4) Diamètre axe piston : entrée ou déduction arbre_piston
        d_axe = self.diametre_axe_piston_m
        if d_axe is None and self.arbre_piston is not None:
            d_axe = self._extraire_diametre_axe_depuis_arbre_piston(rapport)
        elif d_axe is not None:
            d_axe = _req_pos("diametre_axe_piston_m", d_axe)

        if d_axe is None:
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_axe_piston_m",
                "Requis pour pression de contact petite tête.",
            )

        # Maneton : pas déductible sans vilebrequin -> entrée
        d_maneton = self.diametre_maneton_m
        if d_maneton is None:
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_maneton_m",
                "Requis pour pression de contact grande tête. Non déductible sans vilebrequin/maneton.",
            )
        else:
            d_maneton = _req_pos("diametre_maneton_m", d_maneton)

        rapport["geometrie"]["petite_tete"]["diametre_axe_piston_m"] = d_axe
        rapport["geometrie"]["grande_tete"]["diametre_maneton_m"] = d_maneton

        # 5) Géométrie fût : déterminer A et I_min selon ce que tu fournis
        A: Optional[float] = None
        Imin: Optional[float] = None
        modele_section: Optional[str] = None

        # C) direct
        if self.section_fut_m2 is not None:
            A = _req_pos("section_fut_m2", self.section_fut_m2)
            modele_section = "section_directe"
            rapport["geometrie"]["fut"]["section_fut_m2"] = A
            if self.inertie_min_fut_m4 is not None:
                Imin = _req_pos("inertie_min_fut_m4", self.inertie_min_fut_m4)
                rapport["geometrie"]["fut"]["inertie_min_fut_m4"] = Imin
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "inertie_min_fut_m4",
                    "Indispensable pour flambage si section fournie sans inertie.",
                )

        # B) rectangle
        elif self.largeur_fut_m is not None and self.epaisseur_fut_m is not None:
            b = _req_pos("largeur_fut_m", self.largeur_fut_m)
            h = _req_pos("epaisseur_fut_m", self.epaisseur_fut_m)
            A = b * h
            # inertie minimale : min(b*h^3/12, h*b^3/12)
            I1 = (b * h**3) / 12.0
            I2 = (h * b**3) / 12.0
            Imin = min(I1, I2)
            modele_section = "rectangle"
            rapport["geometrie"]["fut"].update(
                {"largeur_fut_m": b, "epaisseur_fut_m": h, "section_fut_m2": A, "inertie_min_fut_m4": Imin}
            )

        # A) rond équivalent imposé
        elif self.diametre_equivalent_fut_m is not None:
            d_eq = _req_pos("diametre_equivalent_fut_m", self.diametre_equivalent_fut_m)
            A = _aire_disque(d_eq)
            Imin = _inertie_cercle(d_eq)
            modele_section = "rond_equivalent"
            rapport["geometrie"]["fut"].update(
                {"diametre_equivalent_fut_m": d_eq, "section_fut_m2": A, "inertie_min_fut_m4": Imin}
            )

        # Sinon : dimensionnement minimal par traction/compression à partir de Fmax et Re
        else:
            if Fmax is not None and Re is not None:
                sigma_adm = float(Re) / FS
                A_min = abs(float(Fmax)) / sigma_adm
                rapport["dimensionnements"]["section_min_calculee_m2"] = A_min
                rapport["dimensionnements"]["critere_section"] = "sigma_axiale <= Re/FS"
                d_eq_min = math.sqrt(4.0 * A_min / math.pi)
                rapport["dimensionnements"]["diametre_equivalent_min_m"] = d_eq_min
                rapport["notes_modele"].append(
                    "Diamètre équivalent calculé = représentation (section circulaire équivalente), pas un choix de conception."
                )

                # Si tu fournis un ratio rectangle b/h, alors on peut donner des dimensions géométriques
                if self.ratio_largeur_sur_epaisseur is not None:
                    r = _req_pos("ratio_largeur_sur_epaisseur", self.ratio_largeur_sur_epaisseur)
                    # A = b*h et b = r*h => A = r*h^2 => h = sqrt(A/r), b = r*h
                    h = math.sqrt(A_min / r)
                    b = r * h
                    # inertie min du rectangle (axe faible) :
                    I1 = (b * h**3) / 12.0
                    I2 = (h * b**3) / 12.0
                    Imin_rect = min(I1, I2)
                    rapport["dimensionnements"]["rectangle_equivalent"] = {
                        "ratio_b_sur_h": r,
                        "largeur_b_m": b,
                        "epaisseur_h_m": h,
                        "section_m2": A_min,
                        "inertie_min_m4": Imin_rect,
                        "note": "Dimensions calculées uniquement car ratio fourni (pas inventé).",
                    }
            else:
                if Fmax is None:
                    _push_inconnue(rapport, "impossibles", "dimensionnement section fût", "Nécessite force_axiale_max_N.")
                if Re is None:
                    _push_inconnue(rapport, "impossibles", "dimensionnement section fût", "Nécessite limite_elastique_pa (ou materiau_cle résoluble).")

        # 6) Contraintes axiales si A connu
        if A is not None and Fmax is not None:
            sigma = _sigma_axiale(float(Fmax), float(A))
            sigma_adm = (float(Re) / FS) if Re is not None else None
            marge = (sigma_adm / abs(sigma)) if (sigma_adm is not None and sigma != 0) else None
            rapport["contraintes"]["axial"] = {
                "modele_section": modele_section,
                "sigma_axiale_pa_sur_Fmax": sigma,
                "sigma_admissible_pa": sigma_adm,
                "marge_axiale": marge,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contrainte axiale",
                "Calculable si section (ou géométrie fût) et force_axiale_max_N sont connues.",
            )

        # 7) Flambage Euler (si Imin, E, L, K fournis)
        # Remarque : si tu as seulement A_min, on ne peut pas inventer Imin.
        if Imin is not None and E is not None and L is not None and self.K_flambage is not None:
            K = _req_pos("K_flambage", self.K_flambage)
            Pcr = _euler_pcrit(float(E), float(Imin), float(L), float(K))
            marge_flamb = (Pcr / abs(float(Fmax))) if (Fmax is not None and float(Fmax) != 0.0) else None
            rapport["flambage"] = {
                "modele": "Euler (colonne équivalente)",
                "inertie_min_fut_m4": Imin,
                "module_young_pa": E,
                "longueur_bielle_m": L,
                "K_flambage": K,
                "charge_critique_N": Pcr,
                "marge_sur_Fmax": marge_flamb,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "flambage",
                "Calculable si inertie_min_fut_m4 (ou géométrie), module_young_pa, longueur_bielle_m et K_flambage sont fournis.",
            )

        # 8) Contacts têtes : p = F / (d * Lportee)
        if Fmax is not None and d_axe is not None and self.longueur_portee_petite_tete_m is not None:
            Lp = _req_pos("longueur_portee_petite_tete_m", self.longueur_portee_petite_tete_m)
            p = abs(float(Fmax)) / (float(d_axe) * float(Lp))
            ok = None
            marge = None
            if self.pression_admissible_petite_tete_pa is not None:
                padm = _req_pos("pression_admissible_petite_tete_pa", self.pression_admissible_petite_tete_pa)
                ok = p <= (padm / FS)
                marge = (padm / FS) / p if p > 0 else None
            rapport["contacts_tetes"]["petite_tete"] = {
                "diametre_axe_m": d_axe,
                "longueur_portee_m": Lp,
                "pression_moyenne_pa": p,
                "pression_admissible_pa": self.pression_admissible_petite_tete_pa,
                "ok": ok,
                "marge": marge,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contact petite tête",
                "Calculable si force_axiale_max_N, diametre_axe_piston_m et longueur_portee_petite_tete_m sont fournis/déductibles.",
            )

        if Fmax is not None and d_maneton is not None and self.longueur_portee_grande_tete_m is not None:
            Lg = _req_pos("longueur_portee_grande_tete_m", self.longueur_portee_grande_tete_m)
            p = abs(float(Fmax)) / (float(d_maneton) * float(Lg))
            ok = None
            marge = None
            if self.pression_admissible_grande_tete_pa is not None:
                padm = _req_pos("pression_admissible_grande_tete_pa", self.pression_admissible_grande_tete_pa)
                ok = p <= (padm / FS)
                marge = (padm / FS) / p if p > 0 else None
            rapport["contacts_tetes"]["grande_tete"] = {
                "diametre_maneton_m": d_maneton,
                "longueur_portee_m": Lg,
                "pression_moyenne_pa": p,
                "pression_admissible_pa": self.pression_admissible_grande_tete_pa,
                "ok": ok,
                "marge": marge,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contact grande tête",
                "Calculable si force_axiale_max_N, diametre_maneton_m et longueur_portee_grande_tete_m sont fournis.",
            )

        # 9) Masse (modèle minimal) : m ≈ rho * A * L (fût seul, sans surépaisseurs des têtes)
        if rho is not None and A is not None and L is not None:
            V = float(A) * float(L)
            m = float(rho) * V
            rapport["masse"] = {
                "modele": "m = rho * section_fut * longueur_bielle (fût seul, têtes non modélisées)",
                "volume_fut_m3": V,
                "masse_fut_kg": m,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "masse",
                "Calculable si densite_kg_m3 (ou materiau_cle), section (ou géométrie) et longueur_bielle_m sont connus.",
            )

        # 10) Trace entrées
        rapport["entrees"] = {
            "longueur_bielle_m": self.longueur_bielle_m,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "limite_elastique_pa": self.limite_elastique_pa,
            "module_young_pa": self.module_young_pa,
            "facteur_securite": self.facteur_securite,
            "K_flambage": self.K_flambage,
            "force_axiale_max_N": self.force_axiale_max_N,
            "force_axiale_min_N": self.force_axiale_min_N,
            "effort_lateral_max_N": self.effort_lateral_max_N,
            "diametre_equivalent_fut_m": self.diametre_equivalent_fut_m,
            "largeur_fut_m": self.largeur_fut_m,
            "epaisseur_fut_m": self.epaisseur_fut_m,
            "section_fut_m2": self.section_fut_m2,
            "inertie_min_fut_m4": self.inertie_min_fut_m4,
            "ratio_largeur_sur_epaisseur": self.ratio_largeur_sur_epaisseur,
            "diametre_axe_piston_m": self.diametre_axe_piston_m,
            "longueur_portee_petite_tete_m": self.longueur_portee_petite_tete_m,
            "pression_admissible_petite_tete_pa": self.pression_admissible_petite_tete_pa,
            "diametre_maneton_m": self.diametre_maneton_m,
            "longueur_portee_grande_tete_m": self.longueur_portee_grande_tete_m,
            "pression_admissible_grande_tete_pa": self.pression_admissible_grande_tete_pa,
        }

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "CorpsBielle(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# =============================================================================
# Exemple minimal (à supprimer en prod)
# =============================================================================
if __name__ == "__main__":
    # IMPORTANT : ceci n'invente rien. Si tes autres pièces ne retournent pas un dict exploitable,
    # les champs resteront en inconnues.
    try:
        from backend.pieces.piston import Piston  # type: ignore
        piston = Piston(
            diametre_piston_m=0.085,
            hauteur_piston_m=0.05,
            pression_cote_froid_pa=6e5,
            temperature_cote_froid_k=300.0,
            course_m=0.085,
            rpm=3000.0,
        )
    except Exception:
        piston = None

    try:
        from backend.pieces.arbre_piston import ArbrePiston  # type: ignore
        arbre = ArbrePiston(
            diametre_portee_coussinet_m=0.02,
        )
    except Exception:
        arbre = None

    b = CorpsBielle(
        piston=piston,
        arbre_piston=arbre,
        longueur_bielle_m=0.14,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        facteur_securite=2.0,
        K_flambage=1.0,
        # Pour obtenir des "dimensions géométriques" sans inventer : impose un ratio rectangle
        ratio_largeur_sur_epaisseur=2.0,
        # Contacts
        longueur_portee_petite_tete_m=0.018,
        diametre_maneton_m=0.03,
        longueur_portee_grande_tete_m=0.02,
    )

    from pprint import pprint
    pprint(b.calculer(strict=False))

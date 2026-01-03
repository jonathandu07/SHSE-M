# backend/pieces/arbre_piston.py
# =============================================================================
# ARBRE DE PISTON — SHSE-M
# =============================================================================
# Rôle :
# - Lien mécanique entre le piston et la bielle (axe/goujon/“arbre” de piston).
# - Peut porter un coussinet côté bielle (réduction frottement/usure).
# - Taraudé de chaque côté si tu le fixes au piston par vis.
#
# IMPORTANT (conformément à “rien inventer”) :
# - Ce module calcule tout ce qui est calculable à partir des entrées.
# - Toute décision “de conception” (choix d’un diamètre normalisé, nombre de vis, etc.)
#   n’est PAS inventée : si tu ne donnes pas la norme/le choix, on te renvoie l’inconnue.
# =============================================================================

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


def _req_pos(name: str, x: Any, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0:
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


def _aire_disque(d: float) -> float:
    r = 0.5 * d
    return math.pi * r * r


# =============================================================================
# Résolution matériau (utilise materiaux.py si présent)
# =============================================================================

def _resoudre_materiau(
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
) -> Dict[str, Optional[float]]:
    """
    Tente de compléter rho, Re, E via backend/materiaux.py (ou variantes),
    sans rien inventer : si introuvable -> valeurs fournies seulement.
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
                # On accepte plusieurs styles de base de données matériaux
                # - dict MATERIAUX[materiau_cle]
                # - fonction get_materiau(cle)
                mat = None
                if hasattr(mod, "get_materiau"):
                    mat = mod.get_materiau(materiau_cle)  # type: ignore
                elif hasattr(mod, "MATERIAUX"):
                    mats = getattr(mod, "MATERIAUX")
                    if isinstance(mats, dict):
                        mat = mats.get(materiau_cle)

                if mat is None:
                    continue

                # Lecture souple
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
# Contraintes (arbres/axes)
# =============================================================================

def _sigma_axiale(F: float, A: float) -> float:
    return F / A


def _tau_cisaillement(F: float, A: float) -> float:
    return F / A


def _sigma_flexion(M: float, d: float) -> float:
    # Section ronde pleine : W = π d^3 / 32
    W = (math.pi * d**3) / 32.0
    return M / W


def _von_mises_sigma_tau(sigma: float, tau: float) -> float:
    # von Mises en traction + cisaillement (hypothèse)
    return math.sqrt(sigma**2 + 3.0 * tau**2)


def _inertie_cercle(d: float) -> float:
    # I = π d^4 / 64
    return (math.pi * d**4) / 64.0


def _euler_pcrit(E: float, I: float, L: float, K: float) -> float:
    # Pcr = π² E I / (K L)²
    return (math.pi**2) * E * I / ((K * L) ** 2)


# =============================================================================
# Pièce : ArbrePiston
# =============================================================================

@dataclass
class ArbrePiston:
    """
    Objectif :
    - Déduire un maximum de grandeurs calculables (contraintes, diamètres minimaux, inerties, masse, flambage).
    - S’appuyer sur les autres pièces si elles sont fournies (Piston -> effort axial, etc.).
    - Ne PAS choisir de standards (M8/M10, nombre de vis…) sans entrée explicite.
    """

    # Liens vers pièces (optionnels)
    piston: Optional[Any] = None          # idéalement backend.pieces.piston.Piston
    bielle: Optional[Any] = None          # si tu as une pièce bielle plus tard
    cylindre: Optional[Any] = None        # si besoin de cohérence géométrique

    # Géométrie “arbre/axe”
    diametre_arbre_m: Optional[float] = None
    longueur_libre_m: Optional[float] = None     # longueur libre en compression (flambage) si applicable
    entraxe_appuis_m: Optional[float] = None     # portée entre appuis (pour flexion si charge latérale)
    bras_levier_charge_m: Optional[float] = None # si effort latéral appliqué avec un bras de levier (moment)

    # Efforts (si pas déductibles)
    force_axiale_N: Optional[float] = None       # traction/compression
    force_cisaillement_N: Optional[float] = None # effort transversal
    moment_flexion_Nm: Optional[float] = None    # si déjà connu

    # Taraudages / fixation au piston (sans inventer)
    # -> si tu veux dimensionner, il faut fournir : nombre_vis, effort_par_vis ou effort_total, classe/limite
    nombre_vis: Optional[int] = None
    diametre_noyau_filet_m: Optional[float] = None   # diamètre “résistant” du taraudage (noyau)
    longueur_engagement_filet_m: Optional[float] = None
    resistance_cisaillement_filet_pa: Optional[float] = None  # matériau taraudé (piston ou arbre)

    # Coussinet (si présent)
    diametre_portee_coussinet_m: Optional[float] = None
    longueur_coussinet_m: Optional[float] = None
    pression_admissible_coussinet_pa: Optional[float] = None  # si tu as un module coussinet plus tard

    # Matériau arbre
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None

    # Calcul
    facteur_securite: float = 2.0
    # flambage : K (coefficient longueur équivalente). On ne “devine” pas : entrée, sinon inconnue.
    K_flambage: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "materiau": {},
            "geometrie": {},
            "efforts": {},
            "dimensionnement": {},
            "contraintes": {},
            "flambage": {},
            "coussinet": {},
            "fixation_taraudee": {},
            "masse": {},
            "inerties": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ----------------------------
        # 1) Matériau (réduction inconnues)
        # ----------------------------
        props_mat = _resoudre_materiau(
            self.materiau_cle,
            self.densite_kg_m3,
            self.limite_elastique_pa,
            self.module_young_pa,
        )
        rho = props_mat["densite_kg_m3"]
        Re = props_mat["limite_elastique_pa"]
        E = props_mat["module_young_pa"]

        rapport["materiau"] = {
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": rho,
            "limite_elastique_pa": Re,
            "module_young_pa": E,
        }

        # ----------------------------
        # 2) Efforts : déduction depuis le piston si possible
        # ----------------------------
        F_ax = self.force_axiale_N
        F_sh = self.force_cisaillement_N
        M = self.moment_flexion_Nm

        if self.piston is not None:
            # On tente de récupérer des résultats déjà calculés dans piston.calculer()
            try:
                if hasattr(self.piston, "calculer") and callable(self.piston.calculer):
                    r_p = self.piston.calculer()  # type: ignore
                    # piston.py met typiquement les résultats dans r_p["resultats"]
                    bloc = r_p.get("resultats", {}) if isinstance(r_p, dict) else {}
                    # force gaz
                    if F_ax is None and _is_finite(bloc.get("force_gaz_N")):
                        F_ax = float(bloc["force_gaz_N"])
                        rapport["notes_modele"].append("force_axiale_N déduite de piston.calculer().resultats.force_gaz_N")
                    # effort latéral jupe (utile si on veut approx cisaillement)
                    if F_sh is None and _is_finite(bloc.get("force_laterale_jupe_N")):
                        F_sh = float(bloc["force_laterale_jupe_N"])
                        rapport["notes_modele"].append("force_cisaillement_N déduite de piston.calculer().resultats.force_laterale_jupe_N")
            except Exception:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "efforts depuis piston",
                    "Impossible de déduire via piston.calculer() (erreur d'appel ou format inattendu).",
                )

        # Moment flexion : déductible si effort transversal et bras de levier fournis
        if M is None and F_sh is not None and self.bras_levier_charge_m is not None:
            a = _req_pos("bras_levier_charge_m", self.bras_levier_charge_m, strictly=False)
            M = F_sh * a
            rapport["notes_modele"].append("moment_flexion_Nm déduit : M = F_cisaillement * bras_levier")

        rapport["efforts"] = {
            "force_axiale_N": F_ax,
            "force_cisaillement_N": F_sh,
            "moment_flexion_Nm": M,
        }

        # ----------------------------
        # 3) Géométrie : diamètre connu ou à dimensionner
        # ----------------------------
        d = self.diametre_arbre_m
        if d is not None:
            d = _req_pos("diametre_arbre_m", d)
            rapport["geometrie"]["diametre_arbre_m"] = d
        else:
            rapport["geometrie"]["diametre_arbre_m"] = None

        # Inerties / sections si diamètre connu
        if d is not None:
            A = _aire_disque(d)
            I = _inertie_cercle(d)
            Jp = (math.pi * d**4) / 32.0  # polaire cercle plein
            rapport["inerties"] = {
                "section_m2": A,
                "inertie_flexion_I_m4": I,
                "inertie_polaire_J_m4": Jp,
            }

        # ----------------------------
        # 4) Dimensionnement minimal (si d inconnu)
        # ----------------------------
        # On dimensionne par contrainte von Mises <= Re/FS si Re connu
        if d is None:
            if Re is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "dimensionnement diamètre",
                    "Impossible sans limite_elastique_pa (ou materiau_cle résoluble).",
                )
            else:
                # On dimensionne sur un cas “charge composée” si F_ax/F_sh/M connus.
                # Sans l’un d’eux, on dimensionne sur ceux disponibles.
                sigma_allow = Re / FS

                # Fonction de recherche (binaire) du diamètre mini
                def vm_for_d(dtest: float) -> float:
                    Atest = _aire_disque(dtest)
                    sigma = 0.0
                    tau = 0.0
                    if F_ax is not None:
                        sigma += _sigma_axiale(F_ax, Atest)
                    if M is not None:
                        sigma += _sigma_flexion(M, dtest)
                    if F_sh is not None:
                        tau += _tau_cisaillement(F_sh, Atest)
                    return _von_mises_sigma_tau(sigma, tau)

                # Il faut au moins un effort pour dimensionner
                if F_ax is None and F_sh is None and M is None:
                    _push_inconnue(
                        rapport,
                        "impossibles",
                        "dimensionnement diamètre",
                        "Aucun effort connu (force_axiale_N / force_cisaillement_N / moment_flexion_Nm).",
                    )
                else:
                    # bornes
                    dmin = 1e-4  # 0.1 mm (borne technique pure)
                    dmax = 1.0   # 1 m (borne large)
                    # s'assurer que dmax suffit
                    if vm_for_d(dmax) > sigma_allow:
                        _push_inconnue(
                            rapport,
                            "impossibles",
                            "dimensionnement diamètre",
                            "Même d=1 m ne respecte pas la contrainte admissible (vérifier charges / matériau).",
                        )
                    else:
                        # binaire
                        for _ in range(80):
                            mid = 0.5 * (dmin + dmax)
                            if vm_for_d(mid) <= sigma_allow:
                                dmax = mid
                            else:
                                dmin = mid
                        d_calc = dmax
                        d = d_calc
                        rapport["dimensionnement"]["diametre_min_calcule_m"] = d_calc
                        rapport["dimensionnement"]["critere"] = "von_mises <= Re/FS"
                        rapport["dimensionnement"]["sigma_admissible_pa"] = sigma_allow

                        # On calcule aussi les grandeurs associées
                        A = _aire_disque(d)
                        I = _inertie_cercle(d)
                        Jp = (math.pi * d**4) / 32.0
                        rapport["inerties"] = {
                            "section_m2": A,
                            "inertie_flexion_I_m4": I,
                            "inertie_polaire_J_m4": Jp,
                        }

                        # Contraintes correspondantes
                        sigma_ax = _sigma_axiale(F_ax, A) if F_ax is not None else 0.0
                        sigma_b = _sigma_flexion(M, d) if M is not None else 0.0
                        tau = _tau_cisaillement(F_sh, A) if F_sh is not None else 0.0
                        sigma_eq = _von_mises_sigma_tau(sigma_ax + sigma_b, tau)
                        marge = sigma_allow / sigma_eq if sigma_eq > 0 else None

                        rapport["contraintes"] = {
                            "sigma_axiale_pa": sigma_ax if F_ax is not None else None,
                            "sigma_flexion_pa": sigma_b if M is not None else None,
                            "tau_cisaillement_pa": tau if F_sh is not None else None,
                            "sigma_von_mises_pa": sigma_eq,
                            "marge_von_mises": marge,
                        }

        # Si d connu, on calcule contraintes et marges (si charges + Re connus)
        if d is not None:
            A = _aire_disque(d)
            sigma_ax = _sigma_axiale(F_ax, A) if F_ax is not None else None
            tau = _tau_cisaillement(F_sh, A) if F_sh is not None else None
            sigma_b = _sigma_flexion(M, d) if M is not None else None

            if sigma_ax is None and sigma_b is None and tau is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "contraintes arbre",
                    "Calculables si force_axiale_N / force_cisaillement_N / moment_flexion_Nm sont fournis.",
                )
            else:
                s_total = 0.0
                if sigma_ax is not None:
                    s_total += sigma_ax
                if sigma_b is not None:
                    s_total += sigma_b
                t_total = float(tau) if tau is not None else 0.0
                sigma_eq = _von_mises_sigma_tau(s_total, t_total)

                marge = None
                sigma_allow = None
                if Re is not None:
                    sigma_allow = Re / FS
                    marge = sigma_allow / sigma_eq if sigma_eq > 0 else None
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "marge matériau",
                        "Marge calculable si limite_elastique_pa (ou materiau_cle résoluble) est fourni.",
                    )

                rapport["contraintes"] = {
                    "sigma_axiale_pa": sigma_ax,
                    "sigma_flexion_pa": sigma_b,
                    "tau_cisaillement_pa": tau,
                    "sigma_von_mises_pa": sigma_eq,
                    "sigma_admissible_pa": sigma_allow,
                    "marge_von_mises": marge,
                }

        # ----------------------------
        # 5) Flambage (compression)
        # ----------------------------
        # Calculable si : d, E, longueur_libre_m, K_flambage
        if d is not None and E is not None and self.longueur_libre_m is not None and self.K_flambage is not None:
            L = _req_pos("longueur_libre_m", self.longueur_libre_m)
            K = _req_pos("K_flambage", self.K_flambage)
            I = _inertie_cercle(d)
            Pcr = _euler_pcrit(E, I, L, K)

            rapport["flambage"] = {
                "longueur_libre_m": L,
                "K_flambage": K,
                "charge_critique_euler_N": Pcr,
                "marge_flambage": (Pcr / abs(F_ax)) if (F_ax is not None and F_ax != 0) else None,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "flambage",
                "Calculable si diametre_arbre_m, module_young_pa, longueur_libre_m et K_flambage sont fournis.",
            )

        # ----------------------------
        # 6) Coussinet : pression de contact (si données)
        # ----------------------------
        if self.diametre_portee_coussinet_m is not None and self.longueur_coussinet_m is not None and F_sh is not None:
            db = _req_pos("diametre_portee_coussinet_m", self.diametre_portee_coussinet_m)
            lb = _req_pos("longueur_coussinet_m", self.longueur_coussinet_m)

            # Pression moyenne projetée : p = F / (d * L) (contact “journal bearing” approx)
            p_b = abs(F_sh) / (db * lb)
            ok = None
            marge = None
            if self.pression_admissible_coussinet_pa is not None:
                p_adm = _req_pos("pression_admissible_coussinet_pa", self.pression_admissible_coussinet_pa)
                ok = p_b <= p_adm
                marge = p_adm / p_b if p_b > 0 else None

            rapport["coussinet"] = {
                "diametre_portee_m": db,
                "longueur_m": lb,
                "pression_contact_pa": p_b,
                "pression_admissible_pa": self.pression_admissible_coussinet_pa,
                "ok_pression": ok,
                "marge_pression": marge,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "coussinet",
                "Calculable si diametre_portee_coussinet_m, longueur_coussinet_m et force_cisaillement_N sont fournis.",
            )

        # ----------------------------
        # 7) Fixation taraudée au piston (sans inventer le nombre de vis / diamètre)
        # ----------------------------
        # On peut calculer :
        # - effort par vis
        # - contrainte en traction au noyau du filet (si diametre_noyau_filet_m)
        # - cisaillement filet (si longueur_engagement + résistance cisaillement)
        if self.nombre_vis is not None and F_ax is not None:
            n = int(self.nombre_vis)
            if n <= 0:
                raise ValueError("nombre_vis doit être > 0.")
            F_par_vis = abs(F_ax) / n
            rapport["fixation_taraudee"]["nombre_vis"] = n
            rapport["fixation_taraudee"]["effort_axial_total_N"] = abs(F_ax)
            rapport["fixation_taraudee"]["effort_par_vis_N"] = F_par_vis

            # traction noyau
            if self.diametre_noyau_filet_m is not None:
                dn = _req_pos("diametre_noyau_filet_m", self.diametre_noyau_filet_m)
                Acore = _aire_disque(dn)
                sigma_core = F_par_vis / Acore
                rapport["fixation_taraudee"]["diametre_noyau_filet_m"] = dn
                rapport["fixation_taraudee"]["contrainte_traction_noyau_pa"] = sigma_core

                # marge si Re connu
                if Re is not None:
                    sigma_allow = Re / FS
                    rapport["fixation_taraudee"]["sigma_admissible_pa"] = sigma_allow
                    rapport["fixation_taraudee"]["marge_traction_noyau"] = sigma_allow / sigma_core if sigma_core > 0 else None
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "marge traction taraudage",
                        "Calculable si limite_elastique_pa (ou materiau_cle) est fourni pour la pièce en traction.",
                    )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "traction noyau filet",
                    "Calculable si diametre_noyau_filet_m est fourni (dépend du standard de vis).",
                )

            # cisaillement filet (approx) : A_shear ~ π * d_moyen * L_engagement
            if self.longueur_engagement_filet_m is not None and self.resistance_cisaillement_filet_pa is not None and self.diametre_noyau_filet_m is not None:
                Leng = _req_pos("longueur_engagement_filet_m", self.longueur_engagement_filet_m)
                tau_adm = _req_pos("resistance_cisaillement_filet_pa", self.resistance_cisaillement_filet_pa)

                # d_moyen : on ne l’invente pas -> on approxime par d_noyau si rien d'autre (conservatif),
                # mais c’est une hypothèse “modèle”. On le signale.
                d_moy = _req_pos("diametre_noyau_filet_m", self.diametre_noyau_filet_m)
                A_shear = math.pi * d_moy * Leng
                tau = F_par_vis / A_shear

                rapport["fixation_taraudee"]["longueur_engagement_m"] = Leng
                rapport["fixation_taraudee"]["aire_cisaillement_filet_m2_modele"] = A_shear
                rapport["fixation_taraudee"]["tau_cisaillement_filet_pa"] = tau
                rapport["fixation_taraudee"]["tau_admissible_filet_pa"] = tau_adm
                rapport["fixation_taraudee"]["ok_cisaillement_filet"] = tau <= (tau_adm / FS)
                rapport["fixation_taraudee"]["marge_cisaillement_filet"] = (tau_adm / FS) / tau if tau > 0 else None

                rapport["notes_modele"].append(
                    "Cisaillement filet : d_moy pris = d_noyau (approx conservatrice). "
                    "Si tu veux une valeur plus fidèle, fournis d_moyen_filet_m."
                )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "cisaillement filet",
                    "Calculable si longueur_engagement_filet_m, resistance_cisaillement_filet_pa et diametre_noyau_filet_m sont fournis.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "fixation taraudée",
                "Calcul détaillé possible si nombre_vis et force_axiale_N (ou déductible) sont fournis, "
                "et si diametre_noyau_filet_m / longueurs d’engagement sont connus.",
            )

        # ----------------------------
        # 8) Masse (si d + longueur “physique” connue + rho)
        # ----------------------------
        # Attention : longueur physique n’est PAS la longueur libre flambage.
        # On ne devine pas : si tu veux la masse, donne longueur_physique_m.
        longueur_physique_m = getattr(self, "longueur_physique_m", None)
        if d is not None and rho is not None and longueur_physique_m is not None:
            Lp = _req_pos("longueur_physique_m", longueur_physique_m)
            V = _aire_disque(d) * Lp
            m = rho * V
            rapport["masse"] = {
                "longueur_physique_m": Lp,
                "volume_m3": V,
                "masse_kg": m,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "masse arbre",
                "Calculable si diametre_arbre_m, densite_kg_m3 (ou materiau_cle) et longueur_physique_m sont fournis.",
            )

        # ----------------------------
        # 9) Entrées (trace)
        # ----------------------------
        rapport["entrees"] = {
            "diametre_arbre_m": self.diametre_arbre_m,
            "longueur_libre_m": self.longueur_libre_m,
            "entraxe_appuis_m": self.entraxe_appuis_m,
            "bras_levier_charge_m": self.bras_levier_charge_m,
            "force_axiale_N": self.force_axiale_N,
            "force_cisaillement_N": self.force_cisaillement_N,
            "moment_flexion_Nm": self.moment_flexion_Nm,
            "nombre_vis": self.nombre_vis,
            "diametre_noyau_filet_m": self.diametre_noyau_filet_m,
            "longueur_engagement_filet_m": self.longueur_engagement_filet_m,
            "resistance_cisaillement_filet_pa": self.resistance_cisaillement_filet_pa,
            "diametre_portee_coussinet_m": self.diametre_portee_coussinet_m,
            "longueur_coussinet_m": self.longueur_coussinet_m,
            "pression_admissible_coussinet_pa": self.pression_admissible_coussinet_pa,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "limite_elastique_pa": self.limite_elastique_pa,
            "module_young_pa": self.module_young_pa,
            "facteur_securite": self.facteur_securite,
            "K_flambage": self.K_flambage,
            "longueur_physique_m": getattr(self, "longueur_physique_m", None),
        }

        # ----------------------------
        # 10) Mode strict
        # ----------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "ArbrePiston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# =============================================================================
# Exemple d'usage minimal (à supprimer en prod)
# =============================================================================
if __name__ == "__main__":
    # Exemple : diamètre calculé à partir d’un piston existant (si piston.calculer() marche)
    try:
        from backend.pieces.piston import Piston  # type: ignore
        p = Piston(
            diametre_piston_m=0.085,
            hauteur_piston_m=0.05,
            pression_cote_froid_pa=6e5,
            temperature_cote_froid_k=300.0,
            course_m=0.085,
            rpm=3000.0,
            densite_kg_m3=2700.0,
            limite_elastique_pa=250e6,
        )
    except Exception:
        p = None

    a = ArbrePiston(
        piston=p,
        force_cisaillement_N=2000.0,   # si tu ne veux pas dépendre du piston
        bras_levier_charge_m=0.01,
        materiau_cle=None,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        facteur_securite=2.0,
        longueur_libre_m=0.06,
        K_flambage=1.0,
    )

    from pprint import pprint
    pprint(a.analyser(strict=False))

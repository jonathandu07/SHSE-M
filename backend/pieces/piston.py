# backend/pieces/piston.py
# =============================================================================
# PISTON (côté froid) — SHSE-M
# =============================================================================
# Rôle : pièce qui translate dans le cylindre, comprimée par l'air côté froid.
# Objectifs : étanchéité (fuites minimales), pertes par frottement minimales,
# robustesse mécanique, maintenance réduite.
#
# IMPORTANT (conformément à ta demande "rien inventer") :
# - Ce module NE "devine" aucune dimension : il calcule tout ce qui est calculable
#   à partir des entrées disponibles (ou récupérées du Cylindre si fourni).
# - Tout résultat dépend d'entrées. Si une entrée manque, la valeur reste None
#   et l'inconnue est listée dans le rapport.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math


# =============================================================================
# Petites utilitaires (validation + inconnues)
# =============================================================================

def _is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini.")
    return float(x)


def _require_positive(name: str, x: Any, strictly: bool = True) -> float:
    v = _require_finite(name, x)
    if strictly:
        if v <= 0:
            raise ValueError(f"{name} doit être > 0.")
    else:
        if v < 0:
            raise ValueError(f"{name} doit être >= 0.")
    return v


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": nom, "raison": raison})


def _aire_disque(diametre_m: float) -> float:
    r = 0.5 * diametre_m
    return math.pi * r * r


def _volume_cylindre(diametre_m: float, hauteur_m: float) -> float:
    return _aire_disque(diametre_m) * hauteur_m


# =============================================================================
# Résolution matériaux (utilise materiaux.py si présent)
# =============================================================================

def _resoudre_materiau(
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
    conductivite_w_mk: Optional[float],
) -> Dict[str, Optional[float]]:
    """
    Tente de compléter les propriétés matériau via backend/materiaux.py (ou materiaux.py),
    sinon retourne ce qui est fourni.
    """
    rho = densite_kg_m3
    Re = limite_elastique_pa
    E = module_young_pa
    k = conductivite_w_mk

    if materiau_cle:
        # On tente plusieurs chemins d'import (selon l'arborescence projet)
        for modname in (
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                # Convention la plus probable : get_materiau(cle) -> dict
                if hasattr(mod, "get_materiau"):
                    m = mod.get_materiau(materiau_cle)  # type: ignore[attr-defined]
                    if isinstance(m, dict):
                        rho = rho if rho is not None else m.get("densite_kg_m3")
                        Re = Re if Re is not None else m.get("limite_elastique_pa")
                        E = E if E is not None else m.get("module_young_pa")
                        k = k if k is not None else m.get("conductivite_w_mk")
                # Autre convention possible : MATERIAUX dict
                elif hasattr(mod, "MATERIAUX"):
                    m = getattr(mod, "MATERIAUX", {}).get(materiau_cle)
                    if isinstance(m, dict):
                        rho = rho if rho is not None else m.get("densite_kg_m3")
                        Re = Re if Re is not None else m.get("limite_elastique_pa")
                        E = E if E is not None else m.get("module_young_pa")
                        k = k if k is not None else m.get("conductivite_w_mk")
                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "limite_elastique_pa": Re,
        "module_young_pa": E,
        "conductivite_w_mk": k,
    }


# =============================================================================
# Air (viscosité/densité) — utilise air.py si présent
# =============================================================================

def _air_props_si_disponible(temperature_k: Optional[float], pression_pa: Optional[float]) -> Dict[str, Optional[float]]:
    """
    Tente de récupérer rho et mu (viscosité dynamique) via air.py si dispo.
    Si indisponible, retourne None.
    """
    rho = None
    mu = None

    if temperature_k is None or pression_pa is None:
        return {"rho_kg_m3": None, "mu_pa_s": None}

    for modname in (
        "backend.air",
        "air",
        "backend.components.air",
        "backend.modules.air",
    ):
        try:
            mod = __import__(modname, fromlist=["*"])
            if hasattr(mod, "air_state"):
                st = mod.air_state(temperature_k=temperature_k, pression_pa=pression_pa)  # type: ignore[attr-defined]
                # On accepte plusieurs conventions de retour (dataclass/dict)
                if isinstance(st, dict):
                    rho = st.get("rho_kg_m3") or st.get("densite_kg_m3")
                    mu = st.get("mu_pa_s") or st.get("viscosite_pa_s")
                else:
                    rho = getattr(st, "rho_kg_m3", None)
                    if rho is None:
                        rho = getattr(st, "densite_kg_m3", None)
                    mu = getattr(st, "mu_pa_s", None)
                    if mu is None:
                        mu = getattr(st, "viscosite_pa_s", None)
                break
        except Exception:
            continue

    return {"rho_kg_m3": rho, "mu_pa_s": mu}


# =============================================================================
# Cinématique (utilise un module si dispo, sinon formule standard)
# =============================================================================

def _vitesse_moyenne_piston(course_m: float, rpm: float) -> float:
    """
    Vitesse moyenne piston (m/s) : v_moy = 2 * course * rpm / 60
    """
    return 2.0 * course_m * (rpm / 60.0)


def _try_vitesse_moyenne_piston_module(course_m: float, rpm: float) -> Tuple[float, List[str]]:
    notes: List[str] = []
    for modname in (
        "backend.modules.bielle_manivelle.calcul_vitesse_piston",
        "backend.modules.cinematique.calcul_vitesse_piston",
        "backend.modules.cinematique",
    ):
        try:
            mod = __import__(modname, fromlist=["*"])
            if hasattr(mod, "calcul_vitesse_moyenne_piston"):
                v = mod.calcul_vitesse_moyenne_piston(course_m=course_m, vitesse_rotation_tr_min=rpm)  # type: ignore
                return float(v), notes
        except Exception:
            continue
    # fallback
    notes.append("Module cinématique introuvable : v_moy = 2*course*rpm/60.")
    return _vitesse_moyenne_piston(course_m, rpm), notes


# =============================================================================
# Interface "pièces liées" (types souples pour éviter les imports circulaires)
# =============================================================================

class _CylindreLike:
    # noms possibles selon ton cylindre.py (on lit via getattr)
    diametre_interieur_m: float
    alesage_m: float
    course_m: float


class _DeplaceurLike:
    # on ne suppose rien : uniquement pour checks si l'utilisateur donne des dims
    pass


# =============================================================================
# Modèle de Piston
# =============================================================================

@dataclass
class Piston:
    # ----- Lien vers les autres pièces (optionnel mais recommandé)
    cylindre: Optional[Any] = None         # idéalement backend.pieces.cylindre.Cylindre
    deplaceur: Optional[Any] = None        # idéalement backend.pieces.deplaceur.Deplaceur (pas obligatoire ici)

    # ----- Géométrie (si cylindre fourni, on peut déduire le diamètre nominal)
    diametre_piston_m: Optional[float] = None      # typiquement ~ diamètre intérieur cylindre - 2*jeu
    hauteur_piston_m: Optional[float] = None       # hauteur totale (jupe + tête)
    longueur_jupe_m: Optional[float] = None        # longueur de guidage en contact (jupe)
    epaisseur_tete_m: Optional[float] = None       # épaisseur "couronne" côté pression

    # ----- Jeux / étanchéité
    jeu_radial_m: Optional[float] = None           # (rayon) : (D_cyl - D_piston)/2
    longueur_portee_etanche_m: Optional[float] = None  # longueur caractéristique des fuites (si modélisées)

    # ----- Conditions de fonctionnement (côté froid)
    pression_cote_froid_pa: Optional[float] = None
    temperature_cote_froid_k: Optional[float] = None

    # ----- Cinématique (pour frottement/usure)
    course_m: Optional[float] = None               # si cylindre fourni, déductible
    rpm: Optional[float] = None

    # ----- Efforts (si on veut aller plus loin que F = P*A)
    force_axiale_externe_n: Optional[float] = None  # si tu l'imposes (ex. effort transmis par bielle)
    angle_bielle_deg: Optional[float] = None        # pour estimer effort latéral (side-load)
    force_bielle_n: Optional[float] = None          # si connue (sinon calculable ailleurs)

    # ----- Frottements (modèle simple)
    coefficient_frottement: Optional[float] = None  # mu Coulomb (nécessite effort normal)
    # effort normal sur jupe : si angle_bielle + force_bielle, calculable, sinon inconnue
    force_normale_jupe_n: Optional[float] = None

    # ----- Matériau (soit cle, soit propriétés directes)
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None
    conductivite_w_mk: Optional[float] = None

    # ----- Options de calcul
    facteur_securite: float = 2.0

    def calculer(self) -> Dict[str, Any]:
        """
        Retourne un rapport complet :
        - géométrie dérivée
        - masse, inertie simplifiée
        - efforts gaz, contraintes moyennes
        - frottements + pertes (si calculables)
        - fuites (si modélisables via jeu + mu air)
        - liste des inconnues (impossibles/partielles)
        """
        rapport: Dict[str, Any] = {"piece": "piston", "notes_modele": [], "entrees": {}, "resultats": {}}

        # ---------------------------------------------------------------------
        # 1) Compléter depuis le cylindre si possible
        # ---------------------------------------------------------------------
        d_cyl = None
        course = self.course_m
        if self.cylindre is not None:
            # On tente plusieurs attributs probables
            for attr in ("diametre_interieur_m", "alesage_m", "diametre_alesage_m"):
                if hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        d_cyl = float(v)
                        break
            if course is None:
                for attr in ("course_m", "course_piston_m"):
                    if hasattr(self.cylindre, attr):
                        v = getattr(self.cylindre, attr)
                        if v is not None:
                            course = float(v)
                            break

        # ---------------------------------------------------------------------
        # 2) Géométrie cohérente (sans rien inventer)
        # ---------------------------------------------------------------------
        Dp = self.diametre_piston_m
        if Dp is None and d_cyl is not None and self.jeu_radial_m is not None:
            # Dp = Dcyl - 2*jeu_radial*2 ? attention : jeu_radial = (Dcyl - Dp)/2  => Dp = Dcyl - 2*jeu_radial
            Dp = d_cyl - 2.0 * float(self.jeu_radial_m)
            rapport["notes_modele"].append("diametre_piston déduit : Dp = Dcyl - 2*jeu_radial.")
        elif Dp is None and d_cyl is not None and self.jeu_radial_m is None:
            _push_inconnue(rapport, "partielles", "diametre_piston_m", "Calculable si jeu_radial_m est fourni (avec cylindre).")
        elif Dp is None and d_cyl is None:
            _push_inconnue(rapport, "impossibles", "diametre_piston_m", "Ni cylindre ni diametre_piston_m fourni.")

        # surface de piston (face pression)
        A = None
        if Dp is not None:
            if Dp <= 0:
                raise ValueError("diametre_piston_m doit être > 0.")
            A = _aire_disque(Dp)
        else:
            _push_inconnue(rapport, "partielles", "surface_piston_m2", "Calculable si diametre_piston_m est connu.")

        # volume / masse (si hauteur connue + densité)
        props_mat = _resoudre_materiau(
            self.materiau_cle,
            self.densite_kg_m3,
            self.limite_elastique_pa,
            self.module_young_pa,
            self.conductivite_w_mk,
        )
        rho = props_mat["densite_kg_m3"]
        Re = props_mat["limite_elastique_pa"]

        V = None
        m = None
        if Dp is not None and self.hauteur_piston_m is not None:
            h = _require_positive("hauteur_piston_m", self.hauteur_piston_m, strictly=True)
            V = _volume_cylindre(Dp, h)
            if rho is not None:
                m = V * float(rho)
            else:
                _push_inconnue(rapport, "partielles", "masse_piston_kg", "Calculable si densite_kg_m3 est fournie (ou materiau_cle résoluble).")
        else:
            if Dp is None:
                _push_inconnue(rapport, "partielles", "volume_piston_m3", "Calculable si diametre_piston_m est connu et hauteur_piston_m fournie.")
            if self.hauteur_piston_m is None:
                _push_inconnue(rapport, "impossibles", "volume_piston_m3", "hauteur_piston_m non fournie.")

        # inertie translationnelle (énergie cinétique alternative) : E = 1/2 m v^2
        v_moy = None
        if course is not None and self.rpm is not None:
            course_val = _require_positive("course_m", course, strictly=True)
            rpm_val = _require_positive("rpm", self.rpm, strictly=False)
            v_moy, notes_v = _try_vitesse_moyenne_piston_module(course_val, rpm_val)
            rapport["notes_modele"].extend(notes_v)
        else:
            _push_inconnue(rapport, "partielles", "vitesse_moyenne_piston_ms", "Calculable si course_m et rpm sont fournis (ou déductibles du cylindre).")

        Ecin = None
        if m is not None and v_moy is not None:
            Ecin = 0.5 * m * v_moy * v_moy
        else:
            _push_inconnue(rapport, "partielles", "energie_cinetique_alternative_J", "Calculable si masse_piston_kg et vitesse_moyenne_piston_ms sont calculées.")

        # ---------------------------------------------------------------------
        # 3) Efforts gaz (P * A) + contraintes "moyennes"
        # ---------------------------------------------------------------------
        F_gaz = None
        if self.pression_cote_froid_pa is not None and A is not None:
            P = _require_positive("pression_cote_froid_pa", self.pression_cote_froid_pa, strictly=True)
            F_gaz = P * A
        else:
            _push_inconnue(rapport, "partielles", "force_gaz_N", "Calculable si pression_cote_froid_pa et surface_piston_m2 sont connues.")

        # contrainte moyenne dans la tête (approx) : sigma = F / A_eff
        # Ici A_eff = A (simple). Pour un vrai dimensionnement, il faut géométrie détaillée.
        sigma_moy = None
        if F_gaz is not None and A is not None:
            sigma_moy = F_gaz / A  # = pression (si A_eff = A)
        else:
            _push_inconnue(rapport, "partielles", "contrainte_moyenne_pa", "Déductible si force_gaz_N et surface_piston_m2.")

        # check matériau (si Re connu)
        marge_Re = None
        if sigma_moy is not None and Re is not None:
            marge_Re = float(Re) / (sigma_moy * float(self.facteur_securite)) if sigma_moy > 0 else None
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "marge_limite_elastique",
                "Calculable si limite_elastique_pa (matériau) est connue et contrainte_moyenne_pa calculée.",
            )

        # ---------------------------------------------------------------------
        # 4) Effort latéral (side-load) sur la jupe + pression de contact
        # ---------------------------------------------------------------------
        F_side = None
        if self.force_normale_jupe_n is not None:
            F_side = _require_positive("force_normale_jupe_n", self.force_normale_jupe_n, strictly=False)
        elif self.force_bielle_n is not None and self.angle_bielle_deg is not None:
            Fb = _require_finite("force_bielle_n", self.force_bielle_n)
            ang = math.radians(_require_finite("angle_bielle_deg", self.angle_bielle_deg))
            F_side = abs(Fb * math.tan(ang))
            rapport["notes_modele"].append("Effort latéral estimé : F_side = |F_bielle * tan(angle_bielle)|.")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force_laterale_jupe_N",
                "Calculable si force_normale_jupe_n est fournie, ou (force_bielle_n + angle_bielle_deg).",
            )

        # pression de contact jupe/cylindre (moyenne) : p_contact = F_side / (pi*D*L)
        p_contact = None
        if F_side is not None and Dp is not None and self.longueur_jupe_m is not None:
            Ljupe = _require_positive("longueur_jupe_m", self.longueur_jupe_m, strictly=True)
            surface_contact = math.pi * Dp * Ljupe
            if surface_contact > 0:
                p_contact = F_side / surface_contact
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pression_contact_jupe_pa",
                "Calculable si (force_laterale_jupe_N, diametre_piston_m, longueur_jupe_m) sont connus.",
            )

        # ---------------------------------------------------------------------
        # 5) Frottement + puissance perdue (modèle Coulomb)
        # ---------------------------------------------------------------------
        F_frott = None
        P_frott = None
        if self.coefficient_frottement is not None and F_side is not None:
            mu = _require_positive("coefficient_frottement", self.coefficient_frottement, strictly=False)
            F_frott = mu * abs(F_side)
            if v_moy is not None:
                P_frott = F_frott * v_moy
            else:
                _push_inconnue(rapport, "partielles", "puissance_perdue_frottement_W", "Calculable si vitesse_moyenne_piston_ms est connue.")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force_frottement_N",
                "Calculable si (coefficient_frottement, force_laterale_jupe_N) sont connus.",
            )

        # PV (usure) : PV = p_contact * v_moy
        PV = None
        if p_contact is not None and v_moy is not None:
            PV = p_contact * v_moy
        else:
            _push_inconnue(rapport, "partielles", "PV_usure", "Calculable si pression_contact_jupe_pa et vitesse_moyenne_piston_ms.")

        # ---------------------------------------------------------------------
        # 6) Fuites par jeu annulaire (modèle laminaire simplifié)
        # ---------------------------------------------------------------------
        # Modèle utilisé (si calculable) :
        # Q ≈ (pi * D * c^3 / (12 * mu * L)) * ΔP
        # avec c = jeu_radial, L = longueur_portee_etanche
        # => nécessite mu (viscosité), D, c, L, ΔP.
        #
        # Remarque : si tu veux un modèle compressible plus réaliste, il faut définir
        # explicitement lequel (et ses paramètres) — ici on reste dans ce qui est
        # calculable simplement à partir des entrées.
        Q_fuite_m3_s = None
        mdot_fuite_kg_s = None

        if (
            Dp is not None
            and self.jeu_radial_m is not None
            and self.longueur_portee_etanche_m is not None
            and self.pression_cote_froid_pa is not None
            and self.temperature_cote_froid_k is not None
        ):
            c = _require_positive("jeu_radial_m", self.jeu_radial_m, strictly=True)
            L = _require_positive("longueur_portee_etanche_m", self.longueur_portee_etanche_m, strictly=True)
            P1 = _require_positive("pression_cote_froid_pa", self.pression_cote_froid_pa, strictly=True)
            # ΔP : il faut une pression de référence "fuite vers où ?"
            # -> on ne l'invente pas : l'utilisateur doit fournir pression_exterieure_pa.
            _push_inconnue(
                rapport,
                "impossibles",
                "debit_fuite_m3_s",
                "Modèle par jeu annulaire nécessite ΔP : fournir pression_exterieure_pa (ou pression_cote_chaud_pa selon chemin de fuite).",
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "debit_fuite_m3_s",
                "Calculable si (Dp, jeu_radial_m, longueur_portee_etanche_m, temperature_cote_froid_k, pression_cote_froid_pa, ΔP) sont fournis.",
            )

        # Variante : si pression_exterieure_pa est injectée via champ dynamique dans calculer()
        # (sans changer la dataclass) :
        # -> on accepte un override dans self.__dict__ pour rester compatible.
        pression_exterieure_pa = getattr(self, "pression_exterieure_pa", None)
        if (
            Dp is not None
            and self.jeu_radial_m is not None
            and self.longueur_portee_etanche_m is not None
            and self.pression_cote_froid_pa is not None
            and self.temperature_cote_froid_k is not None
            and pression_exterieure_pa is not None
        ):
            c = _require_positive("jeu_radial_m", self.jeu_radial_m, strictly=True)
            L = _require_positive("longueur_portee_etanche_m", self.longueur_portee_etanche_m, strictly=True)
            P1 = _require_positive("pression_cote_froid_pa", self.pression_cote_froid_pa, strictly=True)
            P2 = _require_positive("pression_exterieure_pa", pression_exterieure_pa, strictly=False)
            dP = max(P1 - P2, 0.0)

            air = _air_props_si_disponible(self.temperature_cote_froid_k, P1)
            mu_air = air["mu_pa_s"]
            rho_air = air["rho_kg_m3"]

            if mu_air is None:
                _push_inconnue(rapport, "partielles", "debit_fuite_m3_s", "Viscosité air indisponible : fournir mu_pa_s ou compléter air.py.")
            else:
                muv = _require_positive("mu_air_pa_s", mu_air, strictly=True)
                Q_fuite_m3_s = (math.pi * Dp * (c ** 3) / (12.0 * muv * L)) * dP
                if rho_air is not None:
                    mdot_fuite_kg_s = Q_fuite_m3_s * float(rho_air)
                else:
                    _push_inconnue(rapport, "partielles", "debit_fuite_kg_s", "Calculable si densité air (rho) est disponible via air_state().")

                rapport["notes_modele"].append("Fuite (jeu annulaire) : Q = (π*D*c^3/(12*μ*L))*ΔP (laminaire, simplifié).")

        # ---------------------------------------------------------------------
        # 7) Checks géométriques liés au déplaceur (sans inventer)
        # ---------------------------------------------------------------------
        # On ne peut pas vérifier "ne touche jamais le déplaceur" sans :
        # - positions relatives
        # - longueurs utiles
        # - course déplaceur / piston
        # On expose juste un check si l'utilisateur fournit distance_min_avec_deplaceur_m.
        distance_min_avec_deplaceur_m = getattr(self, "distance_min_avec_deplaceur_m", None)
        ok_non_contact = None
        if distance_min_avec_deplaceur_m is not None:
            dist = _require_finite("distance_min_avec_deplaceur_m", distance_min_avec_deplaceur_m)
            ok_non_contact = dist > 0
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "verification_non_contact_deplaceur",
                "Fournir distance_min_avec_deplaceur_m (ou géométrie complète + lois de course) pour conclure.",
            )

        # ---------------------------------------------------------------------
        # Entrées / Résultats
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "diametre_piston_m": Dp,
            "hauteur_piston_m": self.hauteur_piston_m,
            "longueur_jupe_m": self.longueur_jupe_m,
            "epaisseur_tete_m": self.epaisseur_tete_m,
            "jeu_radial_m": self.jeu_radial_m,
            "longueur_portee_etanche_m": self.longueur_portee_etanche_m,
            "pression_cote_froid_pa": self.pression_cote_froid_pa,
            "temperature_cote_froid_k": self.temperature_cote_froid_k,
            "course_m": course,
            "rpm": self.rpm,
            "force_bielle_n": self.force_bielle_n,
            "angle_bielle_deg": self.angle_bielle_deg,
            "coefficient_frottement": self.coefficient_frottement,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": props_mat["densite_kg_m3"],
            "limite_elastique_pa": props_mat["limite_elastique_pa"],
            "module_young_pa": props_mat["module_young_pa"],
            "conductivite_w_mk": props_mat["conductivite_w_mk"],
            "facteur_securite": self.facteur_securite,
            "pression_exterieure_pa": pression_exterieure_pa,
            "distance_min_avec_deplaceur_m": distance_min_avec_deplaceur_m,
        }

        rapport["resultats"] = {
            "surface_piston_m2": A,
            "volume_piston_m3": V,
            "masse_piston_kg": m,
            "vitesse_moyenne_piston_ms": v_moy,
            "energie_cinetique_alternative_J": Ecin,
            "force_gaz_N": F_gaz,
            "contrainte_moyenne_pa": sigma_moy,
            "marge_limite_elastique": marge_Re,
            "force_laterale_jupe_N": F_side,
            "pression_contact_jupe_pa": p_contact,
            "force_frottement_N": F_frott,
            "puissance_perdue_frottement_W": P_frott,
            "PV_usure": PV,
            "debit_fuite_m3_s": Q_fuite_m3_s,
            "debit_fuite_kg_s": mdot_fuite_kg_s,
            "ok_non_contact_deplaceur": ok_non_contact,
        }

        return rapport


# =============================================================================
# Exemple d'usage (à supprimer en prod)
# =============================================================================
if __name__ == "__main__":
    # Exemple minimal : ne calcule que ce qui est possible avec les entrées.
    p = Piston(
        diametre_piston_m=0.085,
        hauteur_piston_m=0.05,
        pression_cote_froid_pa=6e5,
        temperature_cote_froid_k=300.0,
        course_m=0.085,
        rpm=3000.0,
        materiau_cle=None,
        densite_kg_m3=2700.0,
        limite_elastique_pa=250e6,
        coefficient_frottement=0.15,
        force_bielle_n=10000.0,
        angle_bielle_deg=10.0,
        longueur_jupe_m=0.03,
    )
    # Optionnel (si tu veux calculer les fuites) :
    # setattr(p, "pression_exterieure_pa", 1e5)
    # setattr(p, "distance_min_avec_deplaceur_m", 0.002)

    from pprint import pprint
    pprint(p.calculer())

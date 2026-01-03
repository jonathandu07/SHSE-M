# backend/pieces/deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal
import math

# ============================================================
# Imports projet (avec fallbacks) — réduction des inconnues
# ============================================================

# --- Matériaux (réduction d'inconnues) ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# --- Air (pour densité, viscosité, etc. si dispo) ---
try:
    from backend.ensemble.air import air_state
except Exception:  # pragma: no cover
    air_state = None  # type: ignore


# ============================================================
# Helpers robustes
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strictly else v >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v

def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})

def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: list[dict]) -> list[dict]:
        seen: set[Tuple[str, str]] = set()
        out: list[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


# ============================================================
# Modèles de calcul (sans heuristiques “inventées”)
# ============================================================

def aire_disque(diametre_m: float) -> float:
    d = _req_pos("diametre_m", diametre_m)
    r = 0.5 * d
    return math.pi * r * r

def masse_cylindre_plein(diametre_m: float, longueur_m: float, densite_kg_m3: float) -> float:
    A = aire_disque(diametre_m)
    V = A * _req_pos("longueur_m", longueur_m)
    rho = _req_pos("densite_kg_m3", densite_kg_m3)
    return rho * V

def contrainte_axiale(force_N: float, section_m2: float) -> float:
    A = _req_pos("section_m2", section_m2)
    return float(force_N) / A

def flambe_euler(
    *,
    E_pa: float,
    I_m4: float,
    longueur_libre_m: float,
    coeff_k: float = 1.0,
) -> float:
    """
    Charge critique d'Euler : Pcr = (pi^2 * E * I) / (Lk^2)
    - coeff_k = facteur de longueur efficace (K) : Lk = K*L
    """
    E = _req_pos("E_pa", E_pa)
    I = _req_pos("I_m4", I_m4)
    L = _req_pos("longueur_libre_m", longueur_libre_m)
    K = _req_pos("coeff_k", coeff_k)
    Lk = K * L
    return (math.pi ** 2) * E * I / (Lk ** 2)

def inertie_section_circulaire_pleine(diametre_m: float) -> float:
    """
    I (flexion) d'une section circulaire pleine : I = pi/64 * D^4
    """
    D = _req_pos("diametre_m", diametre_m)
    return (math.pi / 64.0) * (D ** 4)

def perte_charge_orifice(
    *,
    rho_kg_m3: float,
    debit_m3_s: float,
    aire_orifice_m2: float,
    coeff_decharge: float,
) -> float:
    """
    Relation inverse (orifice incompressible, très simplifiée) :
    Q = Cd * A * sqrt(2*Δp/rho)  =>  Δp = (rho/2) * (Q/(Cd*A))^2

    Attention : pour gaz compressibles / grands Δp, il faut un modèle compressible.
    Ici, on ne l'emploie que si tu ACCEPTES ce modèle et que tu restes dans un domaine
    où c'est raisonnable (petites variations de pression, Mach faible).
    """
    rho = _req_pos("rho_kg_m3", rho_kg_m3)
    Q = _req_pos("debit_m3_s", debit_m3_s, strictly=False)
    A = _req_pos("aire_orifice_m2", aire_orifice_m2)
    Cd = _req_pos("coeff_decharge", coeff_decharge)
    if Cd * A <= 0:
        raise ValueError("Cd*A doit être > 0")
    v_eq = Q / (Cd * A)
    return 0.5 * rho * (v_eq ** 2)


# ============================================================
# Pièce : Déplaceur (piston libre)
# ============================================================

@dataclass(frozen=True)
class Deplaceur:
    """
    Déplaceur = piston libre, soumis à une différence de pression entre côté chaud et côté froid.

    Objectif :
    - Produire un maximum de grandeurs calculées
    - Réduire les inconnues via :
      * matériau (materiau_cle -> rho, E, nu, alpha, Re...)
      * air_state (rho, mu...) si tu donnes T/p
    - Ne RIEN inventer : si un paramètre n'est pas fourni/déductible -> inconnue.

    Limitations (assumées, explicites) :
    - La “différence de pression” Δp entre côté chaud et froid n’est PAS déductible
      uniquement avec (Tchaud, Tfroid) sans un modèle complet de pertes/volumes/flux.
      Donc : Δp doit être fourni, OU calculé via un sous-modèle explicite (optionnel),
      avec ses entrées (débit, orifice, Cd, rho...).
    - Dimensionnement des joints toriques : impossible sans standard (section, squeeze, etc.).
      On peut cependant calculer des forces “à étancher” et des vitesses / frottements si tu fournis μ_frottement etc.
    """

    # --- Géométrie (obligatoire) ---
    diametre_exterieur_m: float        # diamètre du déplaceur (hors joints)
    longueur_totale_m: float           # longueur totale du déplaceur
    course_disponible_m: float         # course maximale possible dans le cylindre
    jeu_radial_m: float                # jeu radial déplaceur/cylindre (sans joints)

    # --- Pressions ---
    pression_chaud_pa: Optional[float] = None
    pression_froid_pa: Optional[float] = None
    delta_p_chaud_froid_pa: Optional[float] = None  # si fourni, prioritaire

    # --- Thermique (optionnel) ---
    temperature_chaud_C: Optional[float] = None
    temperature_froid_C: Optional[float] = None

    # --- Matériau (réduction inconnues) ---
    materiau_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"

    # Overrides manuels (si fournis, priment sur matériau)
    densite_kg_m3: Optional[float] = None
    module_young_pa: Optional[float] = None
    poisson: Optional[float] = None
    alpha_dilatation_1_k: Optional[float] = None
    limite_elastique_pa: Optional[float] = None

    # --- Joints toriques (étanchéité) ---
    nb_joints_toriques: Optional[int] = None
    largeur_bande_joint_m: Optional[float] = None  # largeur axiale de contact (si modélisée)
    coeff_frottement_joint: Optional[float] = None # μ (si tu veux estimer effort de frottement)
    pression_contact_joint_pa: Optional[float] = None  # pression de contact moyenne (si tu la connais)

    # --- Modèle optionnel de Δp via orifice (si tu veux) ---
    # (sinon Δp reste une inconnue si pas fourni)
    orifice_aire_m2: Optional[float] = None
    orifice_coeff_decharge: Optional[float] = None
    debit_gaz_m3_s: Optional[float] = None
    # Si air_state dispo et T/p fourni, on peut obtenir rho. Sinon, rho doit être fourni.
    rho_gaz_kg_m3: Optional[float] = None
    temperature_gaz_C: Optional[float] = None
    pression_gaz_ref_pa: Optional[float] = None

    # --- Vérifs stabilité mécanique (optionnel) ---
    longueur_libre_flambe_m: Optional[float] = None  # si tu veux estimer flambage type tige (si applicable)
    coeff_k_flambe: float = 1.0                      # K (Euler)

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "materiau": {},
            "geometrie": {},
            "pressions": {},
            "efforts": {},
            "dynamique": {},
            "etancheite": {},
            "thermique": {},
            "contraintes": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ----------------------------
        # 1) Validation entrées
        # ----------------------------
        D = _req_pos("diametre_exterieur_m", self.diametre_exterieur_m)
        L = _req_pos("longueur_totale_m", self.longueur_totale_m)
        stroke = _req_pos("course_disponible_m", self.course_disponible_m, strictly=False)
        jeu = _req_pos("jeu_radial_m", self.jeu_radial_m, strictly=False)

        rapport["entrees"].update({
            "diametre_exterieur_m": D,
            "longueur_totale_m": L,
            "course_disponible_m": stroke,
            "jeu_radial_m": jeu,
            "pression_chaud_pa": self.pression_chaud_pa,
            "pression_froid_pa": self.pression_froid_pa,
            "delta_p_chaud_froid_pa": self.delta_p_chaud_froid_pa,
            "materiau_cle": self.materiau_cle,
            "mode_materiau": self.mode_materiau,
        })

        # ----------------------------
        # 2) Matériau : déduction si possible
        # ----------------------------
        rho = self.densite_kg_m3
        E = self.module_young_pa
        nu = self.poisson
        alpha = self.alpha_dilatation_1_k
        Re = self.limite_elastique_pa

        if self.materiau_cle and get_materiau is not None:
            mat = get_materiau(self.materiau_cle)
            if mat is None:
                _push_inconnue(rapport, "partielles", "materiau_cle", f"Matériau '{self.materiau_cle}' introuvable.")
            else:
                # On ne remplace pas un override utilisateur
                if rho is None:
                    rho = valeur(getattr(mat, "densite_kg_m3", None), mode=self.mode_materiau)
                if E is None:
                    E = valeur(getattr(mat, "module_young_pa", None), mode=self.mode_materiau)
                if nu is None:
                    nu = valeur(getattr(mat, "poisson", None), mode=self.mode_materiau)
                if alpha is None:
                    alpha = valeur(getattr(mat, "alpha_dilatation_1_k", None), mode=self.mode_materiau)
                if Re is None:
                    Re = valeur(getattr(mat, "limite_elastique_pa", None), mode=self.mode_materiau)

                rapport["materiau"].update({
                    "materiau_nom": getattr(mat, "nom", self.materiau_cle),
                    "famille": getattr(mat, "famille", None),
                    "densite_kg_m3": rho,
                    "module_young_pa": E,
                    "poisson": nu,
                    "alpha_dilatation_1_k": alpha,
                    "limite_elastique_pa": Re,
                })
        else:
            if self.materiau_cle and get_materiau is None:
                _push_inconnue(rapport, "partielles", "materiau", "backend.ensemble.materiaux indisponible (get_materiau).")

        # ----------------------------
        # 3) Géométrie calculée
        # ----------------------------
        A_face = aire_disque(D)
        perimetre = math.pi * D

        rapport["geometrie"].update({
            "aire_face_m2": A_face,
            "perimetre_m": perimetre,
            "volume_plein_m3": A_face * L,  # modèle “plein” (si en réalité allégé -> données nécessaires)
        })

        # Masse si rho connu
        if rho is not None:
            rho_v = _req_pos("densite_kg_m3", rho)
            m = rho_v * (A_face * L)
            rapport["geometrie"]["masse_modele_plein_kg"] = m
        else:
            _push_inconnue(rapport, "partielles", "masse", "Calculable si densite_kg_m3 (ou materiau_cle) est fourni.")

        # ----------------------------
        # 4) Δp chaud/froid : priorité à delta fourni
        # ----------------------------
        delta_p = None
        if self.delta_p_chaud_froid_pa is not None:
            delta_p = _req_finite("delta_p_chaud_froid_pa", self.delta_p_chaud_froid_pa)
        else:
            if self.pression_chaud_pa is not None and self.pression_froid_pa is not None:
                p_hot = _req_pos("pression_chaud_pa", self.pression_chaud_pa, strictly=False)
                p_cold = _req_pos("pression_froid_pa", self.pression_froid_pa, strictly=False)
                delta_p = p_hot - p_cold
            else:
                # Tentative via modèle orifice (optionnel, explicite)
                if self.orifice_aire_m2 is not None and self.orifice_coeff_decharge is not None and self.debit_gaz_m3_s is not None:
                    # rho gaz : soit fourni, soit via air_state (si possible)
                    rho_g = self.rho_gaz_kg_m3
                    if rho_g is None:
                        if air_state is not None and self.temperature_gaz_C is not None and self.pression_gaz_ref_pa is not None:
                            Tg = _req_finite("temperature_gaz_C", self.temperature_gaz_C) + 273.15
                            pg = _req_pos("pression_gaz_ref_pa", self.pression_gaz_ref_pa, strictly=False)
                            st = air_state(T_K=Tg, p_Pa=pg)
                            rho_g = float(st.rho_kg_m3)
                            rapport["thermique"]["air_state"] = {
                                "T_K": Tg,
                                "p_Pa": pg,
                                "rho_kg_m3": rho_g,
                                "mu_Pa_s": float(st.mu_Pa_s),
                                "k_W_m_K": float(st.k_W_m_K),
                                "backend": getattr(st, "backend", "air_state"),
                            }
                        else:
                            _push_inconnue(
                                rapport,
                                "impossibles",
                                "delta_p (orifice)",
                                "rho_gaz_kg_m3 manquant (ou fournir temperature_gaz_C + pression_gaz_ref_pa avec air_state disponible).",
                            )

                    if rho_g is not None:
                        delta_p = perte_charge_orifice(
                            rho_kg_m3=_req_pos("rho_gaz_kg_m3", rho_g),
                            debit_m3_s=_req_pos("debit_gaz_m3_s", self.debit_gaz_m3_s, strictly=False),
                            aire_orifice_m2=_req_pos("orifice_aire_m2", self.orifice_aire_m2),
                            coeff_decharge=_req_pos("orifice_coeff_decharge", self.orifice_coeff_decharge),
                        )
                        rapport["notes_modele"].append(
                            "Δp calculé via modèle orifice incompressible simplifié (attention gaz/fort Δp)."
                        )
                else:
                    _push_inconnue(
                        rapport,
                        "impossibles",
                        "delta_p chaud/froid",
                        "Fournir delta_p_chaud_froid_pa OU (pression_chaud_pa et pression_froid_pa). "
                        "Alternative: fournir (orifice_aire_m2, orifice_coeff_decharge, debit_gaz_m3_s, rho_gaz_kg_m3) pour un sous-modèle explicite.",
                    )

        rapport["pressions"].update({
            "delta_p_chaud_moins_froid_Pa": delta_p,
            "pression_chaud_pa": self.pression_chaud_pa,
            "pression_froid_pa": self.pression_froid_pa,
        })

        # ----------------------------
        # 5) Effort net sur déplaceur
        # ----------------------------
        if delta_p is not None:
            # Convention : F = Δp * A, signe selon convention delta_p = p_chaud - p_froid.
            F = float(delta_p) * A_face
            rapport["efforts"]["force_pression_N"] = F
            rapport["efforts"]["force_pression_abs_N"] = abs(F)
        else:
            _push_inconnue(rapport, "impossibles", "force pression", "Impossible sans delta_p chaud/froid.")

        # ----------------------------
        # 6) Étanchéité / joints : calculs possibles si paramètres fournis
        # ----------------------------
        if self.nb_joints_toriques is None:
            _push_inconnue(rapport, "partielles", "nb_joints_toriques", "Nombre de joints non fourni.")
        else:
            nJ = int(self.nb_joints_toriques)
            if nJ < 0:
                _push_inconnue(rapport, "impossibles", "nb_joints_toriques", "Doit être >= 0.")
            rapport["etancheite"]["nb_joints_toriques"] = nJ

        # Effort “à étancher” (charge radiale équivalente) : pas déductible sans modèle joint.
        # On peut toutefois donner une grandeur utile : force axiale de pression.
        if delta_p is not None:
            rapport["etancheite"]["charge_pression_equivalente_N"] = abs(delta_p) * A_face

        # Frottement des joints (optionnel, explicite)
        # Modèle simple : F_frott = μ * (p_contact * A_contact_total)
        # -> A_contact_total = périmètre * largeur_bande * nb_joints
        if (
            self.nb_joints_toriques is not None
            and self.largeur_bande_joint_m is not None
            and self.coeff_frottement_joint is not None
            and self.pression_contact_joint_pa is not None
        ):
            nJ = int(self.nb_joints_toriques)
            w = _req_pos("largeur_bande_joint_m", self.largeur_bande_joint_m)
            mu = _req_pos("coeff_frottement_joint", self.coeff_frottement_joint, strictly=False)
            p_c = _req_pos("pression_contact_joint_pa", self.pression_contact_joint_pa, strictly=False)
            A_contact = perimetre * w * max(0, nJ)
            F_frott = mu * p_c * A_contact
            rapport["etancheite"].update({
                "aire_contact_joints_m2": A_contact,
                "force_frottement_estimee_N": F_frott,
                "modele_frottement": "F=mu*p_contact*(perimetre*largeur*nb_joints) (nécessite p_contact explicite).",
            })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "frottement joints",
                "Calculable si nb_joints_toriques + largeur_bande_joint_m + coeff_frottement_joint + pression_contact_joint_pa sont fournis.",
            )

        # ----------------------------
        # 7) Contraintes matière (très basique) : sigma = F/A_face
        # ----------------------------
        if delta_p is not None:
            sigma = contrainte_axiale(float(delta_p) * A_face, A_face)  # = delta_p
            rapport["contraintes"]["sigma_axiale_equivalente_Pa"] = sigma

            if Re is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "limite_elastique_pa",
                    "Vérif élastique possible si limite_elastique_pa (ou materiau_cle) est fourni.",
                )
            else:
                Re_v = _req_pos("limite_elastique_pa", Re)
                # marge très simple (sans FS ici, car Re est déjà “valeur” ; si tu veux FS, donne-le explicitement)
                rapport["contraintes"]["marge_elastique_simple"] = (Re_v / abs(sigma)) if abs(sigma) > 0 else None

        # ----------------------------
        # 8) Dilatation thermique (si alpha et ΔT fournis)
        # ----------------------------
        if alpha is not None and self.temperature_chaud_C is not None and self.temperature_froid_C is not None:
            a = _req_pos("alpha_dilatation_1_k", alpha)
            Th = _req_finite("temperature_chaud_C", self.temperature_chaud_C)
            Tf = _req_finite("temperature_froid_C", self.temperature_froid_C)
            dT = Th - Tf
            dD = a * D * dT
            rapport["thermique"].update({
                "delta_T_chaud_moins_froid_K": dT,
                "variation_diametre_estimee_m": dD,
                "variation_rayon_estimee_m": 0.5 * dD,
            })
            # check jeu radial vs dilatation (si on suppose cylindre “fixe” -> comparaison indicative)
            if jeu is not None:
                rapport["verifications"]["jeu_radial_vs_dilatation"] = {
                    "jeu_radial_m": jeu,
                    "dilatation_rayon_m": 0.5 * dD,
                    "marge_jeu_m": jeu - (0.5 * dD),
                }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "dilatation thermique",
                "Calculable si alpha_dilatation_1_k (ou materiau_cle) + temperature_chaud_C + temperature_froid_C sont fournis.",
            )

        # ----------------------------
        # 9) Flambage Euler (si applicable) — uniquement si tu fournis longueur libre
        # ----------------------------
        if self.longueur_libre_flambe_m is not None:
            if E is None:
                _push_inconnue(rapport, "impossibles", "flambage", "E (module_young_pa) manquant (ou materiau_cle).")
            else:
                I = inertie_section_circulaire_pleine(D)
                Pcr = flambe_euler(
                    E_pa=_req_pos("module_young_pa", E),
                    I_m4=I,
                    longueur_libre_m=_req_pos("longueur_libre_flambe_m", self.longueur_libre_flambe_m),
                    coeff_k=_req_pos("coeff_k_flambe", self.coeff_k_flambe),
                )
                rapport["verifications"]["flambage_euler"] = {
                    "I_m4": I,
                    "Pcr_N": Pcr,
                    "note": "Vérif indicative (section pleine, Euler). Si géométrie réelle différente -> fournir I réel.",
                }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "flambage",
                "Calculable si longueur_libre_flambe_m est fournie (et E via materiau_cle ou module_young_pa).",
            )

        # ----------------------------
        # 10) Mode strict
        # ----------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "Deplaceur(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# ============================================================
# Exemple rapide (à adapter) — aucune valeur “inventée”
# ============================================================
if __name__ == "__main__":
    dep = Deplaceur(
        diametre_exterieur_m=0.080,
        longueur_totale_m=0.120,
        course_disponible_m=0.090,
        jeu_radial_m=0.0002,
        # delta_p_chaud_froid_pa=15_000.0,  # option 1: direct
        pression_chaud_pa=120_000.0,        # option 2: chaud/froid
        pression_froid_pa=105_000.0,
        materiau_cle="inox_304",
        mode_materiau="typique",
        nb_joints_toriques=2,
        # si tu veux estimer frottement : fournir ces 3 paramètres
        # largeur_bande_joint_m=0.003,
        # coeff_frottement_joint=0.15,
        # pression_contact_joint_pa=200_000.0,
        temperature_chaud_C=400.0,
        temperature_froid_C=80.0,
    )
    r = dep.analyser(strict=False)
    from pprint import pprint
    pprint(r)

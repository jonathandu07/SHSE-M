# backend/pieces/joint_piston.py
# =============================================================================
# JOINT PISTON — étanchéité piston <-> cylindre (côté froid)
# =============================================================================
# Strict "rien inventer" :
# - Ne choisit PAS un standard, un ratio recommandé, ni un type de joint.
# - Calcule tout ce qui est déductible si :
#   * on a un Piston (objet backend.pieces.piston.Piston) et son rapport calculé
#     (piston.analyser()) incluant : diametre_piston_cao_centre_m, diametre_fond_rainure_m,
#     profondeur_radiale_rainure_m, largeur_rainure_m, alesage_nominal_m, etc.
#   * et/ou un Cylindre (alesage_m)
#   * et/ou un joint (ID/CS) explicitement fourni
#
# Ce module sait :
# - reprendre automatiquement la géométrie de gorge calculée dans piston.py (si dispo)
# - calculer volume/surface du tore si ID+CS
# - calculer volume de gorge si (Df, w, d)
# - calculer stretch si ID + D_montage (fond gorge ou piston)
# - calculer squeeze radial si CS + D_cyl + D_fond_gorge
# - calculer aire de contact et frottement si (bande_contact, p_contact, mu)
# - estimer p_contact si module élastomère explicite (ou résoluble via materiaux.py) + squeeze
#
# IMPORTANT :
# - Toute "norme" (ISO 3601, recommandations squeeze/stretch) doit être entrée comme contrainte
#   explicite par l'utilisateur ; sinon ce module ne fait que calculer la géométrie.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal
import math

# =============================================================================
# Imports projet (optionnels, robustes)
# =============================================================================

try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# =============================================================================
# Helpers
# =============================================================================

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

def _push_inc(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
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


def _perimetre(D_m: float) -> float:
    return math.pi * _req_pos("D_m", D_m)

def _aire_disque(D_m: float) -> float:
    D = _req_pos("D_m", D_m)
    return math.pi * (0.5 * D) ** 2


# =============================================================================
# Matériaux : récupération cohérente depuis backend.ensemble.materiaux
# =============================================================================

def _materiau_props(
    cle: Optional[str],
    *,
    mode: Literal["min", "typique", "max"] = "typique",
) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {
        "densite_kg_m3": None,
        # élastomère
        "module_elastomere_pa": None,
    }
    if not cle or get_materiau is None:
        return out
    m = get_materiau(cle)
    if m is None:
        return out

    out["densite_kg_m3"] = valeur(getattr(m, "densite_kg_m3", None), mode=mode)
    # certains jeux de données mettent "module_elastomere_pa", sinon fallback young
    out["module_elastomere_pa"] = valeur(getattr(m, "module_elastomere_pa", None), mode=mode)
    if out["module_elastomere_pa"] is None:
        out["module_elastomere_pa"] = valeur(getattr(m, "module_young_pa", None), mode=mode)
    return out


# =============================================================================
# Géométrie torique
# =============================================================================

def tore_volume_m3(ID_m: float, CS_m: float) -> float:
    IDv = _req_pos("ID_m", ID_m)
    CSv = _req_pos("CS_m", CS_m)
    r = 0.5 * CSv
    R = 0.5 * IDv + r
    return 2.0 * (math.pi**2) * R * (r**2)

def tore_surface_m2(ID_m: float, CS_m: float) -> float:
    IDv = _req_pos("ID_m", ID_m)
    CSv = _req_pos("CS_m", CS_m)
    r = 0.5 * CSv
    R = 0.5 * IDv + r
    return 4.0 * (math.pi**2) * R * r

def tore_diametre_moyen_m(ID_m: float, CS_m: float) -> float:
    IDv = _req_pos("ID_m", ID_m)
    CSv = _req_pos("CS_m", CS_m)
    return IDv + CSv


# =============================================================================
# JointPiston
# =============================================================================

@dataclass(frozen=True)
class JointPiston:
    """
    Joint piston <-> cylindre.
    Par défaut, si ID/CS sont fournis => joint torique (modèle géométrique).
    Sinon, on ne "devine" pas ID/CS.
    """

    # Pièces liées (optionnel, mais permet de récupérer la gorge calculée par piston.py)
    piston: Optional[Any] = None    # backend.pieces.piston.Piston
    cylindre: Optional[Any] = None  # backend.pieces.cylindre.Cylindre

    # Rapport calculé du piston (sortie piston.analyser()).
    # Si fourni, c'est la meilleure source "sans hypothèse".
    rapport_piston: Optional[Dict[str, Any]] = None

    # Joint torique (si connu)
    diametre_interieur_joint_m: Optional[float] = None  # ID
    diametre_section_joint_m: Optional[float] = None    # CS

    # Gorge (si connue) — sinon peut être reprise depuis rapport_piston["joints"]
    diametre_fond_gorge_m: Optional[float] = None
    profondeur_gorge_m: Optional[float] = None          # profondeur radiale (fond->extérieur piston)
    largeur_gorge_m: Optional[float] = None             # largeur axiale

    # Cylindre (si non disponible via cylindre)
    diametre_interieur_cylindre_m: Optional[float] = None

    # Frottement / contact (si tu veux forces)
    pression_diff_pa: Optional[float] = None            # Δp global (ordre de grandeur)
    pression_contact_pa: Optional[float] = None         # si connue
    coeff_frottement_mu: Optional[float] = None
    largeur_bande_contact_m: Optional[float] = None

    # Matière joint (non devinable)
    materiau_joint_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    module_elastomere_pa: Optional[float] = None        # override direct
    mode_materiau: Literal["min", "typique", "max"] = "typique"

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "sources": {},
            "geometrie_joint": {},
            "gorge": {},
            "squeeze_stretch": {},
            "efforts": {},
            "frottements": {},
            "matiere": {},
            "coherences": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ---------------------------------------------------------------------
        # 1) Récupérer D_cyl depuis cylindre / entrée
        # ---------------------------------------------------------------------
        D_cyl = self.diametre_interieur_cylindre_m
        if D_cyl is None and self.cylindre is not None:
            for attr in ("alesage_m", "diametre_interieur_m", "diametre_alesage_m"):
                if hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        D_cyl = float(v)
                        rapport["sources"]["diametre_interieur_cylindre_m"] = f"cylindre.{attr}"
                        break

        # ---------------------------------------------------------------------
        # 2) Récupérer géométrie gorge depuis rapport piston si dispo
        # ---------------------------------------------------------------------
        D_fond = self.diametre_fond_gorge_m
        prof = self.profondeur_gorge_m
        larg = self.largeur_gorge_m

        if self.rapport_piston is not None:
            j = (self.rapport_piston.get("joints") or {})
            if D_fond is None and j.get("diametre_fond_rainure_m") is not None:
                D_fond = float(j["diametre_fond_rainure_m"])
                rapport["sources"]["diametre_fond_gorge_m"] = "rapport_piston.joints.diametre_fond_rainure_m"
            if prof is None and j.get("profondeur_radiale_rainure_m") is not None:
                prof = float(j["profondeur_radiale_rainure_m"])
                rapport["sources"]["profondeur_gorge_m"] = "rapport_piston.joints.profondeur_radiale_rainure_m"
            if larg is None and j.get("largeur_rainure_m") is not None:
                larg = float(j["largeur_rainure_m"])
                rapport["sources"]["largeur_gorge_m"] = "rapport_piston.joints.largeur_rainure_m"

            # si le piston avait un alésages_nominal (utile pour fallback D_cyl)
            if D_cyl is None:
                D_cyl2 = self.rapport_piston.get("dimensions", {}).get("alesage_min_m") or self.rapport_piston.get("liaisons", {}).get("cylindre", {}).get("alesage_nominal_m")
                if D_cyl2 is not None:
                    D_cyl = float(D_cyl2)
                    rapport["sources"]["diametre_interieur_cylindre_m"] = "rapport_piston (fallback)"

        # ---------------------------------------------------------------------
        # 3) Entrées joint (ID/CS)
        # ---------------------------------------------------------------------
        ID = self.diametre_interieur_joint_m
        CS = self.diametre_section_joint_m

        # Possibilité : reprendre CS/ID depuis des entrées piston si ton piston les stocke.
        # (sans rien inventer : on lit seulement si présent)
        if self.rapport_piston is not None:
            pj = (self.rapport_piston.get("joints") or {})
            # section_joint_m éventuelle
            if CS is None and pj.get("section_joint_m") is not None:
                CS = float(pj["section_joint_m"])
                rapport["sources"]["diametre_section_joint_m"] = "rapport_piston.joints.section_joint_m"
            # ID n'est en général pas donné par piston.py (il calcule la gorge), donc on ne le devine pas.

        # ---------------------------------------------------------------------
        # 4) Récap entrées
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "diametre_interieur_cylindre_m": D_cyl,
            "diametre_interieur_joint_m": ID,
            "diametre_section_joint_m": CS,
            "diametre_fond_gorge_m": D_fond,
            "profondeur_gorge_m": prof,
            "largeur_gorge_m": larg,
            "pression_diff_pa": self.pression_diff_pa,
            "pression_contact_pa": self.pression_contact_pa,
            "coeff_frottement_mu": self.coeff_frottement_mu,
            "largeur_bande_contact_m": self.largeur_bande_contact_m,
            "materiau_joint_cle": self.materiau_joint_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "module_elastomere_pa": self.module_elastomere_pa,
            "mode_materiau": self.mode_materiau,
        }

        # ---------------------------------------------------------------------
        # 5) Géométrie du joint (tore) si ID+CS
        # ---------------------------------------------------------------------
        V_joint = None
        S_joint = None
        D_moy = None
        perim_moy = None
        if ID is not None and CS is not None:
            IDv = _req_pos("diametre_interieur_joint_m", ID)
            CSv = _req_pos("diametre_section_joint_m", CS)
            V_joint = tore_volume_m3(IDv, CSv)
            S_joint = tore_surface_m2(IDv, CSv)
            D_moy = tore_diametre_moyen_m(IDv, CSv)
            perim_moy = _perimetre(D_moy)
            rapport["geometrie_joint"].update({
                "volume_joint_m3": V_joint,
                "surface_joint_m2": S_joint,
                "diametre_moyen_joint_m": D_moy,
                "perimetre_moyen_joint_m": perim_moy,
                "rayon_section_m": 0.5 * CSv,
            })
        else:
            _push_inc(
                rapport,
                "impossibles",
                "geometrie_joint_torique",
                "Pour calculer la géométrie d’un tore, fournir diametre_interieur_joint_m ET diametre_section_joint_m (ID/CS).",
            )

        # ---------------------------------------------------------------------
        # 6) Géométrie de gorge + volume gorge
        # ---------------------------------------------------------------------
        V_gorge = None
        if D_fond is not None and prof is not None and larg is not None:
            Df = _req_pos("diametre_fond_gorge_m", D_fond)
            pr = _req_pos("profondeur_gorge_m", prof)
            w = _req_pos("largeur_gorge_m", larg)
            perim_fond = _perimetre(Df)
            A_sec = pr * w  # modèle rectangulaire explicite
            V_gorge = perim_fond * A_sec
            rapport["gorge"].update({
                "perimetre_fond_gorge_m": perim_fond,
                "section_gorge_rect_m2": A_sec,
                "volume_gorge_m3": V_gorge,
            })
            if V_joint is not None and V_gorge > 0:
                rapport["gorge"]["taux_remplissage_volume_joint_sur_gorge"] = V_joint / V_gorge
        else:
            _push_inc(
                rapport,
                "partielles",
                "volume_gorge",
                "Calculable si diametre_fond_gorge_m + profondeur_gorge_m + largeur_gorge_m sont connus (piston.py peut les fournir).",
            )

        # ---------------------------------------------------------------------
        # 7) Stretch (étirement)
        # ---------------------------------------------------------------------
        # stretch = (D_montage - ID)/ID
        # D_montage : diamètre autour duquel l'ID s'étire. Sans norme, on prend explicitement :
        # - D_montage = diametre_fond_gorge_m (si gorge connue), sinon impossible.
        if ID is not None:
            IDv = _req_pos("diametre_interieur_joint_m", ID)
            if D_fond is not None:
                Dm = _req_pos("diametre_fond_gorge_m", D_fond)
                stretch = (Dm - IDv) / IDv
                rapport["squeeze_stretch"]["diametre_montage_stretch_m"] = Dm
                rapport["squeeze_stretch"]["stretch_fraction"] = stretch
            else:
                _push_inc(
                    rapport,
                    "partielles",
                    "stretch_fraction",
                    "Calculable si diametre_fond_gorge_m est connu (diamètre de montage).",
                )

        # ---------------------------------------------------------------------
        # 8) Squeeze (écrasement radial)
        # ---------------------------------------------------------------------
        # Hypothèse géométrique EXPLICITE : joint torique en gorge sur piston, comprimé par cylindre.
        # h_dispo = (D_cyl - D_fond)/2
        # squeeze = (CS - h_dispo)/CS
        squeeze = None
        if CS is not None and D_cyl is not None and D_fond is not None:
            CSv = _req_pos("diametre_section_joint_m", CS)
            Dc = _req_pos("diametre_interieur_cylindre_m", D_cyl)
            Df = _req_pos("diametre_fond_gorge_m", D_fond)
            h_dispo = (Dc - Df) / 2.0
            squeeze = (CSv - h_dispo) / CSv
            rapport["squeeze_stretch"].update({
                "hauteur_radiale_disponible_m": h_dispo,
                "squeeze_radial_fraction": squeeze,
            })
        else:
            _push_inc(
                rapport,
                "partielles",
                "squeeze_radial_fraction",
                "Calculable si diametre_section_joint_m + diametre_interieur_cylindre_m + diametre_fond_gorge_m sont connus.",
            )

        # ---------------------------------------------------------------------
        # 9) Estimation pression de contact (optionnelle) : p_contact ~= E * squeeze
        # ---------------------------------------------------------------------
        # Modèle simplifié explicite. Aucun choix de E si non fourni/résolu.
        p_contact_est = None
        Eel = self.module_elastomere_pa
        if Eel is None and self.materiau_joint_cle:
            props = _materiau_props(self.materiau_joint_cle, mode=self.mode_materiau)
            Eel = props.get("module_elastomere_pa")

        if squeeze is not None:
            if Eel is not None:
                Eelv = _req_pos("module_elastomere_pa", Eel)
                p_contact_est = Eelv * squeeze
                rapport["matiere"]["module_elastomere_pa"] = Eelv
                rapport["efforts"]["pression_contact_estimee_pa"] = p_contact_est
                rapport["notes_modele"].append("p_contact estimée via modèle explicite p≈E*squeeze (simplifié).")
            else:
                _push_inc(
                    rapport,
                    "partielles",
                    "pression_contact_estimee_pa",
                    "Estimable si module_elastomere_pa (override) ou materiau_joint_cle résoluble (module) est disponible.",
                )

        # ---------------------------------------------------------------------
        # 10) Aire de contact + frottement
        # ---------------------------------------------------------------------
        # Aire ≈ périmètre moyen * largeur_bande_contact
        # Force frottement ≈ mu * (p_contact * Aire)
        A_contact = None
        if perim_moy is not None and self.largeur_bande_contact_m is not None:
            b = _req_pos("largeur_bande_contact_m", self.largeur_bande_contact_m)
            A_contact = perim_moy * b
            rapport["frottements"]["aire_contact_m2"] = A_contact
        else:
            _push_inc(
                rapport,
                "partielles",
                "aire_contact_m2",
                "Calculable si largeur_bande_contact_m est fournie ET si le joint (ID/CS) est défini.",
            )

        # Choix pression contact : priorité à pression_contact_pa explicite, sinon estimation
        p_use = None
        if self.pression_contact_pa is not None:
            p_use = _req_pos("pression_contact_pa", self.pression_contact_pa, strictly=False)
            rapport["efforts"]["pression_contact_utilisee_pa"] = p_use
            rapport["sources"]["pression_contact_utilisee_pa"] = "entree pression_contact_pa"
        elif p_contact_est is not None:
            p_use = float(p_contact_est)
            rapport["efforts"]["pression_contact_utilisee_pa"] = p_use
            rapport["sources"]["pression_contact_utilisee_pa"] = "estimation E*squeeze"

        if self.coeff_frottement_mu is not None and p_use is not None and A_contact is not None:
            mu = _req_pos("coeff_frottement_mu", self.coeff_frottement_mu, strictly=False)
            N = p_use * A_contact
            Ff = mu * N
            rapport["frottements"].update({
                "coeff_frottement_mu": mu,
                "effort_normal_estime_N": N,
                "force_frottement_estimee_N": Ff,
                "modele": "F = mu * (p_contact * A_contact)",
            })
        else:
            _push_inc(
                rapport,
                "partielles",
                "force_frottement_estimee_N",
                "Calculable si coeff_frottement_mu + (pression_contact_pa ou E*squeeze) + aire_contact_m2 sont connus.",
            )

        # ---------------------------------------------------------------------
        # 11) Force pression équivalente globale (ordre de grandeur)
        # ---------------------------------------------------------------------
        if self.pression_diff_pa is not None and D_cyl is not None:
            dp = _req_finite("pression_diff_pa", self.pression_diff_pa)
            Dc = _req_pos("diametre_interieur_cylindre_m", D_cyl)
            Aref = _aire_disque(Dc)
            Fp = abs(dp) * Aref
            rapport["efforts"].update({
                "aire_reference_disque_cylindre_m2": Aref,
                "force_pression_equivalente_N": Fp,
                "note": "Ordre de grandeur global Δp * aire cylindre (pas force locale sur joint).",
            })
        else:
            _push_inc(
                rapport,
                "partielles",
                "force_pression_equivalente_N",
                "Calculable si pression_diff_pa et diametre_interieur_cylindre_m sont fournis.",
            )

        # ---------------------------------------------------------------------
        # 12) Matière : densité -> masse si volume joint connu
        # ---------------------------------------------------------------------
        rho = self.densite_kg_m3
        if rho is None and self.materiau_joint_cle:
            props = _materiau_props(self.materiau_joint_cle, mode=self.mode_materiau)
            rho = props.get("densite_kg_m3")

        if rho is not None:
            rhov = _req_pos("densite_kg_m3", rho)
            rapport["matiere"]["densite_kg_m3"] = rhov
            if V_joint is not None:
                rapport["matiere"]["masse_joint_kg"] = rhov * V_joint
            else:
                _push_inc(rapport, "partielles", "masse_joint_kg", "Calculable si volume_joint_m3 est calculable (ID/CS).")
        else:
            _push_inc(
                rapport,
                "impossibles",
                "densite_kg_m3",
                "Impossible sans densite_kg_m3 ou materiau_joint_cle résoluble via materiaux.py.",
            )

        # ---------------------------------------------------------------------
        # 13) Cohérences géométriques simples (sans norme)
        # ---------------------------------------------------------------------
        # - squeeze <= 0 : pas d'écrasement
        # - squeeze >= 1 : impossible
        if squeeze is not None:
            rapport["coherences"]["squeeze_positive"] = (squeeze > 0.0)
            rapport["coherences"]["squeeze_moins_100pct"] = (squeeze < 1.0)
            if squeeze <= 0.0:
                rapport["notes_modele"].append("SQUEEZE <= 0 : pas d'écrasement (risque étanchéité nulle).")
            if squeeze >= 1.0:
                rapport["notes_modele"].append("SQUEEZE >= 1 : montage impossible (écrasement >= 100%).")

        # - taux remplissage gorge (si dispo)
        tr = rapport.get("gorge", {}).get("taux_remplissage_volume_joint_sur_gorge")
        if tr is not None:
            rapport["coherences"]["taux_remplissage_le_1"] = (float(tr) <= 1.0)
            if float(tr) > 1.0:
                rapport["notes_modele"].append("Taux remplissage volume > 1 : joint ne rentre pas dans gorge (modèle gorge rectangulaire).")

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "JointPiston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport


# =============================================================================
# Exemple minimal
# =============================================================================
if __name__ == "__main__":
    # Exemple sans invention :
    # - on suppose que tu as déjà un rapport piston (issu de Piston(...).analyser()).
    # - tu fournis ID/CS si tu connais le joint exact.
    jp = JointPiston(
        rapport_piston=None,  # mets ici le dict retourné par piston.analyser()
        diametre_interieur_cylindre_m=0.080,
        diametre_interieur_joint_m=0.074,   # ID (exemple)
        diametre_section_joint_m=0.003,     # CS (exemple)
        diametre_fond_gorge_m=0.077,
        profondeur_gorge_m=0.0012,
        largeur_gorge_m=0.0045,
        largeur_bande_contact_m=0.003,
        coeff_frottement_mu=0.15,
        pression_contact_pa=2e6,
        materiau_joint_cle="nbr_70",
    )

    from pprint import pprint
    pprint(jp.analyser(strict=False))

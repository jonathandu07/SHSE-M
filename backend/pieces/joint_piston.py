# backend/pieces/joint_piston.py
# =============================================================================
# JOINT PISTON — étanchéité piston <-> cylindre (côté froid)
# =============================================================================
# Objectif (strict "rien inventer") :
# - Calculer TOUT ce qui est calculable à partir :
#   - des dimensions du piston/cylindre (si objets fournis)
#   - des dimensions du joint (ID/CS) si fournies
#   - des dimensions de gorge si fournies (profondeur/largeur/diamètres)
#   - des propriétés matériau si fournies (ou résolues via materiaux.py)
#
# IMPORTANT :
# - On ne "devine" PAS :
#   - type exact de joint (torique, segments, U-cup, etc.)
#   - ratios de squeeze/étirement "recommandés" (normes) => si tu veux ces ratios,
#     tu dois les fournir explicitement.
# - Le module calcule :
#   - géométrie du joint (volume, surface, longueur de joint, masse si densité)
#   - compatibilité dimensionnelle ID/CS vs gorge (si gorge définie)
#   - squeeze (écrasement) et stretch (étirement) si géométrie suffisante
#   - aire de contact approximative (si largeur de bande fournie)
#   - effort friction estimé si pression de contact fournie
#
# Pour un piston "segmenté" (rings métalliques), il faut un autre module dédié :
# gorge(s), épaisseurs, jeu à la coupe, pression radiale, etc.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import math


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


# =============================================================================
# Résolution matériau (optionnelle) via materiaux.py
# =============================================================================

def _resoudre_materiau_joint(
    materiau_joint_cle: Optional[str],
    densite_kg_m3: Optional[float],
) -> Dict[str, Optional[float]]:
    rho = densite_kg_m3
    if materiau_joint_cle:
        for modname in (
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                if hasattr(mod, "get_materiau"):
                    m = mod.get_materiau(materiau_joint_cle)  # type: ignore[attr-defined]
                    if isinstance(m, dict):
                        rho = rho if rho is not None else m.get("densite_kg_m3")
                elif hasattr(mod, "MATERIAUX"):
                    m = getattr(mod, "MATERIAUX", {}).get(materiau_joint_cle)
                    if isinstance(m, dict):
                        rho = rho if rho is not None else m.get("densite_kg_m3")
                break
            except Exception:
                continue
    return {"densite_kg_m3": rho}


# =============================================================================
# Modèle joint piston (TORIQUE par défaut si ID/CS)
# =============================================================================

@dataclass(frozen=True)
class JointPiston:
    """
    Joint piston <-> cylindre.

    Deux modes possibles, SANS invention :
    (A) Tu fournis un joint torique (ID/CS), et éventuellement une gorge.
    (B) Tu ne fournis pas ID/CS, mais tu fournis une gorge et un "diamètre d'assise"
        => on peut déduire ID théorique du joint monté, mais PAS choisir le CS.

    Entrées minimales pour calculer une géométrie complète de joint torique :
    - diametre_interieur_joint_m (ID)
    - diametre_section_joint_m  (CS)

    Si tu veux squeeze/stretch :
    - il faut la géométrie de montage :
      * pour le stretch : diamètre de portée (piston ou gorge) comparé à l'ID
      * pour le squeeze : diamètre cylindre + profondeur gorge vs CS

    NOTE : Ce module ne remplace pas une norme ISO 3601.
    """

    # ---- Pièces liées (optionnel mais recommandé)
    piston: Optional[Any] = None    # backend.pieces.piston.Piston
    cylindre: Optional[Any] = None  # backend.pieces.cylindre.Cylindre

    # ---- Joint torique (si connu)
    diametre_interieur_joint_m: Optional[float] = None  # ID
    diametre_section_joint_m: Optional[float] = None    # CS

    # ---- Gorge (si connue) : joint en gorge sur piston
    # Diamètre au fond de gorge (sur piston) :
    diametre_fond_gorge_m: Optional[float] = None
    # Profondeur radiale de gorge (du Ø fond vers Ø extérieur piston) :
    profondeur_gorge_m: Optional[float] = None
    # Largeur axiale gorge :
    largeur_gorge_m: Optional[float] = None

    # ---- Montage dans cylindre
    # Diamètre intérieur cylindre (si non disponible via cylindre):
    diametre_interieur_cylindre_m: Optional[float] = None

    # ---- Pression / frottement (uniquement si tu fournis ce qu'il faut)
    pression_diff_pa: Optional[float] = None       # Δp à étancher (si tu veux des efforts équivalents)
    pression_contact_pa: Optional[float] = None    # pression de contact (si connue par ailleurs)
    coeff_frottement_mu: Optional[float] = None    # mu (si connu)
    largeur_bande_contact_m: Optional[float] = None  # largeur de bande de contact (si tu veux aire contact)

    # ---- Matière (impossible à deviner)
    materiau_joint_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "geometrie_joint": {},
            "montage": {},
            "squeeze_stretch": {},
            "efforts": {},
            "frottements": {},
            "matiere": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ---------------------------------------------------------------------
        # 1) Récupérer diamètres depuis les pièces si possibles
        # ---------------------------------------------------------------------
        D_cyl = self.diametre_interieur_cylindre_m
        if D_cyl is None and self.cylindre is not None:
            for attr in ("alesage_m", "diametre_interieur_m", "diametre_alesage_m"):
                if hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        D_cyl = float(v)
                        break

        D_piston = None
        if self.piston is not None:
            # piston.py calcule souvent diametre_piston_m ; sinon, on tente une entrée
            for attr in ("diametre_piston_m", "Dp_m", "diametre_m"):
                if hasattr(self.piston, attr):
                    v = getattr(self.piston, attr)
                    if v is not None:
                        D_piston = float(v)
                        break
            # si piston stocke un rapport calculé
            if D_piston is None and hasattr(self.piston, "diametre_piston_m"):
                try:
                    D_piston = float(getattr(self.piston, "diametre_piston_m"))
                except Exception:
                    pass

        # ---------------------------------------------------------------------
        # 2) Entrées joint (ID/CS) + géométrie tore si possible
        # ---------------------------------------------------------------------
        ID = self.diametre_interieur_joint_m
        CS = self.diametre_section_joint_m

        rapport["entrees"].update({
            "diametre_interieur_cylindre_m": D_cyl,
            "diametre_piston_m": D_piston,
            "diametre_interieur_joint_m": ID,
            "diametre_section_joint_m": CS,
            "diametre_fond_gorge_m": self.diametre_fond_gorge_m,
            "profondeur_gorge_m": self.profondeur_gorge_m,
            "largeur_gorge_m": self.largeur_gorge_m,
            "pression_diff_pa": self.pression_diff_pa,
            "pression_contact_pa": self.pression_contact_pa,
            "coeff_frottement_mu": self.coeff_frottement_mu,
            "largeur_bande_contact_m": self.largeur_bande_contact_m,
            "materiau_joint_cle": self.materiau_joint_cle,
            "densite_kg_m3": self.densite_kg_m3,
        })

        # Calcul volume/surface si ID et CS connus (tore)
        V_joint = None
        S_joint = None
        perimetre_moyen = None
        if ID is not None and CS is not None:
            IDv = _req_pos("diametre_interieur_joint_m", ID)
            CSv = _req_pos("diametre_section_joint_m", CS)
            r = 0.5 * CSv
            R = 0.5 * IDv + r
            V_joint = 2.0 * (math.pi**2) * R * (r**2)
            S_joint = 4.0 * (math.pi**2) * R * r
            # périmètre au diamètre moyen ~ (ID + CS)
            D_moy = IDv + CSv
            perimetre_moyen = math.pi * D_moy
            rapport["geometrie_joint"].update({
                "rayon_tube_r_m": r,
                "rayon_majeur_R_m": R,
                "diametre_moyen_joint_m": D_moy,
                "perimetre_moyen_joint_m": perimetre_moyen,
                "volume_joint_m3": V_joint,
                "surface_joint_m2": S_joint,
            })
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "géométrie joint torique",
                "Pour calculer volume/surface d'un joint torique, fournir diametre_interieur_joint_m ET diametre_section_joint_m.",
            )

        # ---------------------------------------------------------------------
        # 3) Géométrie de gorge (si fournie) + volumes libres
        # ---------------------------------------------------------------------
        V_gorge = None
        taux_remplissage = None

        # Gorge = anneau : A_section_gorge ≈ (largeur_gorge * profondeur_gorge) en section rectangulaire,
        # volume = périmètre * A_section
        # Mais il faut un diamètre de référence (fond de gorge) pour le périmètre.
        if self.diametre_fond_gorge_m is not None and self.largeur_gorge_m is not None and self.profondeur_gorge_m is not None:
            Df = _req_pos("diametre_fond_gorge_m", self.diametre_fond_gorge_m)
            w = _req_pos("largeur_gorge_m", self.largeur_gorge_m)
            d = _req_pos("profondeur_gorge_m", self.profondeur_gorge_m)
            perim = math.pi * Df
            A_sec = w * d
            V_gorge = perim * A_sec
            rapport["montage"].update({
                "perimetre_fond_gorge_m": perim,
                "section_gorge_m2": A_sec,
                "volume_gorge_m3": V_gorge,
            })

            if V_joint is not None and V_gorge > 0:
                taux_remplissage = V_joint / V_gorge
                rapport["montage"]["taux_remplissage_volume_joint_sur_gorge"] = taux_remplissage
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "volume_gorge",
                "Calculable si diametre_fond_gorge_m + largeur_gorge_m + profondeur_gorge_m sont fournis.",
            )

        # ---------------------------------------------------------------------
        # 4) Stretch (étirement) — nécessite ID joint + diamètre de montage
        # ---------------------------------------------------------------------
        # Étirement = (D_montage - ID) / ID
        # D_montage : typiquement diamètre au fond de gorge + CS (centre du tore) ou diamètre extérieur piston
        # => on ne l'invente pas : on utilise diametre_fond_gorge_m si fourni, sinon diametre_piston_m.
        stretch = None
        if ID is not None:
            IDv = _req_pos("diametre_interieur_joint_m", ID)
            D_montage = None
            if self.diametre_fond_gorge_m is not None:
                # Le joint s'assoit autour du fond de gorge : diamètre autour duquel s'étire l'ID
                D_montage = _req_pos("diametre_fond_gorge_m", self.diametre_fond_gorge_m)
            elif D_piston is not None:
                D_montage = _req_pos("diametre_piston_m", D_piston)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "stretch_joint",
                    "Calculable si diametre_fond_gorge_m (ou diametre_piston_m) est connu.",
                )

            if D_montage is not None:
                stretch = (D_montage - IDv) / IDv
                rapport["squeeze_stretch"]["diametre_montage_stretch_m"] = D_montage
                rapport["squeeze_stretch"]["stretch_fraction"] = stretch
        # sinon déjà inconnue "impossible" via géométrie

        # ---------------------------------------------------------------------
        # 5) Squeeze (écrasement radial) — nécessite CS + gorge + cylindre/piston
        # ---------------------------------------------------------------------
        # Pour un joint torique en gorge sur piston, comprimé par le cylindre :
        # - rayon cylindre = D_cyl/2
        # - rayon au fond gorge = D_fond/2
        # - hauteur radiale disponible entre fond de gorge et cylindre : h_dispo = (D_cyl - D_fond)/2
        # - CS = diamètre section => épaisseur radiale libre = CS
        # - squeeze_radial = (CS - h_dispo) / CS
        #
        # ATTENTION : ceci suppose que le joint est "posé" au fond de gorge.
        # Si géométrie réelle différente (sur-épaulement, etc.), fournir les dimensions exactes.
        squeeze = None
        h_dispo = None
        if CS is not None and D_cyl is not None and self.diametre_fond_gorge_m is not None:
            CSv = _req_pos("diametre_section_joint_m", CS)
            Dc = _req_pos("diametre_interieur_cylindre_m", D_cyl)
            Df = _req_pos("diametre_fond_gorge_m", self.diametre_fond_gorge_m)

            h_dispo = (Dc - Df) / 2.0
            rapport["squeeze_stretch"]["hauteur_radiale_disponible_m"] = h_dispo

            squeeze = (CSv - h_dispo) / CSv
            rapport["squeeze_stretch"]["squeeze_radial_fraction"] = squeeze
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "squeeze_joint",
                "Calculable si diametre_section_joint_m + diametre_fond_gorge_m + diametre_interieur_cylindre_m sont connus.",
            )

        # ---------------------------------------------------------------------
        # 6) Aire contact + frottement (si données explicites)
        # ---------------------------------------------------------------------
        # Aire_contact ≈ périmètre_moyen * largeur_bande_contact
        A_contact = None
        F_frott = None

        if perimetre_moyen is not None and self.largeur_bande_contact_m is not None:
            w = _req_pos("largeur_bande_contact_m", self.largeur_bande_contact_m)
            A_contact = perimetre_moyen * w
            rapport["frottements"]["aire_contact_m2"] = A_contact
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "aire_contact",
                "Calculable si largeur_bande_contact_m est fournie (et si le joint torique est défini).",
            )

        # Frottement Coulomb : F = mu * N ; N ≈ p_contact * A_contact
        if self.coeff_frottement_mu is not None and self.pression_contact_pa is not None and A_contact is not None:
            mu = _req_pos("coeff_frottement_mu", self.coeff_frottement_mu, strictly=False)
            pc = _req_pos("pression_contact_pa", self.pression_contact_pa, strictly=False)
            N = pc * A_contact
            F_frott = mu * N
            rapport["frottements"].update({
                "effort_normal_estime_N": N,
                "force_frottement_estimee_N": F_frott,
                "modele": "F = mu * (p_contact * A_contact). p_contact doit être fourni (sinon non calculable sans modèle matériau).",
            })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force_frottement_estimee_N",
                "Calculable si coeff_frottement_mu + pression_contact_pa + aire_contact_m2 sont connus.",
            )

        # ---------------------------------------------------------------------
        # 7) Effort pression équivalent (si demandé)
        # ---------------------------------------------------------------------
        # Une estimation simple : F = Δp * A_ref avec A_ref = aire disque diamètre intérieur cylindre
        # MAIS ce n'est pas la force sur le joint ; c'est un ordre de grandeur de charge système.
        if self.pression_diff_pa is not None and D_cyl is not None:
            dp = _req_finite("pression_diff_pa", self.pression_diff_pa)
            Dc = _req_pos("diametre_interieur_cylindre_m", D_cyl)
            Aref = math.pi * (0.5 * Dc) ** 2
            Fp = abs(dp) * Aref
            rapport["efforts"].update({
                "aire_reference_disque_cylindre_m2": Aref,
                "force_pression_equivalente_N": Fp,
                "note": "Ordre de grandeur global (Δp * aire cylindre). Pas une force locale sur le joint.",
            })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force_pression_equivalente_N",
                "Calculable si pression_diff_pa et diametre_interieur_cylindre_m sont fournis.",
            )

        # ---------------------------------------------------------------------
        # 8) Matière : densité => masse, sinon inconnue
        # ---------------------------------------------------------------------
        props = _resoudre_materiau_joint(self.materiau_joint_cle, self.densite_kg_m3)
        rho = props["densite_kg_m3"]
        if rho is not None:
            rapport["matiere"]["densite_kg_m3"] = float(rho)
            if V_joint is not None:
                rapport["matiere"]["masse_joint_kg"] = float(rho) * V_joint
            else:
                _push_inconnue(rapport, "partielles", "masse_joint_kg", "Calculable si volume_joint_m3 est calculable (ID/CS requis).")
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "matière du joint",
                "Impossible de déterminer la matière sans materiau_joint_cle (résoluble) ou densite_kg_m3 fournie. La matière ne se devine pas.",
            )

        # ---------------------------------------------------------------------
        # 9) Contrôles de cohérence simples (sans normes)
        # ---------------------------------------------------------------------
        if squeeze is not None:
            # squeeze > 1 => impossible (écrasement > 100%)
            if squeeze >= 1.0:
                rapport["notes_modele"].append("SQUEEZE >= 1 : montage géométriquement impossible (écrasement >= 100%).")
            # squeeze < 0 => pas de contact (jeu)
            if squeeze <= 0.0:
                rapport["notes_modele"].append("SQUEEZE <= 0 : pas d'écrasement (risque étanchéité nulle).")

        if taux_remplissage is not None:
            # >1 signifie le joint ne rentre pas en volume (si gorge rectangulaire simplifiée)
            if taux_remplissage > 1.0:
                rapport["notes_modele"].append("Taux remplissage volume > 1 : joint ne peut pas rentrer dans la gorge (géométrie incohérente).")

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "JointPiston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport

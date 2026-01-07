# backend/pieces/joint_deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal
import math

# ============================================================
# Imports projet (optionnels) — cohérence avec autres pièces
# ============================================================

# Matériaux génériques projet (si tu as une base matériaux)
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# Déplaceur (pour récupérer section/squeeze/nb joints/pressions/températures si définis)
try:
    from backend.pieces.deplaceur import Deplaceur  # type: ignore
except Exception:  # pragma: no cover
    Deplaceur = None  # type: ignore


# Cylindre (pour récupérer l’alésage si défini)
try:
    from backend.pieces.cylindre import Cylindre  # type: ignore
except Exception:  # pragma: no cover
    Cylindre = None  # type: ignore


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

def _req_int_ge(name: str, x: Any, *, min_value: int = 0) -> int:
    if not isinstance(x, (int, float)) or int(x) != x:
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    xi = int(x)
    if xi < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {xi}).")
    return xi

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
# Géométrie : modèles EXPLICITES (sans norme implicite)
# ============================================================

def perimetre_cercle(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    return math.pi * D

def aire_disque(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    r = 0.5 * D
    return math.pi * r * r

def aire_section_joint_torique(section_joint_m: float) -> float:
    """Section du tore (cercle) : A = pi*(d/2)^2"""
    d = _req_pos("section_joint_m", section_joint_m)
    return math.pi * (0.5 * d) ** 2

def volume_joint_torique_approx(
    *,
    diametre_centreline_m: float,
    section_joint_m: float,
) -> float:
    """
    Volume ≈ Aire_section * périmètre_centreline.
    Hypothèse explicite : tore circulaire parfait, sans aplatissement.
    """
    Dc = _req_pos("diametre_centreline_m", diametre_centreline_m)
    A = aire_section_joint_torique(section_joint_m)
    return A * perimetre_cercle(Dc)

def profondeur_gorge_depuis_squeeze(section_joint_m: float, squeeze: float) -> float:
    """
    Définition explicite (radiale) :
    profondeur = section * (1 - squeeze), squeeze dans (0,1)
    """
    s = _req_pos("section_joint_m", section_joint_m)
    sq = _req_pos("squeeze", squeeze, strictly=False)
    if not (0.0 < sq < 1.0):
        raise ValueError("squeeze doit être dans (0,1).")
    return s * (1.0 - sq)

def largeur_gorge_depuis_facteur(section_joint_m: float, facteur_largeur: float) -> float:
    """largeur = facteur_largeur * section (facteur fourni, non deviné)"""
    s = _req_pos("section_joint_m", section_joint_m)
    f = _req_pos("facteur_largeur", facteur_largeur)
    return f * s

def volume_gorge_annulaire_rect(
    *,
    diametre_fond_gorge_m: float,
    largeur_gorge_m: float,
    profondeur_gorge_m: float,
) -> float:
    """
    Modèle explicite :
    gorge annulaire rectangulaire ≈ périmètre(diamètre fond) * largeur * profondeur
    """
    Df = _req_pos("diametre_fond_gorge_m", diametre_fond_gorge_m)
    w = _req_pos("largeur_gorge_m", largeur_gorge_m)
    t = _req_pos("profondeur_gorge_m", profondeur_gorge_m)
    return perimetre_cercle(Df) * w * t

def jeu_radial_depuis_alesage_et_deplaceur(alesage_m: float, diametre_deplaceur_m: float) -> float:
    """jeu_radial = (D_cyl - D_dep)/2"""
    Dc = _req_pos("alesage_m", alesage_m)
    Dd = _req_pos("diametre_deplaceur_m", diametre_deplaceur_m)
    return 0.5 * (Dc - Dd)


# ============================================================
# Pièce : Joint torique du Déplaceur
# ============================================================

@dataclass(frozen=True)
class JointDeplaceur:
    """
    Joint(s) toriques du déplaceur, calculé(s) en s'appuyant sur :
    - Deplaceur : diamètre, nb joints, section joint, taux compression, pressions, températures…
    - Cylindre : alésage
    - Materiaux : si tu fournis un matériau de joint via ta base (sinon: contraintes mécaniques calculées)

    Aucun choix “catalogue” n’est fait ici :
    - On calcule des contraintes nécessaires (ex: module min pour obtenir p_contact) au lieu d’inventer un matériau.
    """

    # --- Références (optionnelles) ---
    deplaceur: Optional[Any] = None     # instance Deplaceur
    cylindre: Optional[Any] = None      # instance Cylindre

    # --- Données minimales (si pas d'objets) ---
    diametre_deplaceur_m: Optional[float] = None
    alesage_cylindre_m: Optional[float] = None
    jeu_radial_m: Optional[float] = None

    # --- Nombre de joints (sinon récupéré du déplaceur) ---
    nb_joints: Optional[int] = None

    # --- Données joint (sinon récupérées du déplaceur) ---
    section_joint_mm: Optional[float] = None     # diamètre de tore (mm)
    squeeze: Optional[float] = None              # compression radiale relative (0..1)
    facteur_largeur: Optional[float] = None      # largeur_gorge = facteur * section

    # --- Orientation du montage (pour déduire D_fond de gorge) ---
    # Sans cette info, D_fond n'est pas déductible “à coup sûr”.
    orientation: Optional[Literal["gorge_externe_sur_deplaceur"]] = "gorge_externe_sur_deplaceur"

    # --- Pression de service (sinon déduite des pressions du déplaceur/cylindre si présentes) ---
    pression_service_pa: Optional[float] = None

    # --- Matériau joint (optionnel) ---
    # Si ta base materiaux contient un élastomère, tu peux fournir sa clé ;
    # sinon, tu peux donner directement module_elastomere_pa.
    materiau_joint_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"
    module_elastomere_pa: Optional[float] = None  # override direct

    # --- Frottement (optionnel) ---
    coeff_frottement: Optional[float] = None
    largeur_bande_contact_m: Optional[float] = None  # pour aire contact ≈ périmètre*bande*nb_joints

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "liaisons_pieces": {},
            "geometrie": {},
            "gorge": {},
            "service": {},
            "materiau": {},
            "elasticite": {},
            "frottement": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # 1) Collecte depuis pièces (sans mutation dataclass)
        # ------------------------------------------------------------
        D_dep = self.diametre_deplaceur_m
        Dcyl = self.alesage_cylindre_m
        jeu = self.jeu_radial_m
        nb_j = self.nb_joints
        sec_mm = self.section_joint_mm
        sq = self.squeeze
        fL = self.facteur_largeur

        p_service = self.pression_service_pa

        if self.deplaceur is not None:
            # Diamètre
            if D_dep is None and hasattr(self.deplaceur, "diametre_exterieur_m"):
                D_dep = getattr(self.deplaceur, "diametre_exterieur_m")
            # Nb joints
            if nb_j is None and hasattr(self.deplaceur, "nb_joints_toriques"):
                nb_j = getattr(self.deplaceur, "nb_joints_toriques")
            # Section joint
            if sec_mm is None:
                if hasattr(self.deplaceur, "section_joint_mm"):
                    sec_mm = getattr(self.deplaceur, "section_joint_mm")
            # Squeeze
            if sq is None:
                if hasattr(self.deplaceur, "taux_compression_joint"):
                    sq = getattr(self.deplaceur, "taux_compression_joint")
            # Pressions (pour p_service si non fourni)
            p_hot = getattr(self.deplaceur, "pression_chaud_pa", None)
            p_cold = getattr(self.deplaceur, "pression_froid_pa", None)
            dp = getattr(self.deplaceur, "delta_p_chaud_froid_pa", None)

            rapport["liaisons_pieces"]["deplaceur"] = {
                "diametre_exterieur_m": D_dep,
                "nb_joints_toriques": nb_j,
                "section_joint_mm": sec_mm,
                "taux_compression_joint": sq,
                "pression_chaud_pa": p_hot,
                "pression_froid_pa": p_cold,
                "delta_p_chaud_froid_pa": dp,
            }

            if p_service is None:
                # Modèle explicite : pression de service = max(p_chaud, p_froid) si dispo,
                # sinon |delta_p| si dispo, sinon inconnue.
                candidates = []
                if _is_finite(p_hot):
                    candidates.append(float(p_hot))
                if _is_finite(p_cold):
                    candidates.append(float(p_cold))
                if candidates:
                    p_service = max(abs(x) for x in candidates)
                    rapport["notes_modele"].append("pression_service_pa déduite comme max(|p_chaud|,|p_froid|).")
                elif _is_finite(dp):
                    p_service = abs(float(dp))
                    rapport["notes_modele"].append("pression_service_pa déduite comme |delta_p_chaud_froid_pa| (fallback).")

        if self.cylindre is not None:
            # Alésage
            if Dcyl is None:
                if hasattr(self.cylindre, "alesage_m"):
                    Dcyl = getattr(self.cylindre, "alesage_m")
            # Pression cylindre si dispo et p_service pas déjà fixé
            if p_service is None:
                # On tente quelques noms probables (sans inventer)
                for attr in ("pression_service_pa", "pression_max_pa", "pression_nominale_pa", "pression_gaz_pa"):
                    v = getattr(self.cylindre, attr, None)
                    if _is_finite(v):
                        p_service = abs(float(v))
                        rapport["notes_modele"].append(f"pression_service_pa déduite depuis cylindre.{attr}.")
                        break

            rapport["liaisons_pieces"]["cylindre"] = {"alesage_m": Dcyl}

        # ------------------------------------------------------------
        # 2) Validation minimale et dérivations simples
        # ------------------------------------------------------------
        if D_dep is None:
            _push_inconnue(rapport, "impossibles", "diametre_deplaceur_m", "Fournir diametre_deplaceur_m ou un Deplaceur.")
        else:
            D_dep = _req_pos("diametre_deplaceur_m", D_dep)

        if Dcyl is not None:
            Dcyl = _req_pos("alesage_cylindre_m", Dcyl)

        if jeu is None and (Dcyl is not None) and (D_dep is not None):
            jeu = jeu_radial_depuis_alesage_et_deplaceur(Dcyl, D_dep)
            rapport["notes_modele"].append("jeu_radial_m déduit de (alesage - diametre_deplaceur)/2.")
        elif jeu is not None:
            jeu = _req_pos("jeu_radial_m", jeu, strictly=False)

        if nb_j is None:
            _push_inconnue(rapport, "impossibles", "nb_joints", "Fournir nb_joints ou Deplaceur.nb_joints_toriques.")
        else:
            nb_j = _req_int_ge("nb_joints", nb_j, min_value=0)

        rapport["entrees"].update({
            "diametre_deplaceur_m": D_dep,
            "alesage_cylindre_m": Dcyl,
            "jeu_radial_m": jeu,
            "nb_joints": nb_j,
            "section_joint_mm": sec_mm,
            "squeeze": sq,
            "facteur_largeur": fL,
            "orientation": self.orientation,
            "pression_service_pa": p_service,
            "materiau_joint_cle": self.materiau_joint_cle,
            "mode_materiau": self.mode_materiau,
            "module_elastomere_pa": self.module_elastomere_pa,
            "coeff_frottement": self.coeff_frottement,
            "largeur_bande_contact_m": self.largeur_bande_contact_m,
        })

        # Géométrie générale
        if D_dep is not None:
            rapport["geometrie"].update({
                "perimetre_sur_diametre_deplaceur_m": perimetre_cercle(D_dep),
                "aire_face_deplaceur_m2": aire_disque(D_dep),
                "rayon_deplaceur_m": 0.5 * D_dep,
            })

        if (Dcyl is not None) and (D_dep is not None):
            rapport["verifications"]["compatibilite_cylindre_deplaceur"] = {
                "alesage_cylindre_m": Dcyl,
                "diametre_deplaceur_m": D_dep,
                "jeu_radial_calcule_m": 0.5 * (Dcyl - D_dep),
                "ok_si_alesage_superieur": (Dcyl >= D_dep),
            }

        # ------------------------------------------------------------
        # 3) Joint : section, squeeze, largeur gorge
        # ------------------------------------------------------------
        section_m: Optional[float] = None
        if sec_mm is None:
            _push_inconnue(rapport, "impossibles", "section_joint_mm", "Non déductible sans choix de série (ISO) ou donnée explicite.")
        else:
            section_m = _req_pos("section_joint_mm", sec_mm) * 1e-3
            rapport["geometrie"]["section_joint_m"] = section_m
            rapport["geometrie"]["aire_section_joint_m2"] = aire_section_joint_torique(section_m)

        if sq is None:
            _push_inconnue(rapport, "impossibles", "squeeze", "Non déductible sans règle/objectif explicite. Fournir squeeze (ex: Deplaceur.taux_compression_joint).")
        else:
            sq = _req_pos("squeeze", sq, strictly=False)
            if not (0.0 < sq < 1.0):
                _push_inconnue(rapport, "impossibles", "squeeze", "Doit être dans (0,1).")

        if fL is None:
            _push_inconnue(rapport, "partielles", "facteur_largeur", "Nécessaire pour calculer largeur_gorge (sinon largeur inconnue).")
        else:
            fL = _req_pos("facteur_largeur", fL)

        # ------------------------------------------------------------
        # 4) Gorge : profondeur/largeur/protrusion + diamètre fond (si orientation)
        # ------------------------------------------------------------
        profondeur: Optional[float] = None
        largeur: Optional[float] = None
        protrusion: Optional[float] = None  # dépassement radial avant compression = squeeze*section

        if (section_m is not None) and (sq is not None) and (0.0 < sq < 1.0):
            profondeur = profondeur_gorge_depuis_squeeze(section_m, sq)
            protrusion = section_m - profondeur  # = sq*section
            rapport["gorge"].update({
                "profondeur_gorge_radiale_m": profondeur,
                "protrusion_radiale_theorique_m": protrusion,
                "definition": "profondeur = section*(1-squeeze), protrusion = section - profondeur",
            })
        else:
            _push_inconnue(rapport, "impossibles", "profondeur_gorge", "Impossible sans section_joint et squeeze valides.")

        if (section_m is not None) and (fL is not None):
            largeur = largeur_gorge_depuis_facteur(section_m, fL)
            rapport["gorge"]["largeur_gorge_axiale_m"] = largeur
        else:
            _push_inconnue(rapport, "partielles", "largeur_gorge_m", "Calculable si section_joint et facteur_largeur sont fournis.")

        # Diamètre fond de gorge (cas explicitement modélisé : gorge externe sur déplaceur)
        D_fond: Optional[float] = None
        if self.orientation == "gorge_externe_sur_deplaceur":
            if (D_dep is not None) and (profondeur is not None):
                # Hypothèse explicite : profondeur_gorge_radiale est mesurée depuis la surface extérieure du déplaceur
                # => D_fond = D_dep - 2*profondeur
                D_fond = D_dep - 2.0 * profondeur
                if D_fond <= 0:
                    _push_inconnue(rapport, "impossibles", "diametre_fond_gorge_m", "D_fond <= 0 (géométrie impossible).")
                else:
                    rapport["gorge"]["diametre_fond_gorge_m"] = D_fond
                    rapport["notes_modele"].append("D_fond déduit avec hypothèse: gorge externe sur OD du déplaceur (D_fond = D_dep - 2*profondeur).")
            else:
                _push_inconnue(rapport, "partielles", "diametre_fond_gorge_m", "Calculable si D_dep et profondeur_gorge connus.")
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "orientation",
                "Orientation non fournie : impossible de déduire le diamètre au fond de gorge.",
            )

        # ------------------------------------------------------------
        # 5) Vérification radiale avec cylindre (si alésage dispo)
        # ------------------------------------------------------------
        if (Dcyl is not None) and (D_dep is not None) and (protrusion is not None):
            clearance = 0.5 * (Dcyl - D_dep)
            rapport["verifications"]["jeu_radial_m"] = clearance
            rapport["verifications"]["protrusion_radiale_m"] = protrusion
            rapport["verifications"]["protrusion_compatible_avec_jeu"] = (protrusion <= clearance)
            # Gap résiduel après compression (si protrusion < jeu, il reste un espace)
            rapport["verifications"]["gap_radial_residuel_apres_contact_m"] = max(0.0, clearance - protrusion)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "verification_radiale",
                "Vérif protrusion<=jeu calculable si alésage cylindre + D_dep + profondeur (donc protrusion) sont disponibles.",
            )

        # ------------------------------------------------------------
        # 6) Volumes : gorge vs joint (si géométrie complète)
        # ------------------------------------------------------------
        if (nb_j is not None) and (nb_j > 0):
            if (D_fond is not None) and (largeur is not None) and (profondeur is not None) and (section_m is not None):
                V_gorge_1 = volume_gorge_annulaire_rect(
                    diametre_fond_gorge_m=D_fond,
                    largeur_gorge_m=largeur,
                    profondeur_gorge_m=profondeur,
                )
                # centreline du tore : au fond + section (diamètre)
                D_centreline = D_fond + section_m
                V_joint_1 = volume_joint_torique_approx(
                    diametre_centreline_m=D_centreline,
                    section_joint_m=section_m,
                )
                rapport["geometrie"].update({
                    "volume_gorge_unitaire_m3": V_gorge_1,
                    "volume_gorges_total_m3": V_gorge_1 * nb_j,
                    "diametre_centreline_joint_m": D_centreline,
                    "volume_joint_unitaire_approx_m3": V_joint_1,
                    "volume_joints_total_approx_m3": V_joint_1 * nb_j,
                    "taux_remplissage_gorge_approx": (V_joint_1 / V_gorge_1) if V_gorge_1 > 0 else None,
                    "note_volume_joint": "Volume joint: tore parfait (sans aplatissement). Volume gorge: rectangle (approx).",
                })
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "volumes_gorge_joint",
                    "Calculable si D_fond + largeur + profondeur + section sont disponibles.",
                )

        # ------------------------------------------------------------
        # 7) Contraintes mécaniques => exigences matériau (sans “choisir” un polymère)
        # ------------------------------------------------------------
        if p_service is None:
            _push_inconnue(
                rapport,
                "partielles",
                "pression_service_pa",
                "Requise pour calculer les exigences mécaniques du matériau (p_contact nécessaire, module minimal, etc.).",
            )
        else:
            p_service = _req_pos("pression_service_pa", p_service, strictly=False)
            rapport["service"]["pression_service_pa"] = p_service

            # Exigence minimale explicite (modèle volontairement simple, mais traçable) :
            # p_contact_est ~= E * squeeze  => E_min ~= p_service / squeeze
            if (sq is not None) and (0.0 < sq < 1.0):
                if sq <= 0:
                    _push_inconnue(rapport, "impossibles", "squeeze", "squeeze <= 0 : aucune pression de contact ne peut être générée.")
                else:
                    E_min = p_service / sq
                    rapport["elasticite"]["module_min_pour_p_contact_ge_p_service_pa"] = E_min
                    rapport["notes_modele"].append("Exigence module (simplifiée): p_contact ≈ E*squeeze => E_min = p_service/squeeze.")
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "module_min",
                    "Calculable si squeeze est fourni et valide.",
                )

        # Module réel du matériau (si fourni)
        E_elast = self.module_elastomere_pa
        if (E_elast is None) and self.materiau_joint_cle and (get_materiau is not None):
            mat = get_materiau(self.materiau_joint_cle)
            if mat is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "materiau_joint_cle",
                    f"Matériau '{self.materiau_joint_cle}' introuvable dans backend.ensemble.materiaux.",
                )
            else:
                # On tente d'utiliser module_young_pa si présent dans ta base.
                E_elast = valeur(getattr(mat, "module_young_pa", None), mode=self.mode_materiau)
                rapport["materiau"]["materiau_joint_nom"] = getattr(mat, "nom", self.materiau_joint_cle)
                rapport["materiau"]["module_young_pa"] = E_elast

        if E_elast is not None:
            E_elast = _req_pos("module_elastomere_pa", E_elast)
            rapport["elasticite"]["module_elastomere_pa"] = E_elast
            if (sq is not None) and (0.0 < sq < 1.0):
                p_contact_est = E_elast * sq
                rapport["elasticite"]["pression_contact_estimee_pa"] = p_contact_est
                if p_service is not None:
                    rapport["elasticite"]["marge_p_contact_vs_service"] = (p_contact_est / p_service) if p_service > 0 else None
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "pression_contact_estimee",
                    "Calculable si squeeze est fourni et valide.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "module_elastomere_pa",
                "Fournir module_elastomere_pa (ou materiau_joint_cle existant dans ta base) pour estimer p_contact.",
            )

        # ------------------------------------------------------------
        # 8) Frottement (si p_contact estimée + μ + bande)
        # ------------------------------------------------------------
        if (nb_j is not None) and (nb_j > 0) and (D_dep is not None):
            p_contact = rapport["elasticite"].get("pression_contact_estimee_pa", None)
            if p_contact is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "frottement",
                    "Nécessite pression_contact_estimee_pa (donc module_elastomere + squeeze).",
                )
            else:
                if self.coeff_frottement is None or self.largeur_bande_contact_m is None:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "frottement",
                        "Calculable si coeff_frottement et largeur_bande_contact_m sont fournis.",
                    )
                else:
                    mu = _req_pos("coeff_frottement", self.coeff_frottement, strictly=False)
                    b = _req_pos("largeur_bande_contact_m", self.largeur_bande_contact_m)
                    perim = perimetre_cercle(D_dep)
                    A_contact = perim * b * nb_j
                    Ff = mu * float(p_contact) * A_contact
                    rapport["frottement"].update({
                        "perimetre_contact_m": perim,
                        "aire_contact_m2": A_contact,
                        "force_frottement_N": Ff,
                        "modele": "F = mu * p_contact * (perimetre * bande * nb_joints)",
                    })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "frottement",
                "Calculable si nb_joints, D_dep, et pression_contact estimée sont disponibles.",
            )

        # ------------------------------------------------------------
        # 9) Mode strict
        # ------------------------------------------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "JointDeplaceur(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport


# ============================================================
# Exemple (aucune valeur cachée ; ici on suppose que le Deplaceur fournit déjà section/squeeze/nb joints)
# ============================================================
if __name__ == "__main__":
    # Exemple sans objets projet : tu donnes juste ce qui est nécessaire
    j = JointDeplaceur(
        diametre_deplaceur_m=0.080,
        alesage_cylindre_m=0.0804,   # => jeu 0.2 mm
        nb_joints=2,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur=1.5,
        pression_service_pa=150_000.0,
        module_elastomere_pa=7e6,
        coeff_frottement=0.15,
        largeur_bande_contact_m=0.003,
    )
    from pprint import pprint
    pprint(j.analyser(strict=False))

# backend/pieces/joint_deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal
import math

# ============================================================
# Imports projet (optionnels)
# ============================================================

# Matériaux génériques projet (si tu as une base matériaux)
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# Déplaceur (pour cohérence géométrique) - optionnel
try:
    from backend.pieces.deplaceur import Deplaceur  # type: ignore
except Exception:  # pragma: no cover
    Deplaceur = None  # type: ignore


# Cylindre (pour cohérence alesage/jeu) - optionnel
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
# Géométrie : gorge + contrôles (sans normes implicites)
# ============================================================

def perimetre_cercle(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    return math.pi * D

def aire_cercle(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    r = 0.5 * D
    return math.pi * r * r

def volume_gorge_annulaire(
    *,
    diametre_fond_gorge_m: float,
    largeur_gorge_m: float,
    profondeur_gorge_m: float,
) -> float:
    """
    Modèle géométrique simple : gorge annulaire "rectangle"
    V = périmètre * largeur * profondeur, au diamètre fond de gorge.
    """
    Df = _req_pos("diametre_fond_gorge_m", diametre_fond_gorge_m)
    w = _req_pos("largeur_gorge_m", largeur_gorge_m)
    t = _req_pos("profondeur_gorge_m", profondeur_gorge_m)
    return perimetre_cercle(Df) * w * t

def profondeur_gorge_depuis_squeeze(section_joint_m: float, squeeze: float) -> float:
    """
    Définition EXPLICITE :
    - section_joint_m = diamètre de tore (section) (m)
    - squeeze = compression radiale relative (0..1)
    Alors profondeur = section * (1 - squeeze).
    (Aucune valeur par défaut)
    """
    s = _req_pos("section_joint_m", section_joint_m)
    sq = _req_pos("squeeze", squeeze, strictly=False)
    if not (0.0 < sq < 1.0):
        raise ValueError("squeeze doit être dans (0,1).")
    return s * (1.0 - sq)

def largeur_gorge_depuis_facteur(section_joint_m: float, facteur_largeur: float) -> float:
    """
    largeur_gorge = facteur_largeur * section
    (facteur fourni par l'utilisateur, pas inventé)
    """
    s = _req_pos("section_joint_m", section_joint_m)
    f = _req_pos("facteur_largeur", facteur_largeur)
    return f * s

def section_joint_depuis_profondeur_et_squeeze(profondeur_gorge_m: float, squeeze: float) -> float:
    """
    Si tu connais profondeur + squeeze :
    section = profondeur / (1 - squeeze)
    """
    t = _req_pos("profondeur_gorge_m", profondeur_gorge_m)
    sq = _req_pos("squeeze", squeeze, strictly=False)
    if not (0.0 < sq < 1.0):
        raise ValueError("squeeze doit être dans (0,1).")
    return t / (1.0 - sq)

def squeeze_depuis_section_et_profondeur(section_joint_m: float, profondeur_gorge_m: float) -> float:
    """
    squeeze = 1 - profondeur/section
    """
    s = _req_pos("section_joint_m", section_joint_m)
    t = _req_pos("profondeur_gorge_m", profondeur_gorge_m)
    if t >= s:
        # pas une erreur forcément (pas de compression), mais squeeze <= 0 -> pas d'étanchéité
        return 0.0
    return 1.0 - (t / s)

def jeu_radial_depuis_alesage_et_deplaceur(alesage_m: float, diametre_deplaceur_m: float) -> float:
    """
    jeu_radial = (D_cyl - D_dep) / 2
    """
    Dc = _req_pos("alesage_m", alesage_m)
    Dd = _req_pos("diametre_deplaceur_m", diametre_deplaceur_m)
    return 0.5 * (Dc - Dd)


# ============================================================
# Pièce : Joint de Déplaceur (torique)
# ============================================================

@dataclass(frozen=True)
class JointDeplaceur:
    """
    Joint(s) du déplaceur (joints toriques) – calcul "zéro invention".

    Ce module ne choisit PAS une section ISO, ni un matériau, ni un squeeze par défaut.
    Il calcule tout ce qui est calculable à partir :
    - de la géométrie du déplaceur (diamètre, longueur, jeu)
    - du cylindre (alesage) si fourni
    - des paramètres de gorge / joint si fournis

    Notion clé :
    - Sans section_joint_mm (ou profondeur+ squee﻿ze), on ne peut pas sortir une gorge unique.
      On peut toutefois calculer des *bornes* (ex: section max imposée par le jeu).
    """

    # ------------------------------------------------------------------
    # Références aux autres pièces (optionnelles, pour cohérence)
    # ------------------------------------------------------------------
    deplaceur: Optional[Any] = None          # instance Deplaceur (si dispo)
    cylindre: Optional[Any] = None           # instance Cylindre (si dispo)

    # ------------------------------------------------------------------
    # Géométrie minimale (si pas d'objets)
    # ------------------------------------------------------------------
    diametre_deplaceur_m: Optional[float] = None
    longueur_deplaceur_m: Optional[float] = None
    jeu_radial_m: Optional[float] = None
    alesage_cylindre_m: Optional[float] = None

    # ------------------------------------------------------------------
    # Nombre de joints
    # - si deplaceur fourni et nb_joints_toriques défini -> on l'utilise
    # - sinon, fournir nb_joints
    # ------------------------------------------------------------------
    nb_joints: Optional[int] = None

    # ------------------------------------------------------------------
    # Données joint / gorge (aucun défaut)
    # ------------------------------------------------------------------
    section_joint_mm: Optional[float] = None     # diamètre de tore (mm)
    squeeze: Optional[float] = None              # (0..1) compression radiale relative
    facteur_largeur: Optional[float] = None      # largeur_gorge = facteur * section

    # Alternativement, tu peux donner la gorge directement :
    profondeur_gorge_m: Optional[float] = None
    largeur_gorge_m: Optional[float] = None

    # Diamètre au fond de gorge (sur le déplaceur)
    diametre_fond_gorge_m: Optional[float] = None

    # ------------------------------------------------------------------
    # Placement axial des gorges (optionnel)
    # Sans règles -> impossible de "deviner" les positions.
    # On peut toutefois calculer la place totale occupée si largeurs connues.
    # ------------------------------------------------------------------
    marge_axiale_min_m: Optional[float] = None    # marge mini entre gorge et extrémité (si tu l'imposes)

    # ------------------------------------------------------------------
    # Elasticité / pression de contact (optionnel, EXPLICITE)
    # Si module_elastomere_pa fourni, on peut estimer p_contact ~ E * strain
    # (modèle très simplifié, mais explicite; sinon aucune estimation).
    # ------------------------------------------------------------------
    materiau_joint_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"
    module_elastomere_pa: Optional[float] = None  # override direct

    # Frottement (optionnel)
    coeff_frottement: Optional[float] = None      # μ
    # bande de contact axiale si tu veux aire contact = périmètre * bande * nb_joints
    largeur_bande_contact_m: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "liaisons_pieces": {},
            "geometrie": {},
            "gorge": {},
            "elasticite": {},
            "frottement": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # 1) Récupération données depuis Deplaceur/Cylindre si fournis
        # ------------------------------------------------------------
        D_dep = self.diametre_deplaceur_m
        L_dep = self.longueur_deplaceur_m
        jeu = self.jeu_radial_m
        Dcyl = self.alesage_cylindre_m

        # Deplaceur
        if self.deplaceur is not None:
            # On ne suppose pas la structure; on tente des attributs connus.
            if D_dep is None and hasattr(self.deplaceur, "diametre_exterieur_m"):
                D_dep = getattr(self.deplaceur, "diametre_exterieur_m")
            if L_dep is None and hasattr(self.deplaceur, "longueur_totale_m"):
                L_dep = getattr(self.deplaceur, "longueur_totale_m")
            if jeu is None and hasattr(self.deplaceur, "jeu_radial_m"):
                jeu = getattr(self.deplaceur, "jeu_radial_m")
            if self.nb_joints is None and hasattr(self.deplaceur, "nb_joints_toriques"):
                nbj = getattr(self.deplaceur, "nb_joints_toriques")
                if nbj is not None:
                    self_nb = int(nbj)
                    # on garde seulement si cohérent
                    if self_nb >= 0:
                        object.__setattr__(self, "nb_joints", self_nb)  # type: ignore[attr-defined]

            rapport["liaisons_pieces"]["deplaceur"] = {
                "source": "objet",
                "diametre_exterieur_m": D_dep,
                "longueur_totale_m": L_dep,
                "jeu_radial_m": jeu,
                "nb_joints_toriques": getattr(self.deplaceur, "nb_joints_toriques", None),
            }

        # Cylindre
        if self.cylindre is not None:
            if Dcyl is None:
                if hasattr(self.cylindre, "alesage_m"):
                    Dcyl = getattr(self.cylindre, "alesage_m")
            rapport["liaisons_pieces"]["cylindre"] = {
                "source": "objet",
                "alesage_m": Dcyl,
            }

        # Validation minimale
        if D_dep is None:
            _push_inconnue(rapport, "impossibles", "diametre_deplaceur_m", "Requis (ou fournir un Deplaceur).")
        else:
            D_dep = _req_pos("diametre_deplaceur_m", D_dep)

        if L_dep is None:
            _push_inconnue(rapport, "partielles", "longueur_deplaceur_m", "Utile pour placement axial (sinon non calculable).")
        else:
            L_dep = _req_pos("longueur_deplaceur_m", L_dep)

        # Si on a alesage et pas jeu, on peut déduire jeu.
        if jeu is None and Dcyl is not None and D_dep is not None:
            Dcyl_v = _req_pos("alesage_cylindre_m", Dcyl)
            jeu = jeu_radial_depuis_alesage_et_deplaceur(Dcyl_v, D_dep)
            rapport["notes_modele"].append("jeu_radial_m déduit de (alesage - diametre_deplaceur)/2.")
        elif jeu is not None:
            jeu = _req_pos("jeu_radial_m", jeu, strictly=False)

        # Si on a jeu et pas alesage, on peut déduire alesage.
        if Dcyl is None and jeu is not None and D_dep is not None:
            Dcyl = D_dep + 2.0 * jeu
            rapport["notes_modele"].append("alesage_cylindre_m déduit de diametre_deplaceur + 2*jeu_radial.")

        if Dcyl is not None:
            Dcyl = _req_pos("alesage_cylindre_m", Dcyl)

        # Nombre de joints
        if self.nb_joints is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "nb_joints",
                "Requis (ou fournir Deplaceur.nb_joints_toriques).",
            )
            nb_j = None
        else:
            nb_j = _req_int_ge("nb_joints", self.nb_joints, min_value=0)

        rapport["entrees"].update({
            "diametre_deplaceur_m": D_dep,
            "longueur_deplaceur_m": L_dep,
            "jeu_radial_m": jeu,
            "alesage_cylindre_m": Dcyl,
            "nb_joints": nb_j,
            "section_joint_mm": self.section_joint_mm,
            "squeeze": self.squeeze,
            "facteur_largeur": self.facteur_largeur,
            "profondeur_gorge_m": self.profondeur_gorge_m,
            "largeur_gorge_m": self.largeur_gorge_m,
            "diametre_fond_gorge_m": self.diametre_fond_gorge_m,
            "marge_axiale_min_m": self.marge_axiale_min_m,
            "materiau_joint_cle": self.materiau_joint_cle,
            "mode_materiau": self.mode_materiau,
            "module_elastomere_pa": self.module_elastomere_pa,
        })

        # ------------------------------------------------------------
        # 2) Calculs géométriques généraux (joint sur déplaceur)
        # ------------------------------------------------------------
        if D_dep is not None:
            rapport["geometrie"].update({
                "perimetre_sur_diametre_deplaceur_m": perimetre_cercle(D_dep),
                "aire_section_deplaceur_m2": aire_cercle(D_dep),
                "rayon_deplaceur_m": 0.5 * D_dep,
            })

        if Dcyl is not None and D_dep is not None:
            rapport["verifications"]["compatibilite_cylindre_deplaceur"] = {
                "alesage_cylindre_m": Dcyl,
                "diametre_deplaceur_m": D_dep,
                "jeu_radial_calcule_m": 0.5 * (Dcyl - D_dep),
                "ok_si_alesage_superieur": (Dcyl >= D_dep),
            }

        # ------------------------------------------------------------
        # 3) Bornes de section joint déductibles du jeu (si jeu connu)
        # ------------------------------------------------------------
        # Sans norme, on ne choisit pas une section, mais :
        # - si jeu_radial connu, la section MAX est bornée par la place radiale disponible
        #   (en fonction du squeeze et de la profondeur de gorge).
        if jeu is not None:
            # La compression impose : (section - profondeur) = squeeze*section <= jeu_effectif ?
            # Or, sans profondeur/squeeze, on ne peut pas conclure; on donne la contrainte :
            rapport["geometrie"]["jeu_radial_m"] = jeu
            _push_inconnue(
                rapport,
                "partielles",
                "section_joint",
                "Une section ISO ne peut pas être déduite du seul jeu_radial. "
                "On peut seulement vérifier la cohérence si section/squeeze/profondeur sont fournis.",
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "jeu_radial_m",
                "Sans jeu_radial (ou alesage), impossible d'évaluer la place radiale disponible pour le joint.",
            )

        # ------------------------------------------------------------
        # 4) Détermination section / gorge suivant les entrées
        # ------------------------------------------------------------
        # Cas A : section_joint_mm fournie
        section_m: Optional[float] = None
        if self.section_joint_mm is not None:
            section_m = _req_pos("section_joint_mm", self.section_joint_mm) * 1e-3
            rapport["geometrie"]["section_joint_m"] = section_m

        # Cas B : profondeur + squeeze fournis => section déductible
        if section_m is None and self.profondeur_gorge_m is not None and self.squeeze is not None:
            section_m = section_joint_depuis_profondeur_et_squeeze(
                profondeur_gorge_m=_req_pos("profondeur_gorge_m", self.profondeur_gorge_m),
                squeeze=_req_pos("squeeze", self.squeeze, strictly=False),
            )
            rapport["geometrie"]["section_joint_m"] = section_m
            rapport["notes_modele"].append("section_joint déduite de (profondeur_gorge, squeeze).")

        # Détermination profondeur/largeur de gorge si possible
        profondeur: Optional[float] = None
        largeur: Optional[float] = None

        if self.profondeur_gorge_m is not None:
            profondeur = _req_pos("profondeur_gorge_m", self.profondeur_gorge_m)

        if self.largeur_gorge_m is not None:
            largeur = _req_pos("largeur_gorge_m", self.largeur_gorge_m)

        # Si section + squeeze => profondeur calculable
        if profondeur is None and section_m is not None and self.squeeze is not None:
            profondeur = profondeur_gorge_depuis_squeeze(
                section_joint_m=section_m,
                squeeze=_req_pos("squeeze", self.squeeze, strictly=False),
            )
            rapport["notes_modele"].append("profondeur_gorge calculée via section_joint et squeeze.")

        # Si section + facteur_largeur => largeur calculable
        if largeur is None and section_m is not None and self.facteur_largeur is not None:
            largeur = largeur_gorge_depuis_facteur(
                section_joint_m=section_m,
                facteur_largeur=_req_pos("facteur_largeur", self.facteur_largeur),
            )
            rapport["notes_modele"].append("largeur_gorge calculée via section_joint et facteur_largeur.")

        # Squeeze déductible si section + profondeur
        if section_m is not None and profondeur is not None:
            sq_calc = squeeze_depuis_section_et_profondeur(section_m, profondeur)
            rapport["gorge"]["squeeze_calcule_depuis_section_et_profondeur"] = sq_calc

        # Diamètre fond de gorge
        D_fond = None
        if self.diametre_fond_gorge_m is not None:
            D_fond = _req_pos("diametre_fond_gorge_m", self.diametre_fond_gorge_m)
        else:
            # Par défaut, on ne l'invente pas.
            # MAIS si on modélise une gorge sur le déplaceur sans autre info,
            # le seul diamètre certain disponible est le diamètre du déplaceur.
            # On ne peut pas savoir la profondeur "radiale" (interne/externe),
            # donc on marque inconnu.
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_fond_gorge_m",
                "Non déductible : il dépend de l'orientation de la gorge et de la cote de référence (fond). "
                "Fournir diametre_fond_gorge_m (diamètre au fond de gorge).",
            )

        # Enregistrer gorge si complète
        if profondeur is not None:
            rapport["gorge"]["profondeur_gorge_m"] = profondeur
        else:
            _push_inconnue(rapport, "partielles", "profondeur_gorge_m", "Calculable si (section+squeeze) ou profondeur fournie.")

        if largeur is not None:
            rapport["gorge"]["largeur_gorge_m"] = largeur
        else:
            _push_inconnue(rapport, "partielles", "largeur_gorge_m", "Calculable si (section+facteur_largeur) ou largeur fournie.")

        if section_m is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "section_joint_mm",
                "Impossible de définir un joint torique sans section (ISO 3601) ou sans (profondeur_gorge_m + squeeze).",
            )

        # ------------------------------------------------------------
        # 5) Volumes de gorge / longueur axiale occupée (si nb_joints connu)
        # ------------------------------------------------------------
        if nb_j is not None and nb_j > 0:
            if profondeur is not None and largeur is not None and D_fond is not None:
                V1 = volume_gorge_annulaire(
                    diametre_fond_gorge_m=D_fond,
                    largeur_gorge_m=largeur,
                    profondeur_gorge_m=profondeur,
                )
                rapport["gorge"]["volume_gorge_unitaire_m3"] = V1
                rapport["gorge"]["volume_gorges_total_m3"] = V1 * nb_j
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "volume_gorge",
                    "Calculable si diametre_fond_gorge_m + largeur_gorge_m + profondeur_gorge_m sont fournis/calculés.",
                )

            if largeur is not None:
                rapport["gorge"]["largeur_axiale_occupee_par_gorges_m"] = largeur * nb_j
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "place_axiale_gorges",
                    "Calculable si largeur_gorge_m est connue.",
                )

            # Place restante si longueur déplaceur connue
            if L_dep is not None and largeur is not None:
                place = L_dep - (largeur * nb_j)
                rapport["verifications"]["place_axiale_restante_m"] = place

                if self.marge_axiale_min_m is not None:
                    marge = _req_pos("marge_axiale_min_m", self.marge_axiale_min_m, strictly=False)
                    # contrainte : 2 marges extrémités + (nb_j-1)*marges inter-gorges (si tu les imposes)
                    # -> sans règle inter-gorge explicite, on ne déduit pas.
                    rapport["verifications"]["marge_axiale_min_m"] = marge
                    if 2.0 * marge > L_dep:
                        rapport["verifications"]["marge_extremites_ok"] = False
                    else:
                        rapport["verifications"]["marge_extremites_ok"] = True
            elif L_dep is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "longueur_deplaceur_m",
                    "Nécessaire pour vérifier le placement axial / espace disponible.",
                )
        elif nb_j == 0:
            rapport["notes_modele"].append("nb_joints=0 : aucune gorge/joint à calculer.")
        else:
            # nb_joints inconnu déjà loggé
            pass

        # ------------------------------------------------------------
        # 6) Cohérence radiale (si jeu, section, profondeur connus)
        # ------------------------------------------------------------
        # Sans modèle standard, on peut au moins vérifier que la compression radiale
        # n'exige pas plus que le jeu disponible, SI on suppose que la compression
        # se fait principalement sur le jeu.
        if jeu is not None and section_m is not None and profondeur is not None:
            compression_radiale_m = max(0.0, section_m - profondeur)
            rapport["verifications"]["compression_radiale_m"] = compression_radiale_m
            rapport["verifications"]["jeu_radial_m"] = jeu
            rapport["verifications"]["compression_compatible_avec_jeu"] = (compression_radiale_m <= jeu)
        elif jeu is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "verification_radiale",
                "Vérif compression<=jeu calculable si section_joint et profondeur_gorge sont connus.",
            )

        # ------------------------------------------------------------
        # 7) Elasticité : estimation pression de contact (si module fourni)
        # ------------------------------------------------------------
        # Modèle explicite (très simple) :
        # strain ~= squeeze (compression relative)
        # p_contact_est ~= E * strain
        E_elast = self.module_elastomere_pa

        if E_elast is None and self.materiau_joint_cle and get_materiau is not None:
            mat = get_materiau(self.materiau_joint_cle)
            if mat is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "materiau_joint_cle",
                    f"Matériau '{self.materiau_joint_cle}' introuvable dans backend.ensemble.materiaux.",
                )
            else:
                # On tente un champ générique ; si ta base n'a pas ce champ, ça restera None.
                E_elast = valeur(getattr(mat, "module_young_pa", None), mode=self.mode_materiau)
                rapport["elasticite"]["materiau_joint_nom"] = getattr(mat, "nom", self.materiau_joint_cle)
                rapport["elasticite"]["module_young_pa_source"] = E_elast

        if E_elast is not None:
            E_elast = _req_pos("module_elastomere_pa", E_elast)
            rapport["elasticite"]["module_elastomere_pa"] = E_elast
            if self.squeeze is not None:
                sq = _req_pos("squeeze", self.squeeze, strictly=False)
                if not (0.0 < sq < 1.0):
                    _push_inconnue(rapport, "impossibles", "squeeze", "Doit être dans (0,1) pour calcul élastique.")
                else:
                    p_contact_est = E_elast * sq
                    rapport["elasticite"]["pression_contact_estimee_pa"] = p_contact_est
                    rapport["notes_modele"].append("Estimation p_contact ~= E * squeeze (modèle simplifié explicite).")
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "pression_contact",
                    "Estimation possible si squeeze est fourni (et module_elastomere_pa connu).",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "module_elastomere_pa",
                "Nécessaire si tu veux estimer une pression de contact par calcul (sinon inconnue).",
            )

        # ------------------------------------------------------------
        # 8) Frottement : si μ + largeur bande + p_contact estimée + diamètre connu
        # ------------------------------------------------------------
        # Aire contact ~ périmètre * bande * nb_joints
        # Force ~ μ * p_contact * aire
        if (
            self.coeff_frottement is not None
            and self.largeur_bande_contact_m is not None
            and nb_j is not None
            and nb_j > 0
            and D_dep is not None
        ):
            mu = _req_pos("coeff_frottement", self.coeff_frottement, strictly=False)
            b = _req_pos("largeur_bande_contact_m", self.largeur_bande_contact_m)

            p_contact = rapport["elasticite"].get("pression_contact_estimee_pa")
            if p_contact is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "frottement",
                    "Force de frottement calculable si pression_contact_estimee_pa est disponible (module_elastomere + squeeze).",
                )
            else:
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
                "Calculable si coeff_frottement + largeur_bande_contact_m + (pression_contact estimée) + nb_joints + diamètre sont disponibles.",
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
# Exemple minimal (zéro valeur cachée)
# ============================================================
if __name__ == "__main__":
    # Exemple 1 : avec données directes
    j = JointDeplaceur(
        diametre_deplaceur_m=0.080,
        longueur_deplaceur_m=0.120,
        alesage_cylindre_m=0.0804,
        # -> jeu = (0.0804-0.080)/2 = 0.0002
        nb_joints=2,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur=1.5,
        diametre_fond_gorge_m=0.080,   # à fournir explicitement (cote fond gorge)
        module_elastomere_pa=7e6,      # si tu veux pression contact estimée (sinon enlève)
        coeff_frottement=0.15,
        largeur_bande_contact_m=0.003,
    )
    from pprint import pprint
    pprint(j.analyser(strict=False))

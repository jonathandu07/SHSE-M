# backend/pieces/arbre_vilbrequin.py
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


# =============================================================================
# Matériaux : tentative de résolution via materiaux.py (sans inventer)
# =============================================================================

def _resoudre_materiau(
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
) -> Dict[str, Optional[float]]:
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
# RDM arbres (dimensionnements)
# =============================================================================

def _section_disque(d: float) -> float:
    r = 0.5 * d
    return math.pi * r * r

def _inertie_cercle(d: float) -> float:
    # I = π d^4 / 64
    return (math.pi * d**4) / 64.0

def _polar_J(d: float) -> float:
    # Jp = π d^4 / 32
    return (math.pi * d**4) / 32.0

def _tau_torsion_max(T: float, d: float) -> float:
    # τmax = 16 T / (π d^3)
    return (16.0 * abs(T)) / (math.pi * d**3)

def _sigma_flexion_max(M: float, d: float) -> float:
    # σmax = 32 M / (π d^3)
    return (32.0 * abs(M)) / (math.pi * d**3)

def _von_mises_sigma_tau(sigma: float, tau: float) -> float:
    return math.sqrt(sigma**2 + 3.0 * tau**2)

def _dmin_torsion_vonmises(T: float, Re: float, FS: float) -> float:
    """
    Hypothèse arbre ductile :
    - von Mises en torsion pure : σ_eq = sqrt(3) τ
    - Critère : σ_eq <= Re/FS
    -> τ <= Re/(FS*sqrt(3))
    -> 16T/(π d^3) <= Re/(FS*sqrt(3))
    """
    tau_adm = Re / (FS * math.sqrt(3.0))
    if tau_adm <= 0:
        raise ValueError("tau_adm <= 0")
    return (16.0 * abs(T) / (math.pi * tau_adm)) ** (1.0 / 3.0)

def _dmin_bending_vonmises(M: float, Re: float, FS: float) -> float:
    """
    Flexion pure : σ = 32M/(π d^3) <= Re/FS
    """
    sigma_adm = Re / FS
    if sigma_adm <= 0:
        raise ValueError("sigma_adm <= 0")
    return (32.0 * abs(M) / (math.pi * sigma_adm)) ** (1.0 / 3.0)


# =============================================================================
# Pièce : ArbreVilbrequin
# =============================================================================

@dataclass
class ArbreVilbrequin:
    """
    Arbre de vilebrequin (journal(s) + maneton).

    Mise à jour importante :
    - Le roulement à aiguilles (backend/pieces/roulement_aiguille_arbre_vilebrequin.py)
      fournit maintenant :
        * dimensions_requises.d_interieur_requis_m  (=> maneton nominal requis)
        * dimensions_reference.{d_interieur_m, D_exterieur_m, B_largeur_m} (si référence choisie)
    - Ce module :
        * priorise un diamètre maneton imposé,
        * sinon utilise la bielle,
        * sinon utilise le roulement (d_interieur_requis_m) pour fixer le maneton.
    """

    # ---- Liens ----
    cylindre: Optional[Any] = None
    piston: Optional[Any] = None
    bielle: Optional[Any] = None
    moteur_thermique: Optional[Any] = None
    roulement_aiguille: Optional[Any] = None  # RoulementAiguilleArbreVilebrequin (ou équivalent)

    # ---- Cinématique / externes ----
    course_m: Optional[float] = None
    couple_max_Nm: Optional[float] = None
    moment_flexion_max_Nm: Optional[float] = None
    rpm: Optional[float] = None

    # ---- Géométrie imposée ----
    diametre_journal_principal_m: Optional[float] = None
    diametre_maneton_m: Optional[float] = None
    largeur_portee_journal_m: Optional[float] = None
    largeur_portee_maneton_m: Optional[float] = None

    # ---- Matériau ----
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None
    facteur_securite: float = 2.0

    # ---- Ajustements (sans inventer) ----
    serrage_roulement_m: Optional[float] = None
    jeu_roulement_m: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "arbre_vilbrequin",
            "entrees": {},
            "materiau": {},
            "recuperations": {},
            "cinematique": {},
            "roulement": {},
            "bielle_maneton": {},
            "dimensionnements": {},
            "contraintes": {},
            "geometrie": {},
            "masse": {},
            "inerties": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ---------------------------------------------------------------------
        # 1) Matériau
        # ---------------------------------------------------------------------
        props = _resoudre_materiau(self.materiau_cle, self.densite_kg_m3, self.limite_elastique_pa, self.module_young_pa)
        rho = props["densite_kg_m3"]
        Re = props["limite_elastique_pa"]
        E = props["module_young_pa"]
        rapport["materiau"] = {
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": rho,
            "limite_elastique_pa": Re,
            "module_young_pa": E,
            "facteur_securite": FS,
        }

        # ---------------------------------------------------------------------
        # 2) Course -> rayon manivelle
        # ---------------------------------------------------------------------
        course = self.course_m

        if course is None and self.cylindre is not None:
            try:
                if hasattr(self.cylindre, "course_m") and _is_finite(getattr(self.cylindre, "course_m")):
                    course = float(getattr(self.cylindre, "course_m"))
                    rapport["notes_modele"].append("course_m récupérée depuis cylindre.course_m.")
                elif hasattr(self.cylindre, "entrees") and isinstance(getattr(self.cylindre, "entrees"), dict):
                    v = getattr(self.cylindre, "entrees").get("course_m")
                    if _is_finite(v):
                        course = float(v)
            except Exception:
                pass

        if course is None and self.piston is not None:
            try:
                if hasattr(self.piston, "course_m") and _is_finite(getattr(self.piston, "course_m")):
                    course = float(getattr(self.piston, "course_m"))
                    rapport["notes_modele"].append("course_m récupérée depuis piston.course_m.")
                elif hasattr(self.piston, "calculer") and callable(self.piston.calculer):
                    rp = self.piston.calculer()
                    if isinstance(rp, dict):
                        v = rp.get("entrees", {}).get("course_m")
                        if _is_finite(v):
                            course = float(v)
                            rapport["notes_modele"].append("course_m récupérée via piston.calculer().entrees.course_m.")
            except Exception:
                pass

        if course is None:
            _push_inconnue(rapport, "impossibles", "course_m", "Nécessaire pour déterminer le rayon de manivelle r = course/2.")
        else:
            course = _req_pos("course_m", course)
            r_manivelle = 0.5 * course
            rapport["cinematique"] = {"course_m": course, "rayon_manivelle_m": r_manivelle}

        # ---------------------------------------------------------------------
        # 3) Roulement + maneton : extraction mise à jour (nouveau format)
        # ---------------------------------------------------------------------
        # Roulement : on veut (si dispo)
        # - d_ref (d_interieur_m), D_ref (D_exterieur_m), B_ref (B_largeur_m)
        # - d_requis (dimensions_requises.d_interieur_requis_m) = contrainte maneton nominal
        d_ref = None
        D_ref = None
        B_ref = None
        d_requis_maneton = None

        if self.roulement_aiguille is not None:
            # 3.1.a : essayer analyser()/calculer() en priorité (format dict)
            rr = None
            try:
                if hasattr(self.roulement_aiguille, "analyser") and callable(self.roulement_aiguille.analyser):
                    rr = self.roulement_aiguille.analyser()
                elif hasattr(self.roulement_aiguille, "calculer") and callable(self.roulement_aiguille.calculer):
                    rr = self.roulement_aiguille.calculer()
            except Exception:
                rr = None

            if isinstance(rr, dict):
                dim_req = rr.get("dimensions_requises", {}) if isinstance(rr.get("dimensions_requises", {}), dict) else {}
                dim_ref = rr.get("dimensions_reference", {}) if isinstance(rr.get("dimensions_reference", {}), dict) else {}
                bloc_r = rr.get("roulement", {}) if isinstance(rr.get("roulement", {}), dict) else {}

                # requis maneton
                v = dim_req.get("d_interieur_requis_m")
                if _is_finite(v):
                    d_requis_maneton = float(v)
                    rapport["notes_modele"].append("d_interieur_requis_m récupéré depuis roulement_aiguille.dimensions_requises.")

                # dimensions référence (si roulement choisi)
                for k in ("d_interieur_m", "d_alesage_m"):
                    v = dim_ref.get(k)
                    if d_ref is None and _is_finite(v):
                        d_ref = float(v)
                v = dim_ref.get("D_exterieur_m")
                if _is_finite(v):
                    D_ref = float(v)
                v = dim_ref.get("B_largeur_m")
                if _is_finite(v):
                    B_ref = float(v)

                # fallback ancien bloc "roulement"
                if d_ref is None and _is_finite(bloc_r.get("d_alesage_m")):
                    d_ref = float(bloc_r.get("d_alesage_m"))
                if D_ref is None and _is_finite(bloc_r.get("D_exterieur_m")):
                    D_ref = float(bloc_r.get("D_exterieur_m"))
                if B_ref is None and _is_finite(bloc_r.get("largeur_m")):
                    B_ref = float(bloc_r.get("largeur_m"))

            # 3.1.b : fallback attributs directs (compat)
            # (ancien naming / mocks)
            if d_ref is None:
                for attr in ("d_interieur_m", "d_alesage_m", "diametre_interieur_m", "d_m", "diametre_bore_m"):
                    if hasattr(self.roulement_aiguille, attr) and _is_finite(getattr(self.roulement_aiguille, attr)):
                        d_ref = float(getattr(self.roulement_aiguille, attr))
                        break
            if D_ref is None:
                for attr in ("D_exterieur_m", "diametre_exterieur_m", "D_m", "diametre_OD_m"):
                    if hasattr(self.roulement_aiguille, attr) and _is_finite(getattr(self.roulement_aiguille, attr)):
                        D_ref = float(getattr(self.roulement_aiguille, attr))
                        break
            if B_ref is None:
                for attr in ("B_largeur_m", "largeur_m", "B_m", "epaisseur_m", "width_m"):
                    if hasattr(self.roulement_aiguille, attr) and _is_finite(getattr(self.roulement_aiguille, attr)):
                        B_ref = float(getattr(self.roulement_aiguille, attr))
                        break

        # Journal principal : inchangé (on prend d_ref comme alésage roulement journal si c'est bien le cas)
        # NB : ici on ne sait pas si ton "roulement_aiguille" concerne le maneton (bielle) OU le journal principal.
        # On conserve la logique : si tu veux imposer le journal principal, tu le fournis explicitement.
        d_journal = self.diametre_journal_principal_m
        if d_journal is not None:
            d_journal = _req_pos("diametre_journal_principal_m", d_journal)

        # Largeur portée journal : si tu l'imposes, ok ; sinon, on peut prendre B_ref (mais seulement si c'est bien le journal).
        largeur_journal = self.largeur_portee_journal_m
        if largeur_journal is not None:
            largeur_journal = _req_pos("largeur_portee_journal_m", largeur_journal)

        rapport["roulement"] = {
            "d_interieur_reference_m": d_ref,
            "D_exterieur_reference_m": D_ref,
            "B_largeur_reference_m": B_ref,
            "d_interieur_requis_maneton_m": d_requis_maneton,
            "diametre_journal_principal_m": d_journal,
            "largeur_portee_journal_m": largeur_journal,
        }

        # ---------------------------------------------------------------------
        # 3.2 Maneton : priorité = imposé > bielle > roulement (d_requis)
        # ---------------------------------------------------------------------
        d_maneton = self.diametre_maneton_m

        if d_maneton is None and self.bielle is not None:
            try:
                if hasattr(self.bielle, "diametre_maneton_m") and _is_finite(getattr(self.bielle, "diametre_maneton_m")):
                    d_maneton = float(getattr(self.bielle, "diametre_maneton_m"))
                    rapport["notes_modele"].append("diametre_maneton_m récupéré depuis bielle.diametre_maneton_m.")
                elif hasattr(self.bielle, "calculer") and callable(self.bielle.calculer):
                    rb = self.bielle.calculer()
                    if isinstance(rb, dict):
                        v = rb.get("geometrie", {}).get("grande_tete", {}).get("diametre_maneton_m")
                        if _is_finite(v):
                            d_maneton = float(v)
                            rapport["notes_modele"].append("diametre_maneton_m récupéré via bielle.calculer().geometrie.grande_tete.")
            except Exception:
                _push_inconnue(rapport, "partielles", "diametre_maneton_m", "Bielle fournie mais format non exploitable pour récupérer le maneton.")

        if d_maneton is None and d_requis_maneton is not None:
            d_maneton = float(d_requis_maneton)
            rapport["notes_modele"].append("diametre_maneton_m fixé depuis roulement_aiguille.dimensions_requises.d_interieur_requis_m.")

        if d_maneton is not None:
            d_maneton = _req_pos("diametre_maneton_m", d_maneton)
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "diametre_maneton_m",
                "Requis pour géométrie du vilebrequin. Fournir bielle/diametre_maneton_m ou un roulement (d_interieur_requis_m).",
            )

        # largeur portée maneton
        largeur_maneton = self.largeur_portee_maneton_m
        if largeur_maneton is None and self.bielle is not None:
            try:
                if hasattr(self.bielle, "longueur_portee_grande_tete_m") and _is_finite(getattr(self.bielle, "longueur_portee_grande_tete_m")):
                    largeur_maneton = float(getattr(self.bielle, "longueur_portee_grande_tete_m"))
                    rapport["notes_modele"].append("largeur_portee_maneton_m récupérée depuis bielle.longueur_portee_grande_tete_m.")
            except Exception:
                pass
        if largeur_maneton is not None:
            largeur_maneton = _req_pos("largeur_portee_maneton_m", largeur_maneton)

        rapport["bielle_maneton"] = {
            "diametre_maneton_m": d_maneton,
            "largeur_portee_maneton_m": largeur_maneton,
        }

        # ---------------------------------------------------------------------
        # 4) Couple / efforts depuis moteur_thermique si possible
        # ---------------------------------------------------------------------
        T = self.couple_max_Nm
        F_bielle = None

        if self.moteur_thermique is not None:
            try:
                rmt = None
                if hasattr(self.moteur_thermique, "analyser") and callable(self.moteur_thermique.analyser):
                    rmt = self.moteur_thermique.analyser()
                elif hasattr(self.moteur_thermique, "calculer") and callable(self.moteur_thermique.calculer):
                    rmt = self.moteur_thermique.calculer()

                if isinstance(rmt, dict):
                    bloc_c = rmt.get("couple", rmt.get("resultats", rmt))
                    if isinstance(bloc_c, dict):
                        for k in ("T_instantane_Nm", "couple_Nm", "couple_max_Nm", "T_Nm"):
                            if T is None and _is_finite(bloc_c.get(k)):
                                T = float(bloc_c.get(k))
                                rapport["notes_modele"].append(f"couple_max_Nm récupéré depuis moteur_thermique ({k}).")
                                break

                    bloc_f = rmt.get("forces", rmt.get("resultats", rmt))
                    if isinstance(bloc_f, dict):
                        for k in ("F_bielle_effective_N", "force_bielle_effective_N", "force_bielle_n", "force_bielle_N"):
                            if _is_finite(bloc_f.get(k)):
                                F_bielle = float(bloc_f.get(k))
                                rapport["notes_modele"].append(f"F_bielle récupérée depuis moteur_thermique ({k}).")
                                break
            except Exception:
                _push_inconnue(rapport, "partielles", "moteur_thermique", "Objet moteur_thermique fourni mais format non exploitable (analyser/calculer).")

        if T is None and F_bielle is not None and course is not None:
            T = abs(F_bielle) * (0.5 * course)
            rapport["notes_modele"].append("couple_max_Nm déduit via T = |F_bielle| * r_manivelle (approx, sans angle).")

        if T is None:
            _push_inconnue(rapport, "impossibles", "couple_max_Nm", "Nécessaire pour dimensionner l'arbre en torsion (ou déductible via moteur_thermique).")

        rapport["recuperations"] = {
            "couple_max_Nm": T,
            "force_bielle_effective_N": F_bielle,
            "rpm": self.rpm,
        }

        # ---------------------------------------------------------------------
        # 5) Dimensionnements RDM (torsion / flexion)
        # ---------------------------------------------------------------------
        if Re is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "limite_elastique_pa",
                "Nécessaire pour dimensionner un diamètre minimal (donner materiau_cle ou limite_elastique_pa).",
            )

        dmin_tors = None
        if T is not None and Re is not None:
            dmin_tors = _dmin_torsion_vonmises(float(T), float(Re), FS)
            rapport["dimensionnements"]["diametre_min_torsion_m"] = dmin_tors
            rapport["dimensionnements"]["critere_torsion"] = "von Mises torsion pure : sqrt(3)*tau <= Re/FS"

        dmin_bend = None
        Mmax = self.moment_flexion_max_Nm
        if Mmax is not None:
            Mmax = _req_pos("moment_flexion_max_Nm", Mmax, strictly=False)

        if Mmax is not None and Re is not None:
            dmin_bend = _dmin_bending_vonmises(float(Mmax), float(Re), FS)
            rapport["dimensionnements"]["diametre_min_flexion_m"] = dmin_bend
            rapport["dimensionnements"]["critere_flexion"] = "sigma <= Re/FS"
        elif Mmax is None:
            _push_inconnue(
                rapport,
                "partielles",
                "moment_flexion_max_Nm",
                "Non calculable sans modèle d'appuis (entraxe paliers, positions charges). Donne moment_flexion_max_Nm ou les entraxes/charges pour le calculer ailleurs.",
            )

        # Vérifs journal (si défini)
        if d_journal is not None and dmin_tors is not None:
            rapport["verifs_journal"] = {
                "diametre_journal_m": d_journal,
                "diametre_min_torsion_m": dmin_tors,
                "ok_torsion": d_journal >= dmin_tors,
                "marge_torsion_d3": (d_journal / dmin_tors) ** 3 if dmin_tors > 0 else None,
            }

        # Contraintes réelles si d_journal connu
        if d_journal is not None and T is not None:
            tau = _tau_torsion_max(float(T), float(d_journal))
            sigma_b = _sigma_flexion_max(float(Mmax), float(d_journal)) if Mmax is not None else 0.0
            sigma_eq = _von_mises_sigma_tau(sigma_b, tau)
            sigma_adm = (float(Re) / FS) if Re is not None else None
            rapport["contraintes"]["journal_principal"] = {
                "tau_torsion_pa": tau,
                "sigma_flexion_pa": sigma_b if Mmax is not None else None,
                "sigma_von_mises_pa": sigma_eq,
                "sigma_admissible_pa": sigma_adm,
                "marge_von_mises": (sigma_adm / sigma_eq) if (sigma_adm is not None and sigma_eq > 0) else None,
            }

        # Maneton : contraintes sur d_maneton
        if d_maneton is not None and T is not None:
            tau = _tau_torsion_max(float(T), float(d_maneton))
            sigma_b = _sigma_flexion_max(float(Mmax), float(d_maneton)) if Mmax is not None else 0.0
            sigma_eq = _von_mises_sigma_tau(sigma_b, tau)
            sigma_adm = (float(Re) / FS) if Re is not None else None
            rapport["contraintes"]["maneton"] = {
                "diametre_maneton_m": d_maneton,
                "tau_torsion_pa": tau,
                "sigma_flexion_pa": sigma_b if Mmax is not None else None,
                "sigma_von_mises_pa": sigma_eq,
                "sigma_admissible_pa": sigma_adm,
                "marge_von_mises": (sigma_adm / sigma_eq) if (sigma_adm is not None and sigma_eq > 0) else None,
            }

        # ---------------------------------------------------------------------
        # 6) Ajustement roulement (sans inventer)
        # ---------------------------------------------------------------------
        # Ici on applique sur un "journal" associé à un alésage d_ref.
        if d_ref is not None and d_journal is not None:
            if self.serrage_roulement_m is not None and self.jeu_roulement_m is not None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "ajustement roulement",
                    "Donne soit serrage_roulement_m, soit jeu_roulement_m (pas les deux).",
                )
            elif self.serrage_roulement_m is not None:
                s = _req_finite("serrage_roulement_m", self.serrage_roulement_m)
                rapport["geometrie"]["diametre_usinage_journal_m"] = d_ref + abs(s)
                rapport["notes_modele"].append("Diamètre usiné journal calculé à partir d'un serrage cible (modèle simplifié, tolérances non traitées).")
            elif self.jeu_roulement_m is not None:
                j = _req_finite("jeu_roulement_m", self.jeu_roulement_m)
                rapport["geometrie"]["diametre_usinage_journal_m"] = d_ref - abs(j)
                rapport["notes_modele"].append("Diamètre usiné journal calculé à partir d'un jeu cible (modèle simplifié, tolérances non traitées).")
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "ajustement roulement",
                    "Impossible de proposer un diamètre usiné sans critère (jeu/serrage cible) ni classe d'ajustement.",
                )

        # ---------------------------------------------------------------------
        # 7) Géométrie minimale
        # ---------------------------------------------------------------------
        rapport["geometrie"].update({
            "diametre_journal_principal_m": d_journal,
            "largeur_portee_journal_m": largeur_journal,
            "diametre_maneton_m": d_maneton,
            "largeur_portee_maneton_m": largeur_maneton,
            "rayon_manivelle_m": (0.5 * course) if course is not None else None,
            # utile côté CAO/logement (si référence roulement connue)
            "D_exterieur_reference_m": D_ref,
            "B_largeur_reference_m": B_ref,
        })

        _push_inconnue(
            rapport,
            "partielles",
            "entraxe_paliers / positions",
            "Nécessaire pour calculer moments fléchissants, réactions aux paliers, et dimensionner épaulements/rayons.",
        )
        _push_inconnue(
            rapport,
            "partielles",
            "rayons de congé",
            "Nécessaire pour la fatigue (facteurs de concentration Kt/Kf) : dépend des transitions réelles.",
        )
        _push_inconnue(
            rapport,
            "partielles",
            "fatigue",
            "Nécessite spectre de charge (cycle, alternances), rugosité, traitements, et concentrations de contraintes.",
        )
        _push_inconnue(
            rapport,
            "partielles",
            "masse/inerties globales vilebrequin",
            "Impossible sans longueur totale, nombre de paliers, contrepoids, et volumes détaillés (CAO ou décomposition).",
        )

        # ---------------------------------------------------------------------
        # 8) Trace entrées + strict
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "course_m": self.course_m,
            "couple_max_Nm": self.couple_max_Nm,
            "moment_flexion_max_Nm": self.moment_flexion_max_Nm,
            "rpm": self.rpm,
            "diametre_journal_principal_m": self.diametre_journal_principal_m,
            "diametre_maneton_m": self.diametre_maneton_m,
            "largeur_portee_journal_m": self.largeur_portee_journal_m,
            "largeur_portee_maneton_m": self.largeur_portee_maneton_m,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "limite_elastique_pa": self.limite_elastique_pa,
            "module_young_pa": self.module_young_pa,
            "facteur_securite": self.facteur_securite,
            "serrage_roulement_m": self.serrage_roulement_m,
            "jeu_roulement_m": self.jeu_roulement_m,
        }

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "ArbreVilbrequin(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# =============================================================================
# Exemple d'usage minimal (à supprimer en prod)
# =============================================================================
if __name__ == "__main__":
    # Mock dans le format NOUVEAU (dict via calculer)
    class RoulementAiguilleMock:
        def calculer(self):
            return {
                "dimensions_requises": {"d_interieur_requis_m": 0.030},
                "dimensions_reference": {"d_interieur_m": 0.030, "D_exterieur_m": 0.037, "B_largeur_m": 0.016},
            }

    av = ArbreVilbrequin(
        roulement_aiguille=RoulementAiguilleMock(),
        course_m=0.085,
        couple_max_Nm=134.0,
        limite_elastique_pa=800e6,
        facteur_securite=2.0,
    )

    from pprint import pprint
    pprint(av.analyser(strict=False))

# backend/components/moteur_thermique/pieces/vilbrequin.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.modules.systeme.dossier_definition import ajouter_dossier_definition_solidworks
import math


# =============================================================================
# Utilitaires (validation + extraction robuste)
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


def _get(obj: Any, *names: str) -> Any:
    """
    Lecture robuste :
    - dict: obj[name]
    - objet: getattr(obj, name)
    - sinon: None
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        for n in names:
            if n in obj:
                return obj.get(n)
        return None
    for n in names:
        if hasattr(obj, n):
            try:
                return getattr(obj, n)
            except Exception:
                pass
    return None


def _dig(obj: Any, *path: str) -> Any:
    """
    Navigation robuste dans des structures imbriquées dict/obj.
    Exemple: _dig(rep, "geometrie", "diametre_journal_principal_m")
    """
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


def _try_call(obj: Any, method_name: str) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    fn = getattr(obj, method_name, None)
    if callable(fn):
        try:
            out = fn(strict=False) if method_name == "analyser" else fn()
            return out if isinstance(out, dict) else None
        except TypeError:
            try:
                out = fn(strict=False)
                return out if isinstance(out, dict) else None
            except Exception:
                return None
        except Exception:
            return None
    return None


def _push_inconnue(rapport: Dict[str, Any], kind: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(kind, []).append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for kind in ("impossibles", "partielles"):
        items = inc.get(kind, []) or []
        seen = set()
        out = []
        for it in items:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        inc[kind] = out


# =============================================================================
# Matériaux : résolution (sans invention)
# =============================================================================

def _resoudre_materiau(
    *,
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
    poisson: Optional[float] = None,
    resistance_traction_pa: Optional[float] = None,
    limite_fatigue_pa: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    """
    Résout les propriétés matériau sans rien inventer.
    - Les overrides numériques priment.
    - Sinon, on tente de charger depuis le catalogue `materiaux.py` du projet.
    """
    rho = float(densite_kg_m3) if _is_finite(densite_kg_m3) else None
    Re = float(limite_elastique_pa) if _is_finite(limite_elastique_pa) else None
    E = float(module_young_pa) if _is_finite(module_young_pa) else None
    nu = float(poisson) if _is_finite(poisson) else None
    Rm = float(resistance_traction_pa) if _is_finite(resistance_traction_pa) else None
    Sf = float(limite_fatigue_pa) if _is_finite(limite_fatigue_pa) else None

    if materiau_cle:
        candidates = [
            "backend.ensemble.materiaux",
            "backend.materiaux",
            "materiaux",
            "backend.modules.materiaux",
        ]
        for mod in candidates:
            try:
                m = __import__(mod, fromlist=["get_materiau"])
                get_materiau = getattr(m, "get_materiau", None)
                if not callable(get_materiau):
                    continue
                mat = get_materiau(materiau_cle)

                def g(*keys: str) -> Optional[float]:
                    v = _get(mat, *keys)
                    return float(v) if _is_finite(v) else None

                rho = rho if rho is not None else g("densite_kg_m3", "rho_kg_m3", "densite")
                Re = Re if Re is not None else g("limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa")
                E = E if E is not None else g("module_young_pa", "E_pa", "young_pa", "young_modulus_pa")
                nu = nu if nu is not None else g("poisson", "nu")
                Rm = Rm if Rm is not None else g("resistance_traction_pa", "Rm_pa", "uts_pa", "ultimate_strength_pa")
                Sf = Sf if Sf is not None else g("limite_fatigue_pa", "Sf_pa", "endurance_limit_pa")
                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "limite_elastique_pa": Re,
        "module_young_pa": E,
        "poisson": nu,
        "resistance_traction_pa": Rm,
        "limite_fatigue_pa": Sf,
    }


# =============================================================================
# Géométrie / volumétrie (modèles explicites, sans spéculation)
# =============================================================================

def _volume_cylindre(d_m: float, L_m: float) -> float:
    r = 0.5 * d_m
    return math.pi * (r * r) * L_m


def _masse_volume(rho: float, V_m3: float) -> float:
    return rho * V_m3


def _inertie_polaire_cylindre_autour_axe(m_kg: float, d_m: float) -> float:
    """
    Moment d'inertie polaire d'un cylindre plein autour de son axe longitudinal :
    I = 1/2 m r²
    """
    r = 0.5 * d_m
    return 0.5 * m_kg * (r * r)


def _module_cisaillement_G(E: float, nu: float) -> float:
    return E / (2.0 * (1.0 + nu))


def _module_compressibilite_K(E: float, nu: float) -> float:
    return E / (3.0 * (1.0 - 2.0 * nu))


def _moment_polaire_section(d_m: float) -> float:
    return (math.pi * (d_m ** 4)) / 32.0


def _raideur_torsion_segment(G_pa: float, J_m4: float, L_m: float) -> float:
    return (G_pa * J_m4) / L_m


# =============================================================================
# Vilbrequin (global) : agrégation inter-pièces
# =============================================================================

@dataclass
class Vilbrequin:
    """
    Vilbrequin complet (niveau "système mécanique") :
    - Se base sur l'arbre (journaux + maneton) calculé par `ArbreVilbrequin`
      et complète avec des grandeurs globales (masse/inerties/raideur torsionnelle)
      UNIQUEMENT si les paramètres nécessaires sont fournis ou déductibles.

    Philosophie :
    - dépendance explicite aux autres pièces (cylindre/piston/bielle/deplaceur/arbre)
    - aucune valeur n'est inventée : si une grandeur manque, elle est listée en inconnue.
    - les modèles (volumes = cylindres, inerties = formules analytiques) sont explicites.
    """

    arbre: Optional[Any] = None
    cylindre: Optional[Any] = None
    piston: Optional[Any] = None
    bielle: Optional[Any] = None
    deplaceur: Optional[Any] = None
    systeme_complet: Optional[Any] = None
    moteur_thermique: Optional[Any] = None

    nb_manetons: Optional[int] = None
    nb_journaux_principaux: Optional[int] = None

    course_m: Optional[float] = None
    rpm: Optional[float] = None

    couple_max_Nm: Optional[float] = None
    moment_flexion_max_Nm: Optional[float] = None

    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None
    poisson: Optional[float] = None
    resistance_traction_pa: Optional[float] = None
    limite_fatigue_pa: Optional[float] = None

    facteur_securite: float = 2.0

    volume_webs_total_m3: Optional[float] = None
    volume_contrepoids_total_m3: Optional[float] = None

    longueur_torsion_equivalente_m: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "vilbrequin",
            "entrees": {},
            "recuperations": {},
            "materiau": {},
            "proprietes_derivees": {},
            "cinematique": {},
            "geometrie": {},
            "volumes": {},
            "masses": {},
            "inerties": {},
            "raideur": {},
            "contraintes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        rep_arbre = _try_call(self.arbre, "analyser") if self.arbre is not None else None
        rep_cyl = _try_call(self.cylindre, "analyser") if self.cylindre is not None else None
        rep_dep = _try_call(self.deplaceur, "analyser") if self.deplaceur is not None else None
        rep_pis = _try_call(self.piston, "calculer") if self.piston is not None else None
        rep_bie = _try_call(self.bielle, "calculer") if self.bielle is not None else None
        rep_mt = _try_call(self.moteur_thermique, "analyser") if hasattr(self.moteur_thermique, "analyser") else None

        rapport["recuperations"] = {
            "arbre_vilbrequin": bool(rep_arbre),
            "cylindre": bool(rep_cyl),
            "deplaceur": bool(rep_dep),
            "piston": bool(rep_pis),
            "bielle": bool(rep_bie),
            "moteur_thermique": bool(rep_mt) or bool(self.moteur_thermique),
        }

        course = self.course_m
        if course is None:
            course = _dig(rep_arbre, "entrees", "course_m")
            if course is None and isinstance(rep_arbre, dict):
                rayon_src = _dig(rep_arbre, "geometrie", "rayon_manivelle_m")
                if _is_finite(rayon_src):
                    course = 2.0 * float(rayon_src)
                    rapport["cinematique"]["rayon_manivelle_m_source_arbre"] = float(rayon_src)

            if course is None:
                course = _get(self.arbre, "course_m")
            if course is None:
                course = _get(self.cylindre, "course_m")
            if course is None and isinstance(rep_cyl, dict):
                course = _dig(rep_cyl, "entrees", "course_m")
            if course is None:
                course = _get(self.deplaceur, "course_disponible_m")
            if course is None and isinstance(rep_dep, dict):
                course = _dig(rep_dep, "entrees", "course_disponible_m")

        if course is not None:
            course = _req_pos("course_m", course)
            r = 0.5 * course
            rapport["cinematique"]["course_m"] = course
            rapport["cinematique"]["rayon_manivelle_m"] = r
        else:
            r = None
            _push_inconnue(
                rapport,
                "partielles",
                "course_m",
                "Requis pour rayon manivelle, inertie des manetons (offset) et couples <-> forces.",
            )

        rpm = self.rpm
        if rpm is None:
            rpm = _get(self.arbre, "rpm")
            if rpm is None and isinstance(rep_arbre, dict):
                rpm = _dig(rep_arbre, "recuperations", "rpm")
            if rpm is None:
                rpm = _get(self.systeme_complet, "rpm")
        if rpm is not None:
            rpm = _req_pos("rpm", rpm, strictly=False)
            rapport["cinematique"]["rpm"] = rpm

        T = self.couple_max_Nm
        if T is None:
            T = _get(self.arbre, "couple_max_Nm")
            if T is None and isinstance(rep_arbre, dict):
                T = _dig(rep_arbre, "entrees", "couple_max_Nm")
        if T is not None:
            T = _req_pos("couple_max_Nm", T, strictly=False)
            rapport["cinematique"]["couple_max_Nm"] = T

        Mmax = self.moment_flexion_max_Nm
        if Mmax is None:
            Mmax = _get(self.arbre, "moment_flexion_max_Nm")
            if Mmax is None and isinstance(rep_arbre, dict):
                Mmax = _dig(rep_arbre, "entrees", "moment_flexion_max_Nm")
        if Mmax is not None:
            Mmax = _req_pos("moment_flexion_max_Nm", Mmax, strictly=False)
            rapport["cinematique"]["moment_flexion_max_Nm"] = Mmax

        mat_key = self.materiau_cle or _get(self.arbre, "materiau_cle")
        if mat_key is None and isinstance(rep_arbre, dict):
            mat_key = _dig(rep_arbre, "entrees", "materiau_cle")

        props = _resoudre_materiau(
            materiau_cle=mat_key,
            densite_kg_m3=self.densite_kg_m3 or _get(self.arbre, "densite_kg_m3"),
            limite_elastique_pa=self.limite_elastique_pa or _get(self.arbre, "limite_elastique_pa"),
            module_young_pa=self.module_young_pa or _get(self.arbre, "module_young_pa"),
            poisson=self.poisson,
            resistance_traction_pa=self.resistance_traction_pa,
            limite_fatigue_pa=self.limite_fatigue_pa,
        )
        rapport["materiau"] = {"materiau_cle": mat_key, **props}

        rho = props.get("densite_kg_m3")
        Re = props.get("limite_elastique_pa")
        E = props.get("module_young_pa")
        nu = props.get("poisson")

        if E is not None and nu is not None:
            G = _module_cisaillement_G(E, nu)
            K = _module_compressibilite_K(E, nu)
            rapport["proprietes_derivees"].update({
                "module_cisaillement_G_pa": G,
                "module_compressibilite_K_pa": K,
            })
        else:
            if E is None:
                _push_inconnue(rapport, "partielles", "module_young_pa", "Requis pour dériver G et K.")
            if nu is None:
                _push_inconnue(rapport, "partielles", "poisson", "Requis pour dériver G et K (si E connu).")

        if rho is not None and E is not None:
            rapport["proprietes_derivees"]["rigidite_specifique_E_sur_rho"] = E / rho

        d_journal = _get(self.arbre, "diametre_journal_principal_m")
        L_journal = _get(self.arbre, "largeur_portee_journal_m")
        d_maneton = _get(self.arbre, "diametre_maneton_m")
        L_maneton = _get(self.arbre, "largeur_portee_maneton_m")

        if isinstance(rep_arbre, dict):
            if d_journal is None:
                d_journal = _dig(rep_arbre, "geometrie", "diametre_journal_principal_m")
            if L_journal is None:
                L_journal = _dig(rep_arbre, "geometrie", "largeur_portee_journal_m")
            if d_maneton is None:
                d_maneton = _dig(rep_arbre, "geometrie", "diametre_maneton_m")
            if L_maneton is None:
                L_maneton = _dig(rep_arbre, "geometrie", "largeur_portee_maneton_m")

        if d_maneton is None and self.bielle is not None:
            d_maneton = _get(self.bielle, "diametre_maneton_m")
        if L_maneton is None and self.bielle is not None:
            L_maneton = _get(self.bielle, "longueur_portee_grande_tete_m")

        geo = rapport["geometrie"]
        if d_journal is not None:
            d_journal = _req_pos("diametre_journal_principal_m", d_journal)
            geo["diametre_journal_principal_m"] = d_journal
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_journal_principal_m",
                "Requis pour volumes/masses journaux, inerties, raideur torsionnelle et contraintes.",
            )

        if L_journal is not None:
            L_journal = _req_pos("largeur_portee_journal_m", L_journal)
            geo["largeur_portee_journal_m"] = L_journal
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "largeur_portee_journal_m",
                "Requis pour volume/mass journaux (longueur de la portée).",
            )

        if d_maneton is not None:
            d_maneton = _req_pos("diametre_maneton_m", d_maneton)
            geo["diametre_maneton_m"] = d_maneton
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_maneton_m",
                "Requis pour volume/mass manetons, inerties et contraintes.",
            )

        if L_maneton is not None:
            L_maneton = _req_pos("largeur_portee_maneton_m", L_maneton)
            geo["largeur_portee_maneton_m"] = L_maneton
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "largeur_portee_maneton_m",
                "Requis pour volume/mass manetons (largeur de la portée).",
            )

        nJ = self.nb_journaux_principaux
        nM = self.nb_manetons

        if self.moteur_thermique is not None:
            if nM is None:
                nM = _get(self.moteur_thermique, "nb_manetons_requis")
            if nJ is None:
                nJ = _get(self.moteur_thermique, "nb_journaux_principaux_requis")

        if nJ is not None:
            if not isinstance(nJ, int) or nJ <= 0:
                raise ValueError(f"nb_journaux_principaux doit être un int > 0 (reçu: {nJ!r}).")
            geo["nb_journaux_principaux"] = nJ
        if nM is not None:
            if not isinstance(nM, int) or nM <= 0:
                raise ValueError(f"nb_manetons doit être un int > 0 (reçu: {nM!r}).")
            geo["nb_manetons"] = nM

        if nJ is None:
            _push_inconnue(
                rapport,
                "partielles",
                "nb_journaux_principaux",
                "Requis pour totaux (volume/masse/inerties globales) à partir des portées.",
            )
        if nM is None:
            _push_inconnue(
                rapport,
                "partielles",
                "nb_manetons",
                "Requis pour totaux (volume/masse/inerties globales) à partir des portées.",
            )

        Vj = Vm = None
        if d_journal is not None and L_journal is not None:
            Vj = _volume_cylindre(d_journal, L_journal)
            rapport["volumes"]["journal_principal_unitaire_m3"] = Vj
        if d_maneton is not None and L_maneton is not None:
            Vm = _volume_cylindre(d_maneton, L_maneton)
            rapport["volumes"]["maneton_unitaire_m3"] = Vm

        if rho is None:
            _push_inconnue(rapport, "partielles", "densite_kg_m3", "Requise pour masses et inerties.")

        mj = mm = None
        if rho is not None and Vj is not None:
            mj = _masse_volume(rho, Vj)
            rapport["masses"]["journal_principal_unitaire_kg"] = mj
        if rho is not None and Vm is not None:
            mm = _masse_volume(rho, Vm)
            rapport["masses"]["maneton_unitaire_kg"] = mm

        if nJ is not None and Vj is not None:
            rapport["volumes"]["journaux_total_m3"] = nJ * Vj
        if nM is not None and Vm is not None:
            rapport["volumes"]["manetons_total_m3"] = nM * Vm

        if rho is not None and nJ is not None and Vj is not None:
            rapport["masses"]["journaux_total_kg"] = rho * (nJ * Vj)
        if rho is not None and nM is not None and Vm is not None:
            rapport["masses"]["manetons_total_kg"] = rho * (nM * Vm)

        V_webs = self.volume_webs_total_m3
        V_cw = self.volume_contrepoids_total_m3
        if V_webs is not None:
            V_webs = _req_pos("volume_webs_total_m3", V_webs, strictly=False)
            rapport["volumes"]["webs_total_m3"] = V_webs
            if rho is not None:
                rapport["masses"]["webs_total_kg"] = rho * V_webs
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "volume_webs_total_m3",
                "Requis pour masse globale (webs) si tu veux un vilbrequin complet au-delà des portées cylindriques.",
            )

        if V_cw is not None:
            V_cw = _req_pos("volume_contrepoids_total_m3", V_cw, strictly=False)
            rapport["volumes"]["contrepoids_total_m3"] = V_cw
            if rho is not None:
                rapport["masses"]["contrepoids_total_kg"] = rho * V_cw
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "volume_contrepoids_total_m3",
                "Requis pour masse globale (contrepoids) si tu veux un vilbrequin complet.",
            )

        if rho is not None:
            V_sum = 0.0
            have_any = False
            if nJ is not None and Vj is not None:
                V_sum += nJ * Vj
                have_any = True
            if nM is not None and Vm is not None:
                V_sum += nM * Vm
                have_any = True
            if V_webs is not None:
                V_sum += V_webs
                have_any = True
            if V_cw is not None:
                V_sum += V_cw
                have_any = True
            if have_any:
                rapport["volumes"]["volume_total_modele_m3"] = V_sum
                rapport["masses"]["masse_totale_modele_kg"] = rho * V_sum

        if mj is not None and d_journal is not None:
            Ij = _inertie_polaire_cylindre_autour_axe(mj, d_journal)
            rapport["inerties"]["journal_principal_unitaire_kg_m2"] = Ij
            if nJ is not None:
                rapport["inerties"]["journaux_total_kg_m2"] = nJ * Ij

        if mm is not None and d_maneton is not None:
            I_pin_axis = _inertie_polaire_cylindre_autour_axe(mm, d_maneton)
            rapport["inerties"]["maneton_unitaire_autour_son_axe_kg_m2"] = I_pin_axis
            if r is not None:
                I_pin_about_crank = I_pin_axis + mm * (r ** 2)
                rapport["inerties"]["maneton_unitaire_autour_axe_vilbrequin_kg_m2"] = I_pin_about_crank
                if nM is not None:
                    rapport["inerties"]["manetons_total_autour_axe_vilbrequin_kg_m2"] = nM * I_pin_about_crank
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "rayon_manivelle_m",
                    "Requis pour inertie des manetons autour de l'axe vilbrequin (décalage).",
                )

        I_total = 0.0
        have_I = False
        if "journaux_total_kg_m2" in rapport["inerties"]:
            I_total += float(rapport["inerties"]["journaux_total_kg_m2"])
            have_I = True
        if "manetons_total_autour_axe_vilbrequin_kg_m2" in rapport["inerties"]:
            I_total += float(rapport["inerties"]["manetons_total_autour_axe_vilbrequin_kg_m2"])
            have_I = True
        if have_I:
            rapport["inerties"]["inertie_polaire_minimale_modele_kg_m2"] = I_total
            rapport["notes_modele"].append(
                "Inertie_polaire_minimale_modele : inclut uniquement journaux + manetons. "
                "Webs/contrepoids non inclus sans géométrie/volumes + position radiale."
            )

        FS = _req_pos("facteur_securite", self.facteur_securite)
        if E is not None and nu is not None:
            G = _module_cisaillement_G(E, nu)
        else:
            G = None

        if G is not None and d_journal is not None and L_journal is not None:
            J = _moment_polaire_section(d_journal)
            k = _raideur_torsion_segment(G, J, L_journal)
            rapport["raideur"]["journal_type"] = {"J_m4": J, "k_Nm_par_rad": k}
        elif G is None:
            _push_inconnue(rapport, "partielles", "G_pa", "Requis pour raideur torsionnelle (nécessite E et ν).")

        L_eq = self.longueur_torsion_equivalente_m
        if L_eq is not None:
            L_eq = _req_pos("longueur_torsion_equivalente_m", L_eq)
            if G is not None and d_journal is not None:
                J = _moment_polaire_section(d_journal)
                rapport["raideur"]["equivalente_modele"] = {
                    "hypothese": "segment cylindrique plein de diamètre journal_principal",
                    "J_m4": J,
                    "L_eq_m": L_eq,
                    "k_Nm_par_rad": _raideur_torsion_segment(G, J, L_eq),
                }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "longueur_torsion_equivalente_m",
                "Requis pour une raideur torsionnelle globale équivalente.",
            )

        def tau_torsion_max(T_Nm: float, d_m: float) -> float:
            return (16.0 * T_Nm) / (math.pi * (d_m ** 3))

        def sigma_flexion_max(M_Nm: float, d_m: float) -> float:
            return (32.0 * M_Nm) / (math.pi * (d_m ** 3))

        def von_mises(sigma: float, tau: float) -> float:
            return math.sqrt(sigma * sigma + 3.0 * tau * tau)

        sigma_adm = (Re / FS) if (Re is not None) else None
        if T is not None and d_journal is not None:
            tau = tau_torsion_max(float(T), float(d_journal))
            sigma = sigma_flexion_max(float(Mmax), float(d_journal)) if Mmax is not None else None
            sigma_eq = von_mises(float(sigma) if sigma is not None else 0.0, tau)
            rapport["contraintes"]["journal_principal"] = {
                "tau_torsion_pa": tau,
                "sigma_flexion_pa": sigma,
                "sigma_von_mises_pa": sigma_eq,
                "sigma_admissible_pa": sigma_adm,
                "marge_von_mises": (sigma_adm / sigma_eq) if (sigma_adm is not None and sigma_eq > 0) else None,
            }
        elif T is None:
            _push_inconnue(rapport, "partielles", "couple_max_Nm", "Requis pour contraintes en torsion.")

        if Mmax is None:
            _push_inconnue(
                rapport,
                "partielles",
                "moment_flexion_max_Nm",
                "Non déductible sans modèle d'appuis/charges. À fournir si tu veux la flexion.",
            )

        if T is not None and d_maneton is not None:
            tau = tau_torsion_max(float(T), float(d_maneton))
            sigma = sigma_flexion_max(float(Mmax), float(d_maneton)) if Mmax is not None else None
            sigma_eq = von_mises(float(sigma) if sigma is not None else 0.0, tau)
            rapport["contraintes"]["maneton"] = {
                "tau_torsion_pa": tau,
                "sigma_flexion_pa": sigma,
                "sigma_von_mises_pa": sigma_eq,
                "sigma_admissible_pa": sigma_adm,
                "marge_von_mises": (sigma_adm / sigma_eq) if (sigma_adm is not None and sigma_eq > 0) else None,
            }

        if sigma_adm is None:
            _push_inconnue(
                rapport,
                "partielles",
                "limite_elastique_pa",
                "Requise pour contrainte admissible et marges.",
            )

        if isinstance(rep_pis, dict):
            m_pis = _dig(rep_pis, "resultats", "masse_piston_kg")
            if _is_finite(m_pis):
                rapport["masses"]["masse_piston_kg"] = float(m_pis)

        if isinstance(rep_bie, dict):
            m_bie = _dig(rep_bie, "masse", "masse_fut_kg")
            if _is_finite(m_bie):
                rapport["masses"]["masse_fut_bielle_kg"] = float(m_bie)
                rapport["notes_modele"].append(
                    "Masse bielle : modèle de la bielle (CorpsBielle) ne couvre que le fût (têtes non modélisées)."
                )

        rapport["entrees"] = {
            "nb_manetons": self.nb_manetons,
            "nb_journaux_principaux": self.nb_journaux_principaux,
            "course_m": self.course_m,
            "rpm": self.rpm,
            "couple_max_Nm": self.couple_max_Nm,
            "moment_flexion_max_Nm": self.moment_flexion_max_Nm,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "limite_elastique_pa": self.limite_elastique_pa,
            "module_young_pa": self.module_young_pa,
            "poisson": self.poisson,
            "volume_webs_total_m3": self.volume_webs_total_m3,
            "volume_contrepoids_total_m3": self.volume_contrepoids_total_m3,
            "longueur_torsion_equivalente_m": self.longueur_torsion_equivalente_m,
            "facteur_securite": self.facteur_securite,
        }

        _dedup_inconnues(rapport)
        if strict:
            essentiels = [
                ("densite_kg_m3", rho),
                ("module_young_pa", E),
                ("limite_elastique_pa", Re),
                ("diametre_journal_principal_m", d_journal),
                ("largeur_portee_journal_m", L_journal),
                ("diametre_maneton_m", d_maneton),
                ("largeur_portee_maneton_m", L_maneton),
            ]
            missing = [n for n, v in essentiels if v is None]
            if missing:
                raise ValueError(f"Données essentielles manquantes (strict=True) : {', '.join(missing)}")

        ajouter_dossier_definition_solidworks(rapport, "vilbrequin")
        return rapport


ArbreVilbrequinFine = None  # type: ignore


@dataclass
class VilbrequinFine(Vilbrequin):
    """
    Variante agrégée du vilbrequin qui récupère, quand disponible, les résultats
    fins portés par `ArbreVilbrequinFine` : réactions de paliers, joues,
    équilibrage, fatigue et torsion vibratoire.
    """

    arbre: Optional[Any] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport = super().analyser(strict=False)

        if ArbreVilbrequinFine is not None and isinstance(self.arbre, ArbreVilbrequinFine):
            ra = self.arbre.analyser(strict=False)
        elif self.arbre is not None and hasattr(self.arbre, "analyser"):
            try:
                ra = self.arbre.analyser(strict=False)
            except Exception:
                ra = None
        else:
            ra = None

        if isinstance(ra, dict):
            for key in ("reactions_paliers", "joues", "equilibrage", "fatigue", "torsion_vibratoire", "pressions_contact"):
                if key in ra:
                    rapport[key] = ra[key]
            rapport.setdefault("sources", {})
            rapport["sources"]["modele_fin_vilebrequin"] = "arbre_vilbrequin_fine"
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "modele_fin_vilebrequin",
                "Fournir un arbre compatible pour agréger les réactions, l'équilibrage, la fatigue et la torsion vibratoire.",
            )

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "VilbrequinFine(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        ajouter_dossier_definition_solidworks(rapport, "vilbrequin")
        return rapport


if __name__ == "__main__":  # pragma: no cover
    from pprint import pprint
    vb = Vilbrequin()
    pprint(vb.analyser(strict=False))

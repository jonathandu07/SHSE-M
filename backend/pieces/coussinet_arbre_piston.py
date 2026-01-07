# backend/pieces/coussinet_arbre_piston.py
# =============================================================================
# COUSSINET ARBRE-PISTON — SHSE-M
# =============================================================================
# Rôle :
# - Palier lisse (coussinet) entre l’arbre de piston et la bielle (ou tête de bielle),
#   pour réduire frottement et usure.
#
# Objectif :
# - Calculer TOUT ce qui est calculable (pressions, PV, échauffement par frottement,
#   régime hydrodynamique minimal via Sommerfeld si données suffisantes, etc.).
# - Dimensionner (au minimum) les dimensions calculables SANS inventer :
#   * d (diamètre portée) : déductible si l’arbre de piston le fournit (directement ou via son rapport).
#   * L (longueur) : calcul de L_min à partir des contraintes disponibles :
#       - pression projetée admissible p_adm
#       - PV admissible pv_adm
#     => si aucune limite n’est fournie, on ne peut pas dimensionner L.
#   * épaisseur e / jeu c : non déductibles sans données d’assemblage, tolérances, lubrifiant, tables, etc.
#
# Notes modèle (sans heuristique cachée) :
# - Pression moyenne projetée : p = W / (d * L)
# - ω = 2πN (N en tr/s ; rpm fourni en tr/min)
# - Vitesse de glissement : v = ω * (d/2)
# - PV = p * v  (W/m²)
#   Remarque importante : PV = (W/(dL))*(ω d/2) = W*ω/(2L) => indépendant de d si v défini ainsi.
# - Puissance frottement (approx Coulomb) : P = μ * W * v (si μ fourni)
# - Hydrodynamique (Sommerfeld) :
#   nécessite viscosité η, jeu radial c, géométrie L/d, charge W, vitesse N -> S.
#   On calcule S si possible, sans l’interpréter sans tables/corrélations fournies.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List, Literal, Iterable
import math


# =============================================================================
# Utilitaires
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


def _omega_rad_s(rpm: float) -> float:
    return 2.0 * math.pi * (rpm / 60.0)


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
# Résolution matériau (optionnelle via backend/ensemble/materiaux.py)
# =============================================================================

def _resoudre_materiau(
    cle: Optional[str],
    densite_kg_m3: Optional[float],
    k_therm_w_m_k: Optional[float],
    limite_pression_pa: Optional[float],
    *,
    mode_valeur: str = "typique",
) -> Dict[str, Optional[float]]:
    """
    Essaie de compléter densité, conductivité thermique, pression admissible via une DB matériaux.
    - Rien n’est inventé : si introuvable, on garde les entrées.
    - Note : la plupart des DB matériaux ne donnent pas p_adm / PV (tribologie) => souvent inconnue.
    """
    rho = densite_kg_m3
    k = k_therm_w_m_k
    p_adm = limite_pression_pa

    if cle:
        for modname in (
            "backend.ensemble.materiaux",
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                get_materiau = getattr(mod, "get_materiau", None)
                valeur = getattr(mod, "valeur", None)

                mat = None
                if callable(get_materiau):
                    mat = get_materiau(cle)
                else:
                    mats = getattr(mod, "MATERIAUX", None)
                    if isinstance(mats, dict):
                        mat = mats.get(cle)

                if mat is None:
                    continue

                def vprop(obj: Any, *names: str) -> Optional[float]:
                    for n in names:
                        raw = None
                        if isinstance(obj, dict) and n in obj:
                            raw = obj.get(n)
                        else:
                            raw = getattr(obj, n, None)
                        if raw is None:
                            continue
                        if callable(valeur):
                            try:
                                vv = valeur(raw, mode=mode_valeur)  # type: ignore[misc]
                                if vv is not None and _is_finite(vv):
                                    return float(vv)
                            except Exception:
                                pass
                        if _is_finite(raw):
                            return float(raw)
                    return None

                # Noms utilisés par backend/ensemble/materiaux.py
                rho = rho if rho is not None else vprop(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                k = k if k is not None else vprop(mat, "conductivite_thermique_w_mk", "conductivite_w_m_k", "k_w_m_k", "lambda_w_m_k")
                # “limite_pression” est rarement dispo dans une DB matériaux générique.
                p_adm = p_adm if p_adm is not None else vprop(mat, "pression_admissible_pa", "p_admissible_pa", "bearing_pressure_pa")

                break
            except Exception:
                continue

    return {"densite_kg_m3": rho, "conductivite_w_m_k": k, "pression_admissible_pa": p_adm}


# =============================================================================
# Déductions depuis arbre_piston
# =============================================================================

def _iter_floats(xs: Iterable[Any]) -> List[float]:
    out: List[float] = []
    for x in xs:
        if _is_finite(x):
            out.append(float(x))
    return out


def _extraire_depuis_rapport_arbre_piston(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait des candidats pour :
    - d (diamètre de portée coussinet)
    - L (longueur coussinet)
    - W (charge radiale approx.)
    - rpm
    depuis un rapport arbre_piston.analyser() si sa structure est compatible.

    Ne choisit pas un scénario : renvoie un unique si disponible, sinon des listes.
    """
    out: Dict[str, Any] = {"d_unique_m": None, "d_candidates_m": [], "L_m": None, "W_N": None, "rpm": None, "notes": []}

    if not isinstance(r, dict):
        return out

    ent = r.get("entrees", {}) if isinstance(r.get("entrees", {}), dict) else {}
    eff = r.get("efforts", {}) if isinstance(r.get("efforts", {}), dict) else {}

    # Géométrie coussinet si l’arbre la stocke explicitement
    if _is_finite(ent.get("diametre_portee_coussinet_m")):
        out["d_unique_m"] = float(ent["diametre_portee_coussinet_m"])
        out["notes"].append("d déduit de arbre_piston.entrees.diametre_portee_coussinet_m")
    if _is_finite(ent.get("longueur_coussinet_m")):
        out["L_m"] = float(ent["longueur_coussinet_m"])
        out["notes"].append("L déduite de arbre_piston.entrees.longueur_coussinet_m")

    # Effort radial approx.
    if _is_finite(eff.get("force_cisaillement_N")):
        out["W_N"] = float(eff["force_cisaillement_N"])
        out["notes"].append("W approx. déduite de arbre_piston.efforts.force_cisaillement_N")

    # rpm
    cin = r.get("cinematique", {}) if isinstance(r.get("cinematique", {}), dict) else {}
    if _is_finite(cin.get("rpm")):
        out["rpm"] = float(cin["rpm"])
        out["notes"].append("rpm déduit de arbre_piston.cinematique.rpm")
    elif _is_finite(ent.get("rpm")):
        out["rpm"] = float(ent["rpm"])
        out["notes"].append("rpm déduit de arbre_piston.entrees.rpm")

    # Si d non unique : tenter dimensionnement_evide
    if out["d_unique_m"] is None:
        dim = r.get("dimensionnement_evide", {}) if isinstance(r.get("dimensionnement_evide", {}), dict) else {}
        res = dim.get("resultat_unique") if isinstance(dim.get("resultat_unique"), dict) else None
        if isinstance(res, dict) and _is_finite(res.get("Do_m")):
            out["d_unique_m"] = float(res["Do_m"])
            out["notes"].append("d déduit de arbre_piston.dimensionnement_evide.resultat_unique.Do_m (Do)")
        else:
            sc = dim.get("scenarios") if isinstance(dim.get("scenarios"), dict) else None
            if isinstance(sc, dict):
                # structures possibles : critere_vm / critere_tresca = liste d'objets contenant Do_min_m
                cand: List[float] = []
                for kname in ("critere_vm", "critere_tresca"):
                    lst = sc.get(kname)
                    if isinstance(lst, list):
                        for it in lst:
                            if isinstance(it, dict) and _is_finite(it.get("Do_min_m")):
                                cand.append(float(it["Do_min_m"]))
                out["d_candidates_m"] = sorted(set(cand))
                if out["d_candidates_m"]:
                    out["notes"].append("d candidats extraits de arbre_piston.dimensionnement_evide.scenarios.(Do_min_m) (sans sélection).")

    return out


def _extraire_depuis_objet_arbre_piston(obj: Any) -> Dict[str, Any]:
    """
    Extrait directement depuis un objet arbre_piston, puis via obj.analyser() si possible.
    """
    out: Dict[str, Any] = {"d_unique_m": None, "d_candidates_m": [], "L_m": None, "W_N": None, "rpm": None, "notes": []}

    # Accès direct si attributs présents
    try:
        if _is_finite(getattr(obj, "diametre_portee_coussinet_m", None)):
            out["d_unique_m"] = float(getattr(obj, "diametre_portee_coussinet_m"))
            out["notes"].append("d déduit de arbre_piston.diametre_portee_coussinet_m")
        if _is_finite(getattr(obj, "longueur_coussinet_m", None)):
            out["L_m"] = float(getattr(obj, "longueur_coussinet_m"))
            out["notes"].append("L déduite de arbre_piston.longueur_coussinet_m")
        if _is_finite(getattr(obj, "force_cisaillement_N", None)):
            out["W_N"] = float(getattr(obj, "force_cisaillement_N"))
            out["notes"].append("W approx. déduite de arbre_piston.force_cisaillement_N")
        if _is_finite(getattr(obj, "rpm", None)):
            out["rpm"] = float(getattr(obj, "rpm"))
            out["notes"].append("rpm déduit de arbre_piston.rpm")
    except Exception:
        pass

    # Fallback : via analyser()
    if hasattr(obj, "analyser") and callable(getattr(obj, "analyser")):
        try:
            r = obj.analyser(strict=False)  # type: ignore[misc]
            ext = _extraire_depuis_rapport_arbre_piston(r if isinstance(r, dict) else {})
            # fusion
            for k in ("d_unique_m", "L_m", "W_N", "rpm"):
                out[k] = out[k] if out[k] is not None else ext.get(k)
            out["d_candidates_m"] = out["d_candidates_m"] or ext.get("d_candidates_m", [])
            out["notes"].extend(ext.get("notes", []))
        except Exception:
            out["notes"].append("Impossible d'extraire via arbre_piston.analyser() (erreur d'appel ou format inattendu).")

    # Dédup notes
    out["notes"] = list(dict.fromkeys(out["notes"]))
    return out


# =============================================================================
# Coussinet
# =============================================================================

LubrificationMode = Literal["inconnue", "sec", "huile", "eau", "autre"]


@dataclass
class CoussinetArbrePiston:
    """
    Coussinet lisse (journal bearing) pour arbre de piston.

    Le dimensionnement "sans invention" est possible uniquement si tu fournis :
    - charge_radiale_N (W) ou un arbre_piston dont on peut la déduire,
    - rpm,
    - au moins une limite : pression_admissible_pa et/ou pv_admissible_W_m2,
    - et un diamètre de portée d (ou un arbre_piston qui le donne / le dimensionne).

    Sinon, le module produit des inconnues et/ou des scénarios.
    """

    # Liens vers pièces (optionnels)
    arbre_piston: Optional[Any] = None   # idéalement backend.pieces.arbre_piston.ArbrePiston

    # Géométrie (si non déductible de l’arbre)
    diametre_portee_m: Optional[float] = None       # d (diamètre arbre côté coussinet)
    longueur_coussinet_m: Optional[float] = None    # L
    epaisseur_coussinet_m: Optional[float] = None   # e (utile masse + conduction)
    jeu_radial_m: Optional[float] = None            # c (clearance radial)
    excentricite_m: Optional[float] = None          # ε*c (si tu veux aller plus loin)

    # Efforts
    charge_radiale_N: Optional[float] = None        # W (portée radiale)
    charge_axiale_N: Optional[float] = None         # optionnel (rare ici)

    # Cinématique
    rpm: Optional[float] = None                     # vitesse relative (rotation de l’arbre)

    # Tribologie
    coefficient_frottement: Optional[float] = None  # μ
    mode_lubrification: LubrificationMode = "inconnue"

    # Lubrifiant : viscosité dynamique η (Pa.s), sinon tentative via fluide
    viscosite_Pa_s: Optional[float] = None
    temperature_lubrifiant_K: Optional[float] = None
    pression_lubrifiant_Pa: Optional[float] = None

    # Matériau coussinet
    materiau_coussinet: Optional[str] = None
    densite_coussinet_kg_m3: Optional[float] = None
    conductivite_coussinet_w_m_k: Optional[float] = None
    pression_admissible_pa: Optional[float] = None      # p_adm (tribologie / fabricant)
    pv_admissible_W_m2: Optional[float] = None          # PV_adm (tribologie / fabricant)

    # Facteur sécurité
    facteur_securite: float = 2.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "geometrie": {},
            "cinematique": {},
            "efforts": {},
            "tribologie": {},
            "dimensionnement": {},
            "pressions": {},
            "pv": {},
            "frottement": {},
            "hydrodynamique": {},
            "thermique": {},
            "masse": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ----------------------------
        # 1) Matériau coussinet (compléments)
        # ----------------------------
        props_mat = _resoudre_materiau(
            self.materiau_coussinet,
            self.densite_coussinet_kg_m3,
            self.conductivite_coussinet_w_m_k,
            self.pression_admissible_pa,
            mode_valeur="typique",
        )
        rho_c = props_mat["densite_kg_m3"]
        k_c = props_mat["conductivite_w_m_k"]
        p_adm = props_mat["pression_admissible_pa"]

        # ----------------------------
        # 2) Déductions depuis arbre_piston si possible
        # ----------------------------
        d = self.diametre_portee_m
        L = self.longueur_coussinet_m
        W = self.charge_radiale_N
        rpm = self.rpm

        d_candidates: List[float] = []

        if self.arbre_piston is not None:
            ext = _extraire_depuis_objet_arbre_piston(self.arbre_piston)
            if d is None and _is_finite(ext.get("d_unique_m")):
                d = float(ext["d_unique_m"])
            if not d_candidates:
                d_candidates = _iter_floats(ext.get("d_candidates_m", []))
            if L is None and _is_finite(ext.get("L_m")):
                L = float(ext["L_m"])
            if W is None and _is_finite(ext.get("W_N")):
                W = float(ext["W_N"])
            if rpm is None and _is_finite(ext.get("rpm")):
                rpm = float(ext["rpm"])
            for n in ext.get("notes", []):
                rapport["notes_modele"].append(n)

        # ----------------------------
        # 3) Dimensionnement minimal (si limites suffisantes)
        # ----------------------------
        # On ne "choisit" pas une géométrie finale : on calcule des minima / scénarios.
        dim: Dict[str, Any] = {"p_allow_pa": None, "pv_allow_W_m2": None, "solutions": [], "notes": []}

        p_allow = None
        if p_adm is not None and _is_finite(p_adm):
            p_allow = float(p_adm) / FS
            dim["p_allow_pa"] = p_allow
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pression admissible (p_adm)",
                "Dimensionnement pression possible si pression_admissible_pa est fourni (ou résoluble via materiau_coussinet).",
            )

        pv_allow = None
        if self.pv_admissible_W_m2 is not None:
            pv_allow = _req_pos("pv_admissible_W_m2", self.pv_admissible_W_m2) / FS
            dim["pv_allow_W_m2"] = pv_allow
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "PV admissible (PV_adm)",
                "Dimensionnement PV possible si pv_admissible_W_m2 est fourni (spec fabricant/standard).",
            )

        omega = None
        if rpm is not None:
            rpm = _req_pos("rpm", rpm, strictly=False)
            omega = _omega_rad_s(rpm)
        else:
            _push_inconnue(rapport, "partielles", "rpm", "Indispensable pour v, PV, et dimensionnement via PV.")

        if W is not None:
            W = _req_pos("charge_radiale_N", W, strictly=False)
        else:
            _push_inconnue(rapport, "impossibles", "charge_radiale_N", "Indispensable pour pression/PV/dimensionnement.")

        # Construire la liste de diamètres à analyser (d connu + candidats)
        if d is not None:
            d = _req_pos("diametre_portee_m", d)
            d_candidates = [d] + [x for x in d_candidates if x > 0 and abs(x - d) > 1e-12]
        d_candidates = sorted(set([x for x in d_candidates if x > 0]))

        def calc_L_min_for_d(d_use: float) -> Dict[str, Any]:
            out: Dict[str, Any] = {"d_m": d_use, "L_min_m": None, "contraintes": {}, "ok_avec_L": None, "L_actuel_m": L}
            if W is None:
                return out

            # Contrainte pression : L >= W/(d*p_allow)
            Lmin_p = None
            if p_allow is not None and p_allow > 0:
                Lmin_p = (W / (d_use * p_allow)) if (d_use > 0) else None
                out["contraintes"]["L_min_pression_m"] = Lmin_p
            # Contrainte PV : PV = W*ω/(2L) <= pv_allow  => L >= W*ω/(2*pv_allow)
            Lmin_pv = None
            if pv_allow is not None and pv_allow > 0 and omega is not None:
                Lmin_pv = (W * abs(omega)) / (2.0 * pv_allow)
                out["contraintes"]["L_min_PV_m"] = Lmin_pv

            cands = [x for x in (Lmin_p, Lmin_pv) if x is not None and x >= 0]
            if cands:
                out["L_min_m"] = max(cands)
            else:
                out["L_min_m"] = None

            if L is not None and out["L_min_m"] is not None:
                try:
                    L_act = _req_pos("longueur_coussinet_m", L)
                    out["ok_avec_L"] = (L_act + 0.0) >= float(out["L_min_m"])  # tolérance numérique
                except Exception:
                    pass

            # ratio L/d si L actuel connu
            if L is not None:
                try:
                    L_act = _req_pos("longueur_coussinet_m", L)
                    out["L_sur_d_actuel"] = (L_act / d_use) if d_use > 0 else None
                except Exception:
                    pass
            if out["L_min_m"] is not None:
                out["L_sur_d_min"] = (float(out["L_min_m"]) / d_use) if d_use > 0 else None

            return out

        if W is not None and (p_allow is not None or (pv_allow is not None and omega is not None)):
            if d_candidates:
                dim["solutions"] = [calc_L_min_for_d(dd) for dd in d_candidates]
                if d is None and len(d_candidates) > 0:
                    dim["notes"].append("Aucun d unique: solutions calculées pour d candidats (sans sélection).")
            else:
                # d inconnu => impossible d'appliquer contrainte pression ; PV possible sans d
                if pv_allow is not None and omega is not None:
                    Lmin_pv = (W * abs(omega)) / (2.0 * pv_allow)
                    dim["solutions"] = [{"d_m": None, "L_min_m": Lmin_pv, "contraintes": {"L_min_PV_m": Lmin_pv}, "ok_avec_L": None, "L_actuel_m": L}]
                    dim["notes"].append("d inconnu: seule contrainte PV donne un L_min (indépendant de d).")
                else:
                    dim["notes"].append("Dimensionnement impossible sans d (pression) et/ou sans rpm/PV_adm (PV).")
        else:
            dim["notes"].append("Dimensionnement impossible: fournir au moins W + (p_adm ou (PV_adm et rpm)).")

        rapport["dimensionnement"] = dim

        # ----------------------------
        # 4) Validation géométrie (si données)
        # ----------------------------
        if d is None and not d_candidates:
            _push_inconnue(rapport, "impossibles", "diametre_portee_m", "Indispensable pour pression, vitesse, masse/conduction.")
        elif d is None and d_candidates:
            _push_inconnue(rapport, "partielles", "diametre_portee_m", "d non unique: plusieurs candidats issus de arbre_piston.")
        else:
            # d déjà validé si non None
            pass

        if L is None:
            # Si dimensionnement a produit un L_min unique, on NE l’impose pas : on le laisse dans rapport["dimensionnement"].
            _push_inconnue(rapport, "impossibles", "longueur_coussinet_m", "Indispensable pour pression projetée (et résultats finaux).")
        else:
            L = _req_pos("longueur_coussinet_m", L)

        if W is None:
            _push_inconnue(rapport, "impossibles", "charge_radiale_N", "Indispensable pour pression, PV, frottement.")
        else:
            # W déjà validé
            pass

        # ----------------------------
        # 5) Cinématique : vitesse de glissement
        # ----------------------------
        v = None
        if rpm is not None and d is not None:
            omega = _omega_rad_s(rpm)
            v = omega * (0.5 * d)

        # ----------------------------
        # 6) Pression projetée + contraintes
        # ----------------------------
        p_proj = None
        if d is not None and L is not None and W is not None:
            denom = d * L
            if denom > 0:
                p_proj = W / denom
                rapport["pressions"]["pression_projetee_pa"] = p_proj
                rapport["pressions"]["surface_projetee_m2"] = denom
                rapport["pressions"]["charge_radiale_N"] = W

                if p_adm is not None:
                    p_allow2 = float(p_adm) / FS
                    rapport["pressions"]["pression_admissible_pa"] = float(p_adm)
                    rapport["pressions"]["pression_admissible_effective_pa"] = p_allow2
                    rapport["pressions"]["ok_pression"] = p_proj <= p_allow2
                    rapport["pressions"]["marge_pression"] = (p_allow2 / p_proj) if p_proj > 0 else None
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "pression admissible",
                        "Vérification pression possible si pression_admissible_pa est fourni.",
                    )

        # ----------------------------
        # 7) PV (pression * vitesse)
        # ----------------------------
        if p_proj is not None and v is not None:
            PV = p_proj * abs(v)  # W/m²
            rapport["pv"]["pv_W_m2"] = PV
            if self.pv_admissible_W_m2 is not None:
                pv_adm = _req_pos("pv_admissible_W_m2", self.pv_admissible_W_m2)
                pv_allow2 = pv_adm / FS
                rapport["pv"]["pv_admissible_W_m2"] = pv_adm
                rapport["pv"]["pv_admissible_effective_W_m2"] = pv_allow2
                rapport["pv"]["ok_pv"] = PV <= pv_allow2
                rapport["pv"]["marge_pv"] = (pv_allow2 / PV) if PV > 0 else None
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "PV admissible",
                    "Vérification PV possible si pv_admissible_W_m2 est fourni.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "PV",
                "Calculable si pression projetée (d,L,W) et rpm sont fournis.",
            )

        # ----------------------------
        # 8) Frottement / puissance dissipée
        # ----------------------------
        if self.coefficient_frottement is not None and v is not None and W is not None and d is not None:
            mu = _req_pos("coefficient_frottement", self.coefficient_frottement, strictly=False)
            P_f = mu * abs(W) * abs(v)  # W
            T_f = mu * abs(W) * (0.5 * d)  # N·m
            rapport["frottement"]["mu"] = mu
            rapport["frottement"]["puissance_frottement_W"] = P_f
            rapport["frottement"]["couple_frottement_Nm"] = T_f
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "puissance frottement",
                "Calculable si coefficient_frottement, rpm, charge_radiale_N et diametre_portee_m sont fournis.",
            )

        # ----------------------------
        # 9) Hydrodynamique (Sommerfeld) — uniquement si données suffisantes
        # ----------------------------
        eta = self.viscosite_Pa_s
        if eta is None and self.mode_lubrification in ("huile", "eau"):
            if self.mode_lubrification == "eau":
                if self.temperature_lubrifiant_K is not None and self.pression_lubrifiant_Pa is not None:
                    try:
                        from backend.ensemble.eau import etat_eau_pure  # type: ignore
                        et = etat_eau_pure(
                            T_K=float(self.temperature_lubrifiant_K),
                            p_Pa=float(self.pression_lubrifiant_Pa),
                            backend="auto",
                        )
                        eta = float(et.mu_Pa_s)
                        rapport["notes_modele"].append("viscosite_Pa_s déduite via backend.ensemble.eau.etat_eau_pure().mu_Pa_s")
                    except Exception:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "viscosité lubrifiant",
                            "mode=eau mais impossible de déduire (backend eau indisponible ou erreur).",
                        )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "viscosité lubrifiant",
                        "mode=eau : calculable si temperature_lubrifiant_K et pression_lubrifiant_Pa sont fournis.",
                    )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "viscosité lubrifiant",
                    "mode=huile : nécessite un module huile (non présent) ou viscosite_Pa_s fournie.",
                )

        if (
            eta is not None
            and p_proj is not None
            and rpm is not None
            and d is not None
            and L is not None
            and self.jeu_radial_m is not None
        ):
            eta = _req_pos("viscosite_Pa_s", eta)
            c = _req_pos("jeu_radial_m", self.jeu_radial_m)
            if c <= 0:
                raise ValueError("jeu_radial_m doit être > 0")

            N_tr_s = rpm / 60.0
            r = 0.5 * d
            S = (eta * N_tr_s * (r / c) ** 2 / p_proj) * (L / d)

            rapport["hydrodynamique"]["sommerfeld_S"] = S
            rapport["hydrodynamique"]["eta_Pa_s"] = eta
            rapport["hydrodynamique"]["jeu_radial_m"] = c
            rapport["hydrodynamique"]["L_sur_d"] = L / d
            rapport["hydrodynamique"]["notes"] = (
                "S calculé, mais aucune interprétation (ε, Q, f) sans tables/corrélations explicitement fournies."
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "hydrodynamique (Sommerfeld)",
                "Calculable si viscosite_Pa_s (ou déductible), rpm, pression_projetee, diametre_portee, longueur et jeu_radial sont fournis.",
            )

        # ----------------------------
        # 10) Thermique : conduction radiale à travers coussinet (si épaisseur + k)
        # ----------------------------
        if self.epaisseur_coussinet_m is not None and k_c is not None and d is not None and L is not None:
            e = _req_pos("epaisseur_coussinet_m", self.epaisseur_coussinet_m)
            k = _req_pos("conductivite_coussinet_w_m_k", k_c)
            ri = 0.5 * d
            ro = ri + e
            if ro <= ri:
                raise ValueError("epaisseur_coussinet_m invalide (ro<=ri).")
            R = math.log(ro / ri) / (2.0 * math.pi * k * L)
            rapport["thermique"]["R_conduction_K_W"] = R
            rapport["thermique"]["k_coussinet_W_m_K"] = k
            rapport["thermique"]["ri_m"] = ri
            rapport["thermique"]["ro_m"] = ro
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "thermique conduction",
                "Calculable si epaisseur_coussinet_m et conductivite_coussinet_w_m_k (ou materiau) sont fournis.",
            )

        # ----------------------------
        # 11) Masse (si e + rho)
        # ----------------------------
        if self.epaisseur_coussinet_m is not None and rho_c is not None and d is not None and L is not None:
            e = _req_pos("epaisseur_coussinet_m", self.epaisseur_coussinet_m)
            rho = _req_pos("densite_coussinet_kg_m3", rho_c)
            ri = 0.5 * d
            ro = ri + e
            V = math.pi * (ro * ro - ri * ri) * L
            m = rho * V
            rapport["masse"] = {
                "volume_m3": V,
                "masse_kg": m,
                "densite_kg_m3": rho,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "masse coussinet",
                "Calculable si epaisseur_coussinet_m, densite_coussinet_kg_m3 (ou materiau) sont fournis.",
            )

        # ----------------------------
        # 12) Entrées / sorties
        # ----------------------------
        rapport["entrees"] = {
            "diametre_portee_m": self.diametre_portee_m,
            "longueur_coussinet_m": self.longueur_coussinet_m,
            "epaisseur_coussinet_m": self.epaisseur_coussinet_m,
            "jeu_radial_m": self.jeu_radial_m,
            "charge_radiale_N": self.charge_radiale_N,
            "rpm": self.rpm,
            "coefficient_frottement": self.coefficient_frottement,
            "mode_lubrification": self.mode_lubrification,
            "viscosite_Pa_s": self.viscosite_Pa_s,
            "temperature_lubrifiant_K": self.temperature_lubrifiant_K,
            "pression_lubrifiant_Pa": self.pression_lubrifiant_Pa,
            "materiau_coussinet": self.materiau_coussinet,
            "densite_coussinet_kg_m3": self.densite_coussinet_kg_m3,
            "conductivite_coussinet_w_m_k": self.conductivite_coussinet_w_m_k,
            "pression_admissible_pa": self.pression_admissible_pa,
            "pv_admissible_W_m2": self.pv_admissible_W_m2,
            "facteur_securite": self.facteur_securite,
        }

        rapport["geometrie"] = {
            "diametre_portee_m": d,
            "longueur_coussinet_m": L,
            "epaisseur_coussinet_m": self.epaisseur_coussinet_m,
            "jeu_radial_m": self.jeu_radial_m,
            "diametre_exterieur_m": (d + 2.0 * self.epaisseur_coussinet_m) if (d is not None and self.epaisseur_coussinet_m is not None) else None,
        }
        rapport["cinematique"] = {
            "rpm": rpm,
            "omega_rad_s": (_omega_rad_s(rpm) if rpm is not None else None),
            "vitesse_glissement_m_s": v,
        }
        rapport["efforts"] = {
            "charge_radiale_N": W,
            "charge_axiale_N": self.charge_axiale_N,
        }
        rapport["tribologie"] = {
            "mode_lubrification": self.mode_lubrification,
            "viscosite_Pa_s": eta,
            "coefficient_frottement": self.coefficient_frottement,
        }

        # ----------------------------
        # 13) Mode strict
        # ----------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "CoussinetArbrePiston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# =============================================================================
# Exemple d'usage (à supprimer en prod)
# =============================================================================
if __name__ == "__main__":
    from pprint import pprint

    # Exemple volontairement complet : ici p_adm et PV_adm sont des données de SPEC (à fournir, pas à inventer).
    c = CoussinetArbrePiston(
        diametre_portee_m=0.020,
        longueur_coussinet_m=0.020,
        epaisseur_coussinet_m=0.002,
        charge_radiale_N=2000.0,
        rpm=3000.0,
        coefficient_frottement=0.05,
        mode_lubrification="eau",
        temperature_lubrifiant_K=300.0,
        pression_lubrifiant_Pa=101325.0,
        jeu_radial_m=20e-6,
        materiau_coussinet="bronze_cusn12",
        # p_adm / PV_adm : EXEMPLES uniquement (doivent venir d'une spec réelle)
        pression_admissible_pa=30e6,
        pv_admissible_W_m2=1.0e9,
        facteur_securite=2.0,
    )

    pprint(c.analyser(strict=False))

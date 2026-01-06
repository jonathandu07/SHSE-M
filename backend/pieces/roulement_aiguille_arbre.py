# backend/pieces/roulement_aiguille_arbre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
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
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Tente .analyser(strict=False), puis .calculer(), puis .analyser().
    """
    if obj is None:
        return None

    for name in ("analyser", "calculer"):
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                if name == "analyser":
                    out = fn(strict=False)
                else:
                    out = fn()
                return out if isinstance(out, dict) else None
            except TypeError:
                try:
                    out = fn()
                    return out if isinstance(out, dict) else None
                except Exception:
                    continue
            except Exception:
                continue
    return None


def _push_inconnue(rapport: Dict[str, Any], kind: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(kind, []).append({"nom": nom, "raison": raison})


# =============================================================================
# Formules roulements (standard ISO "générique" - sans données constructeur)
# =============================================================================

def _L10_rev_from_C_P(C_N: float, P_N: float, *, p: float) -> float:
    """
    Durée de vie nominale L10 en nombre de tours.
    L10 (10^6 tours) = (C/P)^p  => L10_rev = 1e6 * (C/P)^p
    """
    C = _req_pos("C_N", C_N, strictly=True)
    P = _req_pos("P_N", P_N, strictly=True)
    return 1e6 * (C / P) ** p


def _L10_h_from_C_P(C_N: float, P_N: float, n_rpm: float, *, p: float) -> float:
    """
    L10h = L10_rev / (60*n)
    """
    n = _req_pos("n_rpm", n_rpm, strictly=True)
    L10_rev = _L10_rev_from_C_P(C_N, P_N, p=p)
    return L10_rev / (60.0 * n)


def _C_required_from_P_L10h(P_N: float, n_rpm: float, L10_h: float, *, p: float) -> float:
    """
    Inversion de L10h pour obtenir C requis.
    L10_rev = 60*n*L10h
    L10_rev = 1e6*(C/P)^p => C = P*(L10_rev/1e6)^(1/p)
    """
    P = _req_pos("P_N", P_N, strictly=True)
    n = _req_pos("n_rpm", n_rpm, strictly=True)
    Lh = _req_pos("L10_h", L10_h, strictly=True)
    Lrev = 60.0 * n * Lh
    return P * (Lrev / 1e6) ** (1.0 / p)


def _force_tangentielle_depuis_couple(T_Nm: float, r_m: float) -> float:
    """
    Force tangente équivalente au rayon r : F = T/r
    (utile comme borne calculable si T et r sont connus)
    """
    T = _req_finite("couple_max_Nm", T_Nm)
    r = _req_pos("rayon_manivelle_m", r_m, strictly=True)
    return abs(T) / r if r > 0 else float("nan")


def _dmin_torsion_vonmises(T_Nm: float, Re_pa: float, FS: float) -> float:
    """
    Torsion pure, critère von Mises :
    τ = 16T/(π d^3)
    σ_eq = sqrt(3)*τ <= Re/FS
    """
    T = _req_finite("couple_max_Nm", T_Nm)
    Re = _req_pos("limite_elastique_pa", Re_pa, strictly=True)
    FS = _req_pos("facteur_securite", FS, strictly=True)
    tau_adm = Re / (FS * math.sqrt(3.0))
    if tau_adm <= 0:
        raise ValueError("tau_adm <= 0")
    return (16.0 * abs(T) / (math.pi * tau_adm)) ** (1.0 / 3.0)


# =============================================================================
# Référence "commerce" (optionnelle)
# =============================================================================

@dataclass
class ReferenceRoulementAiguille:
    """
    Données fournisseur/constructeur (si tu as déjà une référence en tête).
    Tu peux laisser None si tu n'as pas ces infos (le module ne les invente pas).
    """
    designation: Optional[str] = None

    d_interieur_m: Optional[float] = None   # alésage / arbre (ID)
    D_exterieur_m: Optional[float] = None   # logement (OD)
    B_largeur_m: Optional[float] = None     # largeur (B)

    C_dynamique_N: Optional[float] = None   # capacité dynamique (catalogue)
    C0_statique_N: Optional[float] = None   # capacité statique (catalogue)

    n_lim_rpm: Optional[float] = None       # vitesse limite catalogue (si fournie)


# =============================================================================
# Pièce : Roulement à aiguilles (arbre / vilebrequin)
# =============================================================================

@dataclass
class RoulementAiguilleArbre:
    """
    Roulement à aiguilles "issu du commerce".
    Objectif : sortir un maximum d'informations calculées pour choisir une référence catalogue,
    SANS RIEN INVENTER.

    Dépendances (recommandées) :
    - vilbrequin (backend/pieces/vilbrequin.py) : rpm, couple, diamètres/largeurs des portées.
    - bielle / piston : si ces modules fournissent une force max, on peut l'utiliser comme charge radiale candidate.

    Remarque :
    - Un roulement à aiguilles standard est principalement radial.
      Si tu as une charge axiale (thrust), il faut une autre solution (butée) :
      le module ne déduit pas une butée sans données explicites.
    """

    # Dépendances
    vilbrequin: Optional[Any] = None
    arbre_vilbrequin: Optional[Any] = None
    bielle: Optional[Any] = None
    piston: Optional[Any] = None
    cylindre: Optional[Any] = None

    # Sélection / position (si tu veux forcer une seule portée)
    # None => calcule et rapporte "journal principal" ET "maneton" si disponibles.
    type_portee: Optional[str] = None  # "journal" | "maneton" | None

    # Entrées explicites (si non déductibles)
    rpm: Optional[float] = None
    couple_max_Nm: Optional[float] = None
    rayon_manivelle_m: Optional[float] = None

    # Charge radiale (si tu la connais déjà, elle prime)
    force_radiale_equivalente_N: Optional[float] = None
    force_axiale_N: Optional[float] = None  # si connue (sinon inconnue)

    # Critère de vie (si tu veux dimensionner C requis)
    duree_vie_cible_h: Optional[float] = None

    # Exposant p (roulements à rouleaux/à aiguilles ~ 10/3) :
    # si tu ne veux rien supposer, laisse None -> pas de calcul de durée de vie.
    exposant_vie_p: Optional[float] = None

    # Critère "pression projetée" optionnel (uniquement si tu veux comparer à une valeur admissible)
    # p_proj = Fr / (d * B)  (d et B = portée)
    pression_projetee_admissible_pa: Optional[float] = None

    # Contraintes arbre (si diamètres inconnus et si on veut calculer un d_min)
    limite_elastique_pa: Optional[float] = None
    facteur_securite: float = 2.0

    # Référence commerce (facultatif) + vérification
    reference: Optional[ReferenceRoulementAiguille] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "roulement_aiguille_arbre",
            "entrees": {},
            "recuperations": {},
            "roulement": {},
            "dimensions_requises": {},
            "dimensions_reference": {},
            "charges": {},
            "vie": {},
            "verifications_reference": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ---------------------------------------------------------------------
        # 1) Récupérer rapports dépendances
        # ---------------------------------------------------------------------
        rep_vb = _try_call_report(self.vilbrequin)
        rep_av = _try_call_report(self.arbre_vilbrequin)
        rep_b = _try_call_report(self.bielle)
        rep_p = _try_call_report(self.piston)
        rep_c = _try_call_report(self.cylindre)

        rapport["recuperations"] = {
            "vilbrequin": bool(rep_vb),
            "arbre_vilbrequin": bool(rep_av),
            "bielle": bool(rep_b),
            "piston": bool(rep_p),
            "cylindre": bool(rep_c),
        }

        # ---------------------------------------------------------------------
        # 2) Cinématique : rpm / couple / rayon
        # ---------------------------------------------------------------------
        rpm = self.rpm
        if rpm is None:
            rpm = _dig(rep_vb, "cinematique", "rpm") or _dig(rep_vb, "cinematique", "rpm")
            if rpm is None:
                rpm = _dig(rep_av, "recuperations", "rpm") or _dig(rep_av, "cinematique", "rpm")
            if rpm is None:
                rpm = _get(self.vilbrequin, "rpm") or _get(self.arbre_vilbrequin, "rpm")
        if rpm is not None:
            rpm = _req_pos("rpm", rpm, strictly=False)
            rapport["roulement"]["rpm"] = rpm
        else:
            _push_inconnue(rapport, "partielles", "rpm", "Requis pour vérifier vitesse et calculer une durée de vie en heures.")

        T = self.couple_max_Nm
        if T is None:
            T = _dig(rep_vb, "cinematique", "couple_max_Nm")
            if T is None:
                T = _dig(rep_av, "entrees", "couple_max_Nm")
            if T is None:
                T = _get(self.vilbrequin, "couple_max_Nm") or _get(self.arbre_vilbrequin, "couple_max_Nm")
        if T is not None:
            T = _req_pos("couple_max_Nm", T, strictly=False)
            rapport["roulement"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rapport, "partielles", "couple_max_Nm", "Utile pour force tangente équivalente (F=T/r) si r est connu.")

        r = self.rayon_manivelle_m
        if r is None:
            r = _dig(rep_vb, "cinematique", "rayon_manivelle_m")
            if r is None:
                r = _dig(rep_av, "cinematique", "rayon_manivelle_m")
        if r is not None:
            r = _req_pos("rayon_manivelle_m", r)
            rapport["roulement"]["rayon_manivelle_m"] = r
        else:
            _push_inconnue(rapport, "partielles", "rayon_manivelle_m", "Requis pour F=T/r (force tangente équivalente).")

        # ---------------------------------------------------------------------
        # 3) Géométrie portée : (journal, maneton) depuis vilbrequin/arbre_vilbrequin
        # ---------------------------------------------------------------------
        # On sort "journal" et "maneton" si possible, même si type_portee est None.
        def lire_portee(kind: str) -> Dict[str, Optional[float]]:
            # kind: "journal" ou "maneton"
            if kind == "journal":
                d = (
                    _dig(rep_vb, "geometrie", "diametre_journal_principal_m")
                    or _dig(rep_av, "journal", "diametre_m")
                    or _dig(rep_av, "geometrie", "diametre_journal_principal_m")
                    or _get(self.vilbrequin, "diametre_journal_principal_m")
                    or _get(self.arbre_vilbrequin, "diametre_journal_principal_m")
                )
                B = (
                    _dig(rep_vb, "geometrie", "largeur_portee_journal_m")
                    or _dig(rep_av, "geometrie", "largeur_portee_journal_m")
                    or _get(self.vilbrequin, "largeur_portee_journal_m")
                    or _get(self.arbre_vilbrequin, "largeur_portee_journal_m")
                )
            else:
                d = (
                    _dig(rep_vb, "geometrie", "diametre_maneton_m")
                    or _dig(rep_av, "geometrie", "diametre_maneton_m")
                    or _get(self.vilbrequin, "diametre_maneton_m")
                    or _get(self.arbre_vilbrequin, "diametre_maneton_m")
                )
                # largeur maneton : souvent la largeur de portée grande tête de bielle
                B = (
                    _dig(rep_vb, "geometrie", "largeur_portee_maneton_m")
                    or _dig(rep_av, "geometrie", "largeur_portee_maneton_m")
                    or _get(self.vilbrequin, "largeur_portee_maneton_m")
                    or _get(self.arbre_vilbrequin, "largeur_portee_maneton_m")
                )
                if B is None:
                    B = _dig(rep_b, "geometrie", "grande_tete", "longueur_portee_grande_tete_m") or _get(self.bielle, "longueur_portee_grande_tete_m")
            out: Dict[str, Optional[float]] = {"d_m": None, "B_m": None}
            if d is not None and _is_finite(d):
                out["d_m"] = _req_pos(f"diametre_{kind}_m", d)
            if B is not None and _is_finite(B):
                out["B_m"] = _req_pos(f"largeur_portee_{kind}_m", B)
            return out

        portee_j = lire_portee("journal")
        portee_m = lire_portee("maneton")

        rapport["dimensions_requises"]["journal"] = {
            "d_interieur_requis_m": portee_j["d_m"],
            "B_largeur_requise_m": portee_j["B_m"],
        }
        rapport["dimensions_requises"]["maneton"] = {
            "d_interieur_requis_m": portee_m["d_m"],
            "B_largeur_requise_m": portee_m["B_m"],
        }

        if portee_j["d_m"] is None:
            _push_inconnue(rapport, "partielles", "diametre_journal_principal_m", "Requis pour choisir l'alésage (d) du roulement côté journal.")
        if portee_m["d_m"] is None:
            _push_inconnue(rapport, "partielles", "diametre_maneton_m", "Requis pour choisir l'alésage (d) du roulement côté maneton.")
        if portee_j["B_m"] is None:
            _push_inconnue(rapport, "partielles", "largeur_portee_journal_m", "Requise pour choisir la largeur (B) du roulement côté journal.")
        if portee_m["B_m"] is None:
            _push_inconnue(rapport, "partielles", "largeur_portee_maneton_m", "Requise pour choisir la largeur (B) du roulement côté maneton.")

        # Si type_portee est spécifié, on ne calculera les charges/vie que pour celle-là,
        # mais on conserve les dimensions requises des deux pour aider au choix.
        type_portee = self.type_portee
        if type_portee is not None and type_portee not in ("journal", "maneton"):
            raise ValueError("type_portee doit être 'journal', 'maneton' ou None.")

        # ---------------------------------------------------------------------
        # 4) Charges : candidates calculables (sans hypothèses de cycle)
        # ---------------------------------------------------------------------
        # Priorité si force_radiale_equivalente_N donnée
        Fr_user = self.force_radiale_equivalente_N
        if Fr_user is not None:
            Fr_user = _req_pos("force_radiale_equivalente_N", Fr_user, strictly=False)
            rapport["charges"]["force_radiale_equivalente_N"] = Fr_user

        Fax = self.force_axiale_N
        if Fax is not None:
            Fax = _req_pos("force_axiale_N", Fax, strictly=False)
            rapport["charges"]["force_axiale_N"] = Fax
            rapport["notes_modele"].append(
                "Charge axiale fournie. Un roulement à aiguilles standard est principalement radial : vérifier la nécessité d'une butée."
            )

        # Candidate 1 : force tangente équivalente via couple (si T et r connus)
        F_tan = None
        if T is not None and r is not None and r > 0:
            F_tan = _force_tangentielle_depuis_couple(T, r)
            rapport["charges"]["force_tangente_equivalente_N"] = F_tan
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force_tangente_equivalente_N",
                "Calculable si couple_max_Nm et rayon_manivelle_m sont connus (F=T/r).",
            )

        # Candidate 2 : force max depuis bielle (si disponible)
        F_bielle_max = None
        # Le module bielle expose: rapport['efforts']['force_axiale_max_N']
        v = _dig(rep_b, "efforts", "force_axiale_max_N")
        if _is_finite(v):
            F_bielle_max = abs(float(v))
            rapport["charges"]["force_max_depuis_bielle_N"] = F_bielle_max

        # Candidate 3 : force gaz depuis piston (si dispo)
        F_gaz = None
        v = _dig(rep_p, "resultats", "force_gaz_N")
        if _is_finite(v):
            F_gaz = abs(float(v))
            rapport["charges"]["force_gaz_depuis_piston_N"] = F_gaz

        # Sélection du P (charge équivalente) :
        # - si l'utilisateur fournit Fr_user => P=Fr_user
        # - sinon, on liste les candidats calculables et on fournit P_min/P_max "calculés"
        #   (sans inventer un cycle, donc pas de "vrai max" si rien n'est fourni).
        candidates: List[float] = []
        for val in (F_tan, F_bielle_max, F_gaz):
            if val is not None and _is_finite(val) and val >= 0:
                candidates.append(float(val))

        if Fr_user is not None:
            P = Fr_user
            rapport["charges"]["P_equivalente_N"] = P
            rapport["charges"]["P_source"] = "force_radiale_equivalente_N (entrée utilisateur)"
        else:
            if candidates:
                rapport["charges"]["P_min_calculable_N"] = min(candidates)
                rapport["charges"]["P_max_calculable_N"] = max(candidates)
                rapport["charges"]["P_sources_disponibles"] = [
                    "force_tangente_equivalente_N" if F_tan is not None else None,
                    "force_max_depuis_bielle_N" if F_bielle_max is not None else None,
                    "force_gaz_depuis_piston_N" if F_gaz is not None else None,
                ]
                rapport["charges"]["P_sources_disponibles"] = [s for s in rapport["charges"]["P_sources_disponibles"] if s]
                _push_inconnue(
                    rapport,
                    "partielles",
                    "P_equivalente_N",
                    "Pour dimensionner un roulement catalogue, il faut une charge radiale équivalente P. "
                    "Tu peux la fournir directement, ou fournir un modèle de charges (cycle/angles/appuis).",
                )
            else:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "P_equivalente_N",
                    "Aucune charge calculable : fournir force_radiale_equivalente_N ou rendre déductible via bielle/piston/cycle.",
                )

        # ---------------------------------------------------------------------
        # 5) Pression projetée (optionnel) : p = Fr/(d*B)
        # ---------------------------------------------------------------------
        p_adm = self.pression_projetee_admissible_pa
        if p_adm is not None:
            p_adm = _req_pos("pression_projetee_admissible_pa", p_adm, strictly=True)
            rapport["roulement"]["pression_projetee_admissible_pa"] = p_adm

        def pression_projetee(Fr: float, d: float, B: float) -> Optional[float]:
            if Fr is None or d is None or B is None:
                return None
            if d <= 0 or B <= 0:
                return None
            return Fr / (d * B)

        # calculer p_proj pour journal/maneton si possible (avec Fr_user ou candidates max)
        Fr_for_pressure = None
        if Fr_user is not None:
            Fr_for_pressure = Fr_user
        elif candidates:
            # on ne "prétend" pas que c'est la vraie charge maxi ; c'est la plus grande candidate calculable
            Fr_for_pressure = max(candidates)

        if Fr_for_pressure is not None:
            pj = None
            pm = None
            if portee_j["d_m"] is not None and portee_j["B_m"] is not None:
                pj = pression_projetee(Fr_for_pressure, portee_j["d_m"], portee_j["B_m"])
            if portee_m["d_m"] is not None and portee_m["B_m"] is not None:
                pm = pression_projetee(Fr_for_pressure, portee_m["d_m"], portee_m["B_m"])
            rapport["charges"]["pression_projetee_journal_pa"] = pj
            rapport["charges"]["pression_projetee_maneton_pa"] = pm

            if p_adm is not None:
                rapport["charges"]["ok_p_proj_journal"] = (pj is not None and pj <= p_adm)
                rapport["charges"]["ok_p_proj_maneton"] = (pm is not None and pm <= p_adm)

        # ---------------------------------------------------------------------
        # 6) Dimensionnement vie : C requis (si p + rpm + P + L10h fournis)
        # ---------------------------------------------------------------------
        p = self.exposant_vie_p
        if p is not None:
            p = _req_pos("exposant_vie_p", p, strictly=True)
            rapport["vie"]["exposant_p"] = p
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "exposant_vie_p",
                "Requis pour calculer L10 / C requis (catalogue). Pour un roulement à rouleaux, p est généralement > 1 (à confirmer).",
            )

        Lh = self.duree_vie_cible_h
        if Lh is not None:
            Lh = _req_pos("duree_vie_cible_h", Lh, strictly=True)
            rapport["vie"]["duree_vie_cible_h"] = Lh
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "duree_vie_cible_h",
                "Requise pour calculer C requis (sinon impossible de dimensionner la capacité dynamique).",
            )

        # P exploitable pour C requis ?
        # - si Fr_user => P=Fr_user
        # - sinon impossible : on ne choisit pas arbitrairement une candidate comme "P"
        P_for_life = Fr_user if Fr_user is not None else None
        if p is not None and Lh is not None and rpm is not None and P_for_life is not None:
            C_req = _C_required_from_P_L10h(P_for_life, rpm, Lh, p=p)
            rapport["vie"]["C_dynamique_requis_N"] = C_req
            rapport["vie"]["P_utilisee_N"] = P_for_life
            rapport["vie"]["P_source"] = "force_radiale_equivalente_N (entrée utilisateur)"
        else:
            if Fr_user is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "C_dynamique_requis_N",
                    "Calculable si (force_radiale_equivalente_N, rpm, duree_vie_cible_h, exposant_vie_p) sont fournis.",
                )

        # ---------------------------------------------------------------------
        # 7) d_min (arbre) : uniquement si on manque de diamètre et si Re + T sont connus
        # ---------------------------------------------------------------------
        # (utile pour fixer un alésage requis si la géométrie n'a pas encore été arrêtée)
        Re = self.limite_elastique_pa
        if Re is None:
            # tenter via vilbrequin (materiau.limite_elastique_pa)
            Re = _dig(rep_vb, "materiau", "limite_elastique_pa")
            if Re is None:
                Re = _dig(rep_av, "materiau", "limite_elastique_pa")
        if Re is not None:
            Re = _req_pos("limite_elastique_pa", Re, strictly=True)
            rapport["roulement"]["limite_elastique_pa"] = Re

        FS = _req_pos("facteur_securite", self.facteur_securite, strictly=True)
        rapport["roulement"]["facteur_securite"] = FS

        if T is not None and Re is not None:
            try:
                dmin = _dmin_torsion_vonmises(T, Re, FS)
                rapport["dimensions_requises"]["d_min_torsion_vonmises_m"] = dmin
                # utile si les diamètres n'étaient pas disponibles
                if portee_j["d_m"] is None:
                    rapport["dimensions_requises"]["journal"]["d_interieur_requis_m"] = dmin
                    rapport["notes_modele"].append("Journal : d_interieur_requis_m fixé par d_min (torsion von Mises) faute de diamètre connu.")
                if portee_m["d_m"] is None:
                    rapport["dimensions_requises"]["maneton"]["d_interieur_requis_m"] = dmin
                    rapport["notes_modele"].append("Maneton : d_interieur_requis_m fixé par d_min (torsion von Mises) faute de diamètre connu.")
            except Exception as e:
                _push_inconnue(rapport, "partielles", "d_min_torsion_vonmises_m", f"Erreur calcul d_min torsion : {e!r}")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "d_min_torsion_vonmises_m",
                "Calculable si couple_max_Nm et limite_elastique_pa sont connus (avec facteur_securite).",
            )

        # ---------------------------------------------------------------------
        # 8) Référence commerce : copier + vérifier si possible
        # ---------------------------------------------------------------------
        ref = self.reference
        if ref is not None:
            dims_ref: Dict[str, Any] = {"designation": ref.designation}

            if ref.d_interieur_m is not None:
                dims_ref["d_interieur_m"] = _req_pos("reference.d_interieur_m", ref.d_interieur_m)
            if ref.D_exterieur_m is not None:
                dims_ref["D_exterieur_m"] = _req_pos("reference.D_exterieur_m", ref.D_exterieur_m)
            if ref.B_largeur_m is not None:
                dims_ref["B_largeur_m"] = _req_pos("reference.B_largeur_m", ref.B_largeur_m)

            if ref.C_dynamique_N is not None:
                dims_ref["C_dynamique_N"] = _req_pos("reference.C_dynamique_N", ref.C_dynamique_N)
            if ref.C0_statique_N is not None:
                dims_ref["C0_statique_N"] = _req_pos("reference.C0_statique_N", ref.C0_statique_N)
            if ref.n_lim_rpm is not None:
                dims_ref["n_lim_rpm"] = _req_pos("reference.n_lim_rpm", ref.n_lim_rpm, strictly=False)

            rapport["dimensions_reference"] = dims_ref

            # Vérifs dimensions : selon type_portee (ou les deux)
            def check_dims_for(kind: str) -> Dict[str, Any]:
                out: Dict[str, Any] = {}
                d_req = _dig(rapport, "dimensions_requises", kind, "d_interieur_requis_m")
                B_req = _dig(rapport, "dimensions_requises", kind, "B_largeur_requise_m")
                d_ref = dims_ref.get("d_interieur_m")
                B_ref = dims_ref.get("B_largeur_m")

                out["d_ok"] = (d_req is not None and d_ref is not None and abs(d_ref - d_req) < 1e-12)  # égalité stricte (pas de tolérance inventée)
                out["B_ok"] = (B_req is not None and B_ref is not None and B_ref >= B_req)
                out["d_requis_m"] = d_req
                out["d_ref_m"] = d_ref
                out["B_requise_m"] = B_req
                out["B_ref_m"] = B_ref
                return out

            if type_portee is None:
                rapport["verifications_reference"]["journal"] = check_dims_for("journal")
                rapport["verifications_reference"]["maneton"] = check_dims_for("maneton")
            else:
                rapport["verifications_reference"][type_portee] = check_dims_for(type_portee)

            # Vérif vitesse limite (si fournie)
            if rpm is not None and ref.n_lim_rpm is not None:
                rapport["verifications_reference"]["vitesse_ok"] = (rpm <= float(ref.n_lim_rpm))

            # Vérif vie si tout est connu
            if p is not None and rpm is not None and Fr_user is not None and ref.C_dynamique_N is not None:
                L10h = _L10_h_from_C_P(float(ref.C_dynamique_N), float(Fr_user), float(rpm), p=p)
                rapport["verifications_reference"]["L10h_calculee_h"] = L10h
                if Lh is not None:
                    rapport["verifications_reference"]["L10h_ok"] = (L10h >= float(Lh))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "verification_L10h_reference",
                    "Calculable si (reference.C_dynamique_N, force_radiale_equivalente_N, rpm, exposant_vie_p) sont fournis.",
                )

        else:
            _push_inconnue(
                rapport,
                "partielles",
                "reference_roulement",
                "Optionnel : si tu donnes une référence (d/D/B/C/C0/n_lim), le module peut la vérifier (dimensions, vitesse, vie).",
            )

        # ---------------------------------------------------------------------
        # 9) Format attendu par ArbreVilbrequin (compat)
        # ---------------------------------------------------------------------
        # ArbreVilbrequin extrait :
        # - dimensions_requises.d_interieur_requis_m
        # - dimensions_reference.{d_interieur_m, D_exterieur_m, B_largeur_m}
        #
        # Ici, comme on peut calculer journal+maneton, on expose aussi des raccourcis.
        # Si type_portee est défini => raccourci pointe sur celle-ci.
        def shortcut(kind: str) -> Optional[Dict[str, Any]]:
            if kind == "journal":
                return rapport["dimensions_requises"].get("journal")
            if kind == "maneton":
                return rapport["dimensions_requises"].get("maneton")
            return None

        if type_portee is None:
            # par défaut, on ne "choisit" pas arbitrairement une portée
            rapport["dimensions_requises"]["d_interieur_requis_m"] = None
            _push_inconnue(
                rapport,
                "partielles",
                "dimensions_requises.d_interieur_requis_m",
                "Ambigu : préciser type_portee ('journal' ou 'maneton') si tu veux fournir un seul d_interieur_requis_m au module ArbreVilbrequin.",
            )
        else:
            rapport["dimensions_requises"]["d_interieur_requis_m"] = _dig(rapport, "dimensions_requises", type_portee, "d_interieur_requis_m")

        # ---------------------------------------------------------------------
        # Entrées (traçabilité)
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "type_portee": self.type_portee,
            "rpm": self.rpm,
            "couple_max_Nm": self.couple_max_Nm,
            "rayon_manivelle_m": self.rayon_manivelle_m,
            "force_radiale_equivalente_N": self.force_radiale_equivalente_N,
            "force_axiale_N": self.force_axiale_N,
            "duree_vie_cible_h": self.duree_vie_cible_h,
            "exposant_vie_p": self.exposant_vie_p,
            "pression_projetee_admissible_pa": self.pression_projetee_admissible_pa,
            "limite_elastique_pa": self.limite_elastique_pa,
            "facteur_securite": self.facteur_securite,
            "reference": (self.reference.designation if self.reference else None),
        }

        if strict:
            # en strict, on exige au minimum : type_portee + d + B + rpm + P
            if type_portee is None:
                raise ValueError("strict=True : type_portee doit être 'journal' ou 'maneton'.")
            d_req = _dig(rapport, "dimensions_requises", type_portee, "d_interieur_requis_m")
            B_req = _dig(rapport, "dimensions_requises", type_portee, "B_largeur_requise_m")
            if d_req is None or B_req is None:
                raise ValueError("strict=True : d_interieur_requis_m et B_largeur_requise_m doivent être connus pour la portée choisie.")
            if rpm is None:
                raise ValueError("strict=True : rpm requis.")
            if self.force_radiale_equivalente_N is None:
                raise ValueError("strict=True : force_radiale_equivalente_N requis (pas de charge 'inventée').")

        return rapport


if __name__ == "__main__":  # pragma: no cover
    from pprint import pprint

    # Exemple minimal : pas de dépendances => beaucoup d'inconnues (normal)
    r = RoulementAiguilleArbre(type_portee=None).analyser(strict=False)
    pprint(r)

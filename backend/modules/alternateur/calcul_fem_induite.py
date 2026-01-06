# backend/modules/alternateur/calcul_fem_induite.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


# =============================================================================
# Validation robuste
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 0) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return x


def _req_ratio_0_1(name: str, x: Any, *, strict_min: bool = True) -> float:
    v = _req_finite(name, x)
    if strict_min:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    if v > 1.0:
        raise ValueError(f"{name} doit être <= 1 (reçu: {v}).")
    return v


# =============================================================================
# Conversions utiles (mécanique/électrique)
# =============================================================================

def rpm_to_hz(rpm: float) -> float:
    rpm = _req_pos("rpm", rpm, strict=False)
    return float(rpm) / 60.0


def hz_to_rpm(hz: float) -> float:
    hz = _req_pos("hz", hz, strict=False)
    return float(hz) * 60.0


def omega_to_hz(omega_rad_s: float) -> float:
    omega_rad_s = _req_pos("omega_rad_s", omega_rad_s, strict=False)
    return float(omega_rad_s) / (2.0 * math.pi)


def hz_to_omega(hz: float) -> float:
    hz = _req_pos("hz", hz, strict=False)
    return float(hz) * (2.0 * math.pi)


# =============================================================================
# Forme d’onde / constante RMS
# =============================================================================
# IMPORTANT: on ne "devine" pas la forme d’onde.
#  - sinus RMS: 4.44
#  - carrée RMS: 4.00 (si flux/EMF carrée idéale)
#  - trapézoïdale: dépend (exiger un C fourni)
Waveform = Literal["sinus", "carree", "custom"]


def constante_rms_par_forme(onde: Waveform, *, constante_custom: Optional[float] = None) -> float:
    """
    Donne la constante C de la formule E = C * f * N * Phi * k_w
    selon une hypothèse explicite de forme d’onde.

    - sinus  : C = 4.44 (classique alternateur sinusoïdal, tension RMS)
    - carree : C = 4.00 (idéalisation; seulement si tu assumes explicitement cette forme)
    - custom : C = constante_custom (obligatoire)

    Aucun "choix implicite": si tu veux autre chose, tu passes custom.
    """
    if onde == "sinus":
        return 4.44
    if onde == "carree":
        return 4.00
    if onde == "custom":
        if constante_custom is None:
            raise ValueError("constante_custom est requise quand onde='custom'.")
        return _req_pos("constante_custom", constante_custom, strict=True)
    raise ValueError("onde doit être 'sinus', 'carree' ou 'custom'.")


# =============================================================================
# Calculs fondamentaux: E_phase RMS
# =============================================================================

def calcul_fem_induite(
    frequence_hz: float,
    nombre_spires_serie: int,
    flux_max_pole_wb: float,
    facteur_enroulement_kw: float,
    *,
    onde: Waveform = "sinus",
    constante_custom: Optional[float] = None,
    clamp_non_negative: bool = True,
) -> float:
    """
    FEM induite RMS par PHASE (E_ph).

    E_ph = C * f * N * Phi_max * k_w

    - frequence_hz: f (Hz) >= 0
    - nombre_spires_serie: N (entier) >= 0
    - flux_max_pole_wb: Phi_max (Wb) (peut être signé par convention)
    - facteur_enroulement_kw: k_w (si tu veux le borner: utilise _req_ratio_0_1 en amont)
    - onde/constante_custom: définition explicite de C (pas de supposition)

    clamp_non_negative=True -> retourne |E| (utile si flux signé).
    """
    f = _req_pos("frequence_hz", frequence_hz, strict=False)
    N = _req_int_ge("nombre_spires_serie", nombre_spires_serie, 0)
    phi = _req_finite("flux_max_pole_wb", flux_max_pole_wb)
    kw = _req_finite("facteur_enroulement_kw", facteur_enroulement_kw)
    C = constante_rms_par_forme(onde, constante_custom=constante_custom)

    E = C * f * float(N) * phi * kw
    return abs(E) if clamp_non_negative else float(E)


FluxModel = Literal["B*A", "abs(B)*A"]


def calcul_flux_pole(
    induction_gap_t: float,
    aire_pole_m2: float,
    *,
    flux_model: FluxModel = "B*A",
) -> float:
    """
    Phi ≈ B_g * A_p

    - flux_model = "B*A"      conserve le signe de B
    - flux_model = "abs(B)*A" force Phi >= 0

    Retour: flux (Wb)
    """
    B = _req_finite("induction_gap_t", induction_gap_t)
    A = _req_pos("aire_pole_m2", aire_pole_m2, strict=False)
    if flux_model == "abs(B)*A":
        return float(abs(B) * A)
    if flux_model == "B*A":
        return float(B * A)
    raise ValueError("flux_model doit être 'B*A' ou 'abs(B)*A'.")


def calcul_fem_induite_avec_induction(
    frequence_hz: float,
    nombre_spires_serie: int,
    induction_gap_t: float,
    aire_pole_m2: float,
    facteur_enroulement_kw: float,
    *,
    onde: Waveform = "sinus",
    constante_custom: Optional[float] = None,
    clamp_non_negative: bool = True,
    flux_model: FluxModel = "B*A",
) -> float:
    """
    FEM RMS par phase en utilisant B dans l'entrefer + aire de pôle.

    Phi = B*A
    E_ph = C*f*N*Phi*k_w
    """
    phi = calcul_flux_pole(induction_gap_t, aire_pole_m2, flux_model=flux_model)
    return calcul_fem_induite(
        frequence_hz=frequence_hz,
        nombre_spires_serie=nombre_spires_serie,
        flux_max_pole_wb=phi,
        facteur_enroulement_kw=facteur_enroulement_kw,
        onde=onde,
        constante_custom=constante_custom,
        clamp_non_negative=clamp_non_negative,
    )


# =============================================================================
# Dérivés: conversions phase/ligne et recherche de paramètres
# =============================================================================

Couplage = Literal["etoile", "triangle"]


def tension_ligne_depuis_phase(v_phase_rms: float, couplage: Couplage) -> float:
    """
    Convertit V_phase RMS -> V_ligne RMS selon le couplage.

    - étoile (Y): V_ligne = sqrt(3)*V_phase
    - triangle (Δ): V_ligne = V_phase
    """
    Vph = _req_pos("v_phase_rms", v_phase_rms, strict=False)
    if couplage == "etoile":
        return float(math.sqrt(3.0) * Vph)
    if couplage == "triangle":
        return float(Vph)
    raise ValueError("couplage doit être 'etoile' ou 'triangle'.")


def tension_phase_depuis_ligne(v_ligne_rms: float, couplage: Couplage) -> float:
    """
    Convertit V_ligne RMS -> V_phase RMS.
    """
    Vl = _req_pos("v_ligne_rms", v_ligne_rms, strict=False)
    if couplage == "etoile":
        return float(Vl / math.sqrt(3.0))
    if couplage == "triangle":
        return float(Vl)
    raise ValueError("couplage doit être 'etoile' ou 'triangle'.")


def calcul_frequence_depuis_rpm(
    rpm_mecanique: float,
    nb_paires_poles: int,
) -> float:
    """
    f = (rpm/60) * p

    - nb_paires_poles = p (entier >= 1)
    """
    rpm = _req_pos("rpm_mecanique", rpm_mecanique, strict=False)
    p = _req_int_ge("nb_paires_poles", nb_paires_poles, 1)
    return float((rpm / 60.0) * float(p))


def calcul_rpm_depuis_frequence(
    frequence_hz: float,
    nb_paires_poles: int,
) -> float:
    """
    rpm = (f/p)*60
    """
    f = _req_pos("frequence_hz", frequence_hz, strict=False)
    p = _req_int_ge("nb_paires_poles", nb_paires_poles, 1)
    return float((f / float(p)) * 60.0)


def calcul_spires_depuis_tension(
    v_phase_rms_cible: float,
    frequence_hz: float,
    flux_max_pole_wb: float,
    facteur_enroulement_kw: float,
    *,
    onde: Waveform = "sinus",
    constante_custom: Optional[float] = None,
    arrondi: Literal["floor", "ceil", "round"] = "ceil",
) -> int:
    """
    Inverse E = C*f*N*Phi*k_w -> N = E / (C*f*Phi*k_w)

    Retourne un entier (choix d'arrondi explicite).
    """
    E = _req_pos("v_phase_rms_cible", v_phase_rms_cible, strict=False)
    f = _req_pos("frequence_hz", frequence_hz, strict=True)  # strict: sinon division par 0
    phi = _req_finite("flux_max_pole_wb", flux_max_pole_wb)
    kw = _req_finite("facteur_enroulement_kw", facteur_enroulement_kw)
    C = constante_rms_par_forme(onde, constante_custom=constante_custom)

    denom = C * f * phi * kw
    if denom == 0.0:
        raise ValueError("Division par zéro: C*f*Phi*k_w vaut 0.")
    n_float = E / denom

    if arrondi == "floor":
        return int(math.floor(n_float))
    if arrondi == "ceil":
        return int(math.ceil(n_float))
    if arrondi == "round":
        return int(round(n_float))
    raise ValueError("arrondi doit être 'floor', 'ceil' ou 'round'.")


def calcul_flux_depuis_tension(
    v_phase_rms_cible: float,
    frequence_hz: float,
    nombre_spires_serie: int,
    facteur_enroulement_kw: float,
    *,
    onde: Waveform = "sinus",
    constante_custom: Optional[float] = None,
) -> float:
    """
    Inverse E = C*f*N*Phi*k_w -> Phi = E / (C*f*N*k_w)
    """
    E = _req_pos("v_phase_rms_cible", v_phase_rms_cible, strict=False)
    f = _req_pos("frequence_hz", frequence_hz, strict=True)
    N = _req_int_ge("nombre_spires_serie", nombre_spires_serie, 1)
    kw = _req_finite("facteur_enroulement_kw", facteur_enroulement_kw)
    C = constante_rms_par_forme(onde, constante_custom=constante_custom)

    denom = C * f * float(N) * kw
    if denom == 0.0:
        raise ValueError("Division par zéro: C*f*N*k_w vaut 0.")
    return float(E / denom)


def calcul_facteur_enroulement_depuis_tension(
    v_phase_rms_cible: float,
    frequence_hz: float,
    nombre_spires_serie: int,
    flux_max_pole_wb: float,
    *,
    onde: Waveform = "sinus",
    constante_custom: Optional[float] = None,
) -> float:
    """
    Inverse E = C*f*N*Phi*k_w -> k_w = E / (C*f*N*Phi)
    """
    E = _req_pos("v_phase_rms_cible", v_phase_rms_cible, strict=False)
    f = _req_pos("frequence_hz", frequence_hz, strict=True)
    N = _req_int_ge("nombre_spires_serie", nombre_spires_serie, 1)
    phi = _req_finite("flux_max_pole_wb", flux_max_pole_wb)
    C = constante_rms_par_forme(onde, constante_custom=constante_custom)

    denom = C * f * float(N) * phi
    if denom == 0.0:
        raise ValueError("Division par zéro: C*f*N*Phi vaut 0.")
    return float(E / denom)


# =============================================================================
# Rapport complet (calcule tout ce qui est calculable, sinon inconnues)
# =============================================================================

@dataclass(frozen=True)
class RapportFEM:
    """
    Produit un rapport calculé à partir d'un set minimal, sans inventer.

    Tu peux fournir soit:
      - frequence_hz
    soit:
      - rpm_mecanique + nb_paires_poles  -> f calculée

    Et soit:
      - flux_max_pole_wb
    soit:
      - induction_gap_t + aire_pole_m2 -> flux calculé

    Puis:
      - nombre_spires_serie
      - facteur_enroulement_kw

    Optionnel:
      - couplage (etoile/triangle) -> tensions ligne/phase
    """

    def generer(self, **kwargs: Any) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "entrees": dict(kwargs),
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes": [],
        }

        onde: Waveform = kwargs.get("onde", "sinus")
        constante_custom = kwargs.get("constante_custom", None)

        # 1) fréquence
        f: Optional[float] = None
        if "frequence_hz" in kwargs:
            f = _req_pos("frequence_hz", kwargs["frequence_hz"], strict=False)
        else:
            if "rpm_mecanique" in kwargs and "nb_paires_poles" in kwargs:
                f = calcul_frequence_depuis_rpm(
                    rpm_mecanique=_req_pos("rpm_mecanique", kwargs["rpm_mecanique"], strict=False),
                    nb_paires_poles=_req_int_ge("nb_paires_poles", kwargs["nb_paires_poles"], 1),
                )
            else:
                rep["inconnues"]["impossibles"].append(
                    {
                        "nom": "frequence_hz",
                        "raison": "Fournir frequence_hz, ou fournir (rpm_mecanique + nb_paires_poles).",
                    }
                )

        # 2) flux
        phi: Optional[float] = None
        if "flux_max_pole_wb" in kwargs:
            phi = _req_finite("flux_max_pole_wb", kwargs["flux_max_pole_wb"])
        else:
            if "induction_gap_t" in kwargs and "aire_pole_m2" in kwargs:
                phi = calcul_flux_pole(
                    induction_gap_t=_req_finite("induction_gap_t", kwargs["induction_gap_t"]),
                    aire_pole_m2=_req_pos("aire_pole_m2", kwargs["aire_pole_m2"], strict=False),
                    flux_model=kwargs.get("flux_model", "B*A"),
                )
            else:
                rep["inconnues"]["impossibles"].append(
                    {
                        "nom": "flux_max_pole_wb",
                        "raison": "Fournir flux_max_pole_wb, ou fournir (induction_gap_t + aire_pole_m2).",
                    }
                )

        # 3) N, k_w
        if "nombre_spires_serie" not in kwargs:
            rep["inconnues"]["impossibles"].append({"nom": "nombre_spires_serie", "raison": "Paramètre requis."})
            N = None
        else:
            N = _req_int_ge("nombre_spires_serie", kwargs["nombre_spires_serie"], 0)

        if "facteur_enroulement_kw" not in kwargs:
            rep["inconnues"]["impossibles"].append({"nom": "facteur_enroulement_kw", "raison": "Paramètre requis."})
            kw = None
        else:
            kw = _req_finite("facteur_enroulement_kw", kwargs["facteur_enroulement_kw"])

        # 4) calcul E_phase
        if f is not None and phi is not None and N is not None and kw is not None:
            E_ph = calcul_fem_induite(
                frequence_hz=f,
                nombre_spires_serie=N,
                flux_max_pole_wb=phi,
                facteur_enroulement_kw=kw,
                onde=onde,
                constante_custom=constante_custom,
                clamp_non_negative=kwargs.get("clamp_non_negative", True),
            )
            rep["resultats"]["E_phase_rms_V"] = float(E_ph)
            rep["resultats"]["frequence_hz"] = float(f)
            rep["resultats"]["flux_max_pole_wb"] = float(phi)
            rep["resultats"]["constante_C"] = float(constante_rms_par_forme(onde, constante_custom=constante_custom))
        else:
            rep["notes"].append("E_phase non calculable: paramètres manquants listés dans 'inconnues'.")

        # 5) couplage -> V ligne
        if "couplage" in kwargs:
            if "E_phase_rms_V" in rep["resultats"]:
                Vph = float(rep["resultats"]["E_phase_rms_V"])
                couplage: Couplage = kwargs["couplage"]
                rep["resultats"]["V_ligne_rms_V"] = float(tension_ligne_depuis_phase(Vph, couplage))
                rep["resultats"]["couplage"] = couplage
            else:
                rep["inconnues"]["partielles"].append(
                    {"nom": "V_ligne_rms_V", "raison": "Calculable si E_phase_rms_V est calculée."}
                )

        # 6) inverses utiles (si tension cible fournie)
        if "v_phase_rms_cible" in kwargs:
            if f is not None and phi is not None and kw is not None:
                rep["resultats"]["N_requis_ceil"] = int(
                    calcul_spires_depuis_tension(
                        v_phase_rms_cible=_req_pos("v_phase_rms_cible", kwargs["v_phase_rms_cible"], strict=False),
                        frequence_hz=f,
                        flux_max_pole_wb=phi,
                        facteur_enroulement_kw=kw,
                        onde=onde,
                        constante_custom=constante_custom,
                        arrondi="ceil",
                    )
                )
            else:
                rep["inconnues"]["partielles"].append(
                    {"nom": "N_requis_ceil", "raison": "Calculable si (frequence + flux + k_w) sont connus."}
                )

        # 7) dédup
        _dedup_inconnues(rep)
        return rep


if __name__ == "__main__":
    # Exemple minimal (aucune valeur "typique" imposée ici; tu dois tout fournir)
    r = RapportFEM().generer(
        # Option 1: fréquence directe
        frequence_hz=200.0,
        # Option 2 alternative: rpm_mecanique=6000, nb_paires_poles=2,

        # flux direct, ou via B/A:
        induction_gap_t=0.9,
        aire_pole_m2=1.2e-3,

        nombre_spires_serie=40,
        facteur_enroulement_kw=0.95,

        couplage="etoile",
        onde="sinus",
    )
    print(r)

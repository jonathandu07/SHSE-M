# backend\modules\architecture\calcul_cout_maintenance_archard.py
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.request import Request, urlopen


# =========================
# Utilitaires robustesse
# =========================

def _est_fini(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _exiger_fini(nom: str, x: float) -> float:
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _exiger_positif(nom: str, x: float, *, strict: bool = True) -> float:
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def _exiger_int_positif(nom: str, x: int, *, strict: bool = True) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{nom} doit être un entier (reçu: {x!r}).")
    ok = x > 0 if strict else x >= 0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def _median(vals: list[float]) -> float:
    if not vals:
        raise ValueError("Impossible de calculer une médiane sur une liste vide.")
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


# =========================
# Fonction existante (API inchangée)
# =========================

def calcul_cout_maintenance_estime(
    duree_usage_h: float,
    duree_vie_joint_base_h: float,
    charge_nominale_n: float,
    charge_actuelle_n: float,
    nb_joints_base: int,
    nb_joints_actuel: int,
    cout_inter_eur: float
) -> float:
    """
    Estime le coût de maintenance relatif à l'usure des joints selon le nombre de cylindres.

    Modèle empirique :
      Cost_total = N_inter * Cout_par_inter
      N_inter ~ T / L_seal
      L_seal = L0 * (W0/W)^beta
      Cout_par_inter = Cout_inter_base * (N_joints_actuel / N_joints_base)

    IMPORTANT :
    - API conservée : même signature, même type de retour (float).
    - cout_inter_eur est interprété comme un coût "base" (configuration de référence nb_joints_base).
    """
    beta_wear = 1.5  # exposant empirique (à calibrer)

    T = _exiger_positif("duree_usage_h", duree_usage_h, strict=False)
    L0 = _exiger_positif("duree_vie_joint_base_h", duree_vie_joint_base_h, strict=True)
    W0 = _exiger_positif("charge_nominale_n", charge_nominale_n, strict=True)
    W = _exiger_fini("charge_actuelle_n", charge_actuelle_n)
    nb_base = _exiger_int_positif("nb_joints_base", nb_joints_base, strict=True)
    nb_actuel = _exiger_int_positif("nb_joints_actuel", nb_joints_actuel, strict=False)
    cout_base = _exiger_positif("cout_inter_eur", cout_inter_eur, strict=False)

    # Comportement conservé : charge <= 0 -> coût nul
    if W <= 0.0:
        return 0.0

    ratio_charge = W0 / W
    duree_vie_estimee = L0 * (ratio_charge ** beta_wear)

    if duree_vie_estimee <= 0.0 or not math.isfinite(duree_vie_estimee):
        raise ValueError("Durée de vie estimée non valide (vérifier charges et paramètres).")

    nb_interventions = T / duree_vie_estimee

    facteur_joints = nb_actuel / nb_base
    cout_par_inter = cout_base * facteur_joints

    return nb_interventions * cout_par_inter


# =========================
# Scraping (OPTIONNEL) : prix joints + main d'oeuvre
# =========================

_PRIX_EUR_RE = re.compile(
    r"(?<!\d)"              # pas collé à un chiffre avant
    r"(\d{1,4}(?:[ \u00A0]?\d{3})*(?:[.,]\d{1,2})?)"  # 1 234,56 ou 1234.56
    r"\s*(?:€|EUR)\b",
    flags=re.IGNORECASE
)


def _normaliser_montant_eur(s: str) -> Optional[float]:
    """
    Convertit un montant texte européen en float:
    - gère espaces / NBSP, virgule décimale.
    """
    try:
        t = s.replace("\u00A0", " ").replace(" ", "")
        t = t.replace(",", ".")
        v = float(t)
        if not math.isfinite(v):
            return None
        return v
    except Exception:
        return None


def _telecharger_html(url: str, *, timeout_s: float = 6.0, user_agent: str = "Mozilla/5.0") -> str:
    """
    Télécharge une page HTML (scraping simple).
    - timeout court pour éviter de bloquer tes scripts.
    - user-agent configurable.
    """
    req = Request(url, headers={"User-Agent": user_agent, "Accept": "text/html,*/*"})
    with urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
        # Décodage "best effort"
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode(errors="ignore")


def _extraire_montants_eur(html: str) -> list[float]:
    """
    Extrait des montants en € d'une page HTML.
    Filtre ensuite les valeurs absurdes au moment de l'agrégation.
    """
    montants: list[float] = []
    for m in _PRIX_EUR_RE.finditer(html):
        v = _normaliser_montant_eur(m.group(1))
        if v is not None:
            montants.append(v)
    return montants


@dataclass(frozen=True)
class EstimationPrixWeb:
    prix_joint_unitaire_eur: float
    taux_horaire_mo_eur_h: float
    sources_utilisees: int


def estimer_prix_depuis_web(
    *,
    urls_prix_joints: Iterable[str],
    urls_main_oeuvre: Iterable[str],
    timeout_s: float = 6.0,
    # filtres plausibilité (évite de prendre livraison, promos aberrantes, etc.)
    plage_prix_joint_eur: tuple[float, float] = (0.10, 200.0),
    plage_mo_eur_h: tuple[float, float] = (30.0, 250.0),
    user_agent: str = "Mozilla/5.0",
) -> EstimationPrixWeb:
    """
    Scrape des pages pour estimer :
    - prix unitaire de joint (€/pièce)
    - taux horaire de main d'œuvre (€/h)

    IMPORTANT :
    - Ce scraping est volontairement générique (regex €). Les pages peuvent changer.
    - Utilise plusieurs URLs pour stabiliser (médiane).
    """
    prix_joints: list[float] = []
    mo_rates: list[float] = []
    sources_ok = 0

    # 1) Prix joints
    for url in urls_prix_joints:
        try:
            html = _telecharger_html(url, timeout_s=timeout_s, user_agent=user_agent)
            vals = _extraire_montants_eur(html)
            # filtre plage plausible
            vals = [v for v in vals if plage_prix_joint_eur[0] <= v <= plage_prix_joint_eur[1]]
            if vals:
                prix_joints.extend(vals)
                sources_ok += 1
        except Exception:
            # On n'échoue pas : on essaie les autres sources
            continue

    # 2) Main d'oeuvre
    for url in urls_main_oeuvre:
        try:
            html = _telecharger_html(url, timeout_s=timeout_s, user_agent=user_agent)
            vals = _extraire_montants_eur(html)
            vals = [v for v in vals if plage_mo_eur_h[0] <= v <= plage_mo_eur_h[1]]
            if vals:
                mo_rates.extend(vals)
                sources_ok += 1
        except Exception:
            continue

    if not prix_joints:
        raise ValueError("Scraping: aucun prix de joint exploitable trouvé (URLs/filtrage à ajuster).")
    if not mo_rates:
        raise ValueError("Scraping: aucun tarif main d'œuvre exploitable trouvé (URLs/filtrage à ajuster).")

    # Médiane = robuste aux outliers (livraison, packs, etc.)
    prix_joint = _median(prix_joints)
    taux_mo = _median(mo_rates)

    return EstimationPrixWeb(
        prix_joint_unitaire_eur=prix_joint,
        taux_horaire_mo_eur_h=taux_mo,
        sources_utilisees=sources_ok
    )


# =========================
# Cache local (évite de re-scraper à chaque run)
# =========================

def _charger_cache_json(path: Path) -> Optional[dict]:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sauver_cache_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def estimer_prix_depuis_web_avec_cache(
    *,
    cache_path: str = "backend/.cache/prix_maintenance.json",
    cache_ttl_h: float = 168.0,  # 7 jours
    urls_prix_joints: Iterable[str],
    urls_main_oeuvre: Iterable[str],
    timeout_s: float = 6.0,
    user_agent: str = "Mozilla/5.0",
) -> EstimationPrixWeb:
    """
    Même estimation que estimer_prix_depuis_web(), mais avec cache JSON.
    """
    ttl_s = _exiger_positif("cache_ttl_h", cache_ttl_h, strict=True) * 3600.0
    p = Path(cache_path)

    cache = _charger_cache_json(p)
    now = time.time()

    if cache and isinstance(cache, dict):
        ts = cache.get("timestamp")
        if isinstance(ts, (int, float)) and (now - float(ts)) <= ttl_s:
            pj = cache.get("prix_joint_unitaire_eur")
            mo = cache.get("taux_horaire_mo_eur_h")
            if _est_fini(pj) and _est_fini(mo):
                return EstimationPrixWeb(
                    prix_joint_unitaire_eur=float(pj),
                    taux_horaire_mo_eur_h=float(mo),
                    sources_utilisees=int(cache.get("sources_utilisees", 0)),
                )

    est = estimer_prix_depuis_web(
        urls_prix_joints=urls_prix_joints,
        urls_main_oeuvre=urls_main_oeuvre,
        timeout_s=timeout_s,
        user_agent=user_agent,
    )

    _sauver_cache_json(p, {
        "timestamp": now,
        "prix_joint_unitaire_eur": est.prix_joint_unitaire_eur,
        "taux_horaire_mo_eur_h": est.taux_horaire_mo_eur_h,
        "sources_utilisees": est.sources_utilisees,
    })
    return est


# =========================
# Wrapper "auto prix" (OPTIONNEL) : ne casse pas l’existant
# =========================

def calcul_cout_maintenance_estime_auto_prix(
    duree_usage_h: float,
    duree_vie_joint_base_h: float,
    charge_nominale_n: float,
    charge_actuelle_n: float,
    nb_joints_base: int,
    nb_joints_actuel: int,
    cout_inter_eur: float,
    *,
    # Paramètres pour décomposer/fiabiliser le "cout_inter_eur" via le web
    activer_scraping: bool = True,
    urls_prix_joints: Optional[list[str]] = None,
    urls_main_oeuvre: Optional[list[str]] = None,
    cache_path: str = "backend/.cache/prix_maintenance.json",
    cache_ttl_h: float = 168.0,
    timeout_s: float = 6.0,
    # Hypothèses intervention (à calibrer)
    temps_intervention_h: float = 1.0,
    cout_arret_eur: float = 0.0,
    cout_consommables_eur: float = 0.0,
    # Si scraping échoue : strict=True -> erreur ; strict=False -> fallback sur cout_inter_eur fourni
    strict_scraping: bool = False,
) -> float:
    """
    Calcule le coût de maintenance comme la fonction de base, mais peut (optionnellement)
    ESTIMER un cout_inter_eur "réaliste" à partir :
      - prix des joints (€/pièce) scrapés
      - taux horaire MO (€/h) scrapé
      - temps d'intervention + arrêt + consommables

    IMPORTANT (compatibilité modèle existant) :
    - On construit un coût d'intervention "BASE" correspondant à nb_joints_base.
      Ensuite calcul_cout_maintenance_estime applique son scaling (nb_joints_actuel/nb_joints_base).
    """
    # Valeurs par défaut (exemples) : à adapter à ton contexte / tes joints exacts.
    # Tu peux remplacer/étendre ces listes sans toucher au calcul.
    if urls_prix_joints is None:
        urls_prix_joints = [
            # prix joints toriques Viton/FPM
            "https://www.fishoponline.com/1220-joints-toriques-fpm-viton",
            "https://www.lebonroulement.com/316010265-joint-spi-bague-d-etancheite?p=71",
        ]
    if urls_main_oeuvre is None:
        urls_main_oeuvre = [
            # articles donnant des fourchettes €/h
            "https://location.carrefour.fr/bien-louer/prix-main-d-oeuvre-garage",
            "https://www.fiches-auto.fr/articles-auto/entretien-automobile/s-470-tarifs-main-d-oeuvre.php",
        ]

    # Validation des paramètres d'intervention
    t_inter = _exiger_positif("temps_intervention_h", temps_intervention_h, strict=False)
    c_arret = _exiger_positif("cout_arret_eur", cout_arret_eur, strict=False)
    c_cons = _exiger_positif("cout_consommables_eur", cout_consommables_eur, strict=False)

    cout_inter_base = cout_inter_eur  # fallback par défaut

    if activer_scraping:
        try:
            est = estimer_prix_depuis_web_avec_cache(
                cache_path=cache_path,
                cache_ttl_h=cache_ttl_h,
                urls_prix_joints=urls_prix_joints,
                urls_main_oeuvre=urls_main_oeuvre,
                timeout_s=timeout_s,
            )

            # Coût pièces BASE (configuration de référence)
            nb_base = _exiger_int_positif("nb_joints_base", nb_joints_base, strict=True)
            cout_pieces_base = est.prix_joint_unitaire_eur * nb_base

            # Coût main d'œuvre (hypothèse simple)
            cout_mo = est.taux_horaire_mo_eur_h * t_inter

            # Coût intervention base (pièces + MO + arrêt + consommables)
            cout_inter_base = cout_pieces_base + cout_mo + c_arret + c_cons

        except Exception as e:
            if strict_scraping:
                raise
            # sinon, on retombe sur cout_inter_eur fourni (ne casse pas l’usage)
            cout_inter_base = cout_inter_eur

    # On appelle le calcul "canon" (API inchangée) avec un cout_inter_eur base
    return calcul_cout_maintenance_estime(
        duree_usage_h=duree_usage_h,
        duree_vie_joint_base_h=duree_vie_joint_base_h,
        charge_nominale_n=charge_nominale_n,
        charge_actuelle_n=charge_actuelle_n,
        nb_joints_base=nb_joints_base,
        nb_joints_actuel=nb_joints_actuel,
        cout_inter_eur=cout_inter_base,
    )

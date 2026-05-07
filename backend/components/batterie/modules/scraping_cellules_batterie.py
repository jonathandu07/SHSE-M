# backend\modules\batterie\scraping_cellules_batterie.py
from __future__ import annotations

"""
Module de scraping / normalisation de cellules commerciales pour affiner le
pré-dimensionnement batterie avec des cellules réellement achetables.

Objectifs :
- récupérer des pages produit de vendeurs publics (ici surtout NKON) ;
- récupérer les fiches techniques PDF ;
- extraire uniquement des valeurs publiées ou déductibles directement ;
- produire un catalogue structuré de cellules candidates ;
- pré-dimensionner un pack à partir de cellules achetables ;
- préparer les données pour `dimensionner_pack_cellules.py` sans inventer.

Philosophie stricte :
- pas de crawling agressif ; uniquement des URLs explicites ;
- pas de constantes métier cachées ;
- pas de courbes OCV(SOC,T) inventées ;
- si une donnée manque, elle reste `None` et est signalée.

Dépendances optionnelles :
- requests
- beautifulsoup4
- pypdf

Ce module reste volontairement robuste : si une dépendance n'est pas disponible,
il lève une erreur claire au moment de l'usage concerné.
"""

from dataclasses import dataclass, field, asdict
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import json
import math
import re
import time
from urllib.parse import urljoin


# =============================================================================
# Imports optionnels
# =============================================================================

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore


# =============================================================================
# Validation / utilitaires
# =============================================================================


def _est_fini(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))



def _exiger_fini(nom: str, x: Any) -> float:
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)



def _exiger_positif(nom: str, x: Any, *, strict: bool = True) -> float:
    v = _exiger_fini(nom, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {v}).")
    return v



def _exiger_ratio_0_1(nom: str, x: Any, *, strict_min: bool = False) -> float:
    v = _exiger_fini(nom, x)
    ok = (0.0 < v <= 1.0) if strict_min else (0.0 <= v <= 1.0)
    if not ok:
        borne = "0 < x <= 1" if strict_min else "0 <= x <= 1"
        raise ValueError(f"{nom} doit vérifier {borne} (reçu: {v}).")
    return v



def _ceil_div(a: float, b: float) -> int:
    a = _exiger_positif("a", a, strict=False)
    b = _exiger_positif("b", b, strict=True)
    if a == 0.0:
        return 0
    return int(math.ceil(a / b))



def _coalesce(*vals: Optional[float]) -> Optional[float]:
    for v in vals:
        if v is not None:
            return v
    return None



def _norm_text(txt: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", txt.replace("\xa0", " ")).strip()



def _find_first_float(patterns: Sequence[str], text: str, *, flags: int = re.IGNORECASE) -> Optional[float]:
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            g = m.group(1).replace(",", ".")
            try:
                return float(g)
            except Exception:
                continue
    return None



def _find_first_int(patterns: Sequence[str], text: str, *, flags: int = re.IGNORECASE) -> Optional[int]:
    v = _find_first_float(patterns, text, flags=flags)
    if v is None:
        return None
    return int(round(v))



def _safe_append_warning(warnings: List[str], msg: str) -> None:
    if msg not in warnings:
        warnings.append(msg)


# =============================================================================
# Modèles de données
# =============================================================================


@dataclass(frozen=True)
class SeedSource:
    reference: str
    vendor: str
    product_url: str
    html_parser: str
    datasheet_url: Optional[str] = None
    pdf_parser: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class OffreCommerciale:
    vendor: str
    product_url: str
    status: Optional[str] = None
    price_value: Optional[float] = None
    currency: Optional[str] = None
    title: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    raw_fields: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class SpecCellulePartielle:
    reference: str
    brand: Optional[str] = None
    model: Optional[str] = None
    chemistry: Optional[str] = None
    format_cellule: Optional[str] = None

    capacite_typ_ah: Optional[float] = None
    capacite_min_ah: Optional[float] = None
    energie_typ_wh: Optional[float] = None
    energie_min_wh: Optional[float] = None

    tension_nominale_v: Optional[float] = None
    tension_charge_max_v: Optional[float] = None
    tension_decharge_min_v: Optional[float] = None
    tension_decharge_min_basse_temp_v: Optional[float] = None

    courant_decharge_max_a: Optional[float] = None
    courant_charge_standard_a: Optional[float] = None
    courant_charge_max_a: Optional[float] = None

    resistance_ac_ohm: Optional[float] = None
    resistance_dc_ohm: Optional[float] = None
    soc_mesure_resistance_ac: Optional[float] = None
    soc_mesure_resistance_dc: Optional[float] = None

    poids_kg: Optional[float] = None
    diametre_mm: Optional[float] = None
    hauteur_mm: Optional[float] = None
    largeur_mm: Optional[float] = None
    epaisseur_mm: Optional[float] = None

    temperature_charge_min_c: Optional[float] = None
    temperature_charge_max_c: Optional[float] = None
    temperature_decharge_min_c: Optional[float] = None
    temperature_decharge_max_c: Optional[float] = None

    cycle_life_80pct: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    source_urls: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_source(self, url: Optional[str]) -> None:
        if url and url not in self.source_urls:
            self.source_urls.append(url)

    @property
    def energie_typ_kwh(self) -> Optional[float]:
        if self.energie_typ_wh is not None:
            return self.energie_typ_wh / 1000.0
        if self.capacite_typ_ah is not None and self.tension_nominale_v is not None:
            return (self.capacite_typ_ah * self.tension_nominale_v) / 1000.0
        return None

    @property
    def energie_specifique_wh_kg(self) -> Optional[float]:
        if self.energie_typ_wh is None or self.poids_kg is None or self.poids_kg <= 0:
            return None
        return self.energie_typ_wh / self.poids_kg

    @property
    def puissance_continue_estimee_w(self) -> Optional[float]:
        if self.courant_decharge_max_a is None or self.tension_nominale_v is None:
            return None
        return self.courant_decharge_max_a * self.tension_nominale_v


@dataclass
class CelluleCommerciale:
    seed: SeedSource
    offre: Optional[OffreCommerciale]
    specs: SpecCellulePartielle


@dataclass
class PreDimensionnementPack:
    reference: str
    vendor: str
    product_url: str
    tension_pack_nominale_v: float
    nb_series: int
    nb_parallele_energie: int
    nb_parallele_puissance_continue: Optional[int]
    nb_parallele_puissance_pic: Optional[int]
    nb_parallele_retenu: int
    nb_cellules_total: int
    energie_pack_kwh: float
    capacite_pack_ah: float
    courant_pack_continu_a: Optional[float]
    courant_pack_pic_a: Optional[float]
    courant_cellule_continu_a: Optional[float]
    courant_cellule_pic_a: Optional[float]
    masse_cellules_kg: Optional[float]
    volume_cellules_m3: Optional[float]
    avertissements: List[str] = field(default_factory=list)


# =============================================================================
# Dépendances externes : vérification
# =============================================================================


def _require_requests() -> None:
    if requests is None:  # pragma: no cover
        raise ImportError("Le module 'requests' est requis pour le scraping HTTP.")



def _require_bs4() -> None:
    if BeautifulSoup is None:  # pragma: no cover
        raise ImportError("Le module 'beautifulsoup4' est requis pour parser le HTML.")



def _require_pypdf() -> None:
    if PdfReader is None:  # pragma: no cover
        raise ImportError("Le module 'pypdf' est requis pour parser les fiches PDF.")


# =============================================================================
# Téléchargement / parsing bas niveau
# =============================================================================


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}



def telecharger_texte_html(url: str, *, timeout_s: float = 20.0, headers: Optional[Dict[str, str]] = None) -> str:
    _require_requests()
    resp = requests.get(url, timeout=timeout_s, headers=headers or DEFAULT_HEADERS)
    resp.raise_for_status()
    return resp.text



def telecharger_pdf_texte(url: str, *, timeout_s: float = 30.0, headers: Optional[Dict[str, str]] = None) -> str:
    _require_requests()
    _require_pypdf()
    resp = requests.get(url, timeout=timeout_s, headers=headers or DEFAULT_HEADERS)
    resp.raise_for_status()
    reader = PdfReader(BytesIO(resp.content))
    textes: List[str] = []
    for page in reader.pages:
        try:
            textes.append(page.extract_text() or "")
        except Exception:
            textes.append("")
    return "\n".join(textes)



def _html_to_text(html: str) -> str:
    _require_bs4()
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    txt = soup.get_text("\n")
    lines = [_norm_text(line) for line in txt.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


# =============================================================================
# Parsing HTML : NKON
# =============================================================================



def parser_html_nkon(html: str, product_url: str) -> OffreCommerciale:
    txt = _html_to_text(html)
    offre = OffreCommerciale(vendor="NKON", product_url=product_url)

    m_title = re.search(r"#?\s*([A-Za-z0-9 .+\-]+(?:P45B|P42A|50S|LF280K)[^\n]*)", txt, re.IGNORECASE)
    if m_title:
        offre.title = _norm_text(m_title.group(1))

    # Statut
    if re.search(r"\bOut of stock\b", txt, re.IGNORECASE):
        offre.status = "out_of_stock"
    elif re.search(r"\bIn stock\b", txt, re.IGNORECASE):
        offre.status = "in_stock"
    elif re.search(r"\bAvailable to order\b", txt, re.IGNORECASE):
        offre.status = "available_to_order"

    # Prix HT principal
    m_price = re.search(r"€\s*([0-9]+(?:[\.,][0-9]+)?)\s*Excl\. Tax", txt, re.IGNORECASE)
    if m_price:
        offre.price_value = float(m_price.group(1).replace(",", "."))
        offre.currency = "EUR"

    # Champs produit
    patterns = {
        "brand": [r"\bBrand\s+([A-Za-z0-9\-+ ]+)"],
        "model": [r"\bModel\s+([A-Za-z0-9\-+_.]+)"],
        "weight_g": [r"Weight\s*-\s*g\s+([0-9]+(?:[\.,][0-9]+)?)", r"Weight:\s*([0-9]+(?:[\.,][0-9]+)?)g"],
        "voltage_v": [r"\bVoltage\s+([0-9]+(?:[\.,][0-9]+)?)V", r"Rated Voltage\s*([0-9]+(?:[\.,][0-9]+)?)V"],
        "capacity_typ_mAh": [r"Typ\. capacity - mAh\s+([0-9]+(?:[\.,][0-9]+)?)", r"Capacity:\s*([0-9]+(?:[\.,][0-9]+)?)mAh"],
        "capacity_min_mAh": [r"Min\. capacity - mAh\s+([0-9]+(?:[\.,][0-9]+)?)"],
        "capacity_ah": [r"Capacity - Ah\s+([0-9]+(?:[\.,][0-9]+)?)", r"Capacity:\s*([0-9]+(?:[\.,][0-9]+)?)\s*Ah"],
        "current_discharge_a": [r"Discharge current - A\s+([0-9]+(?:[\.,][0-9]+)?)", r"Maximum discharge value:\s*([0-9]+(?:[\.,][0-9]+)?)A", r"max discharge current:\s*([0-9]+(?:[\.,][0-9]+)?)A"],
        "height_mm": [r"Height - mm\s+([0-9]+(?:[\.,][0-9]+)?)", r"Height:\s*([0-9]+(?:[\.,][0-9]+)?)mm"],
        "diameter_mm": [r"Diameter in mm\s+([0-9]+(?:[\.,][0-9]+)?)", r"Diameter:\s*([0-9]+(?:[\.,][0-9]+)?)mm"],
        "width_mm": [r"Width - mm\s+([0-9]+(?:[\.,][0-9]+)?)"],
        "thickness_mm": [r"Thickness - mm\s+([0-9]+(?:[\.,][0-9]+)?)"],
        "charge_cutoff_v": [r"Charging cycle termination voltage\s*([0-9]+(?:[\.,][0-9]+)?)V"],
        "discharge_cutoff_v": [r"Do not discharge deeper than\s*([0-9]+(?:[\.,][0-9]+)?)V"],
        "chemistry": [r"Battery chemistry\s+([A-Za-z0-9\-+]+)", r"Chemistry:\s*([A-Za-z0-9\-+]+)"],
        "size": [r"\bSize\s+([0-9]{4,5})"],
    }

    for key, pats in patterns.items():
        val = _find_first_float(pats, txt) if key not in {"brand", "model", "chemistry", "size"} else None
        if key in {"brand", "model", "chemistry", "size"}:
            for pat in pats:
                m = re.search(pat, txt, re.IGNORECASE)
                if m:
                    offre.raw_fields[key] = _norm_text(m.group(1))
                    break
        elif val is not None:
            offre.raw_fields[key] = val

    offre.brand = _norm_text(str(offre.raw_fields.get("brand"))) if offre.raw_fields.get("brand") is not None else None
    offre.model = _norm_text(str(offre.raw_fields.get("model"))) if offre.raw_fields.get("model") is not None else None
    return offre


# =============================================================================
# Parsing PDF : Molicel P45B / P42A
# =============================================================================



def _parse_molicel_pdf_common(text: str, reference: str) -> SpecCellulePartielle:
    txt = _norm_text(text).replace("\n", " ")
    spec = SpecCellulePartielle(reference=reference)

    spec.capacite_typ_ah = (_find_first_float([r"Typical\s*([0-9]+(?:\.[0-9]+)?)\s*mAh"], txt) or 0.0) / 1000.0 or None
    spec.capacite_min_ah = (_find_first_float([r"Minimum\s*([0-9]+(?:\.[0-9]+)?)\s*mAh"], txt) or 0.0) / 1000.0 or None
    spec.energie_typ_wh = _find_first_float([r"Typical\s*[0-9]+(?:\.[0-9]+)?\s*mAh\s*([0-9]+(?:\.[0-9]+)?)\s*Wh"], txt)
    spec.energie_min_wh = _find_first_float([r"Minimum\s*[0-9]+(?:\.[0-9]+)?\s*mAh\s*([0-9]+(?:\.[0-9]+)?)\s*Wh"], txt)

    spec.tension_nominale_v = _find_first_float([r"Nominal\s*([0-9]+(?:\.[0-9]+)?)\s*V"], txt)
    spec.tension_charge_max_v = _find_first_float([r"Charge\s*([0-9]+(?:\.[0-9]+)?)\s*V"], txt)
    spec.tension_decharge_min_v = _find_first_float([r"Discharge\s*([0-9]+(?:\.[0-9]+)?)\s*V"], txt)

    spec.courant_charge_standard_a = _find_first_float([r"Charge Current\s*Standard\s*([0-9]+(?:\.[0-9]+)?)\s*A"], txt)
    spec.courant_charge_max_a = _find_first_float([r"Maximum\s*([0-9]+(?:\.[0-9]+)?)\s*A"], txt)
    spec.courant_decharge_max_a = _find_first_float([r"Discharge Current\s*Continuous\s*([0-9]+(?:\.[0-9]+)?)\s*A"], txt)

    ac_mohm = _find_first_float([r"AC\s*(?:\([^)]+\))?\s*([0-9]+(?:\.[0-9]+)?)\s*mΩ", r"AC\s*(?:\([^)]+\))?\s*([0-9]+(?:\.[0-9]+)?)\s*m\u03a9"], txt)
    dc_mohm = _find_first_float([r"DC\s*(?:\([^)]+\))?\s*([0-9]+(?:\.[0-9]+)?)\s*mΩ", r"DC\s*(?:\([^)]+\))?\s*([0-9]+(?:\.[0-9]+)?)\s*m\u03a9"], txt)
    spec.resistance_ac_ohm = None if ac_mohm is None else ac_mohm / 1000.0
    spec.resistance_dc_ohm = None if dc_mohm is None else dc_mohm / 1000.0

    soc_ac = _find_first_float([r"AC\s*\(([0-9]+)%SOC\)"], txt)
    soc_dc = _find_first_float([r"DC\s*\(([0-9]+)%SOC\)"], txt)
    spec.soc_mesure_resistance_ac = None if soc_ac is None else soc_ac / 100.0
    spec.soc_mesure_resistance_dc = None if soc_dc is None else soc_dc / 100.0

    spec.temperature_charge_min_c = _find_first_float([r"Temperature\s*Charge\s*(-?[0-9]+)°C"], txt)
    spec.temperature_charge_max_c = _find_first_float([r"Temperature\s*Charge\s*-?[0-9]+°C\s*to\s*(-?[0-9]+)°C"], txt)
    spec.temperature_decharge_min_c = _find_first_float([r"Discharge\s*(-?[0-9]+)°C\s*to\s*-?[0-9]+°C"], txt)
    spec.temperature_decharge_max_c = _find_first_float([r"Discharge\s*-?[0-9]+°C\s*to\s*(-?[0-9]+)°C"], txt)

    spec.diametre_mm = _find_first_float([r"Diameter\s*([0-9]+(?:\.[0-9]+)?)\s*mm"], txt)
    spec.hauteur_mm = _find_first_float([r"Height\s*([0-9]+(?:\.[0-9]+)?)\s*mm"], txt)
    poids_g = _find_first_float([r"Weight\s*([0-9]+(?:\.[0-9]+)?)\s*g"], txt)
    spec.poids_kg = None if poids_g is None else poids_g / 1000.0

    spec.chemistry = "Li-ion"
    spec.format_cellule = "21700"
    spec.brand = "Molicel"
    spec.model = reference
    return spec



def parser_pdf_molicel_p45b(text: str, url: str) -> SpecCellulePartielle:
    spec = _parse_molicel_pdf_common(text, "INR21700-P45B")
    spec.add_source(url)
    return spec



def parser_pdf_molicel_p42a(text: str, url: str) -> SpecCellulePartielle:
    spec = _parse_molicel_pdf_common(text, "INR21700-P42A")
    spec.add_source(url)
    return spec


# =============================================================================
# Parsing PDF : Samsung 50S (miroir PDF)
# =============================================================================



def parser_pdf_samsung_50s(text: str, url: str) -> SpecCellulePartielle:
    txt = text.replace("\xa0", " ")
    spec = SpecCellulePartielle(reference="INR21700-50S")
    spec.add_source(url)

    # Le PDF miroir disponible publiquement expose surtout : capacité nominale mini,
    # impédance initiale AC et table température/capacité.
    cap_min_mAh = _find_first_float([r"Rated discharge capacity\s*[≥>=]+\s*([0-9]+(?:\.[0-9]+)?)mAh"], txt)
    spec.capacite_min_ah = None if cap_min_mAh is None else cap_min_mAh / 1000.0

    imp_mohm = _find_first_float([r"Initial internal impedance\s*[≤<=]+\s*([0-9]+(?:\.[0-9]+)?)m[ΩΩ]"], txt)
    spec.resistance_ac_ohm = None if imp_mohm is None else imp_mohm / 1000.0
    # Le PDF ne donne pas ici de DCIR explicite exploitable sur le texte extrait.

    spec.soc_mesure_resistance_ac = None  # non explicitée dans l'extrait accessible

    # Températures de capacité relatives à 10A
    table = re.search(
        r"Discharge temperature\s*-20℃\s*-10℃\s*0℃\s*23℃\s*60℃\s*([0-9]+)%\s*([0-9]+)%\s*([0-9]+)%\s*([0-9]+)%\s*([0-9]+)%",
        txt,
        re.IGNORECASE,
    )
    if table:
        spec.extra["capacity_relative_vs_temp_at_10A"] = {
            "-20C": int(table.group(1)) / 100.0,
            "-10C": int(table.group(2)) / 100.0,
            "0C": int(table.group(3)) / 100.0,
            "23C": int(table.group(4)) / 100.0,
            "60C": int(table.group(5)) / 100.0,
        }

    spec.brand = "Samsung"
    spec.model = "INR21700-50S"
    spec.chemistry = "Li-ion"
    spec.format_cellule = "21700"
    return spec


# =============================================================================
# Parsing PDF : EVE LF280K
# =============================================================================



def parser_pdf_eve_lf280k(text: str, url: str) -> SpecCellulePartielle:
    txt = text.replace("\xa0", " ")
    spec = SpecCellulePartielle(reference="LF280K")
    spec.add_source(url)

    cap_ah = _find_first_float([r"Min\. Capacity\s*([0-9]+(?:\.[0-9]+)?)Ah"], txt)
    spec.capacite_min_ah = cap_ah
    # Aucune capacité typique universelle dans la spec officielle utilisée ici.

    spec.energie_min_wh = _find_first_float([r"Min\. Energy\s*([0-9]+(?:\.[0-9]+)?)Wh"], txt)
    spec.tension_nominale_v = _find_first_float([r"Nominal Voltage\s*([0-9]+(?:\.[0-9]+)?)V"], txt)
    spec.tension_charge_max_v = _find_first_float([r"Charging Cut-off Voltage\s*(?:Umax)?\s*([0-9]+(?:\.[0-9]+)?)V"], txt)
    spec.tension_decharge_min_v = _find_first_float([r"Discharging Cut-off Voltage\s*(?:Umin)?\s*([0-9]+(?:\.[0-9]+)?)V\s*T\s*>\s*0"], txt)
    spec.tension_decharge_min_basse_temp_v = _find_first_float([r"([0-9]+(?:\.[0-9]+)?)V\s*T\s*≤\s*0"], txt)

    ir_mohm = _find_first_float([r"Initial IR\s*[≤<=]\s*([0-9]+(?:\.[0-9]+)?)mΩ", r"Initial IR\s*[≤<=]\s*([0-9]+(?:\.[0-9]+)?)mΩ"], txt)
    spec.resistance_ac_ohm = None if ir_mohm is None else ir_mohm / 1000.0
    spec.soc_mesure_resistance_ac = 0.40 if ir_mohm is not None else None

    poids_g = _find_first_float([r"Weight\s*([0-9]+(?:\.[0-9]+)?)g"], txt)
    spec.poids_kg = None if poids_g is None else poids_g / 1000.0

    spec.temperature_charge_min_c = _find_first_float([r"Charging Temperature\s*([0-9]+)~[0-9]+℃"], txt)
    spec.temperature_charge_max_c = _find_first_float([r"Charging Temperature\s*[0-9]+~([0-9]+)℃"], txt)
    spec.temperature_decharge_min_c = _find_first_float([r"Discharging Temperature\s*(-?[0-9]+)~[0-9]+℃"], txt)
    spec.temperature_decharge_max_c = _find_first_float([r"Discharging Temperature\s*-?[0-9]+~([0-9]+)℃"], txt)

    spec.cycle_life_80pct = _find_first_float([r"([0-9]+)\s*Cycles"], txt)

    # 0.5P = 448W et nominal 3.2V => courant standard purement déduit.
    standard_power_w = _find_first_float([r"Standard Charging Power\s*([0-9]+(?:\.[0-9]+)?)W"], txt)
    if standard_power_w is not None and spec.tension_nominale_v is not None and spec.tension_nominale_v > 0:
        spec.courant_charge_standard_a = standard_power_w / spec.tension_nominale_v

    spec.brand = "EVE"
    spec.model = "LF280K"
    spec.chemistry = "LiFePO4"
    spec.format_cellule = "prismatic"
    return spec


# =============================================================================
# Fusion : offre + fiche technique
# =============================================================================



def fusionner_offre_et_specs(seed: SeedSource, offre: Optional[OffreCommerciale], pdf_specs: Optional[SpecCellulePartielle]) -> CelluleCommerciale:
    ref = seed.reference
    spec = SpecCellulePartielle(reference=ref)

    if pdf_specs is not None:
        spec = pdf_specs

    if offre is not None:
        spec.add_source(offre.product_url)
        if offre.brand and spec.brand is None:
            spec.brand = offre.brand
        if offre.model and spec.model is None:
            spec.model = offre.model

        rf = offre.raw_fields
        if spec.chemistry is None and isinstance(rf.get("chemistry"), str):
            spec.chemistry = rf["chemistry"]
        if spec.format_cellule is None and isinstance(rf.get("size"), str):
            spec.format_cellule = rf["size"]

        if spec.capacite_typ_ah is None:
            if rf.get("capacity_typ_mAh") is not None:
                spec.capacite_typ_ah = float(rf["capacity_typ_mAh"]) / 1000.0
            elif rf.get("capacity_ah") is not None:
                spec.capacite_typ_ah = float(rf["capacity_ah"])

        if spec.capacite_min_ah is None and rf.get("capacity_min_mAh") is not None:
            spec.capacite_min_ah = float(rf["capacity_min_mAh"]) / 1000.0

        if spec.tension_nominale_v is None and rf.get("voltage_v") is not None:
            spec.tension_nominale_v = float(rf["voltage_v"])
        if spec.tension_charge_max_v is None and rf.get("charge_cutoff_v") is not None:
            spec.tension_charge_max_v = float(rf["charge_cutoff_v"])
        if spec.tension_decharge_min_v is None and rf.get("discharge_cutoff_v") is not None:
            spec.tension_decharge_min_v = float(rf["discharge_cutoff_v"])
        if spec.courant_decharge_max_a is None and rf.get("current_discharge_a") is not None:
            spec.courant_decharge_max_a = float(rf["current_discharge_a"])

        if spec.poids_kg is None and rf.get("weight_g") is not None:
            spec.poids_kg = float(rf["weight_g"]) / 1000.0
        if spec.diametre_mm is None and rf.get("diameter_mm") is not None:
            spec.diametre_mm = float(rf["diameter_mm"])
        if spec.hauteur_mm is None and rf.get("height_mm") is not None:
            spec.hauteur_mm = float(rf["height_mm"])
        if spec.largeur_mm is None and rf.get("width_mm") is not None:
            spec.largeur_mm = float(rf["width_mm"])
        if spec.epaisseur_mm is None and rf.get("thickness_mm") is not None:
            spec.epaisseur_mm = float(rf["thickness_mm"])

    if spec.capacite_typ_ah is None and spec.capacite_min_ah is not None:
        _safe_append_warning(spec.warnings, "Capacité typique absente ; seule la capacité minimale est certaine.")
    if spec.resistance_ac_ohm is None and spec.resistance_dc_ohm is None:
        _safe_append_warning(spec.warnings, "Résistance interne non extraite automatiquement.")
    if spec.tension_charge_max_v is None:
        _safe_append_warning(spec.warnings, "Tension de charge max absente.")
    if spec.tension_decharge_min_v is None:
        _safe_append_warning(spec.warnings, "Tension de coupure décharge absente.")

    return CelluleCommerciale(seed=seed, offre=offre, specs=spec)


# =============================================================================
# Catalogue courant basé sur des URLs explicites
# =============================================================================


CATALOGUE_SEEDS: Tuple[SeedSource, ...] = (
    SeedSource(
        reference="INR21700-P45B",
        vendor="NKON",
        product_url="https://www.nkon.nl/en/molicel-inr21700-p45b-4500mah-45a.html",
        html_parser="nkon",
        datasheet_url="https://www.molicel.com/wp-content/uploads/INR21700P45B_1.2_Product-Data-Sheet-of-INR-21700-P45B-80109.pdf",
        pdf_parser="molicel_p45b",
        notes="Retailer EU + fiche Molicel officielle.",
    ),
    SeedSource(
        reference="INR21700-P42A",
        vendor="NKON",
        product_url="https://www.nkon.nl/en/molicel-21700a-4200mah-30a.html",
        html_parser="nkon",
        datasheet_url="https://www.molicel.com/wp-content/uploads/INR21700P42A-V4-80092.pdf",
        pdf_parser="molicel_p42a",
        notes="Retailer EU + fiche Molicel officielle.",
    ),
    SeedSource(
        reference="INR21700-50S",
        vendor="NKON",
        product_url="https://www.nkon.nl/en/samsung-inr21700-50s-5000mah-35a.html",
        html_parser="nkon",
        datasheet_url="https://www.dnkpower.com/wp-content/uploads/2022/07/SAMSUNG-INR21700-50S-Cell-Specification.pdf",
        pdf_parser="samsung_50s",
        notes="Retailer EU + PDF miroir publiquement accessible pour la fiche 50S.",
    ),
    SeedSource(
        reference="LF280K",
        vendor="NKON",
        product_url="https://www.nkon.nl/en/eve-lf280-prismatic-280ah-280a-lifepo4.html",
        html_parser="nkon",
        datasheet_url="https://www.battery-germany.de/wp-content/uploads/2022/02/LF280K-280Ah-Product-Specification-Version-B-2023.pdf",
        pdf_parser="eve_lf280k",
        notes="Retailer EU + fiche technique publique EVE.",
    ),
)


HTML_PARSERS = {
    "nkon": parser_html_nkon,
}

PDF_PARSERS = {
    "molicel_p45b": parser_pdf_molicel_p45b,
    "molicel_p42a": parser_pdf_molicel_p42a,
    "samsung_50s": parser_pdf_samsung_50s,
    "eve_lf280k": parser_pdf_eve_lf280k,
}



def collecter_catalogue_cellules(
    seeds: Sequence[SeedSource] = CATALOGUE_SEEDS,
    *,
    sleep_s: float = 0.0,
    timeout_html_s: float = 20.0,
    timeout_pdf_s: float = 30.0,
) -> List[CelluleCommerciale]:
    cellules: List[CelluleCommerciale] = []

    for seed in seeds:
        offre: Optional[OffreCommerciale] = None
        specs_pdf: Optional[SpecCellulePartielle] = None

        html_parser = HTML_PARSERS.get(seed.html_parser)
        if html_parser is None:
            raise ValueError(f"Parser HTML inconnu: {seed.html_parser}")

        try:
            html = telecharger_texte_html(seed.product_url, timeout_s=timeout_html_s)
            offre = html_parser(html, seed.product_url)
        except Exception as exc:
            offre = OffreCommerciale(vendor=seed.vendor, product_url=seed.product_url)
            _safe_append_warning(offre.warnings, f"Échec scraping HTML: {exc}")

        if seed.datasheet_url and seed.pdf_parser:
            pdf_parser = PDF_PARSERS.get(seed.pdf_parser)
            if pdf_parser is None:
                raise ValueError(f"Parser PDF inconnu: {seed.pdf_parser}")
            try:
                pdf_txt = telecharger_pdf_texte(seed.datasheet_url, timeout_s=timeout_pdf_s)
                specs_pdf = pdf_parser(pdf_txt, seed.datasheet_url)
            except Exception as exc:
                specs_pdf = SpecCellulePartielle(reference=seed.reference)
                specs_pdf.add_source(seed.datasheet_url)
                _safe_append_warning(specs_pdf.warnings, f"Échec parsing PDF: {exc}")

        cellules.append(fusionner_offre_et_specs(seed, offre, specs_pdf))

        if sleep_s > 0.0:
            time.sleep(sleep_s)

    return cellules


# =============================================================================
# Pré-dimensionnement à partir de cellules achetables
# =============================================================================



def _volume_cellule_m3(spec: SpecCellulePartielle) -> Optional[float]:
    # Cylindrique
    if spec.diametre_mm is not None and spec.hauteur_mm is not None:
        d = spec.diametre_mm / 1000.0
        h = spec.hauteur_mm / 1000.0
        r = d / 2.0
        return math.pi * r * r * h

    # Prismatique simple
    if spec.largeur_mm is not None and spec.epaisseur_mm is not None and spec.hauteur_mm is not None:
        l = spec.largeur_mm / 1000.0
        e = spec.epaisseur_mm / 1000.0
        h = spec.hauteur_mm / 1000.0
        return l * e * h

    return None



def pre_dimensionner_depuis_cellule_commerciale(
    *,
    cellule: CelluleCommerciale,
    energie_nominale_cible_kwh: float,
    tension_pack_nominale_cible_v: float,
    puissance_continue_kw: Optional[float] = None,
    puissance_pic_kw: Optional[float] = None,
) -> PreDimensionnementPack:
    spec = cellule.specs
    e_target = _exiger_positif("energie_nominale_cible_kwh", energie_nominale_cible_kwh, strict=True)
    v_pack_target = _exiger_positif("tension_pack_nominale_cible_v", tension_pack_nominale_cible_v, strict=True)

    if spec.tension_nominale_v is None:
        raise ValueError(f"{spec.reference}: tension_nominale_v manquante.")
    if spec.capacite_typ_ah is None and spec.capacite_min_ah is None:
        raise ValueError(f"{spec.reference}: capacité cellule manquante.")

    cap_ah = spec.capacite_typ_ah if spec.capacite_typ_ah is not None else spec.capacite_min_ah
    assert cap_ah is not None

    ns = max(1, int(round(v_pack_target / spec.tension_nominale_v)))
    v_pack_nom = ns * spec.tension_nominale_v

    e_cell_kwh = (cap_ah * spec.tension_nominale_v) / 1000.0
    e_string_kwh = ns * e_cell_kwh
    np_energy = max(1, _ceil_div(e_target, e_string_kwh))

    np_p_cont: Optional[int] = None
    np_p_pic: Optional[int] = None
    i_pack_cont: Optional[float] = None
    i_pack_pic: Optional[float] = None
    i_cell_cont: Optional[float] = None
    i_cell_pic: Optional[float] = None
    warnings: List[str] = []

    if puissance_continue_kw is not None:
        p_cont = _exiger_positif("puissance_continue_kw", puissance_continue_kw, strict=False)
        i_pack_cont = (p_cont * 1000.0) / v_pack_nom
        if spec.courant_decharge_max_a is not None and spec.courant_decharge_max_a > 0:
            np_p_cont = max(1, _ceil_div(i_pack_cont, spec.courant_decharge_max_a))
        else:
            _safe_append_warning(warnings, "Courant max cellule absent : contrainte puissance continue non vérifiée.")

    if puissance_pic_kw is not None:
        p_pic = _exiger_positif("puissance_pic_kw", puissance_pic_kw, strict=False)
        i_pack_pic = (p_pic * 1000.0) / v_pack_nom
        if spec.courant_decharge_max_a is not None and spec.courant_decharge_max_a > 0:
            np_p_pic = max(1, _ceil_div(i_pack_pic, spec.courant_decharge_max_a))
        else:
            _safe_append_warning(warnings, "Courant max cellule absent : contrainte puissance pic non vérifiée.")

    np_retenu = np_energy
    for np_c in (np_p_cont, np_p_pic):
        if np_c is not None:
            np_retenu = max(np_retenu, np_c)

    nb_total = ns * np_retenu
    energie_pack = nb_total * e_cell_kwh
    capacite_pack_ah = np_retenu * cap_ah

    if i_pack_cont is not None:
        i_cell_cont = i_pack_cont / np_retenu
    if i_pack_pic is not None:
        i_cell_pic = i_pack_pic / np_retenu

    masse = None if spec.poids_kg is None else nb_total * spec.poids_kg
    vol_cell = _volume_cellule_m3(spec)
    volume = None if vol_cell is None else nb_total * vol_cell

    if spec.capacite_typ_ah is None and spec.capacite_min_ah is not None:
        _safe_append_warning(warnings, "Pré-dimensionnement basé sur capacité minimale faute de capacité typique.")
    if spec.resistance_ac_ohm is None and spec.resistance_dc_ohm is None:
        _safe_append_warning(warnings, "Résistance interne non disponible : pas de chute de tension ni pertes Joule.")

    return PreDimensionnementPack(
        reference=spec.reference,
        vendor=cellule.seed.vendor,
        product_url=cellule.seed.product_url,
        tension_pack_nominale_v=v_pack_nom,
        nb_series=ns,
        nb_parallele_energie=np_energy,
        nb_parallele_puissance_continue=np_p_cont,
        nb_parallele_puissance_pic=np_p_pic,
        nb_parallele_retenu=np_retenu,
        nb_cellules_total=nb_total,
        energie_pack_kwh=energie_pack,
        capacite_pack_ah=capacite_pack_ah,
        courant_pack_continu_a=i_pack_cont,
        courant_pack_pic_a=i_pack_pic,
        courant_cellule_continu_a=i_cell_cont,
        courant_cellule_pic_a=i_cell_pic,
        masse_cellules_kg=masse,
        volume_cellules_m3=volume,
        avertissements=warnings,
    )



def classer_candidats_pre_dimensionnement(
    *,
    cellules: Sequence[CelluleCommerciale],
    energie_nominale_cible_kwh: float,
    tension_pack_nominale_cible_v: float,
    puissance_continue_kw: Optional[float] = None,
    puissance_pic_kw: Optional[float] = None,
) -> List[PreDimensionnementPack]:
    res: List[PreDimensionnementPack] = []
    for cell in cellules:
        try:
            res.append(
                pre_dimensionner_depuis_cellule_commerciale(
                    cellule=cell,
                    energie_nominale_cible_kwh=energie_nominale_cible_kwh,
                    tension_pack_nominale_cible_v=tension_pack_nominale_cible_v,
                    puissance_continue_kw=puissance_continue_kw,
                    puissance_pic_kw=puissance_pic_kw,
                )
            )
        except Exception:
            continue

    # Priorité : moins de cellules, puis moins de masse si connue, puis plus faible surénergie.
    def _key(x: PreDimensionnementPack) -> Tuple[float, float, float]:
        masse = x.masse_cellules_kg if x.masse_cellules_kg is not None else 1e18
        surenergie = max(0.0, x.energie_pack_kwh - energie_nominale_cible_kwh)
        return (float(x.nb_cellules_total), float(masse), float(surenergie))

    return sorted(res, key=_key)


# =============================================================================
# Passage strict vers dimensionner_pack_cellules.py
# =============================================================================



def exigences_pour_cellule_complete(spec: SpecCellulePartielle) -> List[str]:
    besoins: List[str] = []

    if spec.tension_nominale_v is None:
        besoins.append("tension_nominale_v")
    if spec.tension_charge_max_v is None:
        besoins.append("tension_charge_max_v")
    if spec.tension_decharge_min_v is None:
        besoins.append("tension_decharge_min_v")
    if spec.capacite_typ_ah is None and spec.capacite_min_ah is None:
        besoins.append("capacite_typ_ah ou capacite_min_ah")
    if spec.courant_decharge_max_a is None:
        besoins.append("courant_decharge_max_a")
    if spec.poids_kg is None:
        besoins.append("poids_kg")

    # Ce qui manque presque toujours pour le dimensionnement fin strict.
    besoins.extend([
        "point_min_decharge.soc mesuré",
        "point_min_decharge.tension_ocv_v mesurée",
        "point_min_decharge.resistance_interne_ohm mesurée",
        "point_nominal.soc mesuré ou convention explicite",
        "point_nominal.tension_ocv_v mesurée ou convention explicite",
        "point_max_charge.soc mesuré ou convention explicite",
        "point_max_charge.tension_ocv_v mesurée",
    ])
    return besoins


# =============================================================================
# Export / sérialisation
# =============================================================================



def cellule_vers_dict(cellule: CelluleCommerciale) -> Dict[str, Any]:
    return {
        "seed": asdict(cellule.seed),
        "offre": None if cellule.offre is None else asdict(cellule.offre),
        "specs": asdict(cellule.specs),
    }



def catalogue_vers_json(cellules: Sequence[CelluleCommerciale], *, indent: int = 2) -> str:
    return json.dumps([cellule_vers_dict(c) for c in cellules], ensure_ascii=False, indent=indent)


# =============================================================================
# Cellule intégrée : Samsung INR18650-25R
# =============================================================================


def cellule_commerciale_samsung_25r_locale() -> CelluleCommerciale:
    """
    Fournit la Samsung INR18650-25R sans scraping réseau.

    Utile lorsque tu veux dimensionner directement avec les valeurs constructeur
    déjà connues, sans dépendre d'une page vendeur ou d'un PDF accessible en ligne.
    """
    seed = SeedSource(
        reference="Samsung INR18650-25R",
        vendor="local_datasheet",
        product_url="local://samsung-inr18650-25r",
        html_parser="none",
        datasheet_url="Samsung SDI INR18650-25R",
        pdf_parser=None,
        notes="Fiche locale intégrée pour pré-dimensionnement hors ligne.",
    )
    spec = SpecCellulePartielle(
        reference="Samsung INR18650-25R",
        brand="Samsung SDI",
        model="INR18650-25R",
        chemistry="NCA",
        format_cellule="18650",
        capacite_typ_ah=2.56,
        capacite_min_ah=2.5,
        energie_typ_wh=9.38,
        energie_min_wh=9.0,
        tension_nominale_v=3.6,
        tension_charge_max_v=4.2,
        tension_decharge_min_v=2.5,
        courant_decharge_max_a=20.0,
        courant_charge_standard_a=1.25,
        courant_charge_max_a=4.0,
        resistance_ac_ohm=0.01320,
        resistance_dc_ohm=0.02215,
        poids_kg=0.045,
        diametre_mm=18.33,
        hauteur_mm=64.85,
        extra={
            "courant_decharge_prudent_a": 10.0,
            "courant_decharge_performant_a": 15.0,
            "courant_impulsion_moins_1s_a": 100.0,
            "energie_typique_10a_wh": 8.74,
            "resistance_ac_max_ohm": 0.018,
            "resistance_dc_max_ohm": 0.030,
            "table_temperature_decharge_c": {
                5.0: 41.2,
                10.0: 60.6,
                15.0: 78.4,
                20.0: 95.2,
                25.0: 106.8,
            },
        },
        source_urls=["local://samsung-inr18650-25r"],
        warnings=[
            "Cellule non protégée individuellement : prévoir BMS.",
            "Pré-dimensionnement local : vérifier la fiche fournisseur réelle avant achat/assemblage.",
        ],
    )
    offre = OffreCommerciale(
        vendor="local_datasheet",
        product_url="local://samsung-inr18650-25r",
        status="datasheet_only",
        title="Samsung INR18650-25R",
        brand="Samsung SDI",
        model="INR18650-25R",
    )
    return CelluleCommerciale(seed=seed, offre=offre, specs=spec)


__all__ = [
    "SeedSource",
    "OffreCommerciale",
    "SpecCellulePartielle",
    "CelluleCommerciale",
    "PreDimensionnementPack",
    "CATALOGUE_SEEDS",
    "collecter_catalogue_cellules",
    "pre_dimensionner_depuis_cellule_commerciale",
    "classer_candidats_pre_dimensionnement",
    "exigences_pour_cellule_complete",
    "cellule_vers_dict",
    "catalogue_vers_json",
    "cellule_commerciale_samsung_25r_locale",
]

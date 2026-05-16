# frontend\gui\edit_parameters.py
from __future__ import annotations

import ast
import inspect
import json
import math
import re
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import (
    COLORS,
    AccordionSection,
    EditableField,
    EmptyState,
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    StatusBadge,
)


# =============================================================================
# Helpers stricts — aucune valeur inventée
# =============================================================================

_SKIP = object()


def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _safe_float(value: Any) -> Optional[float]:
    return float(value) if _is_finite(value) else None


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)

    if _is_finite(value):
        rounded = round(float(value))
        if abs(float(value) - rounded) <= 1e-9:
            return int(rounded)

    return None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _deep_get(data: Any, *path: str) -> Any:
    cur = data
    for key in path:
        if isinstance(cur, Mapping):
            cur = cur.get(key)
        else:
            return None
        if cur is None:
            return None
    return cur


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _merge_dict_non_none(base: Optional[Dict[str, Any]], extra: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    out = dict(base or {})
    if not isinstance(extra, Mapping):
        return out

    for key, value in extra.items():
        if value is None:
            continue

        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[str(key)] = _merge_dict_non_none(dict(out[key]), value)
        else:
            out[str(key)] = value

    return out


def _pretty_key(key: str) -> str:
    text = str(key).replace("_", " ").strip()
    replacements = {
        "rpm": "RPM",
        "pme": "PME",
        "pa": "Pa",
        "kw": "kW",
        "kwh": "kWh",
        "dc": "DC",
        "cao": "CAO",
        "w": "W",
        "nm": "Nm",
        "kg": "kg",
        "ms2": "m/s²",
        "ms": "m/s",
    }

    parts = []
    for raw in text.split():
        low = raw.lower()
        parts.append(replacements.get(low, raw.capitalize()))

    return " ".join(parts)


def _short_text(value: Any, max_len: int = 140) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _label(text: str, *, color: Any = None, bold: bool = False, size: str = "12sp", height: int = 24) -> Label:
    lbl = Label(
        text=str(text),
        color=color or COLORS["BFW"],
        bold=bold,
        font_size=size,
        size_hint_y=None,
        height=dp(height),
        halign="left",
        valign="middle",
    )
    lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
    return lbl


def _normalise_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_")


# =============================================================================
# Catalogue backend/main.py
# =============================================================================

FALLBACK_BACKEND_KEYS: Tuple[str, ...] = (
    "puissance_traction_kw",
    "production_electrique_sortie_w",
    "puissance_bus_dc_w",
    "puissance_moteur_requise_W",
    "type_puissance_nominale",
    "charger_batterie",
    "distance_km",
    "vitesse_moyenne_kmh",
    "masse_kg",
    "vitesse_ms",
    "acceleration_ms2",
    "angle_pente",
    "angle_unite",
    "coef_roulement",
    "coef_trainee_aero_cda",
    "rayon_roue_m",
    "rapport_reduction_global",
    "rendement_transmission",
    "nb_roues_motrices",
    "nb_moteurs_electriques",
    "pertes_fixes_transmission_w",
    "couple_pertes_transmission_nm",
    "marge_puissance",
    "marge_couple",
    "puissance_auxiliaire_w",
    "conso_kwh_km",
    "puissance_pic_kw",
    "duree_pic_s",
    "energie_utile_imposee_kwh",
    "temps_charge_cible_h",
    "scenario_bus_dc",
    "tension_bus_dc_v",
    "vitesse_alternateur_rpm",
    "rapport_vitesse_alt_sur_moteur",
    "vitesse_moteur_thermique_rpm",
    "tension_alt_v",
    "courant_alt_a",
    "facteur_puissance_alt",
    "courant_est_ligne",
    "rendement_liaison_meca_alt",
    "rapports_boite_candidates",
    "rendement_boite",
    "facteur_service_boite",
    "moment_flechissant_nm",
    "inertie_primaire_kg_m2",
    "inertie_secondaire_kg_m2",
    "delta_omega_rad_s",
    "temps_engagement_s",
    "force_axiale_roulement_N",
    "force_radiale_roulement_N",
    "pme_pa",
    "vitesse_piston_max_ms",
    "longueur_dispo_m",
    "largeur_dispo_m",
    "hauteur_dispo_m",
    "horizon_usage_h",
    "architectures_autorisees",
    "architecture_forcee",
    "poids_maintenance",
    "poids_masse",
    "poids_cout_matiere",
    "poids_compacite",
    "poids_fiabilite",
    "poids_rendement",
    "pression_max_pa",
    "contrainte_admissible_pa",
    "densite_materiau_kg_m3",
    "cout_matiere_eur_kg",
    "rendement_indique_cible_min",
    "rendement_mecanique_cible_min",
    "masse_estimee_max_kg",
    "cout_matiere_max_eur",
    "indice_maintenance_max",
    "duree_vie_cible_h",
    "moteur_thermique_definition",
    "temps_moteur",
    "nombre_cylindres",
    "architecture_moteur",
    "alesage_m",
    "course_m",
    "rpm_moteur_nominal",
    "couple_moteur_max_Nm",
    "force_bielle_N",
    "carburant",
    "ratio_course_alesage_max",
    "ratio_course_alesage_cible",
    "taux_compression_nominal",
    "volume_mort_nominal_m3",
    "pieces_definition",
    "analyses_complementaires",
    "composants_definition",
    "usage_moteur_electrique_depuis_puissance",
    "lancer_pipeline_legacy",
    "lancer_stho_me_secondaire",
)

CATEGORY_ORDER: Tuple[str, ...] = (
    "Puissance & mission",
    "Véhicule & traction",
    "Batterie / Bus DC",
    "Alternateur",
    "Boîte à crabots",
    "Architecture moteur",
    "Moteur thermique",
    "Matériaux / contraintes",
    "Pièces / composants",
    "Backend calculé",
    "Autres",
)

PARAM_META: Dict[str, Dict[str, Any]] = {
    # Puissance & mission
    "puissance_traction_kw": {"label": "Puissance traction", "unit": "kW", "category": "Puissance & mission", "type": "float"},
    "production_electrique_sortie_w": {"label": "Production électrique sortie", "unit": "W", "category": "Puissance & mission", "type": "float"},
    "puissance_bus_dc_w": {"label": "Puissance bus DC", "unit": "W", "category": "Puissance & mission", "type": "float"},
    "puissance_moteur_requise_W": {"label": "Puissance moteur requise", "unit": "W", "category": "Puissance & mission", "type": "float"},
    "type_puissance_nominale": {"label": "Type puissance nominale", "unit": "", "category": "Puissance & mission", "type": "str"},
    "distance_km": {"label": "Distance mission", "unit": "km", "category": "Puissance & mission", "type": "float"},
    "vitesse_moyenne_kmh": {"label": "Vitesse moyenne", "unit": "km/h", "category": "Puissance & mission", "type": "float"},
    "charger_batterie": {"label": "Charger batterie", "unit": "", "category": "Puissance & mission", "type": "bool"},

    # Véhicule
    "masse_kg": {"label": "Masse véhicule", "unit": "kg", "category": "Véhicule & traction", "type": "float"},
    "vitesse_ms": {"label": "Vitesse", "unit": "m/s", "category": "Véhicule & traction", "type": "float"},
    "acceleration_ms2": {"label": "Accélération", "unit": "m/s²", "category": "Véhicule & traction", "type": "float"},
    "angle_pente": {"label": "Angle pente", "unit": "", "category": "Véhicule & traction", "type": "float"},
    "angle_unite": {"label": "Unité angle", "unit": "rad/deg", "category": "Véhicule & traction", "type": "str"},
    "coef_roulement": {"label": "Coefficient roulement", "unit": "", "category": "Véhicule & traction", "type": "float"},
    "coef_trainee_aero_cda": {"label": "CxA / CdA", "unit": "m²", "category": "Véhicule & traction", "type": "float"},
    "rayon_roue_m": {"label": "Rayon roue", "unit": "m", "category": "Véhicule & traction", "type": "float"},
    "rapport_reduction_global": {"label": "Réduction globale", "unit": "", "category": "Véhicule & traction", "type": "float"},
    "rendement_transmission": {"label": "Rendement transmission", "unit": "0..1", "category": "Véhicule & traction", "type": "float"},
    "nb_roues_motrices": {"label": "Roues motrices", "unit": "", "category": "Véhicule & traction", "type": "int"},
    "nb_moteurs_electriques": {"label": "Moteurs électriques", "unit": "", "category": "Véhicule & traction", "type": "int"},
    "puissance_auxiliaire_w": {"label": "Puissance auxiliaire", "unit": "W", "category": "Véhicule & traction", "type": "float"},

    # Batterie / Bus
    "conso_kwh_km": {"label": "Consommation", "unit": "kWh/km", "category": "Batterie / Bus DC", "type": "float"},
    "puissance_pic_kw": {"label": "Puissance pic", "unit": "kW", "category": "Batterie / Bus DC", "type": "float"},
    "duree_pic_s": {"label": "Durée pic", "unit": "s", "category": "Batterie / Bus DC", "type": "float"},
    "energie_utile_imposee_kwh": {"label": "Énergie utile imposée", "unit": "kWh", "category": "Batterie / Bus DC", "type": "float"},
    "temps_charge_cible_h": {"label": "Temps charge cible", "unit": "h", "category": "Batterie / Bus DC", "type": "float"},
    "scenario_bus_dc": {"label": "Scénario Bus DC", "unit": "", "category": "Batterie / Bus DC", "type": "str"},
    "tension_bus_dc_v": {"label": "Tension Bus DC", "unit": "V", "category": "Batterie / Bus DC", "type": "float"},

    # Alternateur
    "vitesse_alternateur_rpm": {"label": "Vitesse alternateur", "unit": "rpm", "category": "Alternateur", "type": "float"},
    "rapport_vitesse_alt_sur_moteur": {"label": "Rapport vitesse alt/moteur", "unit": "", "category": "Alternateur", "type": "float"},
    "vitesse_moteur_thermique_rpm": {"label": "Vitesse moteur thermique", "unit": "rpm", "category": "Alternateur", "type": "float"},
    "tension_alt_v": {"label": "Tension alternateur", "unit": "V", "category": "Alternateur", "type": "float"},
    "courant_alt_a": {"label": "Courant alternateur", "unit": "A", "category": "Alternateur", "type": "float"},
    "facteur_puissance_alt": {"label": "Facteur puissance alternateur", "unit": "0..1", "category": "Alternateur", "type": "float"},
    "courant_est_ligne": {"label": "Courant ligne", "unit": "", "category": "Alternateur", "type": "bool"},
    "rendement_liaison_meca_alt": {"label": "Rendement liaison mécanique alt", "unit": "0..1", "category": "Alternateur", "type": "float"},

    # Boîte
    "rapports_boite_candidates": {"label": "Rapports boîte candidats", "unit": "liste", "category": "Boîte à crabots", "type": "list_float"},
    "rendement_boite": {"label": "Rendement boîte", "unit": "0..1", "category": "Boîte à crabots", "type": "float"},
    "facteur_service_boite": {"label": "Facteur service boîte", "unit": "", "category": "Boîte à crabots", "type": "float"},
    "moment_flechissant_nm": {"label": "Moment fléchissant", "unit": "Nm", "category": "Boîte à crabots", "type": "float"},
    "inertie_primaire_kg_m2": {"label": "Inertie primaire", "unit": "kg·m²", "category": "Boîte à crabots", "type": "float"},
    "inertie_secondaire_kg_m2": {"label": "Inertie secondaire", "unit": "kg·m²", "category": "Boîte à crabots", "type": "float"},
    "delta_omega_rad_s": {"label": "Delta omega", "unit": "rad/s", "category": "Boîte à crabots", "type": "float"},
    "temps_engagement_s": {"label": "Temps engagement", "unit": "s", "category": "Boîte à crabots", "type": "float"},
    "force_axiale_roulement_N": {"label": "Force axiale roulement", "unit": "N", "category": "Boîte à crabots", "type": "float"},
    "force_radiale_roulement_N": {"label": "Force radiale roulement", "unit": "N", "category": "Boîte à crabots", "type": "float"},

    # Architecture
    "pme_pa": {"label": "PME", "unit": "Pa", "category": "Architecture moteur", "type": "float"},
    "vitesse_piston_max_ms": {"label": "Vitesse piston max", "unit": "m/s", "category": "Architecture moteur", "type": "float"},
    "longueur_dispo_m": {"label": "Longueur disponible", "unit": "m", "category": "Architecture moteur", "type": "float"},
    "largeur_dispo_m": {"label": "Largeur disponible", "unit": "m", "category": "Architecture moteur", "type": "float"},
    "hauteur_dispo_m": {"label": "Hauteur disponible", "unit": "m", "category": "Architecture moteur", "type": "float"},
    "architectures_autorisees": {"label": "Architectures autorisées", "unit": "liste", "category": "Architecture moteur", "type": "list_str"},
    "architecture_forcee": {"label": "Architecture forcée", "unit": "", "category": "Architecture moteur", "type": "str"},
    "architecture_moteur": {"label": "Architecture moteur", "unit": "", "category": "Architecture moteur", "type": "str"},
    "nombre_cylindres": {"label": "Nombre de cylindres", "unit": "", "category": "Architecture moteur", "type": "int"},

    # Moteur thermique
    "temps_moteur": {"label": "Temps moteur", "unit": "2/4", "category": "Moteur thermique", "type": "int"},
    "alesage_m": {"label": "Alésage", "unit": "m", "category": "Moteur thermique", "type": "float"},
    "course_m": {"label": "Course", "unit": "m", "category": "Moteur thermique", "type": "float"},
    "rpm_moteur_nominal": {"label": "Régime moteur nominal", "unit": "rpm", "category": "Moteur thermique", "type": "float"},
    "couple_moteur_max_Nm": {"label": "Couple moteur max", "unit": "Nm", "category": "Moteur thermique", "type": "float"},
    "force_bielle_N": {"label": "Force bielle", "unit": "N", "category": "Moteur thermique", "type": "float"},
    "carburant": {"label": "Carburant", "unit": "", "category": "Moteur thermique", "type": "str"},
    "ratio_course_alesage_max": {"label": "Ratio course/alésage max", "unit": "", "category": "Moteur thermique", "type": "float"},
    "ratio_course_alesage_cible": {"label": "Ratio course/alésage cible", "unit": "", "category": "Moteur thermique", "type": "float"},
    "taux_compression_nominal": {"label": "Taux compression nominal", "unit": "", "category": "Moteur thermique", "type": "float"},
    "volume_mort_nominal_m3": {"label": "Volume mort nominal", "unit": "m³", "category": "Moteur thermique", "type": "float"},

    # Matériaux
    "pression_max_pa": {"label": "Pression max", "unit": "Pa", "category": "Matériaux / contraintes", "type": "float"},
    "contrainte_admissible_pa": {"label": "Contrainte admissible", "unit": "Pa", "category": "Matériaux / contraintes", "type": "float"},
    "densite_materiau_kg_m3": {"label": "Densité matériau", "unit": "kg/m³", "category": "Matériaux / contraintes", "type": "float"},
    "cout_matiere_eur_kg": {"label": "Coût matière", "unit": "€/kg", "category": "Matériaux / contraintes", "type": "float"},
    "rendement_indique_cible_min": {"label": "Rendement indiqué min", "unit": "0..1", "category": "Matériaux / contraintes", "type": "float"},
    "rendement_mecanique_cible_min": {"label": "Rendement mécanique min", "unit": "0..1", "category": "Matériaux / contraintes", "type": "float"},
    "masse_estimee_max_kg": {"label": "Masse estimée max", "unit": "kg", "category": "Matériaux / contraintes", "type": "float"},
    "cout_matiere_max_eur": {"label": "Coût matière max", "unit": "€", "category": "Matériaux / contraintes", "type": "float"},
    "indice_maintenance_max": {"label": "Indice maintenance max", "unit": "", "category": "Matériaux / contraintes", "type": "float"},
    "duree_vie_cible_h": {"label": "Durée vie cible", "unit": "h", "category": "Matériaux / contraintes", "type": "float"},

    # Structures avancées
    "moteur_thermique_definition": {"label": "Définition moteur thermique", "unit": "dict", "category": "Pièces / composants", "type": "dict"},
    "pieces_definition": {"label": "Définition pièces", "unit": "dict", "category": "Pièces / composants", "type": "dict"},
    "composants_definition": {"label": "Définition composants", "unit": "dict", "category": "Pièces / composants", "type": "dict"},
    "analyses_complementaires": {"label": "Analyses complémentaires", "unit": "", "category": "Pièces / composants", "type": "bool"},
    "usage_moteur_electrique_depuis_puissance": {"label": "Usage moteur électrique depuis puissance", "unit": "", "category": "Pièces / composants", "type": "bool"},
    "lancer_pipeline_legacy": {"label": "Lancer pipeline legacy", "unit": "", "category": "Pièces / composants", "type": "bool"},
    "lancer_stho_me_secondaire": {"label": "Lancer STHO-ME secondaire", "unit": "", "category": "Pièces / composants", "type": "bool"},
}

LEGACY_ALIAS_MAP: Dict[str, str] = {
    "puissance_entree": "puissance_traction_kw",
    "puissance_requise": "puissance_traction_kw",
    "puissance": "puissance_traction_kw",
    "pme": "pme_pa",
    "regime_pmax": "rpm_moteur_nominal",
    "rpm": "rpm_moteur_nominal",
    "nb_cylindres": "nombre_cylindres",
    "rapport_al_course": "ratio_course_alesage_cible",
    "diametre_piston": "alesage_m",
    "course_piston": "course_m",
    "entraxe_bielle": "longueur_bielle_m",
}

INT_KEYS = {key for key, meta in PARAM_META.items() if meta.get("type") == "int"}
BOOL_KEYS = {key for key, meta in PARAM_META.items() if meta.get("type") == "bool"}
DICT_KEYS = {key for key, meta in PARAM_META.items() if meta.get("type") == "dict"}
LIST_FLOAT_KEYS = {key for key, meta in PARAM_META.items() if meta.get("type") == "list_float"}
LIST_STR_KEYS = {key for key, meta in PARAM_META.items() if meta.get("type") == "list_str"}
STR_KEYS = {key for key, meta in PARAM_META.items() if meta.get("type") == "str"}

RATIO_0_1_KEYS = {
    "rendement_transmission",
    "facteur_puissance_alt",
    "rendement_liaison_meca_alt",
    "rendement_boite",
    "rendement_indique_cible_min",
    "rendement_mecanique_cible_min",
}

STRICT_POSITIVE_KEYS = {
    "puissance_traction_kw",
    "production_electrique_sortie_w",
    "puissance_bus_dc_w",
    "puissance_moteur_requise_W",
    "masse_kg",
    "rayon_roue_m",
    "rapport_reduction_global",
    "nb_roues_motrices",
    "nb_moteurs_electriques",
    "tension_bus_dc_v",
    "vitesse_alternateur_rpm",
    "vitesse_moteur_thermique_rpm",
    "tension_alt_v",
    "courant_alt_a",
    "pme_pa",
    "longueur_dispo_m",
    "largeur_dispo_m",
    "hauteur_dispo_m",
    "pression_max_pa",
    "contrainte_admissible_pa",
    "densite_materiau_kg_m3",
    "temps_moteur",
    "nombre_cylindres",
    "alesage_m",
    "course_m",
    "rpm_moteur_nominal",
}

POWER_TARGET_KEYS = (
    "puissance_traction_kw",
    "production_electrique_sortie_w",
    "puissance_bus_dc_w",
    "puissance_moteur_requise_W",
)


# =============================================================================
# Pont backend/main.py
# =============================================================================

class BackendMainParameterBridge:
    REPORT_ATTRS: Tuple[str, ...] = (
        "backend_report",
        "last_backend_report",
        "full_report",
        "last_full_report",
        "engine_report",
        "last_engine_report",
        "system_report",
        "last_system_report",
        "raw_report",
        "report",
        "last_report",
        "all_data",
        "toutes_les_donnees",
        "ui_report",
    )

    REPORT_HOOKS: Tuple[str, ...] = (
        "get_backend_report",
        "collect_backend_report",
        "fetch_backend_report",
        "load_backend_report",
        "refresh_backend_report",
        "sync_backend_report",
    )

    JSON_PATH_ATTRS: Tuple[str, ...] = (
        "backend_report_path",
        "last_report_path",
        "report_path",
        "output_json_path",
        "toutes_les_donnees_path",
    )

    JSON_NAMES: Tuple[str, ...] = (
        "toutes_les_donnees_completes.json",
        "systeme_complet.json",
        "rapport_systeme.json",
        "rapport_backend.json",
        "test_systeme_complet.json",
    )

    def __init__(self, app: Any) -> None:
        self.app = app
        self.sources: List[str] = []
        self.errors: List[Dict[str, str]] = []

    def backend_signature(self) -> Tuple[List[str], Dict[str, Any], set[str]]:
        """
        Récupère les vrais paramètres de backend.main.dimensionner_systeme_shsem.
        Si l'import échoue, fallback sur la liste connue.
        """
        try:
            from backend.main import dimensionner_systeme_shsem  # type: ignore
        except Exception:
            try:
                from main import dimensionner_systeme_shsem  # type: ignore
            except Exception as exc:
                self.errors.append(
                    {
                        "source": "backend.main.dimensionner_systeme_shsem",
                        "erreur": f"Import impossible, fallback utilisé : {exc}",
                    }
                )
                return list(FALLBACK_BACKEND_KEYS), {}, {"puissance_traction_kw"}

        try:
            sig = inspect.signature(dimensionner_systeme_shsem)
        except Exception as exc:
            self.errors.append(
                {
                    "source": "inspect.signature",
                    "erreur": f"Signature inaccessible, fallback utilisé : {exc}",
                }
            )
            return list(FALLBACK_BACKEND_KEYS), {}, {"puissance_traction_kw"}

        keys: List[str] = []
        defaults: Dict[str, Any] = {}
        required: set[str] = set()

        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            keys.append(name)

            if param.default is inspect._empty:
                required.add(name)
            else:
                defaults[name] = param.default

        if not keys:
            keys = list(FALLBACK_BACKEND_KEYS)

        return keys, defaults, required

    def collect_backend_report(self) -> Dict[str, Any]:
        reports: List[Dict[str, Any]] = []

        reports.extend(self._read_app_reports())
        reports.extend(self._call_safe_report_hooks())
        reports.extend(self._read_json_reports())

        merged: Dict[str, Any] = {}
        for report in reports:
            merged = _merge_dict_non_none(merged, report)

        merged["_edit_parameters_sources"] = list(dict.fromkeys(self.sources))
        if self.errors:
            merged["_edit_parameters_errors"] = self.errors

        return merged

    def _read_app_reports(self) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []

        for attr in self.REPORT_ATTRS:
            try:
                value = getattr(self.app, attr, None)
            except Exception:
                continue

            if isinstance(value, Mapping):
                reports.append(dict(value))
                self.sources.append(f"app.{attr}")

        return reports

    def _call_safe_report_hooks(self) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []

        for name in self.REPORT_HOOKS:
            fn = getattr(self.app, name, None)
            if not callable(fn):
                continue

            try:
                out = fn()
            except TypeError:
                try:
                    out = fn(dict(getattr(self.app, "engine_params", {}) or {}))
                except Exception as exc:
                    self.errors.append({"source": f"app.{name}", "erreur": str(exc)})
                    continue
            except Exception as exc:
                self.errors.append({"source": f"app.{name}", "erreur": str(exc)})
                continue

            if isinstance(out, Mapping):
                reports.append(dict(out))
                self.sources.append(f"app.{name}")

        return reports

    def _read_json_reports(self) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []
        raw_paths: List[Any] = []

        for attr in self.JSON_PATH_ATTRS:
            try:
                value = getattr(self.app, attr, None)
            except Exception:
                value = None

            if value:
                raw_paths.append(value)

        cwd = Path.cwd()
        for name in self.JSON_NAMES:
            raw_paths.append(cwd / name)
            raw_paths.append(cwd / "backend" / name)
            raw_paths.append(cwd / "backend" / "outputs" / name)
            raw_paths.append(cwd / "exports" / name)

        seen: set[str] = set()
        for raw in raw_paths:
            try:
                path = Path(raw).expanduser().resolve()
            except Exception:
                continue

            if str(path) in seen:
                continue
            seen.add(str(path))

            if not path.is_file():
                continue

            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, Mapping):
                    reports.append(dict(data))
                    self.sources.append(f"json:{path}")
            except Exception as exc:
                self.errors.append({"source": f"json:{path}", "erreur": str(exc)})

        return reports


# =============================================================================
# Extraction des valeurs backend
# =============================================================================

def _put_backend_value(
    values: Dict[str, Dict[str, Any]],
    key: str,
    value: Any,
    *,
    source: str,
    readonly: bool = False,
) -> None:
    if value is None:
        return

    old = values.get(key)
    if old is None:
        values[key] = {"value": value, "source": source, "readonly": readonly}
        return

    # Préférer les valeurs explicites déjà renseignées, sinon garder la plus récente.
    if old.get("value") is None:
        values[key] = {"value": value, "source": source, "readonly": readonly}


def extract_backend_values(report: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    values: Dict[str, Dict[str, Any]] = {}

    resume = _safe_dict(report.get("resume_gui"))
    systeme_complet = _safe_dict(report.get("systeme_complet"))
    sc_synth = _safe_dict(systeme_complet.get("synthese"))
    sc_veh = _safe_dict(sc_synth.get("vehicule"))
    sc_batt = _safe_dict(sc_synth.get("batterie"))
    sc_alt = _safe_dict(sc_synth.get("alternateur"))
    sc_mt = _safe_dict(sc_synth.get("moteur_thermique"))
    cao = _safe_dict(report.get("cao"))
    cao_mt = _safe_dict(cao.get("moteur_thermique"))
    synth = _safe_dict(report.get("synthese"))
    synth_mt = _safe_dict(synth.get("moteur_thermique"))

    # resume_gui
    _put_backend_value(values, "architecture_moteur", resume.get("Architecture"), source="backend.resume_gui", readonly=False)
    _put_backend_value(values, "architecture_forcee", resume.get("Architecture"), source="backend.resume_gui", readonly=False)
    _put_backend_value(values, "nombre_cylindres", resume.get("N_cyl"), source="backend.resume_gui", readonly=False)

    bore_mm = _safe_float(resume.get("Bore_mm"))
    if bore_mm is not None:
        _put_backend_value(values, "alesage_m", bore_mm / 1000.0, source="backend.resume_gui.Bore_mm", readonly=False)

    stroke_mm = _safe_float(resume.get("Stroke_mm"))
    if stroke_mm is not None:
        _put_backend_value(values, "course_m", stroke_mm / 1000.0, source="backend.resume_gui.Stroke_mm", readonly=False)

    _put_backend_value(values, "rpm_moteur_nominal", resume.get("RPM"), source="backend.resume_gui", readonly=False)
    _put_backend_value(values, "pme_pa", _first_non_none(resume.get("PME_Pa"), resume.get("PME")), source="backend.resume_gui", readonly=False)
    _put_backend_value(values, "pression_max_pa", resume.get("Pmax_Pa"), source="backend.resume_gui", readonly=False)
    _put_backend_value(values, "couple_moteur_max_Nm", resume.get("Couple_max_Nm"), source="backend.resume_gui", readonly=False)
    _put_backend_value(values, "force_bielle_N", resume.get("Force_bielle_N"), source="backend.resume_gui", readonly=False)
    _put_backend_value(values, "puissance_bus_dc_w", resume.get("P_bus_dc_design_w"), source="backend.resume_gui", readonly=False)
    _put_backend_value(values, "energie_utile_imposee_kwh", resume.get("energie_batterie_kwh"), source="backend.resume_gui", readonly=False)

    # systeme_complet
    _put_backend_value(values, "puissance_bus_dc_w", sc_veh.get("puissance_bus_dc_design_w"), source="backend.systeme_complet.synthese.vehicule", readonly=False)
    _put_backend_value(values, "tension_bus_dc_v", sc_veh.get("tension_bus_dc_v"), source="backend.systeme_complet.synthese.vehicule", readonly=False)
    _put_backend_value(values, "energie_utile_imposee_kwh", sc_batt.get("energie_utile_kwh"), source="backend.systeme_complet.synthese.batterie", readonly=False)
    _put_backend_value(values, "vitesse_alternateur_rpm", sc_alt.get("vitesse_rotation_rpm"), source="backend.systeme_complet.synthese.alternateur", readonly=False)

    _put_backend_value(values, "architecture_moteur", sc_mt.get("architecture"), source="backend.systeme_complet.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "nombre_cylindres", sc_mt.get("nombre_cylindres"), source="backend.systeme_complet.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "alesage_m", sc_mt.get("alesage_m"), source="backend.systeme_complet.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "course_m", sc_mt.get("course_m"), source="backend.systeme_complet.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "pme_pa", sc_mt.get("pme_pa"), source="backend.systeme_complet.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "pression_max_pa", sc_mt.get("pression_max_pa"), source="backend.systeme_complet.synthese.moteur_thermique", readonly=False)

    # cao
    cao_bore_mm = _safe_float(cao_mt.get("alesage_mm"))
    if cao_bore_mm is not None:
        _put_backend_value(values, "alesage_m", cao_bore_mm / 1000.0, source="backend.cao.moteur_thermique.alesage_mm", readonly=False)

    cao_stroke_mm = _safe_float(cao_mt.get("course_mm"))
    if cao_stroke_mm is not None:
        _put_backend_value(values, "course_m", cao_stroke_mm / 1000.0, source="backend.cao.moteur_thermique.course_mm", readonly=False)

    _put_backend_value(values, "nombre_cylindres", cao_mt.get("nombre_cylindres"), source="backend.cao.moteur_thermique", readonly=False)
    _put_backend_value(values, "rpm_moteur_nominal", cao_mt.get("rpm_nominal"), source="backend.cao.moteur_thermique", readonly=False)

    # synthèse racine
    _put_backend_value(values, "architecture_moteur", synth_mt.get("architecture"), source="backend.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "nombre_cylindres", synth_mt.get("nombre_cylindres"), source="backend.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "alesage_m", synth_mt.get("alesage_m"), source="backend.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "course_m", synth_mt.get("course_m"), source="backend.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "pme_pa", synth_mt.get("pme_pa"), source="backend.synthese.moteur_thermique", readonly=False)
    _put_backend_value(values, "pression_max_pa", synth_mt.get("pression_max_pa"), source="backend.synthese.moteur_thermique", readonly=False)

    return values


def flatten_backend_unknowns(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, Mapping):
            inc = node.get("inconnues")
            if isinstance(inc, Mapping):
                for category, values in inc.items():
                    for item in _safe_list(values):
                        if isinstance(item, Mapping):
                            row = dict(item)
                            row.setdefault("categorie", category)
                            row.setdefault("source", path or "racine")
                            out.append(row)

            inconnues_cao = node.get("inconnues_cao")
            if isinstance(inconnues_cao, list):
                for item in inconnues_cao:
                    if isinstance(item, Mapping):
                        row = dict(item)
                        row.setdefault("categorie", "cao")
                        row.setdefault("source", path or "cao")
                        out.append(row)

            for key, value in node.items():
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}.{key}" if path else str(key))

        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}[{index}]")

    walk(report)

    seen: set[Tuple[str, str, str, str]] = set()
    deduped: List[Dict[str, Any]] = []

    for item in out:
        sig = (
            str(item.get("nom", "")),
            str(item.get("champ", "")),
            str(item.get("raison", "")),
            str(item.get("source", "")),
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(item)

    return deduped


def infer_missing_backend_keys(unknowns: Sequence[Mapping[str, Any]], backend_keys: Sequence[str]) -> set[str]:
    missing: set[str] = set()
    key_index = {_normalise_text(k): k for k in backend_keys}

    extra_aliases = {
        "pme": "pme_pa",
        "pression_moyenne_effective": "pme_pa",
        "pression_max": "pression_max_pa",
        "pmax": "pression_max_pa",
        "rpm": "rpm_moteur_nominal",
        "regime": "rpm_moteur_nominal",
        "alesage": "alesage_m",
        "bore": "alesage_m",
        "course": "course_m",
        "stroke": "course_m",
        "architecture": "architecture_moteur",
        "cylindres": "nombre_cylindres",
        "nb_cyl": "nombre_cylindres",
        "bus_dc": "puissance_bus_dc_w",
        "batterie": "energie_utile_imposee_kwh",
    }

    for item in unknowns:
        text = " ".join(
            str(item.get(k, ""))
            for k in ("nom", "champ", "piece", "raison", "detail", "source")
        )
        normalised = _normalise_text(text)

        for norm_key, real_key in key_index.items():
            if norm_key and norm_key in normalised:
                missing.add(real_key)

        for needle, target in extra_aliases.items():
            if needle in normalised:
                missing.add(target)

    return missing


# =============================================================================
# Parsing / validation
# =============================================================================

def parse_bool(text: str) -> bool:
    low = text.strip().lower()
    if low in {"1", "true", "vrai", "oui", "yes", "y", "on"}:
        return True
    if low in {"0", "false", "faux", "non", "no", "n", "off"}:
        return False
    raise ValueError("booléen attendu : true/false, oui/non, 1/0")


def parse_structured(text: str) -> Any:
    raw = text.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    try:
        return ast.literal_eval(raw)
    except Exception as exc:
        raise ValueError(f"structure JSON/Python invalide : {exc}") from exc


def parse_parameter_value(key: str, text: str, *, expected_type: str = "") -> Any:
    raw = (text or "").strip()

    if raw == "":
        return _SKIP

    if raw.lower() in {"none", "null", "inconnu", "inconnue", "...", "nan"}:
        return None

    if key in BOOL_KEYS or expected_type == "bool":
        return parse_bool(raw)

    if key in DICT_KEYS or expected_type == "dict":
        value = parse_structured(raw)
        if not isinstance(value, dict):
            raise ValueError("dictionnaire attendu")
        return value

    if key in LIST_FLOAT_KEYS or expected_type == "list_float":
        value = parse_structured(raw) if raw.startswith("[") else [x.strip() for x in re.split(r"[;,]", raw) if x.strip()]
        if not isinstance(value, (list, tuple)):
            raise ValueError("liste attendue")
        return [float(str(x).replace(",", ".")) for x in value]

    if key in LIST_STR_KEYS or expected_type == "list_str":
        value = parse_structured(raw) if raw.startswith("[") else [x.strip() for x in re.split(r"[;,]", raw) if x.strip()]
        if not isinstance(value, (list, tuple)):
            raise ValueError("liste attendue")
        return [str(x).strip() for x in value if str(x).strip()]

    if key in INT_KEYS or expected_type == "int":
        value = float(raw.replace(",", "."))
        rounded = round(value)
        if abs(value - rounded) > 1e-9:
            raise ValueError("entier attendu")
        return int(rounded)

    if key in STR_KEYS or expected_type == "str":
        return raw

    # Auto : nombre scientifique, négatif, décimal, puis texte.
    candidate = raw.replace(",", ".")
    try:
        return float(candidate)
    except Exception:
        return raw


def canonicalise_legacy_aliases(params: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(params)

    # Conversion prudente puissance_entree + unite_entree.
    if "puissance_entree" in out and "puissance_traction_kw" not in out:
        value = _safe_float(out.get("puissance_entree"))
        unit = str(out.get("unite_entree", "kw")).strip().lower()

        if value is not None:
            if unit in {"kw", "kilowatt", "kilowatts"}:
                out["puissance_traction_kw"] = value
            elif unit in {"w", "watt", "watts"}:
                out["puissance_traction_kw"] = value / 1000.0
            else:
                # Unité non reconnue : on ne convertit pas silencieusement.
                out.setdefault("_warnings_front", []).append(
                    {
                        "champ": "puissance_entree",
                        "detail": f"Unité non convertie automatiquement : {unit!r}",
                    }
                )

    for old_key, new_key in LEGACY_ALIAS_MAP.items():
        if old_key in out and new_key not in out:
            out[new_key] = out[old_key]

    return out


def validate_engine_params(params: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []

    if not any(_safe_float(params.get(k)) is not None and float(params[k]) > 0.0 for k in POWER_TARGET_KEYS):
        errors.append(
            "Aucune cible de puissance exploitable : renseigne au moins puissance_traction_kw, "
            "production_electrique_sortie_w, puissance_bus_dc_w ou puissance_moteur_requise_W."
        )

    for key in STRICT_POSITIVE_KEYS:
        value = params.get(key)
        if value is None:
            continue

        num = _safe_float(value)
        if num is None:
            errors.append(f"{key} doit être numérique.")
        elif num <= 0.0:
            errors.append(f"{key} doit être > 0.")

    for key in RATIO_0_1_KEYS:
        value = params.get(key)
        if value is None:
            continue

        num = _safe_float(value)
        if num is None:
            errors.append(f"{key} doit être numérique.")
        elif not (0.0 < num <= 1.0):
            errors.append(f"{key} doit être dans ]0 ; 1].")

    if params.get("temps_moteur") is not None and params.get("temps_moteur") not in {2, 4}:
        errors.append("temps_moteur doit valoir 2 ou 4.")

    return errors


# =============================================================================
# Construction des champs éditables
# =============================================================================

def build_editable_parameters(app: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    bridge = BackendMainParameterBridge(app)

    backend_keys, defaults, required = bridge.backend_signature()
    backend_report = bridge.collect_backend_report()
    backend_values = extract_backend_values(backend_report)
    unknowns = flatten_backend_unknowns(backend_report)
    missing_keys = infer_missing_backend_keys(unknowns, backend_keys)

    current_params = _safe_dict(getattr(app, "engine_params", {}) or {})
    ui_report = _safe_dict(getattr(app, "ui_report", {}) or {})
    existing_ui_params = _safe_list(ui_report.get("editable_parameters"))

    legacy_params_by_key: Dict[str, Mapping[str, Any]] = {}
    for item in existing_ui_params:
        if isinstance(item, Mapping) and item.get("key"):
            legacy_params_by_key[str(item["key"])] = item

    keys: List[str] = []

    def add_key(key: str) -> None:
        if key and key not in keys:
            keys.append(key)

    for key in backend_keys:
        add_key(key)

    for key in current_params.keys():
        add_key(str(key))

    for key in backend_values.keys():
        add_key(str(key))

    for key in missing_keys:
        add_key(str(key))

    for key in legacy_params_by_key.keys():
        add_key(str(key))

    parameters: List[Dict[str, Any]] = []

    for key in keys:
        canonical_key = LEGACY_ALIAS_MAP.get(key, key)
        meta = PARAM_META.get(canonical_key, PARAM_META.get(key, {}))
        backend_value = backend_values.get(canonical_key) or backend_values.get(key)
        legacy = legacy_params_by_key.get(key) or legacy_params_by_key.get(canonical_key)

        value = None
        source = "DONNÉE ATTENDUE"
        editable = True

        if canonical_key in current_params:
            value = current_params.get(canonical_key)
            source = "SAISIE_UTILISATEUR"
        elif key in current_params:
            value = current_params.get(key)
            source = "SAISIE_UTILISATEUR_ALIAS"
        elif legacy and legacy.get("value") is not None:
            value = legacy.get("value")
            source = str(legacy.get("source", "UI_EXISTANT"))
            editable = bool(legacy.get("editable", True))
        elif backend_value is not None:
            value = backend_value.get("value")
            source = str(backend_value.get("source", "CALCUL_BACKEND"))
            editable = not bool(backend_value.get("readonly", False))
        elif canonical_key in defaults and defaults.get(canonical_key) is not inspect._empty:
            default_value = defaults.get(canonical_key)
            if default_value is not None:
                value = default_value
                source = "DÉFAUT_SIGNATURE_BACKEND"

        missing = (
            canonical_key in missing_keys
            or key in missing_keys
            or value is None
            or str(value).strip().upper() in {"INCONNU", "NONE", "...", "NULL"}
        )

        if missing and source not in {"SAISIE_UTILISATEUR", "SAISIE_UTILISATEUR_ALIAS"}:
            source = "DONNÉE ATTENDUE_BACKEND"

        parameters.append(
            {
                "key": canonical_key,
                "legacy_key": key if key != canonical_key else None,
                "label": str(
                    _first_non_empty(
                        meta.get("label"),
                        legacy.get("label") if legacy else None,
                        _pretty_key(canonical_key),
                    )
                ),
                "value": value,
                "unit": str(meta.get("unit", "")),
                "category": str(meta.get("category", "Autres")),
                "type": str(meta.get("type", "")),
                "source": source,
                "editable": editable,
                "required": canonical_key in required or canonical_key in POWER_TARGET_KEYS or canonical_key in missing_keys,
                "missing": missing,
            }
        )

    # Ordre : catégories connues, requis/manquants d'abord.
    category_rank = {name: idx for idx, name in enumerate(CATEGORY_ORDER)}

    parameters.sort(
        key=lambda item: (
            category_rank.get(str(item.get("category", "Autres")), 999),
            0 if item.get("required") else 1,
            0 if item.get("missing") else 1,
            str(item.get("label", "")),
        )
    )

    context = {
        "backend_report": backend_report,
        "backend_sources": bridge.sources,
        "backend_errors": bridge.errors,
        "unknowns": unknowns,
        "missing_keys": sorted(missing_keys),
        "backend_keys_count": len(backend_keys),
    }

    return parameters, context


# =============================================================================
# Écran principal
# =============================================================================

class EditParametersScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.fields: Dict[str, EditableField] = {}
        self.field_meta: Dict[str, Dict[str, Any]] = {}
        self._last_context: Dict[str, Any] = {}
        self._last_apply_errors: List[str] = []

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self, *_: Any) -> None:
        self.clear_widgets()
        self.fields = {}
        self.field_meta = {}

        app = App.get_running_app()

        try:
            params, context = build_editable_parameters(app)
        except Exception as exc:
            params = []
            context = {
                "backend_errors": [
                    {
                        "source": "build_editable_parameters",
                        "erreur": str(exc),
                        "trace": traceback.format_exc(),
                    }
                ],
                "backend_sources": [],
                "unknowns": [],
                "missing_keys": [],
                "backend_keys_count": 0,
            }

        self._last_context = context

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        root.add_widget(self._top_bar())
        root.add_widget(self._backend_summary_panel(params, context))

        if self._last_apply_errors:
            root.add_widget(self._errors_panel(self._last_apply_errors))

        if not params:
            root.add_widget(
                EmptyState(
                    text="AUCUN PARAMÈTRE CONFIGURABLE",
                    action_text="RETOUR DASHBOARD",
                    callback=lambda *_: self.go_dashboard(),
                )
            )
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        for category in CATEGORY_ORDER:
            section_items = [p for p in params if p.get("category") == category]
            if not section_items:
                continue

            content.add_widget(
                AccordionSection(
                    title=f"{category} ({len(section_items)})",
                    content=self._make_grid(section_items),
                    collapsed=category not in {"Puissance & mission", "Architecture moteur", "Moteur thermique"},
                )
            )

        remaining = [p for p in params if p.get("category") not in CATEGORY_ORDER]
        if remaining:
            content.add_widget(
                AccordionSection(
                    title=f"Autres ({len(remaining)})",
                    content=self._make_grid(remaining),
                    collapsed=True,
                )
            )

        scroll.add_widget(content)
        root.add_widget(scroll)

        apply_btn = ModernButton(
            text="APPLIQUER ET RECALCULER",
            size_hint_y=None,
            height=dp(52),
            font_size="13sp",
        )
        apply_btn.bind(on_release=self.apply_and_recalculate)
        root.add_widget(apply_btn)

        self.add_widget(root)

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(56),
            spacing=dp(10),
            padding=[dp(10), dp(5)],
        )

        lbl = Label(
            text="PANNEAU D'INGÉNIERIE — BACKEND MAIN",
            color=COLORS["BFW"],
            bold=True,
            font_size="16sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)

        btn_refresh = ModernButton(text="SYNC BACKEND", size_hint_x=None, width=dp(140), font_size="11sp")
        btn_refresh.bind(on_release=self.refresh)
        bar.add_widget(btn_refresh)

        btn_json = ModernButton(text="JSON", size_hint_x=None, width=dp(80), font_size="11sp")
        btn_json.bind(on_release=lambda *_: self._go("raw_report"))
        bar.add_widget(btn_json)

        btn_back = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=dp(180), font_size="11sp")
        btn_back.bind(on_release=self.go_dashboard)
        bar.add_widget(btn_back)

        return bar

    def _backend_summary_panel(self, params: List[Dict[str, Any]], context: Mapping[str, Any]) -> NeoCard:
        missing_count = sum(1 for p in params if p.get("missing"))
        required_count = sum(1 for p in params if p.get("required"))
        source_count = len(_safe_list(context.get("backend_sources")))
        error_count = len(_safe_list(context.get("backend_errors")))

        panel = NeoCard(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(82),
            spacing=dp(8),
            padding=dp(8),
        )

        panel.add_widget(MetricRow("Paramètres backend", context.get("backend_keys_count"), "", "ok"))
        panel.add_widget(MetricRow("Champs affichés", len(params), "", "ok"))
        panel.add_widget(MetricRow("Requis", required_count, "", "alerte" if required_count else "ok"))
        panel.add_widget(MetricRow("Manquants", missing_count, "", "alerte" if missing_count else "ok"))
        panel.add_widget(MetricRow("Sources backend", source_count, "", "ok" if source_count else "missing"))
        panel.add_widget(MetricRow("Erreurs", error_count, "", "alerte" if error_count else "ok"))

        return panel

    def _errors_panel(self, errors: Sequence[str]) -> PremiumCard:
        panel = PremiumCard(title="Erreurs de validation", bg=COLORS["RS_18"], size_hint_y=None)
        panel.height = dp(52 + min(len(errors), 5) * 34)

        box = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))

        for err in list(errors)[:5]:
            box.add_widget(_label(f"• {err}", color=COLORS["RS"], size="11sp", height=32))

        panel.add_widget(box)
        return panel

    def _make_grid(self, items: List[Dict[str, Any]]) -> GridLayout:
        grid = GridLayout(cols=2, spacing=dp(12), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for item in items:
            key = str(item.get("key", "")).strip()
            if not key:
                continue

            value = item.get("value")
            is_missing = bool(item.get("missing"))

            source = str(item.get("source", "DONNÉE ATTENDUE"))
            unit = str(item.get("unit", "")).strip()
            type_name = str(item.get("type", "")).strip()

            suffix_parts = []
            if unit:
                suffix_parts.append(unit)
            if type_name:
                suffix_parts.append(type_name)
            if item.get("required"):
                suffix_parts.append("REQUIS")
            if is_missing:
                suffix_parts.append("À RENSEIGNER")

            source_text = f"Source: {source}"
            if suffix_parts:
                source_text += " | " + " | ".join(suffix_parts)

            field = EditableField(
                label=str(item.get("label", key)),
                value=value,
                source=source_text,
                editable=bool(item.get("editable", True)),
                key=key,
            )

            grid.add_widget(field)
            self.fields[key] = field
            self.field_meta[key] = dict(item)

        return grid

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------

    def apply_and_recalculate(self, *_: Any) -> None:
        app = App.get_running_app()
        params = dict(getattr(app, "engine_params", {}) or {})
        errors: List[str] = []

        for key, field in self.fields.items():
            meta = self.field_meta.get(key, {})
            if not getattr(field, "editable", True):
                continue

            text = (field.input.text or "").strip()
            expected_type = str(meta.get("type", "")).strip()

            try:
                parsed = parse_parameter_value(key, text, expected_type=expected_type)
            except Exception as exc:
                errors.append(f"{key} : {exc}")
                continue

            if parsed is _SKIP:
                continue

            params[key] = parsed

            legacy_key = meta.get("legacy_key")
            if legacy_key and legacy_key != key:
                params[str(legacy_key)] = parsed

        params = canonicalise_legacy_aliases(params)

        validation_errors = validate_engine_params(params)
        errors.extend(validation_errors)

        if errors:
            self._last_apply_errors = errors
            self.refresh()
            return

        self._last_apply_errors = []
        app.engine_params = params

        # Stocke aussi les champs édités pour que les autres écrans puissent les relire.
        ui_report = dict(getattr(app, "ui_report", {}) or {})
        ui_report["editable_parameters"] = self._serialize_current_fields(params)
        app.ui_report = ui_report

        # Notifie l'App si elle expose un hook.
        for hook_name in (
            "on_engine_params_changed",
            "request_recalculation",
            "request_recalculate",
            "recalculate_backend",
            "recalculate",
            "run_calculation",
            "start_calculation",
        ):
            fn = getattr(app, hook_name, None)
            if not callable(fn):
                continue

            try:
                self._call_hook_safely(fn, params)
                break
            except Exception:
                continue

        self._go("loading")

    def _serialize_current_fields(self, params: Mapping[str, Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        for key, meta in self.field_meta.items():
            out.append(
                {
                    "key": key,
                    "label": meta.get("label", _pretty_key(key)),
                    "value": params.get(key),
                    "source": "SAISIE_UTILISATEUR" if key in params else meta.get("source", "DONNÉE_ATTENDUE"),
                    "editable": meta.get("editable", True),
                    "category": meta.get("category", "Autres"),
                    "type": meta.get("type", ""),
                    "unit": meta.get("unit", ""),
                }
            )

        return out

    def _call_hook_safely(self, fn: Callable[..., Any], params: Mapping[str, Any]) -> Any:
        try:
            sig = inspect.signature(fn)
        except Exception:
            sig = None

        if sig is not None:
            try:
                accepted = set(sig.parameters.keys())
                if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    return fn(**dict(params))

                filtered = {k: v for k, v in dict(params).items() if k in accepted}
                if filtered:
                    return fn(**filtered)
            except TypeError:
                pass

        try:
            return fn(dict(params))
        except TypeError:
            return fn()

    def go_dashboard(self, *_: Any) -> None:
        self._go("dashboard")

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name
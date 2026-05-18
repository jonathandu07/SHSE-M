# frontend/gui/loading.py
from __future__ import annotations

import inspect
import math
import threading
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from frontend.gui.components import (
    COLORS,
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    SectionTitle,
    StatusBadge,
)

try:
    from frontend.gui.report_adapter import adapt_backend_report, extract_architecture_candidates
except Exception:  # pragma: no cover
    adapt_backend_report = None  # type: ignore
    extract_architecture_candidates = None  # type: ignore

try:
    from frontend.main import dimensionner_systeme_shsem, refresh_backend_data
except Exception:  # pragma: no cover
    dimensionner_systeme_shsem = None  # type: ignore
    refresh_backend_data = None  # type: ignore

normaliser_puissance = None  # le GUI ne dépend pas directement d'un module backend


# =============================================================================
# Constantes / alias
# =============================================================================

CH_TO_W = 735.49875
KW_TO_W = 1000.0

POWER_TARGET_KEYS: tuple[str, ...] = (
    "puissance_traction_kw",
    "production_electrique_sortie_w",
    "puissance_bus_dc_w",
    "puissance_moteur_requise_W",
)

LEGACY_ALIAS_MAP: dict[str, str] = {
    "puissance": "puissance_traction_kw",
    "puissance_requise": "puissance_traction_kw",
    "puissance_kw": "puissance_traction_kw",
    "pme": "pme_pa",
    "regime_pmax": "rpm_moteur_nominal",
    "rpm": "rpm_moteur_nominal",
    "nb_cylindres": "nombre_cylindres",
    "rapport_al_course": "ratio_course_alesage_cible",
    "diametre_piston": "alesage_m",
    "diametre_piston_m": "alesage_m",
    "course_piston": "course_m",
    "course_piston_m": "course_m",
    "architecture": "architecture_moteur",
}

INT_KEYS = {
    "nombre_cylindres",
    "nb_roues_motrices",
    "nb_moteurs_electriques",
    "temps_moteur",
}

FLOAT_KEYS = {
    "puissance_traction_kw",
    "production_electrique_sortie_w",
    "puissance_bus_dc_w",
    "puissance_moteur_requise_W",
    "masse_kg",
    "vitesse_ms",
    "acceleration_ms2",
    "angle_pente",
    "coef_roulement",
    "coef_trainee_aero_cda",
    "rayon_roue_m",
    "rapport_reduction_global",
    "rendement_transmission",
    "pertes_fixes_transmission_w",
    "couple_pertes_transmission_nm",
    "marge_puissance",
    "marge_couple",
    "puissance_auxiliaire_w",
    "distance_km",
    "conso_kwh_km",
    "puissance_moyenne_kw",
    "vitesse_moyenne_kmh",
    "temps_charge_cible_h",
    "puissance_pic_kw",
    "duree_pic_s",
    "energie_utile_imposee_kwh",
    "tension_bus_dc_v",
    "vitesse_alternateur_rpm",
    "rapport_vitesse_alt_sur_moteur",
    "vitesse_moteur_thermique_rpm",
    "tension_alt_v",
    "courant_alt_a",
    "facteur_puissance_alt",
    "rendement_liaison_meca_alt",
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
    "alesage_m",
    "course_m",
    "alesage_mm",
    "course_mm",
    "rpm_moteur_nominal",
    "couple_moteur_max_Nm",
    "force_bielle_N",
    "ratio_course_alesage_max",
    "ratio_course_alesage_cible",
    "taux_compression_nominal",
    "volume_mort_nominal_m3",
}

BOOL_KEYS = {
    "charger_batterie",
    "courant_est_ligne",
    "analyses_complementaires",
    "usage_moteur_electrique_depuis_puissance",
    "lancer_pipeline_legacy",
    "lancer_stho_me_secondaire",
}


# =============================================================================
# Helpers stricts
# =============================================================================

def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _safe_float(value: Any) -> Optional[float]:
    if _is_finite(value):
        return float(value)

    if isinstance(value, str):
        raw = value.strip().replace(",", ".")
        if not raw:
            return None
        try:
            out = float(raw)
        except Exception:
            return None
        return out if math.isfinite(out) else None

    return None


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return value

    number = _safe_float(value)
    if number is None:
        return None

    rounded = round(number)
    if abs(number - rounded) <= 1e-9:
        return int(rounded)

    return None


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _merge_dict_non_none(base: Optional[dict[str, Any]], extra: Optional[Mapping[str, Any]]) -> dict[str, Any]:
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


def _fmt(value: Any, digits: int = 4) -> str:
    number = _safe_float(value)
    if number is None:
        return "—"

    av = abs(number)

    if av >= 1_000_000:
        return f"{number / 1_000_000:.{digits}g} M"
    if av >= 1_000:
        return f"{number / 1_000:.{digits}g} k"
    if 0.0 < av < 0.001:
        return f"{number:.{digits}e}"

    return f"{number:.{digits}g}"


def _short_text(value: Any, max_len: int = 140) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = 6) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Mapping):
        return {
            str(k): _jsonable(v, depth=depth + 1, max_depth=max_depth)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _jsonable(v, depth=depth + 1, max_depth=max_depth)
            for v in value
        ]

    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass

    try:
        return str(value)
    except Exception:
        return {"type": type(value).__name__}


def _parse_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "vrai", "oui", "yes", "on"}:
            return True
        if raw in {"0", "false", "faux", "non", "no", "off"}:
            return False

    return value


def _normalise_basic_value(key: str, value: Any) -> Any:
    if value is None:
        return None

    if key in BOOL_KEYS:
        return _parse_bool(value)

    if key in INT_KEYS:
        parsed = _safe_int(value)
        return parsed if parsed is not None else value

    if key in FLOAT_KEYS:
        parsed = _safe_float(value)
        return parsed if parsed is not None else value

    return value


def _filter_kwargs_for_signature(fn: Callable[..., Any], params: Mapping[str, Any]) -> dict[str, Any]:
    clean = {
        str(k): v
        for k, v in dict(params or {}).items()
        if v is not None
    }

    try:
        sig = inspect.signature(fn)
    except Exception:
        return clean

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return clean

    accepted = set(sig.parameters.keys())
    return {k: v for k, v in clean.items() if k in accepted}


def _signature_keys(fn: Optional[Callable[..., Any]]) -> set[str]:
    if fn is None:
        return set()

    try:
        sig = inspect.signature(fn)
    except Exception:
        return set()

    return {
        name
        for name, param in sig.parameters.items()
        if name != "self"
        and param.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
    }


def _has_power_target(params: Mapping[str, Any]) -> bool:
    for key in POWER_TARGET_KEYS:
        value = _safe_float(params.get(key))
        if value is not None and value > 0.0:
            return True
    return False


# =============================================================================
# Normalisation front → backend
# =============================================================================

def _normalise_power_from_legacy(params: dict[str, Any]) -> dict[str, Any]:
    """
    Conserve les anciens champs, mais injecte les cibles strictes attendues par backend/main.py.
    """
    out = dict(params)

    # 1) Puissance brute historique : puissance_entree + unite_entree
    raw_value = out.get("puissance_entree")
    raw_unit = out.get("unite_entree")

    if raw_value is not None and raw_unit is not None:
        value = _safe_float(raw_value)
        unit = str(raw_unit).strip()

        if value is not None and value > 0:
            if normaliser_puissance is not None:
                normalized = normaliser_puissance(value, unit)
                if isinstance(normalized, Mapping):
                    kw = _safe_float(normalized.get("kw"))
                    w = _safe_float(normalized.get("w"))
                    ch = _safe_float(normalized.get("ch"))
                else:
                    kw = None
                    w = None
                    ch = None
            else:
                if unit == "kW":
                    kw = value
                    w = value * KW_TO_W
                    ch = w / CH_TO_W
                elif unit == "W":
                    w = value
                    kw = value / KW_TO_W
                    ch = w / CH_TO_W
                elif unit in {"ch", "cv"}:
                    w = value * CH_TO_W
                    kw = w / KW_TO_W
                    ch = value
                else:
                    kw = None
                    w = None
                    ch = None

            if kw is not None and kw > 0:
                out.setdefault("puissance_traction_kw", kw)

            if w is not None and w > 0:
                out.setdefault("production_electrique_sortie_w", w)
                out.setdefault("puissance_bus_dc_w", w)
                out.setdefault("puissance_moteur_requise_W", w)

            out.setdefault(
                "saisie_home",
                {
                    "valeur": value,
                    "unite": unit,
                    "puissance_kw": kw,
                    "puissance_w": w,
                    "puissance_ch": ch,
                    "source": "LoadingScreen._normalise_power_from_legacy",
                },
            )

    # 2) Si seule une puissance kW existe, propager les autres clés.
    kw = _safe_float(out.get("puissance_traction_kw"))
    if kw is not None and kw > 0:
        w = kw * KW_TO_W
        out.setdefault("production_electrique_sortie_w", w)
        out.setdefault("puissance_bus_dc_w", w)
        out.setdefault("puissance_moteur_requise_W", w)

    # 3) Si seule une puissance W existe, reconstruire kW.
    for w_key in ("production_electrique_sortie_w", "puissance_bus_dc_w", "puissance_moteur_requise_W"):
        w = _safe_float(out.get(w_key))
        if w is not None and w > 0:
            out.setdefault("puissance_traction_kw", w / KW_TO_W)
            out.setdefault("production_electrique_sortie_w", w)
            out.setdefault("puissance_bus_dc_w", w)
            out.setdefault("puissance_moteur_requise_W", w)
            break

    return out


def build_backend_args(params: Mapping[str, Any]) -> dict[str, Any]:
    """
    Transforme app.engine_params en kwargs backend.

    Règles :
    - ne pas inventer ;
    - convertir les aliases historiques ;
    - convertir mm → m quand les clés *_mm existent ;
    - conserver toute clé acceptée par dimensionner_systeme_shsem ;
    - filtrer selon la signature réelle.
    """
    out: dict[str, Any] = {}

    # 1) Copier / parser les clés existantes.
    for key, value in dict(params or {}).items():
        if value in ("", "...", "INCONNU", "None", "none", "null"):
            continue

        out[str(key)] = _normalise_basic_value(str(key), value)

    # 2) Aliases historiques.
    for old_key, new_key in LEGACY_ALIAS_MAP.items():
        if old_key in out and new_key not in out:
            out[new_key] = _normalise_basic_value(new_key, out[old_key])

    # 3) Architecture : compatibilité architecture_choice.
    arch = _first_non_empty(
        out.get("architecture_moteur"),
        out.get("architecture_forcee"),
        out.get("architecture"),
    )
    if arch:
        out.setdefault("architecture_moteur", arch)
        out.setdefault("architecture_forcee", arch)

    # 4) Alésage/course mm → m.
    alesage_mm = _safe_float(out.get("alesage_mm"))
    if alesage_mm is not None and "alesage_m" not in out:
        out["alesage_m"] = alesage_mm / 1000.0

    course_mm = _safe_float(out.get("course_mm"))
    if course_mm is not None and "course_m" not in out:
        out["course_m"] = course_mm / 1000.0

    # 5) Nombre de cylindres.
    if "nombre_cylindres" in out:
        n = _safe_int(out.get("nombre_cylindres"))
        if n is not None:
            out["nombre_cylindres"] = n

    # 6) Puissance : normalisation stricte.
    out = _normalise_power_from_legacy(out)

    # 7) Filtrer selon backend/main.py.
    if dimensionner_systeme_shsem is not None:
        out = _filter_kwargs_for_signature(dimensionner_systeme_shsem, out)

    return out


def validate_backend_args(args: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    if not _has_power_target(args):
        errors.append(
            "Cible de puissance absente : renseigner puissance_traction_kw, "
            "production_electrique_sortie_w, puissance_bus_dc_w ou puissance_moteur_requise_W."
        )

    for key in ("puissance_traction_kw", "production_electrique_sortie_w", "puissance_bus_dc_w", "puissance_moteur_requise_W"):
        value = args.get(key)
        if value is None:
            continue

        number = _safe_float(value)
        if number is None:
            errors.append(f"{key} doit être numérique.")
        elif number <= 0:
            errors.append(f"{key} doit être > 0.")

    for key in ("nombre_cylindres", "temps_moteur"):
        value = args.get(key)
        if value is None:
            continue

        number = _safe_int(value)
        if number is None:
            errors.append(f"{key} doit être un entier.")

    if args.get("temps_moteur") is not None and args.get("temps_moteur") not in {2, 4}:
        errors.append("temps_moteur doit valoir 2 ou 4.")

    for key in ("alesage_m", "course_m", "pme_pa", "pression_max_pa", "tension_bus_dc_v"):
        value = args.get(key)
        if value is None:
            continue

        number = _safe_float(value)
        if number is None:
            errors.append(f"{key} doit être numérique.")
        elif number <= 0:
            errors.append(f"{key} doit être > 0.")

    return errors


# =============================================================================
# UI state
# =============================================================================

@dataclass
class StepWidgets:
    badge: StatusBadge
    label: Label
    detail: Label


# =============================================================================
# Loading screen
# =============================================================================

class LoadingScreen(Screen):
    steps: tuple[str, ...] = (
        "lecture des paramètres front",
        "normalisation puissance et aliases",
        "validation des entrées backend",
        "appel backend/main.py",
        "orchestration STHO-ME",
        "adaptation du rapport UI",
        "stockage rapports complets",
        "choix de la prochaine vue",
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._run_id = 0
        self._running = False
        self._cancel_requested = False
        self.step_widgets: list[StepWidgets] = []

        self.status: Label
        self.progress: ProgressBar
        self.args_preview: TextInput
        self.summary_box: BoxLayout

        self._build_ui()

    # -------------------------------------------------------------------------
    # Construction UI
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.clear_widgets()

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(54), dp(34)],
            spacing=dp(16),
        )

        panel = NeoCard(
            orientation="vertical",
            padding=dp(24),
            spacing=dp(12),
            size_hint_y=None,
            height=dp(520),
        )

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38),
            spacing=dp(10),
        )
        header.add_widget(SectionTitle(text="CALCUL EN COURS"))
        self.header_badge = StatusBadge(status="calculée", text="PRÉPARATION", size_hint_x=None, width=dp(140))
        header.add_widget(self.header_badge)
        panel.add_widget(header)

        self.status = Label(
            text="Préparation du calcul...",
            color=COLORS["BFW"],
            font_size="17sp",
            bold=True,
            size_hint_y=None,
            height=dp(36),
            halign="left",
            valign="middle",
        )
        self.status.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        panel.add_widget(self.status)

        self.progress = ProgressBar(
            max=len(self.steps),
            value=0,
            size_hint_y=None,
            height=dp(18),
        )
        panel.add_widget(self.progress)

        steps_grid = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        steps_grid.bind(minimum_height=steps_grid.setter("height"))

        self.step_widgets = []
        for step in self.steps:
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(44),
                spacing=dp(10),
            )

            badge = StatusBadge(status="partiel", text="ATTENTE", size_hint_x=None, width=dp(110))
            row.add_widget(badge)

            text_box = BoxLayout(orientation="vertical", spacing=dp(0))
            label = Label(
                text=step,
                color=COLORS["BFW"],
                bold=True,
                font_size="12sp",
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(22),
            )
            detail = Label(
                text="",
                color=COLORS["GS"],
                font_size="10sp",
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(18),
            )
            label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            detail.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))

            text_box.add_widget(label)
            text_box.add_widget(detail)
            row.add_widget(text_box)

            steps_grid.add_widget(row)
            self.step_widgets.append(StepWidgets(badge=badge, label=label, detail=detail))

        panel.add_widget(steps_grid)

        button_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            spacing=dp(10),
        )

        btn_cancel = ModernButton(text="ANNULER", font_size="11sp")
        btn_cancel.bind(on_release=self.cancel)
        button_row.add_widget(btn_cancel)

        btn_params = ModernButton(text="PARAMÈTRES", font_size="11sp")
        btn_params.bind(on_release=lambda *_: self._go("edit_parameters"))
        button_row.add_widget(btn_params)

        btn_home = ModernButton(text="ACCUEIL", font_size="11sp")
        btn_home.bind(on_release=lambda *_: self._go("home"))
        button_row.add_widget(btn_home)

        panel.add_widget(button_row)

        root.add_widget(panel)

        bottom = BoxLayout(
            orientation="horizontal",
            spacing=dp(14),
            size_hint_y=None,
            height=dp(210),
        )

        preview_card = PremiumCard(title="Arguments backend", size_hint_x=0.62)
        self.args_preview = TextInput(
            readonly=True,
            multiline=True,
            background_color=COLORS["BL"],
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["RS"],
            font_size="11sp",
        )
        preview_card.add_widget(self.args_preview)
        bottom.add_widget(preview_card)

        summary_card = PremiumCard(title="Résumé calcul", size_hint_x=0.38)
        self.summary_box = BoxLayout(orientation="vertical", spacing=dp(2))
        summary_card.add_widget(self.summary_box)
        bottom.add_widget(summary_card)

        root.add_widget(bottom)
        self.add_widget(root)

    # -------------------------------------------------------------------------
    # Cycle de vie
    # -------------------------------------------------------------------------

    def on_enter(self, *_: Any) -> None:
        if self._running:
            return

        self._run_id += 1
        self._cancel_requested = False
        self._running = True

        self._reset_ui()
        threading.Thread(
            target=self._run_backend,
            args=(self._run_id,),
            daemon=True,
        ).start()

    def on_leave(self, *_: Any) -> None:
        # Ne tue pas le thread brutalement ; empêche juste les navigations obsolètes.
        self._cancel_requested = True

    def cancel(self, *_: Any) -> None:
        self._cancel_requested = True
        self._set_status("Annulation demandée. Le calcul en cours sera ignoré à son retour.", badge="alerte")
        self._go("dashboard")

    # -------------------------------------------------------------------------
    # UI updates thread-safe
    # -------------------------------------------------------------------------

    def _reset_ui(self) -> None:
        self.header_badge.status = "calculée"
        self.header_badge.text = "PRÉPARATION"
        self.status.text = "Démarrage du calcul..."
        self.progress.value = 0
        self.args_preview.text = ""

        self.summary_box.clear_widgets()
        self.summary_box.add_widget(MetricRow("État", "Préparation", "", "calculée"))
        self.summary_box.add_widget(MetricRow("Backend", "backend.main", "", "partiel"))
        self.summary_box.add_widget(MetricRow("Rapport", "Non généré", "", "missing"))

        for widgets in self.step_widgets:
            widgets.badge.status = "partiel"
            widgets.badge.text = "ATTENTE"
            widgets.label.color = COLORS["BFW"]
            widgets.detail.text = ""

    def _set_status(self, text: str, *, badge: str = "calculée") -> None:
        def apply(_: Any = None) -> None:
            self.status.text = text
            self.header_badge.status = badge
            self.header_badge.text = badge.upper()

        Clock.schedule_once(apply, 0)

    def _set_step(self, index: int, status: str, detail: str = "") -> None:
        def apply(_: Any = None) -> None:
            if not (0 <= index < len(self.step_widgets)):
                return

            widgets = self.step_widgets[index]
            widgets.badge.status = status
            widgets.badge.text = {
                "ok": "OK",
                "erreur": "ERREUR",
                "alerte": "ALERTE",
                "calculée": "EN COURS",
                "partiel": "ATTENTE",
                "missing": "MANQUANT",
            }.get(status, status.upper())

            widgets.detail.text = _short_text(detail, 180)

            if status == "ok":
                self.progress.value = max(self.progress.value, index + 1)

        Clock.schedule_once(apply, 0)

    def _set_args_preview(self, args: Mapping[str, Any]) -> None:
        def apply(_: Any = None) -> None:
            lines = []
            for key in sorted(args.keys()):
                value = args[key]
                if isinstance(value, Mapping):
                    lines.append(f"{key}: <dict:{len(value)}>")
                elif isinstance(value, list):
                    lines.append(f"{key}: <list:{len(value)}>")
                else:
                    lines.append(f"{key}: {value!r}")
            self.args_preview.text = "\n".join(lines)

        Clock.schedule_once(apply, 0)

    def _set_summary(self, rows: Sequence[tuple[str, Any, str]]) -> None:
        def apply(_: Any = None) -> None:
            self.summary_box.clear_widgets()
            for label, value, status in rows:
                self.summary_box.add_widget(MetricRow(label, value, "", status))

        Clock.schedule_once(apply, 0)

    # -------------------------------------------------------------------------
    # Backend flow
    # -------------------------------------------------------------------------

    def _run_backend(self, run_id: int) -> None:
        app = App.get_running_app()

        try:
            if refresh_backend_data is None:
                raise RuntimeError(
                    "Backend indisponible : impossible d'importer frontend.main.refresh_backend_data."
                )

            self._set_step(0, "calculée", "Lecture de app.engine_params.")
            raw_params = dict(getattr(app, "engine_params", {}) or {})
            if not raw_params:
                raise ValueError("Aucun paramètre moteur disponible dans app.engine_params.")
            self._set_step(0, "ok", f"{len(raw_params)} paramètre(s) lu(s).")

            self._set_step(1, "calculée", "Conversion aliases, unités et puissance.")
            backend_args = build_backend_args(raw_params)
            self._set_args_preview(backend_args)
            self._set_step(1, "ok", f"{len(backend_args)} argument(s) backend préparé(s).")

            self._set_step(2, "calculée", "Validation minimale avant backend.")
            validation_errors = validate_backend_args(backend_args)
            if validation_errors:
                raise ValueError("\n".join(validation_errors))
            self._set_step(2, "ok", "Entrées minimales validées.")

            accepted_keys = _signature_keys(dimensionner_systeme_shsem)
            ignored = sorted(set(raw_params.keys()) - set(backend_args.keys()))
            self._set_summary(
                [
                    ("Paramètres front", len(raw_params), "ok"),
                    ("Arguments backend", len(backend_args), "ok"),
                    ("Signature backend", len(accepted_keys), "ok" if accepted_keys else "partiel"),
                    ("Ignorés / non signés", len(ignored), "alerte" if ignored else "ok"),
                ]
            )

            if self._cancel_requested or run_id != self._run_id:
                return

            self._set_step(3, "calculée", "Appel frontend.main.refresh_backend_data.")
            self._set_status("Appel du frontend orchestrateur.", badge="calculée")

            state = refresh_backend_data(backend_args)
            report = state.get("raw_report") if isinstance(state, Mapping) else None

            if not isinstance(report, dict):
                raise RuntimeError(f"Le backend a retourné {type(report).__name__}, attendu dict.")

            if report.get("erreur"):
                raise RuntimeError(str(report.get("erreur")))

            self._set_step(3, "ok", "Rapport backend reçu.")

            if self._cancel_requested or run_id != self._run_id:
                return

            self._set_step(4, "calculée", "Analyse du rapport système.")
            report_summary = self._summarise_report(report)
            self._set_summary(report_summary)
            self._set_step(4, "ok", "Rapport analysé.")

            self._set_step(5, "calculée", "Adaptation rapport backend → UI.")
            ui_report = self._adapt_report(report)
            self._set_step(5, "ok", "ui_report généré.")

            self._set_step(6, "calculée", "Stockage app.raw_backend_report / backend_report / full_report.")
            self._store_reports(app, report, ui_report, backend_args)
            self._set_step(6, "ok", "Rapports stockés.")

            self._set_step(7, "calculée", "Détermination de la prochaine vue.")
            target = self._choose_next_screen(app, report, ui_report, raw_params)
            self._set_step(7, "ok", f"Navigation vers {target}.")

            self._set_status("Calcul terminé.", badge="ok")

            if self._cancel_requested or run_id != self._run_id:
                return

            Clock.schedule_once(lambda *_: self._go(target), 0)

        except Exception as exc:
            trace = traceback.format_exc()
            Clock.schedule_once(lambda *_: self._show_error(exc, trace), 0)

        finally:
            self._running = False

    def _adapt_report(self, report: dict[str, Any]) -> dict[str, Any]:
        if adapt_backend_report is None:
            return self._minimal_ui_report(report)

        adapted = adapt_backend_report(report)
        if not isinstance(adapted, dict):
            return self._minimal_ui_report(report)

        # Ajouter des blocs que les écrans musclés attendent.
        adapted.setdefault("backend_report_present", True)
        adapted.setdefault("resume_gui", report.get("resume_gui") or {})
        adapted.setdefault("cao", report.get("cao") or {})
        adapted.setdefault("raw_sections", self._build_raw_sections(report))

        if "architecture_candidates" not in adapted:
            adapted["architecture_candidates"] = self._extract_candidates_safe(report)

        return adapted

    def _minimal_ui_report(self, report: dict[str, Any]) -> dict[str, Any]:
        resume = _safe_dict(report.get("resume_gui"))
        cao = _safe_dict(report.get("cao"))
        candidates = self._extract_candidates_safe(report)

        energy_chain = []
        if resume.get("P_bus_dc_design_w") is not None:
            energy_chain.append(
                {
                    "label": "Puissance bus DC",
                    "value": resume.get("P_bus_dc_design_w"),
                    "unit": "W",
                    "status": "ok",
                }
            )

        if resume.get("Architecture") is not None:
            energy_chain.append(
                {
                    "label": "Architecture",
                    "value": resume.get("Architecture"),
                    "unit": "",
                    "status": "ok",
                }
            )

        if resume.get("N_cyl") is not None:
            energy_chain.append(
                {
                    "label": "Nombre cylindres",
                    "value": resume.get("N_cyl"),
                    "unit": "",
                    "status": "ok",
                }
            )

        return {
            "is_empty": False,
            "backend_report_present": True,
            "resume_gui": resume,
            "cao": cao,
            "architecture_candidates": candidates,
            "raw_sections": self._build_raw_sections(report),
            "dashboard": {
                "title": "STHOME COCKPIT",
                "summary": {
                    "missing_count": self._count_unknowns(report),
                    "alert_count": self._count_alerts(report),
                },
                "energy_chain": energy_chain,
                "subsystems": self._build_subsystems(report),
                "alerts": [],
                "actions": [
                    {"label": "Architecture", "target": "architecture_choice"},
                    {"label": "Audit", "target": "energy_audit"},
                    {"label": "Exports", "target": "exports"},
                    {"label": "Paramètres", "target": "edit_parameters"},
                    {"label": "JSON", "target": "raw_report"},
                ],
            },
        }

    def _store_reports(
        self,
        app: Any,
        report: dict[str, Any],
        ui_report: dict[str, Any],
        backend_args: Mapping[str, Any],
    ) -> None:
        report = dict(report)
        report.setdefault("_frontend_backend_args", _jsonable(dict(backend_args)))
        report.setdefault("_frontend_source", "LoadingScreen")

        existing_ui = _safe_dict(getattr(app, "ui_report", {}) or {})
        merged_ui = _merge_dict_non_none(existing_ui, ui_report)

        app.raw_backend_report = report
        app.backend_report = report
        app.full_report = report
        app.last_backend_report = report
        app.ui_report = merged_ui

    def _choose_next_screen(
        self,
        app: Any,
        report: dict[str, Any],
        ui_report: dict[str, Any],
        raw_params: Mapping[str, Any],
    ) -> str:
        candidates = _safe_list(ui_report.get("architecture_candidates")) or self._extract_candidates_safe(report)
        has_arch = bool(
            _first_non_empty(
                raw_params.get("architecture"),
                raw_params.get("architecture_moteur"),
                raw_params.get("architecture_forcee"),
                _safe_dict(getattr(app, "engine_params", {})).get("architecture"),
            )
        )

        if candidates and not has_arch:
            return "architecture_choice"

        return "dashboard"

    # -------------------------------------------------------------------------
    # Rapport helpers
    # -------------------------------------------------------------------------

    def _extract_candidates_safe(self, report: Mapping[str, Any]) -> list[Any]:
        if extract_architecture_candidates is not None:
            try:
                candidates = extract_architecture_candidates(report)
                if isinstance(candidates, list):
                    return candidates
            except Exception:
                pass

        resume = _safe_dict(report.get("resume_gui"))
        if resume.get("Architecture") or resume.get("N_cyl"):
            return [
                {
                    "architecture": resume.get("Architecture"),
                    "nombre_cylindres": resume.get("N_cyl"),
                    "alesage_m": (_safe_float(resume.get("Bore_mm")) or 0) / 1000.0 if resume.get("Bore_mm") is not None else None,
                    "course_m": (_safe_float(resume.get("Stroke_mm")) or 0) / 1000.0 if resume.get("Stroke_mm") is not None else None,
                    "cylindree_totale_cc": resume.get("vd_tot_cc"),
                    "score": _first_non_empty(
                        resume.get("score_global_100"),
                        resume.get("score_coherence_100"),
                    ),
                    "description": "Candidat reconstruit depuis resume_gui.",
                    "backend_source_path": "resume_gui",
                }
            ]

        return []

    def _build_raw_sections(self, report: Mapping[str, Any]) -> list[dict[str, Any]]:
        sections = []

        for name, key in (
            ("Résumé GUI", "resume_gui"),
            ("Synthèse", "synthese"),
            ("Système complet", "systeme_complet"),
            ("CAO", "cao"),
            ("Analyses composants", "analyses_composants"),
            ("Construction pièces", "construction_pieces"),
            ("Rapports pièces", "rapports_pieces"),
            ("Optimisation", "optimisation"),
            ("Legacy", "legacy"),
            ("Inconnues", "inconnues"),
            ("Alertes", "alertes"),
        ):
            value = report.get(key)
            if value:
                sections.append({"name": name, "value": value})

        if not sections:
            sections.append({"name": "Rapport backend complet", "value": dict(report)})

        return sections

    def _build_subsystems(self, report: Mapping[str, Any]) -> list[dict[str, str]]:
        subs = []

        for name, value in (
            ("Système complet", report.get("systeme_complet")),
            ("CAO", report.get("cao")),
            ("Analyses composants", report.get("analyses_composants")),
            ("Construction pièces", report.get("construction_pieces")),
            ("Rapports pièces", report.get("rapports_pieces")),
            ("Optimisation", report.get("optimisation")),
        ):
            if value:
                status = "alerte" if self._count_unknowns(value) else "ok"
            else:
                status = "missing"

            subs.append({"name": name, "status": status})

        return subs

    def _summarise_report(self, report: Mapping[str, Any]) -> list[tuple[str, Any, str]]:
        resume = _safe_dict(report.get("resume_gui"))

        return [
            ("Rapport", "reçu", "ok"),
            ("Architecture", resume.get("Architecture") or "—", "ok" if resume.get("Architecture") else "missing"),
            ("Cylindres", resume.get("N_cyl") or "—", "ok" if resume.get("N_cyl") else "missing"),
            ("Inconnues", self._count_unknowns(report), "alerte" if self._count_unknowns(report) else "ok"),
            ("Alertes", self._count_alerts(report), "alerte" if self._count_alerts(report) else "ok"),
        ]

    def _count_unknowns(self, value: Any) -> int:
        total = 0

        def walk(node: Any) -> None:
            nonlocal total
            if isinstance(node, Mapping):
                inc = node.get("inconnues")
                if isinstance(inc, Mapping):
                    for values in inc.values():
                        if isinstance(values, list):
                            total += len(values)

                inconnues_cao = node.get("inconnues_cao")
                if isinstance(inconnues_cao, list):
                    total += len(inconnues_cao)

                for child in node.values():
                    if isinstance(child, (Mapping, list)):
                        walk(child)

            elif isinstance(node, list):
                for child in node:
                    if isinstance(child, (Mapping, list)):
                        walk(child)

        walk(value)
        return total

    def _count_alerts(self, value: Any) -> int:
        total = 0

        def walk(node: Any) -> None:
            nonlocal total
            if isinstance(node, Mapping):
                alerts = node.get("alertes")
                if isinstance(alerts, Mapping):
                    for values in alerts.values():
                        if isinstance(values, list):
                            total += len(values)

                for child in node.values():
                    if isinstance(child, (Mapping, list)):
                        walk(child)

            elif isinstance(node, list):
                for child in node:
                    if isinstance(child, (Mapping, list)):
                        walk(child)

        walk(value)
        return total

    # -------------------------------------------------------------------------
    # Erreurs / navigation
    # -------------------------------------------------------------------------

    def _show_error(self, exc: BaseException, trace: str) -> None:
        self._set_status("Erreur backend.", badge="erreur")

        try:
            app = App.get_running_app()
            app.last_error_payload = {
                "message": str(exc),
                "trace": trace,
                "source": "frontend.gui.loading.LoadingScreen",
                "severity": "erreur",
                "context": {
                    "engine_params": _jsonable(getattr(app, "engine_params", {}) or {}),
                    "args_preview": self.args_preview.text,
                },
            }
        except Exception:
            pass

        try:
            screen = self.manager.get_screen("error")
            if hasattr(screen, "set_error_payload"):
                screen.set_error_payload(App.get_running_app().last_error_payload)
            elif hasattr(screen, "set_error"):
                screen.set_error(str(exc), trace)
            self.manager.current = "error"
        except Exception:
            raise exc

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name

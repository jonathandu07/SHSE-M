from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget

from frontend.gui.components import (
    COLORS,
    ModernButton,
    NeumorphicInput,
    SectionTitle,
    NeoCard,
    MetricRow,
    StatusBadge,
    PremiumCard,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = PROJECT_ROOT / "frontend" / "images" / "logo.png"

CH_TO_W = 735.49875
KW_TO_W = 1000.0


# =============================================================================
# Helpers
# =============================================================================

def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _safe_float(value: Any) -> Optional[float]:
    try:
        v = float(str(value).strip().replace(",", "."))
    except Exception:
        return None
    return v if math.isfinite(v) else None


def _fmt(value: Any, digits: int = 5) -> str:
    if not _is_finite(value):
        return "—"

    v = float(value)
    av = abs(v)

    if av >= 1_000_000:
        return f"{v / 1_000_000:.{digits}g} M"
    if av >= 1_000:
        return f"{v / 1_000:.{digits}g} k"
    if 0.0 < av < 0.001:
        return f"{v:.{digits}e}"

    return f"{v:.{digits}g}"


def _label(
    text: str,
    *,
    color: Any = None,
    bold: bool = False,
    size: str = "13sp",
    height: int = 28,
) -> Label:
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


def convert_power(value: float, unit: str) -> dict[str, float]:
    if unit == "kW":
        power_kw = value
        power_w = value * KW_TO_W
    elif unit == "W":
        power_w = value
        power_kw = value / KW_TO_W
    elif unit == "ch":
        power_w = value * CH_TO_W
        power_kw = power_w / KW_TO_W
    else:
        raise ValueError(f"Unité non reconnue : {unit!r}")

    return {
        "power_kw": float(power_kw),
        "power_w": float(power_w),
        "power_ch": float(power_w / CH_TO_W),
    }


# =============================================================================
# Home screen
# =============================================================================

class HomeScreen(Screen):
    """
    Écran d'accueil / saisie initiale.

    Objectif :
    - afficher immédiatement la donnée saisie ;
    - normaliser la puissance pour backend/main.py ;
    - conserver les clés legacy utilisées par les anciens écrans ;
    - fournir aussi les clés strictes attendues par les écrans musclés.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.error_label: Label
        self.preview_badge: StatusBadge
        self.preview_raw: Label
        self.preview_kw: Label
        self.preview_w: Label
        self.preview_ch: Label
        self.preview_payload: Label
        self.power_input: NeumorphicInput
        self.unit_spinner: Spinner

        self._build_ui()

    # -------------------------------------------------------------------------
    # Construction UI
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.clear_widgets()

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(42), dp(28)],
            spacing=dp(18),
        )

        root.add_widget(self._hero())

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(16),
            size_hint_y=None,
            padding=[0, dp(6)],
        )
        content.bind(minimum_height=content.setter("height"))

        content.add_widget(self._input_card())
        content.add_widget(self._preview_card())
        content.add_widget(self._help_card())

        scroll.add_widget(content)
        root.add_widget(scroll)

        self.add_widget(root)

    def _hero(self) -> BoxLayout:
        hero = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(120),
            spacing=dp(20),
        )

        if LOGO_PATH.exists():
            hero.add_widget(
                Image(
                    source=str(LOGO_PATH),
                    size_hint=(None, None),
                    size=(dp(88), dp(88)),
                    allow_stretch=True,
                    keep_ratio=True,
                )
            )

        title_box = BoxLayout(orientation="vertical", spacing=dp(2))

        title = Label(
            text="STHOME",
            color=COLORS["BFW"],
            bold=True,
            font_size="44sp",
            halign="left",
            valign="bottom",
            size_hint_y=None,
            height=dp(62),
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        title_box.add_widget(title)

        subtitle = Label(
            text="Cockpit de dimensionnement thermo-hybride",
            color=COLORS["NG"],
            font_size="18sp",
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(34),
        )
        subtitle.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        title_box.add_widget(subtitle)

        title_box.add_widget(
            Label(
                text="La donnée saisie est affichée, convertie et envoyée explicitement au backend.",
                color=COLORS["GS"],
                font_size="12sp",
                halign="left",
                valign="top",
            )
        )

        hero.add_widget(title_box)
        hero.add_widget(Widget())

        return hero

    def _input_card(self) -> NeoCard:
        card = NeoCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(440),
            spacing=dp(16),
            padding=dp(26),
        )

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
            spacing=dp(10),
        )
        header.add_widget(SectionTitle(text="PUISSANCE DE SORTIE DEMANDÉE"))
        header.add_widget(StatusBadge(status="saisie"))
        card.add_widget(header)

        intro = Label(
            text=(
                "Saisis la puissance de départ. La valeur reste visible ci-dessous, "
                "puis elle est normalisée en kW et en W pour le backend."
            ),
            color=COLORS["GS"],
            font_size="14sp",
            size_hint_y=None,
            height=dp(50),
            halign="left",
            valign="top",
        )
        intro.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        card.add_widget(intro)

        form = BoxLayout(
            orientation="horizontal",
            spacing=dp(18),
            size_hint_y=None,
            height=dp(100),
        )

        self.power_input = NeumorphicInput(
            text="",
            hint_text="ex : 100",
            size_hint_x=0.70,
            font_size="30sp",
            halign="center",
        )

        # Correction visibilité forte : couleur texte / curseur / hint explicites.
        self.power_input.foreground_color = COLORS["BFW"]
        self.power_input.cursor_color = COLORS["RS"]
        self.power_input.hint_text_color = COLORS["BFW_35"]
        self.power_input.background_color = (0, 0, 0, 0)

        self.power_input.bind(text=lambda *_: self._update_preview())

        self.unit_spinner = Spinner(
            text="kW",
            values=("kW", "W", "ch"),
            size_hint_x=0.30,
            background_normal="",
            background_color=COLORS["BFW"],
            color=COLORS["BL"],
            bold=True,
            font_size="18sp",
        )
        self.unit_spinner.bind(text=lambda *_: self._update_preview())

        form.add_widget(self.power_input)
        form.add_widget(self.unit_spinner)
        card.add_widget(form)

        presets = GridLayout(
            cols=4,
            spacing=dp(10),
            size_hint_y=None,
            height=dp(46),
        )

        for label, value, unit in (
            ("10 kW", "10", "kW"),
            ("50 kW", "50", "kW"),
            ("100 kW", "100", "kW"),
            ("250 kW", "250", "kW"),
        ):
            btn = ModernButton(text=label, font_size="11sp")
            btn.bind(on_release=lambda *_args, v=value, u=unit: self._set_power(v, u))
            presets.add_widget(btn)

        card.add_widget(presets)

        self.error_label = Label(
            text="",
            color=COLORS["RS"],
            bold=True,
            size_hint_y=None,
            height=dp(34),
            halign="left",
            valign="middle",
        )
        self.error_label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        card.add_widget(self.error_label)

        actions = BoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            size_hint_y=None,
            height=dp(62),
        )

        btn_calc = ModernButton(text="CALCULER", font_size="15sp")
        btn_calc.bind(on_release=self._launch)
        actions.add_widget(btn_calc)

        btn_reset = ModernButton(text="RÉINITIALISER", size_hint_x=None, width=dp(160), font_size="12sp")
        btn_reset.bind(on_release=self._reset)
        actions.add_widget(btn_reset)

        btn_dash = ModernButton(text="DASHBOARD", size_hint_x=None, width=dp(150), font_size="12sp")
        btn_dash.bind(on_release=lambda *_: self._go("dashboard"))
        actions.add_widget(btn_dash)

        card.add_widget(actions)

        return card

    def _preview_card(self) -> PremiumCard:
        card = PremiumCard(
            title="DONNÉE SAISIE / NORMALISATION BACKEND",
            size_hint_y=None,
            height=dp(250),
        )

        self.preview_badge = StatusBadge(
            status="missing",
            size_hint_y=None,
            height=dp(26),
        )
        card.add_widget(self.preview_badge)

        self.preview_raw = _label("Saisie visible : —", color=COLORS["BFW"], height=30)
        self.preview_kw = _label("Puissance normalisée : — kW", color=COLORS["BFW"], height=30)
        self.preview_w = _label("Puissance backend : — W", color=COLORS["BFW"], height=30)
        self.preview_ch = _label("Équivalent : — ch", color=COLORS["BFW"], height=30)
        self.preview_payload = _label(
            "Payload backend : aucune donnée prête.",
            color=COLORS["GS"],
            size="11sp",
            height=54,
        )

        card.add_widget(self.preview_raw)
        card.add_widget(self.preview_kw)
        card.add_widget(self.preview_w)
        card.add_widget(self.preview_ch)
        card.add_widget(self.preview_payload)

        return card

    def _help_card(self) -> PremiumCard:
        card = PremiumCard(
            title="CLÉS TRANSMISES AU BACKEND",
            size_hint_y=None,
            height=dp(180),
        )

        card.add_widget(MetricRow("Legacy conservé", "puissance_entree + unite_entree", "", "ok"))
        card.add_widget(MetricRow("Cible backend", "puissance_traction_kw", "", "ok"))
        card.add_widget(MetricRow("Sortie électrique", "production_electrique_sortie_w", "", "ok"))
        card.add_widget(MetricRow("Bus DC initial", "puissance_bus_dc_w", "", "ok"))

        info = Label(
            text=(
                "Ces clés évitent que les écrans suivants affichent des inconnues uniquement "
                "par absence de propagation des données saisies."
            ),
            color=COLORS["GS"],
            font_size="11sp",
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(38),
        )
        info.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        card.add_widget(info)

        return card

    # -------------------------------------------------------------------------
    # Cycle de vie
    # -------------------------------------------------------------------------

    def on_enter(self, *_: Any) -> None:
        self.error_label.text = ""
        self._restore_existing_input()
        self._update_preview()

    def _restore_existing_input(self) -> None:
        app = App.get_running_app()
        params = dict(getattr(app, "engine_params", {}) or {})

        # Priorité à la saisie brute si elle existe encore.
        raw_value = params.get("puissance_entree")
        raw_unit = params.get("unite_entree")

        if raw_value is not None and raw_unit in {"kW", "W", "ch"}:
            self.power_input.text = str(raw_value)
            self.unit_spinner.text = str(raw_unit)
            return

        # Sinon reconstruction depuis les clés backend.
        kw = _safe_float(params.get("puissance_traction_kw"))
        if kw is not None and kw > 0:
            self.power_input.text = _fmt(kw)
            self.unit_spinner.text = "kW"
            return

        w = _safe_float(params.get("production_electrique_sortie_w"))
        if w is not None and w > 0:
            self.power_input.text = _fmt(w / KW_TO_W)
            self.unit_spinner.text = "kW"

    # -------------------------------------------------------------------------
    # Preview / validation
    # -------------------------------------------------------------------------

    def _set_power(self, value: str, unit: str) -> None:
        self.power_input.text = str(value)
        self.unit_spinner.text = str(unit)
        self._update_preview()

    def _reset(self, *_: Any) -> None:
        self.power_input.text = ""
        self.unit_spinner.text = "kW"
        self.error_label.text = ""

        app = App.get_running_app()
        app.engine_params = {}
        app.raw_backend_report = {}
        app.backend_report = {}
        app.full_report = {}
        app.ui_report = {}

        self._update_preview()

    def _read_power(self) -> tuple[Optional[float], str, Optional[dict[str, float]], Optional[str]]:
        raw = (self.power_input.text or "").strip().replace(",", ".")
        unit = self.unit_spinner.text

        if not raw:
            return None, unit, None, "Valeur absente : indique une puissance."

        value = _safe_float(raw)
        if value is None:
            return None, unit, None, "Valeur invalide : nombre attendu."

        if value <= 0:
            return value, unit, None, "Valeur invalide : puissance strictement positive attendue."

        if unit not in {"kW", "W", "ch"}:
            return value, unit, None, "Unité absente : choisis kW, W ou ch."

        try:
            converted = convert_power(value, unit)
        except Exception as exc:
            return value, unit, None, str(exc)

        return value, unit, converted, None

    def _update_preview(self) -> None:
        value, unit, converted, error = self._read_power()

        if error:
            self.preview_badge.status = "missing"
            self.preview_badge.text = "INCOMPLET"
            self.preview_raw.text = f"Saisie visible : {(self.power_input.text or '—')} {unit}"
            self.preview_kw.text = "Puissance normalisée : — kW"
            self.preview_w.text = "Puissance backend : — W"
            self.preview_ch.text = "Équivalent : — ch"
            self.preview_payload.text = "Payload backend : aucune donnée prête."
            return

        assert value is not None
        assert converted is not None

        power_kw = converted["power_kw"]
        power_w = converted["power_w"]
        power_ch = converted["power_ch"]

        self.preview_badge.status = "ok"
        self.preview_badge.text = "PRÊT"

        self.preview_raw.text = f"Saisie visible : {_fmt(value)} {unit}"
        self.preview_kw.text = f"Puissance normalisée : {_fmt(power_kw)} kW"
        self.preview_w.text = f"Puissance backend : {_fmt(power_w)} W"
        self.preview_ch.text = f"Équivalent : {_fmt(power_ch)} ch"

        self.preview_payload.text = (
            "Payload backend : "
            f"puissance_traction_kw={_fmt(power_kw)} ; "
            f"production_electrique_sortie_w={_fmt(power_w)} ; "
            f"puissance_bus_dc_w={_fmt(power_w)}"
        )

    # -------------------------------------------------------------------------
    # Lancement backend
    # -------------------------------------------------------------------------

    def _launch(self, *_: Any) -> None:
        value, unit, converted, error = self._read_power()

        if error:
            self.error_label.text = error
            self._update_preview()
            return

        assert value is not None
        assert converted is not None

        power_kw = converted["power_kw"]
        power_w = converted["power_w"]
        power_ch = converted["power_ch"]

        app = App.get_running_app()

        # On conserve les anciens noms, mais on ajoute les clés que backend/main.py
        # et les écrans musclés savent exploiter directement.
        app.engine_params = {
            # Ancien format front
            "puissance_entree": float(value),
            "unite_entree": str(unit),

            # Format strict backend
            "puissance_traction_kw": float(power_kw),
            "production_electrique_sortie_w": float(power_w),
            "puissance_bus_dc_w": float(power_w),
            "puissance_moteur_requise_W": float(power_w),

            # Métadonnées lisibles dans les écrans audit/export/debug
            "saisie_home": {
                "valeur": float(value),
                "unite": str(unit),
                "puissance_kw": float(power_kw),
                "puissance_w": float(power_w),
                "puissance_ch": float(power_ch),
                "source": "HomeScreen",
            },
        }

        app.raw_backend_report = {}
        app.backend_report = {}
        app.full_report = {}

        app.ui_report = {
            "is_empty": False,
            "home_input": {
                "valeur": float(value),
                "unite": str(unit),
                "puissance_kw": float(power_kw),
                "puissance_w": float(power_w),
                "puissance_ch": float(power_ch),
            },
            "editable_parameters": [
                {
                    "key": "puissance_traction_kw",
                    "label": "Puissance traction",
                    "value": float(power_kw),
                    "unit": "kW",
                    "source": "SAISIE_HOME",
                    "editable": True,
                    "category": "Puissance & mission",
                    "type": "float",
                },
                {
                    "key": "production_electrique_sortie_w",
                    "label": "Production électrique sortie",
                    "value": float(power_w),
                    "unit": "W",
                    "source": "SAISIE_HOME",
                    "editable": True,
                    "category": "Puissance & mission",
                    "type": "float",
                },
                {
                    "key": "puissance_bus_dc_w",
                    "label": "Puissance bus DC",
                    "value": float(power_w),
                    "unit": "W",
                    "source": "SAISIE_HOME",
                    "editable": True,
                    "category": "Batterie / Bus DC",
                    "type": "float",
                },
            ],
            "dashboard": {
                "title": "STHOME COCKPIT",
                "summary": {
                    "missing_count": 0,
                    "alert_count": 0,
                },
                "energy_chain": [
                    {
                        "label": "Puissance totale demandée",
                        "value": float(power_kw),
                        "unit": "kW",
                        "status": "ok",
                    },
                    {
                        "label": "Puissance backend",
                        "value": float(power_w),
                        "unit": "W",
                        "status": "ok",
                    },
                ],
            },
        }

        self.error_label.text = ""
        self._go("loading")

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name
# frontend/gui/missing_requirements.py
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from frontend.gui.components import (
    COLORS,
    EmptyState,
    FilterChips,
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    SearchBar,
    SectionTitle,
    StatusBadge,
)


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


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
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


def _short_text(value: Any, max_len: int = 130) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _normalise_text(value: Any) -> str:
    raw = str(value or "").lower()
    out = []
    for ch in raw:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    return "_".join(part for part in "".join(out).split("_") if part)


def _fmt_value(value: Any) -> str:
    if value is None:
        return "—"

    if isinstance(value, bool):
        return "Oui" if value else "Non"

    if _is_finite(value):
        v = float(value)
        av = abs(v)
        if av >= 1_000_000:
            return f"{v / 1_000_000:.4g} M"
        if av >= 1_000:
            return f"{v / 1_000:.4g} k"
        if 0 < av < 0.001:
            return f"{v:.4e}"
        return f"{v:.4g}"

    if isinstance(value, Mapping):
        return f"dict:{len(value)}"
    if isinstance(value, list):
        return f"list:{len(value)}"

    return _short_text(value, 60)


def _label(
    text: str,
    *,
    color: Any = None,
    bold: bool = False,
    size: str = "12sp",
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


# =============================================================================
# Inférence métier
# =============================================================================

FIELD_ALIASES: Dict[str, str] = {
    # Puissance
    "puissance": "puissance_traction_kw",
    "puissance_traction": "puissance_traction_kw",
    "puissance_demandee": "puissance_traction_kw",
    "puissance_totale": "puissance_traction_kw",
    "puissance_sortie": "production_electrique_sortie_w",
    "production_electrique": "production_electrique_sortie_w",
    "bus_dc": "puissance_bus_dc_w",
    "p_bus_dc": "puissance_bus_dc_w",

    # Architecture / moteur
    "architecture": "architecture_moteur",
    "architecture_moteur": "architecture_moteur",
    "architecture_forcee": "architecture_forcee",
    "cylindres": "nombre_cylindres",
    "nombre_cylindres": "nombre_cylindres",
    "nb_cyl": "nombre_cylindres",
    "n_cyl": "nombre_cylindres",
    "alesage": "alesage_m",
    "bore": "alesage_m",
    "diametre_piston": "alesage_m",
    "course": "course_m",
    "stroke": "course_m",
    "course_piston": "course_m",
    "rpm": "rpm_moteur_nominal",
    "regime": "rpm_moteur_nominal",
    "regime_moteur": "rpm_moteur_nominal",
    "pme": "pme_pa",
    "pression_moyenne_effective": "pme_pa",
    "pression_max": "pression_max_pa",
    "pmax": "pression_max_pa",
    "force_bielle": "force_bielle_N",
    "couple": "couple_moteur_max_Nm",
    "couple_moteur": "couple_moteur_max_Nm",

    # Véhicule / batterie
    "masse": "masse_kg",
    "masse_vehicule": "masse_kg",
    "vitesse": "vitesse_ms",
    "acceleration": "acceleration_ms2",
    "distance": "distance_km",
    "batterie": "energie_utile_imposee_kwh",
    "energie_batterie": "energie_utile_imposee_kwh",
    "tension": "tension_bus_dc_v",
    "tension_bus": "tension_bus_dc_v",

    # Alternateur / boîte
    "alternateur": "vitesse_alternateur_rpm",
    "vitesse_alternateur": "vitesse_alternateur_rpm",
    "rendement_boite": "rendement_boite",
    "rapports_boite": "rapports_boite_candidates",
}

SUBSYSTEM_KEYWORDS: Dict[str, str] = {
    "moteur_thermique": "Moteur thermique",
    "thermal": "Moteur thermique",
    "piston": "Moteur thermique",
    "cylindre": "Moteur thermique",
    "bielle": "Moteur thermique",
    "vilebrequin": "Moteur thermique",
    "deplaceur": "Moteur thermique",

    "moteur_electrique": "Moteur électrique",
    "electric": "Moteur électrique",
    "traction": "Moteur électrique",

    "batterie": "Batterie / Bus DC",
    "battery": "Batterie / Bus DC",
    "bus_dc": "Batterie / Bus DC",

    "alternateur": "Alternateur",
    "generator": "Alternateur",

    "boite": "Boîte à crabots",
    "crabot": "Boîte à crabots",

    "architecture": "Architecture",
    "packaging": "Architecture",

    "cao": "CAO / SolidWorks",
    "solidworks": "CAO / SolidWorks",

    "optimisation": "Optimisation",
    "assemblage": "Assemblage",
}

PRIORITY_RANK = {
    "bloquant": 0,
    "impossible": 0,
    "erreur": 0,
    "missing": 0,
    "alerte": 1,
    "cao": 2,
    "partiel": 3,
    "inconnu": 4,
    "info": 5,
    "ok": 9,
}


def infer_field_key(*texts: Any) -> Optional[str]:
    blob = _normalise_text(" ".join(str(t or "") for t in texts))
    if not blob:
        return None

    # Exact / substring alias
    for needle, target in FIELD_ALIASES.items():
        if needle in blob:
            return target

    # Si le texte contient déjà une clé connue complète.
    for target in set(FIELD_ALIASES.values()):
        if _normalise_text(target) in blob:
            return target

    return None


def infer_subsystem(*texts: Any) -> str:
    blob = _normalise_text(" ".join(str(t or "") for t in texts))
    for needle, subsystem in SUBSYSTEM_KEYWORDS.items():
        if needle in blob:
            return subsystem
    return "Général"


def normalize_priority(value: Any, *, category: str = "") -> str:
    raw = _normalise_text(_first_non_empty(value, category, "partiel"))

    if raw in {"impossibles", "impossible", "bloquant", "erreur", "error", "missing"}:
        return "bloquant"
    if raw in {"partielles", "partielle", "partiel", "warning"}:
        return "partiel"
    if raw in {"cao", "inconnues_cao"}:
        return "cao"
    if raw in {"alerte", "alertes", "alert"}:
        return "alerte"

    return raw or "partiel"


# =============================================================================
# Collecte depuis backend/ui
# =============================================================================

REPORT_ATTRS: Tuple[str, ...] = (
    "backend_report",
    "full_report",
    "raw_backend_report",
    "last_backend_report",
    "engine_report",
    "system_report",
    "raw_report",
    "report",
    "last_report",
    "all_data",
    "toutes_les_donnees",
    "ui_report",
)


def _app_reports(app: Any) -> List[Tuple[str, Mapping[str, Any]]]:
    reports: List[Tuple[str, Mapping[str, Any]]] = []

    for attr in REPORT_ATTRS:
        try:
            value = getattr(app, attr, None)
        except Exception:
            continue

        if isinstance(value, Mapping) and value:
            reports.append((f"app.{attr}", value))

    return reports


def _current_value_for_key(app: Any, key: Optional[str], backend_item: Mapping[str, Any]) -> Any:
    if not key:
        return None

    params = _safe_dict(getattr(app, "engine_params", {}) or {})
    if key in params:
        return params.get(key)

    # Aliases fréquents
    reverse_aliases = {
        "puissance_traction_kw": ("puissance_entree", "puissance_kw"),
        "architecture_moteur": ("architecture", "architecture_forcee"),
        "nombre_cylindres": ("nb_cylindres", "n_cyl"),
        "alesage_m": ("alesage_mm", "diametre_piston"),
        "course_m": ("course_mm", "course_piston"),
    }

    for alias in reverse_aliases.get(key, ()):
        if alias in params:
            value = params.get(alias)
            if alias.endswith("_mm") and _safe_float(value) is not None:
                return float(value) / 1000.0
            return value

    # Dernier recours : valeur portée par l’item backend.
    for raw_key in ("value", "valeur", "valeur_attendue", "current_value"):
        if backend_item.get(raw_key) is not None:
            return backend_item.get(raw_key)

    return None


def _normalize_missing_item(
    app: Any,
    raw: Mapping[str, Any],
    *,
    source: str,
    category: str = "",
) -> Dict[str, Any]:
    name = str(
        _first_non_empty(
            raw.get("name"),
            raw.get("nom"),
            raw.get("label"),
            raw.get("champ"),
            raw.get("key"),
            raw.get("piece"),
            "Donnée inconnue",
        )
    )

    reason = str(
        _first_non_empty(
            raw.get("reason"),
            raw.get("raison"),
            raw.get("detail"),
            raw.get("message"),
            raw.get("erreur"),
            raw.get("value"),
            "Donnée nécessaire pour fermer le calcul.",
        )
    )

    explicit_key = _first_non_empty(raw.get("key"), raw.get("champ"), raw.get("field"))
    key = str(explicit_key) if explicit_key else infer_field_key(name, reason, source, raw.get("source"))

    subsystem = str(
        _first_non_empty(
            raw.get("subsystem"),
            raw.get("sous_systeme"),
            raw.get("systeme"),
            infer_subsystem(name, reason, source, raw.get("source")),
        )
    )

    priority = normalize_priority(
        _first_non_empty(raw.get("priority"), raw.get("priorite"), raw.get("severity"), raw.get("status")),
        category=category,
    )

    item = {
        "name": name,
        "key": key,
        "subsystem": subsystem,
        "priority": priority,
        "reason": reason,
        "source": str(_first_non_empty(raw.get("source"), source)),
        "category": category or str(raw.get("categorie") or raw.get("category") or ""),
        "raw": dict(raw),
    }

    item["current_value"] = _current_value_for_key(app, key, item)

    return item


def _walk_backend_missing(
    app: Any,
    node: Any,
    *,
    source: str,
    out: List[Dict[str, Any]],
) -> None:
    if isinstance(node, Mapping):
        # Format standard : inconnues = {"impossibles": [...], "partielles": [...]}
        inc = node.get("inconnues")
        if isinstance(inc, Mapping):
            for category, values in inc.items():
                for raw in _safe_list(values):
                    if isinstance(raw, Mapping):
                        out.append(
                            _normalize_missing_item(
                                app,
                                raw,
                                source=f"{source}.inconnues.{category}",
                                category=str(category),
                            )
                        )
                    else:
                        out.append(
                            _normalize_missing_item(
                                app,
                                {"nom": str(raw), "raison": str(raw)},
                                source=f"{source}.inconnues.{category}",
                                category=str(category),
                            )
                        )

        # Format CAO
        inconnues_cao = node.get("inconnues_cao")
        if isinstance(inconnues_cao, list):
            for raw in inconnues_cao:
                if isinstance(raw, Mapping):
                    out.append(
                        _normalize_missing_item(
                            app,
                            raw,
                            source=f"{source}.inconnues_cao",
                            category="cao",
                        )
                    )

        # Alertes : elles ne sont pas toujours des manques, mais elles peuvent bloquer.
        alerts = node.get("alertes")
        if isinstance(alerts, Mapping):
            for category, values in alerts.items():
                for raw in _safe_list(values):
                    if isinstance(raw, Mapping):
                        out.append(
                            _normalize_missing_item(
                                app,
                                raw,
                                source=f"{source}.alertes.{category}",
                                category="alerte",
                            )
                        )

        # construction_debug avec erreurs
        construction_debug = node.get("construction_debug")
        if isinstance(construction_debug, Mapping):
            for piece, debug in construction_debug.items():
                if isinstance(debug, Mapping) and debug.get("erreur"):
                    out.append(
                        _normalize_missing_item(
                            app,
                            {
                                "nom": str(piece),
                                "raison": str(debug.get("erreur")),
                                "piece": str(piece),
                                "priority": "bloquant",
                            },
                            source=f"{source}.construction_debug",
                            category="erreur",
                        )
                    )

        # Erreur directe
        if node.get("erreur"):
            out.append(
                _normalize_missing_item(
                    app,
                    {
                        "nom": "Erreur backend",
                        "raison": str(node.get("erreur")),
                        "priority": "bloquant",
                    },
                    source=source,
                    category="erreur",
                )
            )

        for key, value in node.items():
            if isinstance(value, (Mapping, list)):
                _walk_backend_missing(app, value, source=f"{source}.{key}", out=out)

    elif isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, (Mapping, list)):
                _walk_backend_missing(app, value, source=f"{source}[{index}]", out=out)


def collect_missing_requirements(app: Any) -> List[Dict[str, Any]]:
    ui = _safe_dict(getattr(app, "ui_report", {}) or {})
    out: List[Dict[str, Any]] = []

    # 1) Manques déjà préparés par l’adapter UI.
    for raw in _safe_list(ui.get("missing_requirements")):
        if isinstance(raw, Mapping):
            out.append(_normalize_missing_item(app, raw, source="ui_report.missing_requirements"))

    # 2) Sections brutes UI.
    for section in _safe_list(ui.get("raw_sections")):
        if not isinstance(section, Mapping):
            continue
        name = str(section.get("name", "raw_section"))
        value = section.get("value")
        _walk_backend_missing(app, value, source=f"ui_report.raw_sections.{name}", out=out)

    # 3) Rapports backend complets en mémoire.
    for source, report in _app_reports(app):
        _walk_backend_missing(app, report, source=source, out=out)

    # 4) Si aucune donnée mais engine_params incomplet : créer au moins l’action puissance.
    params = _safe_dict(getattr(app, "engine_params", {}) or {})
    has_power = any(
        _safe_float(params.get(k)) is not None and float(params[k]) > 0
        for k in (
            "puissance_traction_kw",
            "production_electrique_sortie_w",
            "puissance_bus_dc_w",
            "puissance_moteur_requise_W",
        )
    )

    if not has_power:
        out.append(
            _normalize_missing_item(
                app,
                {
                    "nom": "Cible de puissance",
                    "key": "puissance_traction_kw",
                    "subsystem": "Puissance & mission",
                    "priority": "bloquant",
                    "raison": (
                        "Aucune cible de puissance exploitable : renseigner puissance_traction_kw, "
                        "production_electrique_sortie_w, puissance_bus_dc_w ou puissance_moteur_requise_W."
                    ),
                },
                source="engine_params",
                category="impossibles",
            )
        )

    return _dedup_and_sort(out)


def _dedup_and_sort(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, str, str, str]] = set()
    out: List[Dict[str, Any]] = []

    for item in items:
        key = str(item.get("key") or "")
        name = str(item.get("name") or "")
        reason = str(item.get("reason") or "")
        source = str(item.get("source") or "")

        sig = (key, name, reason, source)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(dict(item))

    out.sort(
        key=lambda x: (
            PRIORITY_RANK.get(str(x.get("priority", "partiel")).lower(), 5),
            str(x.get("subsystem", "")),
            str(x.get("key") or x.get("name") or ""),
        )
    )

    return out


# =============================================================================
# Écran principal
# =============================================================================

class MissingRequirementsScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.search_query = ""
        self.active_filter = "Tous"
        self.items: List[Dict[str, Any]] = []
        self.content: Optional[BoxLayout] = None

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()

        app = App.get_running_app()
        self.items = collect_missing_requirements(app)

        # Stocker aussi pour les autres écrans.
        ui_report = dict(getattr(app, "ui_report", {}) or {})
        ui_report["missing_requirements"] = list(self.items)
        app.ui_report = ui_report

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )
        root.add_widget(self._top_bar())
        root.add_widget(self._summary_panel(self.items))

        if not self.items:
            root.add_widget(
                EmptyState(
                    text="SYSTÈME COMPLET",
                    action_text="RETOUR DASHBOARD",
                    callback=lambda *_: self._go("dashboard"),
                )
            )
            self.add_widget(root)
            return

        controls = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(92),
            spacing=dp(5),
        )
        controls.add_widget(SearchBar(callback=self._on_search))

        filters = self._build_filters(self.items)
        controls.add_widget(FilterChips(filters=filters, callback=self._on_filter))
        root.add_widget(controls)

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        self.content = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint_y=None,
            padding=[dp(4), dp(10)],
        )
        self.content.bind(minimum_height=self.content.setter("height"))

        self._populate_items()

        scroll.add_widget(self.content)
        root.add_widget(scroll)
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
            text="DONNÉES À COMPLÉTER",
            color=COLORS["RS"],
            bold=True,
            font_size="16sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)

        btn_refresh = ModernButton(text="RAFRAÎCHIR", size_hint_x=None, width=dp(120), font_size="11sp")
        btn_refresh.bind(on_release=lambda *_: self.refresh())
        bar.add_widget(btn_refresh)

        btn_edit = ModernButton(text="PARAMÈTRES", size_hint_x=None, width=dp(130), font_size="11sp")
        btn_edit.bind(on_release=lambda *_: self._go("edit_parameters"))
        bar.add_widget(btn_edit)

        btn_back = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=dp(180), font_size="11sp")
        btn_back.bind(on_release=lambda *_: self._go("dashboard"))
        bar.add_widget(btn_back)

        return bar

    def _summary_panel(self, items: Sequence[Mapping[str, Any]]) -> PremiumCard:
        total = len(items)
        bloquants = sum(1 for x in items if str(x.get("priority")) in {"bloquant", "impossible", "erreur", "missing"})
        partiels = sum(1 for x in items if str(x.get("priority")) == "partiel")
        cao = sum(1 for x in items if str(x.get("priority")) == "cao")
        with_key = sum(1 for x in items if x.get("key"))

        subsystems = sorted({str(x.get("subsystem", "Général")) for x in items})

        panel = PremiumCard(title="Résumé des manques", size_hint_y=None, height=dp(124))

        grid = GridLayout(cols=5, spacing=dp(8), size_hint_y=None, height=dp(48))
        grid.add_widget(MetricRow("Total", total, "", "alerte" if total else "ok"))
        grid.add_widget(MetricRow("Bloquants", bloquants, "", "alerte" if bloquants else "ok"))
        grid.add_widget(MetricRow("Partiels", partiels, "", "partiel" if partiels else "ok"))
        grid.add_widget(MetricRow("CAO", cao, "", "alerte" if cao else "ok"))
        grid.add_widget(MetricRow("Champs liés", with_key, "", "ok" if with_key else "missing"))
        panel.add_widget(grid)

        panel.add_widget(
            _label(
                f"Sous-systèmes concernés : {', '.join(subsystems[:8]) if subsystems else 'aucun'}",
                color=COLORS["GS"],
                size="11sp",
                height=28,
            )
        )

        return panel

    def _build_filters(self, items: Sequence[Mapping[str, Any]]) -> List[str]:
        subsystems = sorted({str(item.get("subsystem", "Général")) for item in items})
        priorities = ["Bloquants", "Partiels", "CAO", "Alertes"]
        return priorities + subsystems[:16]

    def _populate_items(self) -> None:
        if self.content is None:
            return

        self.content.clear_widgets()
        filtered = self._filtered_items()

        if not filtered:
            self.content.add_widget(
                Label(
                    text="Aucun résultat pour ces filtres.",
                    color=COLORS["GS"],
                    size_hint_y=None,
                    height=dp(40),
                )
            )
            return

        for item in filtered[:60]:
            self.content.add_widget(self._requirement_card(item))

        if len(filtered) > 60:
            self.content.add_widget(
                Label(
                    text=f"... et {len(filtered) - 60} autres éléments. Affine la recherche.",
                    color=COLORS["GS"],
                    font_size="11sp",
                    size_hint_y=None,
                    height=dp(34),
                )
            )

    def _filtered_items(self) -> List[Dict[str, Any]]:
        query = self.search_query.strip().lower()
        active = self.active_filter

        out: List[Dict[str, Any]] = []

        for item in self.items:
            priority = str(item.get("priority", "")).lower()
            subsystem = str(item.get("subsystem", "Général"))

            if active != "Tous":
                if active == "Bloquants" and priority not in {"bloquant", "impossible", "erreur", "missing"}:
                    continue
                elif active == "Partiels" and priority != "partiel":
                    continue
                elif active == "CAO" and priority != "cao":
                    continue
                elif active == "Alertes" and priority != "alerte":
                    continue
                elif active not in {"Bloquants", "Partiels", "CAO", "Alertes"} and subsystem != active:
                    continue

            if query:
                blob = " ".join(
                    str(item.get(k, ""))
                    for k in ("name", "key", "subsystem", "priority", "reason", "source", "category")
                ).lower()
                if query not in blob:
                    continue

            out.append(item)

        return out

    def _requirement_card(self, item: Mapping[str, Any]) -> NeoCard:
        priority = str(item.get("priority", "partiel"))
        key = item.get("key")
        current_value = item.get("current_value")

        card = NeoCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(238),
            spacing=dp(6),
            padding=dp(12),
        )

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
            spacing=dp(8),
        )
        header.add_widget(SectionTitle(text=str(item.get("name", "Inconnu")).upper()))
        header.add_widget(StatusBadge(status=priority, size_hint_x=None, width=dp(120)))
        card.add_widget(header)

        reason = Label(
            text=_short_text(item.get("reason", "Donnée nécessaire pour fermer le calcul."), 220),
            color=COLORS["BFW"],
            font_size="12sp",
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(48),
        )
        reason.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        card.add_widget(reason)

        grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, height=dp(72))
        grid.add_widget(MetricRow("Sous-système", item.get("subsystem", "Général"), "", priority))
        grid.add_widget(MetricRow("Champ corrigible", key or "Non inféré", "", "ok" if key else "missing"))
        grid.add_widget(MetricRow("Valeur actuelle", _fmt_value(current_value), "", "ok" if current_value is not None else "missing"))
        grid.add_widget(MetricRow("Source", _short_text(item.get("source", ""), 46), "", priority))
        card.add_widget(grid)

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(42),
            spacing=dp(8),
        )

        resolve_btn = ModernButton(
            text="RÉSOUDRE",
            font_size="10sp",
        )
        resolve_btn.bind(on_release=lambda *_args, it=dict(item): self._on_resolve(it))
        buttons.add_widget(resolve_btn)

        copy_btn = ModernButton(
            text="COPIER CLÉ",
            font_size="10sp",
        )
        copy_btn.disabled = not bool(key)
        copy_btn.bind(on_release=lambda *_args, it=dict(item): self._copy_key(it))
        buttons.add_widget(copy_btn)

        raw_btn = ModernButton(
            text="COPIER RAISON",
            font_size="10sp",
        )
        raw_btn.bind(on_release=lambda *_args, it=dict(item): self._copy_reason(it))
        buttons.add_widget(raw_btn)

        card.add_widget(buttons)
        return card

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def _on_search(self, query: str) -> None:
        self.search_query = query or ""
        self._populate_items()

    def _on_filter(self, filter_name: str) -> None:
        self.active_filter = filter_name or "Tous"
        self._populate_items()

    def _copy_key(self, item: Mapping[str, Any]) -> None:
        key = item.get("key")
        if key:
            Clipboard.copy(str(key))

    def _copy_reason(self, item: Mapping[str, Any]) -> None:
        Clipboard.copy(str(item.get("reason", "")))

    def _on_resolve(self, item: Dict[str, Any]) -> None:
        """
        Prépare edit_parameters à afficher directement le champ concerné.
        Les écrans musclés EditParametersScreen peuvent lire :
          - app.focus_parameter_key
          - app.resolve_requirement
          - ui_report["edit_focus_key"]
          - ui_report["resolve_target"]
        """
        app = App.get_running_app()
        key = item.get("key")

        try:
            app.focus_parameter_key = key
            app.resolve_requirement = dict(item)
        except Exception:
            pass

        ui_report = dict(getattr(app, "ui_report", {}) or {})
        ui_report["edit_focus_key"] = key
        ui_report["resolve_target"] = dict(item)

        # Injecte un champ éditable minimal si l’écran paramètres ne l’a pas encore.
        if key:
            existing = _safe_list(ui_report.get("editable_parameters"))
            exists = any(isinstance(p, Mapping) and p.get("key") == key for p in existing)

            if not exists:
                existing.append(
                    {
                        "key": key,
                        "label": str(item.get("name") or key),
                        "value": item.get("current_value"),
                        "source": f"À RENSEIGNER depuis {item.get('source', 'backend')}",
                        "editable": True,
                        "category": str(item.get("subsystem", "Général")),
                        "type": "float" if _looks_numeric_key(str(key)) else "str",
                        "unit": _unit_for_key(str(key)),
                    }
                )
                ui_report["editable_parameters"] = existing

        app.ui_report = ui_report
        self._go("edit_parameters")

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name


def _looks_numeric_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        token in lowered
        for token in (
            "_kw",
            "_w",
            "_pa",
            "_m",
            "_mm",
            "_kg",
            "_nm",
            "_rpm",
            "_ms",
            "_kwh",
            "nombre_",
            "nb_",
            "ratio",
            "rendement",
            "pression",
            "puissance",
            "vitesse",
            "force",
            "couple",
        )
    )


def _unit_for_key(key: str) -> str:
    lowered = key.lower()

    if lowered.endswith("_kw"):
        return "kW"
    if lowered.endswith("_w"):
        return "W"
    if lowered.endswith("_pa"):
        return "Pa"
    if lowered.endswith("_kg"):
        return "kg"
    if lowered.endswith("_nm"):
        return "Nm"
    if lowered.endswith("_rpm"):
        return "rpm"
    if lowered.endswith("_kwh"):
        return "kWh"
    if lowered.endswith("_mm"):
        return "mm"
    if lowered.endswith("_m"):
        return "m"
    if "rendement" in lowered or "ratio" in lowered:
        return "0..1"
    if "nombre" in lowered or lowered.startswith("nb_"):
        return ""

    return ""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import (
    COLORS,
    EmptyState,
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    SectionTitle,
    StatusBadge,
)


# =============================================================================
# Helpers UI / données
# =============================================================================

def _c(name: str, fallback: Any = (1, 1, 1, 1)) -> Any:
    return COLORS.get(name, fallback)


def _is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _safe_float(value: Any) -> Optional[float]:
    return float(value) if _is_finite(value) else None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
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


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _first_finite(*values: Any) -> Optional[float]:
    for value in values:
        if _is_finite(value):
            return float(value)
    return None


def _fmt_number(value: Any, digits: int = 3) -> str:
    if not _is_finite(value):
        return "—"

    v = float(value)
    av = abs(v)

    if av >= 1_000_000:
        return f"{v / 1_000_000:.{digits}g} M"
    if av >= 1_000:
        return f"{v / 1_000:.{digits}g} k"
    if 0 < av < 0.001:
        return f"{v:.{digits}e}"
    return f"{v:.{digits}g}"


def _fmt_percent(value: Any) -> str:
    if not _is_finite(value):
        return "—"
    v = float(value)
    if 0.0 <= v <= 1.0:
        v *= 100.0
    return f"{v:.1f}"


def _fmt_bool(value: Any) -> str:
    if value is True:
        return "OUI"
    if value is False:
        return "NON"
    return "—"


def _short_text(value: Any, max_len: int = 150) -> str:
    txt = str(value or "").strip()
    if not txt:
        return "Aucune description fournie."
    return txt if len(txt) <= max_len else txt[: max_len - 1].rstrip() + "…"


def _make_label(
    text: str,
    *,
    color: Any = None,
    font_size: str = "12sp",
    bold: bool = False,
    height: Optional[float] = None,
) -> Label:
    lbl = Label(
        text=str(text),
        color=color or _c("BFW"),
        font_size=font_size,
        bold=bold,
        halign="left",
        valign="top",
        size_hint_y=None,
        height=height or dp(24),
    )
    lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
    return lbl


def _candidate_architecture(cand: Mapping[str, Any]) -> str:
    return str(
        _first_non_empty(
            cand.get("architecture"),
            cand.get("Architecture"),
            cand.get("nom"),
            cand.get("name"),
            cand.get("type_architecture"),
            _deep_get(cand, "resultats", "architecture"),
            _deep_get(cand, "synthese", "architecture"),
            "INCONNU",
        )
    )


def _candidate_score(cand: Mapping[str, Any]) -> Optional[float]:
    return _first_finite(
        cand.get("score"),
        cand.get("score_technique"),
        cand.get("note"),
        cand.get("Score"),
        _deep_get(cand, "scores", "global"),
        _deep_get(cand, "scores", "score_global"),
        _deep_get(cand, "resultats", "score"),
        _deep_get(cand, "synthese", "score"),
    )


def _candidate_is_blocking(cand: Mapping[str, Any]) -> bool:
    for key in ("bloquant", "blocking", "invalide"):
        if cand.get(key) is True:
            return True

    for key in ("ok", "compatible", "faisable", "valide", "packaging_ok"):
        if cand.get(key) is False:
            return True

    inconnues = _safe_dict(cand.get("inconnues"))
    if inconnues.get("impossibles"):
        return True

    return False


def _candidate_status(cand: Mapping[str, Any], selected_arch: Optional[str]) -> str:
    arch = _candidate_architecture(cand)

    if selected_arch and arch == selected_arch:
        return "retenue"

    if _candidate_is_blocking(cand):
        return "bloquant"

    score = _candidate_score(cand)
    if score is not None:
        return "disponible"

    return "partiel"


def _candidate_sort_key(cand: Mapping[str, Any]) -> Tuple[int, float, str]:
    blocking = 1 if _candidate_is_blocking(cand) else 0
    score = _candidate_score(cand)
    return (blocking, -(score if score is not None else -1.0), _candidate_architecture(cand))


def _collect_missing_reasons(ui_report: Mapping[str, Any]) -> List[str]:
    reasons: List[str] = []

    for category in ("impossibles", "partielles"):
        for item in _as_list(_deep_get(ui_report, "inconnues", category)):
            if not isinstance(item, Mapping):
                continue
            nom = str(item.get("nom", "")).strip()
            raison = str(item.get("raison", "")).strip()
            if nom or raison:
                reasons.append(f"• {nom} — {raison}" if nom and raison else f"• {nom or raison}")

    for category, values in _safe_dict(ui_report.get("alertes")).items():
        for item in _as_list(values):
            if not isinstance(item, Mapping):
                continue
            nom = str(item.get("nom", "")).strip()
            detail = str(item.get("detail", "")).strip()
            if nom or detail:
                reasons.append(f"• {nom} — {detail}" if nom and detail else f"• {nom or detail}")

    if not reasons:
        reasons = [
            "• Paramètres PME / puissance thermique insuffisants",
            "• Cylindrée, nombre de cylindres ou contraintes géométriques non fermés",
            "• Packaging, bus DC, alternateur ou boîte non suffisamment dimensionnés",
        ]

    # Déduplication conservatrice
    seen = set()
    deduped = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            deduped.append(reason)

    return deduped[:10]


# =============================================================================
# Écran principal
# =============================================================================

class ArchitectureChoiceScreen(Screen):
    """
    Écran de sélection d'architecture.

    Entrées attendues dans app.ui_report :
      - architecture_candidates: list[dict]

    À la sélection :
      - app.engine_params["architecture"] est mis à jour ;
      - app.engine_params["architecture_candidate"] conserve le candidat complet ;
      - app.selected_architecture est renseigné si possible ;
      - navigation vers "loading".
    """

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()

        app = App.get_running_app()
        ui_report = _safe_dict(getattr(app, "ui_report", {}) or {})
        engine_params = _safe_dict(getattr(app, "engine_params", {}) or {})

        candidates = [
            cand for cand in _as_list(ui_report.get("architecture_candidates"))
            if isinstance(cand, Mapping)
        ]
        candidates.sort(key=_candidate_sort_key)

        selected_arch = str(engine_params.get("architecture", "") or "")

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )

        root.add_widget(self._top_bar(count=len(candidates), selected_arch=selected_arch))

        if not candidates:
            root.add_widget(self._empty_panel(ui_report))
        else:
            root.add_widget(self._candidates_panel(candidates, selected_arch))

        self.add_widget(root)

    # -------------------------------------------------------------------------
    # Sections UI
    # -------------------------------------------------------------------------

    def _top_bar(self, *, count: int, selected_arch: str) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
            spacing=dp(10),
            padding=[dp(10), dp(5)],
        )

        left = BoxLayout(orientation="vertical", spacing=dp(2))

        title = _make_label(
            "SÉLECTION D'ARCHITECTURE",
            color=_c("BFW"),
            font_size="16sp",
            bold=True,
            height=dp(28),
        )
        left.add_widget(title)

        subtitle = f"{count} architecture(s) candidate(s)"
        if selected_arch:
            subtitle += f" · retenue actuellement : {selected_arch}"

        left.add_widget(
            _make_label(
                subtitle,
                color=_c("GS"),
                font_size="11sp",
                height=dp(22),
            )
        )

        bar.add_widget(left)

        btn_refresh = ModernButton(
            text="RAFRAÎCHIR",
            size_hint_x=None,
            width=dp(120),
            font_size="11sp",
        )
        btn_refresh.bind(on_release=lambda *_: self.refresh())
        bar.add_widget(btn_refresh)

        btn_back = ModernButton(
            text="RETOUR DASHBOARD",
            size_hint_x=None,
            width=dp(180),
            font_size="11sp",
        )
        btn_back.bind(on_release=lambda *_: self._go("dashboard"))
        bar.add_widget(btn_back)

        return bar

    def _empty_panel(self, ui_report: Mapping[str, Any]) -> PremiumCard:
        panel = PremiumCard(
            title="ARCHITECTURE INDISPONIBLE",
            bg=_c("BFW_08"),
        )

        why_box = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=[dp(20), dp(8)],
            size_hint_y=None,
        )
        why_box.bind(minimum_height=why_box.setter("height"))

        why_box.add_widget(
            _make_label(
                "Pourquoi aucune architecture n'est retenable ?",
                color=_c("RS"),
                font_size="14sp",
                bold=True,
                height=dp(30),
            )
        )

        for reason in _collect_missing_reasons(ui_report):
            why_box.add_widget(
                _make_label(
                    reason,
                    color=_c("BFW"),
                    font_size="12sp",
                    height=dp(34),
                )
            )

        panel.add_widget(why_box)

        panel.add_widget(
            EmptyState(
                text="DES DONNÉES CRITIQUES MANQUENT",
                action_text="COMPLÉTER LES PARAMÈTRES",
                callback=lambda *_: self._go("edit_parameters"),
            )
        )

        return panel

    def _candidates_panel(self, candidates: List[Mapping[str, Any]], selected_arch: str) -> ScrollView:
        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)

        cols = 1 if Window.width < dp(980) else 2

        grid = GridLayout(
            cols=cols,
            spacing=dp(16),
            size_hint_y=None,
            padding=[dp(2), dp(2), dp(8), dp(8)],
        )
        grid.bind(minimum_height=grid.setter("height"))

        for cand in candidates:
            grid.add_widget(self._candidate_card(dict(cand), selected_arch))

        scroll.add_widget(grid)
        return scroll

    def _candidate_card(self, cand: Dict[str, Any], selected_arch: str) -> NeoCard:
        arch = _candidate_architecture(cand)
        score = _candidate_score(cand)
        status = _candidate_status(cand, selected_arch)

        metrics = self._extract_display_metrics(cand)

        card_height = dp(245 + 30 * len(metrics))
        card = NeoCard(
            orientation="vertical",
            size_hint_y=None,
            height=card_height,
            spacing=dp(8),
            padding=dp(12),
        )

        # Header
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
            spacing=dp(8),
        )
        header.add_widget(SectionTitle(text=str(arch)))
        header.add_widget(StatusBadge(status=status))
        card.add_widget(header)

        # Description
        desc = _first_non_empty(
            cand.get("description"),
            cand.get("resume"),
            cand.get("commentaire"),
            _deep_get(cand, "synthese", "description"),
            "Aucune description fournie.",
        )
        card.add_widget(
            _make_label(
                _short_text(desc, max_len=180),
                color=_c("GS"),
                font_size="11sp",
                height=dp(48),
            )
        )

        # Score
        card.add_widget(
            MetricRow(
                "Score technique",
                _fmt_number(score) if score is not None else "—",
                "/100",
            )
        )

        # Métriques disponibles
        for label, value, unit in metrics:
            card.add_widget(MetricRow(label, value, unit))

        # Diagnostic court
        diag = self._candidate_short_diagnostic(cand)
        if diag:
            card.add_widget(
                _make_label(
                    diag,
                    color=_c("RS") if _candidate_is_blocking(cand) else _c("GS"),
                    font_size="10sp",
                    height=dp(36),
                )
            )

        # Bouton choix
        btn = ModernButton(
            text="RETENIR CETTE ARCHITECTURE",
            size_hint_y=None,
            height=dp(44),
            font_size="12sp",
        )
        btn.disabled = _candidate_is_blocking(cand)
        btn.bind(on_release=lambda *_cand_args, _arch=arch, _cand=cand: self._choose(_arch, _cand))
        card.add_widget(btn)

        return card

    # -------------------------------------------------------------------------
    # Extraction affichage
    # -------------------------------------------------------------------------

    def _extract_display_metrics(self, cand: Mapping[str, Any]) -> List[Tuple[str, str, str]]:
        rows: List[Tuple[str, str, str]] = []

        nb_cyl = _first_non_empty(
            cand.get("nombre_cylindres"),
            cand.get("nb_cyl"),
            cand.get("n_cylindres"),
            _deep_get(cand, "resultats", "nombre_cylindres"),
            _deep_get(cand, "synthese", "nombre_cylindres"),
        )
        if nb_cyl is not None:
            rows.append(("Cylindres", str(nb_cyl), ""))

        cylindree_cc = _first_finite(
            cand.get("cylindree_totale_cc"),
            _deep_get(cand, "resultats", "cylindree_totale_cc"),
            _deep_get(cand, "synthese", "cylindree_totale_cc"),
        )
        cylindree_m3 = _first_finite(
            cand.get("cylindree_totale_m3"),
            _deep_get(cand, "resultats", "cylindree_totale_m3"),
            _deep_get(cand, "synthese", "cylindree_totale_m3"),
        )
        if cylindree_cc is not None:
            rows.append(("Cylindrée", _fmt_number(cylindree_cc), "cm³"))
        elif cylindree_m3 is not None:
            rows.append(("Cylindrée", _fmt_number(cylindree_m3 * 1e6), "cm³"))

        bore = _first_finite(
            cand.get("alesage_m"),
            cand.get("bore_m"),
            _deep_get(cand, "geometrie", "alesage_m"),
            _deep_get(cand, "resultats", "alesage_m"),
        )
        stroke = _first_finite(
            cand.get("course_m"),
            cand.get("stroke_m"),
            _deep_get(cand, "geometrie", "course_m"),
            _deep_get(cand, "resultats", "course_m"),
        )
        if bore is not None:
            rows.append(("Alésage", _fmt_number(bore * 1000.0), "mm"))
        if stroke is not None:
            rows.append(("Course", _fmt_number(stroke * 1000.0), "mm"))

        longueur = _first_finite(
            cand.get("longueur_m"),
            cand.get("L_m"),
            _deep_get(cand, "packaging", "longueur_m"),
            _deep_get(cand, "resultats", "longueur_m"),
        )
        largeur = _first_finite(
            cand.get("largeur_m"),
            cand.get("W_m"),
            _deep_get(cand, "packaging", "largeur_m"),
            _deep_get(cand, "resultats", "largeur_m"),
        )
        if longueur is not None and largeur is not None:
            rows.append(("Packaging", f"{_fmt_number(longueur)} × {_fmt_number(largeur)}", "m"))
        elif longueur is not None:
            rows.append(("Longueur estimée", _fmt_number(longueur), "m"))
        elif largeur is not None:
            rows.append(("Largeur estimée", _fmt_number(largeur), "m"))

        masse = _first_finite(
            cand.get("masse_kg"),
            cand.get("masse_estimee_kg"),
            _deep_get(cand, "masse", "masse_estimee_kg"),
            _deep_get(cand, "resultats", "masse_estimee_kg"),
        )
        if masse is not None:
            rows.append(("Masse estimée", _fmt_number(masse), "kg"))

        rendement = _first_finite(
            cand.get("rendement"),
            cand.get("rendement_mecanique"),
            _deep_get(cand, "rendements", "mecanique"),
            _deep_get(cand, "resultats", "rendement_mecanique"),
        )
        if rendement is not None:
            rows.append(("Rendement", _fmt_percent(rendement), "%"))

        maintenance = _first_finite(
            cand.get("indice_maintenance"),
            cand.get("maintenance_score"),
            _deep_get(cand, "maintenance", "indice"),
            _deep_get(cand, "resultats", "indice_maintenance"),
        )
        if maintenance is not None:
            rows.append(("Indice maintenance", _fmt_number(maintenance), ""))

        packaging_ok = _first_non_empty(
            cand.get("packaging_ok"),
            _deep_get(cand, "contraintes", "packaging_ok"),
            _deep_get(cand, "resultats", "packaging_ok"),
        )
        if isinstance(packaging_ok, bool):
            rows.append(("Packaging compatible", _fmt_bool(packaging_ok), ""))

        return rows[:9]

    def _candidate_short_diagnostic(self, cand: Mapping[str, Any]) -> str:
        if _candidate_is_blocking(cand):
            inc = _safe_dict(cand.get("inconnues"))
            impossibles = _as_list(inc.get("impossibles"))
            if impossibles and isinstance(impossibles[0], Mapping):
                nom = str(impossibles[0].get("nom", "")).strip()
                raison = str(impossibles[0].get("raison", "")).strip()
                return _short_text(f"Blocage : {nom} — {raison}", max_len=160)

            return "Architecture candidate bloquée par au moins une contrainte."

        warnings = _safe_dict(cand.get("alertes"))
        for values in warnings.values():
            values_list = _as_list(values)
            if values_list and isinstance(values_list[0], Mapping):
                nom = str(values_list[0].get("nom", "")).strip()
                detail = str(values_list[0].get("detail", "")).strip()
                return _short_text(f"Alerte : {nom} — {detail}", max_len=160)

        return ""

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def _choose(self, arch: str, cand: Mapping[str, Any]) -> None:
        app = App.get_running_app()

        params = dict(getattr(app, "engine_params", {}) or {})
        params["architecture"] = str(arch)
        params["architecture_candidate"] = dict(cand)

        # Champs pratiques pour les autres écrans / orchestrateurs
        score = _candidate_score(cand)
        if score is not None:
            params["architecture_score"] = score

        for key in (
            "nombre_cylindres",
            "nb_cyl",
            "alesage_m",
            "course_m",
            "cylindree_totale_m3",
            "cylindree_totale_cc",
        ):
            if key in cand and cand.get(key) is not None:
                params[key] = cand.get(key)

        app.engine_params = params

        try:
            app.selected_architecture = str(arch)
            app.selected_architecture_candidate = dict(cand)
        except Exception:
            pass

        self._go("loading")

        # Si ton App possède déjà un recalcul explicite, on le déclenche sans casser l’ancien flux.
        for method_name in (
            "request_recalculation",
            "request_recalculate",
            "recalculate",
            "run_calculation",
            "start_calculation",
        ):
            fn = getattr(app, method_name, None)
            if callable(fn):
                Clock.schedule_once(lambda *_args, _fn=fn: _fn(), 0)
                break

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name
# frontend/gui/error_view.py
from __future__ import annotations

import inspect
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput

from frontend.gui.components import (
    COLORS,
    MetricRow,
    ModernButton,
    PremiumCard,
    StatusBadge,
)


# =============================================================================
# Helpers
# =============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
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


def _short_text(value: Any, max_len: int = 160) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = 5) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

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

    if isinstance(value, BaseException):
        return {
            "type": type(value).__name__,
            "message": str(value),
        }

    try:
        return str(value)
    except Exception:
        return {"type": type(value).__name__}


def _format_trace_from_exception(exc: BaseException) -> str:
    return "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )


def _as_trace(trace: Any) -> str:
    if trace is None:
        return ""

    if isinstance(trace, str):
        return trace.strip()

    if isinstance(trace, BaseException):
        return _format_trace_from_exception(trace)

    try:
        return json.dumps(_jsonable(trace), ensure_ascii=False, indent=2)
    except Exception:
        return str(trace)


def _call_hook_safely(fn: Callable[..., Any], params: Mapping[str, Any]) -> Any:
    try:
        sig = inspect.signature(fn)
    except Exception:
        sig = None

    if sig is not None:
        try:
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                return fn(**dict(params))

            accepted = set(sig.parameters.keys())
            filtered = {k: v for k, v in dict(params).items() if k in accepted}

            if filtered:
                return fn(**filtered)
        except TypeError:
            pass

    try:
        return fn(dict(params))
    except TypeError:
        return fn()


def _extract_error_from_mapping(data: Mapping[str, Any], *, source: str = "") -> Optional[Dict[str, Any]]:
    """
    Accepte plusieurs formats possibles :
    - {"message": "...", "trace": "..."}
    - {"erreur": "..."}
    - {"error": "..."}
    - {"exception": "..."}
    - {"backend_errors": [...]}
    """
    if not isinstance(data, Mapping):
        return None

    message = _first_non_empty(
        data.get("message"),
        data.get("erreur"),
        data.get("error"),
        data.get("exception"),
        data.get("detail"),
        data.get("reason"),
    )

    trace = _first_non_empty(
        data.get("trace"),
        data.get("traceback"),
        data.get("stack"),
        data.get("stacktrace"),
    )

    nested_lists = (
        data.get("backend_errors"),
        data.get("dashboard_backend_errors"),
        data.get("energy_audit_errors"),
        data.get("edit_parameters_errors"),
        data.get("_dashboard_backend_errors"),
        data.get("_energy_audit_errors"),
    )

    for candidate in nested_lists:
        items = _safe_list(candidate)
        if items:
            first = items[0]
            if isinstance(first, Mapping):
                nested = _extract_error_from_mapping(first, source=str(first.get("source", source)))
                if nested:
                    return nested
            else:
                return {
                    "message": str(first),
                    "trace": "",
                    "source": source or "backend_errors",
                    "severity": "erreur",
                    "context": {"raw": _jsonable(first)},
                }

    if not message and not trace:
        return None

    return {
        "message": str(message or "Erreur backend non documentée."),
        "trace": str(trace or ""),
        "source": str(data.get("source") or source or "backend"),
        "severity": str(data.get("severity") or data.get("niveau") or "erreur"),
        "context": _jsonable(data),
    }


# =============================================================================
# Error screen
# =============================================================================

class ErrorScreen(Screen):
    """
    Vue de diagnostic backend.

    Objectifs :
    - afficher l'erreur sans perdre le contexte ;
    - aider à corriger le paramètre bloquant ;
    - permettre copie/export de la trace ;
    - relancer le calcul si l'application expose un hook compatible.
    """

    APP_ERROR_ATTRS: Sequence[str] = (
        "last_error_payload",
        "error_payload",
        "last_backend_error",
        "backend_error",
        "last_error",
        "startup_error",
        "calculation_error",
        "backend_sync_errors",
        "dashboard_backend_errors",
        "energy_audit_errors",
        "edit_parameters_errors",
    )

    RECALC_HOOKS: Sequence[str] = (
        "request_recalculation",
        "request_recalculate",
        "recalculate_backend",
        "recalculate",
        "run_calculation",
        "start_calculation",
        "compute_backend_report",
        "dimensionner_backend",
        "dimensionner_systeme",
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.error_payload: Dict[str, Any] = {}
        self._build_ui()

    # -------------------------------------------------------------------------
    # Construction UI
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.clear_widgets()

        root = BoxLayout(
            orientation="vertical",
            padding=dp(20),
            spacing=dp(12),
        )

        root.add_widget(self._top_bar())

        self.message = Label(
            text="",
            color=COLORS["BFW"],
            font_size="15sp",
            bold=True,
            size_hint_y=None,
            height=dp(70),
            halign="left",
            valign="middle",
        )
        self.message.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        root.add_widget(self.message)

        self.summary_panel = PremiumCard(
            title="Diagnostic rapide",
            size_hint_y=None,
            height=dp(148),
        )
        self.summary_box = BoxLayout(
            orientation="vertical",
            spacing=dp(2),
            size_hint_y=None,
        )
        self.summary_box.bind(minimum_height=self.summary_box.setter("height"))
        self.summary_panel.add_widget(self.summary_box)
        root.add_widget(self.summary_panel)

        context_panel = PremiumCard(
            title="Contexte backend",
            size_hint_y=None,
            height=dp(180),
        )
        self.context = TextInput(
            readonly=True,
            multiline=True,
            background_color=COLORS["BL"],
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["RS"],
            font_size="12sp",
        )
        context_panel.add_widget(self.context)
        root.add_widget(context_panel)

        trace_panel = PremiumCard(
            title="Trace technique",
        )
        self.trace = TextInput(
            readonly=True,
            multiline=True,
            background_color=COLORS["BL"],
            foreground_color=COLORS["RS"],
            cursor_color=COLORS["RS"],
            font_size="12sp",
        )
        trace_panel.add_widget(self.trace)
        root.add_widget(trace_panel)

        root.add_widget(self._buttons())

        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
            spacing=dp(10),
        )

        lbl = Label(
            text="ERREUR BACKEND",
            color=COLORS["RS"],
            bold=True,
            font_size="24sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        bar.add_widget(lbl)

        self.badge = StatusBadge(
            status="erreur",
            size_hint_x=None,
            width=dp(120),
        )
        bar.add_widget(self.badge)

        return bar

    def _buttons(self) -> GridLayout:
        grid = GridLayout(
            cols=6,
            spacing=dp(8),
            size_hint_y=None,
            height=dp(52),
        )

        buttons = (
            ("COPIER TRACE", self.copy_trace),
            ("COPIER RAPPORT", self.copy_report),
            ("EXPORT JSON", self.export_error_report),
            ("PARAMÈTRES", lambda *_: self._go("edit_parameters")),
            ("RECALCULER", self.retry_calculation),
            ("ACCUEIL", lambda *_: self._go("home")),
        )

        for text, callback in buttons:
            btn = ModernButton(text=text, font_size="10sp")
            btn.bind(on_release=callback)
            grid.add_widget(btn)

        return grid

    # -------------------------------------------------------------------------
    # Cycle de vie
    # -------------------------------------------------------------------------

    def on_enter(self, *_: Any) -> None:
        if not self.error_payload:
            self.load_error_from_app()

    def load_error_from_app(self) -> None:
        app = App.get_running_app()

        payload = self._collect_app_error(app)
        if payload is None:
            payload = {
                "message": "Aucune erreur backend détaillée n'a été transmise à l'écran.",
                "trace": "Trace indisponible.",
                "source": "frontend.gui.error_view",
                "severity": "missing",
                "context": {
                    "hint": (
                        "Utilise set_error(message, trace) ou stocke app.last_error_payload "
                        "avant de naviguer vers l'écran error."
                    )
                },
            }

        self.set_error_payload(payload)

    def _collect_app_error(self, app: Any) -> Optional[Dict[str, Any]]:
        for attr in self.APP_ERROR_ATTRS:
            try:
                value = getattr(app, attr, None)
            except Exception:
                continue

            if value is None:
                continue

            if isinstance(value, BaseException):
                return {
                    "message": str(value),
                    "trace": _format_trace_from_exception(value),
                    "source": f"app.{attr}",
                    "severity": "erreur",
                    "context": {"exception_type": type(value).__name__},
                }

            if isinstance(value, Mapping):
                extracted = _extract_error_from_mapping(value, source=f"app.{attr}")
                if extracted:
                    return extracted

            items = _safe_list(value)
            if items:
                first = items[0]
                if isinstance(first, Mapping):
                    extracted = _extract_error_from_mapping(first, source=f"app.{attr}[0]")
                    if extracted:
                        return extracted

                return {
                    "message": str(first),
                    "trace": "",
                    "source": f"app.{attr}[0]",
                    "severity": "erreur",
                    "context": {"raw": _jsonable(first)},
                }

            if isinstance(value, str) and value.strip():
                return {
                    "message": value.strip(),
                    "trace": "",
                    "source": f"app.{attr}",
                    "severity": "erreur",
                    "context": {},
                }

        return None

    # -------------------------------------------------------------------------
    # API publique
    # -------------------------------------------------------------------------

    def set_error(
        self,
        message: str,
        trace: str = "",
        *,
        source: str = "backend",
        severity: str = "erreur",
        context: Optional[Mapping[str, Any]] = None,
        exception: Optional[BaseException] = None,
    ) -> None:
        if exception is not None:
            message = message or str(exception)
            trace = trace or _format_trace_from_exception(exception)

        self.set_error_payload(
            {
                "message": str(message or "Erreur backend."),
                "trace": str(trace or ""),
                "source": str(source or "backend"),
                "severity": str(severity or "erreur"),
                "context": _jsonable(context or {}),
            }
        )

    def set_exception(
        self,
        exc: BaseException,
        *,
        source: str = "backend",
        context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.set_error(
            str(exc),
            _format_trace_from_exception(exc),
            source=source,
            severity="erreur",
            context={
                "exception_type": type(exc).__name__,
                **dict(context or {}),
            },
        )

    def set_error_payload(self, payload: Mapping[str, Any]) -> None:
        self.error_payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "message": str(payload.get("message") or "Erreur backend."),
            "trace": _as_trace(payload.get("trace")),
            "source": str(payload.get("source") or "backend"),
            "severity": str(payload.get("severity") or "erreur"),
            "context": _jsonable(payload.get("context") or {}),
        }

        self._render_payload()

        try:
            app = App.get_running_app()
            app.last_error_payload = dict(self.error_payload)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Rendu dynamique
    # -------------------------------------------------------------------------

    def _render_payload(self) -> None:
        payload = self.error_payload

        message = str(payload.get("message") or "Erreur backend.")
        trace = str(payload.get("trace") or "Trace indisponible.")
        source = str(payload.get("source") or "backend")
        severity = str(payload.get("severity") or "erreur")
        context = payload.get("context") or {}

        self.badge.status = severity
        self.badge.text = severity.upper()

        self.message.text = _short_text(message, 260)
        self.trace.text = trace or "Trace indisponible."

        try:
            self.context.text = json.dumps(context, ensure_ascii=False, indent=2)
        except Exception:
            self.context.text = str(context)

        self._render_summary(
            message=message,
            source=source,
            severity=severity,
            trace=trace,
            context=context,
        )

    def _render_summary(
        self,
        *,
        message: str,
        source: str,
        severity: str,
        trace: str,
        context: Any,
    ) -> None:
        self.summary_box.clear_widgets()

        self.summary_box.add_widget(MetricRow("Source", source, "", severity))
        self.summary_box.add_widget(MetricRow("Niveau", severity, "", severity))
        self.summary_box.add_widget(MetricRow("Trace disponible", "oui" if trace else "non", "", "ok" if trace else "missing"))
        self.summary_box.add_widget(MetricRow("Contexte disponible", "oui" if context else "non", "", "ok" if context else "missing"))

        suggestion = self._diagnose(message, trace)
        self.summary_box.add_widget(
            Label(
                text=f"Diagnostic : {suggestion}",
                color=COLORS["BFW"],
                font_size="11sp",
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(34),
            )
        )

    def _diagnose(self, message: str, trace: str) -> str:
        full = f"{message}\n{trace}".lower()

        if "puissance" in full and ("absente" in full or "manquant" in full or "missing" in full):
            return "cible de puissance absente ; renseigner puissance_traction_kw ou production_electrique_sortie_w."

        if "import" in full or "no module named" in full or "cannot import" in full:
            return "problème d'import ; vérifier l'arborescence Python, le PYTHONPATH et les noms de modules."

        if "dimensionner_systeme_shsem" in full:
            return "échec de l'orchestrateur backend principal ; vérifier app.engine_params et les paramètres requis."

        if "keyerror" in full or "paramètre manquant" in full:
            return "clé absente dans les paramètres ; ouvrir le panneau d'ingénierie et compléter les champs requis."

        if "valueerror" in full or "doit être" in full:
            return "valeur invalide ; vérifier unité, signe, format numérique et intervalle admissible."

        if "json" in full or "decode" in full:
            return "rapport JSON invalide ou incomplet ; régénérer le rapport backend."

        return "erreur non catégorisée ; lire la trace complète et le contexte backend."

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def copy_trace(self, *_: Any) -> None:
        Clipboard.copy(self.trace.text or "Trace indisponible.")

    def copy_report(self, *_: Any) -> None:
        Clipboard.copy(
            json.dumps(
                _jsonable(self.error_payload),
                ensure_ascii=False,
                indent=2,
            )
        )

    def export_error_report(self, *_: Any) -> None:
        try:
            export_dir = Path.cwd() / "backend" / "logs"
            export_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = export_dir / f"frontend_error_{timestamp}.json"

            path.write_text(
                json.dumps(
                    _jsonable(self.error_payload),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.set_error_payload(
                {
                    **self.error_payload,
                    "message": f"Rapport d'erreur exporté : {path}",
                    "severity": "ok",
                    "context": {
                        **_safe_dict(self.error_payload.get("context")),
                        "export_path": str(path),
                    },
                }
            )

        except Exception as exc:
            self.set_exception(exc, source="frontend.gui.error_view.export_error_report")

    def retry_calculation(self, *_: Any) -> None:
        app = App.get_running_app()
        params = _safe_dict(getattr(app, "engine_params", {}) or {})

        for hook_name in self.RECALC_HOOKS:
            fn = getattr(app, hook_name, None)
            if not callable(fn):
                continue

            try:
                _call_hook_safely(fn, params)
                self._go("loading")
                return
            except Exception as exc:
                self.set_exception(
                    exc,
                    source=f"app.{hook_name}",
                    context={"engine_params": _jsonable(params)},
                )
                return

        self.set_error(
            "Aucun hook de recalcul disponible dans l'application.",
            trace="Hooks essayés : " + ", ".join(self.RECALC_HOOKS),
            source="frontend.gui.error_view.retry_calculation",
            severity="missing",
            context={"engine_params": _jsonable(params)},
        )

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name
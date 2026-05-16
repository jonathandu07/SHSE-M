from __future__ import annotations

import threading
import traceback
from typing import Any, Dict

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from frontend.gui.components import COLORS, ModernButton, SectionTitle, StatusBadge, NeoCard
from frontend.gui.report_adapter import adapt_backend_report, extract_architecture_candidates

try:
    from backend.main import dimensionner_systeme_shsem
    from backend.modules.systeme.analyse_puissance_sortie import normaliser_puissance
except Exception:  # pragma: no cover - traité à l'écran erreur
    dimensionner_systeme_shsem = None
    normaliser_puissance = None


class LoadingScreen(Screen):
    steps = (
        "normalisation de la puissance",
        "appel backend",
        "orchestration STHO_ME",
        "adaptation du rapport",
        "génération de la vue",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.labels: list[Label] = []
        root = BoxLayout(orientation="vertical", padding=[80, 60], spacing=22)
        panel = NeoCard(orientation="vertical", padding=28, spacing=14)
        panel.add_widget(SectionTitle(text="CALCUL EN COURS"))
        self.status = Label(text="Préparation...", color=COLORS["BFW"], font_size="18sp", size_hint_y=None, height=42)
        panel.add_widget(self.status)
        for step in self.steps:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=36, spacing=10)
            row.add_widget(StatusBadge(status="partiel", text="EN ATTENTE", size_hint_x=None, width=120))
            label = Label(text=step, color=COLORS["GS"], halign="left", valign="middle")
            label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            row.add_widget(label)
            panel.add_widget(row)
            self.labels.append(row.children[-1])
        root.add_widget(panel)
        self.add_widget(root)

    def on_enter(self, *_):
        self.status.text = "Démarrage du calcul..."
        threading.Thread(target=self._run_backend, daemon=True).start()

    def _set_status(self, text: str) -> None:
        Clock.schedule_once(lambda *_: setattr(self.status, "text", text))

    def _run_backend(self) -> None:
        app = App.get_running_app()
        try:
            if dimensionner_systeme_shsem is None or normaliser_puissance is None:
                raise RuntimeError("Backend indisponible : impossible de lancer le calcul.")

            params = dict(app.engine_params or {})
            value = params.get("puissance_entree")
            unit = params.get("unite_entree")
            if value is None or unit is None:
                raise ValueError("Puissance ou unité manquante.")

            self._set_status("Normalisation de la puissance par le backend.")
            normalized = normaliser_puissance(value, unit)
            p_kw = normalized.get("kw") if isinstance(normalized, dict) else None
            if p_kw is None:
                raise ValueError("Le backend n'a pas retourné de puissance normalisée en kW.")

            backend_args: Dict[str, Any] = {"puissance_traction_kw": p_kw}
            if params.get("architecture"):
                backend_args["architecture_moteur"] = params["architecture"]
                backend_args["architecture_forcee"] = params["architecture"]
            if params.get("nombre_cylindres") not in (None, ""):
                backend_args["nombre_cylindres"] = int(float(params["nombre_cylindres"]))
            if params.get("alesage_mm") not in (None, ""):
                backend_args["alesage_m"] = float(params["alesage_mm"]) / 1000.0
            if params.get("course_mm") not in (None, ""):
                backend_args["course_m"] = float(params["course_mm"]) / 1000.0

            self._set_status("Appel du backend strict.")
            report = dimensionner_systeme_shsem(**backend_args)
            if not isinstance(report, dict):
                raise RuntimeError("Le backend n'a pas retourné de rapport exploitable.")
            if report.get("erreur"):
                raise RuntimeError(str(report.get("erreur")))

            self._set_status("Adaptation du rapport pour l'interface.")
            app.raw_backend_report = report
            app.ui_report = adapt_backend_report(report)

            candidates = extract_architecture_candidates(report)
            target = "architecture_choice" if candidates and not params.get("architecture") else "dashboard"
            self._set_status("Vue prête.")
            Clock.schedule_once(lambda *_: setattr(self.manager, "current", target))
        except Exception as exc:
            trace = traceback.format_exc()
            Clock.schedule_once(lambda *_: self._show_error(str(exc), trace))

    def _show_error(self, message: str, trace: str) -> None:
        screen = self.manager.get_screen("error")
        screen.set_error(message, trace)
        self.manager.current = "error"

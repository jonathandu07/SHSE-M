from __future__ import annotations

import inspect

import frontend.gui.cao_dossier_view as cao_view
import frontend.gui.dashboard as dashboard
import frontend.gui.json_diagnostic_view as diag_view
import frontend.gui.technical_visualization as tech_view


def test_gui_critiques_deleguent_aux_modeles_ensemble():
    assert dashboard.build_dashboard_ui_from_backend({"frontend": {}})["is_empty"] is False
    assert "build_dashboard_model" in inspect.getsource(dashboard.build_dashboard_ui_from_backend)
    assert "build_visualisation_model" in inspect.getsource(tech_view.build_technical_visualization_payload)
    assert "build_cao_model" in inspect.getsource(cao_view._build_payload)
    assert "diagnostiquer_frontend_data" in inspect.getsource(diag_view.build_json_diagnostic_for_app)

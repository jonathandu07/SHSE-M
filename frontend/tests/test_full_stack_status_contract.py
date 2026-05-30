from __future__ import annotations

import pytest

from frontend.ensemble.cao_adapter import build_cao_frontend_summary
from frontend.ensemble.contract_adapter import build_contract_model, normalize_contract_status
from frontend.ensemble.dashboard_model import build_dashboard_model
from frontend.ensemble.graph_rendering import build_chart_figure
from frontend.ensemble.graphs_adapter import collect_backend_charts
from frontend.gui.backend_resource_adapter import build_resource_catalog
from frontend.gui.frontend_contract import candidate_label, field_badge_label, get_field_status, is_field_blocking
from frontend.gui.report_adapter import resolve_metric


def _field(path: str, status: str, *, value: object = 1.0, trace: dict[str, object] | None = None, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {"path": path, "value": value, "unit": "W", "status": status}
    if trace is not None:
        row["trace"] = trace
    row.update(extra)
    return row


def _backend_report_with_all_statuses() -> dict[str, object]:
    trace = {"source": "resolution_inconnues", "formula": "test_formula"}
    opt_trace = {"source": "optimisation", "iteration": 1, "recalculated": True}
    return {
        "synthese": {
            "moteur_electrique": {"puissance_sortie_w": 100000.0},
            "systeme": {"P_bus_dc_design_w": 122000.0},
        },
        "frontend_contract": {
            "fields": [
                _field("synthese.moteur_electrique.puissance_sortie_w", "computed", value=100000.0, trace=trace),
                _field("synthese.systeme.P_bus_dc_design_w", "computed", value=122000.0),
                _field("partial.value", "partial", value=12.0),
                _field("untraced.value", "computed", value=13.0, confidence="untraced_report_value"),
                _field("candidate.cdc", "candidate_from_cdc", value=14.0),
                _field("candidate.profile", "candidate_from_power_profile", value=15.0),
                _field("opt.validated", "validated_by_optimization", value=16.0, trace=opt_trace),
                _field("opt.untraced", "validated_by_optimization", value=17.0),
                _field("opt.rejected", "rejected_by_optimization", value=18.0),
                _field("missing.required", "missing_required", value=None, blocking=True),
                _field("missing.optional", "missing_optional", value=None),
                _field("impossible.value", "impossible", value=None, blocking=True),
                _field("error.value", "error", value=None, blocking=True),
                _field("legacy.optimisee", "optimisee", value=20.0),
                _field("legacy.optimise_accent", "optimise", value=21.0),
                _field("legacy.optimise_unicode", "optimisé", value=22.0),
                _field("legacy.optimized", "optimized", value=23.0),
                _field("legacy.candidate_optimized", "candidate_optimized", value=24.0),
                _field("legacy.validated", "validated", value=25.0),
            ],
            "cao": {
                "solidworks_ready": True,
                "status": "partial",
                "missing_for_solidworks": ["alesage_m"],
            },
        },
        "mechanical_graphs": {
            "graphiques": [
                {
                    "id": "computed_traced",
                    "status": "computed",
                    "trace": trace,
                    "series": [{"name": "backend", "points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}],
                },
                {
                    "id": "computed_untraced",
                    "status": "computed",
                    "series": [{"name": "backend", "points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}],
                },
                {
                    "id": "validated_untraced",
                    "status": "validated_by_optimization",
                    "series": [{"name": "backend", "points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}],
                },
                {
                    "id": "candidate",
                    "status": "candidate_from_power_profile",
                    "series": [{"name": "backend", "points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}],
                },
            ]
        },
        "cao": {
            "solidworks_ready": True,
            "status": "partial",
            "missing_for_solidworks": ["alesage_m"],
        },
        "inconnues": {
            "bloquantes": [{"nom": "alesage_m", "raison": "cote non fournie"}],
        },
    }


def test_full_stack_status_contract_preserve_backend_truth():
    report = _backend_report_with_all_statuses()
    contract = report["frontend_contract"]
    model = build_contract_model(report)
    fields = model["fields_by_path"]

    assert fields["synthese.moteur_electrique.puissance_sortie_w"]["status"] == "computed"
    assert fields["synthese.systeme.P_bus_dc_design_w"]["status"] == "partial"
    assert fields["synthese.systeme.P_bus_dc_design_w"]["raw_status"] == "computed"
    assert fields["partial.value"]["status"] == "partial"
    assert fields["untraced.value"]["status"] == "partial"
    assert fields["candidate.cdc"]["status"] == "candidate_from_cdc"
    assert fields["candidate.profile"]["status"] == "candidate_from_power_profile"
    assert fields["opt.validated"]["status"] == "validated_by_optimization"
    assert fields["opt.untraced"]["status"] == "partial"
    assert fields["opt.rejected"]["status"] == "rejected_by_optimization"
    assert fields["missing.required"]["status"] == "missing_required"
    assert fields["missing.optional"]["status"] == "missing_optional"
    assert fields["impossible.value"]["status"] == "impossible"
    assert fields["error.value"]["status"] == "error"

    assert get_field_status(contract, "legacy.optimisee") == "candidate_from_cdc"
    assert get_field_status(contract, "legacy.optimized") == "partial"
    assert get_field_status(contract, "legacy.optimise_unicode") == "partial"
    assert get_field_status(contract, "legacy.candidate_optimized") == "candidate_from_cdc"
    assert get_field_status(contract, "legacy.validated") == "partial"
    assert normalize_contract_status("optimise") == "partial"
    assert normalize_contract_status("optimisé") == "partial"
    assert normalize_contract_status("optimise") != "validated_by_optimization"

    assert field_badge_label(fields["synthese.systeme.P_bus_dc_design_w"]) == "partiel"
    assert candidate_label(fields["candidate.cdc"]) == "proposee par le backend"
    assert candidate_label(fields["candidate.profile"]) == "hypothese de pre-dimensionnement"
    assert is_field_blocking(fields["missing.required"]) is True
    assert is_field_blocking(fields["impossible.value"]) is True
    assert is_field_blocking(fields["error.value"]) is True
    assert model["summary"]["blocking_count"] >= 3


def test_dashboard_metrics_and_raw_adapter_keep_untraced_values_partial():
    report = _backend_report_with_all_statuses()

    dashboard = build_dashboard_model({"raw_report": report})
    power_chain = dashboard["dashboard"]["power_chain"]

    assert power_chain[0]["status"] == "computed"
    assert power_chain[0]["trace_present"] is True
    assert power_chain[1]["status"] == "partial"
    assert power_chain[1]["confidence"] == "untraced_report_value"

    metric = resolve_metric(
        report,
        [{"raw_path": "synthese.systeme.P_bus_dc_design_w", "label": "Bus DC", "unit": "W"}],
    )
    assert metric["status"] == "partial"
    assert metric["confidence"] == "untraced_report_value"


def test_graphs_and_cao_refuse_untraced_or_partial_final_state():
    report = _backend_report_with_all_statuses()

    graphs = collect_backend_charts(report)
    by_id = {chart["id"]: chart for chart in graphs["charts"]}

    assert by_id["computed_traced"]["status"] == "computed"
    assert by_id["computed_untraced"]["status"] == "partial"
    assert by_id["validated_untraced"]["status"] == "partial"
    assert by_id["candidate"]["status"] == "candidate_from_power_profile"

    fig = build_chart_figure(by_id["computed_traced"])
    fig.clear()
    with pytest.raises(ValueError):
        build_chart_figure(by_id["computed_untraced"])
    with pytest.raises(ValueError):
        build_chart_figure(by_id["validated_untraced"])

    cao = build_cao_frontend_summary(report)
    assert cao["solidworks_ready"] is False
    assert cao["missing_for_solidworks"] == ["alesage_m"]
    assert cao["warning"]


def test_resource_catalog_marks_raw_chart_data_partial_not_final():
    catalog = build_resource_catalog({"cartographies": {"serie": [1, 2, 3]}})
    charts = catalog["resources"]["charts"]
    raw_chart = next(item for item in charts if item["name"] == "Donnees cartographie backend")

    assert raw_chart["status"] == "partial"
    assert raw_chart["reason"]

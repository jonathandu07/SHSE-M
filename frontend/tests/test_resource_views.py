from __future__ import annotations

from frontend.gui.resource_views import _split_resources_by_status


def test_resource_views_separent_disponibles_et_indisponibles():
    available, unavailable = _split_resources_by_status(
        [
            {"name": "cao", "status": "available"},
            {"name": "sketch", "status": "unavailable"},
            {"name": "json", "status": "partial"},
        ]
    )
    assert [item["name"] for item in available] == ["cao"]
    assert [item["name"] for item in unavailable] == ["sketch", "json"]


def test_resource_views_ne_traitent_pas_partial_comme_available():
    available, unavailable = _split_resources_by_status([{"name": "graph", "status": "partial"}])
    assert available == []
    assert unavailable[0]["name"] == "graph"

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_all_piece_modules_import_cleanly():
    root = Path(__file__).resolve().parents[1] / "components"
    modules = []
    for path in root.glob("*/pieces/*.py"):
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(root.parent).with_suffix("")
        module_name = "backend." + ".".join(rel.parts)
        modules.append(module_name)

    assert modules, "Aucun module de pièce détecté."

    for module_name in sorted(modules):
        module = importlib.import_module(module_name)
        assert module is not None, module_name


def test_real_system_report_keeps_piece_inventory_consistent():
    from backend.main import dimensionner_systeme_shsem

    report = dimensionner_systeme_shsem(55.0)

    pieces = report.get("pieces") or {}
    rapports = report.get("rapports_pieces") or {}
    construction = ((report.get("construction_pieces") or {}).get("construction")) or {}
    objets = ((report.get("objets_serialises") or {}).get("pieces")) or {}
    inventory = ((report.get("inventaire") or {}).get("pieces")) or {}

    assert len(pieces) >= 10
    assert len(inventory) >= len(pieces)

    for name, piece_obj in pieces.items():
        assert name in inventory, name
        assert name in objets, name
        assert isinstance(objets[name], dict), name
        construit = bool(inventory[name]["construit"])
        if construit:
            assert name in rapports, name
            assert name in construction, name
            assert inventory[name]["rapport_disponible"] is True
            assert isinstance(rapports[name], dict), name
            assert piece_obj is not None or objets[name].get("type") is not None, name
        else:
            assert piece_obj is None, name

    nested = {name: payload for name, payload in inventory.items() if "." in name}
    assert nested, "Aucune pièce imbriquée remontée par les composants."
    for name, payload in nested.items():
        assert payload["construit"] is True
        assert payload["rapport_disponible"] is True
        assert payload.get("source_composant"), name


def test_optimisation_depuis_rapport_backend_runs_on_real_report():
    from backend.main import dimensionner_systeme_shsem
    from backend.ensemble.optimisation import OptimisationSysteme

    report = dimensionner_systeme_shsem(55.0)
    analyse = OptimisationSysteme.depuis_rapport_backend(report).analyser()

    synthese = analyse["synthese_optimisation"]
    assert 0.0 <= synthese["score_coherence_100"] <= 100.0
    assert 0.0 <= synthese["score_global_100"] <= 100.0
    assert analyse["rapports_sources"]["systeme_complet"] is True
    assert analyse["rapports_sources"]["cylindre"] is True
    assert any(key in analyse["coherences"] for key in ("piston_vs_cylindre", "alesage_global"))

from __future__ import annotations

from frontend.ensemble.piece_data_adapter import extract_field, get_piece_report, require_fields


def test_data_adapter_ne_remplace_pas_cote_manquante_par_zero():
    report = {"rapports_pieces": {"arbre_piston": {"cao": {}}}}
    piece = get_piece_report(report, "arbre_piston")

    field = extract_field(piece, "cao.fut_central.diametre_exterieur_m", unit="m")
    required = require_fields(piece, [{"path": "cao.fut_central.diametre_exterieur_m", "unit": "m"}])

    assert field["value"] is None
    assert field["status"] == "missing_required"
    assert required["ok"] is False
    assert required["missing_fields"][0]["value"] is None


def test_data_adapter_extrait_piece_depuis_alias_backend():
    report = {"rapports_pieces": {"arbre_vilbrequin": {"piece": "arbre_vilbrequin", "cao": {"diametre_m": 0.04}}}}

    piece = get_piece_report(report, "arbre_vilebrequin")

    assert piece["piece"] == "arbre_vilbrequin"
    assert piece["cao"]["diametre_m"] == 0.04


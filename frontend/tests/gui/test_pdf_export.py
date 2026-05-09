from pathlib import Path

import matplotlib.pyplot as plt


def test_export_element_pdf_creates_multiview_document(tmp_path, monkeypatch):
    from frontend.gui import pdf_export

    calls = []

    def fake_get_viz_figure(name, obj, viz_type):
        calls.append((name, viz_type))
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot([0, 1], [0, 1])
        return fig

    monkeypatch.setattr(pdf_export, "get_viz_figure", fake_get_viz_figure)

    output = tmp_path / "piece.pdf"
    result = pdf_export.export_element_pdf(
        element_name="piston",
        display_name="PISTON",
        payload={
            "construit": True,
            "rapport_disponible": True,
            "inventaire": {"type": "Piston"},
            "rapport": {"dimensions": {"diametre_exterieur_m": 0.089}},
        },
        element_obj=object(),
        output_path=output,
        is_component=False,
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0
    assert calls == [
        ("piston", "sketches_2d"),
        ("piston", "views_3d"),
        ("piston", "charts"),
    ]


def test_export_element_pdf_handles_missing_views(tmp_path, monkeypatch):
    from frontend.gui import pdf_export

    monkeypatch.setattr(pdf_export, "get_viz_figure", lambda *args, **kwargs: None)

    output = tmp_path / "component.pdf"
    result = pdf_export.export_element_pdf(
        element_name="alternateur",
        display_name="ALTERNATEUR",
        payload={"construit": True, "rapport": {"note": "partiel"}},
        element_obj=None,
        output_path=output,
        is_component=True,
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_build_element_display_lines_filters_internal_backend_noise():
    from frontend.gui.pdf_export import build_element_display_lines

    lines = build_element_display_lines(
        {
            "construit": True,
            "inventaire": {"type": "ArbreMoteur", "source_composant": "moteur_thermique"},
            "construction": {
                "construit": True,
                "kwargs": {"moteur_thermique": {"resume": {"puissance_nominale_w": 150000.0}}},
            },
            "rapport": {
                "dimensionnements": {"couple_max_Nm": 447.6, "rpm": 3200.0},
                "cao": {"diametre_nominal_arbre_m": 0.052, "longueur_totale_m": 0.41},
                "inconnues": {"impossibles": ["tau_admissible_arbre_pa"], "partielles": []},
            },
        }
    )

    text = "\n".join(lines)
    assert "Dimensionnements" in text
    assert "couple_max_Nm" not in text
    assert "Couple max nm" in text
    assert "construction > kwargs" not in text.lower()
    assert "puissance_nominale_w" not in text
    assert "tau_admissible_arbre_pa" in text

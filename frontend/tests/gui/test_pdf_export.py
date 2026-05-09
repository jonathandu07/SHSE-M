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

import pytest
from frontend.gui.viz_utils import backend_graph_to_figure, backend_graphs_available, resolve_viz_module, get_draw_3d_func

def test_resolve_viz_module_pieces():
    """Vérifie que les pièces du moteur thermique sont correctement résolues."""
    # Test piston (2D)
    mod = resolve_viz_module("piston", "sketches_2d")
    assert mod is not None
    assert hasattr(mod, "draw") or hasattr(mod, "tracer_croquis_piston_2d")
    
    # Test bielle (3D)
    mod = resolve_viz_module("bielle", "views_3d")
    assert mod is not None
    assert hasattr(mod, "draw_3d")

def test_resolve_viz_module_subsystems():
    """Vérifie que les sous-systèmes racines sont correctement résolus."""
    # Test alternateur
    mod = resolve_viz_module("alternateur", "sketches_2d")
    assert mod is not None
    assert hasattr(mod, "tracer_croquis_alternateur_2d")
    
    # Test batterie
    mod = resolve_viz_module("batterie", "sketches_2d")
    assert mod is not None
    assert hasattr(mod, "tracer_croquis_batterie_2d")

def test_resolve_viz_module_spelling():
    """Vérifie la robustesse aux fautes de frappe et variations de casse."""
    # Test avec espaces et majuscules
    mod = resolve_viz_module("Arbre Vilebrequin", "charts")
    assert mod is not None
    
    # Test typo 'architecture'
    mod = resolve_viz_module("architecture", "sketches_2d")
    assert mod is not None
    assert "architechture" in mod.__name__
    
    # Test typo 'vilbrequin'
    mod = resolve_viz_module("arbre_vilbrequin", "charts")
    assert mod is not None

def test_get_draw_3d_func():
    """Vérifie la fonction de récupération des fonctions de dessin 3D."""
    func = get_draw_3d_func("piston")
    assert callable(func)
    
    # Test fallback
    func_fallback = get_draw_3d_func("piece_inexistante")
    assert callable(func_fallback)
    assert "viz_3d_generic" in func_fallback.__module__


def test_backend_graph_to_figure_utilise_uniquement_points_backend():
    graph = {
        "id": "courant_bus_vs_tension",
        "title": "Courant bus",
        "x_label": "U",
        "y_label": "I",
        "status": "available",
        "series": [{"name": "courant", "points": [{"x": 300, "y": 400}, {"x": 400, "y": 300}]}],
        "markers": [{"name": "design", "x": 400, "y": 300}],
        "interpretation": "Courbe fournie par backend.",
    }

    fig = backend_graph_to_figure(graph)

    assert fig is not None
    assert len(fig.axes[0].lines) == 1
    assert len(backend_graphs_available({"graphiques": [graph]})) == 1


def test_backend_graph_missing_reste_etat_vide_sans_generer_points():
    graph = {
        "id": "pertes_joule_vs_courant",
        "title": "Pertes Joule",
        "status": "missing_required",
        "missing": ["resistance_electrique_ohm"],
        "series": [],
        "markers": [],
    }

    fig = backend_graph_to_figure(graph)

    assert fig is not None
    assert len(fig.axes[0].lines) == 0

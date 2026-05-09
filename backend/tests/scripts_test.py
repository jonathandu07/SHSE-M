from __future__ import annotations

import json
from pathlib import Path


def test_generer_rapport_puissance_load_json_arg_supports_inline_and_file(tmp_path):
    from backend.scripts.generer_rapport_puissance import _load_json_arg

    inline = _load_json_arg('{"rpm_sortie":[1000,2000]}')
    assert inline["rpm_sortie"] == [1000, 2000]

    json_path = tmp_path / "search.json"
    json_path.write_text('{"tension_dc_v":[400,800]}', encoding="utf-8")
    from_file = _load_json_arg(str(json_path))
    assert from_file["tension_dc_v"] == [400, 800]


def test_generer_rapport_puissance_cli_main_writes_json_and_returns_zero(tmp_path, monkeypatch, capsys):
    from backend.scripts import generer_rapport_puissance as script

    output_path = tmp_path / "rapport.json"
    db_path = tmp_path / "rapport.db"
    key_path = tmp_path / "secret.key"
    monkeypatch.setattr(
        "sys.argv",
        [
            "generer_rapport_puissance.py",
            "100",
            "--unite",
            "kw",
            "--output-path",
            str(output_path),
            "--db-path",
            str(db_path),
            "--key-path",
            str(key_path),
            "--search-json",
            '{"rpm_sortie":[1000,2000],"tension_dc_v":[400,800]}',
        ],
    )

    rc = script.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert output_path.exists()
    assert payload["json_path"] == str(output_path)
    assert isinstance(payload["orchestration_pieces_active"], bool)
    assert payload["nombre_pieces"] >= 0


def test_simulation_script_runs_end_to_end_with_monkeypatched_visuals(tmp_path, monkeypatch):
    from backend.scripts import simulation_shse_m as script

    saved_paths = []
    captured = {}

    class FakeFig:
        def savefig(self, path):
            saved_paths.append(Path(path))

    class FakeSystemeComplet:
        def __init__(self, **kwargs):
            captured["systeme_init"] = dict(kwargs)

        def analyser(self, **kwargs):
            captured["systeme_analyser"] = dict(kwargs)
            return {"ok": True, "kwargs": kwargs}

    class FakeMoteurElectrique:
        def __init__(self, **kwargs):
            captured["moteur_electrique"] = dict(kwargs)

    class FakeBatterie:
        def __init__(self, **kwargs):
            captured["batterie"] = dict(kwargs)

    class FakeAlternateur:
        def __init__(self, **kwargs):
            captured["alternateur"] = dict(kwargs)

    class FakeMoteurThermique:
        def __init__(self, **kwargs):
            captured["moteur_thermique"] = dict(kwargs)

    class FakeBoiteCrabots:
        def __init__(self, **kwargs):
            captured["boite_crabots"] = dict(kwargs)

    class FakeArchitecture:
        def __init__(self, **kwargs):
            captured["architecture"] = dict(kwargs)

    monkeypatch.setattr(script, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(script, "SystemeComplet", FakeSystemeComplet)
    monkeypatch.setattr(script, "MoteurElectrique", FakeMoteurElectrique)
    monkeypatch.setattr(script, "Batterie", FakeBatterie)
    monkeypatch.setattr(script, "Alternateur", FakeAlternateur)
    monkeypatch.setattr(script, "MoteurThermique", FakeMoteurThermique)
    monkeypatch.setattr(script, "BoiteCrabots", FakeBoiteCrabots)
    monkeypatch.setattr(script, "Architecture", FakeArchitecture)
    monkeypatch.setattr(script, "tracer_croquis_batterie_2d", lambda *args, **kwargs: FakeFig())
    monkeypatch.setattr(script, "tracer_croquis_alternateur_2d", lambda *args, **kwargs: FakeFig())
    monkeypatch.setattr(script, "tracer_croquis_architecture_2d", lambda *args, **kwargs: FakeFig())

    script.executer_simulation()

    assert len(saved_paths) == 3
    assert {path.name for path in saved_paths} == {
        "viz_batterie.png",
        "viz_alternateur.png",
        "viz_architecture.png",
    }
    for path in saved_paths:
        assert path.parent == tmp_path / "backend" / "outputs" / "simulations"
    assert captured["moteur_electrique"]["puissance_max_w"] == 120000
    assert captured["batterie"]["tension_nominale_v"] == 400
    assert captured["alternateur"]["nombre_poles"] == 12
    assert captured["moteur_thermique"]["nombre_cylindres"] == 6
    assert set(captured["systeme_init"]) == {
        "moteur_electrique",
        "batterie",
        "alternateur",
        "moteur_thermique",
        "boite_crabots",
        "architecture",
    }
    assert captured["systeme_analyser"]["scenario_bus_dc"] == "charge"
    assert captured["systeme_analyser"]["puissance_elec_alt_cible_w"] == 45000.0
    assert captured["systeme_analyser"]["architecture_forcee"] == "V"

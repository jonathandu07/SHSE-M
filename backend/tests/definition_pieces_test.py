import importlib


def test_definition_pieces_saves_structured_piece_records(monkeypatch):
    definition_pieces = importlib.import_module("backend.modules.systeme.definition_pieces")
    orchestrateur = importlib.import_module("backend.modules.systeme.orchestrateur_pieces")

    saved = []

    def fake_dimensionner(**kwargs):
        return {
            "pieces": {
                "cylindre": {"nom": "cylindre", "indicateurs": {"masse_kg": 1.2}},
                "piston": {"nom": "piston", "indicateurs": {"masse_kg": 0.4}},
            },
            "rapports_pieces": {
                "cylindre": {"geometrie": {"diametre_interieur_nominal_m": 0.08}},
            },
            "construction_pieces": {
                "construction": {
                    "cylindre": {"construit": True},
                    "piston": {"construit": True},
                }
            },
            "objets_serialises": {"pieces": {"cylindre": {"type": "Cylindre"}}},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
            "synthese": {"masse_pieces_kg": 1.6},
        }

    class FakeDatabase:
        def save_record(self, category, name, payload):
            saved.append((category, name, payload))
            return len(saved)

    monkeypatch.setattr(orchestrateur, "dimensionner_pieces_moteur_thermique", fake_dimensionner)
    monkeypatch.setattr("backend.modules.systeme.database.SecureDatabase", FakeDatabase)

    result = definition_pieces.dimensionner_pieces_completes(
        puissance_cible_w=40000.0,
        regime_tr_min=3000.0,
        n_cyl=2,
        pression_max_pa=3.0e6,
    )

    assert result["masse_pieces_kg"] == 1.6
    assert sorted(result["pieces"]) == ["cylindre", "piston"]
    assert ("piece_inventaire", "cylindre", result["pieces"]["cylindre"]) in saved
    assert ("piece_rapport", "cylindre", result["rapports_pieces"]["cylindre"]) in saved
    assert ("piece_construction", "piston", {"construit": True}) in saved


def test_orchestrateur_pieces_builds_report_from_backend_main(monkeypatch):
    orchestrateur = importlib.import_module("backend.modules.systeme.orchestrateur_pieces")

    class FakePiece:
        pass

    piece = FakePiece()
    piece.masse_kg = 2.5

    class FakeMain:
        @staticmethod
        def _collect_public_data(obj):
            return {
                "type": type(obj).__name__,
                "attributs": {"masse_kg": getattr(obj, "masse_kg", None)},
            }

        @staticmethod
        def construire_pieces_depuis_systeme(**kwargs):
            assert kwargs["definition_moteur_thermique"]["alesage_m"] == 0.08
            assert kwargs["definition_moteur_thermique"]["course_m"] == 0.06
            pieces = {"cylindre": piece}
            rapport = {
                "construction": {"cylindre": {"construit": True, "type": "FakePiece"}},
                "rapports_pieces": {
                    "cylindre": {
                        "geometrie": {"diametre_interieur_nominal_m": 0.08},
                        "dimensionnement": {"facteur_securite": 2.1},
                    }
                },
                "inconnues": {"impossibles": [], "partielles": []},
                "notes_modele": ["ok"],
            }
            return pieces, rapport

    monkeypatch.setattr(orchestrateur.importlib, "import_module", lambda name: FakeMain())

    report = orchestrateur.dimensionner_pieces_moteur_thermique(
        puissance_cible_w=50000.0,
        regime_tr_min=3000.0,
        n_cyl=2,
        pression_max_pa=3.0e6,
        pme_pa=8.0e5,
        alesage_m=0.08,
        course_m=0.06,
    )

    assert report["synthese"]["nombre_pieces_construites"] == 1
    assert report["synthese"]["masse_pieces_kg"] == 2.5
    assert report["pieces"]["cylindre"]["indicateurs"]["facteur_securite"] == 2.1
    assert report["notes_modele"][-1] == "ok"

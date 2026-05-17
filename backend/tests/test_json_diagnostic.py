import json
import subprocess
import sys
from pathlib import Path

from backend.modules.systeme.json_diagnostic import (
    dedupliquer_problemes,
    detecter_type_json,
    diagnostiquer_json_sthome,
    extraire_inconnues_et_alertes,
)


def _sample_report():
    return {
        "meta": {"project_id": "p1"},
        "sous_systemes": {},
        "pieces": {},
        "synthese": {},
        "tracabilite": {},
        "inconnues": {
            "impossibles": [
                {
                    "nom": "moteur_thermique_definir_depuis_exigences",
                    "path": "rapports.composants.moteur_thermique_definition",
                    "raison": "MoteurThermique.definir_depuis_exigences() missing required keyword-only arguments: rpm, pme_pa",
                },
                {
                    "nom": "boite_crabots.rapports",
                    "path": "composants.boite_crabots.rapports",
                    "raison": "Rapports de boite absents : impossible de relier alternateur et moteur thermique.",
                },
                {
                    "nom": "couple_alternateur_nm",
                    "path": "alternateur.couple_alternateur_nm",
                    "raison": "couple alternateur non fourni par les analyses disponibles",
                },
            ],
            "partielles": [
                {"nom": "rpm_moteur", "path": "moteur_thermique.rpm_min", "raison": "Plage de regime moteur thermique absente."},
                {"nom": "couple_alternateur_nm", "path": "strategie_energie.couple_alternateur_nm", "raison": "couple alternateur non fourni par les analyses disponibles"},
            ],
        },
        "cao": {"available": False, "solidworks_ready_detaille": False},
    }


def test_detecte_config_rapport_frontend_contract():
    assert detecter_type_json({"meta": {}, "composants": {}, "pieces": {}, "analyses": {}}) == "config"
    assert detecter_type_json(_sample_report()) == "rapport_sthome"
    assert detecter_type_json({"fields": [], "cao": {}}) == "frontend_contract"


def test_extrait_inconnues_depuis_plusieurs_sections():
    data = _sample_report()
    data["frontend"] = {"unknowns": {"impossibles": [{"champ": "solidworks_ready", "raison": "CAO absente"}]}}
    extracted = extraire_inconnues_et_alertes(data)
    champs = {item["champ"] for item in extracted["items"]}
    assert "couple_alternateur_nm" in champs
    assert "solidworks_ready" in champs


def test_dedoublonne_par_alias_et_raison():
    extracted = extraire_inconnues_et_alertes(_sample_report())
    dedup = dedupliquer_problemes(extracted["items"])
    assert dedup["doublons"]
    assert any(group["cause_probable"] == "couple_alternateur_nm" for group in dedup["causes_probables"])


def test_identifie_causes_racines_et_patchs_non_automatiques():
    diagnostic = diagnostiquer_json_sthome(data=_sample_report(), strict=True)
    ids = {cause["id"] for cause in diagnostic["causes_racines"]}
    assert "couple_alternateur_absent" in ids
    assert "boite_crabots_rapports" in ids
    assert "rpm_moteur_absent" in ids
    assert all(patch["apply_automatically"] is False for patch in diagnostic["patchs_proposes"])


def test_ne_propose_pas_3000_rpm_ni_400v_en_strict():
    diagnostic = diagnostiquer_json_sthome(data=_sample_report(), strict=True)
    text = json.dumps(diagnostic, ensure_ascii=False)
    assert "3000" not in text
    assert "400" not in text


def test_diagnostic_json_serializable():
    diagnostic = diagnostiquer_json_sthome(data=_sample_report(), strict=True)
    json.dumps(diagnostic, ensure_ascii=False)


def test_cli_exporte_un_diagnostic(tmp_path):
    input_path = tmp_path / "rapport.json"
    output_path = tmp_path / "diagnostic.json"
    input_path.write_text(json.dumps(_sample_report()), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "backend/scripts/diagnose_sthome_json.py", str(input_path), "--out", str(output_path), "--strict"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["type_detecte"] == "rapport_sthome"

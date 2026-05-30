from __future__ import annotations

"""Validation end-to-end du scenario 100 kW sortie moteur electrique."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ensemble.STHO_ME import STHO_ME
from backend.modules.systeme.cao_dossier import construire_dossier_cao_sthome
from backend.modules.systeme.chain_validator import valider_chaine_puissance_sthome
from backend.modules.systeme.frontend_contract import build_frontend_contract
from backend.modules.systeme.json_diagnostic import diagnostiquer_json_sthome
from backend.modules.systeme.mechanical_graphs import generer_graphiques_mecaniques


CONFIG_100KW = {
    "puissance_sortie_kw": 100.0,
    "puissance_sortie_moteur_electrique_kw": 100.0,
}

CAHIER_DES_CHARGES_100KW = {
    "mode_resolution": "pre_dimensionnement",
    "duty_cycle_moteur_thermique_max": 0.50,
    "marge_wltp": 0.20,
    "systeme_multi_energies": True,
    "compatibilite_solidworks_requise": True,
}


def valider_scenario_100kw(*, out_dir: str | Path | None = None, strict: bool = False) -> dict[str, Any]:
    export_dir = Path(out_dir) if out_dir is not None else ROOT / "backend" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    rapport = STHO_ME().analyser(
        config=CONFIG_100KW,
        cahier_des_charges=CAHIER_DES_CHARGES_100KW,
        resolve_unknowns=True,
        optimize=True,
        strict=strict,
        frontend_contract=False,
    )
    chain = valider_chaine_puissance_sthome(rapport, puissance_sortie_w=100_000.0, strict=strict)
    rapport["validation_chaine_100kw"] = chain

    mechanical_graphs = generer_graphiques_mecaniques(rapport, strict=strict)
    rapport["mechanical_graphs"] = mechanical_graphs
    cao_dossier = construire_dossier_cao_sthome(rapport, strict=strict)
    rapport["cao_dossier"] = cao_dossier
    rapport["cao"] = _merge_cao(rapport.get("cao"), cao_dossier.get("resume"))
    chain["livrables"] = _livrables_from_cao(cao_dossier)
    chain["livrables"]["power_chain_ok"] = bool(chain.get("ok"))

    rapport["frontend"] = build_frontend_contract(rapport)
    diagnostic = diagnostiquer_json_sthome(
        data=rapport,
        source_name="validation_100kw",
        strict=True,
        include_patch=True,
    )

    paths = {
        "rapport": export_dir / "rapport_100kw.json",
        "frontend_contract": export_dir / "frontend_contract_100kw.json",
        "diagnostic": export_dir / "diagnostic_100kw.json",
        "cao_dossier": export_dir / "cao_dossier_100kw.json",
        "mechanical_graphs": export_dir / "mechanical_graphs_100kw.json",
    }
    _write_json(paths["rapport"], rapport)
    _write_json(paths["frontend_contract"], rapport["frontend"])
    _write_json(paths["diagnostic"], diagnostic)
    _write_json(paths["cao_dossier"], cao_dossier)
    _write_json(paths["mechanical_graphs"], mechanical_graphs)

    return {
        "rapport": rapport,
        "frontend_contract": rapport["frontend"],
        "diagnostic": diagnostic,
        "cao_dossier": cao_dossier,
        "mechanical_graphs": mechanical_graphs,
        "validation_chaine": chain,
        "paths": {k: str(v) for k, v in paths.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valide la chaine STHO-ME 100 kW sortie moteur electrique.")
    parser.add_argument("--out-dir", default=str(ROOT / "backend" / "exports"), help="Dossier d'export JSON.")
    parser.add_argument("--strict", action="store_true", help="Lance l'orchestrateur en mode strict.")
    args = parser.parse_args(argv)

    result = valider_scenario_100kw(out_dir=args.out_dir, strict=bool(args.strict))
    _print_summary(result)
    return 0


def _print_summary(result: Mapping[str, Any]) -> None:
    rapport = _safe_dict(result.get("rapport"))
    chain = _safe_dict(result.get("validation_chaine"))
    values = _safe_dict(chain.get("valeurs"))
    diagnostic = _safe_dict(result.get("diagnostic"))
    resume_diag = _safe_dict(diagnostic.get("resume"))
    cao_dossier = _safe_dict(result.get("cao_dossier"))
    cao_resume = _safe_dict(cao_dossier.get("resume"))

    print("=== VALIDATION CHAINE 100 kW ===")
    print(f"Puissance sortie moteur electrique : {_fmt(values.get('puissance_sortie_moteur_electrique_w'), 'W')}")
    print(f"Puissance bus DC : {_fmt(values.get('puissance_bus_dc_design_w'), 'W')}")
    print(f"Puissance alternateur electrique : {_fmt(values.get('puissance_alternateur_electrique_w'), 'W')}")
    print(f"Puissance moteur thermique arbre : {_fmt(values.get('puissance_moteur_thermique_arbre_w'), 'W')}")
    print(f"Regime moteur thermique : {_fmt(values.get('rpm_moteur_thermique'), 'rpm')}")
    print(f"Couple moteur thermique : {_fmt(values.get('couple_moteur_thermique_nm'), 'Nm')}")
    print(f"Batterie : {_brief(_get_path(rapport, 'sous_systemes.batterie'))}")
    print(f"Boite : {_brief(_get_path(rapport, 'sous_systemes.boite_crabots'))}")
    print(f"Statut optimisation : {_brief(rapport.get('optimisation'))}")
    print(f"Dossier de modelisation disponible : {_get_path(rapport, 'frontend.cao.available')}")
    print(f"Croquis cotes : {_fmt_bool(cao_resume.get('sketches_available'))}")
    print(f"Vues 3D indicatives : {_fmt_bool(cao_resume.get('views_3d_available'))}")
    print(f"Graphiques contraintes : {_fmt_bool(cao_resume.get('stress_graphs_available'))}")
    print(f"Preparation SolidWorks suffisante : {_fmt_bool(cao_resume.get('solidworks_ready'))}")
    print(f"Generation STEP : {_fmt_bool(cao_resume.get('step_export'))}")
    print(f"Score chaine : {chain.get('score_chaine_100')}")
    print(f"Chaine OK : {chain.get('ok')}")
    print(f"Causes racines restantes : {resume_diag.get('nb_causes_racines', 0)}")
    for index, cause in enumerate(diagnostic.get("causes_racines", [])[:5], start=1):
        if not isinstance(cause, Mapping):
            continue
        print(f"{index}. {cause.get('id')} - {cause.get('raison')}")
    print("Exports :")
    for name, path in _safe_dict(result.get("paths")).items():
        print(f"- {name}: {path}")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(_jsonable(data), ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_cao(existing: Any, resume: Any) -> dict[str, Any]:
    out = dict(existing) if isinstance(existing, Mapping) else {}
    if isinstance(resume, Mapping):
        out.update({str(k): _jsonable(v) for k, v in resume.items()})
    out["step_export"] = False
    out["solidworks_ready"] = False
    return out


def _livrables_from_cao(cao_dossier: Any) -> dict[str, Any]:
    resume = _safe_dict(cao_dossier.get("resume")) if isinstance(cao_dossier, Mapping) else {}
    return {
        "power_chain_ok": None,
        "mechanical_presizing_ok": bool(resume.get("drawing_data_available")),
        "stress_graphs_available": bool(resume.get("stress_graphs_available")),
        "sketches_available": bool(resume.get("sketches_available")),
        "views_3d_available": bool(resume.get("views_3d_available")),
        "solidworks_ready": False,
        "step_export": False,
    }


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _get_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _fmt(value: Any, unit: str) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.3g} {unit}"
    return "-"


def _fmt_bool(value: Any) -> str:
    if value is True:
        return "OUI"
    if value is False:
        return "NON"
    return "-"


def _brief(value: Any) -> str:
    if isinstance(value, Mapping):
        if value.get("status"):
            return str(value.get("status"))
        keys = [str(k) for k in value.keys()]
        return ", ".join(keys[:5]) if keys else "present"
    if value:
        return str(value)
    return "absent"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())

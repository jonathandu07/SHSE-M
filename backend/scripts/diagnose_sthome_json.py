from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.modules.systeme.json_diagnostic import diagnostiquer_json_sthome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostiquer un JSON STHO-ME sans appliquer de patch.")
    parser.add_argument("json_path", help="Chemin du rapport ou de la config JSON.")
    parser.add_argument("--out", default=None, help="Chemin de sortie du diagnostic JSON complet.")
    parser.add_argument("--mode", default="rapport_ou_config", help="Mode descriptif du diagnostic.")
    parser.add_argument("--strict", action="store_true", help="Mode strict: aucune valeur proposee comme definitive.")
    parser.add_argument("--max-items", type=int, default=500, help="Nombre maximum de symptomes analyses.")
    args = parser.parse_args(argv)

    path = Path(args.json_path).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise SystemExit("Le JSON racine doit etre un objet.")

    diagnostic = diagnostiquer_json_sthome(
        data=data,
        source_name=str(path),
        mode=args.mode,
        strict=bool(args.strict),
        max_items=args.max_items,
    )
    _print_summary(diagnostic)

    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nDiagnostic JSON ecrit: {out}")
    return 0


def _print_summary(diagnostic: Mapping[str, Any]) -> None:
    meta = diagnostic.get("meta", {}) if isinstance(diagnostic.get("meta"), Mapping) else {}
    resume = diagnostic.get("resume", {}) if isinstance(diagnostic.get("resume"), Mapping) else {}
    causes = diagnostic.get("causes_racines", [])

    print("=== DIAGNOSTIC STHO-ME JSON ===")
    print(f"Type detecte : {meta.get('type_detecte', 'inconnu')}")
    print(f"Statut : {str(resume.get('statut', 'inconnu')).upper()}")
    print(f"Score diagnostic : {resume.get('score_diagnostic_100', 0)}/100")
    print("")
    print("Causes racines :")
    if not causes:
        print("Aucune cause racine evidente detectee.")
        return
    for index, cause in enumerate(causes[:10], start=1):
        if not isinstance(cause, Mapping):
            continue
        impact = cause.get("impact", {}) if isinstance(cause.get("impact"), Mapping) else {}
        actions = cause.get("actions", []) if isinstance(cause.get("actions"), list) else []
        print(f"{index}. {cause.get('id')}")
        print(f"   Impact : {impact.get('nb_symptomes_expliques', 0)} symptomes")
        print(f"   Action : {actions[0] if actions else 'Corriger la cause racine.'}")


if __name__ == "__main__":
    raise SystemExit(main())

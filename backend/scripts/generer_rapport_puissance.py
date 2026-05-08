from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _load_json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    candidate = Path(value)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genere un rapport strict depuis une puissance, puis l'ecrit en JSON et en BDD.",
    )
    parser.add_argument("puissance", type=float, help="Puissance demandee.")
    parser.add_argument("--unite", default="kw", help="Unite: W, kW, ch, cv, hp.")
    parser.add_argument("--report-name", default=None, help="Nom logique du rapport en BDD.")
    parser.add_argument("--output-dir", default=None, help="Dossier de sortie JSON.")
    parser.add_argument("--output-path", default=None, help="Chemin JSON exact.")
    parser.add_argument("--db-path", default=None, help="Chemin SQLite exact.")
    parser.add_argument("--key-path", default=None, help="Chemin de cle exact.")
    parser.add_argument("--known-json", default=None, help="JSON ou chemin JSON des donnees connues.")
    parser.add_argument("--search-json", default=None, help="JSON ou chemin JSON de l'espace de recherche vectorise.")
    parser.add_argument("--constraints-json", default=None, help="JSON ou chemin JSON des contraintes.")
    parser.add_argument("--max-candidats", type=int, default=50000)
    parser.add_argument("--no-json", action="store_true", help="Ne pas ecrire de fichier JSON.")
    parser.add_argument("--no-db", action="store_true", help="Ne pas sauvegarder en BDD.")
    args = parser.parse_args()

    from backend.main import generer_rapport_puissance_json_bdd

    result = generer_rapport_puissance_json_bdd(
        args.puissance,
        args.unite,
        report_name=args.report_name,
        output_dir=args.output_dir,
        output_path=args.output_path,
        db_path=args.db_path,
        key_path=args.key_path,
        donnees_connues=_load_json_arg(args.known_json),
        espace_recherche=_load_json_arg(args.search_json),
        contraintes=_load_json_arg(args.constraints_json),
        max_candidats=args.max_candidats,
        exporter_json_file=not args.no_json,
        sauvegarder_bdd=not args.no_db,
    )
    payload = {k: v for k, v in result.items() if k != "rapport"}
    rapport = result.get("rapport", {}) or {}
    payload["orchestration_pieces_active"] = bool((rapport.get("orchestration_pieces") or {}).get("active"))
    payload["nombre_pieces"] = len((rapport.get("pieces") or {}))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

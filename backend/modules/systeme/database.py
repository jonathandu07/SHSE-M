# backend/modules/systeme/database.py
from __future__ import annotations

import base64
import dataclasses
import hashlib
import importlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from cryptography.fernet import Fernet


class SecureDatabase:
    """
    Base chiffrée pour stocker le rapport produit par backend/main.py.

    Objectif :
    - conserver l'état courant du système complet,
    - écraser les anciennes valeurs quand un nouveau calcul arrive,
    - permettre une lecture ciblée par section, pièce, composant,
    - garder les noms/index en clair pour la recherche,
    - chiffrer le contenu technique.
    """

    def __init__(
        self,
        db_path: str = "shse_technical_data.db",
        key_path: str = "secret.key",
    ) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        db_file = Path(db_path)
        key_file = Path(key_path)
        self.db_path = str((db_file if db_file.is_absolute() else base_dir / db_file).resolve())
        self.key_path = str((key_file if key_file.is_absolute() else base_dir / key_file).resolve())
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)
        self._init_db()

    # -----------------------------------------------------------------
    # Clé / chiffrement
    # -----------------------------------------------------------------
    def _load_or_generate_key(self) -> bytes:
        key_file = Path(self.key_path)
        if key_file.exists():
            key = key_file.read_bytes().strip()
            if not key:
                raise ValueError("Le fichier de clé existe mais est vide.")
            return key

        key = Fernet.generate_key()
        key_file.write_bytes(key)
        try:
            os.chmod(self.key_path, 0o600)
        except Exception:
            pass
        return key

    def _encrypt(self, payload: Mapping[str, Any] | list | str | int | float | bool | None) -> bytes:
        raw = json.dumps(self._to_jsonable(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self.cipher.encrypt(raw)

    def _decrypt(self, encrypted_data: bytes) -> Any:
        decrypted_json = self.cipher.decrypt(encrypted_data)
        return json.loads(decrypted_json.decode("utf-8"))

    # -----------------------------------------------------------------
    # Base SQLite
    # -----------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()

            # Index clair des entrées sauvegardées.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category, name)
                )
                """
            )

            # Contenu technique chiffré.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS record_payloads (
                    record_id INTEGER PRIMARY KEY,
                    data_encrypted BLOB NOT NULL,
                    sha256 TEXT,
                    size_bytes INTEGER,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
                )
                """
            )

            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_category ON records(category)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_name ON records(name)"
            )
            conn.commit()

    # -----------------------------------------------------------------
    # Sérialisation robuste
    # -----------------------------------------------------------------
    def _to_jsonable(self, value: Any, *, depth: int = 0, max_depth: int = 8) -> Any:
        if depth > max_depth:
            return {"type": type(value).__name__}

        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, bytes):
            return {
                "type": "bytes",
                "base64": base64.b64encode(value).decode("ascii"),
            }

        if dataclasses.is_dataclass(value):
            try:
                return self._to_jsonable(dataclasses.asdict(value), depth=depth + 1, max_depth=max_depth)
            except Exception:
                return {"type": type(value).__name__}

        if isinstance(value, Mapping):
            return {
                str(k): self._to_jsonable(v, depth=depth + 1, max_depth=max_depth)
                for k, v in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [self._to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]

        if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
            try:
                return self._to_jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
            except Exception:
                pass

        if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
            try:
                return self._to_jsonable(value.to_dict(), depth=depth + 1, max_depth=max_depth)
            except Exception:
                pass

        if hasattr(value, "__dict__"):
            try:
                public_attrs = {
                    k: v
                    for k, v in vars(value).items()
                    if not k.startswith("_") and not callable(v)
                }
                if public_attrs:
                    return {
                        "type": type(value).__name__,
                        "attributs": self._to_jsonable(public_attrs, depth=depth + 1, max_depth=max_depth),
                    }
            except Exception:
                pass

        return {"type": type(value).__name__, "repr": repr(value)}

    def _hash_payload(self, payload: Any) -> str:
        raw = json.dumps(self._to_jsonable(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    # -----------------------------------------------------------------
    # API bas niveau
    # -----------------------------------------------------------------
    def save_record(self, category: str, name: str, payload: Any) -> int:
        """
        Sauvegarde une entrée et écrase sa valeur précédente si elle existe déjà.
        """
        if not category or not name:
            raise ValueError("category et name sont obligatoires.")

        encrypted_blob = self._encrypt(payload)
        payload_hash = self._hash_payload(payload)
        size_bytes = len(encrypted_blob)

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO records (category, name) VALUES (?, ?) "
                "ON CONFLICT(category, name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP",
                (category, name),
            )
            cur.execute(
                "SELECT id FROM records WHERE category = ? AND name = ?",
                (category, name),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Impossible de récupérer l'identifiant pour {category}:{name}")

            record_id = int(row["id"])
            cur.execute(
                """
                INSERT INTO record_payloads (record_id, data_encrypted, sha256, size_bytes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    data_encrypted = excluded.data_encrypted,
                    sha256 = excluded.sha256,
                    size_bytes = excluded.size_bytes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (record_id, encrypted_blob, payload_hash, size_bytes),
            )
            conn.commit()
            return record_id

    def get_record(self, category: str, name: str) -> Any:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT rp.data_encrypted
                FROM records r
                JOIN record_payloads rp ON rp.record_id = r.id
                WHERE r.category = ? AND r.name = ?
                """,
                (category, name),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return self._decrypt(row["data_encrypted"])

    def list_records(self, category: Optional[str] = None) -> list[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            if category:
                cur.execute(
                    "SELECT category, name, updated_at FROM records WHERE category = ? ORDER BY name",
                    (category,),
                )
            else:
                cur.execute("SELECT category, name, updated_at FROM records ORDER BY category, name")
            return [dict(row) for row in cur.fetchall()]

    def delete_record(self, category: str, name: str) -> bool:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM records WHERE category = ? AND name = ?", (category, name))
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted

    # -----------------------------------------------------------------
    # Compatibilité avec ton ancien usage orienté pièce
    # -----------------------------------------------------------------
    def _infer_piece_name(self, piece_obj: Any) -> str:
        for attr in ("nom", "name", "designation", "id_piece"):
            value = getattr(piece_obj, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return type(piece_obj).__name__

    def save_piece(self, piece_obj: Any) -> int:
        name = self._infer_piece_name(piece_obj)
        payload = self._to_jsonable(piece_obj)
        return self.save_record("piece_objet", name, payload)

    def get_piece_data(self, piece_name: str) -> Dict[str, Any]:
        """
        Retourne une vue fusionnée d'une pièce si elle a été sauvée depuis main.py.
        """
        return {
            "piece": piece_name,
            "inventaire": self.get_record("piece_inventaire", piece_name),
            "rapport": self.get_record("piece_rapport", piece_name),
            "objet_serialise": self.get_record("piece_objet", piece_name),
            "construction": self.get_record("piece_construction", piece_name),
        }

    def get_all_pieces(self) -> Dict[str, Any]:
        names = [row["name"] for row in self.list_records("piece_inventaire")]
        if not names:
            # fallback si inventaire absent mais rapport/objet présents
            seen = set()
            for cat in ("piece_rapport", "piece_objet", "piece_construction"):
                for row in self.list_records(cat):
                    seen.add(row["name"])
            names = sorted(seen)
        return {name: self.get_piece_data(name) for name in names}

    # -----------------------------------------------------------------
    # Sauvegarde structurée du rapport produit par main.py
    # -----------------------------------------------------------------
    def save_main_report(self, report: Mapping[str, Any], *, report_name: str = "latest") -> Dict[str, int]:
        """
        Sauvegarde tout le rapport renvoyé par backend.main.dimensionner_systeme_shsem.
        Chaque enregistrement est écrasé à la prochaine sauvegarde portant le même nom.
        """
        report_jsonable = self._to_jsonable(dict(report))
        saved: Dict[str, int] = {}

        # Rapport complet courant
        saved["report_complet"] = self.save_record("main_report", report_name, report_jsonable)

        # Sections principales en accès rapide
        top_sections = (
            "meta",
            "entrees",
            "inventaire",
            "resume_gui",
            "systeme_complet",
            "analyses_composants",
            "construction_pieces",
            "rapports_pieces",
            "optimisation",
            "stho_me_secondaire",
            "legacy",
            "objets_serialises",
            "inconnues",
            "alertes",
            "notes_modele",
            "synthese",
        )
        for section in top_sections:
            if section in report_jsonable:
                saved[f"section:{section}"] = self.save_record("main_section", section, report_jsonable[section])

        # Inventaire pièces/composants
        inventaire = report_jsonable.get("inventaire", {}) if isinstance(report_jsonable, dict) else {}
        for name, payload in dict(inventaire.get("pieces", {}) or {}).items():
            saved[f"piece_inventaire:{name}"] = self.save_record("piece_inventaire", str(name), payload)
        for name, payload in dict(inventaire.get("composants", {}) or {}).items():
            saved[f"component_inventaire:{name}"] = self.save_record("component_inventaire", str(name), payload)

        # Rapports de pièces et composants
        for name, payload in dict(report_jsonable.get("rapports_pieces", {}) or {}).items():
            saved[f"piece_rapport:{name}"] = self.save_record("piece_rapport", str(name), payload)
        for name, payload in dict(report_jsonable.get("analyses_composants", {}) or {}).items():
            saved[f"component_rapport:{name}"] = self.save_record("component_rapport", str(name), payload)

        # Construction des pièces
        construction_pieces = report_jsonable.get("construction_pieces", {}) or {}
        for name, payload in dict(construction_pieces.get("construction", {}) or {}).items():
            saved[f"piece_construction:{name}"] = self.save_record("piece_construction", str(name), payload)

        # Objets sérialisés
        objets_serialises = report_jsonable.get("objets_serialises", {}) or {}
        for name, payload in dict(objets_serialises.get("pieces", {}) or {}).items():
            saved[f"piece_objet:{name}"] = self.save_record("piece_objet", str(name), payload)
        for name, payload in dict(objets_serialises.get("composants", {}) or {}).items():
            saved[f"component_objet:{name}"] = self.save_record("component_objet", str(name), payload)

        return saved

    def load_main_report(self, report_name: str = "latest") -> Any:
        return self.get_record("main_report", report_name)

    def load_resume_gui(self) -> Any:
        return self.get_record("main_section", "resume_gui")

    def load_synthese(self) -> Any:
        return self.get_record("main_section", "synthese")

    def load_systeme_complet(self) -> Any:
        return self.get_record("main_section", "systeme_complet")

    # -----------------------------------------------------------------
    # Exécution directe du calcul depuis backend.main puis sauvegarde
    # -----------------------------------------------------------------
    def _import_main_module(self) -> Any:
        candidates = (
            "backend.main",
            "main",
        )
        last_error: Optional[Exception] = None
        for module_name in candidates:
            try:
                return importlib.import_module(module_name)
            except Exception as exc:
                last_error = exc
                continue
        if last_error is None:
            raise ImportError("Impossible d'importer backend.main")
        raise ImportError(f"Impossible d'importer backend.main: {last_error}") from last_error

    def compute_and_save_from_main(
        self,
        *,
        report_name: str = "latest",
        function_name: str = "dimensionner_systeme_shsem",
        **main_kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Lance le calcul dans backend.main puis écrase les données précédentes du même report_name.
        """
        main_module = self._import_main_module()
        fn = getattr(main_module, function_name, None)
        if not callable(fn):
            raise AttributeError(f"Fonction introuvable dans main.py : {function_name}")

        report = fn(**main_kwargs)
        if not isinstance(report, Mapping):
            raise TypeError("Le résultat renvoyé par main.py doit être un dictionnaire ou un Mapping.")

        saved = self.save_main_report(report, report_name=report_name)
        return {
            "report_name": report_name,
            "records_saved": len(saved),
            "record_ids": saved,
            "resume_gui": self.load_resume_gui(),
        }


if __name__ == "__main__":
    db = SecureDatabase()

    # Exemple minimal :
    # - calcule le système via backend.main.dimensionner_systeme_shsem
    # - sauvegarde le rapport courant en écrasant le précédent "latest"
    result = db.compute_and_save_from_main(
        report_name="latest",
        puissance_traction_kw=40.0,
        charger_batterie=True,
        temps_charge_cible_h=1.0,
        vitesse_moteur_thermique_rpm=3000.0,
        rapport_vitesse_alt_sur_moteur=2.0,
        pme_pa=8.0e5,
        vitesse_piston_max_ms=10.0,
        longueur_dispo_m=1.2,
        largeur_dispo_m=0.8,
        pression_max_pa=3.0e6,
        contrainte_admissible_pa=1.2e8,
        densite_materiau_kg_m3=7800.0,
        cout_matiere_eur_kg=2.0,
        rendement_mecanique_cible_min=0.80,
        moteur_thermique_definition={
            "temps_moteur": 4,
            "nombre_cylindres": 1,
            "architecture": "mono",
            "alesage_m": 0.090,
            "course_m": 0.080,
            "rpm_nominal": 3000.0,
            "pme_pa": 8.0e5,
            "pression_max_pa": 3.0e6,
            "carburant": "essence",
        },
    )

    print("[BDD] Sauvegarde terminée")
    print(json.dumps(result, ensure_ascii=False, indent=2))

from __future__ import annotations

from typing import Any, Mapping, Optional


def dimensionner_pieces_completes(
    *,
    puissance_cible_w: float,
    regime_tr_min: float,
    n_cyl: int,
    pression_max_pa: float,
    pme_pa: Optional[float] = None,
    alesage_m: Optional[float] = None,
    course_m: Optional[float] = None,
    longueur_bielle_m: Optional[float] = None,
    definition_moteur_thermique: Optional[Mapping[str, Any]] = None,
    pieces_definition: Optional[Mapping[str, Any]] = None,
    rapport_systeme: Optional[Mapping[str, Any]] = None,
    moteur_thermique_obj: Any = None,
    systeme_obj: Any = None,
    save_to_db: bool = True,
) -> dict[str, Any]:
    """
    Compatibilite legacy autour du vrai orchestrateur de pieces.

    Cette fonction ne fabrique plus de dimensions arbitraires. Elle
    centralise les entrees, appelle l'orchestrateur reel fonde sur
    `backend/components`, puis expose un format stable pour `backend.main`
    et la GUI.
    """

    from backend.modules.systeme.orchestrateur_pieces import dimensionner_pieces_moteur_thermique

    report = dimensionner_pieces_moteur_thermique(
        puissance_cible_w=puissance_cible_w,
        regime_tr_min=regime_tr_min,
        n_cyl=n_cyl,
        pression_max_pa=pression_max_pa,
        pme_pa=pme_pa,
        alesage_m=alesage_m,
        course_m=course_m,
        longueur_bielle_m=longueur_bielle_m,
        definition_moteur_thermique=definition_moteur_thermique,
        pieces_definition=pieces_definition,
        rapport_systeme=rapport_systeme,
        moteur_thermique_obj=moteur_thermique_obj,
        systeme_obj=systeme_obj,
    )

    db_error = None
    if save_to_db:
        try:
            from backend.modules.systeme.database import SecureDatabase

            db = SecureDatabase()
            for name, payload in dict(report.get("pieces", {}) or {}).items():
                db.save_record("piece_inventaire", str(name), payload)
            for name, payload in dict(report.get("rapports_pieces", {}) or {}).items():
                db.save_record("piece_rapport", str(name), payload)
            construction = dict(report.get("construction_pieces", {}) or {}).get("construction", {}) or {}
            for name, payload in dict(construction).items():
                db.save_record("piece_construction", str(name), payload)
        except Exception as exc:  # pragma: no cover - GUI must keep running.
            db_error = str(exc)

    return {
        "pieces": report.get("pieces", {}),
        "masse_pieces_kg": dict(report.get("synthese", {}) or {}).get("masse_pieces_kg"),
        "construction_pieces": report.get("construction_pieces", {}),
        "rapports_pieces": report.get("rapports_pieces", {}),
        "objets_serialises": report.get("objets_serialises", {}),
        "inconnues": report.get("inconnues", {}),
        "notes_modele": report.get("notes_modele", []),
        "db_error": db_error,
    }

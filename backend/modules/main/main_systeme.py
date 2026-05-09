# backend/modules/main/main_systeme.py
# Orchestrateur des modules backend/modules/systeme
#
# Objectif :
# - Offrir une API de haut niveau pour concevoir un systeme SHSE-M complet
#   a partir d'une puissance cible.
# - Integrer la logique de selection automatique du "pire carburant".
# - Piloter l'analyse de puissance, la generation de chaine de traction
#   et le dimensionnement mecanique des pieces.

from __future__ import annotations
import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Mapping

# Preparation du chemin pour les imports backend
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[3]  # SHSE-M root
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

# Imports des modules systeme
try:
    from backend.modules.systeme.analyse_puissance_sortie import (
        analyser_puissance_sortie,
        optimiser_puissance_sortie,
        normaliser_puissance
    )
    from backend.modules.systeme.system_generator import DriveChainGenerator
    from backend.modules.systeme.orchestrateur_pieces import (
        enrichir_rapport_puissance_avec_pieces,
        extraire_rapports_pieces_composants
    )
    from backend.modules.systeme.database import SecureDatabase
except ImportError as e:
    print(f"Erreur d'importation dans main_systeme.py : {e}")
    # On laisse les exceptions remonter ou on definit des placeholders
    raise

# Import de l'ensemble (moteur thermique, carburant)
try:
    from backend.ensemble.carburant import get_pire_carburant
    from backend.components.moteur_thermique.moteur_thermique import OrchestrateurMoteurThermique
except ImportError:
    get_pire_carburant = None
    OrchestrateurMoteurThermique = None

class MainSystemeOrchestrator:
    """
    Pilote principal pour la conception automatisée du système hybride.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db = SecureDatabase(db_path=db_path) if db_path else SecureDatabase()
        self.generator = DriveChainGenerator()

    def concevoir_systeme_complet(
        self,
        puissance_cible: float,
        unite: str = "kw",
        *,
        carburant_nom: Optional[str] = None,
        max_iterations_assemblage: int = 3,
        espace_recherche: Optional[Dict[str, Any]] = None,
        contraintes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute le pipeline complet :
        1. Normalisation de la puissance
        2. Generation de la chaine de traction (P_moteur, Batterie, etc.)
        3. Optimisation des parametres moteur (RPM, Cylindres)
        4. Dimensionnement detaille des pieces (moteur thermique)
        5. Sauvegarde en base de donnees securisee
        """
        # 1. Normalisation
        p_norm = normaliser_puissance(puissance_cible, unite)
        p_cible_w = float(p_norm["w"])

        # 2. Chaine de traction
        # On deduit les besoins des composants (Alternateur, Batterie...)
        drivetrain = self.generator.compute(p_cible_w / 1000.0)
        p_meca_moteur_w = float(p_cible_w / 0.90) # Approximation rendement alternateur si non precisé

        # 3. Choix du carburant (Pire cas si non defini)
        carburant_final = None
        if carburant_nom:
            # Ici on pourrait chercher dans la bibliotheque
            pass
        
        if not carburant_final and get_pire_carburant:
            carburant_final = get_pire_carburant(critere="puissance")
        
        # 4. Optimisation architecture moteur
        # On cherche la meilleure combinaison RPM / Cylindres pour la puissance mecanique requise
        donnees_connues = {
            "puissance_moteur_thermique_w": p_meca_moteur_w,
        }
        
        if carburant_final:
            donnees_connues["pci_j_kg"] = getattr(carburant_final, "pci_j_kg", None)
            donnees_connues["afr_st"] = getattr(carburant_final, "afr_stoechiometrique", None)

        opt_report = optimiser_puissance_sortie(
            puissance=p_meca_moteur_w,
            unite="w",
            donnees_connues=donnees_connues,
            espace_recherche=espace_recherche,
            contraintes=contraintes
        )

        # 5. Dimensionnement des pieces et assemblage
        # On enrichit le rapport d'optimisation avec le design detaille des pieces
        final_report = enrichir_rapport_puissance_avec_pieces(opt_report)
        
        # Ajout des infos de chaine de traction
        final_report["drivetrain"] = drivetrain
        
        if carburant_final:
            final_report.setdefault("notes_modele", []).append(
                f"Dimensionnement effectue avec le carburant : {carburant_final.nom}"
            )

        # 6. Archivage
        if hasattr(self.db, "save_full_report"):
             self.db.save_full_report(final_report)
        
        return final_report

def main():
    """Point d'entree CLI pour test rapide."""
    import argparse
    parser = argparse.ArgumentParser(description="SHSE-M System Orchestrator")
    parser.add_argument("puissance", type=float, help="Puissance cible")
    parser.add_argument("--unite", default="kw", help="Unite (kw, hp, cv...)")
    
    args = parser.parse_args()
    
    orchestrator = MainSystemeOrchestrator()
    print(f"--- Conception systeme pour {args.puissance} {args.unite} ---")
    
    try:
        report = orchestrator.concevoir_systeme_complet(args.puissance, args.unite)
        print("\n--- Synthese du systeme ---")
        synthese = report.get("orchestration_pieces", {}).get("resume", {})
        if not synthese:
             print("Attention : Pas de synthese de pieces disponible.")
        else:
             for k, v in synthese.items():
                 print(f" - {k}: {v}")
        
        print(f"\nDonnees sauvegardees dans : {orchestrator.db.db_path}")
        
    except Exception as e:
        print(f"Erreur fatale : {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
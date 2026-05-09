from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable, Protocol

# =============================================================================
# Types et Dataclasses
# =============================================================================

@dataclass
class AssemblyIssue:
    piece_a: str
    piece_b: str
    regle: str
    valeur_a: Any
    valeur_b: Any
    message: str
    gravite: str = "erreur"  # erreur, avertissement
    parametre_correcteur: Dict[str, Any] = field(default_factory=dict)

class PieceLike(Protocol):
    def analyser(self, *, strict: bool = False) -> Dict[str, Any]: ...

# =============================================================================
# Vérificateur d'Assemblage Géo-Mécanique
# =============================================================================

class VerificateurAssemblage:
    """
    Module spécialisé pour vérifier la cohérence géométrique et mécanique
    entre les pièces du moteur thermique.
    
    Il identifie les points de blocage (ex: piston plus gros que l'alésage)
    et propose des corrections pour relancer le dimensionnement.
    """

    def __init__(
        self,
        rapports_pieces: Dict[str, Dict[str, Any]],
        pieces_instances: Optional[Dict[str, Any]] = None
    ):
        self.rapports = rapports_pieces
        self.instances = pieces_instances or {}
        self.issues: List[AssemblyIssue] = []

    def verifier_tout(self) -> List[AssemblyIssue]:
        """Exécute l'ensemble des règles de vérification d'assemblage."""
        self.issues = []
        
        # 1. Cylindre vs Piston
        self._check_cylindre_piston()
        
        # 2. Piston vs Arbre Piston (Axe)
        self._check_piston_axe()
        
        # 3. Arbre Piston vs Bielle (Petite Tête)
        self._check_axe_bielle()
        
        # 4. Bielle vs Vilebrequin (Grande Tête)
        self._check_bielle_vilebrequin()
        
        # 5. Cylindre vs Couvercle
        self._check_cylindre_couvercle()

        return self.issues

    # -------------------------------------------------------------------------
    # Règles de vérification
    # -------------------------------------------------------------------------

    def _check_cylindre_piston(self):
        cyl = self.rapports.get("cylindre")
        pis = self.rapports.get("piston")
        if not cyl or not pis: return

        alesage = cyl.get("entrees", {}).get("alesage_m") or cyl.get("geometrie", {}).get("alesage_m")
        diam_piston = pis.get("geometrie", {}).get("diametre_piston_m") or pis.get("entrees", {}).get("alesage_m")

        if alesage and diam_piston:
            if diam_piston > alesage:
                self.issues.append(AssemblyIssue(
                    piece_a="cylindre", piece_b="piston",
                    regle="Diamètre Piston <= Alésage Cylindre",
                    valeur_a=alesage, valeur_b=diam_piston,
                    message=f"Le piston ({diam_piston*1000:.2f}mm) est plus large que l'alésage ({alesage*1000:.2f}mm).",
                    parametre_correcteur={"alesage_m": diam_piston + 0.0001} # On suggère d'agrandir le cylindre
                ))

    def _check_piston_axe(self):
        pis = self.rapports.get("piston")
        axe = self.rapports.get("arbre_piston")
        if not pis or not axe: return

        diam_logement = pis.get("geometrie", {}).get("diametre_axe_m")
        diam_axe = axe.get("geometrie", {}).get("diametre_exterieur_m")

        if diam_logement and diam_axe:
            if not math.isclose(diam_logement, diam_axe, rel_tol=1e-4):
                self.issues.append(AssemblyIssue(
                    piece_a="piston", piece_b="arbre_piston",
                    regle="Coaxialité Axe/Logement",
                    valeur_a=diam_logement, valeur_b=diam_axe,
                    message=f"L'axe ({diam_axe*1000:.2f}mm) ne correspond pas au logement piston ({diam_logement*1000:.2f}mm).",
                    parametre_correcteur={"diametre_axe_m": diam_logement}
                ))

    def _check_axe_bielle(self):
        axe = self.rapports.get("arbre_piston")
        bie = self.rapports.get("bielle")
        if not axe or not bie: return

        diam_axe = axe.get("geometrie", {}).get("diametre_exterieur_m")
        diam_small_end = bie.get("geometrie", {}).get("diametre_axe_piston_m")

        if diam_axe and diam_small_end:
            if not math.isclose(diam_axe, diam_small_end, rel_tol=1e-4):
                self.issues.append(AssemblyIssue(
                    piece_a="arbre_piston", piece_b="bielle",
                    regle="Axe Piston vs Petite Tête Bielle",
                    valeur_a=diam_axe, valeur_b=diam_small_end,
                    message=f"La bielle attend un axe de {diam_small_end*1000:.2f}mm, reçu {diam_axe*1000:.2f}mm.",
                    parametre_correcteur={"diametre_axe_piston_m": diam_axe}
                ))

    def _check_bielle_vilebrequin(self):
        bie = self.rapports.get("bielle")
        vil = self.rapports.get("vilbrequin")
        if not bie or not vil: return

        diam_big_end = bie.get("geometrie", {}).get("diametre_maneton_m")
        diam_maneton = vil.get("geometrie", {}).get("diametre_maneton_m")

        if diam_big_end and diam_maneton:
            if not math.isclose(diam_big_end, diam_maneton, rel_tol=1e-4):
                self.issues.append(AssemblyIssue(
                    piece_a="bielle", piece_b="vilbrequin",
                    regle="Grande Tête Bielle vs Maneton Vilebrequin",
                    valeur_a=diam_big_end, valeur_b=diam_maneton,
                    message=f"Le vilebrequin a un maneton de {diam_maneton*1000:.2f}mm, bielle attend {diam_big_end*1000:.2f}mm.",
                    parametre_correcteur={"diametre_maneton_m": diam_big_end}
                ))

    def _check_cylindre_couvercle(self):
        cyl = self.rapports.get("cylindre")
        cov = self.rapports.get("couvercle_cylindre")
        if not cyl or not cov: return

        d_ext_cyl = cyl.get("geometrie", {}).get("diametre_exterieur_m")
        d_cov = cov.get("geometrie", {}).get("diametre_exterieur_m")

        if d_ext_cyl and d_cov:
            if d_cov < d_ext_cyl:
                self.issues.append(AssemblyIssue(
                    piece_a="cylindre", piece_b="couvercle_cylindre",
                    regle="Diamètre Couvercle >= Diamètre Cylindre",
                    valeur_a=d_ext_cyl, valeur_b=d_cov,
                    message=f"Le couvercle ({d_cov*1000:.2f}mm) est trop petit pour le cylindre ({d_ext_cyl*1000:.2f}mm).",
                    parametre_correcteur={"diametre_exterieur_m": d_ext_cyl}
                ))

    # -------------------------------------------------------------------------
    # Résolution et Boucle Récursive
    # -------------------------------------------------------------------------

    def resoudre_et_relancer(
        self,
        parametres_initiaux: Dict[str, Any],
        callback_dimensionnement: Callable[[Dict[str, Any]], Dict[str, Dict[str, Any]]],
        max_iterations: int = 3
    ) -> Tuple[Dict[str, Dict[str, Any]], List[AssemblyIssue]]:
        """
        Tente de résoudre les conflits d'assemblage en relançant le calcul
        avec les paramètres corrigés.
        """
        current_params = dict(parametres_initiaux)
        current_reports = self.rapports
        
        for i in range(max_iterations):
            self.rapports = current_reports
            issues = self.verifier_tout()
            
            if not issues:
                return current_reports, []

            # On agrège les corrections
            corrections = {}
            for issue in issues:
                if issue.parametre_correcteur:
                    corrections.update(issue.parametre_correcteur)
            
            if not corrections:
                break # Aucune correction possible automatique
                
            # Mise à jour des paramètres et relance
            current_params.update(corrections)
            print(f"[VERIFICATEUR] Relance calcul itération {i+1} avec: {corrections}")
            current_reports = callback_dimensionnement(current_params)
            
        return current_reports, self.issues

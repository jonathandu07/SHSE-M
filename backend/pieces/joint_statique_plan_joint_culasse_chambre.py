# backend\pieces\joint_statique_plan_joint_culasse_chambre.py

"""
Pièce: joint_statique_plan_joint_culasse_chambre
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'joint_statique_plan_joint_culasse_chambre'.\"\"\"

    def __init__(self):
        self.nom = "joint_statique_plan_joint_culasse_chambre"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
